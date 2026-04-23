from flask import Blueprint, request, jsonify
import uuid
from datetime import datetime
from models import supabase
from utils import get_user_by_token, calculate_distance, check_profanity
from upload import save_upload
from analytics import log_analytics, get_customer_analytics

customer_bp = Blueprint('customer', __name__)

@customer_bp.route('/api/customer/map/vendors')
def api_nearby_vendors():
    lat = float(request.args.get('lat', 13.9443))
    lng = float(request.args.get('lng', 121.3798))
    radius = float(request.args.get('radius_km', 20))
    response = supabase.table('vendors').select('id, business_name, category, description, address, latitude, longitude, rating, phone').eq('is_active', 1).execute()
    vendors = []
    for v in response.data:
        if v['latitude'] and v['longitude']:
            dist = calculate_distance(lat, lng, v['latitude'], v['longitude'])
            if dist <= radius:
                vendors.append({"id": v['id'], "name": v['business_name'], "category": v['category'], "description": v['description'] or "", "address": v['address'], "latitude": v['latitude'], "longitude": v['longitude'], "rating": v['rating'] or 0, "phone": v['phone'] or "", "distance": round(dist, 2)})
    vendors.sort(key=lambda x: x['distance'])
    return jsonify({"vendors": vendors})

@customer_bp.route('/api/customer/feed')
def api_customer_feed():
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    
    # Get posts with user info
    response = supabase.table('posts').select('id, content, likes, created_at, users!inner(full_name), image_url').order('created_at', desc=True).limit(50).execute()
    posts_data = response.data
    
    posts = []
    for post in posts_data:
        pid = post['id']
        
        # Count comments
        comments_response = supabase.table('post_comments').select('id', count='exact').eq('post_id', pid).execute()
        comment_count = comments_response.count
        
        # Check if user liked
        user_liked = False
        if user:
            like_response = supabase.table('post_likes').select('id').eq('post_id', pid).eq('user_id', user[0]).execute()
            user_liked = len(like_response.data) > 0
        
        posts.append({
            'id': pid,
            'content': post['content'],
            'likes': post['likes'],
            'created_at': post['created_at'],
            'author': post['users']['full_name'],
            'image_url': post['image_url'],
            'comments': comment_count,
            'user_liked': user_liked
        })
    
    return jsonify({"posts": posts})

@customer_bp.route('/api/customer/posts', methods=['POST'])
def api_create_customer_post():
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user: return jsonify({"error": "Unauthorized"}), 401
    
    # Guest users cannot create posts with restrictions
    if user[1] == 'guest':
        return jsonify({"error": "Guest users cannot create posts"}), 403
    
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
    
    log_analytics(user_id=user[0], metric_name='post_created', metric_value=1)
    
    return jsonify({"id": pid, "image_url": image_url})

@customer_bp.route('/api/customer/posts/<pid>', methods=['GET'])
def api_get_post(pid):
    """Get detailed post with comments"""
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    
    # Get post with user info
    response = supabase.table('posts').select('id, content, likes, created_at, users!inner(full_name), image_url').eq('id', pid).execute()
    post_data = response.data
    
    if not post_data:
        return jsonify({"error": "Post not found"}), 404
    
    post = post_data[0]
    
    # Get comments
    comments_response = supabase.table('post_comments').select('id, comment, created_at, users!inner(full_name)').eq('post_id', pid).order('created_at', desc=True).execute()
    comments = [{'id': c['id'], 'text': c['comment'], 'created_at': c['created_at'], 'author': c['users']['full_name']} for c in comments_response.data]
    
    user_liked = False
    if user:
        like_response = supabase.table('post_likes').select('id').eq('post_id', pid).eq('user_id', user[0]).execute()
        user_liked = len(like_response.data) > 0
    
    return jsonify({
        'id': post['id'],
        'content': post['content'],
        'likes': post['likes'],
        'created_at': post['created_at'],
        'author': post['users']['full_name'],
        'image_url': post['image_url'],
        'comments': comments,
        'user_liked': user_liked
    })

