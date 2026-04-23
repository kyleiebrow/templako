from flask import Blueprint, request, jsonify
import uuid
from datetime import datetime, timedelta
from models import supabase
from utils import get_user_by_token, check_profanity
from upload import save_upload
from analytics import log_analytics, get_vendor_analytics, get_traffic_by_time

vendor_bp = Blueprint('vendor', __name__)

@vendor_bp.route('/api/vendor/dashboard')
def api_vendor_dashboard():
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    
    vendor_response = supabase.table('vendors').select('id').eq('user_id', user[0]).execute()
    if not vendor_response.data: return jsonify({"error": "Vendor not found"}), 404
    vendor_id = vendor_response.data[0]['id']
    
    products_count = supabase.table('products').select('id', count='exact').eq('vendor_id', vendor_id).execute().count
    posts_count = supabase.table('posts').select('id', count='exact').eq('user_id', user[0]).execute().count
    reviews_response = supabase.table('reviews').select('rating').eq('vendor_id', vendor_id).execute()
    total_reviews = len(reviews_response.data)
    avg_rating = sum(r['rating'] for r in reviews_response.data) / total_reviews if total_reviews > 0 else 0
    
    return jsonify({"total_products": products_count, "total_posts": posts_count, "total_reviews": total_reviews, "average_rating": round(avg_rating, 1)})

@vendor_bp.route('/api/vendor/catalog/products')
def api_vendor_products():
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    
    vendor_response = supabase.table('vendors').select('id').eq('user_id', user[0]).execute()
    if not vendor_response.data: return jsonify({"error": "Vendor not found"}), 404
    vendor_id = vendor_response.data[0]['id']
    
    response = supabase.table('products').select('id, name, description, category, price, stock, moq, image_url').eq('vendor_id', vendor_id).eq('is_active', True).execute()
    products = response.data
    return jsonify({"products": products})

@vendor_bp.route('/api/vendor/catalog/products', methods=['POST'])
def api_create_product():
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    
    vendor_response = supabase.table('vendors').select('id').eq('user_id', user[0]).execute()
    if not vendor_response.data: return jsonify({"error": "Vendor not found"}), 404
    vendor_id = vendor_response.data[0]['id']
    
    name = request.form.get('name', '')
    description = request.form.get('description', '')
    category = request.form.get('category', '')
    price = request.form.get('price', 0)
    stock = request.form.get('stock', 0)
    moq = request.form.get('moq', 1)
    
    image_url = None
    if 'image' in request.files:
        image = request.files['image']
        if image:
            result = save_upload(image, 'products')
            if result['success']:
                image_url = result['path']
            else:
                return jsonify({"error": result['error']}), 400
    
    pid = str(uuid.uuid4())
    product_data = {
        'id': pid,
        'vendor_id': vendor_id,
        'name': name,
        'description': description,
        'category': category,
        'price': float(price),
        'stock': int(stock),
        'moq': int(moq),
        'image_url': image_url,
        'created_at': datetime.now().isoformat()
    }
    supabase.table('products').insert(product_data).execute()
    
    log_analytics(vendor_id=vendor_id, metric_name='product_created', metric_value=1)
    
    return jsonify({"id": pid, "image_url": image_url})

@vendor_bp.route('/api/vendor/catalog/products/<pid>', methods=['PUT'])
def api_update_product(pid):
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    
    vendor_response = supabase.table('vendors').select('id').eq('user_id', user[0]).execute()
    if not vendor_response.data: return jsonify({"error": "Vendor not found"}), 404
    
    name = request.form.get('name', '')
    description = request.form.get('description', '')
    category = request.form.get('category', '')
    price = request.form.get('price', 0)
    stock = request.form.get('stock', 0)
    moq = request.form.get('moq', 1)
    image_url = None
    
    # Get existing image if not uploading new one
    product_response = supabase.table('products').select('image_url').eq('id', pid).execute()
    if product_response.data:
        image_url = product_response.data[0]['image_url']
    
    # Handle new image upload
    if 'image' in request.files:
        image = request.files['image']
        if image:
            result = save_upload(image, 'products')
            if result['success']:
                image_url = result['path']
            else:
                return jsonify({"error": result['error']}), 400
    
    update_data = {
        'name': name,
        'description': description,
        'category': category,
        'price': float(price),
        'stock': int(stock),
        'moq': int(moq),
        'image_url': image_url
    }
    supabase.table('products').update(update_data).eq('id', pid).execute()
    
    return jsonify({"updated": True})

