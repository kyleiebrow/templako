"""
Analytics tracking and reporting module
"""
from models import supabase
from datetime import datetime, timedelta
import uuid
import json

def log_analytics(user_id=None, vendor_id=None, metric_type='event', metric_name='', metric_value=1.0):
    """Log an analytics event"""
    try:
        event_id = str(uuid.uuid4())
        data = {
            'id': event_id,
            'user_id': user_id,
            'vendor_id': vendor_id,
            'type': metric_type,
            'metric_name': metric_name,
            'metric_value': metric_value,
            'timestamp': datetime.now().isoformat()
        }
        supabase.table('analytics').insert(data).execute()
        return True
    except Exception as e:
        print(f"Analytics error: {e}")
        return False

def get_customer_analytics(user_id, days=30):
    """Get customer analytics dashboard data"""
    try:
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Vendor interactions
        vendor_response = supabase.table('analytics').select('vendor_id', count='exact').eq('user_id', user_id).gte('timestamp', start_date).eq('metric_name', 'vendor_view').execute()
        vendors_viewed = len(set(item['vendor_id'] for item in vendor_response.data if item['vendor_id']))
        
        # Posts created
        posts_response = supabase.table('posts').select('id', count='exact').eq('user_id', user_id).gte('created_at', start_date).execute()
        posts_created = posts_response.count
        
        # Total likes received
        likes_response = supabase.table('post_likes').select('post_likes.id', count='exact').gte('post_likes.created_at', start_date).execute()
        # This is complex, need to join with posts
        # For simplicity, count likes on user's posts
        user_posts = supabase.table('posts').select('id').eq('user_id', user_id).execute()
        post_ids = [p['id'] for p in user_posts.data]
        if post_ids:
            likes_count = 0
            for pid in post_ids:
                like_resp = supabase.table('post_likes').select('id', count='exact').eq('post_id', pid).gte('created_at', start_date).execute()
                likes_count += like_resp.count
            likes_received = likes_count
        else:
            likes_received = 0
        
        # Shortlists
        shortlist_response = supabase.table('shortlists').select('id', count='exact').eq('user_id', user_id).execute()
        total_shortlists = shortlist_response.count
        
        # Reviews given
        reviews_response = supabase.table('reviews').select('id', count='exact').eq('customer_id', user_id).gte('created_at', start_date).execute()
        reviews_given = reviews_response.count
        
        return {
            'vendors_viewed': vendors_viewed,
            'posts_created': posts_created,
            'likes_received': likes_received,
            'total_shortlists': total_shortlists,
            'reviews_given': reviews_given,
            'period_days': days
        }
    except Exception as e:
        print(f"Customer analytics error: {e}")
        return None

def get_vendor_analytics(vendor_id, days=30):
    """Get vendor analytics dashboard data"""
    try:
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Product views
        product_views_resp = supabase.table('analytics').select('id', count='exact').eq('vendor_id', vendor_id).gte('timestamp', start_date).eq('metric_name', 'product_view').execute()
        product_views = product_views_resp.count
        
        # Profile views
        profile_views_resp = supabase.table('analytics').select('id', count='exact').eq('vendor_id', vendor_id).gte('timestamp', start_date).eq('metric_name', 'vendor_view').execute()
        profile_views = profile_views_resp.count
        
        # Total reviews
        reviews_resp = supabase.table('reviews').select('rating', count='exact').eq('vendor_id', vendor_id).gte('created_at', start_date).execute()
        total_reviews = reviews_resp.count
        ratings = [r['rating'] for r in reviews_resp.data if r['rating']]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        
        # Total products
        products_resp = supabase.table('products').select('id', count='exact').eq('vendor_id', vendor_id).eq('is_active', True).execute()
        total_products = products_resp.count
        
        # Posts created - need to get vendor's user_id first
        vendor_resp = supabase.table('vendors').select('user_id').eq('id', vendor_id).execute()
        if vendor_resp.data:
            vendor_user_id = vendor_resp.data[0]['user_id']
            posts_resp = supabase.table('posts').select('id', count='exact').eq('user_id', vendor_user_id).gte('created_at', start_date).execute()
            posts_created = posts_resp.count
            
            # Post engagement - sum of likes on vendor's posts
            vendor_posts = supabase.table('posts').select('id, likes').eq('user_id', vendor_user_id).gte('created_at', start_date).execute()
            post_engagement = sum(p['likes'] or 0 for p in vendor_posts.data)
        else:
            posts_created = 0
            post_engagement = 0
        
        # Shortlists count
        shortlists_resp = supabase.table('shortlists').select('id', count='exact').eq('vendor_id', vendor_id).execute()
        total_shortlists = shortlists_resp.count
        
        return {
            'product_views': product_views,
            'profile_views': profile_views,
            'total_reviews': total_reviews,
            'avg_rating': round(avg_rating, 1),
            'total_products': total_products,
            'posts_created': posts_created,
            'post_engagement': post_engagement,
            'total_shortlists': total_shortlists,
            'period_days': days
        }
    except Exception as e:
        print(f"Vendor analytics error: {e}")
        return None

