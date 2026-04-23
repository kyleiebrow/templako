# ============================================
# models.py - COMPLETE SUPABASE INTEGRATION
# ============================================

import uuid
from datetime import datetime
from supabase import create_client
import os
import bcrypt
from config import SUPABASE_URL, SUPABASE_KEY

# Initialize Supabase
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✓ Supabase connected")
    except Exception as e:
        print(f"⚠️ Warning: Supabase initialization failed: {e}")
        supabase = None
else:
    print("⚠️ Warning: Supabase credentials not configured.")

# ============================================
# DATABASE OPERATIONS
# ============================================

def get_user_by_email(email):
    """Get user by email"""
    if supabase:
        try:
            result = supabase.table('users').select('*').eq('email', email).execute()
            return result.data[0] if result.data else None
        except:
            return None
    return None

def get_user_by_id(user_id):
    """Get user by ID"""
    if supabase:
        try:
            result = supabase.table('users').select('*').eq('id', user_id).execute()
            return result.data[0] if result.data else None
        except:
            return None
    return None

def create_user(email, password, role, full_name=None, phone=None):
    """Create a new user"""
    user_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    user_data = {
        'id': user_id,
        'email': email,
        'password': hashed,
        'role': role,
        'full_name': full_name,
        'phone': phone,
        'email_verified': False,
        'is_suspended': False,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat()
    }
    
    if supabase:
        try:
            supabase.table('users').insert(user_data).execute()
        except:
            pass
    
    return user_id

def verify_password(email, password):
    """Verify user password"""
    user = get_user_by_email(email)
    if user and bcrypt.checkpw(password.encode(), user['password'].encode()):
        return user
    return None

def update_user(user_id, data):
    """Update user data"""
    data['updated_at'] = datetime.utcnow().isoformat()
    if supabase:
        try:
            supabase.table('users').update(data).eq('id', user_id).execute()
        except:
            pass

def set_otp(email, otp, expires):
    """Set OTP for user"""
    if supabase:
        try:
            supabase.table('users').update({
                'otp_code': otp,
                'otp_expires': expires.isoformat()
            }).eq('email', email).execute()
        except:
            pass

def verify_otp(email, otp):
    """Verify OTP and mark email as verified"""
    user = get_user_by_email(email)
    if not user or user.get('email_verified'):
        return False, "Invalid request"
    
    if datetime.fromisoformat(user['otp_expires']) < datetime.utcnow():
        return False, "OTP expired"
    
    if user['otp_code'] != otp:
        return False, "Invalid OTP"
    
    if supabase:
        try:
            supabase.table('users').update({
                'email_verified': True,
                'otp_code': None,
                'otp_expires': None
            }).eq('email', email).execute()
        except:
            pass
    
    return True, "Verified"

# ============================================
# VENDOR OPERATIONS
# ============================================

def create_vendor(user_id, business_name, category, address, lat=None, lng=None, phone=None, email=None, description=None):
    """Create a new vendor"""
    vendor_id = str(uuid.uuid4())
    
    vendor_data = {
        'id': vendor_id,
        'user_id': user_id,
        'business_name': business_name,
        'category': category,
        'description': description,
        'address': address,
        'latitude': lat or 13.9443,
        'longitude': lng or 121.3798,
        'phone': phone,
        'email': email,
        'rating': 0,
        'review_count': 0,
        'traffic_count': 0,
        'is_active': True,
        'is_verified': False,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat()
    }
    
    if supabase:
        try:
            supabase.table('vendors').insert(vendor_data).execute()
        except:
            pass
    
    return vendor_id

def get_vendor_by_user_id(user_id):
    """Get vendor by user ID"""
    if supabase:
        try:
            result = supabase.table('vendors').select('*').eq('user_id', user_id).execute()
            return result.data[0] if result.data else None
        except:
            return None
    return None

def get_vendor_by_id(vendor_id):
    """Get vendor by ID"""
    if supabase:
        try:
            result = supabase.table('vendors').select('*').eq('id', vendor_id).execute()
            return result.data[0] if result.data else None
        except:
            return None
    return None

