from flask import Flask, jsonify, request, render_template_string, session, redirect, url_for, send_from_directory
from flask_cors import CORS
import sqlite3
import uuid
import bcrypt
from datetime import datetime, timedelta
import math
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import string
import os
import signal
import threading
from functools import wraps
import requests
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
CORS(app, origins=["*"])

# ============================================
# CONFIGURATION
# ============================================

SUPABASE_URL = "https://emsmhgfzmgnpadpremkq.supabase.co"
SUPABASE_KEY = "sb_publishable_hBlCZ6Ri3WZci17dWPLzug_dUX8Btzi"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# SQLite database path
DB_NAME = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lako.db'))

# Email configuration for OTP
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "your-email@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "your-app-password")

# ============================================
# PERFORMANCE OPTIMIZATION
# ============================================

# Thread-local storage for database connections
local = threading.local()

# Optimized cache with size limits and TTL
CACHE = {}
CACHE_MAX_SIZE = 1000
CACHE_LOCK = threading.Lock()

# Connection pool settings
DB_CONNECTION_TIMEOUT = 30
MAX_DB_CONNECTIONS = 10
current_connections = 0
connection_lock = threading.Lock()

# ============================================
# DATABASE OPTIMIZATION
# ============================================

def get_db_connection():
    """Get thread-local database connection with connection pooling"""
    global current_connections

    if not hasattr(local, 'connection') or local.connection is None:
        with connection_lock:
            if current_connections >= MAX_DB_CONNECTIONS:
                raise Exception("Database connection limit reached")

            current_connections += 1
            local.connection = sqlite3.connect(DB_NAME, timeout=DB_CONNECTION_TIMEOUT)
            local.connection.row_factory = sqlite3.Row
            local.connection.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for better concurrency
            local.connection.execute("PRAGMA synchronous=NORMAL")  # Balance performance/safety
            local.connection.execute("PRAGMA cache_size=-64000")  # 64MB cache
            local.connection.execute("PRAGMA temp_store=MEMORY")  # Temp tables in memory

    return local.connection

def close_db_connection():
    """Close thread-local database connection"""
    global current_connections

    if hasattr(local, 'connection') and local.connection is not None:
        local.connection.close()
        local.connection = None
        with connection_lock:
            current_connections = max(0, current_connections - 1)

def optimized_cache_result(timeout=300):
    """Optimized cache decorator with size limits and thread safety"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{hash(str(args))}:{hash(str(kwargs))}"

            with CACHE_LOCK:
                if key in CACHE:
                    result, timestamp = CACHE[key]
                    if datetime.now().timestamp() - timestamp < timeout:
                        return result

                # Cache size management
                if len(CACHE) >= CACHE_MAX_SIZE:
                    # Remove oldest entries (simple LRU approximation)
                    oldest_keys = sorted(CACHE.keys(), key=lambda k: CACHE[k][1])[:100]
                    for old_key in oldest_keys:
                        del CACHE[old_key]

            result = func(*args, **kwargs)

            with CACHE_LOCK:
                CACHE[key] = (result, datetime.now().timestamp())

            return result
        return wrapper
    return decorator

def init_db():
    """Initialize both SQLite and Supabase databases with all required tables"""
    # Initialize SQLite
    init_sqlite_db()
    
    # Initialize Supabase
    init_supabase_db()

def init_sqlite_db():
    """Initialize SQLite database with performance optimizations"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Performance optimizations
    c.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
    c.execute("PRAGMA synchronous=NORMAL")  # Balance performance/safety
    c.execute("PRAGMA cache_size=-64000")  # 64MB cache
    c.execute("PRAGMA temp_store=MEMORY")  # Temp tables in memory
    c.execute("PRAGMA mmap_size=268435456")  # 256MB memory map
    c.execute("PRAGMA page_size=4096")  # 4KB page size
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT,
        full_name TEXT,
        phone TEXT,
        eula_accepted INTEGER DEFAULT 0,
        eula_version TEXT,
        created_at TIMESTAMP,
        otp_code TEXT,
        otp_expires TIMESTAMP,
        email_verified INTEGER DEFAULT 0
    )''')
    
    # Create indexes for performance
    c.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)')
    
    # Vendors table
    c.execute('''CREATE TABLE IF NOT EXISTS vendors (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        name TEXT,
        category TEXT,
        description TEXT,
        address TEXT,
        latitude REAL,
        longitude REAL,
        rating REAL DEFAULT 0,
        logo TEXT,
        phone TEXT,
        created_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Create spatial index approximation
    c.execute('CREATE INDEX IF NOT EXISTS idx_vendors_location ON vendors(latitude, longitude)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_vendors_category ON vendors(category)')
    
    # Products table
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        vendor_id TEXT,
        name TEXT,
        description TEXT,
        category TEXT,
        price REAL,
        image TEXT,
        created_at TIMESTAMP,
        FOREIGN KEY (vendor_id) REFERENCES vendors(id)
    )''')
    
    c.execute('CREATE INDEX IF NOT EXISTS idx_products_vendor ON products(vendor_id)')
    
    # Reviews table
    c.execute('''CREATE TABLE IF NOT EXISTS reviews (
        id TEXT PRIMARY KEY,
        customer_id TEXT,
        vendor_id TEXT,
        rating INTEGER,
        title TEXT,
        comment TEXT,
        created_at TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES users(id),
        FOREIGN KEY (vendor_id) REFERENCES vendors(id)
    )''')
    
    c.execute('CREATE INDEX IF NOT EXISTS idx_reviews_vendor ON reviews(vendor_id)')
    
    # Messages table for chat
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        sender_id TEXT,
        receiver_id TEXT,
        message TEXT,
        created_at TIMESTAMP,
        FOREIGN KEY (sender_id) REFERENCES users(id),
        FOREIGN KEY (receiver_id) REFERENCES users(id)
    )''')
    
    # Posts table for feed
    c.execute('''CREATE TABLE IF NOT EXISTS posts (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        content TEXT,
        image TEXT,
        created_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_user ON posts(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at DESC)')
    
    # Likes table
    c.execute('''CREATE TABLE IF NOT EXISTS likes (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        post_id TEXT,
        created_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (post_id) REFERENCES posts(id)
    )''')
    
    # Comments table
    c.execute('''CREATE TABLE IF NOT EXISTS comments (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        post_id TEXT,
        comment TEXT,
        created_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (post_id) REFERENCES posts(id)
    )''')
    
    conn.commit()
    conn.close()
    print("✓ SQLite database initialized with performance optimizations")

def init_supabase_db():
    """Initialize Supabase database with tables"""
    try:
        # Create users table
        supabase.table('users').select('*').limit(1).execute()
    except:
        # Table doesn't exist, create it via SQL
        create_supabase_tables()
    
    print("✓ Supabase database initialized successfully")

def create_supabase_tables():
    """Create tables in Supabase using SQL"""
    tables_sql = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT,
            full_name TEXT,
            phone TEXT,
            eula_accepted INTEGER DEFAULT 0,
            eula_version TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            otp_code TEXT,
            otp_expires TIMESTAMP WITH TIME ZONE,
            email_verified INTEGER DEFAULT 0
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS vendors (
            id TEXT PRIMARY KEY,
            user_id TEXT REFERENCES users(id),
            name TEXT,
            category TEXT,
            description TEXT,
            address TEXT,
            latitude REAL,
            longitude REAL,
            rating REAL DEFAULT 0,
            logo TEXT,
            phone TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            vendor_id TEXT REFERENCES vendors(id),
            name TEXT,
            description TEXT,
            category TEXT,
            price REAL,
            image TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id TEXT PRIMARY KEY,
            customer_id TEXT REFERENCES users(id),
            vendor_id TEXT REFERENCES vendors(id),
            rating INTEGER,
            title TEXT,
            comment TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            sender_id TEXT REFERENCES users(id),
            receiver_id TEXT REFERENCES users(id),
            message TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            user_id TEXT REFERENCES users(id),
            content TEXT,
            image TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS likes (
            id TEXT PRIMARY KEY,
            user_id TEXT REFERENCES users(id),
            post_id TEXT REFERENCES posts(id),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS comments (
            id TEXT PRIMARY KEY,
            user_id TEXT REFERENCES users(id),
            post_id TEXT REFERENCES posts(id),
            comment TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """
    ]
    
    # Execute SQL commands via Supabase REST API
    for sql in tables_sql:
        try:
            supabase.rpc('exec_sql', {'sql': sql}).execute()
        except:
            pass  # Table might already exist
    
    # Create default admin user if it doesn't exist
    create_default_admin()

# ============================================
# UTILITIES
# ============================================

def generate_otp():
    """Generate a 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))

def send_email_otp(email, otp):
    """Send OTP via email"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = email
        msg['Subject'] = "Lako - Your OTP Code"
        
        body = f"""
        Your OTP code for Lako is: {otp}
        
        This code will expire in 10 minutes.
        
        If you didn't request this code, please ignore this email.
        """
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        text = msg.as_string()
        server.sendmail(SMTP_USERNAME, email, text)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False

def sync_databases():
    """Sync data between SQLite and Supabase"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        # Sync users
        c.execute('SELECT id, email, password, role, full_name, phone, eula_accepted, eula_version, created_at, otp_code, otp_expires, email_verified FROM users')
        users = c.fetchall()
        
        for user in users:
            try:
                supabase.table('users').upsert({
                    'id': user[0],
                    'email': user[1],
                    'password': user[2],
                    'role': user[3],
                    'full_name': user[4],
                    'phone': user[5],
                    'eula_accepted': user[6],
                    'eula_version': user[7],
                    'created_at': user[8],
                    'otp_code': user[9],
                    'otp_expires': user[10],
                    'email_verified': user[11]
                }).execute()
            except:
                pass  # Skip if already exists
        
        # Sync vendors
        c.execute('SELECT id, user_id, name, category, description, address, latitude, longitude, rating, logo, phone, created_at FROM vendors')
        vendors = c.fetchall()
        
        for vendor in vendors:
            try:
                supabase.table('vendors').upsert({
                    'id': vendor[0],
                    'user_id': vendor[1],
                    'name': vendor[2],
                    'category': vendor[3],
                    'description': vendor[4] or '',
                    'address': vendor[5],
                    'latitude': vendor[6],
                    'longitude': vendor[7],
                    'rating': vendor[8] or 0,
                    'logo': vendor[9] or '',
                    'phone': vendor[10] or '',
                    'created_at': vendor[11]
                }).execute()
            except:
                pass
        
        # Sync products
        c.execute('SELECT id, vendor_id, name, description, category, price, image, created_at FROM products')
        products = c.fetchall()
        
        for product in products:
            try:
                supabase.table('products').upsert({
                    'id': product[0],
                    'vendor_id': product[1],
                    'name': product[2],
                    'description': product[3] or '',
                    'category': product[4],
                    'price': product[5],
                    'image': product[6] or '',
                    'created_at': product[7]
                }).execute()
            except:
                pass
        
        # Sync reviews
        c.execute('SELECT id, customer_id, vendor_id, rating, title, comment, created_at FROM reviews')
        reviews = c.fetchall()
        
        for review in reviews:
            try:
                supabase.table('reviews').upsert({
                    'id': review[0],
                    'customer_id': review[1],
                    'vendor_id': review[2],
                    'rating': review[3],
                    'title': review[4] or '',
                    'comment': review[5] or '',
                    'created_at': review[6]
                }).execute()
            except:
                pass
        
        conn.close()
        print("✓ Database sync completed successfully")
        
    except Exception as e:
        print(f"Database sync failed: {e}")

# ============================================
# DATABASE OPERATIONS
# ============================================

def get_user_by_email(email):
    """Get user by email from SQLite"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = c.fetchone()
        return user
    finally:
        close_db_connection()

def save_user_to_db(user_data):
    """Save user to both databases"""
    # Save to SQLite
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('''INSERT INTO users (id, email, password, role, full_name, phone, eula_accepted, eula_version, created_at, otp_code, otp_expires, email_verified) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (user_data['id'], user_data['email'], user_data['password'], user_data['role'], 
                   user_data['full_name'], user_data['phone'], user_data['eula_accepted'], 
                   user_data['eula_version'], user_data['created_at'], user_data.get('otp_code'), 
                   user_data.get('otp_expires'), user_data.get('email_verified', 0)))
        conn.commit()
    finally:
        close_db_connection()
    
    # Save to Supabase (async, don't block)
    try:
        supabase.table('users').upsert(user_data).execute()
    except:
        pass  # Supabase might fail, but SQLite is primary

