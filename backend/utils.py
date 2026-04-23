import random
import string
import math
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from better_profanity import profanity
import uuid
from config import SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def generate_magic_token():
    return str(uuid.uuid4())

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

def send_magic_link_email(email, token):
    try:
        magic_link = f"https://yourdomain.com/auth/verify/{token}"  # Replace with your actual domain
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = email
        msg['Subject'] = "Lako - Sign In Link"
        msg.attach(MIMEText(f"Click this link to sign in: {magic_link}\n\nThis link expires in 10 minutes.", 'plain'))
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_USERNAME, email, msg.as_string())
        server.quit()
        print(f"✓ Magic link sent to {email}")
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def get_user_by_token(token):
    if not token: return None
    from models import supabase
    if not supabase: return None
    response = supabase.table('users').select('id, role, full_name, email').eq('id', token).execute()
    if response.data:
        user = response.data[0]
        return (user['id'], user['role'], user['full_name'], user['email'])
    return None

def calculate_distance(lat1, lng1, lat2, lng2):
    if None in [lat1, lng1, lat2, lng2]: return float('inf')
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def check_profanity(text):
    return profanity.contains_profanity(text)

def suggest_suspension(user_id):
    # Simple algorithm: if user has many negative reviews or posts with profanity
    from models import supabase
    if not supabase: return False
    
    # Check posts with profanity
    response = supabase.table('posts').select('id', count='exact').ilike('content', '%fuck%').eq('user_id', user_id).execute()
    profanity_posts = response.count
    
    # Check negative reviews
    response = supabase.table('reviews').select('id', count='exact').eq('customer_id', user_id).lte('rating', 2).execute()
    negative_reviews = response.count
    
    # Suggest suspension if more than 3 profanity posts or 5 negative reviews
    return profanity_posts > 3 or negative_reviews > 5