def get_vendors_nearby(lat, lng, radius_km=20, category=None):
    """Get vendors within radius"""
    if supabase:
        try:
            query = supabase.table('vendors').select('*').eq('is_active', True)
            if category:
                query = query.eq('category', category)
            result = query.execute()
            return result.data or []
        except:
            return []
    return []

def update_vendor(vendor_id, data):
    """Update vendor data"""
    data['updated_at'] = datetime.utcnow().isoformat()
    if supabase:
        try:
            supabase.table('vendors').update(data).eq('id', vendor_id).execute()
        except:
            pass

def increment_traffic(vendor_id):
    """Increment vendor traffic count"""
    vendor = get_vendor_by_id(vendor_id)
    if vendor:
        update_vendor(vendor_id, {'traffic_count': (vendor.get('traffic_count', 0) + 1)})

# ============================================
# PRODUCT OPERATIONS
# ============================================

def create_product(vendor_id, name, description=None, category=None, price=None, stock=0, moq=1):
    """Create a new product"""
    product_id = str(uuid.uuid4())
    
    product_data = {
        'id': product_id,
        'vendor_id': vendor_id,
        'name': name,
        'description': description,
        'category': category,
        'price': price,
        'stock': stock,
        'moq': moq,
        'rating': 0,
        'review_count': 0,
        'is_active': True,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat()
    }
    
    if supabase:
        try:
            supabase.table('products').insert(product_data).execute()
        except:
            pass
    
    return product_id

def get_products_by_vendor(vendor_id):
    """Get all products for a vendor"""
    if supabase:
        try:
            result = supabase.table('products').select('*').eq('vendor_id', vendor_id).eq('is_active', True).execute()
            return result.data or []
        except:
            return []
    return []

def get_product_by_id(product_id):
    """Get product by ID"""
    if supabase:
        try:
            result = supabase.table('products').select('*, vendors(business_name)').eq('id', product_id).execute()
            return result.data[0] if result.data else None
        except:
            return None
    return None

def update_product(product_id, data):
    """Update product data"""
    data['updated_at'] = datetime.utcnow().isoformat()
    if supabase:
        try:
            supabase.table('products').update(data).eq('id', product_id).execute()
        except:
            pass

def delete_product(product_id):
    """Soft delete a product"""
    update_product(product_id, {'is_active': False})

# ============================================
# POST OPERATIONS
# ============================================

def create_post(user_id, user_role, content, images=None):
    """Create a new post"""
    post_id = str(uuid.uuid4())
    
    post_data = {
        'id': post_id,
        'user_id': user_id,
        'user_role': user_role,
        'content': content,
        'images': images,
        'likes': 0,
        'comment_count': 0,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat()
    }
    
    if supabase:
        try:
            supabase.table('posts').insert(post_data).execute()
        except:
            pass
    
    return post_id

def get_feed_posts(limit=20, offset=0):
    """Get feed posts"""
    if supabase:
        try:
            result = supabase.table('posts').select('*, users(full_name, avatar)').is_('parent_id', 'null').order('created_at', desc=True).range(offset, offset + limit - 1).execute()
            return result.data or []
        except:
            return []
    return []

def get_post_by_id(post_id):
    """Get post by ID"""
    if supabase:
        try:
            result = supabase.table('posts').select('*, users(full_name, avatar)').eq('id', post_id).execute()
            return result.data[0] if result.data else None
        except:
            return None
    return None

def like_post(post_id, user_id):
    """Toggle like on a post"""
    if supabase:
        try:
            # Check if already liked
            existing = supabase.table('post_likes').select('*').eq('post_id', post_id).eq('user_id', user_id).execute()
            
            if existing.data:
                # Unlike
                supabase.table('post_likes').delete().eq('post_id', post_id).eq('user_id', user_id).execute()
                post = get_post_by_id(post_id)
                if post:
                    update_post(post_id, {'likes': max(0, post.get('likes', 1) - 1)})
                return False
            else:
                # Like
                supabase.table('post_likes').insert({
                    'id': str(uuid.uuid4()),
                    'post_id': post_id,
                    'user_id': user_id,
                    'created_at': datetime.utcnow().isoformat()
                }).execute()
                post = get_post_by_id(post_id)
                if post:
                    update_post(post_id, {'likes': post.get('likes', 0) + 1})
                return True
        except:
            pass
    return False