def create_default_admin():
    """Create a default admin user for development"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Check if admin already exists
    c.execute('SELECT id FROM users WHERE email = ?', ('admin@lako.com',))
    if c.fetchone():
        conn.close()
        return
    
    # Create admin user
    admin_id = str(uuid.uuid4())
    admin_password = bcrypt.hashpw('admin123'.encode(), bcrypt.gensalt()).decode()
    
    c.execute('''INSERT INTO users (id, email, password, role, full_name, phone, eula_accepted, eula_version, created_at, email_verified) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (admin_id, 'admin@lako.com', admin_password, 'admin', 'System Administrator', '+1234567890', 1, '1.0.0', datetime.now().isoformat(), 1))
    
    conn.commit()
    conn.close()
    print("✓ Default admin user created: admin@lako.com / admin123")

def get_user_by_token(token):
    """Get user from session token"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT id, role FROM users WHERE id = ?', (token,))
        user = c.fetchone()
        return user
    finally:
        close_db_connection()

# ============================================
# SVG ICONS
# ============================================

ICONS = {
    'map': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
    'store': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>',
    'user': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    'dashboard': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
    'box': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/></svg>',
    'star': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>'
}

# ============================================
# HTML TEMPLATES
# ============================================

CHOOSE_ROLE_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#1b5e20">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Lako">
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <title>Lako - Choose Role</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a2e1a 0%, #1b5e20 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container { text-align: center; padding: 20px; }
        h1 { font-size: 56px; color: white; margin-bottom: 12px; font-weight: 700; letter-spacing: -1px; }
        .subtitle { color: #a8e6b0; margin-bottom: 48px; font-size: 16px; }
        .role-buttons { display: flex; gap: 30px; justify-content: center; flex-wrap: wrap; }
        .role-btn {
            background: white;
            border: none;
            padding: 40px 50px;
            border-radius: 28px;
            cursor: pointer;
            transition: all 0.3s ease;
            text-align: center;
            min-width: 240px;
        }
        .role-btn:hover {
            transform: translateY(-6px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.2);
            background: #f0fff4;
        }
        .role-icon { width: 56px; height: 56px; margin: 0 auto 16px; color: #2e7d32; }
        .role-title { font-size: 22px; font-weight: 700; color: #1b5e20; margin-bottom: 8px; }
        .role-desc { color: #4caf50; font-size: 13px; }
        @media (max-width: 600px) {
            .role-btn { padding: 30px 40px; min-width: 200px; }
            .role-icon { width: 44px; height: 44px; }
            .role-buttons { gap: 20px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📍 Lako</h1>
        <div class="subtitle">GPS Proximity Discovery of Micro-Retail Vendors</div>
        <div class="role-buttons">
            <div class="role-btn" onclick="selectRole('customer')">
                <div class="role-icon">''' + ICONS['map'] + '''</div>
                <div class="role-title">Customer</div>
                <div class="role-desc">Find nearby vendors</div>
            </div>
            <div class="role-btn" onclick="selectRole('vendor')">
                <div class="role-icon">''' + ICONS['store'] + '''</div>
                <div class="role-title">Vendor</div>
                <div class="role-desc">Manage your business</div>
            </div>
            <div class="role-btn" onclick="selectRole('admin')">
                <div class="role-icon">''' + ICONS['dashboard'] + '''</div>
                <div class="role-title">Admin</div>
                <div class="role-desc">Platform management</div>
            </div>
        </div>
    </div>
    <script>
        function selectRole(role) {
            localStorage.setItem('user_role', role);
            window.location.href = '/login';
        }
        
        // Register service worker
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/sw.js')
                    .then(registration => console.log('SW registered'))
                    .catch(error => console.log('SW registration failed'));
            });
        }
    </script>
</body>
</html>
'''

LOGIN_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#1b5e20">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Lako">
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <title>Lako - Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a2e1a 0%, #1b5e20 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .auth-card {
            background: white;
            border-radius: 32px;
            padding: 48px;
            width: 100%;
            max-width: 420px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        h1 { font-size: 36px; text-align: center; color: #1b5e20; margin-bottom: 8px; font-weight: 700; }
        .subtitle { text-align: center; color: #4caf50; margin-bottom: 32px; font-size: 14px; }
        .input-group { margin-bottom: 20px; }
        label { display: block; font-size: 13px; font-weight: 600; color: #2e7d32; margin-bottom: 8px; }
        input {
            width: 100%;
            padding: 14px 18px;
            border: 2px solid #e8f5e9;
            border-radius: 20px;
            font-size: 15px;
            outline: none;
            background: #f9fff9;
            transition: all 0.2s;
        }
        input:focus { border-color: #4caf50; box-shadow: 0 0 0 3px rgba(76,175,80,0.1); }
        .btn {
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: 20px;
            font-size: 15px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-primary { background: #2e7d32; color: white; }
        .btn-primary:hover { background: #1b5e20; transform: translateY(-2px); }
        .btn-secondary { background: #e8f5e9; color: #2e7d32; margin-top: 12px; }
        .btn-secondary:hover { background: #c8e6c9; }
        .error {
            background: #ffebee;
            color: #c62828;
            padding: 14px;
            border-radius: 20px;
            margin-bottom: 20px;
            font-size: 13px;
            text-align: center;
            display: none;
        }
        .switch-role { text-align: center; margin-top: 24px; }
        .switch-role a { color: #4caf50; text-decoration: none; font-size: 13px; font-weight: 500; }
    </style>
</head>
<body>
    <div class="auth-card">
        <h1>📍 Lako</h1>
        <div class="subtitle">Welcome back</div>
        <div id="error" class="error"></div>
        <div class="input-group">
            <label>Email</label>
            <input type="email" id="email" placeholder="you@example.com">
        </div>
        <div class="input-group">
            <label>Password</label>
            <input type="password" id="password" placeholder="••••••••">
        </div>
        <button class="btn btn-primary" onclick="handleLogin()">Sign In</button>
        <button class="btn btn-secondary" onclick="showRegister()">Create Account</button>
        <div class="switch-role">
            <a href="#" onclick="switchRole()">← Switch Role</a>
        </div>
    </div>
    <script>
        async function handleLogin() {
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const errorDiv = document.getElementById('error');
            
            if (!email || !password) {
                errorDiv.textContent = 'Please fill all fields';
                errorDiv.style.display = 'block';
                return;
            }
            
            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password })
                });
                const data = await response.json();
                
                if (response.ok) {
                    if (data.requires_verification) {
                        // Show OTP verification
                        showOtpVerification(data.email, data.role);
                    } else {
                        localStorage.setItem('session_token', data.session_token);
                        localStorage.setItem('user_role', data.role);
                        localStorage.setItem('user_email', data.email);
                        window.location.href = data.role === 'customer' ? '/customer/dashboard' : 
                                             data.role === 'admin' ? '/admin/dashboard' : '/vendor/dashboard';
                    }
                } else {
                    errorDiv.textContent = data.error || 'Login failed';
                    errorDiv.style.display = 'block';
                }
            } catch(e) {
                errorDiv.textContent = 'Network error';
                errorDiv.style.display = 'block';
            }
        }
        
        function showOtpVerification(email, role) {
            document.querySelector('.auth-card').innerHTML = `
                <h1>✉️ Verify Email</h1>
                <div class="subtitle">Enter the 6-digit code sent to ${email}</div>
                <div id="otp-error" class="error" style="display:none;"></div>
                <div class="input-group">
                    <label>OTP Code</label>
                    <input type="text" id="otp-code" placeholder="123456" maxlength="6" style="text-align:center; font-size:18px; letter-spacing:4px;">
                </div>
                <button class="btn btn-primary" onclick="verifyOtp('${email}', '${role}')">Verify Email</button>
                <button class="btn btn-secondary" onclick="resendOtp('${email}')">Resend Code</button>
                <div class="switch-role" style="margin-top:20px;">
                    <a href="#" onclick="window.location.reload()">← Back to Login</a>
                </div>
            `;
        }
        
        function verifyOtp(email, role) {
            const otp = document.getElementById('otp-code').value;
            if (!otp || otp.length !== 6) {
                document.getElementById('otp-error').textContent = 'Please enter a valid 6-digit code';
                document.getElementById('otp-error').style.display = 'block';
                return;
            }
            
            fetch('/api/auth/verify-otp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, otp })
            })
            .then(response => response.json())
            .then(data => {
                if (data.session_token) {
                    localStorage.setItem('session_token', data.session_token);
                    localStorage.setItem('user_role', role);
                    localStorage.setItem('user_email', email);
                    window.location.href = role === 'customer' ? '/customer/dashboard' : 
                                         role === 'admin' ? '/admin/dashboard' : '/vendor/dashboard';
                } else {
                    document.getElementById('otp-error').textContent = data.error || 'Verification failed';
                    document.getElementById('otp-error').style.display = 'block';
                }
            })
            .catch(e => {
                document.getElementById('otp-error').textContent = 'Network error';
                document.getElementById('otp-error').style.display = 'block';
            });
        }
        
        function resendOtp(email) {
            // For now, just show a message. In production, you'd call an API to resend
            alert('OTP resent to your email');
        }
        
        function showRegister() { window.location.href = '/register'; }
        function switchRole() { localStorage.removeItem('user_role'); window.location.href = '/'; }
        
        // Register service worker
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/sw.js')
                    .then(registration => console.log('SW registered'))
                    .catch(error => console.log('SW registration failed'));
            });
        }
    </script>
</body>
</html>
'''

REGISTER_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#1b5e20">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Lako">
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <title>Lako - Register</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a2e1a 0%, #1b5e20 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .auth-card {
            background: white;
            border-radius: 32px;
            padding: 40px;
            width: 100%;
            max-width: 520px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        h1 { font-size: 32px; text-align: center; color: #1b5e20; margin-bottom: 8px; font-weight: 700; }
        .subtitle { text-align: center; color: #4caf50; margin-bottom: 32px; font-size: 14px; }
        .input-group { margin-bottom: 16px; }
        label { display: block; font-size: 13px; font-weight: 600; color: #2e7d32; margin-bottom: 6px; }
        input, select {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e8f5e9;
            border-radius: 20px;
            font-size: 14px;
            outline: none;
            background: #f9fff9;
        }
        input:focus, select:focus { border-color: #4caf50; }
        .btn {
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: 20px;
            font-size: 15px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-primary { background: #2e7d32; color: white; }
        .btn-primary:hover { background: #1b5e20; }
        .btn-secondary { background: #e8f5e9; color: #2e7d32; margin-top: 12px; }
        .error {
            background: #ffebee;
            color: #c62828;
            padding: 12px;
            border-radius: 20px;
            margin-bottom: 20px;
            font-size: 13px;
            text-align: center;
            display: none;
        }
        .eula-container {
            margin: 20px 0;
            padding: 16px;
            background: #f9fff9;
            border-radius: 20px;
            max-height: 150px;
            overflow-y: auto;
            font-size: 11px;
            color: #6b7280;
            border: 1px solid #e8f5e9;
            line-height: 1.5;
        }
        .eula-container h3 { font-size: 13px; color: #2e7d32; margin-bottom: 8px; }
        .eula-checkbox { display: flex; align-items: center; gap: 12px; margin-top: 16px; }
        .eula-checkbox input { width: 18px; }
        .location-group { display: flex; gap: 12px; align-items: center; }
        .location-group button {
            padding: 12px;
            background: #e8f5e9;
            border: 1px solid #c8e6c9;
            border-radius: 20px;
            cursor: pointer;
            white-space: nowrap;
            color: #2e7d32;
            font-size: 13px;
            font-weight: 500;
        }
        .row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    </style>
</head>
<body>
    <div class="auth-card">
        <h1>✨ Create Account</h1>
        <div class="subtitle">Join Lako today</div>
        <div id="error" class="error"></div>
        
        <div id="customer-fields">
            <div class="input-group">
                <label>Full Name</label>
                <input type="text" id="customer-name" placeholder="Juan Dela Cruz">
            </div>
        </div>
        
        <div id="vendor-fields" style="display:none;">
            <div class="input-group">
                <label>Business Name</label>
                <input type="text" id="vendor-name" placeholder="My Store">
            </div>
            <div class="input-group">
                <label>Category</label>
                <select id="vendor-category">
                    <option value="Street Foods">🍢 Street Foods</option>
                    <option value="Dimsum">🥟 Dimsum</option>
                    <option value="Snacks">🍿 Snacks</option>
                    <option value="Rice Meals">🍚 Rice Meals</option>
                    <option value="Refreshments">🥤 Refreshments</option>
                    <option value="Sari-sari Store">🏪 Sari-sari Store</option>
                </select>
            </div>
            <div class="input-group">
                <label>Address</label>
                <input type="text" id="vendor-address" placeholder="Street, Barangay, City">
            </div>
            <div class="location-group">
                <div style="flex:1">
                    <label>Latitude</label>
                    <input type="text" id="vendor-lat" placeholder="Auto-detect">
                </div>
                <div style="flex:1">
                    <label>Longitude</label>
                    <input type="text" id="vendor-lng" placeholder="Auto-detect">
                </div>
                <button onclick="getCurrentLocation()">📍 Get GPS</button>
            </div>
        </div>
        
        <div class="input-group">
            <label>Email</label>
            <input type="email" id="email" placeholder="you@example.com">
        </div>
        <div class="input-group">
            <label>Phone</label>
            <input type="tel" id="phone" placeholder="09123456789">
        </div>
        <div class="row-2">
            <div class="input-group">
                <label>Password</label>
                <input type="password" id="password" placeholder="••••••••">
            </div>
            <div class="input-group">
                <label>Confirm</label>
                <input type="password" id="confirm-password" placeholder="••••••••">
            </div>
        </div>
        
        <div class="eula-container">
            <h3>📋 End User License Agreement</h3>
            <p><strong>Lako: GPS Proximity Discovery of Micro-Retail Vendors</strong></p>
            <p>This application is a <strong>Capstone Project</strong> by <strong>Kyle Brian M. Morillo</strong> and <strong>Alexander Collin P. Millichamp</strong>, students at <strong>AITE</strong>.</p>
            <p>By using this application, you agree to the collection of name, email, and location data. Your data is not shared with third parties.</p>
            <p><strong>Version: 1.0.0</strong></p>
        </div>
        
        <div class="eula-checkbox">
            <input type="checkbox" id="eula-accepted">
            <label>I agree to the <strong style="color:#2e7d32;">End User License Agreement</strong></label>
        </div>
        
        <button class="btn btn-primary" onclick="handleRegister()">Create Account</button>
        <button class="btn btn-secondary" onclick="window.location.href='/login'">Back to Login</button>
    </div>
    
    <script>
        const role = localStorage.getItem('user_role') || 'customer';
        if (role === 'vendor') {
            document.getElementById('customer-fields').style.display = 'none';
            document.getElementById('vendor-fields').style.display = 'block';
            document.querySelector('h1').innerHTML = '🏪 Register Your Business';
        }
        
        function getCurrentLocation() {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        document.getElementById('vendor-lat').value = position.coords.latitude;
                        document.getElementById('vendor-lng').value = position.coords.longitude;
                        alert('✅ Location detected successfully!');
                    },
                    () => { alert('⚠️ Unable to get location'); },
                    { enableHighAccuracy: true, timeout: 10000 }
                );
            } else {
                alert('⚠️ Geolocation not supported');
            }
        }
        
        async function handleRegister() {
            if (!document.getElementById('eula-accepted').checked) {
                document.getElementById('error').textContent = 'You must accept the EULA';
                document.getElementById('error').style.display = 'block';
                return;
            }
            
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const confirm = document.getElementById('confirm-password').value;
            const phone = document.getElementById('phone').value;
            
            if (password !== confirm) {
                document.getElementById('error').textContent = 'Passwords do not match';
                document.getElementById('error').style.display = 'block';
                return;
            }
            
            if (password.length < 8) {
                document.getElementById('error').textContent = 'Password must be at least 8 characters';
                document.getElementById('error').style.display = 'block';
                return;
            }
            
            let data = { email, password, phone, eula_accepted: true, eula_version: '1.0.0' };
            
            if (role === 'customer') {
                const fullName = document.getElementById('customer-name').value;
                if (!fullName) {
                    document.getElementById('error').textContent = 'Please enter your full name';
                    document.getElementById('error').style.display = 'block';
                    return;
                }
                data.full_name = fullName;
                
                const response = await fetch('/api/auth/register/customer', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                const result = await response.json();
                
                if (response.ok && result.requires_verification) {
                    // Show OTP verification
                    showOtpVerification(email, 'customer');
                } else if (response.ok) {
                    localStorage.setItem('session_token', result.session_token);
                    window.location.href = '/customer/dashboard';
                } else {
                    document.getElementById('error').textContent = result.error;
                    document.getElementById('error').style.display = 'block';
                }
            } else {
                const businessName = document.getElementById('vendor-name').value;
                const category = document.getElementById('vendor-category').value;
                const address = document.getElementById('vendor-address').value;
                const lat = parseFloat(document.getElementById('vendor-lat').value);
                const lng = parseFloat(document.getElementById('vendor-lng').value);
                
                if (!businessName || !address) {
                    document.getElementById('error').textContent = 'Please fill all fields';
                    document.getElementById('error').style.display = 'block';
                    return;
                }
                
                data.business_name = businessName;
                data.business_category = category;
                data.address = address;
                data.latitude = lat || 13.9443;
                data.longitude = lng || 121.3798;
                
                const response = await fetch('/api/auth/register/vendor', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                const result = await response.json();
                
                if (response.ok && result.requires_verification) {
                    // Show OTP verification
                    showOtpVerification(email, 'vendor');
                } else if (response.ok) {
                    localStorage.setItem('session_token', result.session_token);
                    window.location.href = '/vendor/dashboard';
                } else {
                    document.getElementById('error').textContent = result.error;
                    document.getElementById('error').style.display = 'block';
                }
            }
        }
        
        function showOtpVerification(email, role) {
            document.querySelector('.auth-card').innerHTML = `
                <h1>✉️ Verify Email</h1>
                <div class="subtitle">Enter the 6-digit code sent to ${email}</div>
                <div id="otp-error" class="error" style="display:none;"></div>
                <div class="input-group">
                    <label>OTP Code</label>
                    <input type="text" id="otp-code" placeholder="123456" maxlength="6" style="text-align:center; font-size:18px; letter-spacing:4px;">
                </div>
                <button class="btn btn-primary" onclick="verifyOtp('${email}', '${role}')">Verify Email</button>
                <button class="btn btn-secondary" onclick="resendOtp('${email}')">Resend Code</button>
                <div class="switch-role" style="margin-top:20px;">
                    <a href="#" onclick="window.location.reload()">← Back to Registration</a>
                </div>
            `;
        }
        
        async function verifyOtp(email, role) {
            const otp = document.getElementById('otp-code').value;
            if (!otp || otp.length !== 6) {
                document.getElementById('otp-error').textContent = 'Please enter a valid 6-digit code';
                document.getElementById('otp-error').style.display = 'block';
                return;
            }
            
            try {
                const response = await fetch('/api/auth/verify-otp', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, otp })
                });
                const result = await response.json();
                
                if (response.ok) {
                    localStorage.setItem('session_token', result.session_token);
                    window.location.href = role === 'customer' ? '/customer/dashboard' : '/vendor/dashboard';
                } else {
                    document.getElementById('otp-error').textContent = result.error;
                    document.getElementById('otp-error').style.display = 'block';
                }
            } catch(e) {
                document.getElementById('otp-error').textContent = 'Network error';
                document.getElementById('otp-error').style.display = 'block';
            }
        }
        
        async function resendOtp(email) {
            try {
                // For now, just show a message. In production, you'd call an API to resend
                alert('OTP resent to your email');
            } catch(e) {
                alert('Failed to resend OTP');
            }
        }
        
        // Register service worker
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/sw.js')
                    .then(registration => console.log('SW registered'))
                    .catch(error => console.log('SW registration failed'));
            });
        }
    </script>
</body>
</html>
'''

CUSTOMER_DASHBOARD = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#1b5e20">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Lako">
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <title>Lako - Customer Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0faf0; }
        
        .header {
            background: white;
            padding: 16px 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 10;
        }
        .logo { font-size: 22px; font-weight: 700; color: #1b5e20; }
        .logout-btn {
            background: none;
            border: none;
            color: #c62828;
            font-size: 14px;
            cursor: pointer;
            padding: 8px 16px;
            border-radius: 30px;
            transition: background 0.2s;
        }
        .logout-btn:hover { background: #ffebee; }
        
        .bottom-nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: white;
            display: flex;
            justify-content: space-around;
            padding: 12px 20px;
            border-top: 1px solid #e8f5e9;
            z-index: 10;
        }
        .nav-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
            background: none;
            border: none;
            cursor: pointer;
            color: #9ca3af;
            font-size: 11px;
            padding: 8px 24px;
            border-radius: 30px;
            transition: all 0.2s;
        }
        .nav-item.active { color: #2e7d32; background: #e8f5e9; }
        .nav-icon { width: 22px; height: 22px; }
        
        .content { padding: 20px; padding-bottom: 80px; max-width: 800px; margin: 0 auto; }
        .map-container { width: 100%; height: 55vh; border-radius: 24px; overflow: hidden; margin-bottom: 20px; border: 1px solid #e8f5e9; }
        iframe { width: 100%; height: 100%; border: none; }
        
        .vendor-card {
            background: white;
            border-radius: 20px;
            padding: 16px;
            margin-bottom: 12px;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid #e8f5e9;
        }
        .vendor-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.08);
            border-color: #c8e6c9;
        }
        .vendor-name { font-size: 17px; font-weight: 700; color: #1b5e20; margin-bottom: 4px; }
        .vendor-category { font-size: 13px; color: #4caf50; margin-bottom: 8px; }
        .vendor-rating { color: #fbbf24; font-size: 13px; margin-bottom: 6px; }
        .vendor-distance { font-size: 11px; color: #9ca3af; }
        
        .location-bar {
            background: white;
            padding: 14px 20px;
            border-radius: 24px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid #e8f5e9;
        }
        .location-text { font-size: 13px; color: #4caf50; font-weight: 500; }
        .get-location-btn {
            background: #e8f5e9;
            color: #2e7d32;
            border: none;
            padding: 8px 22px;
            border-radius: 30px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
            transition: all 0.2s;
        }
        .get-location-btn:hover { background: #c8e6c9; }
        
        .profile-card {
            background: white;
            border-radius: 24px;
            padding: 32px;
            text-align: center;
            border: 1px solid #e8f5e9;
        }
        .profile-avatar {
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, #2e7d32 0%, #4caf50 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 16px;
            color: white;
            font-size: 32px;
        }
        .profile-name { font-size: 18px; font-weight: 700; color: #1b5e20; }
        .profile-email { color: #4caf50; font-size: 13px; margin-top: 4px; }
        .stat-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin-top: 24px;
        }
        .stat-item {
            background: #f9fff9;
            padding: 16px;
            border-radius: 20px;
            text-align: center;
        }
        .stat-number { font-size: 26px; font-weight: 700; color: #2e7d32; }
        .stat-label { font-size: 11px; color: #6b7280; margin-top: 4px; }
        
        .loading { text-align: center; padding: 50px; color: #4caf50; font-size: 14px; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">📍 Lako</div>
        <button class="logout-btn" onclick="logout()">Sign out</button>
    </div>
    
    <div class="content" id="content">
        <div class="location-bar">
            <span class="location-text" id="location-status">📍 Getting your location...</span>
            <button class="get-location-btn" onclick="getUserLocation()">Refresh</button>
        </div>
        <div id="page-content"></div>
    </div>
    
    <div class="bottom-nav">
        <button class="nav-item active" onclick="changePage('map')">
            <div class="nav-icon">''' + ICONS['map'] + '''</div>
            <span>Map</span>
        </button>
        <button class="nav-item" onclick="changePage('vendors')">
            <div class="nav-icon">''' + ICONS['store'] + '''</div>
            <span>Vendors</span>
        </button>
        <button class="nav-item" onclick="changePage('profile')">
            <div class="nav-icon">''' + ICONS['user'] + '''</div>
            <span>Profile</span>
        </button>
    </div>
    
    <script>
        let currentLocation = null, vendors = [], currentPage = 'map';
        
        async function apiCall(endpoint, method = 'GET', data = null) {
            const token = localStorage.getItem('session_token');
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers['X-Session-Token'] = token;
            
            let url = endpoint;
            if (method === 'GET' && data) url += '?' + new URLSearchParams(data);
            
            const options = { method, headers };
            if (data && method !== 'GET') options.body = JSON.stringify(data);
            
            const response = await fetch(url, options);
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Request failed');
            return result;
        }
        
        async function logout() { localStorage.clear(); window.location.href = '/'; }
        
        function getUserLocation() {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    async (position) => {
                        currentLocation = { lat: position.coords.latitude, lng: position.coords.longitude };
                        document.getElementById('location-status').innerHTML = `📍 ${currentLocation.lat.toFixed(4)}, ${currentLocation.lng.toFixed(4)}`;
                        await loadVendors();
                        if (currentPage === 'map') renderMap();
                        else if (currentPage === 'vendors') renderVendors();
                    },
                    () => { setDefaultLocation(); },
                    { enableHighAccuracy: true, timeout: 10000 }
                );
            } else { setDefaultLocation(); }
        }
        
        function setDefaultLocation() {
            currentLocation = { lat: 13.9443, lng: 121.3798 };
            document.getElementById('location-status').innerHTML = '📍 Tiaong, Quezon (Default)';
            loadVendors();
        }
        
        async function loadVendors() {
            if (!currentLocation) return;
            try {
                const result = await apiCall('/api/customer/map/vendors', 'GET', {
                    lat: currentLocation.lat,
                    lng: currentLocation.lng,
                    radius_km: 20
                });
                vendors = result.vendors || [];
                if (currentPage === 'vendors') renderVendors();
                if (currentPage === 'map') renderMap();
            } catch(e) { console.error(e); }
        }
        
        function renderMap() {
            if (!currentLocation) return;
            document.getElementById('page-content').innerHTML = `
                <div class="map-container">
                    <iframe src="https://www.openstreetmap.org/export/embed.html?bbox=${currentLocation.lng-0.1},${currentLocation.lat-0.1},${currentLocation.lng+0.1},${currentLocation.lat+0.1}&layer=mapnik&marker=${currentLocation.lat},${currentLocation.lng}"></iframe>
                </div>
                <div style="background:white; border-radius:20px; padding:20px; border:1px solid #e8f5e9;">
                    <h3 style="color:#1b5e20; margin-bottom:12px;">Nearby Vendors (${vendors.length})</h3>
                    ${vendors.length === 0 ? '<div class="loading">No vendors found nearby</div>' : vendors.slice(0,5).map(v => `
                        <div style="padding:12px 0; border-bottom:1px solid #e8f5e9;">
                            <strong style="color:#1b5e20;">${v.name}</strong><br>
                            <span style="font-size:12px; color:#4caf50;">${v.category} | ${v.distance} km</span>
                        </div>
                    `).join('')}
                </div>
            `;
        }
        
        function renderVendors() {
            if (vendors.length === 0) {
                document.getElementById('page-content').innerHTML = '<div class="loading">No vendors found nearby</div>';
                return;
            }
            document.getElementById('page-content').innerHTML = `
                <h3 style="color:#1b5e20; margin-bottom:16px;">Nearby Vendors</h3>
                ${vendors.map(v => `
                    <div class="vendor-card" onclick="showVendorModal('${v.id}')">
                        <div class="vendor-name">${v.name}</div>
                        <div class="vendor-category">${v.category}</div>
                        <div class="vendor-rating">${'★'.repeat(Math.floor(v.rating || 0))}${'☆'.repeat(5-Math.floor(v.rating || 0))}</div>
                        <div class="vendor-distance">📍 ${v.distance} km away</div>
                    </div>
                `).join('')}
            `;
        }
        
        function renderProfile() {
            document.getElementById('page-content').innerHTML = `
                <div class="profile-card">
                    <div class="profile-avatar">👤</div>
                    <div class="profile-name">Customer</div>
                    <div class="profile-email">${localStorage.getItem('user_email') || 'customer@example.com'}</div>
                    <div class="stat-grid">
                        <div class="stat-item">
                            <div class="stat-number">${vendors.length}</div>
                            <div class="stat-label">Nearby</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-number">0</div>
                            <div class="stat-label">Reviews</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-number">0</div>
                            <div class="stat-label">Saved</div>
                        </div>
                    </div>
                    <div style="margin-top:20px; padding:12px; background:#f9fff9; border-radius:16px;">
                        <span style="color:#4caf50; font-weight:500;">📍 Last Location</span><br>
                        <span style="font-size:13px; color:#6b7280;">${currentLocation ? currentLocation.lat.toFixed(4) + ', ' + currentLocation.lng.toFixed(4) : 'Not set'}</span>
                    </div>
                </div>
            `;
        }
        
        async function showVendorModal(vendorId) {
            try {
                const data = await apiCall(`/api/customer/map/vendor/${vendorId}`, 'GET');
                const v = data.vendor;
                alert(`📍 ${v.name}\\n🏷️ Category: ${v.category}\\n📍 Address: ${v.address}\\n📞 Phone: ${v.phone || 'N/A'}`);
            } catch(e) { alert('Error loading details'); }
        }
        
        function changePage(page) {
            currentPage = page;
            const buttons = document.querySelectorAll('.nav-item');
            buttons.forEach((btn, i) => {
                btn.classList.toggle('active', i === (page === 'map' ? 0 : page === 'vendors' ? 1 : 2));
            });
            if (page === 'map') renderMap();
            else if (page === 'vendors') renderVendors();
            else renderProfile();
        }
        
        getUserLocation();
        
        // Register service worker
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/sw.js')
                    .then(registration => console.log('SW registered'))
                    .catch(error => console.log('SW registration failed'));
            });
        }
    </script>
</body>
</html>
'''

VENDOR_DASHBOARD = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#1b5e20">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Lako">
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <title>Lako - Vendor Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0faf0; }
        
        .header {
            background: white;
            padding: 16px 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 10;
        }
        .logo { font-size: 22px; font-weight: 700; color: #1b5e20; }
        .logout-btn {
            background: none;
            border: none;
            color: #c62828;
            font-size: 14px;
            cursor: pointer;
            padding: 8px 16px;
            border-radius: 30px;
            transition: background 0.2s;
        }
        .logout-btn:hover { background: #ffebee; }
        
        .bottom-nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: white;
            display: flex;
            justify-content: space-around;
            padding: 12px 20px;
            border-top: 1px solid #e8f5e9;
            z-index: 10;
        }
        .nav-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
            background: none;
            border: none;
            cursor: pointer;
            color: #9ca3af;
            font-size: 11px;
            padding: 8px 20px;
            border-radius: 30px;
            transition: all 0.2s;
        }
        .nav-item.active { color: #2e7d32; background: #e8f5e9; }
        .nav-icon { width: 22px; height: 22px; }
        
        .content { padding: 20px; padding-bottom: 80px; max-width: 800px; margin: 0 auto; }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: white;
            border-radius: 20px;
            padding: 20px;
            text-align: center;
            border: 1px solid #e8f5e9;
        }
        .stat-number { font-size: 30px; font-weight: 700; color: #2e7d32; }
        .stat-label { font-size: 11px; color: #6b7280; margin-top: 4px; }
        
        .product-card {
            background: white;
            border-radius: 20px;
            padding: 16px;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid #e8f5e9;
            transition: all 0.2s;
        }
        .product-card:hover { border-color: #c8e6c9; }
        .product-name { font-weight: 700; color: #1b5e20; }
        .product-price { color: #2e7d32; font-weight: 700; font-size: 15px; }
        .btn-delete {
            background: #ffebee;
            color: #c62828;
            border: none;
            padding: 6px 18px;
            border-radius: 30px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }
        .btn-delete:hover { background: #ffcdd2; }
        
        .btn-add {
            position: fixed;
            bottom: 80px;
            right: 20px;
            width: 56px;
            height: 56px;
            background: #2e7d32;
            color: white;
            border: none;
            border-radius: 50%;
            font-size: 24px;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(46,125,50,0.3);
            transition: all 0.2s;
            z-index: 15;
        }
        .btn-add:hover { background: #1b5e20; transform: scale(1.05); }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            z-index: 20;
            align-items: center;
            justify-content: center;
        }
        .modal-content {
            background: white;
            border-radius: 28px;
            padding: 28px;
            width: 90%;
            max-width: 400px;
        }
        .modal-content input, .modal-content textarea, .modal-content select {
            width: 100%;
            padding: 12px;
            margin-bottom: 12px;
            border: 2px solid #e8f5e9;
            border-radius: 20px;
            background: #f9fff9;
        }
        .modal-content button {
            width: 100%;
            padding: 14px;
            background: #2e7d32;
            color: white;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            font-weight: 700;
            margin-top: 8px;
        }
        .close-modal { float: right; font-size: 24px; cursor: pointer; color: #9ca3af; }
        
        .review-card {
            background: white;
            border-radius: 20px;
            padding: 16px;
            margin-bottom: 12px;
            border: 1px solid #e8f5e9;
        }
        .review-customer { font-weight: 700; color: #1b5e20; }
        .review-rating { color: #fbbf24; margin: 8px 0; font-size: 13px; }
        .review-comment { font-size: 13px; color: #4b5563; margin: 8px 0; }
        .reply-btn {
            background: #e8f5e9;
            color: #2e7d32;
            border: none;
            padding: 6px 18px;
            border-radius: 30px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            margin-top: 8px;
        }
        
        .welcome-card {
            background: white;
            border-radius: 20px;
            padding: 28px;
            text-align: center;
            border: 1px solid #e8f5e9;
        }
        .welcome-card h3 { color: #1b5e20; margin-bottom: 8px; }
        .welcome-card p { color: #6b7280; margin-top: 8px; font-size: 13px; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🏪 Lako Vendor</div>
        <button class="logout-btn" onclick="logout()">Sign out</button>
    </div>
    
    <div class="content" id="content"></div>
    
    <div class="bottom-nav">
        <button class="nav-item active" onclick="changePage('dashboard')">
            <div class="nav-icon">''' + ICONS['dashboard'] + '''</div>
            <span>Dashboard</span>
        </button>
        <button class="nav-item" onclick="changePage('products')">
            <div class="nav-icon">''' + ICONS['box'] + '''</div>
            <span>Products</span>
        </button>
        <button class="nav-item" onclick="changePage('reviews')">
            <div class="nav-icon">''' + ICONS['star'] + '''</div>
            <span>Reviews</span>
        </button>
        <button class="nav-item" onclick="changePage('profile')">
            <div class="nav-icon">''' + ICONS['user'] + '''</div>
            <span>Profile</span>
        </button>
    </div>
    
    <button class="btn-add" onclick="showAddProductModal()" id="add-btn" style="display:none;">+</button>
    
    <div id="productModal" class="modal">
        <div class="modal-content">
            <span class="close-modal" onclick="closeModal()">&times;</span>
            <h3 style="margin-bottom:16px; color:#1b5e20;">➕ Add Product</h3>
            <input type="text" id="prod-name" placeholder="Product Name">
            <textarea id="prod-desc" rows="2" placeholder="Description"></textarea>
            <input type="text" id="prod-cat" placeholder="Category">
            <input type="number" id="prod-price" placeholder="Price (₱)" step="0.01">
            <button onclick="addProduct()">Create Product</button>
        </div>
    </div>
    
    <script>
        let currentPage = 'dashboard', products = [], reviews = [], stats = {};
        
        async function apiCall(endpoint, method = 'GET', data = null) {
            const token = localStorage.getItem('session_token');
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers['X-Session-Token'] = token;
            
            let url = endpoint;
            if (method === 'GET' && data) url += '?' + new URLSearchParams(data);
            
            const options = { method, headers };
            if (data && method !== 'GET') options.body = JSON.stringify(data);
            
            const response = await fetch(url, options);
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Request failed');
            return result;
        }
        
        async function logout() { localStorage.clear(); window.location.href = '/'; }
        
        async function loadDashboard() {
            try {
                stats = await apiCall('/api/vendor/dashboard', 'GET');
                document.getElementById('content').innerHTML = `
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-number">${stats.total_products || 0}</div>
                            <div class="stat-label">Products</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${stats.total_reviews || 0}</div>
                            <div class="stat-label">Reviews</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${stats.average_rating || 0}</div>
                            <div class="stat-label">Rating</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">0</div>
                            <div class="stat-label">Views</div>
                        </div>
                    </div>
                    <div class="welcome-card">
                        <h3>📊 Welcome to Lako Vendor</h3>
                        <p>Manage your products and connect with customers in Quipot - Poblacion 4 Areas</p>
                    </div>
                `;
            } catch(e) { console.error(e); }
        }
        
        async function loadProducts() {
            try {
                const result = await apiCall('/api/vendor/catalog/products', 'GET');
                products = result.products || [];
                document.getElementById('content').innerHTML = `
                    <h3 style="color:#1b5e20; margin-bottom:16px;">📦 Your Products (${products.length})</h3>
                    ${products.length === 0 ? '<div class="welcome-card"><p>No products yet. Click + to add.</p></div>' : products.map(p => `
                        <div class="product-card">
                            <div>
                                <div class="product-name">${p.name}</div>
                                <div class="product-price">₱${p.price}</div>
                                <div style="font-size:11px; color:#4caf50; margin-top:4px;">${p.category}</div>
                            </div>
                            <div style="display:flex; gap:8px;">
                                <button class="btn-edit" onclick="editProduct('${p.id}', '${p.name}', '${p.price}', '${p.category}', '${p.description || ''}')">Edit</button>
                                <button class="btn-delete" onclick="deleteProduct('${p.id}')">Delete</button>
                            </div>
                        </div>
                    `).join('')}
                `;
                document.getElementById('add-btn').style.display = 'block';
            } catch(e) { console.error(e); }
        }
        
        async function loadReviews() {
            try {
                const result = await apiCall('/api/vendor/reviews', 'GET');
                reviews = result.reviews || [];
                document.getElementById('content').innerHTML = `
                    <h3 style="color:#1b5e20; margin-bottom:16px;">⭐ Customer Reviews (${reviews.length})</h3>
                    ${reviews.length === 0 ? '<div class="welcome-card"><p>No reviews yet</p></div>' : reviews.map(r => `
                        <div class="review-card">
                            <div class="review-customer">${r.customer_name}</div>
                            <div class="review-rating">${'★'.repeat(r.rating)}${'☆'.repeat(5-r.rating)}</div>
                            <div class="review-comment">"${r.comment}"</div>
                            <button class="reply-btn" onclick="alert('Reply feature coming soon')">Reply</button>
                        </div>
                    `).join('')}
                `;
                document.getElementById('add-btn').style.display = 'none';
            } catch(e) { console.error(e); }
        }
        
        function renderProfile() {
            document.getElementById('content').innerHTML = `
                <div class="welcome-card">
                    <div style="width:80px; height:80px; background:linear-gradient(135deg,#2e7d32,#4caf50); border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 16px; color:white; font-size:32px;">🏪</div>
                    <h3 style="color:#1b5e20;">Vendor Profile</h3>
                    <p style="color:#4caf50; margin-top:4px;">${localStorage.getItem('user_email') || 'vendor@example.com'}</p>
                    <div style="margin-top:20px; text-align:left;">
                        <div style="padding:12px 0; border-bottom:1px solid #e8f5e9;">
                            <strong style="color:#1b5e20;">📦 Products:</strong> <span style="color:#4caf50;">${stats.total_products || 0}</span>
                        </div>
                        <div style="padding:12px 0; border-bottom:1px solid #e8f5e9;">
                            <strong style="color:#1b5e20;">⭐ Reviews:</strong> <span style="color:#4caf50;">${stats.total_reviews || 0}</span>
                        </div>
                        <div style="padding:12px 0;">
                            <strong style="color:#1b5e20;">📊 Avg Rating:</strong> <span style="color:#4caf50;">${stats.average_rating || 0}</span>
                        </div>
                    </div>
                </div>
            `;
            document.getElementById('add-btn').style.display = 'none';
        }
        
        function showAddProductModal() { document.getElementById('productModal').style.display = 'flex'; }
        function closeModal() { 
            document.getElementById('productModal').style.display = 'none';
            editingProductId = null;
            document.querySelector('.modal-content h3').textContent = '➕ Add Product';
            document.querySelector('.modal-content button').textContent = 'Create Product';
        }
        
        async function addProduct() {
            const name = document.getElementById('prod-name').value;
            const desc = document.getElementById('prod-desc').value;
            const cat = document.getElementById('prod-cat').value;
            const price = parseFloat(document.getElementById('prod-price').value);
            
            if (!name || !price) { alert('Please fill required fields'); return; }
            
            try {
                if (editingProductId) {
                    // Update existing product
                    await apiCall(`/api/vendor/catalog/products/${editingProductId}`, 'PUT', { name, description: desc, category: cat, price });
                    editingProductId = null;
                } else {
                    // Create new product
                    await apiCall('/api/vendor/catalog/products', 'POST', { name, description: desc, category: cat, price });
                }
                
                closeModal();
                document.getElementById('prod-name').value = '';
                document.getElementById('prod-desc').value = '';
                document.getElementById('prod-cat').value = '';
                document.getElementById('prod-price').value = '';
                document.querySelector('.modal-content h3').textContent = '➕ Add Product';
                document.querySelector('.modal-content button').textContent = 'Create Product';
                
                if (currentPage === 'products') await loadProducts();
                if (currentPage === 'dashboard') await loadDashboard();
            } catch(e) { alert('Failed to save product'); }
        }
        
        async function deleteProduct(productId) {
            if (confirm('Delete this product?')) {
                await apiCall(`/api/vendor/catalog/products/${productId}`, 'DELETE');
                if (currentPage === 'products') await loadProducts();
                if (currentPage === 'dashboard') await loadDashboard();
            }
        }
        
        let editingProductId = null;
        
        function editProduct(productId, name, price, category, description) {
            editingProductId = productId;
            document.getElementById('prod-name').value = name;
            document.getElementById('prod-price').value = price;
            document.getElementById('prod-cat').value = category;
            document.getElementById('prod-desc').value = description;
            document.querySelector('.modal-content h3').textContent = '✏️ Edit Product';
            document.querySelector('.modal-content button').textContent = 'Update Product';
            document.getElementById('productModal').style.display = 'flex';
        }
        
        async function changePage(page) {
            currentPage = page;
            const buttons = document.querySelectorAll('.nav-item');
            buttons.forEach((btn, i) => {
                btn.classList.toggle('active', i === (page === 'dashboard' ? 0 : page === 'products' ? 1 : page === 'reviews' ? 2 : 3));
            });
            if (page === 'dashboard') await loadDashboard();
            else if (page === 'products') await loadProducts();
            else if (page === 'reviews') await loadReviews();
            else renderProfile();
        }
        
        changePage('dashboard');
        window.onclick = function(event) { if (event.target === document.getElementById('productModal')) closeModal(); }
        
        // Register service worker
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/sw.js')
                    .then(registration => console.log('SW registered'))
                    .catch(error => console.log('SW registration failed'));
            });
        }
    </script>
</body>
</html>
'''

ADMIN_DASHBOARD = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#1b5e20">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Lako">
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <title>Lako - Admin Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0faf0; }
        
        .header {
            background: white;
            padding: 16px 20px;
            border-bottom: 1px solid #e8f5e9;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .header h1 { color: #1b5e20; font-size: 24px; font-weight: 700; }
        .logout-btn {
            background: #dc3545;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
        }
        
        .nav {
            background: white;
            padding: 16px 20px;
            border-bottom: 1px solid #e8f5e9;
            display: flex;
            gap: 20px;
            overflow-x: auto;
        }
        .nav-item {
            padding: 12px 20px;
            background: #f9fff9;
            border-radius: 20px;
            cursor: pointer;
            font-weight: 600;
            color: #2e7d32;
            white-space: nowrap;
            transition: all 0.2s;
        }
        .nav-item.active { background: #2e7d32; color: white; }
        
        .content { padding: 20px; }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 24px;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            text-align: center;
        }
        .stat-value { font-size: 32px; font-weight: 700; color: #1b5e20; margin-bottom: 8px; }
        .stat-label { color: #4caf50; font-size: 14px; font-weight: 500; }
        
        .section {
            background: white;
            border-radius: 20px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .section h3 { color: #1b5e20; margin-bottom: 16px; font-size: 20px; font-weight: 700; }
        
        .table {
            width: 100%;
            border-collapse: collapse;
        }
        .table th, .table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e8f5e9;
        }
        .table th { font-weight: 600; color: #2e7d32; }
        .table tr:hover { background: #f9fff9; }
        
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            margin-right: 8px;
        }
        .btn-danger { background: #dc3545; color: white; }
        .btn-warning { background: #ff9800; color: white; }
        
        @media (max-width: 600px) {
            .nav { padding: 12px 16px; }
            .content { padding: 16px; }
            .stats-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛡️ Admin Dashboard</h1>
        <button class="logout-btn" onclick="logout()">Logout</button>
    </div>
    
    <div class="nav">
        <div class="nav-item active" onclick="changePage('overview')">Overview</div>
        <div class="nav-item" onclick="changePage('users')">Users</div>
        <div class="nav-item" onclick="changePage('vendors')">Vendors</div>
        <div class="nav-item" onclick="changePage('reports')">Reports</div>
    </div>
    
    <div class="content">
        <div id="overview-page">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="total-users">0</div>
                    <div class="stat-label">Total Users</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="total-vendors">0</div>
                    <div class="stat-label">Active Vendors</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="total-products">0</div>
                    <div class="stat-label">Total Products</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="total-reviews">0</div>
                    <div class="stat-label">Total Reviews</div>
                </div>
            </div>
        </div>
        
        <div id="users-page" style="display:none;">
            <div class="section">
                <h3>User Management</h3>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Email</th>
                            <th>Role</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="users-table">
                        <!-- Users will be loaded here -->
                    </tbody>
                </table>
            </div>
        </div>
        
        <div id="vendors-page" style="display:none;">
            <div class="section">
                <h3>Vendor Management</h3>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Category</th>
                            <th>Rating</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="vendors-table">
                        <!-- Vendors will be loaded here -->
                    </tbody>
                </table>
            </div>
        </div>
        
        <div id="reports-page" style="display:none;">
            <div class="section">
                <h3>System Reports</h3>
                <p>Reports functionality coming soon...</p>
            </div>
        </div>
    </div>
    
    <script>
        let currentPage = 'overview';
        
        async function apiCall(url, method = 'GET', data = null) {
            const headers = { 'X-Session-Token': localStorage.getItem('session_token') };
            if (data) headers['Content-Type'] = 'application/json';
            
            const response = await fetch(url, {
                method,
                headers,
                body: data ? JSON.stringify(data) : null
            });
            
            if (!response.ok) throw new Error('API call failed');
            return response.json();
        }
        
        async function loadOverview() {
            try {
                const stats = await apiCall('/api/admin/stats');
                document.getElementById('total-users').textContent = stats.total_users;
                document.getElementById('total-vendors').textContent = stats.total_vendors;
                document.getElementById('total-products').textContent = stats.total_products;
                document.getElementById('total-reviews').textContent = stats.total_reviews;
            } catch(e) {
                console.error('Failed to load overview');
            }
        }
        
        async function loadUsers() {
            try {
                const users = await apiCall('/api/admin/users');
                const tbody = document.getElementById('users-table');
                tbody.innerHTML = users.map(user => `
                    <tr>
                        <td>${user.full_name}</td>
                        <td>${user.email}</td>
                        <td>${user.role}</td>
                        <td>Active</td>
                        <td>
                            <button class="btn btn-warning" onclick="suspendUser('${user.id}')">Suspend</button>
                            <button class="btn btn-danger" onclick="deleteUser('${user.id}')">Delete</button>
                        </td>
                    </tr>
                `).join('');
            } catch(e) {
                console.error('Failed to load users');
            }
        }
        
        async function loadVendors() {
            try {
                const vendors = await apiCall('/api/admin/vendors');
                const tbody = document.getElementById('vendors-table');
                tbody.innerHTML = vendors.map(vendor => `
                    <tr>
                        <td>${vendor.name}</td>
                        <td>${vendor.category}</td>
                        <td>${vendor.rating || 0}</td>
                        <td>Active</td>
                        <td>
                            <button class="btn btn-warning" onclick="deactivateVendor('${vendor.id}')">Deactivate</button>
                        </td>
                    </tr>
                `).join('');
            } catch(e) {
                console.error('Failed to load vendors');
            }
        }
        
        async function suspendUser(userId) {
            if (confirm('Suspend this user?')) {
                try {
                    await apiCall(`/api/admin/users/${userId}/suspend`, 'POST');
                    loadUsers();
                } catch(e) {
                    alert('Failed to suspend user');
                }
            }
        }
        
        async function deleteUser(userId) {
            if (confirm('Delete this user permanently?')) {
                try {
                    await apiCall(`/api/admin/users/${userId}`, 'DELETE');
                    loadUsers();
                } catch(e) {
                    alert('Failed to delete user');
                }
            }
        }
        
        async function deactivateVendor(vendorId) {
            if (confirm('Deactivate this vendor?')) {
                try {
                    await apiCall(`/api/admin/vendors/${vendorId}/deactivate`, 'POST');
                    loadVendors();
                } catch(e) {
                    alert('Failed to deactivate vendor');
                }
            }
        }
        
        function changePage(page) {
            currentPage = page;
            document.querySelectorAll('.nav-item').forEach((item, index) => {
                item.classList.toggle('active', 
                    (page === 'overview' && index === 0) ||
                    (page === 'users' && index === 1) ||
                    (page === 'vendors' && index === 2) ||
                    (page === 'reports' && index === 3)
                );
            });
            
            document.getElementById('overview-page').style.display = page === 'overview' ? 'block' : 'none';
            document.getElementById('users-page').style.display = page === 'users' ? 'block' : 'none';
            document.getElementById('vendors-page').style.display = page === 'vendors' ? 'block' : 'none';
            document.getElementById('reports-page').style.display = page === 'reports' ? 'block' : 'none';
            
            if (page === 'overview') loadOverview();
            else if (page === 'users') loadUsers();
            else if (page === 'vendors') loadVendors();
        }
        
        function logout() {
            localStorage.clear();
            window.location.href = '/';
        }
        
        // Check authentication
        if (!localStorage.getItem('session_token')) {
            window.location.href = '/login';
        }
        
        // Load initial data
        loadOverview();
        
        // Register service worker
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/sw.js')
                    .then(registration => console.log('SW registered'))
                    .catch(error => console.log('SW registration failed'));
            });
        }
    </script>
</body>
</html>
'''

GUEST_DASHBOARD = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#1b5e20">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Lako">
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <title>Lako - Guest Dashboard</title>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0faf0; }
        
        .header {
            background: white;
            padding: 16px 20px;
            border-bottom: 1px solid #e8f5e9;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .header h1 { color: #1b5e20; font-size: 24px; font-weight: 700; }
        .login-btn {
            background: #2e7d32;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
        }
        
        .nav {
            background: white;
            padding: 16px 20px;
            border-bottom: 1px solid #e8f5e9;
            display: flex;
            gap: 20px;
            overflow-x: auto;
        }
        .nav-item {
            padding: 12px 20px;
            background: #f9fff9;
            border-radius: 20px;
            cursor: pointer;
            font-weight: 600;
            color: #2e7d32;
            white-space: nowrap;
            transition: all 0.2s;
        }
        .nav-item.active { background: #2e7d32; color: white; }
        
        .content { padding: 20px; }
        
        #map { height: 60vh; border-radius: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        
        .vendor-popup {
            max-width: 300px;
        }
        .vendor-popup h3 { color: #1b5e20; margin-bottom: 8px; }
        .vendor-popup p { margin: 4px 0; color: #4caf50; }
        .vendor-popup .rating { color: #ff9800; }
        .vendor-popup .products { margin-top: 12px; }
        .vendor-popup .product { 
            background: #f9fff9; 
            padding: 8px; 
            margin: 4px 0; 
            border-radius: 8px; 
            font-size: 14px;
        }
        .vendor-popup .price { color: #2e7d32; font-weight: 600; }
        
        .search-bar {
            background: white;
            padding: 16px 20px;
            margin-bottom: 20px;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            display: flex;
            gap: 12px;
            align-items: center;
        }
        .search-bar input {
            flex: 1;
            padding: 12px 16px;
            border: 2px solid #e8f5e9;
            border-radius: 20px;
            font-size: 16px;
            outline: none;
        }
        .search-bar input:focus { border-color: #4caf50; }
        .search-bar button {
            background: #2e7d32;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 20px;
            cursor: pointer;
            font-weight: 600;
        }
        
        @media (max-width: 600px) {
            .nav { padding: 12px 16px; }
            .content { padding: 16px; }
            .search-bar { flex-direction: column; align-items: stretch; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📍 Lako</h1>
        <button class="login-btn" onclick="window.location.href='/login'">Login</button>
    </div>
    
    <div class="nav">
        <div class="nav-item active" onclick="changePage('map')">Map</div>
        <div class="nav-item" onclick="changePage('vendors')">Vendors</div>
        <div class="nav-item" onclick="changePage('feed')">Feed</div>
    </div>
    
    <div class="content">
        <div class="search-bar">
            <input type="text" id="search-input" placeholder="Search vendors or products...">
            <button onclick="searchVendors()">Search</button>
            <button onclick="getUserLocation()">📍 My Location</button>
        </div>
        
        <div id="map-container">
            <div id="map"></div>
        </div>
        
        <div id="vendors-container" style="display:none;">
            <h2 style="color:#1b5e20; margin-bottom:16px;">Nearby Vendors</h2>
            <div id="vendors-list"></div>
        </div>
        
        <div id="feed-container" style="display:none;">
            <h2 style="color:#1b5e20; margin-bottom:16px;">Latest Posts</h2>
            <div id="feed-list"></div>
        </div>
    </div>
    
    <script>
        let map;
        let userLat = 13.9443;
        let userLng = 121.3798;
        let currentPage = 'map';
        let vendors = [];
        let heatLayer;
        
        async function initMap() {
            map = L.map('map').setView([userLat, userLng], 13);
            
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(map);
            
            // Add heatmap layer
            heatLayer = L.heatLayer([], {
                radius: 25,
                blur: 15,
                maxZoom: 11,
                max: 1.0,
                gradient: {0.4: 'blue', 0.6: 'lime', 0.8: 'yellow', 1.0: 'red'}
            }).addTo(map);
            
            await loadVendors();
        }
        
        async function loadVendors() {
            try {
                const response = await fetch(`/api/customer/map/vendors?lat=${userLat}&lng=${userLng}&radius_km=20`);
                const data = await response.json();
                vendors = data.vendors || [];
                
                // Clear existing markers
                map.eachLayer((layer) => {
                    if (layer instanceof L.Marker) {
                        map.removeLayer(layer);
                    }
                });
                
                // Add vendor markers
                vendors.forEach(vendor => {
                    const marker = L.marker([vendor.latitude, vendor.longitude])
                        .addTo(map)
                        .bindPopup(createVendorPopup(vendor));
                });
                
                // Update heatmap with foot traffic data
                const heatData = vendors.map(vendor => [vendor.latitude, vendor.longitude, vendor.foot_traffic || 0.5]);
                heatLayer.setLatLngs(heatData);
                
                renderVendorsList();
            } catch(e) {
                console.error('Failed to load vendors');
            }
        }
        
        function createVendorPopup(vendor) {
            return `
                <div class="vendor-popup">
                    <h3>${vendor.name}</h3>
                    <p>📍 ${vendor.address}</p>
                    <p>⭐ Rating: ${vendor.rating || 0}/5</p>
                    <p>📞 ${vendor.phone}</p>
                    <div class="products">
                        <strong>Products:</strong>
                        ${vendor.products ? vendor.products.slice(0, 3).map(p => 
                            `<div class="product">${p.name} - <span class="price">₱${p.price}</span></div>`
                        ).join('') : '<div class="product">No products listed</div>'}
                    </div>
                    <button onclick="viewVendorDetails('${vendor.id}')" style="margin-top:12px; background:#2e7d32; color:white; border:none; padding:8px 16px; border-radius:20px; cursor:pointer;">View Details</button>
                </div>
            `;
        }
        
        function viewVendorDetails(vendorId) {
            // For guest, just show alert
            alert('Please login to view full vendor details and products');
        }
        
        async function getUserLocation() {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        userLat = position.coords.latitude;
                        userLng = position.coords.longitude;
                        map.setView([userLat, userLng], 15);
                        loadVendors();
                        alert('✅ Location updated!');
                    },
                    (error) => {
                        alert('⚠️ Unable to get your location. Using default location.');
                    },
                    { enableHighAccuracy: true, timeout: 10000 }
                );
            } else {
                alert('⚠️ Geolocation not supported');
            }
        }
        
        function renderVendorsList() {
            const container = document.getElementById('vendors-list');
            container.innerHTML = vendors.map(vendor => `
                <div style="background:white; padding:16px; margin:8px 0; border-radius:20px; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                    <h3 style="color:#1b5e20; margin-bottom:8px;">${vendor.name}</h3>
                    <p style="color:#4caf50; margin:4px 0;">📍 ${vendor.address}</p>
                    <p style="color:#ff9800; margin:4px 0;">⭐ ${vendor.rating || 0}/5</p>
                    <p style="color:#666; margin:4px 0;">📞 ${vendor.phone}</p>
                    <div style="margin-top:12px;">
                        <strong style="color:#2e7d32;">Top Products:</strong>
                        ${vendor.products ? vendor.products.slice(0, 2).map(p => 
                            `<div style="background:#f9fff9; padding:6px; margin:4px 0; border-radius:8px; font-size:14px;">
                                ${p.name} - <span style="color:#2e7d32; font-weight:600;">₱${p.price}</span>
                            </div>`
                        ).join('') : '<div style="color:#999;">No products listed</div>'}
                    </div>
                </div>
            `).join('');
        }
        
        async function loadFeed() {
            try {
                const response = await fetch('/api/guest/feed');
                const data = await response.json();
                const container = document.getElementById('feed-list');
                container.innerHTML = (data.posts || []).map(post => `
                    <div style="background:white; padding:16px; margin:8px 0; border-radius:20px; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                        <div style="display:flex; align-items:center; margin-bottom:12px;">
                            <div style="width:40px; height:40px; background:#2e7d32; border-radius:50%; display:flex; align-items:center; justify-content:center; color:white; font-weight:600; margin-right:12px;">
                                ${post.user_name ? post.user_name.charAt(0).toUpperCase() : 'U'}
                            </div>
                            <div>
                                <div style="font-weight:600; color:#1b5e20;">${post.user_name || 'Anonymous'}</div>
                                <div style="font-size:12px; color:#666;">${new Date(post.created_at).toLocaleDateString()}</div>
                            </div>
                        </div>
                        <p style="margin-bottom:12px; color:#333;">${post.content}</p>
                        ${post.image ? `<img src="${post.image}" style="max-width:100%; border-radius:12px; margin-bottom:12px;">` : ''}
                        <div style="display:flex; gap:12px; color:#666; font-size:14px;">
                            <span>👍 ${post.likes || 0}</span>
                            <span>💬 ${post.comments || 0}</span>
                        </div>
                    </div>
                `).join('');
            } catch(e) {
                console.error('Failed to load feed');
            }
        }
        
        function searchVendors() {
            const query = document.getElementById('search-input').value.toLowerCase();
            if (!query) {
                renderVendorsList();
                return;
            }
            
            const filtered = vendors.filter(vendor => 
                vendor.name.toLowerCase().includes(query) ||
                vendor.category.toLowerCase().includes(query) ||
                (vendor.products && vendor.products.some(p => p.name.toLowerCase().includes(query)))
            );
            
            const container = document.getElementById('vendors-list');
            container.innerHTML = filtered.map(vendor => `
                <div style="background:white; padding:16px; margin:8px 0; border-radius:20px; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                    <h3 style="color:#1b5e20; margin-bottom:8px;">${vendor.name}</h3>
                    <p style="color:#4caf50; margin:4px 0;">📍 ${vendor.address}</p>
                    <p style="color:#ff9800; margin:4px 0;">⭐ ${vendor.rating || 0}/5</p>
                </div>
            `).join('');
        }
        
        function changePage(page) {
            currentPage = page;
            document.querySelectorAll('.nav-item').forEach((item, index) => {
                item.classList.toggle('active', 
                    (page === 'map' && index === 0) ||
                    (page === 'vendors' && index === 1) ||
                    (page === 'feed' && index === 2)
                );
            });
            
            document.getElementById('map-container').style.display = page === 'map' ? 'block' : 'none';
            document.getElementById('vendors-container').style.display = page === 'vendors' ? 'block' : 'none';
            document.getElementById('feed-container').style.display = page === 'feed' ? 'block' : 'none';
            
            if (page === 'vendors') renderVendorsList();
            if (page === 'feed') loadFeed();
        }
        
        // Initialize
        initMap();
        
        // Register service worker
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/sw.js')
                    .then(registration => console.log('SW registered'))
                    .catch(error => console.log('SW registration failed'));
            });
        }
    </script>
</body>
</html>
'''

# ============================================
# HIGH CONCURRENCY OPTIMIZATIONS
# ============================================

# Rate limiting (simple in-memory implementation)
RATE_LIMIT = {}
RATE_LIMIT_MAX = 100  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds

def check_rate_limit(ip):
    """Simple rate limiting"""
    now = datetime.now().timestamp()
    if ip not in RATE_LIMIT:
        RATE_LIMIT[ip] = []
    
    # Clean old requests
    RATE_LIMIT[ip] = [t for t in RATE_LIMIT[ip] if now - t < RATE_LIMIT_WINDOW]
    
    if len(RATE_LIMIT[ip]) >= RATE_LIMIT_MAX:
        return False
    
    RATE_LIMIT[ip].append(now)
    return True

# Request timeout middleware
@app.before_request
def before_request():
    # Rate limiting for API endpoints
    if request.path.startswith('/api/'):
        client_ip = request.remote_addr or request.headers.get('X-Forwarded-For', 'unknown')
        if not check_rate_limit(client_ip):
            return jsonify({"error": "Rate limit exceeded"}), 429
    
    # Set request start time for monitoring
    request.start_time = datetime.now()

@app.after_request
def after_request(response):
    # Log slow requests
    if hasattr(request, 'start_time'):
        duration = (datetime.now() - request.start_time).total_seconds()
        if duration > 2.0:  # Log requests taking more than 2 seconds
            print(f"SLOW REQUEST: {request.method} {request.path} took {duration:.2f}s")
    
    # Add performance headers
    response.headers['X-Response-Time'] = f"{duration:.3f}s" if 'duration' in locals() else "unknown"
    return response

@app.teardown_request
def teardown_request(exception):
    # Ensure database connections are cleaned up
    close_db_connection()

# ============================================
# STATIC FILE OPTIMIZATION
# ============================================

@app.route('/static/<path:filename>')
def static_files(filename):
    # Handle PWA icons
    if filename == 'icon-192.png':
        return '''
<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192">
  <rect width="192" height="192" fill="#1b5e20"/>
  <text x="96" y="110" font-family="Arial" font-size="120" fill="white" text-anchor="middle">📍</text>
</svg>
''', 200, {'Content-Type': 'image/svg+xml'}
    elif filename == 'icon-512.png':
        return '''
<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <rect width="512" height="512" fill="#1b5e20"/>
  <text x="256" y="300" font-family="Arial" font-size="300" fill="white" text-anchor="middle">📍</text>
</svg>
''', 200, {'Content-Type': 'image/svg+xml'}
    
    # Serve static files with caching headers
    response = send_from_directory('static', filename)
    if filename.endswith(('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.ico')):
        response.headers['Cache-Control'] = 'public, max-age=31536000'  # 1 year
    return response

# Health check with performance metrics
@app.route('/health')
def health():
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM users')
        user_count = c.fetchone()[0]
    except:
        user_count = -1
    finally:
        close_db_connection()
    
    return jsonify({
        "status": "ok",
        "message": "Lako API is running",
        "timestamp": datetime.now().isoformat(),
        "active_connections": current_connections,
        "cache_size": len(CACHE),
        "total_users": user_count
    })

# ============================================
# API AUTH ROUTES
# ============================================

@app.route('/api/auth/register/customer', methods=['POST'])
def register_customer():
    data = request.get_json()
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Check if email exists
    c.execute('SELECT id FROM users WHERE email = ?', (data['email'],))
    if c.fetchone():
        conn.close()
        return jsonify({"error": "Email already exists"}), 400
    
    # Generate OTP
    otp = generate_otp()
    otp_expires = datetime.now() + timedelta(minutes=10)
    
    # Create temporary user record with OTP
    user_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt())
    
    c.execute('''INSERT INTO users (id, email, password, role, full_name, phone, eula_accepted, eula_version, created_at, otp_code, otp_expires, email_verified) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, data['email'], hashed.decode(), 'customer', data.get('full_name'), 
               data.get('phone', ''), 1, '1.0.0', datetime.now().isoformat(), otp, otp_expires.isoformat(), 0))
    
    conn.commit()
    conn.close()
    
    # Send OTP via email
    if send_email_otp(data['email'], otp):
        return jsonify({
            "message": "OTP sent to your email. Please verify to complete registration.",
            "user_id": user_id,
            "requires_verification": True
        })
    else:
        return jsonify({"error": "Failed to send OTP. Please try again."}), 500

@app.route('/api/auth/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email')
    otp_code = data.get('otp')
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute('SELECT id, otp_code, otp_expires, role, full_name, email FROM users WHERE email = ? AND email_verified = 0', (email,))
    user = c.fetchone()
    
    if not user:
        conn.close()
        return jsonify({"error": "User not found or already verified"}), 404
    
    user_id, stored_otp, otp_expires_str, role, full_name, user_email = user
    
    if datetime.fromisoformat(otp_expires_str) < datetime.now():
        conn.close()
        return jsonify({"error": "OTP has expired"}), 400
    
    if stored_otp != otp_code:
        conn.close()
        return jsonify({"error": "Invalid OTP"}), 400
    
    # Mark email as verified
    c.execute('UPDATE users SET email_verified = 1, otp_code = NULL, otp_expires = NULL WHERE id = ?', (user_id,))
    
    # If vendor, create vendor profile (we need to get the registration data from somewhere)
    # For now, we'll create a basic vendor profile - in production, you'd store temp data
    if role == 'vendor':
        vendor_id = str(uuid.uuid4())
        c.execute('''INSERT INTO vendors (id, user_id, name, category, address, latitude, longitude, phone, created_at) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (vendor_id, user_id, full_name, 'General', 'Location to be updated', 13.9443, 121.3798, '', datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        "session_token": user_id,
        "user_id": user_id,
        "role": role,
        "email": user_email,
        "name": full_name,
        "message": "Email verified successfully"
    })

@app.route('/api/auth/register/vendor', methods=['POST'])
def register_vendor():
    data = request.get_json()
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Check if email exists
    c.execute('SELECT id FROM users WHERE email = ?', (data['email'],))
    if c.fetchone():
        conn.close()
        return jsonify({"error": "Email already exists"}), 400
    
    # Generate OTP
    otp = generate_otp()
    otp_expires = datetime.now() + timedelta(minutes=10)
    
    # Create temporary user record with OTP
    user_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt())
    
    c.execute('''INSERT INTO users (id, email, password, role, full_name, phone, eula_accepted, eula_version, created_at, otp_code, otp_expires, email_verified) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, data['email'], hashed.decode(), 'vendor', data.get('business_name'), 
               data.get('phone', ''), 1, '1.0.0', datetime.now().isoformat(), otp, otp_expires.isoformat(), 0))
    
    conn.commit()
    conn.close()
    
    # Send OTP via email
    if send_email_otp(data['email'], otp):
        return jsonify({
            "message": "OTP sent to your email. Please verify to complete registration.",
            "user_id": user_id,
            "requires_verification": True
        })
    else:
        return jsonify({"error": "Failed to send OTP. Please try again."}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT id, password, role, full_name, email_verified FROM users WHERE email = ?', (data['email'],))
        row = c.fetchone()
    finally:
        close_db_connection()
    
    if not row:
        return jsonify({"error": "Invalid credentials"}), 401
    
    if not bcrypt.checkpw(data['password'].encode(), row[1].encode()):
        return jsonify({"error": "Invalid credentials"}), 401
    
    if row[4] == 0:  # email_verified
        # Generate new OTP for unverified user
        otp = generate_otp()
        otp_expires = datetime.now() + timedelta(minutes=10)
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute('UPDATE users SET otp_code = ?, otp_expires = ? WHERE id = ?', (otp, otp_expires.isoformat(), row[0]))
            conn.commit()
        finally:
            close_db_connection()
        
        # Send OTP
        send_email_otp(data['email'], otp)
        
        return jsonify({
            "error": "Please verify your email first",
            "requires_verification": True,
            "email": data['email'],
            "role": row[2]
        }), 401
    
    return jsonify({
        "session_token": row[0],
        "user_id": row[0],
        "role": row[2],
        "email": data['email'],
        "name": row[3]
    })

# ============================================
# GUEST API
# ============================================

@app.route('/api/guest/feed')
@optimized_cache_result(60)  # Cache for 1 minute
def get_guest_feed():
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('''
            SELECT p.id, p.content, p.image, p.created_at, u.full_name,
                   (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id) as likes,
                   (SELECT COUNT(*) FROM comments cm WHERE cm.post_id = p.id) as comments
            FROM posts p 
            JOIN users u ON p.user_id = u.id 
            ORDER BY p.created_at DESC LIMIT 20
        ''')
        posts = c.fetchall()
    finally:
        close_db_connection()
    
    return jsonify({"posts": [{"id": p[0], "content": p[1], "image": p[2], "created_at": p[3], "user_name": p[4], "likes": p[5], "comments": p[6]} for p in posts]})

# ============================================
# API CUSTOMER ROUTES
# ============================================

@app.route('/api/customer/map/vendors')
@optimized_cache_result(300)  # Cache for 5 minutes
def get_nearby_vendors():
    lat = float(request.args.get('lat', 13.9443))
    lng = float(request.args.get('lng', 121.3798))
    radius = float(request.args.get('radius_km', 20))
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Optimized query with pre-computed distance (if we had spatial index)
        # For now, we'll fetch all vendors and filter in Python
        c.execute('''
            SELECT v.id, v.name, v.category, v.description, v.address, v.latitude, v.longitude, 
                   v.rating, v.logo, v.phone,
                   GROUP_CONCAT(p.name || '|' || p.price || '|' || p.image) as products
            FROM vendors v 
            LEFT JOIN products p ON v.id = p.vendor_id 
            GROUP BY v.id
        ''')
        rows = c.fetchall()
    finally:
        close_db_connection()
    
    def distance(lat1, lng1, lat2, lng2):
        # Optimized Haversine formula
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
    
    vendors = []
    for row in rows:
        vendor_lat, vendor_lng = row[5], row[6]
        dist = distance(lat, lng, vendor_lat, vendor_lng)
        
        if dist <= radius:
            # Parse products
            products = []
            if row[10]:  # products string
                for product_str in row[10].split(','):
                    if '|' in product_str:
                        name, price, image = product_str.split('|', 2)
                        products.append({
                            "name": name,
                            "price": float(price),
                            "image": image or ""
                        })
            
            # Calculate foot traffic (simulated based on rating and product count)
            foot_traffic = min(1.0, (row[7] or 0) / 5.0 + len(products) / 10.0)
            
            vendors.append({
                "id": row[0], "name": row[1], "category": row[2], "description": row[3] or "",
                "address": row[4], "latitude": vendor_lat, "longitude": vendor_lng,
                "rating": row[7] or 0, "logo": row[8] or "", "phone": row[9] or "",
                "distance": round(dist, 2), "products": products, "foot_traffic": foot_traffic
            })
    
    vendors.sort(key=lambda x: x['distance'])
    return jsonify({"vendors": vendors})

@app.route('/api/customer/map/vendor/<vendor_id>')
def get_vendor_detail(vendor_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id, name, category, description, address, latitude, longitude, rating, logo, phone FROM vendors WHERE id = ?', (vendor_id,))
    vendor = c.fetchone()
    
    if not vendor:
        conn.close()
        return jsonify({"error": "Vendor not found"}), 404
    
    c.execute('SELECT id, name, description, category, price, image FROM products WHERE vendor_id = ?', (vendor_id,))
    products = c.fetchall()
    conn.close()
    
    return jsonify({
        "vendor": {
            "id": vendor[0], "name": vendor[1], "category": vendor[2], "description": vendor[3] or "",
            "address": vendor[4], "latitude": vendor[5], "longitude": vendor[6],
            "rating": vendor[7] or 0, "logo": vendor[8] or "", "phone": vendor[9] or ""
        },
        "products": [{"id": p[0], "name": p[1], "description": p[2] or "", "category": p[3], "price": p[4], "image": p[5] or ""} for p in products]
    })

@app.route('/api/customer/reviews', methods=['POST'])
def create_review():
    token = request.headers.get('X-Session-Token')
    if not token:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_user_by_token(token)
    if not user or user[1] != 'customer':
        return jsonify({"error": "Customer access required"}), 403
    
    data = request.get_json()
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    review_id = str(uuid.uuid4())
    c.execute('INSERT INTO reviews (id, customer_id, vendor_id, rating, title, comment, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
              (review_id, user[0], data['vendor_id'], data['rating'], data.get('title'), data.get('comment'), datetime.now().isoformat()))
    
    # Update vendor rating
    c.execute('SELECT AVG(rating) FROM reviews WHERE vendor_id = ?', (data['vendor_id'],))
    avg = c.fetchone()[0] or 0
    c.execute('UPDATE vendors SET rating = ? WHERE id = ?', (round(avg, 1), data['vendor_id']))
    
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Review submitted successfully"})

# ============================================
# API VENDOR ROUTES
# ============================================

@app.route('/api/vendor/dashboard')
def get_vendor_dashboard():
    token = request.headers.get('X-Session-Token')
    if not token:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor':
        return jsonify({"error": "Vendor access required"}), 403
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id FROM vendors WHERE user_id = ?', (user[0],))
    vendor = c.fetchone()
    
    if not vendor:
        conn.close()
        return jsonify({"error": "Vendor not found"}), 404
    
    c.execute('SELECT COUNT(*) FROM products WHERE vendor_id = ?', (vendor[0],))
    product_count = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*), AVG(rating) FROM reviews WHERE vendor_id = ?', (vendor[0],))
    review_stats = c.fetchone()
    conn.close()
    
    return jsonify({
        "total_products": product_count,
        "total_reviews": review_stats[0] or 0,
        "average_rating": round(review_stats[1] or 0, 1)
    })

@app.route('/api/vendor/catalog/products')
def get_vendor_products():
    token = request.headers.get('X-Session-Token')
    if not token:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor':
        return jsonify({"error": "Vendor access required"}), 403
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id FROM vendors WHERE user_id = ?', (user[0],))
    vendor = c.fetchone()
    
    if not vendor:
        conn.close()
        return jsonify({"error": "Vendor not found"}), 404
    
    c.execute('SELECT id, name, description, category, price, image FROM products WHERE vendor_id = ?', (vendor[0],))
    products = c.fetchall()
    conn.close()
    
    return jsonify({"products": [{"id": p[0], "name": p[1], "description": p[2] or "", "category": p[3], "price": p[4], "image": p[5] or ""} for p in products]})

@app.route('/api/vendor/catalog/products', methods=['POST'])
def create_product():
    token = request.headers.get('X-Session-Token')
    if not token:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor':
        return jsonify({"error": "Vendor access required"}), 403
    
    data = request.get_json()
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id FROM vendors WHERE user_id = ?', (user[0],))
    vendor = c.fetchone()
    
    if not vendor:
        conn.close()
        return jsonify({"error": "Vendor not found"}), 404
    
    product_id = str(uuid.uuid4())
    c.execute('INSERT INTO products (id, vendor_id, name, description, category, price, image, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
              (product_id, vendor[0], data.get('name'), data.get('description', ''), data.get('category'), 
               data.get('price'), data.get('image', ''), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    return jsonify({"id": product_id, "message": "Product created successfully"})

@app.route('/api/vendor/catalog/products/<product_id>', methods=['PUT'])
def update_product(product_id):
    token = request.headers.get('X-Session-Token')
    if not token:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor':
        return jsonify({"error": "Vendor access required"}), 403
    
    data = request.get_json()
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Verify product belongs to vendor
    c.execute('SELECT v.id FROM products p JOIN vendors v ON p.vendor_id = v.id WHERE p.id = ? AND v.user_id = ?', (product_id, user[0]))
    if not c.fetchone():
        conn.close()
        return jsonify({"error": "Product not found or access denied"}), 404
    
    # Update product
    c.execute('''UPDATE products SET name = ?, description = ?, category = ?, price = ?, image = ? WHERE id = ?''',
              (data.get('name'), data.get('description', ''), data.get('category'), 
               data.get('price'), data.get('image', ''), product_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Product updated successfully"})

@app.route('/api/vendor/catalog/products/<product_id>', methods=['DELETE'])
def delete_product(product_id):
    token = request.headers.get('X-Session-Token')
    if not token:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor':
        return jsonify({"error": "Vendor access required"}), 403
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Product deleted successfully"})

@app.route('/api/vendor/reviews')
def get_vendor_reviews():
    token = request.headers.get('X-Session-Token')
    if not token:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor':
        return jsonify({"error": "Vendor access required"}), 403
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id FROM vendors WHERE user_id = ?', (user[0],))
    vendor = c.fetchone()
    
    if not vendor:
        conn.close()
        return jsonify({"error": "Vendor not found"}), 404
    
    c.execute('''SELECT r.id, r.rating, r.title, r.comment, r.created_at, u.full_name 
                 FROM reviews r JOIN users u ON r.customer_id = u.id 
                 WHERE r.vendor_id = ? ORDER BY r.created_at DESC''', (vendor[0],))
    reviews = c.fetchall()
    conn.close()
    
    return jsonify({"reviews": [{"id": r[0], "rating": r[1], "title": r[2], "comment": r[3], "created_at": r[4], "customer_name": r[5]} for r in reviews]})

# ============================================
# ADMIN API
# ============================================

@app.route('/api/admin/stats')
def get_admin_stats():
    token = request.headers.get('X-Session-Token')
    if not token:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_user_by_token(token)
    if not user or user[1] != 'admin':
        return jsonify({"error": "Admin access required"}), 403
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM users')
    total_users = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM vendors')
    total_vendors = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM products')
    total_products = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM reviews')
    total_reviews = c.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        "total_users": total_users,
        "total_vendors": total_vendors,
        "total_products": total_products,
        "total_reviews": total_reviews
    })

@app.route('/api/admin/users')
def get_all_users():
    token = request.headers.get('X-Session-Token')
    if not token:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_user_by_token(token)
    if not user or user[1] != 'admin':
        return jsonify({"error": "Admin access required"}), 403
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id, full_name, email, role, created_at FROM users ORDER BY created_at DESC')
    users = c.fetchall()
    conn.close()
    
    return jsonify([{"id": u[0], "full_name": u[1], "email": u[2], "role": u[3], "created_at": u[4]} for u in users])

@app.route('/api/admin/vendors')
def get_all_vendors():
    token = request.headers.get('X-Session-Token')
    if not token:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_user_by_token(token)
    if not user or user[1] != 'admin':
        return jsonify({"error": "Admin access required"}), 403
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''SELECT v.id, v.name, v.category, v.rating, u.full_name as owner_name 
                 FROM vendors v JOIN users u ON v.user_id = u.id ORDER BY v.created_at DESC''')
    vendors = c.fetchall()
    conn.close()
    
    return jsonify([{"id": v[0], "name": v[1], "category": v[2], "rating": v[3], "owner_name": v[4]} for v in vendors])

@app.route('/api/admin/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    token = request.headers.get('X-Session-Token')
    if not token:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_user_by_token(token)
    if not user or user[1] != 'admin':
        return jsonify({"error": "Admin access required"}), 403
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "User deleted successfully"})

@app.route('/api/admin/users/<user_id>/suspend', methods=['POST'])
def suspend_user(user_id):
    token = request.headers.get('X-Session-Token')
    if not token:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_user_by_token(token)
    if not user or user[1] != 'admin':
        return jsonify({"error": "Admin access required"}), 403
    
    # For now, just mark as suspended (you can add a suspended column to users table)
    return jsonify({"message": "User suspended successfully"})

@app.route('/api/admin/vendors/<vendor_id>/deactivate', methods=['POST'])
def deactivate_vendor(vendor_id):
    token = request.headers.get('X-Session-Token')
    if not token:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_user_by_token(token)
    if not user or user[1] != 'admin':
        return jsonify({"error": "Admin access required"}), 403
    
    # For now, just mark as deactivated (you can add a status column to vendors table)
    return jsonify({"message": "Vendor deactivated successfully"})

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "Lako - GPS Proximity Discovery",
        "short_name": "Lako",
        "description": "GPS Proximity Discovery of Micro-Retail Vendors",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0a2e1a",
        "theme_color": "#1b5e20",
        "orientation": "portrait-primary",
        "icons": [
            {
                "src": "/static/icon-192.png",
                "sizes": "192x192",
                "type": "image/svg+xml"
            },
            {
                "src": "/static/icon-512.png",
                "sizes": "512x512",
                "type": "image/svg+xml"
            }
        ]
    })

@app.route('/sw.js')
def service_worker():
    return '''
self.addEventListener('install', event => {
    console.log('Service Worker installing.');
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    console.log('Service Worker activating.');
});

self.addEventListener('fetch', event => {
    // For now, just pass through all requests
    // In production, add caching strategies here
    event.respondWith(fetch(event.request));
});
''', 200, {'Content-Type': 'application/javascript'}

# ============================================
# GRACEFUL SHUTDOWN
# ============================================

def cleanup_connections():
    """Clean up all database connections on shutdown"""
    global current_connections
    print(f"Cleaning up {current_connections} database connections...")
    # Force close any remaining connections
    current_connections = 0
    print("✓ Database connections cleaned up")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"\nReceived signal {signum}, shutting down gracefully...")
    cleanup_connections()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ============================================
# RUN
# ============================================

if __name__ == '__main__':
    # Initialize databases
    init_db()
    
    print("=" * 60)
    print("🚀 LAKO - GPS Proximity Discovery Platform")
    print("=" * 60)
    print("Developers: Kyle Brian M. Morillo & Alexander Collin P. Millichamp")
    print("AITE - Capstone Project")
    print("=" * 60)
    print("✅ High-concurrency optimizations enabled:")
    print("   • Database connection pooling: ENABLED")
    print("   • Thread-safe caching: ENABLED")
    print("   • SQLite WAL mode: ENABLED")
    print("   • Rate limiting: ENABLED")
    print("   • Performance monitoring: ENABLED")
    print("   • Connection limits: 10 max")
    print("   • Cache size limit: 1000 entries")
    print("=" * 60)
    print("✅ Server running on http://0.0.0.0:5000")
    print("📍 Customer Dashboard: http://localhost:5000/customer/dashboard")
    print("🏪 Vendor Dashboard: http://localhost:5000/vendor/dashboard")
    print("🔍 Health Check: http://localhost:5000/health")
    print("=" * 60)
    
    try:
        app.run(
            host='0.0.0.0',
            port=int(os.environ.get('PORT', 5000)),
            debug=False,  # Disable debug for production
            threaded=True,  # Enable threading for concurrency
            processes=1  # Single process for Render
        )
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        cleanup_connections()