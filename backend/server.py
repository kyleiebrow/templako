from flask import Flask, jsonify, request, render_template_string, session, redirect
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
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
CORS(app, origins=["*"])

DB_NAME = os.path.join(os.path.dirname(__file__), 'lako.db')

# Gmail SMTP (from environment or fallback)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "morillokylebrian@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "khug erxu dhxa ugut")

# Supabase Configuration (from environment)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Initialize Supabase client only if credentials are available
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"⚠️ Warning: Supabase initialization failed: {e}")
        print("Continuing with SQLite-only database...")
        supabase = None
else:
    print("⚠️ Warning: Supabase credentials not configured. Using SQLite only.")

# ============================================
# DATABASE (SQLite + Supabase)
# ============================================

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, email TEXT UNIQUE, password TEXT, role TEXT,
        full_name TEXT, phone TEXT, eula_accepted INTEGER DEFAULT 0,
        created_at TIMESTAMP, otp_code TEXT, otp_expires TIMESTAMP, email_verified INTEGER DEFAULT 0,
        is_suspended INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS vendors (
        id TEXT PRIMARY KEY, user_id TEXT, business_name TEXT, category TEXT,
        description TEXT, address TEXT, latitude REAL, longitude REAL,
        rating REAL DEFAULT 0, phone TEXT, is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY, vendor_id TEXT, name TEXT, description TEXT,
        category TEXT, price REAL, stock INTEGER DEFAULT 0, moq INTEGER,
        is_active INTEGER DEFAULT 1, created_at TIMESTAMP,
        FOREIGN KEY (vendor_id) REFERENCES vendors(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS reviews (
        id TEXT PRIMARY KEY, customer_id TEXT, vendor_id TEXT,
        rating INTEGER, comment TEXT, created_at TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES users(id),
        FOREIGN KEY (vendor_id) REFERENCES vendors(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS posts (
        id TEXT PRIMARY KEY, user_id TEXT, content TEXT,
        likes INTEGER DEFAULT 0, created_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS shortlists (
        id TEXT PRIMARY KEY, user_id TEXT, vendor_id TEXT, created_at TIMESTAMP,
        UNIQUE(user_id, vendor_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (vendor_id) REFERENCES vendors(id)
    )''')
    
    # Create admin
    admin_id = str(uuid.uuid4())
    admin_pass = bcrypt.hashpw('admin123'.encode(), bcrypt.gensalt()).decode()
    try:
        c.execute('''INSERT INTO users (id, email, password, role, full_name, eula_accepted, created_at, email_verified) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (admin_id, 'admin@lako.com', admin_pass, 'admin', 'Administrator', 1, datetime.now().isoformat(), 1))
    except:
        pass
    
    conn.commit()
    conn.close()
    print("✓ SQLite initialized")

def sync_to_supabase(table, data):
    """Sync data to Supabase (optional)"""
    if not supabase:
        return False
    try:
        supabase.table(table).upsert(data).execute()
        return True
    except Exception as e:
        print(f"⚠️ Supabase sync error: {e}")
        return False

init_db()

# ============================================
# UTILITIES
# ============================================

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def send_email_otp(email, otp):
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = email
        msg['Subject'] = "Lako - OTP Code"
        msg.attach(MIMEText(f"Your OTP is: {otp}\nExpires in 10 minutes.", 'plain'))
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_USERNAME, email, msg.as_string())
        server.quit()
        print(f"✓ OTP sent to {email}")
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def get_user_by_token(token):
    if not token: return None
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, role, full_name, email FROM users WHERE id = ?', (token,))
    user = c.fetchone()
    conn.close()
    return user

def calculate_distance(lat1, lng1, lat2, lng2):
    if None in [lat1, lng1, lat2, lng2]: return float('inf')
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ============================================
# SVG ICONS
# ============================================

ICONS = {
    'map': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
    'store': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/></svg>',
    'user': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    'dashboard': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
    'box': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="M12 22V12"/></svg>',
    'star': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    'heart': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>',
    'comment': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    'bookmark': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>',
    'trash': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
    'edit': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
    'camera': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>',
    'filter': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="22 3 2 3 10 13 10 21 14 18 14 13 22 3"/></svg>',
    'share': '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>',
}

# ============================================
# BASE STYLES
# ============================================

BASE_STYLE = '''
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { 
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  background: linear-gradient(135deg, #f0faf0 0%, #e8f5e9 100%);
  min-height: 100vh;
  color: #1b1b1b;
}

.header { 
  background: linear-gradient(135deg, #fff 0%, #f9fff9 100%);
  padding: 16px 24px;
  box-shadow: 0 4px 12px rgba(46, 125, 50, 0.08);
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 10;
  backdrop-filter: blur(10px);
}

.logo { 
  font-size: 24px;
  font-weight: 800;
  background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.logout-btn { 
  background: #ffebee;
  border: none;
  color: #c62828;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  padding: 10px 20px;
  border-radius: 30px;
  transition: all 0.3s ease;
}

.logout-btn:hover {
  background: #ef5350;
  color: white;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(244, 67, 54, 0.2);
}

.content { 
  padding: 20px;
  padding-bottom: 80px;
  max-width: 900px;
  margin: 0 auto;
}

.card { 
  background: white;
  border-radius: 24px;
  padding: 24px;
  margin-bottom: 16px;
  border: 1px solid rgba(46, 125, 50, 0.1);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.card:hover {
  box-shadow: 0 8px 32px rgba(46, 125, 50, 0.12);
  transform: translateY(-4px);
  border-color: rgba(46, 125, 50, 0.2);
}

.btn { 
  padding: 14px 28px;
  border: none;
  border-radius: 30px;
  font-weight: 700;
  cursor: pointer;
  background: linear-gradient(135deg, #2e7d32 0%, #1b5e20 100%);
  color: white;
  transition: all 0.3s ease;
  font-size: 15px;
  letter-spacing: 0.5px;
  box-shadow: 0 4px 12px rgba(46, 125, 50, 0.2);
}

.btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(46, 125, 50, 0.3);
}

.btn:active {
  transform: translateY(0);
}

.btn-outline { 
  background: white;
  border: 2px solid #2e7d32;
  color: #2e7d32;
  box-shadow: 0 2px 8px rgba(46, 125, 50, 0.1);
}

.btn-outline:hover {
  background: #f0faf0;
  box-shadow: 0 4px 16px rgba(46, 125, 50, 0.15);
}

.btn-danger { 
  background: linear-gradient(135deg, #ef5350 0%, #e53935 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(244, 67, 54, 0.2);
}

.btn-danger:hover {
  box-shadow: 0 8px 24px rgba(244, 67, 54, 0.3);
}

.btn-sm { 
  padding: 10px 18px;
  font-size: 13px;
}

input, select, textarea { 
  width: 100%;
  padding: 14px 16px;
  border: 2px solid #e0e0e0;
  border-radius: 16px;
  background: #fafafa;
  margin-bottom: 12px;
  font-family: inherit;
  font-size: 15px;
  transition: all 0.3s ease;
  color: #1b1b1b;
}

input:focus, select:focus, textarea:focus {
  outline: none;
  border-color: #2e7d32;
  background: white;
  box-shadow: 0 0 0 4px rgba(46, 125, 50, 0.1);
}

input::placeholder, textarea::placeholder {
  color: #b0bec5;
}

.bottom-nav { 
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: white;
  display: flex;
  justify-content: space-around;
  padding: 12px;
  border-top: 2px solid #e8f5e9;
  box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.06);
}

.nav-item { 
  display: flex;
  flex-direction: column;
  align-items: center;
  background: none;
  border: none;
  color: #90a4ae;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  padding: 8px 16px;
  border-radius: 12px;
  transition: all 0.3s ease;
  min-width: 60px;
}

.nav-item:hover {
  color: #4caf50;
}

.nav-item.active { 
  color: #2e7d32;
  background: linear-gradient(135deg, #e8f5e9 0%, #f1f8f6 100%);
  font-weight: 700;
}

.stars { 
  color: #fbbf24;
  letter-spacing: 2px;
}

.modal { 
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 100;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(5px);
}

.modal-content { 
  background: white;
  border-radius: 32px;
  padding: 28px;
  max-width: 500px;
  width: 90%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.grid { display: grid; gap: 16px; }
.grid-2 { grid-template-columns: repeat(2, 1fr); }
.grid-3 { grid-template-columns: repeat(3, 1fr); }
.grid-4 { grid-template-columns: repeat(4, 1fr); }

@media (max-width: 640px) {
  .grid-3, .grid-4 { grid-template-columns: 1fr; }
}

.flex { display: flex; }
.flex-1 { flex: 1; }
.gap-2 { gap: 8px; }
.gap-4 { gap: 16px; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.justify-center { justify-content: center; }
.mb-4 { margin-bottom: 16px; }
.mt-4 { margin-top: 16px; }
.text-center { text-align: center; }
.text-secondary { color: #78909c; font-weight: 500; }
.badge { 
  display: inline-block;
  background: linear-gradient(135deg, #e8f5e9 0%, #f1f8f6 100%);
  color: #2e7d32;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.badge.active {
  background: linear-gradient(135deg, #c8e6c9 0%, #a5d6a7 100%);
  color: #1b5e20;
}

.badge.inactive {
  background: #ffebee;
  color: #c62828;
}

h1, h2, h3 { 
  color: #1b5e20;
  font-weight: 800;
  letter-spacing: -0.5px;
}

h2 { font-size: 28px; margin-bottom: 8px; }
h3 { font-size: 20px; margin-bottom: 12px; }

p { line-height: 1.6; }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
'''

# ============================================
# HTML TEMPLATES
# ============================================

CHOOSE_ROLE = '''
<!DOCTYPE html>
<html><head><title>Lako - GPS Proximity Discovery</title><meta name="viewport" content="width=device-width, initial-scale=1">''' + BASE_STYLE + '''</head>
<body>
<div class="header"><div class="logo">📍 Lako</div></div>
<div class="content" style="text-align:center; padding-top:80px;">
<h1 style="font-size:52px; margin-bottom:12px; background:linear-gradient(135deg, #1b5e20 0%, #4caf50 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;">Lako</h1>
<p style="color:#4caf50; margin-bottom:16px; font-size:18px; font-weight:500;">GPS Proximity Discovery of Micro-Retail Vendors</p>
<p style="color:#78909c; margin-bottom:48px; font-size:15px;">Find vendors getting closer or browse as a guest</p>
<div class="grid grid-3" style="max-width:700px; margin:0 auto; gap:20px;">
<div onclick="selectRole('customer')" class="card" style="cursor:pointer; text-align:center; transition:all 0.3s ease;"><div style="font-size:48px; margin-bottom:16px;">📍</div><h3 style="margin-bottom:8px;">Customer</h3><p class="text-secondary">Find nearby vendors</p></div>
<div onclick="selectRole('vendor')" class="card" style="cursor:pointer; text-align:center; transition:all 0.3s ease;"><div style="font-size:48px; margin-bottom:16px;">🏪</div><h3 style="margin-bottom:8px;">Vendor</h3><p class="text-secondary">Manage your business</p></div>
<div onclick="selectRole('admin')" class="card" style="cursor:pointer; text-align:center; transition:all 0.3s ease;"><div style="font-size:48px; margin-bottom:16px;">🛡️</div><h3 style="margin-bottom:8px;">Admin</h3><p class="text-secondary">Manage the platform</p></div>
</div>
<p class="mt-4" style="margin-top:32px;"><a href="/guest" class="btn" style="text-decoration:none; display:inline-block;">Browse as Guest →</a></p>
</div>
<script>function selectRole(r){localStorage.setItem('user_role',r);location.href='/login';}</script>
</body></html>'''

LOGIN = '''
<!DOCTYPE html>
<html><head><title>Sign In - Lako</title><meta name="viewport" content="width=device-width, initial-scale=1">''' + BASE_STYLE + '''</head>
<body>
<div class="content" style="max-width:420px; padding-top:80px;">
<div class="card" style="box-shadow: 0 10px 40px rgba(46, 125, 50, 0.1);">
<div style="text-align:center; margin-bottom:28px;"><div style="font-size:48px; margin-bottom:12px;">📍</div><h2>Sign In</h2><p class="text-secondary" style="margin-top:8px;">Welcome back to Lako</p></div>
<div id="error" style="background:linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%); color:#c62828; padding:14px; border-radius:16px; margin-bottom:20px; display:none; border-left:4px solid #c62828; font-weight:600;"></div>
<input type="email" id="email" placeholder="Email address" value="admin@lako.com" style="margin-bottom:16px;">
<input type="password" id="password" placeholder="Password" value="admin123" style="margin-bottom:24px;">
<button class="btn" style="width:100%; font-size:16px; padding:16px;" onclick="login()">Sign In</button>
<p class="text-center" style="margin-top:20px; color:#78909c;"><a href="/register" style="color:#2e7d32; text-decoration:none; font-weight:700;">Create Account</a> • <a href="/" style="color:#2e7d32; text-decoration:none; font-weight:700;">Back</a></p>
</div>
</div>
<script>
async function login(){
const e=document.getElementById('email').value,p=document.getElementById('password').value,err=document.getElementById('error');
if(!e||!p){err.textContent='⚠️ Fill all fields';err.style.display='block';return;}
try{
const r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:e,password:p})});
const d=await r.json();
if(r.ok){
localStorage.setItem('session_token',d.session_token);
localStorage.setItem('user_role',d.role);
localStorage.setItem('user_email',d.email);
const red={customer:'/customer',vendor:'/vendor',admin:'/admin'};
location.href=red[d.role]||'/';
}else{
if(d.requires_verification){showOtp(e,d.role);}
else{err.textContent='❌ '+d.error;err.style.display='block';}
}
}catch(x){err.textContent='⚠️ Network error';err.style.display='block';}
}
function showOtp(email,role){
document.querySelector('.card').innerHTML='<div style="text-align:center; margin-bottom:24px;"><h2>Verify Email</h2><p class="text-secondary">Enter the code sent to<br><strong style="color:#1b1b1b;">'+email+'</strong></p></div><div id="otp-err" style="background:linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);color:#c62828;padding:14px;border-radius:16px;display:none;border-left:4px solid #c62828;font-weight:600;"></div><input type="text" id="otp" placeholder="000000" maxlength="6" style="text-align:center;font-size:24px;letter-spacing:12px;font-weight:700; margin-bottom:24px;"><button class="btn" style="width:100%;" onclick="verifyOtp(\''+email+'\',\''+role+'\')">Verify Email</button><button class="btn-outline" style="width:100%; margin-top:12px;" onclick="location.reload()">← Back</button>';
}
async function verifyOtp(email,role){
const o=document.getElementById('otp').value,err=document.getElementById('otp-err');
if(!o||o.length!==6){err.textContent='⚠️ Enter 6-digit code';err.style.display='block';return;}
const r=await fetch('/api/auth/verify-otp',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,otp:o})});
const d=await r.json();
if(r.ok){localStorage.setItem('session_token',d.session_token);localStorage.setItem('user_role',role);const red={customer:'/customer',vendor:'/vendor',admin:'/admin'};location.href=red[role]||'/';}
else{err.textContent='❌ '+d.error;err.style.display='block';}
}
</script>
</body></html>'''

REGISTER = '''
<!DOCTYPE html>
<html><head><title>Register - Lako</title><meta name="viewport" content="width=device-width, initial-scale=1">''' + BASE_STYLE + '''</head>
<body>
<div class="content" style="max-width:500px; padding-top:40px;">
<div class="card">
<h2 class="text-center mb-4">Create Account</h2>
<div id="error" style="background:#ffebee; color:#c62828; padding:12px; border-radius:20px; margin-bottom:20px; display:none;"></div>
<div id="customerFields"><input type="text" id="fullName" placeholder="Full Name"></div>
<div id="vendorFields" style="display:none;">
<input type="text" id="businessName" placeholder="Business Name">
<select id="category"><option>Street Foods</option><option>Dimsum</option><option>Snacks</option><option>Rice Meals</option><option>Refreshments</option></select>
<input type="text" id="address" placeholder="Address">
<div class="flex gap-2"><input type="text" id="lat" placeholder="Lat"><input type="text" id="lng" placeholder="Lng"><button type="button" class="btn-outline" style="padding:12px;" onclick="getLocation()">📍</button></div>
</div>
<input type="email" id="email" placeholder="Email">
<input type="tel" id="phone" placeholder="Phone">
<input type="password" id="password" placeholder="Password">
<input type="password" id="confirm" placeholder="Confirm Password">
<div style="margin:16px 0; padding:12px; background:#f9fff9; border-radius:16px; font-size:12px;">
<input type="checkbox" id="eula"> I agree to the EULA
</div>
<button class="btn" style="width:100%;" onclick="register()">Register</button>
<p class="text-center mt-4"><a href="/login" style="color:#4caf50;">← Back to Login</a></p>
</div>
</div>
<script>
const role=localStorage.getItem('user_role')||'customer';
if(role==='vendor'){document.getElementById('customerFields').style.display='none';document.getElementById('vendorFields').style.display='block';}
function getLocation(){navigator.geolocation&&navigator.geolocation.getCurrentPosition(p=>{document.getElementById('lat').value=p.coords.latitude;document.getElementById('lng').value=p.coords.longitude;},()=>alert('Cannot get location'));}
async function register(){
if(!document.getElementById('eula').checked){document.getElementById('error').textContent='Accept EULA';document.getElementById('error').style.display='block';return;}
const p=document.getElementById('password').value,c=document.getElementById('confirm').value;
if(p!==c){document.getElementById('error').textContent='Passwords do not match';document.getElementById('error').style.display='block';return;}
if(p.length<8){document.getElementById('error').textContent='Password too short';document.getElementById('error').style.display='block';return;}
const data={email:document.getElementById('email').value,password:p,phone:document.getElementById('phone').value,eula_accepted:true};
if(role==='customer'){data.full_name=document.getElementById('fullName').value;if(!data.full_name){document.getElementById('error').textContent='Enter full name';document.getElementById('error').style.display='block';return;}var endpoint='/api/auth/register/customer';}
else{data.business_name=document.getElementById('businessName').value;data.business_category=document.getElementById('category').value;data.address=document.getElementById('address').value;data.latitude=parseFloat(document.getElementById('lat').value)||13.9443;data.longitude=parseFloat(document.getElementById('lng').value)||121.3798;if(!data.business_name||!data.address){document.getElementById('error').textContent='Fill all fields';document.getElementById('error').style.display='block';return;}var endpoint='/api/auth/register/vendor';}
try{
const r=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
const d=await r.json();
if(r.ok&&d.requires_verification){showOtp(data.email,role);}
else if(r.ok){localStorage.setItem('session_token',d.session_token);location.href=role==='customer'?'/customer':'/vendor';}
else{document.getElementById('error').textContent=d.error;document.getElementById('error').style.display='block';}
}catch(x){document.getElementById('error').textContent='Network error';document.getElementById('error').style.display='block';}
}
function showOtp(email,role){
document.querySelector('.card').innerHTML='<h2>Verify Email</h2><p>Code sent to '+email+'</p><div id="otp-err" style="background:#ffebee;color:#c62828;padding:12px;border-radius:20px;display:none;"></div><input type="text" id="otp" placeholder="000000" maxlength="6" style="text-align:center;font-size:20px;letter-spacing:8px;"><button class="btn" style="width:100%;" onclick="verifyOtp(\''+email+'\',\''+role+'\')">Verify</button>';
}
async function verifyOtp(email,role){
const o=document.getElementById('otp').value,err=document.getElementById('otp-err');
if(!o||o.length!==6){err.textContent='Enter 6-digit code';err.style.display='block';return;}
const r=await fetch('/api/auth/verify-otp',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,otp:o})});
const d=await r.json();
if(r.ok){localStorage.setItem('session_token',d.session_token);location.href=role==='customer'?'/customer':'/vendor';}
else{err.textContent=d.error;err.style.display='block';}
}
</script>
</body></html>'''

CUSTOMER = '''
<!DOCTYPE html>
<html><head><title>Customer - Lako</title><meta name="viewport" content="width=device-width, initial-scale=1">''' + BASE_STYLE + '''</head>
<body>
<div class="header"><div class="logo">📍 Lako</div><button class="logout-btn" onclick="logout()">Sign out</button></div>
<div class="content" id="content">
<div class="card flex justify-between items-center" style="background:linear-gradient(135deg, #e8f5e9 0%, #f1f8f6 100%); border:2px solid #c8e6c9;"><span id="locStatus" style="font-weight:700; color:#1b5e20;">📍 Getting location...</span><button class="btn btn-sm" onclick="getLocation()" style="cursor:pointer; padding:10px 16px;">🔄 Refresh</button></div>
<div id="pageContent"></div>
</div>
<div class="bottom-nav">
<button class="nav-item active" onclick="showPage('map')"><i class="fas fa-map"></i><br>Map</button>
<button class="nav-item" onclick="showPage('vendors')"><i class="fas fa-store"></i><br>Vendors</button>
<button class="nav-item" onclick="showPage('feed')"><i class="fas fa-comments"></i><br>Feed</button>
<button class="nav-item" onclick="showPage('shortlist')"><i class="fas fa-bookmark"></i><br>Saved</button>
<button class="nav-item" onclick="showPage('profile')"><i class="fas fa-user-circle"></i><br>Profile</button>
</div>
<script>
let loc=null,vendors=[],page='map',posts=[],shortlist=[];
function logout(){if(confirm('Sign out?')){localStorage.clear();location.href='/';}}
async function api(url,method='GET',data=null){
const h={'X-Session-Token':localStorage.getItem('session_token')};
if(data)h['Content-Type']='application/json';
const r=await fetch(url,{method,headers:h,body:data?JSON.stringify(data):null});
return r.json();
}
function getLocation(){
navigator.geolocation&&navigator.geolocation.getCurrentPosition(async p=>{
loc={lat:p.coords.latitude,lng:p.coords.longitude};
document.getElementById('locStatus').innerHTML='📍 '+loc.lat.toFixed(4)+', '+loc.lng.toFixed(4)+' ✓';
await loadVendors();showPage(page);
},()=>{loc={lat:13.9443,lng:121.3798};document.getElementById('locStatus').innerHTML='📍 Default Location';loadVendors();});
}
async function loadVendors(){if(!loc)return;const d=await api('/api/customer/map/vendors?lat='+loc.lat+'&lng='+loc.lng+'&radius_km=20');vendors=d.vendors||[];}
async function loadFeed(){const d=await api('/api/customer/feed');posts=d.posts||[];}
async function loadShortlist(){const d=await api('/api/customer/shortlist');shortlist=d.shortlist||[];}
function showPage(p){
page=p;document.querySelectorAll('.nav-item').forEach((b,i)=>b.classList.toggle('active',(p==='map'&&i===0)||(p==='vendors'&&i===1)||(p==='feed'&&i===2)||(p==='shortlist'&&i===3)||(p==='profile'&&i===4)));
if(p==='map')showMap();else if(p==='vendors')showVendors();else if(p==='feed'){loadFeed().then(showFeed);}else if(p==='shortlist'){loadShortlist().then(showShortlist);}else showProfile();
}
function showMap(){
if(!loc)return;
document.getElementById('pageContent').innerHTML='<div style="height:420px; border-radius:24px; overflow:hidden; margin-bottom:20px; box-shadow:0 4px 20px rgba(46,125,50,0.15);"><iframe width="100%" height="100%" src="https://www.openstreetmap.org/export/embed.html?bbox='+(loc.lng-0.1)+','+(loc.lat-0.1)+','+(loc.lng+0.1)+','+(loc.lat+0.1)+'&layer=mapnik&marker='+loc.lat+','+loc.lng+'"></iframe></div><div class="card"><div style="margin-bottom:16px;"><h3>Nearby Vendors ('+vendors.length+')</h3></div>'+vendors.slice(0,5).map(v=>'<div style="padding:14px; background:linear-gradient(135deg, #f0faf0 0%, #e8f5e9 100%); border-radius:16px; margin-bottom:12px; border-left:4px solid #4caf50;"><div style="display:flex; justify-content:space-between; align-items:start;"><div style="flex:1;"><strong style="font-size:16px;">'+v.name+'</strong><br><span class="text-secondary">'+v.category+' · '+v.distance.toFixed(2)+' km</span></div><span class="badge active">⭐ '+v.rating+'</span></div></div>').join('')+'</div>';
}
function showVendors(){
document.getElementById('pageContent').innerHTML='<div class="mb-4"><input type="text" id="searchVendors" placeholder="🔍 Search vendors..." oninput="filterVendors()" style="font-size:16px;"></div><div id="vendorsList">'+vendors.map(v=>'<div class="card" style="cursor:pointer; position:relative;" onclick="viewVendor(\''+v.id+'\')"><div style="display:flex; justify-content:space-between; align-items:start; gap:16px;"><div style="flex:1;"><h3 style="margin-bottom:6px;">'+v.name+'</h3><p class="text-secondary" style="margin-bottom:8px;">'+v.category+'</p><div style="display:flex; gap:8px; align-items:center;"><span class="stars">★★★★★</span><span style="font-weight:700; color:#1b5e20;">'+v.rating+'</span><span class="text-secondary">('+v.reviews+' reviews)</span></div><p style="margin-top:8px; color:#4caf50; font-weight:700;">📍 '+v.distance.toFixed(2)+' km away</p></div><button class="btn-outline btn-sm" style="min-width:40px; padding:8px;" onclick="event.stopPropagation();toggleShortlist(\''+v.id+'\')"><i class=\"fas fa-bookmark\"></i></button></div></div>').join('')+'</div>';
}
function filterVendors(){const q=document.getElementById('searchVendors').value.toLowerCase();document.getElementById('vendorsList').innerHTML=vendors.filter(v=>v.name.toLowerCase().includes(q)||v.category.toLowerCase().includes(q)).map(v=>'<div class="card" style="cursor:pointer;" onclick="viewVendor(\''+v.id+'\')"><h3>'+v.name+'</h3><p>'+v.category+'</p><p style="color:#4caf50; font-weight:700;">📍 '+v.distance.toFixed(2)+' km</p></div>').join('');}
function viewVendor(id){const v=vendors.find(x=>x.id===id);if(v)alert('📍 '+v.name+'\\n'+v.category+'\\n'+v.address+'\\n📞 '+v.phone);}
async function toggleShortlist(vendorId){const d=await api('/api/customer/shortlist/'+vendorId,'POST');alert(d.added?'✓ Added to Saved':'✗ Removed from Saved');}
function showFeed(){
document.getElementById('pageContent').innerHTML='<div class="card" style="background:linear-gradient(135deg, #fff 0%, #f9fff9 100%); margin-bottom:20px;"><textarea id="postContent" placeholder="Share your vendor discoveries..." style="resize:vertical; min-height:80px; background:#fafafa;"></textarea><div class="flex gap-2" style="margin-top:12px;"><button class="btn" onclick="createPost()" style="cursor:pointer;">Post</button></div></div><div id="feedList">'+posts.map(p=>'<div class="card"><div class="flex gap-2 mb-2" style="align-items:flex-start;"><div style="width:44px; height:44px; background:linear-gradient(135deg, #2e7d32 0%, #1b5e20 100%); border-radius:50%; display:flex; align-items:center; justify-content:center; color:white; font-weight:700; flex-shrink:0;">'+(p.user_name?p.user_name[0].toUpperCase():'U')+'</div><div style="flex:1;"><strong style="display:block; color:#1b5e20;">'+p.user_name+'</strong><p class="text-secondary" style="font-size:12px; margin-top:2px;">'+new Date(p.created_at).toLocaleString()+'</p></div></div><p style="padding:12px; background:#f0faf0; border-radius:16px; margin:12px 0; color:#1b1b1b; line-height:1.6;">'+p.content+'</p><div class="flex gap-4"><button class="btn-outline btn-sm" onclick="likePost(\''+p.id+'\')"><i class=\"fas fa-heart\"></i> '+p.likes+'</button></div></div>').join('')+'</div>';
}
async function createPost(){const c=document.getElementById('postContent').value;if(!c||c.trim()===''){alert('Write something first!');return;}await api('/api/customer/posts','POST',{content:c});loadFeed().then(showFeed);}
async function likePost(id){await api('/api/customer/posts/'+id+'/like','POST');loadFeed().then(showFeed);}
function showShortlist(){document.getElementById('pageContent').innerHTML='<div style="margin-bottom:16px;"><h3>📌 Saved Vendors</h3></div>'+(shortlist.length===0?'<div class="card text-center" style="padding:32px; background:linear-gradient(135deg, #f0faf0 0%, #e8f5e9 100%);"><p style="font-size:48px;">🔖</p><p class="text-secondary">No saved vendors yet</p></div>':shortlist.map(v=>'<div class="card" style="cursor:pointer;" onclick="viewVendor(\''+v.id+'\')"><h3>'+v.business_name+'</h3><p class="text-secondary">'+v.category+'</p></div>').join(''));}
function showProfile(){
document.getElementById('pageContent').innerHTML='<div class="card text-center" style="margin-bottom:20px;"><div style="width:100px;height:100px;background:linear-gradient(135deg, #2e7d32 0%, #1b5e20 100%);border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 16px;color:white;font-size:48px;">👤</div><h2>'+ (localStorage.getItem('user_email')||'Customer') +'</h2><p class="text-secondary" style="margin:8px 0;">📍 '+ (loc?loc.lat.toFixed(4)+', '+loc.lng.toFixed(4):'Location not set') +'</p></div><div class="grid grid-3"><div class="card" style="text-align:center; background:linear-gradient(135deg, #f0faf0 0%, #e8f5e9 100%);"><h3 style="color:#2e7d32; margin-bottom:6px;">0</h3><p class="text-secondary">Reviews</p></div><div class="card" style="text-align:center; background:linear-gradient(135deg, #f0faf0 0%, #e8f5e9 100%);"><h3 style="color:#2e7d32; margin-bottom:6px;">'+posts.length+'</h3><p class="text-secondary">Posts</p></div><div class="card" style="text-align:center; background:linear-gradient(135deg, #f0faf0 0%, #e8f5e9 100%);"><h3 style="color:#2e7d32; margin-bottom:6px;">'+shortlist.length+'</h3><p class="text-secondary">Saved</p></div></div>';
}
getLocation();
</script>
</body></html>'''

VENDOR = '''
<!DOCTYPE html>
<html><head><title>Vendor - Lako</title><meta name="viewport" content="width=device-width, initial-scale=1">''' + BASE_STYLE + '''</head>
<body>
<div class="header"><div class="logo">🏪 Lako Vendor</div><button class="logout-btn" onclick="logout()">Sign out</button></div>
<div class="content" id="content"></div>
<div class="bottom-nav">
<button class="nav-item active" onclick="showPage('dashboard')"><div>''' + ICONS['dashboard'] + '''</div><span>Dashboard</span></button>
<button class="nav-item" onclick="showPage('products')"><div>''' + ICONS['box'] + '''</div><span>Products</span></button>
<button class="nav-item" onclick="showPage('posts')"><div>''' + ICONS['comment'] + '''</div><span>Posts</span></button>
<button class="nav-item" onclick="showPage('reviews')"><div>''' + ICONS['star'] + '''</div><span>Reviews</span></button>
<button class="nav-item" onclick="showPage('profile')"><div>''' + ICONS['user'] + '''</div><span>Profile</span></button>
</div>
<button class="btn" style="position:fixed; bottom:80px; right:20px; width:56px; height:56px; border-radius:50%; font-size:24px;" id="addBtn" onclick="showAddModal()">+</button>
<div class="modal" id="modal" onclick="if(event.target===this)closeModal()"><div class="modal-content"><h3 id="modalTitle">Add Product</h3><input type="text" id="prodName" placeholder="Product Name"><textarea id="prodDesc" placeholder="Description" rows="2"></textarea><div class="grid grid-2"><input type="text" id="prodCat" placeholder="Category"><input type="number" id="prodPrice" placeholder="Price" step="0.01"></div><input type="number" id="prodStock" placeholder="Stock" value="0"><input type="number" id="prodMoq" placeholder="MOQ" value="1"><button class="btn" style="width:100%;" onclick="saveProduct()">Save</button><button class="btn-outline" style="width:100%; margin-top:8px;" onclick="closeModal()">Cancel</button></div></div>
<script>
let page='dashboard',products=[],stats={},editId=null,posts=[],reviews=[];
function logout(){localStorage.clear();location.href='/';}
async function api(url,method='GET',data=null){
const h={'X-Session-Token':localStorage.getItem('session_token')};
if(data)h['Content-Type']='application/json';
const r=await fetch(url,{method,headers:h,body:data?JSON.stringify(data):null});
return r.json();
}
async function showPage(p){
page=p;document.querySelectorAll('.nav-item').forEach((b,i)=>b.classList.toggle('active',i===['dashboard','products','posts','reviews','profile'].indexOf(p)));
document.getElementById('addBtn').style.display=(p==='products')?'flex':'none';
if(p==='dashboard')await loadDashboard();
else if(p==='products')await loadProducts();
else if(p==='posts')await loadPosts();
else if(p==='reviews')await loadReviews();
else showProfile();
}
async function loadDashboard(){
stats=await api('/api/vendor/dashboard');
document.getElementById('content').innerHTML='<div class="grid grid-3"><div class="card text-center"><h2>'+stats.total_products+'</h2><p>Products</p></div><div class="card text-center"><h2>'+stats.total_posts+'</h2><p>Posts</p></div><div class="card text-center"><h2>'+stats.total_reviews+'</h2><p>Reviews</p></div></div><div class="card"><h3>Quick Actions</h3><div class="flex gap-2"><button class="btn" onclick="showPage(\'products\')">Add Product</button><button class="btn-outline" onclick="showPage(\'posts\')">Create Post</button></div></div>';
}
async function loadProducts(){
const d=await api('/api/vendor/catalog/products');products=d.products||[];
document.getElementById('content').innerHTML='<h3>Your Products ('+products.length+')</h3>'+products.map(p=>'<div class="card"><div class="flex justify-between"><div><strong>'+p.name+'</strong><p class="text-secondary">'+p.category+'</p><p>₱'+p.price+' | Stock: '+p.stock+' | MOQ: '+p.moq+'</p></div><div><button class="btn-outline btn-sm" onclick="editProduct(\''+p.id+'\',\''+p.name+'\','+p.price+',\''+(p.category||'')+'\',\''+(p.description||'')+'\','+p.stock+','+p.moq+')">'+ICONS['edit']+'</button><button class="btn-danger btn-sm" onclick="deleteProduct(\''+p.id+'\')">'+ICONS['trash']+'</button></div></div></div>').join('');
}
async function loadPosts(){
const d=await api('/api/vendor/posts');posts=d.posts||[];
document.getElementById('content').innerHTML='<div class="card mb-4"><textarea id="postContent" placeholder="Share an update..."></textarea><div class="flex gap-2"><button class="btn" onclick="createPost()">Post</button></div></div>'+posts.map(p=>'<div class="card"><p>'+p.content+'</p><div class="flex gap-4 mt-2"><span>❤️ '+p.likes+'</span><span class="text-secondary">'+new Date(p.created_at).toLocaleString()+'</span></div></div>').join('');
}
async function createPost(){const c=document.getElementById('postContent').value;if(!c)return;await api('/api/vendor/posts','POST',{content:c});loadPosts();}
async function loadReviews(){
const d=await api('/api/vendor/reviews');reviews=d.reviews||[];
document.getElementById('content').innerHTML='<h3>Reviews ('+reviews.length+')</h3>'+reviews.map(r=>'<div class="card"><div class="flex justify-between"><div><strong>'+r.customer_name+'</strong><div class="stars">'+'★'.repeat(r.rating)+'☆'.repeat(5-r.rating)+'</div><p>'+r.comment+'</p></div></div></div>').join('');
}
function showProfile(){
document.getElementById('content').innerHTML='<div class="card text-center"><div style="width:80px;height:80px;background:#2e7d32;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 16px;color:white;font-size:32px;">🏪</div><h3>'+ (localStorage.getItem('user_email')||'Vendor') +'</h3><div class="grid grid-3 mt-4"><div class="card"><h3>'+stats.total_products+'</h3><p>Products</p></div><div class="card"><h3>'+stats.total_reviews+'</h3><p>Reviews</p></div><div class="card"><h3>'+stats.average_rating+'</h3><p>Rating</p></div></div></div>';
}
function showAddModal(){document.getElementById('modal').style.display='flex';}
function closeModal(){document.getElementById('modal').style.display='none';editId=null;document.getElementById('modalTitle').textContent='Add Product';document.getElementById('prodName').value='';document.getElementById('prodDesc').value='';document.getElementById('prodCat').value='';document.getElementById('prodPrice').value='';document.getElementById('prodStock').value='0';document.getElementById('prodMoq').value='1';}
function editProduct(id,name,price,cat,desc,stock,moq){editId=id;document.getElementById('modalTitle').textContent='Edit Product';document.getElementById('prodName').value=name;document.getElementById('prodPrice').value=price;document.getElementById('prodCat').value=cat;document.getElementById('prodDesc').value=desc;document.getElementById('prodStock').value=stock;document.getElementById('prodMoq').value=moq;document.getElementById('modal').style.display='flex';}
async function saveProduct(){
const data={name:document.getElementById('prodName').value,description:document.getElementById('prodDesc').value,category:document.getElementById('prodCat').value,price:parseFloat(document.getElementById('prodPrice').value),stock:parseInt(document.getElementById('prodStock').value),moq:parseInt(document.getElementById('prodMoq').value)};
if(!data.name||!data.price){alert('Fill required fields');return;}
if(editId){await api('/api/vendor/catalog/products/'+editId,'PUT',data);}else{await api('/api/vendor/catalog/products','POST',data);}
closeModal();loadProducts();loadDashboard();
}
async function deleteProduct(id){if(confirm('Delete?')){await api('/api/vendor/catalog/products/'+id,'DELETE');loadProducts();loadDashboard();}}
showPage('dashboard');
</script>
</body></html>'''

ADMIN = '''
<!DOCTYPE html>
<html><head><title>Admin - Lako</title><meta name="viewport" content="width=device-width, initial-scale=1">''' + BASE_STYLE + '''</head>
<body>
<div class="header"><div class="logo">🛡️ Admin</div><button class="logout-btn" onclick="logout()">Sign out</button></div>
<div style="display:flex; gap:8px; padding:16px; overflow-x:auto;">
<button class="nav-item active" onclick="showPage('overview')">Overview</button>
<button class="nav-item" onclick="showPage('users')">Users</button>
<button class="nav-item" onclick="showPage('vendors')">Vendors</button>
<button class="nav-item" onclick="showPage('products')">Products</button>
<button class="nav-item" onclick="showPage('reviews')">Reviews</button>
</div>
<div class="content" id="content"></div>
<script>
function logout(){localStorage.clear();location.href='/';}
async function api(url,method='GET',data=null){
const h={'X-Session-Token':localStorage.getItem('session_token')};
if(data)h['Content-Type']='application/json';
const r=await fetch(url,{method,headers:h,body:data?JSON.stringify(data):null});
return r.json();
}
async function showPage(p){
document.querySelectorAll('.nav-item').forEach(b=>b.classList.remove('active'));
event.target.classList.add('active');
if(p==='overview')await loadOverview();
else if(p==='users')await loadUsers();
else if(p==='vendors')await loadVendors();
else if(p==='products')await loadProducts();
else if(p==='reviews')await loadReviews();
}
async function loadOverview(){
const s=await api('/api/admin/stats');
document.getElementById('content').innerHTML='<div class="grid grid-4"><div class="card text-center"><h2>'+s.total_users+'</h2><p>Users</p></div><div class="card text-center"><h2>'+s.total_vendors+'</h2><p>Vendors</p></div><div class="card text-center"><h2>'+s.total_products+'</h2><p>Products</p></div><div class="card text-center"><h2>'+s.total_reviews+'</h2><p>Reviews</p></div></div>';
}
async function loadUsers(){
const u=await api('/api/admin/users');
document.getElementById('content').innerHTML='<h3>Users ('+u.length+')</h3>'+u.map(u=>'<div class="card flex justify-between items-center"><div><strong>'+u.full_name+'</strong><br><span class="text-secondary">'+u.email+'</span><br><span class="badge">'+u.role+'</span></div><div><button class="btn-danger btn-sm" onclick="deleteUser(\''+u.id+'\')">'+ICONS['trash']+'</button></div></div>').join('');
}
async function loadVendors(){
const v=await api('/api/admin/vendors');
document.getElementById('content').innerHTML='<h3>Vendors ('+v.length+')</h3>'+v.map(v=>'<div class="card flex justify-between items-center"><div><strong>'+v.name+'</strong><br><span class="text-secondary">'+v.category+'</span><br>⭐ '+v.rating+'</div><div><span class="badge '+(v.is_active?'active':'inactive')+'">'+(v.is_active?'Active':'Inactive')+'</span></div></div>').join('');
}
async function loadProducts(){
const p=await api('/api/admin/products');
document.getElementById('content').innerHTML='<h3>Products ('+p.length+')</h3>'+p.map(p=>'<div class="card flex justify-between items-center"><div><strong>'+p.name+'</strong><br><span class="text-secondary">'+p.vendor_name+' | ₱'+p.price+'</span></div><button class="btn-danger btn-sm" onclick="deleteProduct(\''+p.id+'\')">'+ICONS['trash']+'</button></div>').join('');
}
async function loadReviews(){
const r=await api('/api/admin/reviews');
document.getElementById('content').innerHTML='<h3>Reviews ('+r.length+')</h3>'+r.map(r=>'<div class="card"><div class="flex justify-between"><strong>'+r.customer_name+'</strong><div class="stars">'+'★'.repeat(r.rating)+'☆'.repeat(5-r.rating)+'</div></div><p>'+r.comment+'</p><p class="text-secondary">Vendor: '+r.vendor_name+'</p><button class="btn-danger btn-sm" onclick="deleteReview(\''+r.id+'\')">'+ICONS['trash']+'</button></div>').join('');
}
async function deleteUser(id){if(confirm('Delete?')){await api('/api/admin/users/'+id,'DELETE');loadUsers();}}
async function deleteProduct(id){if(confirm('Delete?')){await api('/api/admin/products/'+id,'DELETE');loadProducts();}}
async function deleteReview(id){if(confirm('Delete?')){await api('/api/admin/reviews/'+id,'DELETE');loadReviews();}}
showPage('overview');
</script>
</body></html>'''

GUEST = '''
<!DOCTYPE html>
<html><head><title>Guest - Lako</title><meta name="viewport" content="width=device-width, initial-scale=1">''' + BASE_STYLE + '''
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
</head>
<body>
<div class="header"><div class="logo">📍 Lako Guest</div><a href="/login"><button class="btn">Sign In</button></a></div>
<div class="content">
<div class="flex gap-2 mb-4"><input type="text" id="search" placeholder="Search vendors..." class="flex-1"><button class="btn" onclick="searchVendors()">🔍</button><button class="btn-outline" onclick="getLocation()">📍</button></div>
<div id="map" style="height:300px; border-radius:20px; margin-bottom:20px;"></div>
<div id="vendorsList"></div>
</div>
<script>
let map,loc={lat:13.9443,lng:121.3798},vendors=[],markers=[];
function initMap(){
map=L.map('map').setView([loc.lat,loc.lng],13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
loadVendors();
}
async function loadVendors(){
const r=await fetch('/api/customer/map/vendors?lat='+loc.lat+'&lng='+loc.lng+'&radius_km=20');
const d=await r.json();vendors=d.vendors||[];
markers.forEach(m=>map.removeLayer(m));markers=[];
vendors.forEach(v=>{if(v.latitude&&v.longitude){const m=L.marker([v.latitude,v.longitude]).addTo(map).bindPopup('<b>'+v.name+'</b><br>'+v.category+'<br>⭐ '+v.rating);markers.push(m);}});
renderList();
}
function renderList(){
document.getElementById('vendorsList').innerHTML='<h3>Nearby Vendors ('+vendors.length+')</h3>'+vendors.map(v=>'<div class="card" onclick="map.setView(['+v.latitude+','+v.longitude+'],15)"><strong>'+v.name+'</strong><p>'+v.category+'</p><div class="stars">'+'★'.repeat(Math.floor(v.rating||0))+'☆'.repeat(5-Math.floor(v.rating||0))+'</div><p>📍 '+(v.distance||'?')+' km</p></div>').join('');
}
function getLocation(){navigator.geolocation&&navigator.geolocation.getCurrentPosition(p=>{loc={lat:p.coords.latitude,lng:p.coords.longitude};map.setView([loc.lat,loc.lng],14);loadVendors();});}
function searchVendors(){const q=document.getElementById('search').value.toLowerCase();const f=vendors.filter(v=>v.name.toLowerCase().includes(q)||v.category.toLowerCase().includes(q));document.getElementById('vendorsList').innerHTML='<h3>Results</h3>'+f.map(v=>'<div class="card"><strong>'+v.name+'</strong><p>'+v.category+'</p></div>').join('');}
initMap();
</script>
</body></html>'''

# ============================================
# PAGE ROUTES
# ============================================

@app.route('/')
def index():
    return render_template_string(CHOOSE_ROLE)

@app.route('/login')
def login_page():
    return render_template_string(LOGIN)

@app.route('/register')
def register_page():
    return render_template_string(REGISTER)

@app.route('/customer')
def customer_page():
    return render_template_string(CUSTOMER)

@app.route('/vendor')
def vendor_page():
    return render_template_string(VENDOR)

@app.route('/admin')
def admin_page():
    return render_template_string(ADMIN)

@app.route('/guest')
def guest_page():
    return render_template_string(GUEST)

@app.route('/api/health')
def health_check():
    return jsonify({"status": "ok", "supabase": "connected" if supabase else "not connected"})

@app.route('/sw.js')
def service_worker():
    return '''
self.addEventListener('install', e => console.log('SW install'));
self.addEventListener('fetch', e => e.respondWith(fetch(e.request)));
''', 200, {'Content-Type': 'application/javascript'}

# ============================================
# API AUTH
# ============================================

@app.route('/api/auth/register/customer', methods=['POST'])
def api_register_customer():
    data = request.get_json()
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id FROM users WHERE email = ?', (data['email'],))
    if c.fetchone():
        conn.close()
        return jsonify({"error": "Email exists"}), 400
    otp = generate_otp()
    user_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt()).decode()
    c.execute('''INSERT INTO users (id, email, password, role, full_name, phone, eula_accepted, created_at, otp_code, otp_expires, email_verified) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, data['email'], hashed, 'customer', data.get('full_name'), data.get('phone', ''), 1, datetime.now().isoformat(), otp, (datetime.now()+timedelta(minutes=10)).isoformat(), 0))
    conn.commit()
    conn.close()
    send_email_otp(data['email'], otp)
    # Sync to Supabase
    sync_to_supabase('users', {'id': user_id, 'email': data['email'], 'role': 'customer', 'full_name': data.get('full_name'), 'created_at': datetime.now().isoformat()})
    return jsonify({"requires_verification": True, "user_id": user_id})

@app.route('/api/auth/register/vendor', methods=['POST'])
def api_register_vendor():
    data = request.get_json()
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id FROM users WHERE email = ?', (data['email'],))
    if c.fetchone():
        conn.close()
        return jsonify({"error": "Email exists"}), 400
    otp = generate_otp()
    user_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt()).decode()
    c.execute('''INSERT INTO users (id, email, password, role, full_name, phone, eula_accepted, created_at, otp_code, otp_expires, email_verified) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, data['email'], hashed, 'vendor', data['business_name'], data.get('phone', ''), 1, datetime.now().isoformat(), otp, (datetime.now()+timedelta(minutes=10)).isoformat(), 0))
    vendor_id = str(uuid.uuid4())
    c.execute('''INSERT INTO vendors (id, user_id, business_name, category, address, latitude, longitude, created_at) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (vendor_id, user_id, data['business_name'], data.get('business_category', 'General'), data['address'], data.get('latitude', 13.9443), data.get('longitude', 121.3798), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    send_email_otp(data['email'], otp)
    # Sync to Supabase
    sync_to_supabase('users', {'id': user_id, 'email': data['email'], 'role': 'vendor', 'full_name': data['business_name'], 'created_at': datetime.now().isoformat()})
    sync_to_supabase('vendors', {'id': vendor_id, 'user_id': user_id, 'business_name': data['business_name'], 'category': data.get('business_category', 'General'), 'address': data['address'], 'created_at': datetime.now().isoformat()})
    return jsonify({"requires_verification": True, "user_id": user_id})

@app.route('/api/auth/verify-otp', methods=['POST'])
def api_verify_otp():
    data = request.get_json()
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, otp_code, otp_expires, role, full_name, email FROM users WHERE email = ? AND email_verified = 0', (data['email'],))
    u = c.fetchone()
    if not u: return jsonify({"error": "Invalid"}), 400
    if datetime.fromisoformat(u[2]) < datetime.now(): return jsonify({"error": "OTP expired"}), 400
    if u[1] != data['otp']: return jsonify({"error": "Invalid OTP"}), 400
    c.execute('UPDATE users SET email_verified = 1, otp_code = NULL, otp_expires = NULL WHERE id = ?', (u[0],))
    conn.commit()
    conn.close()
    return jsonify({"session_token": u[0], "role": u[3], "email": u[5]})

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json()
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, password, role, full_name, email_verified FROM users WHERE email = ?', (data['email'],))
    u = c.fetchone()
    conn.close()
    if not u or not bcrypt.checkpw(data['password'].encode(), u[1].encode()):
        return jsonify({"error": "Invalid credentials"}), 401
    if u[4] == 0:
        return jsonify({"requires_verification": True, "email": data['email'], "role": u[2]}), 401
    return jsonify({"session_token": u[0], "role": u[2], "email": data['email'], "name": u[3]})

# ============================================
# API CUSTOMER
# ============================================

@app.route('/api/customer/map/vendors')
def api_nearby_vendors():
    lat = float(request.args.get('lat', 13.9443))
    lng = float(request.args.get('lng', 121.3798))
    radius = float(request.args.get('radius_km', 20))
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, business_name as name, category, description, address, latitude, longitude, rating, phone FROM vendors WHERE is_active = 1')
    vendors = []
    for v in c.fetchall():
        if v[5] and v[6]:
            dist = calculate_distance(lat, lng, v[5], v[6])
            if dist <= radius:
                vendors.append({"id": v[0], "name": v[1], "category": v[2], "description": v[3] or "", "address": v[4], "latitude": v[5], "longitude": v[6], "rating": v[7] or 0, "phone": v[8] or "", "distance": round(dist, 2)})
    conn.close()
    vendors.sort(key=lambda x: x['distance'])
    return jsonify({"vendors": vendors})

@app.route('/api/customer/feed')
def api_customer_feed():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT p.id, p.content, p.likes, p.created_at, u.full_name FROM posts p JOIN users u ON p.user_id = u.id ORDER BY p.created_at DESC LIMIT 20')
    posts = [dict(p) for p in c.fetchall()]
    conn.close()
    return jsonify({"posts": posts})

@app.route('/api/customer/posts', methods=['POST'])
def api_create_customer_post():
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    conn = get_db()
    c = conn.cursor()
    pid = str(uuid.uuid4())
    c.execute('INSERT INTO posts (id, user_id, content, created_at) VALUES (?, ?, ?, ?)',
              (pid, user[0], data['content'], datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"id": pid})

@app.route('/api/customer/posts/<pid>/like', methods=['POST'])
def api_like_post(pid):
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user: return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE posts SET likes = likes + 1 WHERE id = ?', (pid,))
    conn.commit()
    conn.close()
    return jsonify({"liked": True})

@app.route('/api/customer/shortlist')
def api_get_shortlist():
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user: return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT v.* FROM shortlists s JOIN vendors v ON s.vendor_id = v.id WHERE s.user_id = ?', (user[0],))
    shortlist = [dict(v) for v in c.fetchall()]
    conn.close()
    return jsonify({"shortlist": shortlist})

@app.route('/api/customer/shortlist/<vendor_id>', methods=['POST'])
def api_toggle_shortlist(vendor_id):
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user: return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id FROM shortlists WHERE user_id = ? AND vendor_id = ?', (user[0], vendor_id))
    if c.fetchone():
        c.execute('DELETE FROM shortlists WHERE user_id = ? AND vendor_id = ?', (user[0], vendor_id))
        added = False
    else:
        c.execute('INSERT INTO shortlists (id, user_id, vendor_id, created_at) VALUES (?, ?, ?, ?)', (str(uuid.uuid4()), user[0], vendor_id, datetime.now().isoformat()))
        added = True
    conn.commit()
    conn.close()
    return jsonify({"added": added})

# ============================================
# API VENDOR
# ============================================

@app.route('/api/vendor/dashboard')
def api_vendor_dashboard():
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id FROM vendors WHERE user_id = ?', (user[0],))
    v = c.fetchone()
    if not v: return jsonify({"error": "Vendor not found"}), 404
    c.execute('SELECT COUNT(*) FROM products WHERE vendor_id = ?', (v[0],)); pc = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM posts WHERE user_id = ?', (user[0],)); postc = c.fetchone()[0]
    c.execute('SELECT COUNT(*), AVG(rating) FROM reviews WHERE vendor_id = ?', (v[0],)); rs = c.fetchone()
    conn.close()
    return jsonify({"total_products": pc, "total_posts": postc, "total_reviews": rs[0] or 0, "average_rating": round(rs[1] or 0, 1)})

@app.route('/api/vendor/catalog/products')
def api_vendor_products():
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id FROM vendors WHERE user_id = ?', (user[0],))
    v = c.fetchone()
    if not v: return jsonify({"error": "Vendor not found"}), 404
    c.execute('SELECT id, name, description, category, price, stock, moq FROM products WHERE vendor_id = ? AND is_active = 1', (v[0],))
    products = [dict(p) for p in c.fetchall()]
    conn.close()
    return jsonify({"products": products})

@app.route('/api/vendor/catalog/products', methods=['POST'])
def api_create_product():
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id FROM vendors WHERE user_id = ?', (user[0],))
    v = c.fetchone()
    if not v: return jsonify({"error": "Vendor not found"}), 404
    pid = str(uuid.uuid4())
    c.execute('''INSERT INTO products (id, vendor_id, name, description, category, price, stock, moq, created_at) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (pid, v[0], data['name'], data.get('description', ''), data.get('category'), data['price'], data.get('stock', 0), data.get('moq', 1), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"id": pid})

@app.route('/api/vendor/catalog/products/<pid>', methods=['PUT'])
def api_update_product(pid):
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE products SET name=?, description=?, category=?, price=?, stock=?, moq=? WHERE id=?',
              (data['name'], data.get('description', ''), data.get('category'), data['price'], data.get('stock', 0), data.get('moq', 1), pid))
    conn.commit()
    conn.close()
    return jsonify({"updated": True})

@app.route('/api/vendor/catalog/products/<pid>', methods=['DELETE'])
def api_delete_product(pid):
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE products SET is_active = 0 WHERE id = ?', (pid,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": True})

@app.route('/api/vendor/posts')
def api_vendor_posts():
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, content, likes, created_at FROM posts WHERE user_id = ? ORDER BY created_at DESC', (user[0],))
    posts = [dict(p) for p in c.fetchall()]
    conn.close()
    return jsonify({"posts": posts})

@app.route('/api/vendor/posts', methods=['POST'])
def api_create_vendor_post():
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    conn = get_db()
    c = conn.cursor()
    pid = str(uuid.uuid4())
    c.execute('INSERT INTO posts (id, user_id, content, created_at) VALUES (?, ?, ?, ?)',
              (pid, user[0], data['content'], datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"id": pid})

@app.route('/api/vendor/reviews')
def api_vendor_reviews():
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id FROM vendors WHERE user_id = ?', (user[0],))
    v = c.fetchone()
    if not v: return jsonify({"error": "Vendor not found"}), 404
    c.execute('SELECT r.id, r.rating, r.comment, r.created_at, u.full_name FROM reviews r JOIN users u ON r.customer_id = u.id WHERE r.vendor_id = ? ORDER BY r.created_at DESC', (v[0],))
    reviews = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify({"reviews": reviews})

# ============================================
# API ADMIN
# ============================================

@app.route('/api/admin/stats')
def api_admin_stats():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users'); users = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM vendors'); vendors = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM products'); products = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM reviews'); reviews = c.fetchone()[0]
    conn.close()
    return jsonify({"total_users": users, "total_vendors": vendors, "total_products": products, "total_reviews": reviews})

