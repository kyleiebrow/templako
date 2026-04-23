from flask import Blueprint, request, jsonify
import bcrypt
import uuid
from datetime import datetime, timedelta
from models import supabase
from utils import generate_magic_token, send_magic_link_email

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/auth/register/customer', methods=['POST'])
def api_register_customer():
    data = request.get_json()
    response = supabase.table('users').select('id').eq('email', data['email']).execute()
    if response.data:
        return jsonify({"error": "Email exists"}), 400
    magic_token = generate_magic_token()
    user_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt()).decode()
    user_data = {
        'id': user_id,
        'email': data['email'],
        'password': hashed,
        'role': 'customer',
        'full_name': data.get('full_name'),
        'phone': data.get('phone', ''),
        'eula_accepted': 1,
        'created_at': datetime.now().isoformat(),
        'magic_token': magic_token,
        'token_expires': (datetime.now()+timedelta(minutes=10)).isoformat(),
        'email_verified': 0
    }
    supabase.table('users').insert(user_data).execute()
    send_magic_link_email(data['email'], magic_token)
    return jsonify({"requires_verification": True, "user_id": user_id})

@auth_bp.route('/api/auth/register/vendor', methods=['POST'])
def api_register_vendor():
    data = request.get_json()
    response = supabase.table('users').select('id').eq('email', data['email']).execute()
    if response.data:
        return jsonify({"error": "Email exists"}), 400
    magic_token = generate_magic_token()
    user_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt()).decode()
    user_data = {
        'id': user_id,
        'email': data['email'],
        'password': hashed,
        'role': 'vendor',
        'full_name': data['business_name'],
        'phone': data.get('phone', ''),
        'eula_accepted': 1,
        'created_at': datetime.now().isoformat(),
        'magic_token': magic_token,
        'token_expires': (datetime.now()+timedelta(minutes=10)).isoformat(),
        'email_verified': 0
    }
    supabase.table('users').insert(user_data).execute()
    vendor_id = str(uuid.uuid4())
    vendor_data = {
        'id': vendor_id,
        'user_id': user_id,
        'business_name': data['business_name'],
        'category': data.get('business_category', 'General'),
        'address': data['address'],
        'latitude': data.get('latitude', 13.9443),
        'longitude': data.get('longitude', 121.3798),
        'created_at': datetime.now().isoformat()
    }
    supabase.table('vendors').insert(vendor_data).execute()
    send_magic_link_email(data['email'], magic_token)
    return jsonify({"requires_verification": True, "user_id": user_id})

@auth_bp.route('/api/auth/verify-magic-link/<token>', methods=['GET'])
def api_verify_magic_link(token):
    response = supabase.table('users').select('id, magic_token, token_expires, role, full_name, email').eq('magic_token', token).eq('email_verified', 0).execute()
    if not response.data:
        return jsonify({"error": "Invalid or expired token"}), 400
    u = response.data[0]
    if datetime.fromisoformat(u['token_expires']) < datetime.now():
        return jsonify({"error": "Token expired"}), 400
    supabase.table('users').update({'email_verified': 1, 'magic_token': None, 'token_expires': None}).eq('id', u['id']).execute()
    return jsonify({"session_token": u['id'], "role": u['role'], "email": u['email'], "name": u['full_name']})

@auth_bp.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json()
    response = supabase.table('users').select('id, password, role, full_name, email_verified').eq('email', data['email']).execute()
    if not response.data:
        return jsonify({"error": "Invalid credentials"}), 401
    u = response.data[0]
    if not bcrypt.checkpw(data['password'].encode(), u['password'].encode()):
        return jsonify({"error": "Invalid credentials"}), 401
    if u['email_verified'] == 0:
        # Send magic link for unverified users
        magic_token = generate_magic_token()
        supabase.table('users').update({
            'magic_token': magic_token,
            'token_expires': (datetime.now()+timedelta(minutes=10)).isoformat()
        }).eq('id', u['id']).execute()
        send_magic_link_email(data['email'], magic_token)
        return jsonify({"requires_verification": True, "email": data['email'], "role": u['role']}), 401
    return jsonify({"session_token": u['id'], "role": u['role'], "email": data['email'], "name": u['full_name']})

@auth_bp.route('/api/auth/guest', methods=['POST'])
def api_guest_login():
    """Create a guest session - can view vendors and posts but limited features"""
    guest_id = str(uuid.uuid4())
    guest_name = f"Guest_{str(uuid.uuid4())[:8]}"
    guest_data = {
        'id': guest_id,
        'email': f"guest_{guest_id}@lako.guest",
        'password': "",
        'role': 'guest',
        'full_name': guest_name,
        'eula_accepted': 1,
        'created_at': datetime.now().isoformat(),
        'email_verified': 1,
        'is_guest': 1
    }
    supabase.table('users').insert(guest_data).execute()
    return jsonify({
        "session_token": guest_id,
        "role": "guest",
        "name": guest_name,
        "message": "Guest session created. Limited features available."
    })