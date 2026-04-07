from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
import sqlite3
import uuid
import bcrypt
from datetime import datetime
import math
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
CORS(app, origins="*")

# ============================================
# DATABASE
# ============================================

DB_NAME = 'lako.db'

def init_db():
    """Initialize the database with all required tables"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
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
        created_at TIMESTAMP
    )''')
    
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
    
    conn.commit()
    conn.close()
    print("✓ Database initialized successfully")

init_db()

def get_user_by_token(token):
    """Get user from session token"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id, role FROM users WHERE id = ?', (token,))
    user = c.fetchone()
    conn.close()
    return user

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
        </div>
    </div>
    <script>
        function selectRole(role) {
            localStorage.setItem('user_role', role);
            window.location.href = '/login';
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
                    localStorage.setItem('session_token', data.session_token);
                    localStorage.setItem('user_role', data.role);
                    localStorage.setItem('user_email', data.email);
                    window.location.href = data.role === 'customer' ? '/customer/dashboard' : '/vendor/dashboard';
                } else {
                    errorDiv.textContent = data.error || 'Login failed';
                    errorDiv.style.display = 'block';
                }
            } catch(e) {
                errorDiv.textContent = 'Network error';
                errorDiv.style.display = 'block';
            }
        }
        
        function showRegister() { window.location.href = '/register'; }
        function switchRole() { localStorage.removeItem('user_role'); window.location.href = '/'; }
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
                
                if (response.ok) {
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
                
                if (response.ok) {
                    localStorage.setItem('session_token', result.session_token);
                    window.location.href = '/vendor/dashboard';
                } else {
                    document.getElementById('error').textContent = result.error;
                    document.getElementById('error').style.display = 'block';
                }
            }
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
                            <button class="btn-delete" onclick="deleteProduct('${p.id}')">Delete</button>
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
        function closeModal() { document.getElementById('productModal').style.display = 'none'; }
        
        async function addProduct() {
            const name = document.getElementById('prod-name').value;
            const desc = document.getElementById('prod-desc').value;
            const cat = document.getElementById('prod-cat').value;
            const price = parseFloat(document.getElementById('prod-price').value);
            
            if (!name || !price) { alert('Please fill required fields'); return; }
            
            try {
                await apiCall('/api/vendor/catalog/products', 'POST', { name, description: desc, category: cat, price });
                closeModal();
                document.getElementById('prod-name').value = '';
                document.getElementById('prod-desc').value = '';
                document.getElementById('prod-cat').value = '';
                document.getElementById('prod-price').value = '';
                if (currentPage === 'products') await loadProducts();
                if (currentPage === 'dashboard') await loadDashboard();
            } catch(e) { alert('Failed to add product'); }
        }
        
        async function deleteProduct(productId) {
            if (confirm('Delete this product?')) {
                await apiCall(`/api/vendor/catalog/products/${productId}`, 'DELETE');
                if (currentPage === 'products') await loadProducts();
                if (currentPage === 'dashboard') await loadDashboard();
            }
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
    </script>
</body>
</html>
'''

# ============================================
# ROUTES
# ============================================

@app.route('/')
def index():
    return render_template_string(CHOOSE_ROLE_HTML)

@app.route('/login')
def login_page():
    return render_template_string(LOGIN_HTML)

@app.route('/register')
def register_page():
    return render_template_string(REGISTER_HTML)

@app.route('/customer/dashboard')
def customer_dashboard():
    return render_template_string(CUSTOMER_DASHBOARD)

@app.route('/vendor/dashboard')
def vendor_dashboard():
    return render_template_string(VENDOR_DASHBOARD)

@app.route('/health')
def health():
    return jsonify({"status": "ok", "message": "Lako API is running"})

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
    
    # Create user
    user_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt())
    
    c.execute('''INSERT INTO users (id, email, password, role, full_name, phone, eula_accepted, eula_version, created_at) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, data['email'], hashed.decode(), 'customer', data.get('full_name'), 
               data.get('phone', ''), 1, '1.0.0', datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        "session_token": user_id,
        "user_id": user_id,
        "role": "customer",
        "email": data['email'],
        "name": data.get('full_name')
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
    
    # Create user
    user_id = str(uuid.uuid4())
    vendor_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt())
    
    c.execute('''INSERT INTO users (id, email, password, role, full_name, phone, eula_accepted, eula_version, created_at) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, data['email'], hashed.decode(), 'vendor', data.get('business_name'), 
               data.get('phone', ''), 1, '1.0.0', datetime.now().isoformat()))
    
    # Create vendor profile
    c.execute('''INSERT INTO vendors (id, user_id, name, category, address, latitude, longitude, phone, created_at) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (vendor_id, user_id, data.get('business_name'), data.get('business_category'), 
               data.get('address'), data.get('latitude', 13.9443), data.get('longitude', 121.3798), 
               data.get('phone', ''), datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        "session_token": user_id,
        "user_id": user_id,
        "role": "vendor",
        "email": data['email'],
        "name": data.get('business_name')
    })

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id, password, role, full_name FROM users WHERE email = ?', (data['email'],))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"error": "Invalid credentials"}), 401
    
    if not bcrypt.checkpw(data['password'].encode(), row[1].encode()):
        return jsonify({"error": "Invalid credentials"}), 401
    
    return jsonify({
        "session_token": row[0],
        "user_id": row[0],
        "role": row[2],
        "email": data['email'],
        "name": row[3]
    })

# ============================================
# API CUSTOMER ROUTES
# ============================================

@app.route('/api/customer/map/vendors')
def get_nearby_vendors():
    lat = float(request.args.get('lat', 13.9443))
    lng = float(request.args.get('lng', 121.3798))
    radius = float(request.args.get('radius_km', 20))
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id, name, category, description, address, latitude, longitude, rating, logo, phone FROM vendors')
    rows = c.fetchall()
    conn.close()
    
    def distance(lat1, lng1, lat2, lng2):
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
    
    vendors = []
    for row in rows:
        dist = distance(lat, lng, row[5], row[6])
        if dist <= radius:
            vendors.append({
                "id": row[0], "name": row[1], "category": row[2], "description": row[3] or "",
                "address": row[4], "latitude": row[5], "longitude": row[6],
                "rating": row[7] or 0, "logo": row[8] or "", "phone": row[9] or "",
                "distance": round(dist, 2)
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
# RUN
# ============================================

if __name__ == '__main__':
    print("=" * 60)
    print("📍 LAKO - GPS Proximity Discovery Platform")
    print("=" * 60)
    print("Developers: Kyle Brian M. Morillo & Alexander Collin P. Millichamp")
    print("AITE - Capstone Project")
    print("=" * 60)
    print("✅ Server running on http://0.0.0.0:5000")
    print("📍 Customer Dashboard: http://localhost:5000/customer/dashboard")
    print("🏪 Vendor Dashboard: http://localhost:5000/vendor/dashboard")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)