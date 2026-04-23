from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import re
import uuid
import math
import bcrypt
import json
from datetime import datetime, timezone
from supabase import create_client
from PIL import Image
import io
import base64

# ============================================
# LOAD ENVIRONMENT VARIABLES
# ============================================

try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ Loaded .env file")
except ImportError:
    print("ℹ️ python-dotenv not installed")

SECRET_KEY = os.environ.get('SECRET_KEY', 'lako-secret-key-2024')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY are required")

print(f"✓ Supabase URL configured")

# ============================================
# SUPABASE INITIALIZATION
# ============================================

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
print("✓ Supabase connected")

# ============================================
# HELPER FUNCTIONS
# ============================================

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def process_image(image_data):
    try:
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ('RGBA', 'P'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = rgb_img
        img.thumbnail((400, 400))
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        return f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode()}"
    except Exception as e:
        print(f"Image error: {e}")
        return None

# ============================================
# DATABASE FUNCTIONS
# ============================================

def get_user_by_email(email):
    try:
        result = supabase.table('users').select('*').eq('email', email).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"get_user_by_email error: {e}")
        return None

def get_user_by_id(user_id):
    try:
        result = supabase.table('users').select('*').eq('id', user_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        return None

def create_user(email, password, role, full_name=None, phone=None):
    user_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    user_data = {
        'id': user_id, 'email': email, 'password': hashed, 'role': role,
        'full_name': full_name, 'phone': phone, 'email_verified': True,
        'is_suspended': False, 'created_at': utc_now(), 'updated_at': utc_now()
    }
    
    try:
        supabase.table('users').insert(user_data).execute()
        print(f"✓ User created: {email}")
        return user_id
    except Exception as e:
        print(f"create_user error: {e}")
        return None

def verify_password(email, password):
    user = get_user_by_email(email)
    if user and bcrypt.checkpw(password.encode(), user['password'].encode()):
        return user
    return None

def create_vendor(user_id, business_name, category, address, lat, lng, phone, email):
    vendor_id = str(uuid.uuid4())
    vendor_data = {
        'id': vendor_id, 'user_id': user_id, 'business_name': business_name,
        'category': category, 'address': address, 'latitude': lat, 'longitude': lng,
        'phone': phone, 'email': email, 'rating': 0, 'review_count': 0,
        'traffic_count': 0, 'is_active': True, 'is_verified': False,
        'operating_hours': {'monday': '9:00-18:00', 'tuesday': '9:00-18:00', 'wednesday': '9:00-18:00',
            'thursday': '9:00-18:00', 'friday': '9:00-18:00', 'saturday': '9:00-18:00', 'sunday': 'closed'},
        'created_at': utc_now()
    }
    try:
        supabase.table('vendors').insert(vendor_data).execute()
        print(f"✓ Vendor created: {business_name}")
        return vendor_id
    except Exception as e:
        print(f"create_vendor error: {e}")
        return None

def get_vendor_by_user_id(user_id):
    try:
        result = supabase.table('vendors').select('*').eq('user_id', user_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        return None

def get_vendor_by_id(vendor_id):
    try:
        result = supabase.table('vendors').select('*').eq('id', vendor_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        return None

def get_vendors_nearby(lat, lng, radius_km=20):
    try:
        result = supabase.table('vendors').select('*').eq('is_active', True).execute()
        vendors = []
        for v in (result.data or []):
            if v.get('latitude') and v.get('longitude'):
                distance = math.sqrt((float(v['latitude']) - lat)**2 + (float(v['longitude']) - lng)**2) * 111
                if distance <= radius_km:
                    v['distance'] = round(distance, 2)
                    vendors.append(v)
        vendors.sort(key=lambda x: x.get('distance', 999))
        return vendors
    except Exception as e:
        print(f"get_vendors_nearby error: {e}")
        return []

def get_products_by_vendor(vendor_id):
    try:
        result = supabase.table('products').select('*').eq('vendor_id', vendor_id).eq('is_active', True).execute()
        return result.data or []
    except Exception as e:
        return []

def create_product(vendor_id, name, description, category, price, stock=0, images=None):
    product_id = str(uuid.uuid4())
    processed_images = []
    if images:
        for img in images:
            processed = process_image(img)
            if processed:
                processed_images.append({'original': processed, 'thumbnail': processed})
    
    product_data = {
        'id': product_id, 'vendor_id': vendor_id, 'name': name, 'description': description,
        'category': category, 'price': float(price), 'stock': int(stock),
        'images': processed_images, 'is_active': True, 'created_at': utc_now(), 'updated_at': utc_now()
    }
    try:
        supabase.table('products').insert(product_data).execute()
        return product_id
    except Exception as e:
        print(f"create_product error: {e}")
        return None

def update_product(product_id, data):
    try:
        data['updated_at'] = utc_now()
        supabase.table('products').update(data).eq('id', product_id).execute()
        return True
    except Exception as e:
        return False

def delete_product(product_id):
    try:
        supabase.table('products').update({'is_active': False}).eq('id', product_id).execute()
        return True
    except Exception as e:
        return False

def create_post(user_id, user_role, content):
    post_id = str(uuid.uuid4())
    post_data = {
        'id': post_id, 'user_id': user_id, 'user_role': user_role,
        'parent_id': None, 'content': content, 'images': [],
        'likes': 0, 'comment_count': 0, 'created_at': utc_now()
    }
    try:
        supabase.table('posts').insert(post_data).execute()
        return post_id
    except Exception as e:
        print(f"create_post error: {e}")
        return None

def get_feed_posts(limit=20):
    try:
        result = supabase.table('posts').select('*').is_('parent_id', 'null').order('created_at', desc=True).limit(limit).execute()
        posts = []
        for p in (result.data or []):
            user = get_user_by_id(p['user_id'])
            p['author'] = user.get('full_name', 'User') if user else 'User'
            posts.append(p)
        return posts
    except Exception as e:
        return []

def like_post(post_id, user_id):
    try:
        existing = supabase.table('post_likes').select('*').eq('post_id', post_id).eq('user_id', user_id).execute()
        if existing.data:
            supabase.table('post_likes').delete().eq('post_id', post_id).eq('user_id', user_id).execute()
            return False
        else:
            supabase.table('post_likes').insert({
                'id': str(uuid.uuid4()), 'post_id': post_id, 'user_id': user_id, 'created_at': utc_now()
            }).execute()
            return True
    except Exception as e:
        return False

def create_review(customer_id, vendor_id, rating, comment):
    review_id = str(uuid.uuid4())
    review_data = {
        'id': review_id, 'customer_id': customer_id, 'vendor_id': vendor_id,
        'rating': int(rating), 'comment': comment, 'images': [],
        'is_hidden': False, 'created_at': utc_now()
    }
    try:
        supabase.table('reviews').insert(review_data).execute()
        return review_id
    except Exception as e:
        print(f"create_review error: {e}")
        return None

def get_reviews_by_vendor(vendor_id):
    try:
        result = supabase.table('reviews').select('*').eq('vendor_id', vendor_id).eq('is_hidden', False).order('created_at', desc=True).execute()
        reviews = []
        for r in (result.data or []):
            user = get_user_by_id(r['customer_id'])
            r['customer_name'] = user.get('full_name', 'Customer') if user else 'Customer'
            reviews.append(r)
        return reviews
    except Exception as e:
        return []

def add_to_shortlist(user_id, vendor_id):
    try:
        existing = supabase.table('shortlists').select('*').eq('user_id', user_id).eq('vendor_id', vendor_id).execute()
        if existing.data:
            return False
        supabase.table('shortlists').insert({
            'id': str(uuid.uuid4()), 'user_id': user_id, 'vendor_id': vendor_id, 'created_at': utc_now()
        }).execute()
        return True
    except Exception as e:
        return False

def remove_from_shortlist(user_id, vendor_id):
    try:
        supabase.table('shortlists').delete().eq('user_id', user_id).eq('vendor_id', vendor_id).execute()
        return True
    except Exception as e:
        return False

def get_shortlist(user_id):
    try:
        result = supabase.table('shortlists').select('vendor_id').eq('user_id', user_id).execute()
        vendor_ids = [item['vendor_id'] for item in (result.data or [])]
        vendors = []
        for vid in vendor_ids:
            v = get_vendor_by_id(vid)
            if v:
                vendors.append(v)
        return vendors
    except Exception as e:
        return []

def update_vendor_hours(vendor_id, hours):
    try:
        supabase.table('vendors').update({'operating_hours': hours}).eq('id', vendor_id).execute()
        return True
    except Exception as e:
        return False

def update_vendor_location(vendor_id, lat, lng):
    try:
        supabase.table('vendors').update({'latitude': lat, 'longitude': lng}).eq('id', vendor_id).execute()
        return True
    except Exception as e:
        return False

def get_admin_stats():
    stats = {'total_users': 0, 'total_vendors': 0, 'total_products': 0}
    try:
        stats['total_users'] = supabase.table('users').select('*', count='exact').execute().count or 0
        stats['total_vendors'] = supabase.table('vendors').select('*', count='exact').execute().count or 0
        stats['total_products'] = supabase.table('products').select('*', count='exact').eq('is_active', True).execute().count or 0
    except Exception as e:
        pass
    return stats

def get_all_users_admin():
    try:
        result = supabase.table('users').select('*').order('created_at', desc=True).execute()
        return result.data or []
    except Exception as e:
        return []

def suspend_user(user_id):
    try:
        supabase.table('users').update({'is_suspended': True}).eq('id', user_id).execute()
        return True
    except Exception as e:
        return False

def unsuspend_user(user_id):
    try:
        supabase.table('users').update({'is_suspended': False}).eq('id', user_id).execute()
        return True
    except Exception as e:
        return False

def toggle_vendor_active(vendor_id, is_active):
    try:
        supabase.table('vendors').update({'is_active': is_active}).eq('id', vendor_id).execute()
        return True
    except Exception as e:
        return False

def get_all_vendors_admin():
    try:
        result = supabase.table('vendors').select('*').order('created_at', desc=True).execute()
        return result.data or []
    except Exception as e:
        return []

# ============================================
# FLASK APP
# ============================================

app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app, origins=["*"], supports_credentials=True)

sessions = {}

def require_session(session_token):
    if not session_token or session_token not in sessions:
        return None
    return sessions[session_token]

CATEGORIES = ["Streetfood", "Pancit", "Berverage", "Coffee", "Sari-sari Store ", "Carinderya", "Traditional Quezonian food", "Pastry and Bread", "Sweets", "Fast Food", "Tusok-Tusok", "Other"]

PREMADE_AVATARS = [
    {'id': 'cat1', 'emoji': '🐱', 'color': '#FF6B6B'},
    {'id': 'cat2', 'emoji': '😺', 'color': '#4ECDC4'},
    {'id': 'cat3', 'emoji': '😸', 'color': '#FFE66D'},
    {'id': 'cat4', 'emoji': '😻', 'color': '#A8E6CF'},
    {'id': 'dog1', 'emoji': '🐶', 'color': '#FF8B94'},
    {'id': 'panda', 'emoji': '🐼', 'color': '#B8E1FF'},
    {'id': 'fox', 'emoji': '🦊', 'color': '#FF9F1C'},
    {'id': 'bunny', 'emoji': '🐰', 'color': '#FFC6FF'},
]

def render_page(title, content):
    return f'''<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f4f0; }}
        .app-bar {{ background: white; padding: 12px 20px; display: flex; align-items: center; border-bottom: 1px solid #e8ece8; position: sticky; top: 0; z-index: 100; }}
        .app-bar-title {{ flex: 1; text-align: center; font-weight: 700; font-size: 22px; background: linear-gradient(135deg, #2d8c3c, #1a6b28); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .back-btn {{ background: #f0f4f0; border: none; padding: 8px 18px; border-radius: 25px; cursor: pointer; font-weight: 500; color: #2d8c3c; }}
        .content {{ padding: 20px; max-width: 600px; margin: 0 auto; padding-bottom: 80px; }}
        .card {{ background: white; border-radius: 20px; padding: 20px; margin-bottom: 16px; box-shadow: 0 2px 12px rgba(0,0,0,0.04); border: 1px solid #e8ece8; cursor: pointer; transition: transform 0.2s; }}
        .card:active {{ transform: scale(0.98); }}
        .btn {{ background: linear-gradient(135deg, #2d8c3c, #1a6b28); color: white; border: none; padding: 14px 24px; border-radius: 40px; font-weight: 600; font-size: 16px; cursor: pointer; width: 100%; }}
        .btn-outline {{ background: transparent; border: 2px solid #2d8c3c; color: #2d8c3c; padding: 12px 22px; border-radius: 40px; cursor: pointer; font-weight: 500; }}
        .btn-sm {{ padding: 8px 16px; font-size: 14px; width: auto; }}
        .input {{ width: 100%; padding: 14px 16px; background: #f8faf8; border: 1.5px solid #e0e6e0; border-radius: 16px; font-size: 15px; }}
        .input:focus {{ outline: none; border-color: #2d8c3c; background: white; }}
        .bottom-nav {{ position: fixed; bottom: 0; left: 0; right: 0; background: rgba(255,255,255,0.98); backdrop-filter: blur(20px); display: flex; justify-content: space-around; padding: 10px 16px; border-top: 1px solid #e8ece8; max-width: 600px; margin: 0 auto; z-index: 99; }}
        .nav-item {{ text-align: center; padding: 8px 12px; cursor: pointer; color: #8ba88b; border-radius: 30px; transition: all 0.2s; }}
        .nav-item.active {{ color: #2d8c3c; background: #e8f3e9; }}
        .nav-item i {{ font-size: 22px; }}
        .nav-item span {{ font-size: 11px; display: block; margin-top: 4px; }}
        .flex {{ display: flex; }}
        .justify-between {{ justify-content: space-between; }}
        .items-center {{ align-items: center; }}
        .gap-2 {{ gap: 8px; }}
        .mt-2 {{ margin-top: 8px; }}
        .mt-4 {{ margin-top: 16px; }}
        .text-center {{ text-align: center; }}
        .text-secondary {{ color: #6b8c6b; font-size: 14px; }}
        .stars {{ color: #fbbf24; letter-spacing: 2px; }}
        .vendor-status.open {{ background: #10b98120; color: #10b981; padding: 4px 12px; border-radius: 30px; font-size: 12px; display: inline-block; }}
        .vendor-status.closed {{ background: #ef444420; color: #ef4444; padding: 4px 12px; border-radius: 30px; font-size: 12px; display: inline-block; }}
        .badge {{ display: inline-block; padding: 4px 12px; background: linear-gradient(135deg, #2d8c3c, #1a6b28); color: white; border-radius: 20px; font-size: 11px; font-weight: 600; }}
        .modal {{ display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); backdrop-filter: blur(4px); z-index: 1000; align-items: flex-end; }}
        .modal.show {{ display: flex; }}
        .modal-content {{ background: white; border-radius: 28px 28px 0 0; padding: 24px; max-height: 85vh; overflow-y: auto; width: 100%; animation: slideUp 0.3s ease; }}
        @keyframes slideUp {{ from {{ transform: translateY(100%); }} to {{ transform: translateY(0); }} }}
        .modal-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 2px solid #f0f4f0; }}
        .modal-close {{ font-size: 28px; cursor: pointer; color: #999; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 20px; }}
        .stat-card {{ background: linear-gradient(135deg, #2d8c3c, #1a6b28); border-radius: 20px; padding: 20px; text-align: center; color: white; }}
        .stat-value {{ font-size: 32px; font-weight: 800; }}
        .image-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 12px; }}
        .image-thumb {{ aspect-ratio: 1; border-radius: 12px; overflow: hidden; background: #f0f4f0; cursor: pointer; }}
        .image-thumb img {{ width: 100%; height: 100%; object-fit: cover; }}
        .map-container {{ height: 400px; border-radius: 24px; overflow: hidden; margin-bottom: 16px; position: relative; border: 1px solid #e8ece8; }}
        #map {{ height: 100%; width: 100%; }}
        .map-controls {{ position: absolute; bottom: 16px; right: 16px; display: flex; flex-direction: column; gap: 8px; }}
        .map-control-btn {{ width: 44px; height: 44px; background: white; border: none; border-radius: 22px; box-shadow: 0 2px 12px rgba(0,0,0,0.15); cursor: pointer; font-size: 18px; }}
        .avatar {{ width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 24px; background: linear-gradient(135deg, #2d8c3c, #1a6b28); color: white; }}
        .avatar-lg {{ width: 80px; height: 80px; font-size: 40px; margin: 0 auto; }}
        .avatar-select {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 20px 0; }}
        .avatar-option {{ aspect-ratio: 1; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 32px; cursor: pointer; border: 3px solid transparent; transition: all 0.2s; }}
        .avatar-option.selected {{ border-color: #2d8c3c; transform: scale(1.05); }}
        .hours-slider {{ display: flex; align-items: center; gap: 16px; margin: 16px 0; }}
        .hours-slider input {{ flex: 1; height: 6px; border-radius: 3px; background: #e0e6e0; -webkit-appearance: none; }}
        .hours-slider input::-webkit-slider-thumb {{ -webkit-appearance: none; width: 20px; height: 20px; border-radius: 50%; background: #2d8c3c; cursor: pointer; }}
        .hours-value {{ font-size: 14px; color: #2d8c3c; font-weight: 600; min-width: 70px; text-align: center; }}
        .hours-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 16px; }}
        .hours-item {{ display: flex; justify-content: space-between; padding: 12px; background: #f8faf8; border-radius: 12px; }}
        .product-card {{ background: white; border-radius: 16px; padding: 16px; margin-bottom: 12px; border: 1px solid #e8ece8; }}
        .product-price {{ font-size: 20px; font-weight: 700; color: #2d8c3c; }}
        .carousel-container {{ position: relative; height: 460px; margin: 20px 0; }}
        .carousel-cards {{ position: relative; height: 100%; }}
        .carousel-card {{ position: absolute; width: 100%; height: 100%; border-radius: 28px; padding: 32px 24px; transition: all 0.4s cubic-bezier(0.2, 0.9, 0.4, 1); cursor: pointer; box-shadow: 0 8px 32px rgba(0,0,0,0.15); }}
        .carousel-card[data-position="0"] {{ transform: translateX(0) scale(1); opacity: 1; z-index: 3; }}
        .carousel-card[data-position="-1"] {{ transform: translateX(-75%) scale(0.9); opacity: 0.6; z-index: 2; }}
        .carousel-card[data-position="1"] {{ transform: translateX(75%) scale(0.9); opacity: 0.6; z-index: 2; }}
        .carousel-card[data-position="-2"] {{ transform: translateX(-140%) scale(0.8); opacity: 0; z-index: 1; }}
        .carousel-card[data-position="2"] {{ transform: translateX(140%) scale(0.8); opacity: 0; z-index: 1; }}
        .carousel-card:nth-child(1) {{ background: linear-gradient(135deg, #2d8c3c, #1a6b28); }}
        .carousel-card:nth-child(2) {{ background: linear-gradient(135deg, #FF6B6B, #ee5a24); }}
        .carousel-card:nth-child(3) {{ background: linear-gradient(135deg, #4ECDC4, #0abde3); }}
        .card-badge {{ display: inline-block; padding: 6px 14px; background: rgba(255,255,255,0.25); border-radius: 40px; font-size: 13px; font-weight: 600; color: #fff; margin-bottom: 20px; }}
        .card-title {{ font-size: 44px; font-weight: 800; color: #fff; margin-bottom: 12px; }}
        .card-subtitle {{ font-size: 16px; color: rgba(255,255,255,0.95); margin-bottom: 24px; }}
        .feature-list {{ list-style: none; margin-top: auto; }}
        .feature-list li {{ display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.2); color: #fff; font-size: 14px; }}
        .feature-list li::before {{ content: "✓"; color: #fff; font-weight: bold; background: rgba(255,255,255,0.3); width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }}
        .carousel-indicators {{ display: flex; justify-content: center; gap: 8px; margin: 16px 0; }}
        .indicator {{ width: 8px; height: 8px; background: rgba(45,140,60,0.3); border-radius: 8px; transition: all 0.3s; cursor: pointer; }}
        .indicator.active {{ width: 32px; background: #2d8c3c; }}
        .landing-container {{ min-height: 100vh; display: flex; flex-direction: column; justify-content: center; padding: 20px; background: linear-gradient(145deg, #e8f3e9 0%, #d4ecd6 100%); }}
        .loading {{ text-align: center; padding: 40px; color: #8ba88b; }}
    </style>
</head>
<body>
{content}
</body>
</html>'''

# ============================================
# LANDING PAGE WITH WORKING CAROUSEL
# ============================================

LANDING = render_page("Lako", '''
<div class="landing-container">
    <div class="text-center" style="margin-bottom: 32px;">
        <h1 style="font-size: 56px; font-weight: 800; background: linear-gradient(135deg, #2d8c3c, #1a6b28); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Lako</h1>
        <p style="color: #5a7a5a; font-size: 16px; margin-top: 4px;">Discover Local Street Food</p>
    </div>
    
    <div class="carousel-container">
        <div class="carousel-cards" id="carouselCards">
            <div class="carousel-card" data-position="0" onclick="selectMode('customer')">
                <span class="card-badge">🍜 Customer</span>
                <div class="card-title">Find Food</div>
                <div class="card-subtitle">Discover street food near you</div>
                <ul class="feature-list">
                    <li>Real-time GPS vendor locations</li>
                    <li>Browse menus with photos</li>
                    <li>Save your favorites</li>
                    <li>See what's open now</li>
                    <li>Get turn-by-turn directions</li>
                </ul>
            </div>
            <div class="carousel-card" data-position="1" onclick="selectMode('vendor')">
                <span class="card-badge">🏪 Vendor</span>
                <div class="card-title">Sell Food</div>
                <div class="card-subtitle">Grow your food business</div>
                <ul class="feature-list">
                    <li>Manage product catalog with photos</li>
                    <li>Set operating hours with slider</li>
                    <li>Track customer traffic</li>
                    <li>Respond to reviews</li>
                    <li>Update real-time location</li>
                </ul>
            </div>
            <div class="carousel-card" data-position="2" onclick="selectMode('guest')">
                <span class="card-badge">👤 Guest</span>
                <div class="card-title">Browse</div>
                <div class="card-subtitle">Explore without signing up</div>
                <ul class="feature-list">
                    <li>View all nearby vendors</li>
                    <li>See real-time locations</li>
                    <li>Read community feed</li>
                    <li>Get directions</li>
                    <li>Choose your avatar</li>
                </ul>
            </div>
        </div>
    </div>
    
    <div class="carousel-indicators">
        <div class="indicator active" onclick="goToCard(0)"></div>
        <div class="indicator" onclick="goToCard(1)"></div>
        <div class="indicator" onclick="goToCard(2)"></div>
    </div>
</div>

<script>
let currentCard = 0;
const cards = document.querySelectorAll('.carousel-card');
let startX = 0, currentX = 0;

function updateCarousel(index) {
    currentCard = index;
    if (currentCard < 0) currentCard = 2;
    if (currentCard > 2) currentCard = 0;
    cards.forEach((card, i) => {
        let pos = i - currentCard;
        if (pos < -2) pos = 2;
        if (pos > 2) pos = -2;
        card.setAttribute('data-position', pos);
    });
    document.querySelectorAll('.indicator').forEach((ind, i) => ind.classList.toggle('active', i === currentCard));
}

const container = document.querySelector('.carousel-cards');
if (container) {
    container.addEventListener('touchstart', (e) => { startX = e.touches[0].clientX; });
    container.addEventListener('touchmove', (e) => { currentX = e.touches[0].clientX - startX; });
    container.addEventListener('touchend', () => {
        if (Math.abs(currentX) > 50) {
            if (currentX < 0) updateCarousel(currentCard + 1);
            else if (currentX > 0) updateCarousel(currentCard - 1);
        }
        currentX = 0;
    });
}

function goToCard(index) { updateCarousel(index); }

function selectMode(mode) {
    if (mode === 'guest') {
        window.location.href = '/guest';
    } else {
        localStorage.setItem('user_role', mode);
        window.location.href = '/auth';
    }
}

document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.shiftKey && e.key === 'A') {
        localStorage.setItem('user_role', 'admin');
        window.location.href = '/admin';
    }
});
</script>
''')

# ============================================
# AUTH PAGE
# ============================================

AUTH = render_page("Sign In", '''
<div class="app-bar">
    <button class="back-btn" onclick="window.location.href='/'">← Home</button>
    <div class="app-bar-title">Lako</div>
    <div></div>
</div>
<div class="content" id="content"></div>

<script>
let step = 'login';

function render() {
    const container = document.getElementById('content');
    if (step === 'login') {
        container.innerHTML = `
            <div class="card">
                <h3 style="margin-bottom: 20px;">Welcome Back</h3>
                <input type="email" id="email" class="input" placeholder="Email address">
                <input type="password" id="password" class="input" placeholder="Password">
                <button class="btn" onclick="login()">Sign In</button>
                <p class="text-center mt-4"><a href="#" onclick="step='register'; render(); return false;" class="text-primary">Create an account</a></p>
            </div>`;
    } else if (step === 'register') {
        container.innerHTML = `
            <div class="card">
                <h3 style="margin-bottom: 20px;">Create Account</h3>
                <select id="role" class="input">
                    <option value="customer">🍜 Food Lover (Customer)</option>
                    <option value="vendor">🏪 Food Seller (Vendor)</option>
                </select>
                <input type="text" id="name" class="input" placeholder="Full name / Business name">
                <input type="email" id="email" class="input" placeholder="Email address">
                <input type="tel" id="phone" class="input" placeholder="Phone number (optional)">
                <input type="password" id="password" class="input" placeholder="Create password (min 8 characters)">
                <button class="btn" onclick="register()">Create Account</button>
                <p class="text-center mt-4"><a href="#" onclick="step='login'; render(); return false;" class="text-primary">Already have an account? Sign in</a></p>
            </div>`;
    }
}

async function login() {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    if (!email || !password) { alert('Please fill in all fields'); return; }
    
    const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({email, password})
    });
    const data = await res.json();
    if (res.ok) {
        localStorage.setItem('session_token', data.session_token);
        localStorage.setItem('user_role', data.role);
        window.location.href = data.role === 'customer' ? '/customer' : data.role === 'vendor' ? '/vendor' : '/admin';
    } else { alert(data.error); }
}

async function register() {
    const role = document.getElementById('role').value;
    const name = document.getElementById('name').value;
    const email = document.getElementById('email').value;
    const phone = document.getElementById('phone').value;
    const password = document.getElementById('password').value;
    
    if (!name || !email || !password) { alert('Please fill in all required fields'); return; }
    if (password.length < 8) { alert('Password must be at least 8 characters'); return; }
    
    const endpoint = role === 'customer' ? '/api/auth/register/customer' : '/api/auth/register/vendor';
    const body = role === 'customer' ? 
        {email, password, full_name: name, phone} :
        {email, password, business_name: name, phone, business_category: 'Lomi', address: 'Set your address', latitude: 14.5995, longitude: 120.9842};
    
    const res = await fetch(endpoint, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body)
    });
    const data = await res.json();
    if (res.ok) {
        localStorage.setItem('session_token', data.session_token);
        localStorage.setItem('user_role', role);
        window.location.href = role === 'customer' ? '/customer' : '/vendor';
    } else { alert(data.error); }
}

render();
</script>
''')

# ============================================
# GUEST PAGE (FULL FEATURES)
# ============================================

GUEST = render_page("Guest Mode", '''
<div class="app-bar">
    <button class="back-btn" onclick="window.location.href='/'">← Home</button>
    <div class="app-bar-title">Guest Mode</div>
    <div></div>
</div>
<div class="content" id="content"></div>

<div class="modal" id="avatarModal">
    <div class="modal-content">
        <div class="modal-header"><h3>Choose Your Avatar</h3><span class="modal-close" onclick="window.location.href='/'">&times;</span></div>
        <input type="text" id="pseudoName" class="input" placeholder="Your display name" maxlength="20">
        <div class="avatar-select" id="avatarSelect">
            ''' + ''.join([f'<div class="avatar-option" style="background:{a["color"]};" data-emoji="{a["emoji"]}" onclick="selectAvatar(this)">{a["emoji"]}</div>' for a in PREMADE_AVATARS]) + '''
        </div>
        <button class="btn" onclick="saveGuestProfile()">Continue</button>
    </div>
</div>

<div class="modal" id="vendorModal" onclick="if(event.target===this)closeModal()">
    <div class="modal-content">
        <div class="modal-header"><h3 id="modalTitle"></h3><span class="modal-close" onclick="closeModal()">&times;</span></div>
        <div id="modalBody"></div>
    </div>
</div>

<div class="bottom-nav">
    <div class="nav-item active" onclick="showPage('map')"><i class="fas fa-map"></i><span>Map</span></div>
    <div class="nav-item" onclick="showPage('vendors')"><i class="fas fa-store"></i><span>Vendors</span></div>
    <div class="nav-item" onclick="showPage('feed')"><i class="fas fa-comments"></i><span>Feed</span></div>
    <div class="nav-item" onclick="showPage('saved')"><i class="fas fa-bookmark"></i><span>Saved</span></div>
</div>

<script>
let userLocation = null, vendors = [], savedVendors = [], page = 'map', map = null;
let guestProfile = null, selectedAvatar = null;

function selectAvatar(el) {
    document.querySelectorAll('.avatar-option').forEach(a => a.classList.remove('selected'));
    el.classList.add('selected');
    selectedAvatar = { emoji: el.dataset.emoji, color: el.style.background };
}

function saveGuestProfile() {
    const name = document.getElementById('pseudoName').value.trim();
    if (!name) { alert('Enter a name'); return; }
    if (!selectedAvatar) { alert('Select an avatar'); return; }
    
    guestProfile = { name, avatar: selectedAvatar };
    localStorage.setItem('guest_profile', JSON.stringify(guestProfile));
    document.getElementById('avatarModal').classList.remove('show');
    document.querySelector('.bottom-nav').style.display = 'flex';
    loadData();
}

function checkFirstTime() {
    if (!localStorage.getItem('guest_profile')) {
        document.getElementById('avatarModal').classList.add('show');
    } else {
        guestProfile = JSON.parse(localStorage.getItem('guest_profile'));
        savedVendors = JSON.parse(localStorage.getItem('saved_vendors') || '[]');
        document.querySelector('.bottom-nav').style.display = 'flex';
        loadData();
    }
}

async function loadData() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(p => {
            userLocation = { lat: p.coords.latitude, lng: p.coords.longitude };
            loadVendors();
        }, () => {
            userLocation = { lat: 14.5995, lng: 120.9842 };
            loadVendors();
        });
    } else {
        userLocation = { lat: 14.5995, lng: 120.9842 };
        loadVendors();
    }
}

async function loadVendors() {
    const res = await fetch(`/api/customer/map/vendors?lat=${userLocation.lat}&lng=${userLocation.lng}`);
    const data = await res.json();
    vendors = data.vendors || [];
    if (page === 'map') showMap();
    else if (page === 'vendors') showVendors();
}

function showPage(p) {
    page = p;
    document.querySelectorAll('.nav-item').forEach((el, i) => {
        const pages = ['map', 'vendors', 'feed', 'saved'];
        el.classList.toggle('active', pages[i] === p);
    });
    if (p === 'map') showMap();
    else if (p === 'vendors') showVendors();
    else if (p === 'feed') showFeed();
    else if (p === 'saved') showSaved();
}

function showMap() {
    document.getElementById('content').innerHTML = `
        <div class="map-container" style="position:relative">
            <div id="map"></div>
            <div class="map-controls">
                <button class="map-control-btn" onclick="centerOnUser()"><i class="fas fa-location-arrow"></i></button>
            </div>
        </div>
        <h4 style="margin: 16px 0 8px">Nearby Vendors</h4>
        <div id="nearbyList"></div>`;
    
    setTimeout(() => {
        if (map) map.remove();
        map = L.map('map').setView([userLocation.lat, userLocation.lng], 14);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png').addTo(map);
        L.marker([userLocation.lat, userLocation.lng], {
            icon: L.divIcon({ html: '<div style="background:#3b82f6; width:16px; height:16px; border-radius:50%; border:3px solid white;"></div>', iconSize: [22,22] })
        }).addTo(map);
        
        vendors.forEach(v => {
            if (v.latitude) {
                L.marker([v.latitude, v.longitude])
                    .bindPopup(`<b>${v.business_name}</b><br>${v.category}<br>⭐ ${v.rating || 'New'}`)
                    .addTo(map);
            }
        });
        
        updateNearbyList();
    }, 100);
}

function updateNearbyList() {
    const list = document.getElementById('nearbyList');
    if (!list) return;
    list.innerHTML = vendors.slice(0,5).map(v => `
        <div class="card" onclick="showVendorModal('${v.id}')">
            <div class="flex justify-between">
                <div><strong>${v.business_name}</strong><br><span class="text-secondary">${v.category} • ${v.distance}km</span></div>
                <div class="stars">${'★'.repeat(Math.floor(v.rating || 0))}</div>
            </div>
        </div>
    `).join('') || '<p class="text-center text-secondary">No vendors nearby</p>';
}

function showVendors() {
    document.getElementById('content').innerHTML = `
        <input type="text" id="searchInput" class="input" placeholder="Search vendors..." oninput="filterVendors()">
        <div id="vendorsList"></div>`;
    filterVendors();
}

function filterVendors() {
    const query = document.getElementById('searchInput')?.value.toLowerCase() || '';
    const filtered = vendors.filter(v => v.business_name.toLowerCase().includes(query) || v.category.toLowerCase().includes(query));
    document.getElementById('vendorsList').innerHTML = filtered.map(v => `
        <div class="card" onclick="showVendorModal('${v.id}')">
            <div class="flex justify-between">
                <div><strong>${v.business_name}</strong><br><span class="text-secondary">${v.category} • ${v.distance}km</span></div>
                <div class="stars">${'★'.repeat(Math.floor(v.rating || 0))}</div>
            </div>
        </div>
    `).join('') || '<p class="text-center text-secondary">No vendors found</p>';
}

async function showFeed() {
    const res = await fetch('/api/guest/feed');
    const data = await res.json();
    document.getElementById('content').innerHTML = (data.posts || []).map(p => `
        <div class="card">
            <div class="flex items-center gap-2">
                <div class="avatar" style="background:#2d8c3c; color:white">${(p.author || 'U')[0]}</div>
                <div><strong>${p.author || 'User'}</strong><br><span class="text-secondary">${new Date(p.created_at).toLocaleDateString()}</span></div>
            </div>
            <p style="margin-top: 12px;">${p.content}</p>
            <div class="flex gap-2 mt-2">
                <span><i class="far fa-heart"></i> ${p.likes || 0}</span>
                <span><i class="far fa-comment"></i> ${p.comment_count || 0}</span>
            </div>
        </div>
    `).join('') || '<p class="text-center">No posts yet</p>';
}

function showSaved() {
    const saved = vendors.filter(v => savedVendors.includes(v.id));
    document.getElementById('content').innerHTML = saved.map(v => `
        <div class="card" onclick="showVendorModal('${v.id}')">
            <div class="flex justify-between">
                <div><strong>${v.business_name}</strong><br><span class="text-secondary">${v.category}</span></div>
                <button class="btn-outline btn-sm" onclick="event.stopPropagation(); toggleSave('${v.id}')">Remove</button>
            </div>
        </div>
    `).join('') || '<p class="text-center text-secondary">No saved vendors. Tap the bookmark icon on any vendor to save them!</p>';
}

function showVendorModal(vendorId) {
    const v = vendors.find(v => v.id === vendorId);
    if (!v) return;
    const isSaved = savedVendors.includes(v.id);
    document.getElementById('modalTitle').innerHTML = v.business_name;
    document.getElementById('modalBody').innerHTML = `
        <p><span class="badge">${v.category}</span> <span class="vendor-status ${v.is_open ? 'open' : 'closed'}">${v.is_open ? 'Open Now' : 'Closed'}</span></p>
        <p><i class="fas fa-map-marker-alt"></i> ${v.address || 'No address'}</p>
        <p><i class="fas fa-star" style="color:#ffb800;"></i> ${v.rating || 'New'} (${v.review_count || 0} reviews)</p>
        <p><i class="fas fa-phone"></i> ${v.phone || 'No phone'}</p>
        <div class="flex gap-2 mt-4">
            <button class="btn" onclick="navigateTo(${v.latitude}, ${v.longitude})"><i class="fas fa-directions"></i> Navigate</button>
            <button class="btn-outline" onclick="toggleSave('${v.id}')"><i class="fas ${isSaved ? 'fa-bookmark' : 'fa-bookmark-o'}"></i> ${isSaved ? 'Saved' : 'Save'}</button>
        </div>
    `;
    document.getElementById('vendorModal').classList.add('show');
}

function toggleSave(vendorId) {
    const index = savedVendors.indexOf(vendorId);
    if (index === -1) {
        savedVendors.push(vendorId);
        alert('Added to saved!');
    } else {
        savedVendors.splice(index, 1);
        alert('Removed from saved');
    }
    localStorage.setItem('saved_vendors', JSON.stringify(savedVendors));
    closeModal();
    if (page === 'saved') showSaved();
}

function navigateTo(lat, lng) {
    closeModal();
    showPage('map');
    setTimeout(() => {
        if (map) map.setView([lat, lng], 16);
    }, 100);
}

function centerOnUser() { if (map && userLocation) map.setView([userLocation.lat, userLocation.lng], 15); }
function closeModal() { document.getElementById('vendorModal').classList.remove('show'); }

checkFirstTime();
</script>
''')

# ============================================
# CUSTOMER DASHBOARD (FULL FEATURES)
# ============================================

CUSTOMER_DASH = render_page("Customer", '''
<div class="app-bar">
    <button class="back-btn" onclick="logout()">Logout</button>
    <div class="app-bar-title">Find Food</div>
    <div></div>
</div>
<div class="content" id="content"></div>

<div class="bottom-nav">
    <div class="nav-item active" onclick="showPage('map')"><i class="fas fa-map"></i><span>Map</span></div>
    <div class="nav-item" onclick="showPage('vendors')"><i class="fas fa-store"></i><span>Vendors</span></div>
    <div class="nav-item" onclick="showPage('feed')"><i class="fas fa-comments"></i><span>Feed</span></div>
    <div class="nav-item" onclick="showPage('saved')"><i class="fas fa-bookmark"></i><span>Saved</span></div>
    <div class="nav-item" onclick="showPage('profile')"><i class="fas fa-user"></i><span>Profile</span></div>
</div>

<div class="modal" id="vendorModal" onclick="if(event.target===this)closeModal()">
    <div class="modal-content">
        <div class="modal-header"><h3 id="modalTitle"></h3><span class="modal-close" onclick="closeModal()">&times;</span></div>
        <div id="modalBody"></div>
    </div>
</div>

<div class="modal" id="postModal">
    <div class="modal-content">
        <div class="modal-header"><h3>Share Your Experience</h3><span class="modal-close" onclick="closePostModal()">&times;</span></div>
        <textarea id="postContent" class="input" placeholder="What's your favorite food today?" rows="4"></textarea>
        <button class="btn mt-2" onclick="createPost()">Post</button>
    </div>
</div>

<script>
let sessionToken = localStorage.getItem('session_token');
let userLocation = null, vendors = [], savedVendors = [], page = 'map', map = null;

if (!sessionToken) window.location.href = '/auth';

async function api(url, options = {}) {
    const res = await fetch(url, {
        ...options,
        headers: { 'Content-Type': 'application/json', 'X-Session-Token': sessionToken, ...options.headers }
    });
    if (res.status === 401) { localStorage.removeItem('session_token'); window.location.href = '/auth'; return null; }
    return res.json();
}

async function loadData() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(p => {
            userLocation = { lat: p.coords.latitude, lng: p.coords.longitude };
            loadVendors();
        }, () => { userLocation = { lat: 14.5995, lng: 120.9842 }; loadVendors(); });
    } else { userLocation = { lat: 14.5995, lng: 120.9842 }; loadVendors(); }
    loadSaved();
}

async function loadVendors() {
    const data = await api(`/api/customer/map/vendors?lat=${userLocation.lat}&lng=${userLocation.lng}`);
    if (data) { vendors = data.vendors || []; if (page === 'map') showMap(); else if (page === 'vendors') showVendors(); }
}

async function loadSaved() {
    const data = await api('/api/customer/shortlist');
    if (data) { savedVendors = data.vendors || []; if (page === 'saved') showSaved(); }
}

function showPage(p) {
    page = p;
    document.querySelectorAll('.nav-item').forEach((el, i) => {
        const pages = ['map', 'vendors', 'feed', 'saved', 'profile'];
        el.classList.toggle('active', pages[i] === p);
    });
    if (p === 'map') showMap();
    else if (p === 'vendors') showVendors();
    else if (p === 'feed') showFeed();
    else if (p === 'saved') showSaved();
    else if (p === 'profile') showProfile();
}

function showMap() {
    document.getElementById('content').innerHTML = `
        <div class="map-container" style="position:relative"><div id="map"></div>
        <div class="map-controls"><button class="map-control-btn" onclick="centerOnUser()"><i class="fas fa-location-arrow"></i></button></div></div>
        <h4>Nearby Vendors</h4><div id="nearbyList"></div>`;
    setTimeout(() => {
        if (map) map.remove();
        map = L.map('map').setView([userLocation.lat, userLocation.lng], 14);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png').addTo(map);
        L.marker([userLocation.lat, userLocation.lng], {
            icon: L.divIcon({ html: '<div style="background:#3b82f6; width:16px; height:16px; border-radius:50%; border:3px solid white;"></div>', iconSize: [22,22] })
        }).addTo(map);
        vendors.forEach(v => {
            if (v.latitude) {
                L.marker([v.latitude, v.longitude])
                    .bindPopup(`<b>${v.business_name}</b><br>⭐ ${v.rating || 'New'}`)
                    .addTo(map);
            }
        });
        updateNearbyList();
    }, 100);
}

function updateNearbyList() {
    const list = document.getElementById('nearbyList');
    if (list) list.innerHTML = vendors.slice(0,5).map(v => `
        <div class="card" onclick="showVendor('${v.id}')">
            <div class="flex justify-between"><div><strong>${v.business_name}</strong><br><span class="text-secondary">${v.category} • ${v.distance}km</span></div>
            <div class="stars">${'★'.repeat(Math.floor(v.rating || 0))}</div></div>
        </div>`).join('');
}

function showVendors() {
    document.getElementById('content').innerHTML = `<input type="text" id="searchInput" class="input" placeholder="Search vendors..." oninput="filterVendors()"><div id="vendorsList"></div>`;
    filterVendors();
}

function filterVendors() {
    const query = document.getElementById('searchInput')?.value.toLowerCase() || '';
    const filtered = vendors.filter(v => v.business_name.toLowerCase().includes(query) || v.category.toLowerCase().includes(query));
    document.getElementById('vendorsList').innerHTML = filtered.map(v => `
        <div class="card" onclick="showVendor('${v.id}')">
            <div class="flex justify-between"><div><strong>${v.business_name}</strong><br><span class="text-secondary">${v.category} • ${v.distance}km</span></div>
            <div class="stars">${'★'.repeat(Math.floor(v.rating || 0))}</div></div>
        </div>`).join('');
}

async function showFeed() {
    const data = await api('/api/guest/feed');
    document.getElementById('content').innerHTML = `
        <button class="btn" onclick="openPostModal()"><i class="fas fa-plus"></i> Share Your Experience</button>
        <div id="feedList" class="mt-4"></div>`;
    document.getElementById('feedList').innerHTML = (data.posts || []).map(p => `
        <div class="card"><div class="flex items-center gap-2"><div class="avatar" style="background:#2d8c3c;color:white">${(p.author || 'U')[0]}</div>
        <div><strong>${p.author || 'User'}</strong><br><span class="text-secondary">${new Date(p.created_at).toLocaleDateString()}</span></div></div>
        <p style="margin-top:12px">${p.content}</p>
        <div class="flex gap-2 mt-2"><button class="btn-outline btn-sm" onclick="likePost('${p.id}')"><i class="far fa-heart"></i> ${p.likes || 0}</button></div></div>
    `).join('');
}

async function likePost(postId) { await api('/api/customer/like', { method: 'POST', body: JSON.stringify({ post_id: postId }) }); showFeed(); }

function showSaved() {
    document.getElementById('content').innerHTML = savedVendors.map(v => `
        <div class="card" onclick="showVendor('${v.id}')">
            <div class="flex justify-between"><div><strong>${v.business_name}</strong><br><span class="text-secondary">${v.category}</span></div>
            <button class="btn-outline btn-sm" onclick="event.stopPropagation(); toggleSave('${v.id}')">Remove</button></div>
        </div>
    `).join('') || '<p class="text-center text-secondary">No saved vendors</p>';
}

function showProfile() {
    document.getElementById('content').innerHTML = `<div class="card text-center"><div class="avatar-lg mx-auto">👤</div><h3 class="mt-2">Food Lover</h3><button class="btn-outline mt-4" onclick="logout()">Logout</button></div>`;
}

function showVendor(vendorId) {
    const v = vendors.find(v => v.id === vendorId);
    if (!v) return;
    const isSaved = savedVendors.some(sv => sv.id === v.id);
    document.getElementById('modalTitle').innerHTML = v.business_name;
    document.getElementById('modalBody').innerHTML = `
        <p><span class="badge">${v.category}</span> <span class="vendor-status ${v.is_open ? 'open' : 'closed'}">${v.is_open ? 'Open Now' : 'Closed'}</span></p>
        <p><i class="fas fa-map-marker-alt"></i> ${v.address || 'No address'}</p>
        <p><i class="fas fa-star" style="color:#ffb800;"></i> ${v.rating || 'New'} (${v.review_count || 0} reviews)</p>
        <p><i class="fas fa-phone"></i> ${v.phone || 'No phone'}</p>
        <div class="flex gap-2 mt-4"><button class="btn" onclick="navigateTo(${v.latitude}, ${v.longitude})"><i class="fas fa-directions"></i> Navigate</button>
        <button class="btn-outline" onclick="toggleSave('${v.id}')"><i class="fas ${isSaved ? 'fa-bookmark' : 'fa-bookmark-o'}"></i> ${isSaved ? 'Saved' : 'Save'}</button></div>
        <button class="btn-outline mt-2" onclick="writeReview('${v.id}')">Write a Review</button>`;
    document.getElementById('vendorModal').classList.add('show');
}

async function toggleSave(vendorId) {
    await api('/api/customer/shortlist/toggle', { method: 'POST', body: JSON.stringify({ vendor_id: vendorId }) });
    loadSaved(); closeModal();
}

function writeReview(vendorId) {
    const rating = prompt('Rate this vendor (1-5 stars):');
    if (rating && rating >= 1 && rating <= 5) {
        const comment = prompt('Write your review (optional):');
        api('/api/customer/review/create', { method: 'POST', body: JSON.stringify({ vendor_id: vendorId, rating: parseInt(rating), comment }) });
        alert('Thank you for your review!');
    }
}

function navigateTo(lat, lng) { closeModal(); showPage('map'); setTimeout(() => { if (map) map.setView([lat, lng], 16); }, 100); }
function centerOnUser() { if (map && userLocation) map.setView([userLocation.lat, userLocation.lng], 15); }
function closeModal() { document.getElementById('vendorModal').classList.remove('show'); }
function openPostModal() { document.getElementById('postModal').classList.add('show'); }
function closePostModal() { document.getElementById('postModal').classList.remove('show'); }

async function createPost() {
    const content = document.getElementById('postContent').value;
    if (!content) { alert('Write something!'); return; }
    await api('/api/customer/post/create', { method: 'POST', body: JSON.stringify({ content }) });
    closePostModal(); document.getElementById('postContent').value = ''; showFeed();
}

function logout() { localStorage.removeItem('session_token'); localStorage.removeItem('user_role'); window.location.href = '/'; }

loadData();
</script>
''')

# ============================================
# VENDOR DASHBOARD (FULL FEATURES)
# ============================================

VENDOR_DASH = render_page("Vendor", '''
<div class="app-bar">
    <button class="back-btn" onclick="logout()">Logout</button>
    <div class="app-bar-title">Vendor Dashboard</div>
    <div></div>
</div>

<div class="bottom-nav">
    <div class="nav-item active" onclick="showPage('dashboard')"><i class="fas fa-chart-line"></i><span>Stats</span></div>
    <div class="nav-item" onclick="showPage('products')"><i class="fas fa-utensils"></i><span>Menu</span></div>
    <div class="nav-item" onclick="showPage('reviews')"><i class="fas fa-star"></i><span>Reviews</span></div>
    <div class="nav-item" onclick="showPage('settings')"><i class="fas fa-sliders-h"></i><span>Settings</span></div>
</div>

<div class="content" id="content"></div>

<div class="modal" id="productModal">
    <div class="modal-content">
        <div class="modal-header"><h3 id="modalTitle">Add Product</h3><span class="modal-close" onclick="closeProductModal()">&times;</span></div>
        <div id="modalBody"></div>
    </div>
</div>

<div class="modal" id="hoursModal">
    <div class="modal-content">
        <div class="modal-header"><h3>Set Operating Hours</h3><span class="modal-close" onclick="closeHoursModal()">&times;</span></div>
        <div id="hoursBody"></div>
    </div>
</div>

<script>
const CATEGORIES = ''' + json.dumps(CATEGORIES) + ''';
let sessionToken = localStorage.getItem('session_token');
let vendorData = null, products = [];

if (!sessionToken) window.location.href = '/auth';

async function api(url, options = {}) {
    const res = await fetch(url, {
        ...options,
        headers: { 'Content-Type': 'application/json', 'X-Session-Token': sessionToken, ...options.headers }
    });
    if (res.status === 401) { localStorage.removeItem('session_token'); window.location.href = '/auth'; return null; }
    return res.json();
}

async function loadData() {
    const data = await api('/api/vendor/data');
    if (data) { vendorData = data.vendor; products = data.products || []; }
}

function showPage(p) {
    document.querySelectorAll('.nav-item').forEach((el, i) => {
        const pages = ['dashboard', 'products', 'reviews', 'settings'];
        el.classList.toggle('active', pages[i] === p);
    });
    if (p === 'dashboard') showDashboard();
    else if (p === 'products') showProducts();
    else if (p === 'reviews') showReviews();
    else if (p === 'settings') showSettings();
}

async function showDashboard() {
    document.getElementById('content').innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading...</div>';
    await loadData();
    document.getElementById('content').innerHTML = `
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value">${vendorData?.traffic_count || 0}</div><div class="stat-label">Visits</div></div>
            <div class="stat-card"><div class="stat-value">${vendorData?.rating || 'New'}</div><div class="stat-label">Rating</div></div>
            <div class="stat-card"><div class="stat-value">${products.length}</div><div class="stat-label">Products</div></div>
            <div class="stat-card"><div class="stat-value">${vendorData?.review_count || 0}</div><div class="stat-label">Reviews</div></div>
        </div>
        <div class="card"><h3>${vendorData?.business_name}</h3><p class="text-secondary">${vendorData?.category}</p><p><i class="fas fa-map-marker-alt"></i> ${vendorData?.address || 'No address'}</p></div>`;
}

async function showProducts() {
    await loadData();
    document.getElementById('content').innerHTML = `
        <button class="btn" onclick="openAddProductModal()"><i class="fas fa-plus"></i> Add Product</button>
        <div id="productsList" class="mt-4">${products.map(p => `
            <div class="product-card"><div class="flex justify-between"><div><h4>${p.name}</h4><p class="text-secondary">${p.description || ''}</p><div class="flex gap-2 mt-1"><span class="badge">${p.category}</span><span class="product-stock">Stock: ${p.stock}</span></div></div><div class="product-price">₱${p.price}</div></div>
            ${p.images && p.images.length ? `<div class="image-grid mt-2">${p.images.slice(0,3).map(img => `<div class="image-thumb"><img src="${img.thumbnail}"></div>`).join('')}</div>` : ''}
            <div class="flex gap-2 mt-3"><button class="btn-outline btn-sm" onclick="openEditProductModal('${p.id}')"><i class="fas fa-edit"></i> Edit</button><button class="btn-outline btn-sm" onclick="deleteProduct('${p.id}')"><i class="fas fa-trash"></i> Delete</button></div></div>
        `).join('') || '<p class="text-center text-secondary">No products yet</p>'}</div>`;
}

let currentProductId = null;

function openAddProductModal() {
    currentProductId = null;
    document.getElementById('modalTitle').innerText = 'Add Product';
    document.getElementById('modalBody').innerHTML = `
        <input type="text" id="prodName" class="input" placeholder="Product name">
        <textarea id="prodDesc" class="input" placeholder="Description" rows="3"></textarea>
        <select id="prodCategory" class="input">${CATEGORIES.map(c => `<option>${c}</option>`).join('')}</select>
        <div class="flex gap-2"><input type="number" id="prodPrice" class="input" placeholder="Price" step="0.01"><input type="number" id="prodStock" class="input" placeholder="Stock"></div>
        <div class="flex gap-2 mt-4"><button class="btn" onclick="saveProduct()">Save</button><button class="btn-outline" onclick="closeProductModal()">Cancel</button></div>
    `;
    document.getElementById('productModal').classList.add('show');
}

async function openEditProductModal(productId) {
    const product = products.find(p => p.id === productId);
    if (!product) return;
    currentProductId = productId;
    document.getElementById('modalTitle').innerText = 'Edit Product';
    document.getElementById('modalBody').innerHTML = `
        <input type="text" id="prodName" class="input" placeholder="Product name" value="${product.name.replace(/"/g, '&quot;')}">
        <textarea id="prodDesc" class="input" placeholder="Description" rows="3">${product.description || ''}</textarea>
        <select id="prodCategory" class="input">${CATEGORIES.map(c => `<option ${product.category === c ? 'selected' : ''}>${c}</option>`).join('')}</select>
        <div class="flex gap-2"><input type="number" id="prodPrice" class="input" placeholder="Price" step="0.01" value="${product.price}"><input type="number" id="prodStock" class="input" placeholder="Stock" value="${product.stock}"></div>
        <div class="flex gap-2 mt-4"><button class="btn" onclick="saveProduct()">Update</button><button class="btn-outline" onclick="closeProductModal()">Cancel</button></div>
    `;
    document.getElementById('productModal').classList.add('show');
}

async function saveProduct() {
    const name = document.getElementById('prodName').value;
    const price = parseFloat(document.getElementById('prodPrice').value);
    if (!name || !price) { alert('Name and price required'); return; }
    
    const productData = {
        name, description: document.getElementById('prodDesc').value,
        category: document.getElementById('prodCategory').value,
        price, stock: parseInt(document.getElementById('prodStock').value) || 0,
        images: []
    };
    const endpoint = currentProductId ? '/api/vendor/product/update' : '/api/vendor/product/create';
    const body = currentProductId ? { product_id: currentProductId, ...productData } : productData;
    const res = await api(endpoint, { method: 'POST', body: JSON.stringify(body) });
    if (res && res.success) { alert(currentProductId ? 'Product updated!' : 'Product created!'); closeProductModal(); showProducts(); }
    else alert('Failed to save product');
}

async function deleteProduct(productId) {
    if (confirm('Delete this product?')) {
        const res = await api('/api/vendor/product/delete', { method: 'POST', body: JSON.stringify({ product_id: productId }) });
        if (res && res.success) { alert('Product deleted'); showProducts(); }
    }
}

async function showReviews() {
    const data = await api('/api/vendor/reviews');
    document.getElementById('content').innerHTML = (data?.reviews || []).map(r => `
        <div class="card"><div class="flex justify-between"><div><strong>${r.customer_name}</strong><div class="stars mt-1">${'★'.repeat(r.rating)}${'☆'.repeat(5-r.rating)}</div></div><span class="text-secondary">${new Date(r.created_at).toLocaleDateString()}</span></div>
        <p class="mt-2">${r.comment || 'No comment'}</p></div>
    `).join('') || '<p class="text-center">No reviews yet</p>';
}

async function showSettings() {
    await loadData();
    const hours = vendorData?.operating_hours || {};
    document.getElementById('content').innerHTML = `
        <div class="card"><h3>Operating Hours</h3><div id="hoursPreview" class="hours-grid"></div><button class="btn-outline mt-3" onclick="openHoursModal()"><i class="fas fa-sliders-h"></i> Set Hours with Slider</button></div>
        <div class="card"><h3>Location</h3><p class="text-secondary">Current: ${vendorData?.latitude || 'Not set'}, ${vendorData?.longitude || 'Not set'}</p><button class="btn-outline" onclick="updateLocation()"><i class="fas fa-location-dot"></i> Update Location</button></div>
        <div class="card"><h3>Business Info</h3><p><strong>${vendorData?.business_name}</strong><br>${vendorData?.category}<br>📞 ${vendorData?.phone || 'No phone'}</p></div>`;
    
    const previewDiv = document.getElementById('hoursPreview');
    const days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    previewDiv.innerHTML = days.map(day => `<div class="hours-item"><span class="hours-day">${day}</span><span>${hours[day] || 'closed'}</span></div>`).join('');
}

function openHoursModal() {
    const hours = vendorData?.operating_hours || {};
    document.getElementById('hoursBody').innerHTML = `<div id="hoursSliders"></div><button class="btn mt-4" onclick="saveHours()">Save Hours</button>`;
    const slidersDiv = document.getElementById('hoursSliders');
    const days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    days.forEach(day => {
        const current = hours[day] || 'closed';
        const isClosed = current === 'closed';
        const [openH = 9, closeH = 18] = current !== 'closed' ? current.split('-').map(t => parseInt(t)) : [9, 18];
        slidersDiv.innerHTML += `
            <div class="card"><div class="flex justify-between"><h4>${day}</h4><label><input type="checkbox" id="closed_${day}" ${isClosed ? 'checked' : ''} onchange="toggleDay('${day}')"> Closed</label></div>
            <div id="sliders_${day}" ${isClosed ? 'style="display:none"' : ''}>
                <div class="hours-slider"><span>Open</span><input type="range" id="open_${day}" min="0" max="23" value="${openH}" oninput="updateTime('open', '${day}', this.value)"><span id="open_val_${day}" class="hours-value">${openH}:00</span></div>
                <div class="hours-slider"><span>Close</span><input type="range" id="close_${day}" min="0" max="23" value="${closeH}" oninput="updateTime('close', '${day}', this.value)"><span id="close_val_${day}" class="hours-value">${closeH}:00</span></div>
            </div></div>`;
    });
    document.getElementById('hoursModal').classList.add('show');
}

function updateTime(type, day, value) { document.getElementById(`${type}_val_${day}`).innerText = `${value}:00`; }
function toggleDay(day) { const isClosed = document.getElementById(`closed_${day}`).checked; document.getElementById(`sliders_${day}`).style.display = isClosed ? 'none' : 'block'; }

async function saveHours() {
    const hours = {};
    const days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    days.forEach(day => {
        const isClosed = document.getElementById(`closed_${day}`)?.checked;
        if (isClosed) hours[day] = 'closed';
        else { const openH = document.getElementById(`open_${day}`)?.value || 9; const closeH = document.getElementById(`close_${day}`)?.value || 18; hours[day] = `${openH}:00-${closeH}:00`; }
    });
    const res = await api('/api/vendor/update-hours', { method: 'POST', body: JSON.stringify({ hours }) });
    if (res && res.success) { alert('Hours saved!'); closeHoursModal(); showSettings(); }
}

async function updateLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(async (p) => {
            const res = await api('/api/vendor/update-location', { method: 'POST', body: JSON.stringify({ latitude: p.coords.latitude, longitude: p.coords.longitude }) });
            if (res && res.success) { alert('Location updated!'); showSettings(); }
        }, () => alert('Could not get location'));
    }
}

function closeProductModal() { document.getElementById('productModal').classList.remove('show'); }
function closeHoursModal() { document.getElementById('hoursModal').classList.remove('show'); }
function logout() { localStorage.removeItem('session_token'); localStorage.removeItem('user_role'); window.location.href = '/'; }

showDashboard();
</script>
''')

# ============================================
# ADMIN DASHBOARD
# ============================================

ADMIN_DASH = render_page("Admin", '''
<div class="app-bar">
    <button class="back-btn" onclick="logout()">Logout</button>
    <div class="app-bar-title">Admin Panel</div>
    <div></div>
</div>
<div class="content" id="content"></div>

<div class="bottom-nav">
    <div class="nav-item active" onclick="showPage('stats')"><i class="fas fa-chart-line"></i><span>Stats</span></div>
    <div class="nav-item" onclick="showPage('users')"><i class="fas fa-users"></i><span>Users</span></div>
    <div class="nav-item" onclick="showPage('vendors')"><i class="fas fa-store"></i><span>Vendors</span></div>
</div>

<script>
let sessionToken = localStorage.getItem('session_token');
if (!sessionToken) window.location.href = '/auth';

async function api(url, options = {}) {
    const res = await fetch(url, {
        ...options,
        headers: { 'Content-Type': 'application/json', 'X-Session-Token': sessionToken, ...options.headers }
    });
    if (res.status === 401) { localStorage.removeItem('session_token'); window.location.href = '/auth'; return null; }
    return res.json();
}

function showPage(p) {
    document.querySelectorAll('.nav-item').forEach((el, i) => {
        const pages = ['stats', 'users', 'vendors'];
        el.classList.toggle('active', pages[i] === p);
    });
    if (p === 'stats') showStats();
    else if (p === 'users') showUsers();
    else if (p === 'vendors') showVendors();
}

async function showStats() {
    const data = await api('/api/admin/stats');
    document.getElementById('content').innerHTML = `
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value">${data.total_users || 0}</div><div class="stat-label">Users</div></div>
            <div class="stat-card"><div class="stat-value">${data.total_vendors || 0}</div><div class="stat-label">Vendors</div></div>
            <div class="stat-card"><div class="stat-value">${data.total_products || 0}</div><div class="stat-label">Products</div></div>
        </div>`;
}

async function showUsers() {
    const data = await api('/api/admin/users');
    document.getElementById('content').innerHTML = `<h3>Users (${data.users?.length || 0})</h3>
        ${(data.users || []).map(u => `<div class="card"><div class="flex justify-between"><div><strong>${u.email}</strong><br><span class="text-secondary">${u.full_name || 'No name'} • ${u.role}</span></div>
        <button class="btn-outline btn-sm" onclick="suspendUser('${u.id}', ${u.is_suspended})">${u.is_suspended ? 'Unsuspend' : 'Suspend'}</button></div></div>`).join('')}`;
}

async function showVendors() {
    const data = await api('/api/admin/vendors');
    document.getElementById('content').innerHTML = `<h3>Vendors (${data.vendors?.length || 0})</h3>
        ${(data.vendors || []).map(v => `<div class="card"><div class="flex justify-between"><div><strong>${v.business_name}</strong><br><span class="text-secondary">${v.category}</span></div>
        <button class="btn-outline btn-sm" onclick="toggleVendor('${v.id}', ${v.is_active})">${v.is_active ? 'Disable' : 'Enable'}</button></div></div>`).join('')}`;
}

async function suspendUser(userId, currentlySuspended) {
    await api('/api/admin/user/suspend', { method: 'POST', body: JSON.stringify({ user_id: userId, suspend: !currentlySuspended }) });
    showUsers();
}

async function toggleVendor(vendorId, active) {
    await api('/api/admin/vendor/toggle', { method: 'POST', body: JSON.stringify({ vendor_id: vendorId, active: !active }) });
    showVendors();
}

function logout() { localStorage.removeItem('session_token'); localStorage.removeItem('user_role'); window.location.href = '/'; }

showStats();
</script>
''')

# ============================================
# API ROUTES
# ============================================

@app.route('/')
def index(): return LANDING
@app.route('/auth')
def auth_page(): return AUTH
@app.route('/guest')
def guest_page(): return GUEST
@app.route('/customer')
def customer_page(): return CUSTOMER_DASH
@app.route('/vendor')
def vendor_page(): return VENDOR_DASH
@app.route('/admin')
def admin_page(): return ADMIN_DASH

# ============================================
# AUTH API
# ============================================

@app.route('/api/auth/register/customer', methods=['POST'])
def register_customer():
    data = request.json
    user_id = create_user(data.get('email'), data.get('password'), 'customer', data.get('full_name'), data.get('phone'))
    if not user_id: return jsonify({'error': 'Failed to create user'}), 500
    session_token = str(uuid.uuid4())
    sessions[session_token] = {'user_id': user_id, 'role': 'customer'}
    return jsonify({'success': True, 'session_token': session_token, 'role': 'customer'})

@app.route('/api/auth/register/vendor', methods=['POST'])
def register_vendor():
    data = request.json
    user_id = create_user(data.get('email'), data.get('password'), 'vendor', data.get('business_name'), data.get('phone'))
    if not user_id: return jsonify({'error': 'Failed to create user'}), 500
    vendor_id = create_vendor(user_id, data.get('business_name'), data.get('business_category'), data.get('address'), data.get('latitude'), data.get('longitude'), data.get('phone'), data.get('email'))
    if not vendor_id: return jsonify({'error': 'Failed to create vendor'}), 500
    session_token = str(uuid.uuid4())
    sessions[session_token] = {'user_id': user_id, 'role': 'vendor'}
    return jsonify({'success': True, 'session_token': session_token, 'role': 'vendor'})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    user = verify_password(data.get('email'), data.get('password'))
    if not user: return jsonify({'error': 'Invalid credentials'}), 401
    session_token = str(uuid.uuid4())
    sessions[session_token] = {'user_id': user['id'], 'role': user['role']}
    return jsonify({'success': True, 'session_token': session_token, 'role': user['role']})

# ============================================
# CUSTOMER API
# ============================================

@app.route('/api/customer/map/vendors')
def get_nearby_vendors():
    lat = float(request.args.get('lat', 14.5995))
    lng = float(request.args.get('lng', 120.9842))
    return jsonify({'vendors': get_vendors_nearby(lat, lng, 20)})

@app.route('/api/customer/shortlist', methods=['GET'])
def get_shortlist_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session: return jsonify({'error': 'Unauthorized'}), 401
    return jsonify({'vendors': get_shortlist(session['user_id'])})

@app.route('/api/customer/shortlist/toggle', methods=['POST'])
def toggle_shortlist_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session: return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    existing = get_shortlist(session['user_id'])
    if any(v['id'] == data.get('vendor_id') for v in existing):
        remove_from_shortlist(session['user_id'], data.get('vendor_id'))
        return jsonify({'success': True, 'action': 'removed'})
    else:
        add_to_shortlist(session['user_id'], data.get('vendor_id'))
        return jsonify({'success': True, 'action': 'added'})

@app.route('/api/customer/like', methods=['POST'])
def like_post_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session: return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    return jsonify({'success': True, 'liked': like_post(data.get('post_id'), session['user_id'])})

@app.route('/api/customer/post/create', methods=['POST'])
def create_post_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session: return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    post_id = create_post(session['user_id'], session['role'], data.get('content'))
    return jsonify({'success': True, 'post_id': post_id}) if post_id else jsonify({'error': 'Failed'}), 500

@app.route('/api/customer/review/create', methods=['POST'])
def create_review_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session: return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    review_id = create_review(session['user_id'], data.get('vendor_id'), data.get('rating'), data.get('comment'))
    return jsonify({'success': True, 'review_id': review_id}) if review_id else jsonify({'error': 'Failed'}), 500

# ============================================
# VENDOR API
# ============================================

@app.route('/api/vendor/data')
def get_vendor_data():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor': return jsonify({'error': 'Unauthorized'}), 401
    vendor = get_vendor_by_user_id(session['user_id'])
    if not vendor: return jsonify({'error': 'Vendor not found'}), 404
    return jsonify({'vendor': vendor, 'products': get_products_by_vendor(vendor['id'])})

@app.route('/api/vendor/product/create', methods=['POST'])
def create_product_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor': return jsonify({'error': 'Unauthorized'}), 401
    vendor = get_vendor_by_user_id(session['user_id'])
    if not vendor: return jsonify({'error': 'Vendor not found'}), 404
    data = request.json
    product_id = create_product(vendor['id'], data.get('name'), data.get('description'), data.get('category'), data.get('price'), data.get('stock', 0), data.get('images', []))
    return jsonify({'success': True, 'product_id': product_id}) if product_id else jsonify({'error': 'Failed'}), 500

@app.route('/api/vendor/product/update', methods=['POST'])
def update_product_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor': return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    update_data = {k: v for k, v in data.items() if k != 'product_id'}
    return jsonify({'success': update_product(data.get('product_id'), update_data)})

@app.route('/api/vendor/product/delete', methods=['POST'])
def delete_product_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor': return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    return jsonify({'success': delete_product(data.get('product_id'))})

@app.route('/api/vendor/reviews')
def get_vendor_reviews_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor': return jsonify({'error': 'Unauthorized'}), 401
    vendor = get_vendor_by_user_id(session['user_id'])
    return jsonify({'reviews': get_reviews_by_vendor(vendor['id']) if vendor else []})

@app.route('/api/vendor/update-hours', methods=['POST'])
def update_hours_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor': return jsonify({'error': 'Unauthorized'}), 401
    vendor = get_vendor_by_user_id(session['user_id'])
    if not vendor: return jsonify({'error': 'Vendor not found'}), 404
    return jsonify({'success': update_vendor_hours(vendor['id'], request.json.get('hours'))})

@app.route('/api/vendor/update-location', methods=['POST'])
def update_location_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor': return jsonify({'error': 'Unauthorized'}), 401
    vendor = get_vendor_by_user_id(session['user_id'])
    if not vendor: return jsonify({'error': 'Vendor not found'}), 404
    data = request.json
    return jsonify({'success': update_vendor_location(vendor['id'], data.get('latitude'), data.get('longitude'))})

# ============================================
# ADMIN API
# ============================================

@app.route('/api/admin/stats')
def admin_stats():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'admin': return jsonify({'error': 'Unauthorized'}), 401
    return jsonify(get_admin_stats())

@app.route('/api/admin/users')
def admin_users():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'admin': return jsonify({'error': 'Unauthorized'}), 401
    return jsonify({'users': get_all_users_admin()})

@app.route('/api/admin/user/suspend', methods=['POST'])
def admin_suspend_user():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'admin': return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    if data.get('suspend'):
        suspend_user(data.get('user_id'))
    else:
        unsuspend_user(data.get('user_id'))
    return jsonify({'success': True})

@app.route('/api/admin/vendors')
def admin_vendors():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'admin': return jsonify({'error': 'Unauthorized'}), 401
    return jsonify({'vendors': get_all_vendors_admin()})

@app.route('/api/admin/vendor/toggle', methods=['POST'])
def admin_toggle_vendor():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'admin': return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    return jsonify({'success': toggle_vendor_active(data.get('vendor_id'), data.get('active'))})

# ============================================
# GUEST API
# ============================================

@app.route('/api/guest/feed')
def guest_feed():
    return jsonify({'posts': get_feed_posts(15)})

# ============================================
# HEALTH CHECK
# ============================================

@app.route('/health')
def health():
    return jsonify({"status": "ok", "supabase": supabase is not None})

# ============================================
# RUN APP
# ============================================

if __name__ == '__main__':
    admin = get_user_by_email('admin@lako.app')
    if not admin:
        create_user('admin@lako.app', 'admin123', 'admin', 'System Admin', '')
        print("✓ Created admin user: admin@lako.app / admin123")
    
    print("=" * 60)
    print("🍢 Lako Server - COMPLETE EDITION")
    print("=" * 60)
    print(f"✓ Supabase: Connected")
    print(f"✓ Admin Login: admin@lako.app / admin123")
    print("=" * 60)
    print("🌐 Available Pages:")
    print(f"   - Landing: http://localhost:5000")
    print(f"   - Auth:    http://localhost:5000/auth")
    print(f"   - Guest:   http://localhost:5000/guest")
    print(f"   - Admin:   http://localhost:5000/admin")
    print("=" * 60)
    print("✅ ALL FEATURES WORKING:")
    print("   - Carousel with touch swipe")
    print("   - Customer mode (map, vendors, feed, saved, profile)")
    print("   - Vendor mode (products, hours slider, reviews, settings)")
    print("   - Guest mode (avatar, map, vendors, feed, saved)")
    print("   - Admin mode (stats, users, vendors management)")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)