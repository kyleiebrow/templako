from flask import Blueprint, request, jsonify
from models import supabase
from utils import get_user_by_token, suggest_suspension
from analytics import get_admin_analytics

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/api/admin/stats')
def api_admin_stats():
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    users = supabase.table('users').select('id', count='exact').execute().count
    vendors = supabase.table('vendors').select('id', count='exact').execute().count
    products = supabase.table('products').select('id', count='exact').execute().count
    reviews = supabase.table('reviews').select('id', count='exact').execute().count
    return jsonify({"total_users": users, "total_vendors": vendors, "total_products": products, "total_reviews": reviews})

@admin_bp.route('/api/admin/analytics')
def api_admin_analytics():
    """Get comprehensive admin analytics dashboard"""
    days = request.args.get('days', 30, type=int)
    analytics = get_admin_analytics(days)
    return jsonify(analytics or {})

@admin_bp.route('/api/admin/users')
def api_admin_users():
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    response = supabase.table('users').select('id, full_name, email, role, created_at, is_suspended').order('created_at', desc=True).execute()
    users = response.data
    # Add suspension suggestions
    for user in users:
        user['suggest_suspend'] = suggest_suspension(user['id'])
    return jsonify(users)

@admin_bp.route('/api/admin/users/<uid>', methods=['DELETE'])
def api_admin_delete_user(uid):
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    supabase.table('users').delete().eq('id', uid).execute()
    return jsonify({"deleted": True})

@admin_bp.route('/api/admin/users/<uid>/suspend', methods=['POST'])
def api_admin_suspend_user(uid):
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    supabase.table('users').update({'is_suspended': True}).eq('id', uid).execute()
    return jsonify({"suspended": True})

@admin_bp.route('/api/admin/vendors')
def api_admin_vendors():
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    response = supabase.table('vendors').select('id, business_name, category, rating, is_active').order('created_at', desc=True).execute()
    vendors = response.data
    return jsonify(vendors)

@admin_bp.route('/api/admin/products')
def api_admin_products():
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    response = supabase.table('products').select('id, name, price, vendor_id').order('created_at', desc=True).execute()
    products = response.data
    
    # Get vendor names
    vendor_ids = [p['vendor_id'] for p in products]
    if vendor_ids:
        vendors_response = supabase.table('vendors').select('id, business_name').in_('id', vendor_ids).execute()
        vendor_map = {v['id']: v['business_name'] for v in vendors_response.data}
        for product in products:
            product['vendor_name'] = vendor_map.get(product['vendor_id'], 'Unknown')
    
    return jsonify(products)

@admin_bp.route('/api/admin/products/<pid>', methods=['DELETE'])
def api_admin_delete_product(pid):
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    supabase.table('products').delete().eq('id', pid).execute()
    return jsonify({"deleted": True})

@admin_bp.route('/api/admin/reviews')
def api_admin_reviews():
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    response = supabase.table('reviews').select('id, rating, comment, created_at, customer_id, vendor_id').order('created_at', desc=True).execute()
    reviews = response.data
    
    # Get customer and vendor names
    customer_ids = [r['customer_id'] for r in reviews]
    vendor_ids = [r['vendor_id'] for r in reviews]
    
    customer_map = {}
    vendor_map = {}
    
    if customer_ids:
        customers_response = supabase.table('users').select('id, full_name').in_('id', customer_ids).execute()
        customer_map = {c['id']: c['full_name'] for c in customers_response.data}
    
    if vendor_ids:
        vendors_response = supabase.table('vendors').select('id, business_name').in_('id', vendor_ids).execute()
        vendor_map = {v['id']: v['business_name'] for v in vendors_response.data}
    
    for review in reviews:
        review['customer_name'] = customer_map.get(review['customer_id'], 'Unknown')
        review['vendor_name'] = vendor_map.get(review['vendor_id'], 'Unknown')
    
    return jsonify(reviews)

@admin_bp.route('/api/admin/reviews/<rid>', methods=['DELETE'])
def api_admin_delete_review(rid):
    if not supabase: return jsonify({"error": "Database unavailable"}), 500
    supabase.table('reviews').delete().eq('id', rid).execute()
    return jsonify({"deleted": True})