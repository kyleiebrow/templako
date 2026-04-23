"""
Map & Navigation Module
OpenStreetMap with traffic heatmap, vendor locations, and routing
"""
from flask import Blueprint, request, jsonify
from models import supabase
from datetime import datetime, timedelta
import json

map_bp = Blueprint('map', __name__)

@map_bp.route('/api/map/traffic-heatmap')
def get_traffic_heatmap():
    """
    Get traffic heatmap data for a specific region
    Returns intensity map - higher values = more congestion
    Data format: [[lat, lng, intensity (0-1)], ...]
    """
    lat = float(request.args.get('lat', 13.9443))
    lng = float(request.args.get('lng', 121.3798))
    hour = request.args.get('hour')  # Optional: specific hour for prediction
    
    # Get vendors with analytics
    vendors_resp = supabase.table('vendors').select('latitude, longitude').eq('is_active', True).execute()
    
    heatmap_data = []
    for v in vendors_resp.data:
        if v['latitude'] and v['longitude']:
            # Simple intensity based on proximity and activity
            intensity = 0.5  # Default intensity
            heatmap_data.append([round(v['latitude'], 4), round(v['longitude'], 4), intensity])
    
    # If no real data, return mock heatmap around given location
    if not heatmap_data:
        heatmap_data = [
            [lat, lng, 0.8],
            [lat + 0.01, lng + 0.01, 0.5],
            [lat - 0.01, lng - 0.01, 0.3],
            [lat + 0.02, lng - 0.02, 0.6],
            [lat - 0.02, lng + 0.02, 0.2],
        ]
    
    return jsonify({
        "heatmap": heatmap_data,
        "timestamp": datetime.now().isoformat(),
        "center": [lat, lng]
    })

@map_bp.route('/api/map/routes')
def get_route():
    """
    Get route between two points using Open Route Service (free tier)
    Format: start_lat,start_lng to end_lat,end_lng
    """
    start = request.args.get('start')  # "lat,lng"
    end = request.args.get('end')      # "lat,lng"
    profile = request.args.get('profile', 'driving')  # driving, walking, cycling
    
    if not start or not end:
        return jsonify({"error": "Missing start or end coordinates"}), 400
    
    try:
        start_lat, start_lng = map(float, start.split(','))
        end_lat, end_lng = map(float, end.split(','))
    except:
        return jsonify({"error": "Invalid coordinates"}), 400
    
    # In production, use OpenRouteService API
    # For demo, return mock route
    mock_route = {
        "route": [
            [start_lng, start_lat],
            [(start_lng + end_lng) / 2, (start_lat + end_lat) / 2],
            [end_lng, end_lat]
        ],
        "distance": round(calculate_distance(start_lat, start_lng, end_lat, end_lng), 2),
        "duration_minutes": round(calculate_distance(start_lat, start_lng, end_lat, end_lng) * 2),  # Rough estimate
        "profile": profile
    }
    
    return jsonify(mock_route)

@map_bp.route('/api/map/vendors/heatmap')
def get_vendor_heatmap():
    """
    Get vendor locations as heatmap layer
    Shows concentration of vendors in different areas
    """
    radius_km = float(request.args.get('radius_km', 50))
    category = request.args.get('category')  # Optional filter
    
    query = supabase.table('vendors').select('latitude, longitude, is_active').eq('is_active', True)
    if category:
        query = query.eq('category', category)
    
    vendors_resp = query.execute()
    vendors = []
    for v in vendors_resp.data:
        if v['latitude'] and v['longitude']:
            # Intensity based on activity (1.0 = high concentration area)
            intensity = 0.7 if v['is_active'] else 0.2
            vendors.append([v['latitude'], v['longitude'], intensity])
    
    return jsonify({
        "vendor_heatmap": vendors,
        "timestamp": datetime.now().isoformat()
    })

@map_bp.route('/api/map/analytics/by-hour')
def get_traffic_by_hour():
    """
    Get traffic/activity patterns by hour of day
    Used for heatmap color gradients (Google Maps traffic style)
    """
    # Get analytics data from last 7 days
    start_date = (datetime.now() - timedelta(days=7)).isoformat()
    analytics_resp = supabase.table('analytics').select('timestamp').gte('timestamp', start_date).execute()
    
    hourly_data = []
    counts = {}
    
    for item in analytics_resp.data:
        if item['timestamp']:
            dt = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
            hour = dt.hour
            counts[hour] = counts.get(hour, 0) + 1
    
    all_counts = []
    for hour in range(24):
        count = counts.get(hour, 0)
        all_counts.append(count)
        hourly_data.append({
            "hour": hour,
            "activity_count": count,
            "traffic_avg": 0  # Simplified
        })
    
    # Calculate intensity
    max_count = max(all_counts) if all_counts else 1
    for item in hourly_data:
        item["intensity"] = item["activity_count"] / max_count if max_count > 0 else 0
    
    return jsonify({
        "hourly_traffic": hourly_data,
        "peak_hours": sorted(hourly_data, key=lambda x: x['intensity'], reverse=True)[:3]
    })

# ============== HELPER FUNCTIONS ==============

def calculate_distance(lat1, lng1, lat2, lng2):
    """Calculate distance in kilometers using Haversine formula"""
    from math import radians, cos, sin, asin, sqrt
    
    lon1, lat1, lon2, lat2 = map(radians, [lng1, lat1, lng2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r