@app.route('/api/admin/users')
def api_admin_users():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, full_name, email, role, created_at FROM users ORDER BY created_at DESC')
    users = [dict(u) for u in c.fetchall()]
    conn.close()
    return jsonify(users)

@app.route('/api/admin/users/<uid>', methods=['DELETE'])
def api_admin_delete_user(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id = ?', (uid,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": True})

@app.route('/api/admin/vendors')
def api_admin_vendors():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT v.id, v.business_name as name, v.category, v.rating, v.is_active FROM vendors v ORDER BY v.created_at DESC')
    vendors = [dict(v) for v in c.fetchall()]
    conn.close()
    return jsonify(vendors)

@app.route('/api/admin/products')
def api_admin_products():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT p.id, p.name, p.price, v.business_name as vendor_name FROM products p JOIN vendors v ON p.vendor_id = v.id ORDER BY p.created_at DESC')
    products = [dict(p) for p in c.fetchall()]
    conn.close()
    return jsonify(products)

@app.route('/api/admin/products/<pid>', methods=['DELETE'])
def api_admin_delete_product(pid):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM products WHERE id = ?', (pid,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": True})

@app.route('/api/admin/reviews')
def api_admin_reviews():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT r.id, r.rating, r.comment, r.created_at, u.full_name as customer_name, v.business_name as vendor_name FROM reviews r JOIN users u ON r.customer_id = u.id JOIN vendors v ON r.vendor_id = v.id ORDER BY r.created_at DESC')
    reviews = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(reviews)

@app.route('/api/admin/reviews/<rid>', methods=['DELETE'])
def api_admin_delete_review(rid):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM reviews WHERE id = ?', (rid,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": True})

# ============================================
# RUN
# ============================================

if __name__ == '__main__':
    print("=" * 50)
    print("📍 LAKO - Complete Platform with Supabase")
    print("=" * 50)
    print("Customer: http://localhost:5000/customer")
    print("Vendor: http://localhost:5000/vendor")
    print("Admin: http://localhost:5000/admin")
    print("Guest: http://localhost:5000/guest")
    print("Supabase: " + ("Connected" if supabase else "Not connected"))
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)