def update_post(post_id, data):
    """Update post data"""
    data['updated_at'] = datetime.utcnow().isoformat()
    if supabase:
        try:
            supabase.table('posts').update(data).eq('id', post_id).execute()
        except:
            pass

def delete_post(post_id):
    """Delete a post"""
    if supabase:
        try:
            supabase.table('post_likes').delete().eq('post_id', post_id).execute()
            supabase.table('comments').delete().eq('post_id', post_id).execute()
            supabase.table('posts').delete().eq('id', post_id).execute()
        except:
            pass

# ============================================
# COMMENT OPERATIONS
# ============================================

def create_comment(post_id, user_id, comment):
    """Create a comment on a post"""
    comment_id = str(uuid.uuid4())
    
    if supabase:
        try:
            supabase.table('comments').insert({
                'id': comment_id,
                'post_id': post_id,
                'user_id': user_id,
                'comment': comment,
                'created_at': datetime.utcnow().isoformat()
            }).execute()
            
            # Update comment count
            post = get_post_by_id(post_id)
            if post:
                update_post(post_id, {'comment_count': post.get('comment_count', 0) + 1})
        except:
            pass
    
    return comment_id

def get_comments_by_post(post_id):
    """Get comments for a post"""
    if supabase:
        try:
            result = supabase.table('comments').select('*, users(full_name)').eq('post_id', post_id).order('created_at', asc=True).execute()
            return result.data or []
        except:
            return []
    return []

# ============================================
# REVIEW OPERATIONS
# ============================================

def create_review(customer_id, vendor_id, rating, comment=None):
    """Create a new review"""
    review_id = str(uuid.uuid4())
    
    review_data = {
        'id': review_id,
        'customer_id': customer_id,
        'vendor_id': vendor_id,
        'rating': rating,
        'comment': comment,
        'is_hidden': False,
        'created_at': datetime.utcnow().isoformat()
    }
    
    if supabase:
        try:
            supabase.table('reviews').insert(review_data).execute()
            update_vendor_rating(vendor_id)
        except:
            pass
    
    return review_id

def get_reviews_by_vendor(vendor_id):
    """Get reviews for a vendor"""
    if supabase:
        try:
            result = supabase.table('reviews').select('*, users(full_name, avatar)').eq('vendor_id', vendor_id).eq('is_hidden', False).order('created_at', desc=True).execute()
            return result.data or []
        except:
            return []
    return []

def update_vendor_rating(vendor_id):
    """Update vendor average rating"""
    reviews = get_reviews_by_vendor(vendor_id)
    if reviews:
        avg = sum(r['rating'] for r in reviews) / len(reviews)
        update_vendor(vendor_id, {'rating': round(avg, 1), 'review_count': len(reviews)})

# ============================================
# SHORTLIST OPERATIONS
# ============================================

def add_to_shortlist(user_id, vendor_id):
    """Add vendor to user's shortlist"""
    if supabase:
        try:
            supabase.table('shortlists').insert({
                'id': str(uuid.uuid4()),
                'user_id': user_id,
                'vendor_id': vendor_id,
                'created_at': datetime.utcnow().isoformat()
            }).execute()
            return True
        except:
            return False
    return False

def remove_from_shortlist(user_id, vendor_id):
    """Remove vendor from user's shortlist"""
    if supabase:
        try:
            supabase.table('shortlists').delete().eq('user_id', user_id).eq('vendor_id', vendor_id).execute()
        except:
            pass

def get_shortlist(user_id):
    """Get user's shortlisted vendors"""
    if supabase:
        try:
            result = supabase.table('shortlists').select('vendors(*)').eq('user_id', user_id).execute()
            vendors = []
            for item in result.data or []:
                if item.get('vendors'):
                    vendors.append(item['vendors'])
            return vendors
        except:
            return []
    return []

# ============================================
# ADMIN OPERATIONS
# ============================================

def get_stats():
    """Get platform statistics"""
    stats = {'total_users': 0, 'total_vendors': 0, 'total_products': 0, 'total_reviews': 0}
    if supabase:
        try:
            stats['total_users'] = supabase.table('users').select('*', count='exact').execute().count or 0
            stats['total_vendors'] = supabase.table('vendors').select('*', count='exact').execute().count or 0
            stats['total_products'] = supabase.table('products').select('*', count='exact').eq('is_active', True).execute().count or 0
            stats['total_reviews'] = supabase.table('reviews').select('*', count='exact').execute().count or 0
        except:
            pass
    return stats