@customer_bp.route('/api/customer/posts/<pid>/like', methods=['POST'])
def api_like_post(pid):
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user: return jsonify({"error": "Unauthorized"}), 401
    
    # Check if already liked
    like_response = supabase.table('post_likes').select('id').eq('post_id', pid).eq('user_id', user[0]).execute()
    already_liked = len(like_response.data) > 0
    
    if already_liked:
        # Unlike
        supabase.table('post_likes').delete().eq('post_id', pid).eq('user_id', user[0]).execute()
        # Decrement likes
        supabase.table('posts').update({'likes': supabase.table('posts').select('likes').eq('id', pid).execute().data[0]['likes'] - 1}).eq('id', pid).execute()
        liked = False
    else:
        # Like
        like_id = str(uuid.uuid4())
        supabase.table('post_likes').insert({
            'id': like_id,
            'post_id': pid,
            'user_id': user[0],
            'created_at': datetime.now().isoformat()
        }).execute()
        # Increment likes
        supabase.table('posts').update({'likes': supabase.table('posts').select('likes').eq('id', pid).execute().data[0]['likes'] + 1}).eq('id', pid).execute()
        liked = True
    
    log_analytics(user_id=user[0], metric_name='post_liked', metric_value=1)
    
    return jsonify({"liked": liked})

@customer_bp.route('/api/customer/posts/<pid>/comment', methods=['POST'])
def api_comment_post(pid):
    """Add a comment to a post"""
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user: return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    comment_text = data.get('comment', '').strip()
    
    if not comment_text:
        return jsonify({"error": "Comment cannot be empty"}), 400
    
    if check_profanity(comment_text):
        return jsonify({"error": "Comment contains inappropriate language"}), 400
    
    # Verify post exists
    post_response = supabase.table('posts').select('id').eq('id', pid).execute()
    if not post_response.data:
        return jsonify({"error": "Post not found"}), 404
    
    comment_id = str(uuid.uuid4())
    supabase.table('post_comments').insert({
        'id': comment_id,
        'post_id': pid,
        'user_id': user[0],
        'comment': comment_text,
        'created_at': datetime.now().isoformat()
    }).execute()
    
    log_analytics(user_id=user[0], metric_name='post_commented', metric_value=1)
    
    return jsonify({"id": comment_id, "comment": comment_text, "author": user[2]})

@customer_bp.route('/api/customer/shortlist')
def api_get_shortlist():
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user: return jsonify({"error": "Unauthorized"}), 401
    
    response = supabase.table('shortlists').select('vendors!inner(*)').eq('user_id', user[0]).execute()
    shortlist = [item['vendors'] for item in response.data]
    return jsonify({"shortlist": shortlist})

@customer_bp.route('/api/customer/shortlist/<vendor_id>', methods=['POST'])
def api_toggle_shortlist(vendor_id):
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user: return jsonify({"error": "Unauthorized"}), 401
    
    # Guests cannot shortlist
    if user[1] == 'guest':
        return jsonify({"error": "Guest users cannot shortlist"}), 403
    
    # Check if already shortlisted
    shortlist_response = supabase.table('shortlists').select('id').eq('user_id', user[0]).eq('vendor_id', vendor_id).execute()
    if shortlist_response.data:
        # Remove
        supabase.table('shortlists').delete().eq('user_id', user[0]).eq('vendor_id', vendor_id).execute()
        added = False
    else:
        # Add
        supabase.table('shortlists').insert({
            'id': str(uuid.uuid4()),
            'user_id': user[0],
            'vendor_id': vendor_id,
            'created_at': datetime.now().isoformat()
        }).execute()
        added = True
    
    log_analytics(user_id=user[0], vendor_id=vendor_id, metric_name='vendor_shortlisted', metric_value=1)
    
    return jsonify({"added": added})

@customer_bp.route('/api/customer/analytics')
def api_customer_analytics():
    """Get customer analytics dashboard"""
    token = request.headers.get('X-Session-Token')
    user = get_user_by_token(token)
    if not user: return jsonify({"error": "Unauthorized"}), 401
    
    # Guests cannot access analytics
    if user[1] == 'guest':
        return jsonify({"error": "Guest users cannot access analytics"}), 403
    
    analytics = get_customer_analytics(user[0])
    return jsonify(analytics or {})