@vendor_bp.route('/api/vendor/catalog/products/<pid>', methods=['DELETE'])
def api_delete_product(pid):
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    supabase.table('products').update({'is_active': False}).eq('id', pid).execute()
    return jsonify({"deleted": True})

@vendor_bp.route('/api/vendor/posts')
def api_vendor_posts():
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    response = supabase.table('posts').select('id, content, likes, created_at, image_url').eq('user_id', user[0]).order('created_at', desc=True).execute()
    posts = response.data
    return jsonify({"posts": posts})

@vendor_bp.route('/api/vendor/posts', methods=['POST'])
def api_create_vendor_post():
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    
    content = request.form.get('content', '')
    image_url = None
    
    if check_profanity(content):
        return jsonify({"error": "Content contains inappropriate language"}), 400
    
    # Handle image upload
    if 'image' in request.files:
        image = request.files['image']
        if image:
            result = save_upload(image, 'posts')
            if result['success']:
                image_url = result['path']
            else:
                return jsonify({"error": result['error']}), 400
    
    vendor_response = supabase.table('vendors').select('id').eq('user_id', user[0]).execute()
    vendor_id = vendor_response.data[0]['id'] if vendor_response.data else None
    
    pid = str(uuid.uuid4())
    post_data = {
        'id': pid,
        'user_id': user[0],
        'content': content,
        'image_url': image_url,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    supabase.table('posts').insert(post_data).execute()
    
    if vendor_id:
        log_analytics(vendor_id=vendor_id, metric_name='post_created', metric_value=1)
    
    return jsonify({"id": pid, "image_url": image_url})

@vendor_bp.route('/api/vendor/reviews')
def api_vendor_reviews():
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    
    vendor_response = supabase.table('vendors').select('id').eq('user_id', user[0]).execute()
    if not vendor_response.data: return jsonify({"error": "Vendor not found"}), 404
    vendor_id = vendor_response.data[0]['id']
    
    response = supabase.table('reviews').select('id, rating, comment, created_at, customer_id').eq('vendor_id', vendor_id).order('created_at', desc=True).execute()
    reviews = response.data
    
    # Get customer names
    customer_ids = [r['customer_id'] for r in reviews]
    if customer_ids:
        customers_response = supabase.table('users').select('id, full_name').in_('id', customer_ids).execute()
        customer_map = {c['id']: c['full_name'] for c in customers_response.data}
        for review in reviews:
            review['full_name'] = customer_map.get(review['customer_id'], 'Unknown')
    
    return jsonify({"reviews": reviews})

@vendor_bp.route('/api/vendor/analytics')
def api_vendor_analytics():
    """Get vendor analytics dashboard"""
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    
    vendor_response = supabase.table('vendors').select('id').eq('user_id', user[0]).execute()
    if not vendor_response.data: return jsonify({"error": "Vendor not found"}), 404
    vendor_id = vendor_response.data[0]['id']
    
    analytics = get_vendor_analytics(vendor_id)
    return jsonify(analytics or {})

@vendor_bp.route('/api/vendor/traffic')
def api_vendor_traffic():
    """Get vendor traffic patterns by hour"""
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    
    vendor_response = supabase.table('vendors').select('id').eq('user_id', user[0]).execute()
    if not vendor_response.data: return jsonify({"error": "Vendor not found"}), 404
    vendor_id = vendor_response.data[0]['id']
    
    days = request.args.get('days', 7, type=int)
    traffic = get_traffic_by_time(vendor_id, days)
    return jsonify(traffic or {})

@vendor_bp.route('/api/vendor/map')
def api_vendor_map():
    """Get vendor location and traffic data for map"""
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user or user[1] != 'vendor': return jsonify({"error": "Unauthorized"}), 401
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    
    days = request.args.get('days', 7, type=int)
    vendor_response = supabase.table('vendors').select('id, business_name, address, latitude, longitude').eq('user_id', user[0]).execute()
    if not vendor_response.data: return jsonify({"error": "Vendor not found"}), 404
    
    vendor = vendor_response.data[0]
    vendor_id = vendor['id']
    
    # Get traffic by time
    traffic = get_traffic_by_time(vendor_id, days)
    
    return jsonify({
        'id': vendor_id,
        'name': vendor['business_name'],
        'address': vendor['address'],
        'latitude': vendor['latitude'],
        'longitude': vendor['longitude'],
        'traffic': traffic
    })