def get_all_users():
    """Get all users"""
    if supabase:
        try:
            result = supabase.table('users').select('*').order('created_at', desc=True).execute()
            return result.data or []
        except:
            return []
    return []

def get_all_vendors():
    """Get all vendors"""
    if supabase:
        try:
            result = supabase.table('vendors').select('*, users(full_name, email)').order('created_at', desc=True).execute()
            return result.data or []
        except:
            return []
    return []

def get_all_products():
    """Get all products"""
    if supabase:
        try:
            result = supabase.table('products').select('*, vendors(business_name)').order('created_at', desc=True).execute()
            return result.data or []
        except:
            return []
    return []

def get_all_reviews():
    """Get all reviews"""
    if supabase:
        try:
            result = supabase.table('reviews').select('*, users(full_name), vendors(business_name)').order('created_at', desc=True).execute()
            return result.data or []
        except:
            return []
    return []

def delete_user(user_id):
    """Delete a user"""
    if supabase:
        try:
            supabase.table('users').delete().eq('id', user_id).execute()
        except:
            pass

def suspend_user(user_id):
    """Suspend a user"""
    update_user(user_id, {'is_suspended': True})

def unsuspend_user(user_id):
    """Unsuspend a user"""
    update_user(user_id, {'is_suspended': False})

def toggle_vendor_active(vendor_id, is_active):
    """Toggle vendor active status"""
    update_vendor(vendor_id, {'is_active': is_active})

def delete_review(review_id):
    """Delete a review"""
    if supabase:
        try:
            supabase.table('reviews').delete().eq('id', review_id).execute()
        except:
            pass

def hide_review(review_id, hide=True):
    """Hide or unhide a review"""
    if supabase:
        try:
            supabase.table('reviews').update({'is_hidden': hide}).eq('id', review_id).execute()
        except:
            pass

# ============================================
# ACTIVITY LOGGING
# ============================================

def log_activity(user_id, role, action, target_type=None, target_id=None, details=None):
    """Log user activity"""
    if supabase:
        try:
            supabase.table('activities').insert({
                'id': str(uuid.uuid4()),
                'user_id': user_id,
                'user_role': role,
                'action_type': action,
                'target_type': target_type,
                'target_id': target_id,
                'details': details,
                'created_at': datetime.utcnow().isoformat()
            }).execute()
        except:
            pass

def get_recent_activities(limit=10):
    """Get recent activities"""
    if supabase:
        try:
            result = supabase.table('activities').select('*').order('created_at', desc=True).limit(limit).execute()
            return result.data or []
        except:
            return []
    return []

# ============================================
# MAGIC LINK OPERATIONS
# ============================================

def create_magic_link_token(email, role):
    """Create a magic link token for passwordless login"""
    token = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(hours=24)
    
    if supabase:
        try:
            supabase.table('magic_links').insert({
                'id': str(uuid.uuid4()),
                'email': email,
                'token': token,
                'role': role,
                'expires_at': expires.isoformat(),
                'used': False,
                'created_at': datetime.utcnow().isoformat()
            }).execute()
        except:
            pass
    
    return token

def verify_magic_link_token(token):
    """Verify magic link token"""
    if supabase:
        try:
            result = supabase.table('magic_links').select('*').eq('token', token).eq('used', False).execute()
            if result.data:
                link = result.data[0]
                if datetime.fromisoformat(link['expires_at']) > datetime.utcnow():
                    # Mark as used
                    supabase.table('magic_links').update({'used': True}).eq('token', token).execute()
                    
                    # Get or create user
                    user = get_user_by_email(link['email'])
                    if not user:
                        user_id = create_user(link['email'], str(uuid.uuid4())[:8], link['role'], link['email'].split('@')[0])
                        user = get_user_by_id(user_id)
                        update_user(user_id, {'email_verified': True})
                    
                    return user
        except:
            pass
    return None

print("✓ Models initialized with Supabase integration")