def get_admin_analytics(days=30):
    """Get admin analytics dashboard data"""
    try:
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Total users
        users_resp = supabase.table('users').select('id', count='exact').execute()
        total_users = users_resp.count
        
        # New users this period
        new_users_resp = supabase.table('users').select('id', count='exact').gte('created_at', start_date).execute()
        new_users = new_users_resp.count
        
        # Total vendors
        vendors_resp = supabase.table('vendors').select('id', count='exact').execute()
        total_vendors = vendors_resp.count
        
        # Active vendors
        active_vendors_resp = supabase.table('vendors').select('id', count='exact').eq('is_active', True).execute()
        active_vendors = active_vendors_resp.count
        
        # Total products
        products_resp = supabase.table('products').select('id', count='exact').eq('is_active', True).execute()
        total_products = products_resp.count
        
        # Total posts
        posts_resp = supabase.table('posts').select('id', count='exact').gte('created_at', start_date).execute()
        total_posts = posts_resp.count
        
        # Total reviews
        reviews_resp = supabase.table('reviews').select('rating', count='exact').gte('created_at', start_date).execute()
        total_reviews = reviews_resp.count
        ratings = [r['rating'] for r in reviews_resp.data if r['rating']]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        
        # Suspended users
        suspended_resp = supabase.table('users').select('id', count='exact').eq('is_suspended', True).execute()
        suspended_users = suspended_resp.count
        
        # Platform traffic (unique views)
        traffic_resp = supabase.table('analytics').select('user_id').gte('timestamp', start_date).execute()
        unique_visitors = len(set(item['user_id'] for item in traffic_resp.data if item['user_id']))
        
        # Top vendors by rating
        top_vendors_resp = supabase.table('vendors').select('id, business_name, rating, category').eq('is_active', True).order('rating', desc=True).limit(5).execute()
        top_vendors = [{'id': v['id'], 'name': v['business_name'], 'rating': v['rating'], 'category': v['category']} for v in top_vendors_resp.data]
        
        # Most reviewed vendors
        # This requires aggregation, might need RPC or multiple queries
        vendors_list = supabase.table('vendors').select('id, business_name').eq('is_active', True).execute()
        most_reviewed = []
        for v in vendors_list.data:
            review_count_resp = supabase.table('reviews').select('id', count='exact').eq('vendor_id', v['id']).execute()
            most_reviewed.append({'id': v['id'], 'name': v['business_name'], 'reviews': review_count_resp.count})
        most_reviewed.sort(key=lambda x: x['reviews'], reverse=True)
        most_reviewed = most_reviewed[:5]
        
        return {
            'total_users': total_users,
            'new_users': new_users,
            'total_vendors': total_vendors,
            'active_vendors': active_vendors,
            'total_products': total_products,
            'total_posts': total_posts,
            'total_reviews': total_reviews,
            'avg_rating': round(avg_rating, 1),
            'suspended_users': suspended_users,
            'unique_visitors': unique_visitors,
            'top_vendors': top_vendors,
            'most_reviewed': most_reviewed,
            'period_days': days
        }
    except Exception as e:
        print(f"Admin analytics error: {e}")
        return None

def get_traffic_by_time(vendor_id, days=7):
    """Get vendor traffic patterns by hour of day"""
    try:
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        traffic_by_hour = [0] * 24
        
        # Get analytics data
        analytics_resp = supabase.table('analytics').select('timestamp').eq('vendor_id', vendor_id).gte('timestamp', start_date).execute()
        
        for item in analytics_resp.data:
            if item['timestamp']:
                # Extract hour from ISO timestamp
                dt = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
                hour = dt.hour
                traffic_by_hour[hour] += 1
        
        # Calculate peak hours
        peak_hour = traffic_by_hour.index(max(traffic_by_hour)) if traffic_by_hour else 0
        
        return {
            'traffic_by_hour': traffic_by_hour,
            'peak_hour': peak_hour,
            'total_traffic': sum(traffic_by_hour),
            'avg_per_hour': sum(traffic_by_hour) / 24 if traffic_by_hour else 0,
            'period_days': days
        }
    except Exception as e:
        print(f"Traffic analytics error: {e}")
        return None
