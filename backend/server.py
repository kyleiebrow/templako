from flask import Flask, jsonify, request, session as flask_session
from flask_cors import CORS
import os
import re
import uuid
import math
import bcrypt
import json
import random
import base64
import requests
from datetime import datetime, timedelta, timezone
from supabase import create_client
from PIL import Image
import io
from dotenv import load_dotenv

load_dotenv()

# ============================================
# CONFIGURATION
# ============================================

# ============================================
# CONFIGURATION
# ============================================

# ============================================
# CONFIGURATION
# ============================================

SECRET_KEY = os.environ.get('SECRET_KEY', 'lako-secret-key-2024')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
BREVO_API_KEY = os.environ.get('BREVO_API_KEY')
BREVO_SENDER_EMAIL = os.environ.get('BREVO_SENDER_EMAIL')
BREVO_SENDER_NAME = os.environ.get('BREVO_SENDER_NAME', 'Lako')
TEXTBEE_API_KEY = os.environ.get('TEXTBEE_API_KEY')
TEXTBEE_DEVICE_ID = os.environ.get('TEXTBEE_DEVICE_ID')
TEXTBEE_SENDER_NAME = os.environ.get('TEXTBEE_SENDER_NAME', 'Lako')
APP_NAME = os.environ.get('APP_NAME', 'Lako')
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
PORT = int(os.environ.get('PORT', 5000))
RENDER = os.environ.get('RENDER', 'false').lower() == 'true'

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY are required")

print(f"✓ {APP_NAME} Configuration loaded")

# ============================================
# UTC HELPER
# ============================================

def utc_now():
    return datetime.now(timezone.utc).isoformat()

# ============================================
# SUPABASE INIT
# ============================================

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
print("✓ Supabase connected")

# ============================================
# NOTIFICATION SERVICE (Brevo Email + TextBee SMS)
# ============================================

# ============================================
# NOTIFICATION SERVICE (Brevo Email + TextBee SMS)
# ============================================

class NotificationService:
    def __init__(self):
        self.brevo_api_key = BREVO_API_KEY
        self.brevo_sender_email = BREVO_SENDER_EMAIL
        self.brevo_sender_name = BREVO_SENDER_NAME
        self.textbee_api_key = TEXTBEE_API_KEY
        self.textbee_device_id = TEXTBEE_DEVICE_ID
        self.textbee_sender_name = TEXTBEE_SENDER_NAME
        self.email_enabled = bool(self.brevo_api_key and self.brevo_sender_email)
        self.sms_enabled = bool(self.textbee_api_key and self.textbee_device_id)
        
        # TextBee base URL
        self.textbee_base_url = "https://api.textbee.dev/api/v1"
        
        if self.email_enabled:
            print(f"✓ Brevo email enabled - Sender: {self.brevo_sender_name} <{self.brevo_sender_email}>")
        if self.sms_enabled:
            print(f"✓ TextBee SMS enabled - Device ID: {self.textbee_device_id}")
    
    # ============================================
    # HELPER: Convert phone to local 09 format
    # ============================================
    
    def format_phone_for_sms(self, phone_number):
        """Convert any phone format to local 09xxxxxxxxx for SMS sending"""
        if not phone_number:
            return None
        
        # Convert to string and remove all non-digit characters
        digits = ''.join(filter(str.isdigit, str(phone_number)))
        
        # Philippine numbers: convert 63 or +63 to 09
        if len(digits) == 12 and digits.startswith('63'):
            # 639xxxxxxxxxx -> 09xxxxxxxxx
            digits = '0' + digits[2:]
        elif len(digits) == 13 and digits.startswith('63'):
            # 639xxxxxxxxxx (with extra digit) -> 09xxxxxxxxx
            digits = '0' + digits[2:]
        elif len(digits) == 11 and digits.startswith('09'):
            # Already correct format
            pass
        elif len(digits) == 10 and digits.startswith('9'):
            # 9xxxxxxxxx -> 09xxxxxxxxx
            digits = '0' + digits
        elif len(digits) == 10 and digits.startswith('0'):
            # 0xxxxxxxxx -> add 9? No, keep as is (09xxxxxxxxx is 11 digits)
            pass
        
        # Ensure we have 11 digits starting with 09
        if len(digits) == 11 and digits.startswith('09'):
            return digits
        else:
            # Return original if format is unexpected
            return phone_number
    
    # ============================================
    # EMAIL METHODS
    # ============================================
    
    def send_email(self, to_email, subject, html_content):
        """Send email using Brevo API"""
        if not self.email_enabled or not to_email:
            print(f"[EMAIL SIMULATION] To: {to_email}, Subject: {subject}")
            return True
        
        if to_email.endswith('@lako.customer') or to_email.endswith('@lako.vendor'):
            print(f"[SKIP] Auto-generated email: {to_email}")
            return True
        
        try:
            response = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": self.brevo_api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                json={
                    "sender": {"name": self.brevo_sender_name, "email": self.brevo_sender_email},
                    "to": [{"email": to_email}],
                    "subject": subject,
                    "htmlContent": html_content
                },
                timeout=30
            )
            success = response.status_code in [200, 201, 202]
            if success:
                print(f"✓ Email sent to {to_email}")
            else:
                print(f"✗ Email failed ({response.status_code}): {response.text}")
            return success
        except Exception as e:
            print(f"Brevo error: {e}")
            return False
    
    # ============================================
    # SMS METHODS - WITH LOCAL 09 FORMAT
    # ============================================
    
    def send_sms(self, phone_number, message):
        """Send SMS using TextBee API - converts to local 09 format"""
        if not self.sms_enabled or not phone_number:
            print(f"[SMS SIMULATION] To: {phone_number}, Message: {message}")
            return True
        
        try:
            # Convert phone number to local 09 format
            local_phone = self.format_phone_for_sms(phone_number)
            
            print(f"📱 Phone conversion: {phone_number} -> {local_phone}")
            
            # CORRECTED: Use the proper TextBee endpoint
            url = f"{self.textbee_base_url}/gateway/devices/{self.textbee_device_id}/send-sms"
            
            response = requests.post(
                url,
                headers={
                    "x-api-key": self.textbee_api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "recipients": [local_phone],
                    "message": message
                },
                timeout=30
            )
            
            success = response.status_code == 200
            if success:
                print(f"✓ SMS sent to {local_phone}")
                print(f"   Response: {response.json() if response.text else 'OK'}")
            else:
                print(f"✗ SMS failed ({response.status_code}): {response.text}")
            return success
        except Exception as e:
            print(f"TextBee error: {e}")
            return False
    
    # ============================================
    # OTP VERIFICATION (Email + SMS)
    # ============================================
    
    def send_verification_code_email(self, email, otp, name=None):
        """Send OTP via email with dynamic personalization"""
        display_name = name or "Valued Customer"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Verification Code</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 20px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #2d8c3c, #1a6b28); padding: 30px 20px; text-align: center; }}
                .header h1 {{ color: white; margin: 0; font-size: 28px; }}
                .content {{ padding: 30px; }}
                .greeting {{ font-size: 18px; color: #1a2e1a; margin-bottom: 20px; }}
                .code-box {{ background: #f5faf5; border-radius: 16px; padding: 25px; text-align: center; margin: 20px 0; border: 2px dashed #2d8c3c; }}
                .code {{ font-size: 42px; font-weight: bold; letter-spacing: 8px; color: #2d8c3c; font-family: monospace; }}
                .expiry {{ color: #6b8c6b; font-size: 13px; text-align: center; margin-top: 15px; }}
                .footer {{ background: #f8faf8; padding: 20px; text-align: center; font-size: 12px; color: #8ba88b; }}
                .warning {{ background: #fff3e0; padding: 12px; border-radius: 12px; font-size: 13px; color: #e65100; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 {APP_NAME}</h1>
                    <p style="color: rgba(255,255,255,0.9); margin: 5px 0 0;">Verification Code</p>
                </div>
                <div class="content">
                    <div class="greeting">Hello {display_name},</div>
                    <p>We received a request to verify your {APP_NAME} account. Use the verification code below to complete your registration.</p>
                    <div class="code-box">
                        <div class="code">{otp}</div>
                    </div>
                    <div class="expiry">⏰ This code expires in <strong>10 minutes</strong></div>
                    <div class="warning">
                        ⚠️ If you didn't request this code, please ignore this email or contact support.
                    </div>
                </div>
                <div class="footer">
                    <p>{APP_NAME} - GPS Based Vendor Discovery App</p>
                    <p>📍 Tiaong, Quezon | 🍢 Made with love for local food lovers</p>
                    <p>© 2024 {APP_NAME}. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return self.send_email(email, f"🔐 Your {APP_NAME} Verification Code", html)
    
    def send_verification_code_sms(self, phone, otp, name=None):
        """Send OTP via SMS with personalization - uses local 09 format"""
        display_name = name or "there"
        message = f"""🔐 {APP_NAME} Verification Code

Hi {display_name}!

Your verification code is: {otp}

⏰ This code expires in 10 minutes.

Never share this code with anyone, even if they claim to be from {APP_NAME}.

{APP_NAME} - Find the best street food in Tiaong, Quezon! 🍢"""
        return self.send_sms(phone, message)
    
    def send_verification_code(self, email, phone, otp, name=None):
        """Send OTP via both email and SMS"""
        results = {'email': False, 'sms': False}
        
        if email and not email.endswith('@lako.customer') and not email.endswith('@lako.vendor'):
            results['email'] = self.send_verification_code_email(email, otp, name)
        
        if phone:
            results['sms'] = self.send_verification_code_sms(phone, otp, name)
        
        return results
    
    # ============================================
    # WELCOME MESSAGES (Dynamic by role)
    # ============================================
    
    def send_welcome_email(self, email, name, role='customer', business_name=None, vendor_name=None):
        """Send dynamic welcome email based on role"""
        if not email or email.endswith('@lako.customer') or email.endswith('@lako.vendor'):
            return True
        
        if role == 'admin':
            icon = "👑"
            title = "Admin Dashboard"
            display_name = name
            welcome_message = "You have full access to manage users, vendors, and platform analytics!"
            cta_text = "Go to Admin Panel"
            cta_link = f"{BASE_URL}/admin"
            features = [
                "📊 View platform statistics",
                "👥 Manage all users and vendors",
                "🍽️ Manage vendor products",
                "⚠️ Suspend/unsuspend accounts",
                "📈 Monitor platform growth"
            ]
            
        elif role == 'customer':
            icon = "🍢"
            title = "Food Explorer"
            display_name = name
            welcome_message = "Start exploring street food vendors near you in Tiaong, Quezon!"
            cta_text = "Start Exploring"
            cta_link = f"{BASE_URL}/customer"
            features = [
                "📍 Find street food vendors near you",
                "📋 Browse menus with photos",
                "⭐ Save your favorite vendors",
                "🗺️ Get turn-by-turn directions",
                "📝 Write reviews and rate vendors",
                "📱 Share your food experiences"
            ]
            
        else:  # vendor
            icon = "🏪"
            title = "Business Owner"
            display_name = business_name or name
            welcome_message = "Start managing your business and reaching more customers in Tiaong, Quezon!"
            cta_text = "Go to Dashboard"
            cta_link = f"{BASE_URL}/vendor"
            features = [
                "📝 Manage your product catalog with photos",
                "⏰ Set your operating hours",
                "📊 Track customer traffic and analytics",
                "⭐ Respond to customer reviews",
                "📢 Create posts to engage customers",
                "📍 Update your business location"
            ]
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Welcome to {APP_NAME}</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f5faf5; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 28px; overflow: hidden; box-shadow: 0 8px 24px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #2d8c3c, #1a6b28); padding: 40px 30px; text-align: center; }}
                .header .icon {{ font-size: 64px; margin-bottom: 10px; }}
                .header h1 {{ color: white; margin: 0; font-size: 32px; }}
                .header p {{ color: rgba(255,255,255,0.9); margin: 10px 0 0; }}
                .content {{ padding: 35px; }}
                .greeting {{ font-size: 24px; font-weight: 600; color: #1a2e1a; margin-bottom: 15px; }}
                .message {{ color: #4a5e4a; font-size: 16px; line-height: 1.6; margin-bottom: 25px; }}
                .features {{ background: #f8faf8; border-radius: 20px; padding: 20px; margin: 25px 0; }}
                .features h3 {{ color: #1a2e1a; margin-bottom: 15px; font-size: 18px; }}
                .features ul {{ list-style: none; padding: 0; margin: 0; }}
                .features li {{ padding: 10px 0; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #e8ece8; }}
                .features li:last-child {{ border-bottom: none; }}
                .features li::before {{ content: "✓"; background: #2d8c3c; color: white; width: 24px; height: 24px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 14px; }}
                .cta-button {{ display: inline-block; background: linear-gradient(135deg, #2d8c3c, #1a6b28); color: white; text-decoration: none; padding: 14px 32px; border-radius: 48px; font-weight: 600; margin: 20px 0; text-align: center; }}
                .footer {{ background: #f8faf8; padding: 20px; text-align: center; font-size: 12px; color: #8ba88b; border-top: 1px solid #e8ece8; }}
                .social {{ margin-top: 15px; }}
                .social a {{ color: #2d8c3c; text-decoration: none; margin: 0 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="icon">{icon}</div>
                    <h1>Welcome to {APP_NAME}!</h1>
                    <p>{title}</p>
                </div>
                <div class="content">
                    <div class="greeting">Hello, {display_name}! 🎉</div>
                    <div class="message">{welcome_message}</div>
                    <div class="features">
                        <h3>✨ What you can do:</h3>
                        <ul>
                            {''.join(f'<li>{feature}</li>' for feature in features)}
                        </ul>
                    </div>
                    <div style="text-align: center;">
                        <a href="{cta_link}" class="cta-button">{cta_text} →</a>
                    </div>
                    <p style="font-size: 13px; color: #6b8c6b; text-align: center; margin-top: 20px;">
                        Need help? Contact us at <a href="mailto:support@{APP_NAME.lower()}.app" style="color: #2d8c3c;">support@{APP_NAME.lower()}.app</a>
                    </p>
                </div>
                <div class="footer">
                    <p><strong>{APP_NAME}</strong> - GPS Based Vendor Discovery App</p>
                    <p>📍 Tiaong, Quezon | 🍢 Made with love for local food lovers</p>
                    <div class="social">
                        <a href="#">📱 Download App</a> | <a href="#">💬 Support</a> | <a href="#">📧 Contact</a>
                    </div>
                    <p style="margin-top: 15px;">© 2024 {APP_NAME}. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return self.send_email(email, f"🎉 Welcome to {APP_NAME}, {display_name}!", html)
    
    def send_welcome_sms(self, phone, name, role='customer', business_name=None):
        """Send dynamic welcome SMS based on role - uses local 09 format"""
        if not phone:
            return True
        
        if role == 'admin':
            message = f"""🎉 Welcome to {APP_NAME} Admin Panel, {name}!

You now have full administrative access to manage users, vendors, and platform analytics.

📊 Admin Dashboard: {BASE_URL}/admin

{APP_NAME} - Platform Administrator"""
            
        elif role == 'customer':
            message = f"""🎉 Welcome to {APP_NAME}, {name}! 🍢

Start exploring street food vendors near you in Tiaong, Quezon!

✨ What you can do:
• Find vendors near you
• Browse menus
• Save favorites
• Get directions

📍 Download the app: {BASE_URL}/customer

{APP_NAME} - Find the best street food in Tiaong!"""
            
        else:  # vendor
            display_name = business_name or name
            message = f"""🎉 Welcome to {APP_NAME}, {display_name}! 🏪

Your business is now live on {APP_NAME}!

✨ What you can do:
• Add your menu items with photos
• Set your operating hours
• Track customer analytics
• Create posts to engage customers

📊 Vendor Dashboard: {BASE_URL}/vendor

{APP_NAME} - Grow your food business in Tiaong!"""
        
        return self.send_sms(phone, message)
    
    # ============================================
    # PASSWORD RESET
    # ============================================
    
    def send_password_reset_email(self, email, reset_token, name=None):
        """Send password reset email"""
        display_name = name or "User"
        reset_link = f"{BASE_URL}/reset-password?token={reset_token}"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Password Reset - {APP_NAME}</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                .container {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 20px; overflow: hidden; }}
                .header {{ background: linear-gradient(135deg, #2d8c3c, #1a6b28); padding: 30px; text-align: center; }}
                .header h1 {{ color: white; margin: 0; }}
                .content {{ padding: 30px; }}
                .button {{ display: inline-block; background: #2d8c3c; color: white; text-decoration: none; padding: 12px 30px; border-radius: 30px; margin: 20px 0; }}
                .warning {{ background: #fff3e0; padding: 15px; border-radius: 12px; font-size: 13px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 {APP_NAME}</h1>
                    <p style="color: rgba(255,255,255,0.9);">Password Reset</p>
                </div>
                <div class="content">
                    <p>Hello {display_name},</p>
                    <p>We received a request to reset your {APP_NAME} account password.</p>
                    <div style="text-align: center;">
                        <a href="{reset_link}" class="button">Reset Password</a>
                    </div>
                    <p>This link will expire in <strong>1 hour</strong>.</p>
                    <div class="warning">
                        ⚠️ If you didn't request a password reset, please ignore this email or contact support.
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return self.send_email(email, f"🔐 Reset Your {APP_NAME} Password", html)
    
    def send_password_reset_sms(self, phone, reset_token):
        """Send password reset SMS with link - uses local 09 format"""
        reset_link = f"{BASE_URL}/reset-password?token={reset_token}"
        message = f"""🔐 {APP_NAME} Password Reset

We received a request to reset your password.

Click this link to reset your password:
{reset_link}

⏰ This link expires in 1 hour.

If you didn't request this, please ignore this message.

{APP_NAME} - Security Notice"""
        return self.send_sms(phone, message)
    
    # ============================================
    # ORDER/PURCHASE NOTIFICATIONS (For future use)
    # ============================================
    
    def send_order_confirmation_email(self, email, order_details, customer_name):
        """Send order confirmation email"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Order Confirmation - {APP_NAME}</title>
        </head>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #2d8c3c, #1a6b28); padding: 20px; text-align: center;">
                    <h1 style="color: white;">✅ Order Confirmed!</h1>
                </div>
                <div style="padding: 30px;">
                    <h2>Hello {customer_name},</h2>
                    <p>Your order has been confirmed!</p>
                    <div style="background: #f5faf5; padding: 20px; border-radius: 12px;">
                        <strong>Order Details:</strong>
                        <pre style="margin-top: 10px;">{order_details}</pre>
                    </div>
                    <p>Thank you for ordering through {APP_NAME}!</p>
                </div>
            </div>
        </body>
        </html>
        """
        return self.send_email(email, f"✅ Order Confirmed - {APP_NAME}", html)
    
    def send_order_notification_sms(self, phone, order_summary, customer_name):
        """Send order notification SMS to vendor - uses local 09 format"""
        message = f"""🛒 New Order from {customer_name}!

Order Summary: {order_summary}

Log in to your {APP_NAME} vendor dashboard to manage this order.

{APP_NAME} Vendor Portal: {BASE_URL}/vendor"""
        return self.send_sms(phone, message)
    
    # ============================================
    # PROMOTIONAL / BULK MESSAGES
    # ============================================
    
    def send_promotional_email(self, email, name, title, message_content, cta_text, cta_link):
        """Send promotional email to users"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{title} - {APP_NAME}</title>
        </head>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #2d8c3c, #1a6b28); padding: 30px; text-align: center;">
                    <h1 style="color: white;">{APP_NAME}</h1>
                </div>
                <div style="padding: 30px;">
                    <h2>Hello {name}!</h2>
                    <p>{message_content}</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{cta_link}" style="background: #2d8c3c; color: white; padding: 12px 30px; text-decoration: none; border-radius: 30px;">{cta_text}</a>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return self.send_email(email, f"📢 {title}", html)
    
    def send_promotional_sms(self, phone, name, message_content):
        """Send promotional SMS to users - uses local 09 format"""
        message = f"""📢 Hey {name}!

{message_content}

{APP_NAME} - {BASE_URL}"""
        return self.send_sms(phone, message)
    
    # ============================================
    # ACCOUNT NOTIFICATIONS
    # ============================================
    
    def send_account_suspended_email(self, email, name, reason=None):
        """Notify user that their account has been suspended"""
        reason_text = reason or "violation of our terms of service"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Account Suspended - {APP_NAME}</title>
        </head>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: #e53935; padding: 20px; text-align: center;">
                    <h1 style="color: white;">⚠️ Account Suspended</h1>
                </div>
                <div style="padding: 30px;">
                    <h2>Hello {name},</h2>
                    <p>Your {APP_NAME} account has been suspended due to {reason_text}.</p>
                    <p>If you believe this is a mistake, please contact our support team.</p>
                    <p>Email: <a href="mailto:support@{APP_NAME.lower()}.app">support@{APP_NAME.lower()}.app</a></p>
                </div>
            </div>
        </body>
        </html>
        """
        return self.send_email(email, f"⚠️ Your {APP_NAME} Account Has Been Suspended", html)
    
    def send_account_suspended_sms(self, phone, name):
        """Notify user via SMS about suspension - uses local 09 format"""
        message = f"""⚠️ {APP_NAME} Account Alert

Hello {name}, your account has been suspended due to a policy violation.

Please contact support for more information: support@{APP_NAME.lower()}.app

{APP_NAME} Team"""
        return self.send_sms(phone, message)

# Initialize notification service
notifications = NotificationService()

def create_session(user_id, role):
    session_token = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    session_data = {
        'id': str(uuid.uuid4()),
        'session_token': session_token,
        'user_id': user_id,
        'role': role,
        'created_at': utc_now(),
        'expires_at': expires_at.isoformat(),
        'last_activity': utc_now()
    }
    
    try:
        supabase.table('user_sessions').insert(session_data).execute()
        return session_token
    except Exception as e:
        print(f"Create session error: {e}")
        return None

def get_session(session_token):
    if not session_token:
        return None
    try:
        result = supabase.table('user_sessions').select('*').eq('session_token', session_token).execute()
        if result.data:
            session = result.data[0]
            expiry = datetime.fromisoformat(session['expires_at'].replace('Z', '+00:00'))
            if expiry < datetime.now(timezone.utc):
                supabase.table('user_sessions').delete().eq('session_token', session_token).execute()
                return None
            supabase.table('user_sessions').update({'last_activity': utc_now()}).eq('session_token', session_token).execute()
            return session
        return None
    except:
        return None

def delete_session(session_token):
    try:
        supabase.table('user_sessions').delete().eq('session_token', session_token).execute()
        return True
    except:
        return False

def require_session():
    session_token = request.headers.get('X-Session-Token')
    if not session_token:
        return None
    session = get_session(session_token)
    if not session:
        return None
    return {'user_id': session['user_id'], 'role': session['role']}



def get_admin_stats():
    stats = {'total_users': 0, 'total_vendors': 0, 'total_products': 0, 'total_reviews': 0, 'total_posts': 0, 'user_growth': [10, 25, 45, 70, 100, 150]}
    try:
        stats['total_users'] = supabase.table('users').select('*', count='exact').execute().count or 0
        stats['total_vendors'] = supabase.table('vendors').select('*', count='exact').execute().count or 0
        stats['total_products'] = supabase.table('products').select('*', count='exact').eq('is_active', True).execute().count or 0
        stats['total_reviews'] = supabase.table('reviews').select('*', count='exact').execute().count or 0
        stats['total_posts'] = supabase.table('posts').select('*', count='exact').execute().count or 0
    except:
        pass
    return stats

def get_all_users_admin():
    try:
        return supabase.table('users').select('*').order('created_at', desc=True).execute().data or []
    except:
        return []

def get_all_vendors_admin():
    try:
        return supabase.table('vendors').select('*').order('created_at', desc=True).execute().data or []
    except:
        return []

def suspend_user(user_id):
    try:
        supabase.table('users').update({'is_suspended': True}).eq('id', user_id).execute()
        return True
    except:
        return False

def unsuspend_user(user_id):
    try:
        supabase.table('users').update({'is_suspended': False}).eq('id', user_id).execute()
        return True
    except:
        return False

def toggle_vendor_active(vendor_id, is_active):
    try:
        supabase.table('vendors').update({'is_active': is_active}).eq('id', vendor_id).execute()
        return True
    except:
        return False

def save_profile_photo(user_id, base64_image):
    """Save profile photo to Supabase storage"""
    try:
        # Extract base64 data
        if ',' in base64_image:
            base64_image = base64_image.split(',')[1]
        
        # Decode base64 to bytes
        image_bytes = base64.b64decode(base64_image)
        
        # Upload to Supabase storage
        file_path = f"profile_photos/{user_id}.jpg"
        supabase.storage.from_("user_photos").upload(file_path, image_bytes, {"content-type": "image/jpeg"})
        
        # Get public URL
        public_url = supabase.storage.from_("user_photos").get_public_url(file_path)
        
        # Update user record with photo URL
        supabase.table('users').update({'profile_photo_url': public_url}).eq('id', user_id).execute()
        
        return public_url
    except Exception as e:
        print(f"Save profile photo error: {e}")
        return None

def save_vendor_logo(vendor_id, base64_image):
    """Save vendor logo to Supabase storage"""
    try:
        if ',' in base64_image:
            base64_image = base64_image.split(',')[1]
        
        image_bytes = base64.b64decode(base64_image)
        
        file_path = f"vendor_logos/{vendor_id}.jpg"
        supabase.storage.from_("vendor_photos").upload(file_path, image_bytes, {"content-type": "image/jpeg"})
        
        public_url = supabase.storage.from_("vendor_photos").get_public_url(file_path)
        
        supabase.table('vendors').update({'logo_url': public_url}).eq('id', vendor_id).execute()
        
        return public_url
    except Exception as e:
        print(f"Save vendor logo error: {e}")
        return None


def set_otp(email, otp, expiry):
    try:
        supabase.table('users').update({'otp_code': otp, 'otp_expiry': expiry}).eq('email', email).execute()
    except:
        pass

def verify_otp(email, otp):
    try:
        user = get_user_by_email(email)
        if not user: return False, "User not found"
        if user.get('email_verified'): return True, "Already verified"
        if user.get('otp_code') != otp: return False, "Invalid OTP"
        expiry = user.get('otp_expiry')
        if expiry and datetime.fromisoformat(expiry.replace('Z', '+00:00')) < datetime.now(timezone.utc):
            return False, "OTP expired"
        supabase.table('users').update({'email_verified': True, 'otp_code': None, 'otp_expiry': None}).eq('email', email).execute()
        return True, "Verified"
    except:
        return False, "Error"

# ============================================
# DATABASE FUNCTIONS
# ============================================

def get_user_by_email(email):
    try:
        result = supabase.table('users').select('*').eq('email', email).execute()
        return result.data[0] if result.data else None
    except:
        return None

def get_user_by_id(user_id):
    try:
        result = supabase.table('users').select('*').eq('id', user_id).execute()
        return result.data[0] if result.data else None
    except:
        return None

def create_user(email, password, role, full_name=None, phone=None, auto_generated=False, profile_photo=None):
    user_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user_data = {
        'id': user_id, 
        'email': email, 
        'password': hashed, 
        'role': role,
        'full_name': full_name, 
        'phone': phone, 
        'profile_photo': profile_photo,  # Add this
        'email_verified': auto_generated,
        'phone_verified': False,
        'is_suspended': False, 
        'created_at': utc_now(), 
        'updated_at': utc_now()
    }
    try:
        supabase.table('users').insert(user_data).execute()
        return user_id
    except Exception as e:
        print(f"Create user error: {e}")
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
        return vendor_id
    except:
        return None

def get_vendor_by_user_id(user_id):
    try:
        result = supabase.table('vendors').select('*').eq('user_id', user_id).execute()
        return result.data[0] if result.data else None
    except:
        return None

def get_vendor_by_id(vendor_id):
    try:
        result = supabase.table('vendors').select('*').eq('id', vendor_id).execute()
        return result.data[0] if result.data else None
    except:
        return None

def get_all_vendors():
    try:
        result = supabase.table('vendors').select('*').eq('is_active', True).execute()
        return result.data or []
    except:
        return []

def get_vendors_nearby(lat, lng, radius_km=50):
    try:
        result = supabase.table('vendors').select('*').eq('is_active', True).execute()
        vendors = []
        for v in (result.data or []):
            if v.get('latitude') and v.get('longitude'):
                distance = math.sqrt((float(v['latitude']) - lat)**2 + (float(v['longitude']) - lng)**2) * 111
                v['distance'] = round(distance, 2)
                vendors.append(v)
            else:
                v['distance'] = 999
                vendors.append(v)
        vendors.sort(key=lambda x: x.get('distance', 999))
        return vendors
    except:
        return []

def get_products_by_vendor(vendor_id):
    """Get active products by vendor (exclude deleted)"""
    try:
        result = supabase.table('products').select('*').eq('vendor_id', vendor_id).eq('is_active', True).execute()
        return result.data or []
    except:
        return []

def create_product(vendor_id, name, description, category, price, images=None, stock=0):
    product_id = str(uuid.uuid4())
    
    processed_images = []
    if images:
        for img in images:
            try:
                if ',' in img:
                    img = img.split(',')[1]
                image_bytes = base64.b64decode(img)
                pil_img = Image.open(io.BytesIO(image_bytes))
                if pil_img.mode in ('RGBA', 'P'):
                    rgb_img = Image.new('RGB', pil_img.size, (255, 255, 255))
                    rgb_img.paste(pil_img, mask=pil_img.split()[-1] if pil_img.mode == 'RGBA' else None)
                    pil_img = rgb_img
                pil_img.thumbnail((400, 400))
                buffer = io.BytesIO()
                pil_img.save(buffer, format='JPEG', quality=85)
                processed = f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode()}"
                processed_images.append({'original': processed, 'thumbnail': processed})
            except Exception as e:
                print(f"Image processing error: {e}")
    
    product_data = {
        'id': product_id,
        'vendor_id': vendor_id,
        'name': name,
        'description': description,
        'category': category,
        'price': float(price),
        'stock': int(stock),  # Default to 0, hidden from UI
        'images': processed_images,
        'is_active': True,
        'created_at': utc_now(),
        'updated_at': utc_now()
    }
    
    try:
        supabase.table('products').insert(product_data).execute()
        return product_id
    except Exception as e:
        print(f"create_product error: {e}")
        return None
    
# ============================================
# COMPLETE PRODUCT UPDATE AND DELETE FUNCTIONS
# ============================================

def update_product(product_id, product_data):
    """Update existing product"""
    try:
        # Process new images if provided
        processed_images = None
        if product_data.get('images'):
            processed_images = []
            for img in product_data['images']:
                try:
                    if ',' in img:
                        img = img.split(',')[1]
                    image_bytes = base64.b64decode(img)
                    pil_img = Image.open(io.BytesIO(image_bytes))
                    if pil_img.mode in ('RGBA', 'P'):
                        rgb_img = Image.new('RGB', pil_img.size, (255, 255, 255))
                        rgb_img.paste(pil_img, mask=pil_img.split()[-1] if pil_img.mode == 'RGBA' else None)
                        pil_img = rgb_img
                    pil_img.thumbnail((400, 400))
                    buffer = io.BytesIO()
                    pil_img.save(buffer, format='JPEG', quality=85)
                    processed = f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode()}"
                    processed_images.append({'original': processed, 'thumbnail': processed})
                except Exception as e:
                    print(f"Image processing error: {e}")
        
        # Build update data
        update_data = {
            'name': product_data.get('name'),
            'description': product_data.get('description'),
            'category': product_data.get('category'),
            'price': float(product_data.get('price')),
            'stock': int(product_data.get('stock', 0)),
            'updated_at': utc_now()
        }
        
        if processed_images:
            update_data['images'] = processed_images
        
        # Remove None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        supabase.table('products').update(update_data).eq('id', product_id).execute()
        return True
    except Exception as e:
        print(f"Update product error: {e}")
        return False

def delete_product(product_id):
    """Soft delete product (set is_active to False)"""
    try:
        supabase.table('products').update({'is_active': False, 'updated_at': utc_now()}).eq('id', product_id).execute()
        return True
    except Exception as e:
        print(f"Delete product error: {e}")
        return False

def hard_delete_product(product_id):
    """Permanently delete product from database"""
    try:
        supabase.table('products').delete().eq('id', product_id).execute()
        return True
    except Exception as e:
        print(f"Hard delete product error: {e}")
        return False   

def create_post(user_id, user_role, content, images=None):
    post_id = str(uuid.uuid4())
    
    processed_images = []
    if images:
        for img in images:
            try:
                if ',' in img:
                    img = img.split(',')[1]
                image_bytes = base64.b64decode(img)
                pil_img = Image.open(io.BytesIO(image_bytes))
                if pil_img.mode in ('RGBA', 'P'):
                    rgb_img = Image.new('RGB', pil_img.size, (255, 255, 255))
                    rgb_img.paste(pil_img, mask=pil_img.split()[-1] if pil_img.mode == 'RGBA' else None)
                    pil_img = rgb_img
                pil_img.thumbnail((400, 400))
                buffer = io.BytesIO()
                pil_img.save(buffer, format='JPEG', quality=85)
                processed = f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode()}"
                processed_images.append({'original': processed, 'thumbnail': processed})
            except:
                pass
    
    post_data = {
        'id': post_id,
        'user_id': user_id,
        'user_role': user_role,
        'parent_id': None,
        'content': content,
        'images': processed_images,
        'likes': 0,
        'comment_count': 0,
        'created_at': utc_now()
    }
    try:
        supabase.table('posts').insert(post_data).execute()
        return post_id
    except Exception as e:
        print(f"create_post error: {e}")
        return None

def get_feed_posts(limit=30):
    try:
        result = supabase.table('posts').select('*, users(full_name)').is_('parent_id', 'null').order('created_at', desc=True).limit(limit).execute()
        posts = []
        for p in (result.data or []):
            p['author'] = p.get('users', {}).get('full_name', 'User') if p.get('users') else 'User'
            posts.append(p)
        return posts
    except:
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
    except:
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
        reviews = supabase.table('reviews').select('rating').eq('vendor_id', vendor_id).execute()
        if reviews.data:
            avg = sum(r['rating'] for r in reviews.data) / len(reviews.data)
            supabase.table('vendors').update({'rating': round(avg, 1), 'review_count': len(reviews.data)}).eq('id', vendor_id).execute()
        return review_id
    except:
        return None

def get_reviews_by_vendor(vendor_id):
    try:
        result = supabase.table('reviews').select('*, users(full_name)').eq('vendor_id', vendor_id).eq('is_hidden', False).order('created_at', desc=True).execute()
        for r in result.data:
            r['customer_name'] = r.get('users', {}).get('full_name', 'Customer') if r.get('users') else 'Customer'
        return result.data or []
    except:
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
    except:
        return False

def remove_from_shortlist(user_id, vendor_id):
    try:
        supabase.table('shortlists').delete().eq('user_id', user_id).eq('vendor_id', vendor_id).execute()
        return True
    except:
        return False

def get_shortlist(user_id):
    try:
        result = supabase.table('shortlists').select('vendor_id').eq('user_id', user_id).execute()
        vendors = []
        for item in result.data:
            v = get_vendor_by_id(item['vendor_id'])
            if v:
                vendors.append(v)
        return vendors
    except:
        return []

def update_vendor_hours(vendor_id, hours):
    try:
        supabase.table('vendors').update({'operating_hours': hours}).eq('id', vendor_id).execute()
        return True
    except:
        return False

def update_vendor_location(vendor_id, lat, lng):
    try:
        supabase.table('vendors').update({'latitude': lat, 'longitude': lng}).eq('id', vendor_id).execute()
        return True
    except:
        return False

def get_admin_stats():
    stats = {'total_users': 0, 'total_vendors': 0, 'total_products': 0, 'total_reviews': 0, 'total_posts': 0}
    try:
        stats['total_users'] = supabase.table('users').select('*', count='exact').execute().count or 0
        stats['total_vendors'] = supabase.table('vendors').select('*', count='exact').execute().count or 0
        stats['total_products'] = supabase.table('products').select('*', count='exact').eq('is_active', True).execute().count or 0
        stats['total_reviews'] = supabase.table('reviews').select('*', count='exact').execute().count or 0
        stats['total_posts'] = supabase.table('posts').select('*', count='exact').execute().count or 0
    except:
        pass
    return stats

def get_all_users_admin():
    try:
        return supabase.table('users').select('*').order('created_at', desc=True).execute().data or []
    except:
        return []

def suspend_user(user_id):
    try:
        supabase.table('users').update({'is_suspended': True}).eq('id', user_id).execute()
        return True
    except:
        return False

def unsuspend_user(user_id):
    try:
        supabase.table('users').update({'is_suspended': False}).eq('id', user_id).execute()
        return True
    except:
        return False

def toggle_vendor_active(vendor_id, is_active):
    try:
        supabase.table('vendors').update({'is_active': is_active}).eq('id', vendor_id).execute()
        return True
    except:
        return False

def get_all_vendors_admin():
    try:
        return supabase.table('vendors').select('*').order('created_at', desc=True).execute().data or []
    except:
        return []

# ============================================
# MISSING DB HELPER FUNCTIONS
# ============================================

def get_user_by_phone(phone):
    try:
        result = supabase.table('users').select('*').eq('phone', phone).execute()
        return result.data[0] if result.data else None
    except:
        return None

def verify_password(email, password):
    user = get_user_by_email(email)
    if user and bcrypt.checkpw(password.encode(), user['password'].encode()):
        return user
    return None

def get_vendor_by_user_id(user_id):
    try:
        result = supabase.table('vendors').select('*').eq('user_id', user_id).execute()
        return result.data[0] if result.data else None
    except:
        return None

def get_all_vendors():
    try:
        result = supabase.table('vendors').select('*').eq('is_active', True).execute()
        return result.data or []
    except:
        return []

def update_vendor_hours(vendor_id, hours):
    try:
        supabase.table('vendors').update({'operating_hours': hours}).eq('id', vendor_id).execute()
        return True
    except:
        return False

def update_vendor_location(vendor_id, lat, lng):
    try:
        supabase.table('vendors').update({'latitude': lat, 'longitude': lng}).eq('id', vendor_id).execute()
        return True
    except:
        return False

def get_admin_stats():
    stats = {'total_users': 0, 'total_vendors': 0, 'total_products': 0, 'total_reviews': 0, 'total_posts': 0}
    try:
        stats['total_users'] = supabase.table('users').select('*', count='exact').execute().count or 0
        stats['total_vendors'] = supabase.table('vendors').select('*', count='exact').execute().count or 0
        stats['total_products'] = supabase.table('products').select('*', count='exact').eq('is_active', True).execute().count or 0
        stats['total_reviews'] = supabase.table('reviews').select('*', count='exact').execute().count or 0
        stats['total_posts'] = supabase.table('posts').select('*', count='exact').execute().count or 0
    except:
        pass
    return stats

def get_all_users_admin():
    try:
        return supabase.table('users').select('*').order('created_at', desc=True).execute().data or []
    except:
        return []

def suspend_user(user_id):
    try:
        supabase.table('users').update({'is_suspended': True}).eq('id', user_id).execute()
        return True
    except:
        return False

def unsuspend_user(user_id):
    try:
        supabase.table('users').update({'is_suspended': False}).eq('id', user_id).execute()
        return True
    except:
        return False

def toggle_vendor_active(vendor_id, is_active):
    try:
        supabase.table('vendors').update({'is_active': is_active}).eq('id', vendor_id).execute()
        return True
    except:
        return False

def get_all_vendors_admin():
    try:
        return supabase.table('vendors').select('*').order('created_at', desc=True).execute().data or []
    except:
        return []

def hard_delete_product(product_id):
    """Permanently delete product from database"""
    try:
        supabase.table('products').delete().eq('id', product_id).execute()
        return True
    except:
        return False
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

CATEGORIES = [
    "Coffee", "Pancit", "Tusok Tusok", "Contemporary Street food",
    "Bread and Pastry", "Lomi", "Beverage", "Sarisari Store", "Karendirya",
    "Traditional Desserts", "Contemporary Desserts", "Squidball", "Siomai", "Siopao",
    "Taho", "Balut and other poultry", "Corn", "Fruit shakes", "Fruit Juice"
]

PREMADE_AVATARS = [
    {'id': 1, 'icon': 'user', 'color': '#FF6B6B'},
    {'id': 2, 'icon': 'user', 'color': '#4ECDC4'},
    {'id': 3, 'icon': 'user', 'color': '#FFE66D'},
    {'id': 4, 'icon': 'user', 'color': '#A8E6CF'},
    {'id': 5, 'icon': 'user', 'color': '#FF8B94'},
    {'id': 6, 'icon': 'user', 'color': '#B8E1FF'},
    {'id': 7, 'icon': 'user', 'color': '#FF9F1C'},
    {'id': 8, 'icon': 'user', 'color': '#FFC6FF'},
]

# ============================================
# RENDER PAGE FUNCTION
# ============================================

def render_page(title, content):
    return f'''<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
    <meta name="theme-color" content="#2d8c3c">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
    <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f5faf5; min-height: 100vh; }}
        .app-bar {{ background: #ffffff; padding: 12px 20px; display: flex; align-items: center; border-bottom: 0.5px solid rgba(0, 0, 0, 0.05); position: sticky; top: 0; z-index: 100; }}
        .app-bar-title {{ flex: 1; text-align: center; font-weight: 600; font-size: 18px; color: #1a2e1a; }}
        .back-btn, .menu-btn {{ background: transparent; border: none; padding: 10px; border-radius: 30px; font-size: 18px; color: #2d8c3c; cursor: pointer; min-width: 44px; min-height: 44px; }}
        .back-btn:active, .menu-btn:active {{ background: rgba(45, 140, 60, 0.1); }}
        .content {{ padding: 16px; max-width: 600px; margin: 0 auto; padding-bottom: 80px; }}
        .card {{ background: #ffffff; border-radius: 20px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03); border: 0.5px solid rgba(0, 0, 0, 0.03); cursor: pointer; transition: all 0.2s; }}
        .card:active {{ background: #f8faf8; }}
        .btn {{ background: #2d8c3c; color: white; border: none; padding: 14px 20px; border-radius: 40px; font-weight: 600; font-size: 15px; width: 100%; cursor: pointer; }}
        .btn:active {{ opacity: 0.85; transform: scale(0.97); }}
        .btn-outline {{ background: transparent; border: 1.5px solid #2d8c3c; color: #2d8c3c; }}
        .btn-sm {{ padding: 8px 16px; font-size: 13px; width: auto; }}
        .input {{ width: 100%; padding: 14px 16px; background: #f8faf8; border: 1px solid rgba(0, 0, 0, 0.08); border-radius: 14px; font-size: 16px; margin-bottom: 12px; }}
        .input:focus {{ outline: none; border-color: #2d8c3c; background: white; }}
        .search-bar {{ background: white; border-radius: 30px; padding: 12px 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03); border: 0.5px solid rgba(0, 0, 0, 0.03); display: flex; align-items: center; gap: 12px; }}
        .search-bar i {{ color: #8ba88b; font-size: 18px; }}
        .search-bar input {{ flex: 1; border: none; background: transparent; font-size: 16px; outline: none; }}
        .filter-chips {{ display: flex; gap: 8px; overflow-x: auto; padding: 8px 0 16px; margin-bottom: 8px; -webkit-overflow-scrolling: touch; }}
        .chip {{ padding: 8px 18px; background: #f0f4f0; border-radius: 40px; font-size: 14px; white-space: nowrap; cursor: pointer; transition: all 0.2s; }}
        .chip.active {{ background: #2d8c3c; color: white; }}
        .bottom-nav {{ position: fixed; bottom: 0; left: 0; right: 0; background: rgba(255, 255, 255, 0.98); backdrop-filter: blur(20px); display: flex; justify-content: space-around; padding: 8px 16px 20px; border-top: 0.5px solid rgba(0, 0, 0, 0.05); max-width: 600px; margin: 0 auto; z-index: 99; }}
        .nav-item {{ text-align: center; padding: 8px 12px; cursor: pointer; color: #8ba88b; border-radius: 30px; transition: all 0.2s; }}
        .nav-item.active {{ color: #2d8c3c; background: rgba(45, 140, 60, 0.08); }}
        .nav-item i {{ font-size: 22px; }}
        .nav-item span {{ font-size: 11px; display: block; margin-top: 2px; }}
        .map-wrapper {{ position: relative; border-radius: 24px; overflow: hidden; margin-bottom: 16px; box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08); }}
        .map-container {{ height: 420px; width: 100%; position: relative; }}
        #map, #vendorMap {{ height: 100%; width: 100%; background: #e8ece8; }}
        .map-controls {{ position: absolute; bottom: 16px; right: 16px; display: flex; flex-direction: column; gap: 8px; z-index: 400; }}
        .map-control-btn {{ width: 48px; height: 48px; background: white; border: none; border-radius: 28px; box-shadow: 0 2px 12px rgba(0, 0, 0, 0.12); cursor: pointer; font-size: 20px; color: #2d8c3c; transition: all 0.2s; }}
        .map-control-btn:active {{ transform: scale(0.95); background: #f0f4f0; }}
        .modal {{ display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0, 0, 0, 0.5); backdrop-filter: blur(8px); z-index: 1000; align-items: flex-end; }}
        .modal.show {{ display: flex; }}
        .modal-content {{ background: white; border-radius: 28px 28px 0 0; padding: 24px; max-height: 85vh; overflow-y: auto; width: 100%; animation: slideUp 0.3s ease; }}
        @keyframes slideUp {{ from {{ transform: translateY(100%); }} to {{ transform: translateY(0); }} }}
        .modal-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 0.5px solid #e0e6e0; }}
        .modal-close {{ font-size: 28px; cursor: pointer; color: #999; line-height: 1; padding: 8px; border-radius: 28px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 16px; }}
        .stat-card {{ background: linear-gradient(135deg, #2d8c3c, #1a6b28); border-radius: 20px; padding: 20px; text-align: center; color: white; }}
        .stat-value {{ font-size: 28px; font-weight: 700; }}
        .stat-label {{ font-size: 12px; opacity: 0.9; margin-top: 4px; }}
        .image-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 12px; }}
        .image-thumb {{ aspect-ratio: 1; border-radius: 14px; overflow: hidden; background: #f0f4f0; }}
        .image-thumb img {{ width: 100%; height: 100%; object-fit: cover; }}
        .product-card {{ background: white; border-radius: 20px; padding: 16px; margin-bottom: 12px; border: 0.5px solid rgba(0, 0, 0, 0.05); }}
        .product-price {{ font-size: 18px; font-weight: 700; color: #2d8c3c; }}
        .product-stock {{ font-size: 12px; color: #6b8c6b; }}
        .menu-item {{ background: white; border-radius: 16px; padding: 12px; margin-bottom: 10px; display: flex; gap: 12px; border: 0.5px solid rgba(0, 0, 0, 0.05); }}
        .menu-item-image {{ width: 60px; height: 60px; border-radius: 12px; overflow: hidden; background: #f0f4f0; display: flex; align-items: center; justify-content: center; }}
        .menu-item-image img {{ width: 100%; height: 100%; object-fit: cover; }}
        .menu-item-info {{ flex: 1; }}
        .menu-item-name {{ font-weight: 600; }}
        .menu-item-price {{ color: #2d8c3c; font-weight: 700; margin-top: 4px; }}
        .avatar {{ width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 24px; background: linear-gradient(135deg, #2d8c3c, #1a6b28); color: white; }}
        .flex {{ display: flex; }}
        .justify-between {{ justify-content: space-between; }}
        .items-center {{ align-items: center; }}
        .gap-2 {{ gap: 8px; }}
        .mt-2 {{ margin-top: 8px; }}
        .mt-4 {{ margin-top: 16px; }}
        .text-center {{ text-align: center; }}
        .text-secondary {{ color: #6b8c6b; font-size: 13px; }}
        .stars {{ color: #fbbf24; letter-spacing: 2px; }}
        .vendor-status {{ display: inline-block; padding: 4px 12px; border-radius: 30px; font-size: 11px; font-weight: 600; }}
        .vendor-status.open {{ background: #10b98115; color: #10b981; }}
        .vendor-status.closed {{ background: #ef444415; color: #ef4444; }}
        .badge {{ display: inline-block; padding: 4px 12px; background: #2d8c3c; color: white; border-radius: 30px; font-size: 11px; font-weight: 500; }}
        .chart-container {{ background: white; border-radius: 20px; padding: 16px; margin-bottom: 16px; }}
        canvas {{ max-height: 200px; width: 100%; }}
        .hours-slider {{ display: flex; align-items: center; gap: 16px; margin: 16px 0; }}
        .hours-slider input {{ flex: 1; height: 4px; border-radius: 2px; background: #e0e6e0; -webkit-appearance: none; }}
        .hours-slider input::-webkit-slider-thumb {{ -webkit-appearance: none; width: 20px; height: 20px; border-radius: 50%; background: #2d8c3c; cursor: pointer; }}
        .hours-value {{ font-size: 14px; color: #2d8c3c; font-weight: 600; min-width: 60px; }}
        .hours-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 16px; }}
        .hours-item {{ display: flex; justify-content: space-between; padding: 12px; background: #f8faf8; border-radius: 14px; font-size: 13px; }}
        .avatar-select {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 20px 0; }}
        .avatar-option {{ aspect-ratio: 1; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 28px; cursor: pointer; border: 3px solid transparent; background: #f0f4f0; color: #2d8c3c; }}
        .avatar-option.selected {{ border-color: #2d8c3c; transform: scale(1.05); background: #2d8c3c; color: white; }}
        .otp-container {{ display: flex; gap: 12px; justify-content: center; margin: 24px 0; }}
        .otp-input {{ width: 52px; height: 60px; text-align: center; font-size: 28px; font-weight: 600; border-radius: 14px; border: 1.5px solid #e0e6e0; background: #f8faf8; }}
        .otp-input:focus {{ outline: none; border-color: #2d8c3c; }}
        .carousel-container {{ position: relative; height: 480px; margin: 20px 0; }}
        .carousel-cards {{ position: relative; height: 100%; }}
        .carousel-card {{ position: absolute; width: 100%; height: 100%; border-radius: 32px; padding: 36px 28px; transition: all 0.4s cubic-bezier(0.2, 0.9, 0.4, 1.1); cursor: pointer; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12); }}
        .carousel-card[data-position="0"] {{ transform: translateX(0) scale(1); opacity: 1; z-index: 3; }}
        .carousel-card[data-position="-1"] {{ transform: translateX(-75%) scale(0.9); opacity: 0.6; z-index: 2; }}
        .carousel-card[data-position="1"] {{ transform: translateX(75%) scale(0.9); opacity: 0.6; z-index: 2; }}
        .carousel-card:nth-child(1) {{ background: linear-gradient(135deg, #2d8c3c, #1a6b28); }}
        .carousel-card:nth-child(2) {{ background: linear-gradient(135deg, #FF6B6B, #ee5a24); }}
        .carousel-card:nth-child(3) {{ background: linear-gradient(135deg, #2193b0, #6dd5ed); }}
        .card-badge {{ display: inline-block; padding: 6px 16px; background: rgba(255, 255, 255, 0.2); border-radius: 40px; font-size: 13px; font-weight: 600; color: #fff; margin-bottom: 24px; }}
        .card-title {{ font-size: 44px; font-weight: 800; color: #fff; margin-bottom: 12px; letter-spacing: -0.5px; }}
        .card-subtitle {{ font-size: 15px; color: rgba(255, 255, 255, 0.9); margin-bottom: 32px; }}
        .feature-list {{ list-style: none; }}
        .feature-list li {{ display: flex; align-items: center; gap: 12px; padding: 10px 0; color: #fff; font-size: 14px; }}
        .feature-list li::before {{ content: "✓"; background: rgba(255, 255, 255, 0.2); width: 24px; height: 24px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; }}
        .carousel-indicators {{ display: flex; justify-content: center; gap: 8px; margin: 20px 0; }}
        .indicator {{ width: 8px; height: 8px; background: rgba(45, 140, 60, 0.3); border-radius: 4px; transition: all 0.3s; cursor: pointer; }}
        .indicator.active {{ width: 28px; background: #2d8c3c; }}
        .landing-container {{ min-height: 100vh; display: flex; flex-direction: column; justify-content: center; padding: 24px; background: linear-gradient(145deg, #e8f3e9 0%, #d4ecd6 100%); }}
        .hamburger-menu {{ position: fixed; top: 60px; right: 16px; background: white; border-radius: 20px; padding: 8px; box-shadow: 0 8px 28px rgba(0, 0, 0, 0.15); z-index: 200; display: none; }}
        .hamburger-menu.show {{ display: block; animation: fadeIn 0.2s ease; }}
        @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(-10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        .menu-item {{ padding: 12px 16px; border-radius: 14px; cursor: pointer; font-size: 14px; font-weight: 500; color: #1a2e1a; transition: all 0.2s; }}
        .menu-item:active {{ background: rgba(0, 0, 0, 0.05); }}
        .menu-divider {{ height: 1px; background: #e0e6e0; margin: 8px 0; }}
        .product-images-container {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
        .image-preview {{ position: relative; display: inline-block; }}
        .image-preview img {{ width: 80px; height: 80px; object-fit: cover; border-radius: 8px; }}
        .remove-img {{ position: absolute; top: -8px; right: -8px; background: red; color: white; border-radius: 50%; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 12px; }}
        .loading {{ text-align: center; padding: 40px; color: #8ba88b; }}
    </style>
</head>
<body>
{content}
</body>
</html>'''

# ============================================
# LANDING PAGE (Updated with modern GUI, no emojis)
# ============================================

# ============================================
# LANDING PAGE (Fixed - Proper Carousel, No Emojis)
# ============================================

LANDING = render_page("Lako", '''
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#f5faf5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
.landing-container{max-width:500px;margin:0 auto;padding:40px 24px;text-align:center;min-height:100vh;display:flex;flex-direction:column;justify-content:center}
.logo-wrapper{margin-bottom:40px}
.logo-title{font-size:56px;font-weight:800;background:linear-gradient(135deg,#2d8c3c,#4caf50,#1a6b28,#2d8c3c);background-size:300% 300%;-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:gradientShift 8s ease infinite;letter-spacing:4px;margin-bottom:16px;text-transform:uppercase}
@keyframes gradientShift{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
.logo-divider{width:60px;height:3px;background:linear-gradient(90deg,#2d8c3c,#4caf50,#1a6b28);margin:0 auto 16px;border-radius:3px}
.logo-tagline{background:linear-gradient(135deg,#2d8c3c,#4caf50);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-size:13px;font-weight:600;letter-spacing:2px;text-transform:uppercase}
.carousel-container{position:relative;overflow:hidden;border-radius:28px;margin:30px 0;box-shadow:0 10px 30px rgba(0,0,0,0.08)}
.carousel-track{display:flex;transition:transform 0.4s cubic-bezier(0.2,0.85,0.4,1);cursor:grab}
.carousel-track:active{cursor:grabbing}
.card{min-width:100%;padding:40px 28px;border-radius:28px;color:white}
.card-1{background:linear-gradient(135deg,#2d8c3c,#1a6b28)}
.card-2{background:linear-gradient(135deg,#2196f3,#1565c0)}
.card-3{background:linear-gradient(135deg,#ff9800,#e65100)}
.card-4{background:linear-gradient(135deg,#2d8c3c,#1a6b28)}
.card-badge{display:inline-block;padding:4px 14px;background:rgba(255,255,255,0.25);backdrop-filter:blur(4px);border-radius:30px;font-size:11px;font-weight:600;letter-spacing:1px;margin-bottom:16px}
.card-badge i{margin-right:6px}
.card-title{font-size:34px;font-weight:800;margin-bottom:8px;letter-spacing:-0.5px}
.card-subtitle{font-size:13px;margin-bottom:24px;opacity:0.9}
.feature-list{list-style:none;margin-bottom:28px;text-align:left}
.feature-list li{padding:10px 0;display:flex;align-items:center;gap:10px;font-size:13px}
.feature-list li i{width:20px;font-size:14px}
.btn{width:100%;padding:14px;background:white;color:#1a2e1a;border:none;border-radius:44px;font-size:15px;font-weight:700;cursor:pointer;transition:all 0.2s;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
.btn:active{transform:scale(0.97)}
.dots{display:flex;justify-content:center;gap:10px;margin-top:20px}
.dot{width:6px;height:6px;background:#d0d8d0;border-radius:50%;cursor:pointer;transition:all 0.3s ease}
.dot.active{width:28px;background:#2d8c3c;border-radius:6px}
.drag-hint{color:#8ba88b;font-size:10px;margin-top:16px;display:flex;align-items:center;justify-content:center;gap:10px;font-weight:500}
</style>

<div class="landing-container">
    <div class="logo-wrapper">
        <div class="logo-title">LAKO</div>
        <div class="logo-divider"></div>
        <div class="logo-tagline">Find Tiaong's Finest Street Foods</div>
    </div>
    
    <div class="carousel-container">
        <div class="carousel-track" id="carouselTrack">
            <div class="card card-1">
                <div class="card-badge"><i class="fas fa-user"></i> FOR FOOD LOVERS</div>
                <div class="card-title">Find Food</div>
                <div class="card-subtitle">Discover street food near you</div>
                <ul class="feature-list">
                    <li><i class="fas fa-map-marker-alt"></i> Real-time GPS vendor locations</li>
                    <li><i class="fas fa-utensils"></i> Browse menus with photos</li>
                    <li><i class="fas fa-heart"></i> Save your favorite vendors</li>
                    <li><i class="fas fa-directions"></i> Get turn-by-turn directions</li>
                </ul>
                <button class="btn" data-role="customer">Get Started <i class="fas fa-arrow-right"></i></button>
            </div>
            <div class="card card-2">
                <div class="card-badge"><i class="fas fa-store"></i> FOR BUSINESS OWNERS</div>
                <div class="card-title">Sell Food</div>
                <div class="card-subtitle">Grow your food business</div>
                <ul class="feature-list">
                    <li><i class="fas fa-edit"></i> Manage product catalog with photos</li>
                    <li><i class="fas fa-clock"></i> Set operating hours</li>
                    <li><i class="fas fa-chart-line"></i> Track customer traffic</li>
                    <li><i class="fas fa-chart-bar"></i> View analytics dashboard</li>
                </ul>
                <button class="btn" data-role="vendor">Get Started <i class="fas fa-arrow-right"></i></button>
            </div>
            <div class="card card-3">
                <div class="card-badge"><i class="fas fa-eye"></i> JUST LOOKING</div>
                <div class="card-title">Browse</div>
                <div class="card-subtitle">Explore without signing up</div>
                <ul class="feature-list">
                    <li><i class="fas fa-building"></i> View all nearby vendors</li>
                    <li><i class="fas fa-map-marked-alt"></i> See real-time locations</li>
                    <li><i class="fas fa-comments"></i> Read community reviews</li>
                    <li><i class="fas fa-compass"></i> Get directions to vendors</li>
                </ul>
                <button class="btn" data-role="guest">Browse Now <i class="fas fa-arrow-right"></i></button>
            </div>
            <!-- Duplicate for infinite loop -->
            <div class="card card-4">
                <div class="card-badge"><i class="fas fa-user"></i> FOR FOOD LOVERS</div>
                <div class="card-title">Find Food</div>
                <div class="card-subtitle">Discover street food near you</div>
                <ul class="feature-list">
                    <li><i class="fas fa-map-marker-alt"></i> Real-time GPS vendor locations</li>
                    <li><i class="fas fa-utensils"></i> Browse menus with photos</li>
                    <li><i class="fas fa-heart"></i> Save your favorite vendors</li>
                    <li><i class="fas fa-directions"></i> Get turn-by-turn directions</li>
                </ul>
                <button class="btn" data-role="customer">Get Started <i class="fas fa-arrow-right"></i></button>
            </div>
        </div>
    </div>
    
    <div class="drag-hint">
        <span><i class="fas fa-arrow-left"></i></span> Swipe to explore <span><i class="fas fa-arrow-right"></i></span>
    </div>
    <div class="dots" id="dots"></div>
</div>

<script>
let currentIndex = 0;
let startX = 0;
let isDragging = false;
let dragStartTime = 0;
const track = document.getElementById('carouselTrack');
const totalRealCards = 3;
const totalSlides = 4;

for(let i = 0; i < totalRealCards; i++) {
    let dot = document.createElement('div');
    dot.className = 'dot' + (i === 0 ? ' active' : '');
    dot.onclick = (function(idx) { return function() { goToSlide(idx); }; })(i);
    document.getElementById('dots').appendChild(dot);
}

function updateCarousel() {
    track.style.transform = 'translateX(-' + (currentIndex * 100) + '%)';
    let realIndex = currentIndex % totalRealCards;
    document.querySelectorAll('.dot').forEach((dot, i) => {
        dot.classList.toggle('active', i === realIndex);
    });
    
    if (currentIndex >= totalRealCards) {
        setTimeout(() => {
            track.style.transition = 'none';
            currentIndex = 0;
            track.style.transform = 'translateX(0%)';
            track.offsetHeight;
            track.style.transition = 'transform 0.4s cubic-bezier(0.2, 0.85, 0.4, 1)';
        }, 300);
    }
}

function goToSlide(index) {
    currentIndex = index;
    updateCarousel();
}

// Touch events
track.addEventListener('touchstart', (e) => {
    startX = e.touches[0].clientX;
    isDragging = true;
    dragStartTime = Date.now();
    track.style.transition = 'none';
});

track.addEventListener('touchmove', (e) => {
    if (!isDragging) return;
    let diff = e.touches[0].clientX - startX;
    let movePercent = (-currentIndex * 100) + (diff / track.offsetWidth * 100);
    track.style.transform = 'translateX(' + movePercent + '%)';
});

track.addEventListener('touchend', (e) => {
    if (!isDragging) return;
    isDragging = false;
    track.style.transition = 'transform 0.4s cubic-bezier(0.2, 0.85, 0.4, 1)';
    
    let endX = e.changedTouches[0].clientX;
    let diff = startX - endX;
    let dragTime = Date.now() - dragStartTime;
    
    if (Math.abs(diff) > 40 || dragTime < 150) {
        if (diff > 0 && currentIndex < totalSlides - 1) {
            currentIndex++;
        } else if (diff < 0 && currentIndex > 0) {
            currentIndex--;
        }
    }
    updateCarousel();
});

// Mouse events for desktop
track.addEventListener('mousedown', (e) => {
    e.preventDefault();
    startX = e.clientX;
    isDragging = true;
    track.style.transition = 'none';
    track.style.cursor = 'grabbing';
});

document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    let diff = e.clientX - startX;
    let movePercent = (-currentIndex * 100) + (diff / track.offsetWidth * 100);
    track.style.transform = 'translateX(' + movePercent + '%)';
});

document.addEventListener('mouseup', (e) => {
    if (!isDragging) return;
    isDragging = false;
    track.style.transition = 'transform 0.4s cubic-bezier(0.2, 0.85, 0.4, 1)';
    track.style.cursor = 'grab';
    
    let diff = startX - e.clientX;
    
    if (Math.abs(diff) > 40) {
        if (diff > 0 && currentIndex < totalSlides - 1) {
            currentIndex++;
        } else if (diff < 0 && currentIndex > 0) {
            currentIndex--;
        }
    }
    updateCarousel();
});

// Button clicks
document.querySelectorAll('.btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        let role = btn.getAttribute('data-role');
        localStorage.setItem('selected_role', role);
        window.location.href = role === 'guest' ? '/guest' : '/auth';
    });
});

track.style.cursor = 'grab';

// Add Font Awesome
let fa = document.createElement('link');
fa.rel = 'stylesheet';
fa.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css';
document.head.appendChild(fa);
</script>
''')

# ============================================
# AUTH PAGE (Login/Registration)
# ============================================

AUTH = render_page("Sign In - Lako GPS Vendor Discovery", r'''
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#f5faf5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}
.header{background:white;padding:16px;display:flex;gap:16px;border-bottom:1px solid #e8ece8;position:sticky;top:0;box-shadow:0 1px 3px rgba(0,0,0,0.05)}
.back-btn{background:#f0f4f0;border:none;width:40px;height:40px;border-radius:50%;cursor:pointer;font-size:18px;color:#2d8c3c}
.title{font-size:18px;font-weight:600;color:#1a2e1a;flex:1}
.title small{font-size:10px;color:#8ba88b;display:block;font-weight:normal}
.container{padding:20px;max-width:500px;margin:0 auto;min-height:calc(100vh - 140px)}
.card{background:white;border-radius:24px;padding:28px;margin-bottom:16px;box-shadow:0 2px 8px rgba(0,0,0,0.06)}
h2{font-size:26px;font-weight:700;color:#1a2e1a;margin-bottom:8px}
.subtitle{color:#6b8c6b;margin-bottom:24px;font-size:14px;line-height:1.4}
.input-group{margin-bottom:18px;position:relative}
.input-group input{width:100%;padding:14px 16px;border:1.5px solid #e0e8e0;border-radius:14px;font-size:16px;background:#f8faf8}
.input-group input:focus{outline:none;border-color:#2d8c3c;background:white}
.toggle-pwd{position:absolute;right:16px;top:50%;transform:translateY(-50%);cursor:pointer;color:#8ba88b;font-size:18px}
button{width:100%;padding:15px;background:#2d8c3c;color:white;border:none;border-radius:44px;font-size:16px;font-weight:600;cursor:pointer;margin-top:8px}
button:active{transform:scale(0.97);background:#1a6b28}
button.secondary{background:white;color:#2d8c3c;border:1.5px solid #e0e8e0}
.flex{display:flex;gap:12px;margin-top:16px}
.flex button{flex:1;margin-top:0}
.step-bars{display:flex;justify-content:center;gap:6px;margin-bottom:28px}
.bar{width:32px;height:4px;background:#e0e8e0;border-radius:4px}
.bar.active{background:#2d8c3c;width:48px}
.bar.completed{background:#2d8c3c}
.category-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:20px 0;max-height:300px;overflow-y:auto}
.category-chip{background:#f8faf8;border:1.5px solid #e0e8e0;border-radius:40px;padding:12px;text-align:center;cursor:pointer;font-size:14px;font-weight:500;color:#1a2e1a}
.category-chip.selected{background:#2d8c3c;color:white;border-color:#2d8c3c}
.upload-area{background:#f8faf8;border:2px dashed #c0d0c0;border-radius:16px;padding:20px;text-align:center;cursor:pointer;margin:16px 0}
.upload-area i{font-size:32px;color:#2d8c3c;margin-bottom:8px;display:block}
.file-info{display:flex;align-items:center;gap:12px;padding:12px;background:#f8faf8;border-radius:12px;margin-top:12px}
.thumbnail{width:50px;height:50px;border-radius:12px;object-fit:cover}
.map-container{height:280px;background:#e8ece8;border-radius:20px;margin:16px 0;border:1px solid #e0e8e0;position:relative;overflow:hidden}
.location-badge{background:#f8faf8;border-radius:12px;padding:12px;margin:12px 0;display:flex;align-items:center;gap:12px;border:1px solid #e0e8e0}
.location-badge i{color:#2d8c3c;font-size:18px}
.location-text{flex:1;font-size:13px}
.refresh-loc{background:#f0f4f0;border:none;width:36px;height:36px;border-radius:50%;cursor:pointer}
.confirm-loc{width:100%;padding:12px;background:#2d8c3c;color:white;border:none;border-radius:40px;cursor:pointer;margin-top:12px}
.otp-box{display:flex;gap:12px;justify-content:center;margin:28px 0}
.otp-input{width:52px;height:60px;text-align:center;font-size:26px;font-weight:700;border:1.5px solid #e0e8e0;border-radius:14px;background:white}
.otp-input:focus{outline:none;border-color:#2d8c3c}
.checkbox-row{display:flex;align-items:center;gap:12px;margin:20px 0}
.checkbox-row input{width:18px;height:18px;accent-color:#2d8c3c}
.toast{position:fixed;bottom:24px;left:20px;right:20px;background:#1a2e1a;color:white;padding:14px;border-radius:50px;text-align:center;z-index:1000}
.spinner{display:inline-block;width:16px;height:16px;border:2px solid white;border-top-color:transparent;border-radius:50%;animation:spin 0.5s linear infinite;margin-right:8px}
@keyframes spin{to{transform:rotate(360deg)}}
.loading-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:2000}
.loading-card{background:white;border-radius:24px;padding:32px;text-align:center;min-width:200px}
.loading-card .spinner{width:32px;height:32px;border-width:3px;margin-bottom:16px}
.strength-bar{height:4px;background:#e0e8e0;border-radius:2px;margin:8px 0;overflow:hidden}
.strength-fill{height:100%;width:0%}
.strength-text{font-size:11px;margin-top:4px}
.footer{text-align:center;padding:20px;border-top:1px solid #e8ece8;margin-top:20px;color:#8ba88b;font-size:11px}
.contact-method{display:flex;gap:16px;margin:20px 0;justify-content:center}
.method-btn{flex:1;padding:16px;background:#f8faf8;border:2px solid #e0e8e0;border-radius:16px;cursor:pointer;text-align:center;transition:all 0.2s}
.method-btn.active{border-color:#2d8c3c;background:#e8f5e9}
.method-btn i{font-size:28px;display:block;margin-bottom:8px;color:#2d8c3c}
.method-btn span{font-size:13px;font-weight:600;color:#1a2e1a}
.method-btn small{font-size:11px;color:#8ba88b;display:block}
.eula-modal, .error-modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:3000;align-items:center;justify-content:center;padding:20px}
.eula-modal.show, .error-modal.show{display:flex}
.eula-content, .error-content{background:white;border-radius:28px;max-width:500px;width:100%;max-height:85vh;overflow-y:auto;padding:24px}
.eula-header, .error-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;font-size:20px;font-weight:700;color:#1a2e1a}
.eula-close, .error-close{font-size:28px;cursor:pointer;color:#8ba88b;padding:8px}
.eula-text, .error-text{background:#f8faf8;padding:20px;border-radius:20px;font-size:14px;line-height:1.6;color:#4a5e4a;margin-bottom:20px}
.eula-text h4{color:#1a2e1a;margin-bottom:12px}
.error-icon{font-size:48px;color:#e53935;margin-bottom:16px}
</style>

<div class="header">
    <button class="back-btn" onclick="handleBack()"><i class="fas fa-arrow-left"></i></button>
    <div class="title">Lako<br><small>GPS Based Vendor Discovery App</small></div>
    <div style="width:40px"></div>
</div>
<div class="container" id="content"></div>
<div class="footer">
    <p>Lako Beta Version | Developed by Alexander Collin P. Millichamp &amp; Kyle Brian M. Morillo</p>
    <p>AITE College</p>
</div>

<!-- EULA Modal -->
<div id="eulaModal" class="eula-modal">
    <div class="eula-content">
        <div class="eula-header">
            <h3><i class="fas fa-file-contract"></i> Terms of Service</h3>
            <span class="eula-close" onclick="closeEULA()">&times;</span>
        </div>
        <div class="eula-text">
            <h4>📜 LAKO TERMS OF SERVICE</h4>
            <p>Welcome to Lako, the GPS-based vendor discovery app for Tiaong, Quezon!</p>
            <p><strong>1. Acceptance of Terms</strong><br>By using Lako, you agree to these terms.</p>
            <p><strong>2. User Conduct</strong><br>You agree to use the app responsibly and respectfully.</p>
            <p><strong>3. Privacy</strong><br>Your location data is used only for finding nearby vendors. We never share your personal information.</p>
            <p><strong>4. Vendor Information</strong><br>Vendors are responsible for the accuracy of their business information.</p>
            <p><strong>5. Location Sharing</strong><br>You can choose to share your location for better vendor recommendations.</p>
            <p><strong>6. Account Security</strong><br>You are responsible for maintaining the security of your account.</p>
            <p><strong>7. Content Ownership</strong><br>You retain ownership of content you post, but grant Lako a license to display it.</p>
            <p><strong>8. Prohibited Activities</strong><br>Do not harass users, post false information, or attempt to hack the app.</p>
            <p><strong>9. Termination</strong><br>We may terminate accounts that violate these terms.</p>
            <p><strong>10. Changes to Terms</strong><br>We may update these terms. Continued use means acceptance.</p>
            <p><strong>11. Disclaimer</strong><br>Lako is provided "as is" without warranties.</p>
            <p><strong>12. Contact</strong><br>Questions? Email support@lako.app</p>
            <p style="margin-top:16px"><strong>By continuing, you agree to all terms above.</strong></p>
        </div>
        <div class="checkbox-row">
            <input type="checkbox" id="eulaCheckbox" onchange="toggleEULAAccept()">
            <span>I have read and agree to the <strong>Terms of Service</strong></span>
        </div>
        <button class="btn" id="acceptEulaBtn" onclick="acceptEULA()" disabled><i class="fas fa-check"></i> Accept & Continue</button>
    </div>
</div>

<!-- Error Modal -->
<div id="errorModal" class="error-modal">
    <div class="error-content">
        <div class="error-header">
            <h3><i class="fas fa-exclamation-triangle"></i> Login Failed</h3>
            <span class="error-close" onclick="closeErrorModal()">&times;</span>
        </div>
        <div class="error-text text-center">
            <div class="error-icon"><i class="fas fa-lock"></i></div>
            <p id="errorMessage" style="margin-bottom:20px;font-size:16px">Invalid credentials. Please check your email/phone and password.</p>
            <button class="btn" onclick="closeErrorModalAndRetry()"><i class="fas fa-redo"></i> Try Again</button>
        </div>
    </div>
</div>

<script>
let userRole = localStorage.getItem('selected_role') || 'customer';
localStorage.setItem('user_role', userRole);

let step='login';
let q=0;
let contactMethod = 'phone';
let savedIdentifier = localStorage.getItem('saved_login_identifier') || '';
let savedPassword = localStorage.getItem('saved_login_password') || '';
let regData={
    email: '',
    phone: '',
    autoGeneratedEmail: '',
    password: '',
    full_name: '',
    business_name: '',
    user_name: '',
    category: '',
    location: {lat: null, lng: null, address: ''},
    locationConfirmed: false,
    agreedToEula: false,
    profilePhoto: null,
    profilePhotoName: null,
    skippedPhoto: false,
    logo: null,
    logoName: null,
    skippedLogo: false,
    preferences: {categories: [], priceMin: 0, priceMax: 500, maxDistance: 10}
};
let otpInterval = null;
let map = null;
let currentMarker = null;

const CATEGORIES = ["Coffee","Pancit","Tusok Tusok","Contemporary Street food","Bread and Pastry","Lomi","Beverage","Sarisari Store","Karendirya","Traditional Desserts","Contemporary Desserts","Squidball","Siomai","Siopao","Taho","Balut and other poultry","Corn","Fruit shakes","Fruit Juice"];

function showToast(m){let t=document.querySelector('.toast');if(t)t.remove();t=document.createElement('div');t.className='toast';t.innerHTML='<i class="fas fa-info-circle"></i> '+m;document.body.appendChild(t);setTimeout(()=>t.remove(),3000);}

function showLoading(show, message){
    let existing=document.querySelector('.loading-overlay');
    if(existing)existing.remove();
    if(show){
        let overlay=document.createElement('div');
        overlay.className='loading-overlay';
        overlay.innerHTML='<div class="loading-card"><div class="spinner"></div><p>'+message+'</p></div>';
        document.body.appendChild(overlay);
    }
}

function handleBack(){
    if(step==='register'&&q>0){q--;render();}
    else if(step==='register'){step='login';contactMethod='phone';render();}
    else if(step==='otp'){step='register';q=0;render();}
    else{window.location.href='/';}
}

function toggleEULAAccept() {
    const checkbox = document.getElementById('eulaCheckbox');
    const btn = document.getElementById('acceptEulaBtn');
    btn.disabled = !checkbox.checked;
}

function showEULA() {
    document.getElementById('eulaModal').classList.add('show');
}

function closeEULA() {
    document.getElementById('eulaModal').classList.remove('show');
}

function acceptEULA() {
    regData.agreedToEula = true;
    closeEULA();
    register();
}

function showErrorModal(message, identifier, password) {
    document.getElementById('errorMessage').innerHTML = message || 'Invalid credentials. Please check your email/phone and password.';
    document.getElementById('errorModal').classList.add('show');
    // Save the failed inputs for retry
    if(identifier) localStorage.setItem('saved_login_identifier', identifier);
    if(password) localStorage.setItem('saved_login_password', password);
}

function closeErrorModal() {
    document.getElementById('errorModal').classList.remove('show');
}

function closeErrorModalAndRetry() {
    closeErrorModal();
    // Focus on login form with saved values
    const identifierInput = document.getElementById('loginIdentifier');
    const passwordInput = document.getElementById('loginPassword');
    if(identifierInput) {
        identifierInput.value = localStorage.getItem('saved_login_identifier') || '';
        identifierInput.focus();
    }
    if(passwordInput) passwordInput.value = localStorage.getItem('saved_login_password') || '';
}

function getQuestions(){
    let qs = [];
    if(userRole === 'customer'){
        qs = ['Contact method', 'Your name', 'Phone number', 'Email address', 'Profile photo', 'Create password', 'Confirm password', 'Your preferences'];
    } else if(userRole === 'vendor') {
        qs = ['Contact method', 'Business name', 'Your name', 'Phone number', 'Email address', 'Business category', 'Business location', 'Profile photo', 'Business logo', 'Create password', 'Confirm password'];
    } else {
        qs = ['Email address', 'Create password', 'Confirm password'];
    }
    if(contactMethod === 'phone'){
        qs = qs.filter(q => q !== 'Email address');
    } else {
        qs = qs.filter(q => q !== 'Phone number');
    }
    return qs;
}

let questions = getQuestions();

function getStepMsg(currentQuestion){
    let stepMessages = {
        'Contact method': 'How would you like to receive verification?',
        'Phone number': 'We will send a verification code to this number',
        'Email address': 'We will send a verification code to this email',
        'Your name': 'Tell us what to call you',
        'Business name': 'What is the name of your business?',
        'Business category': 'Select the category that best describes your business',
        'Business location': 'Pin your exact location on the map so customers can find you',
        'Profile photo': 'Add a photo so customers can recognize you (optional)',
        'Business logo': 'Upload your business logo (optional)',
        'Create password': 'Create a secure password for your account',
        'Confirm password': 'Please confirm your password to continue',
        'Your preferences': 'Help us personalize your food recommendations'
    };
    return stepMessages[currentQuestion] || 'Just a few more details';
}

function generateAutoEmail(name, role){
    let slug = name.toLowerCase().replace(/[^a-z0-9]/g, '').substring(0, 20);
    if(role === 'vendor'){
        return `${slug}@lako.vendor`;
    } else {
        return `${slug}@lako.customer`;
    }
}

function initLocationMap(){
    if(typeof L === 'undefined'){
        setTimeout(initLocationMap, 100);
        return;
    }
    if(map) map.remove();
    
    map = L.map('locationMap').setView([14.5995, 120.9842], 15);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
    }).addTo(map);
    
    map.on('click', function(e){
        pinLocation(e.latlng.lat, e.latlng.lng);
    });
    
    if(navigator.geolocation){
        navigator.geolocation.getCurrentPosition(
            function(position){
                let lat = position.coords.latitude;
                let lng = position.coords.longitude;
                map.setView([lat, lng], 16);
                pinLocation(lat, lng);
                showToast('📍 Location detected! Tap anywhere to adjust');
            },
            function(error){
                console.log('Geolocation error:', error);
                showToast('📍 Tap on the map to pin your business location');
            },
            {enableHighAccuracy: true, timeout: 10000}
        );
    } else {
        showToast('📍 Tap on the map to pin your business location');
    }
}

function pinLocation(lat, lng){
    if(currentMarker){
        map.removeLayer(currentMarker);
    }
    
    currentMarker = L.marker([lat, lng], {draggable: true}).addTo(map);
    currentMarker.on('dragend', function(e){
        let pos = e.target.getLatLng();
        pinLocation(pos.lat, pos.lng);
    });
    
    regData.location.lat = lat;
    regData.location.lng = lng;
    regData.locationConfirmed = false;
    
    fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1`)
        .then(res => res.json())
        .then(data => {
            let address = data.display_name || `${lat}, ${lng}`;
            regData.location.address = address;
            document.getElementById('locationText').innerHTML = address.split(',').slice(0,4).join(',');
            document.getElementById('confirmLocBtn').disabled = false;
            document.getElementById('confirmLocBtn').innerHTML = '<i class="fas fa-check"></i> Confirm Location';
        })
        .catch(() => {
            regData.location.address = `${lat}, ${lng}`;
            document.getElementById('locationText').innerHTML = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
            document.getElementById('confirmLocBtn').disabled = false;
        });
}

function confirmLocation(){
    if(!regData.location.lat || !regData.location.lng){
        showToast('Please pin your location on the map first');
        return;
    }
    regData.locationConfirmed = true;
    document.getElementById('confirmLocBtn').innerHTML = '<i class="fas fa-check-circle"></i> Location Confirmed ✓';
    document.getElementById('confirmLocBtn').disabled = true;
    showToast('Location confirmed!');
    setTimeout(() => { q++; render(); }, 500);
}

function render(){
    let c = document.getElementById('content');
    if(!c) return;
    
    if(step === 'login'){
        c.innerHTML = '<div class="card"><h2><i class="fas fa-sign-in-alt"></i> Welcome back</h2><div class="subtitle">Sign in to discover amazing street food near you</div><div class="input-group"><input type="text" id="loginIdentifier" placeholder="Email or Phone number" value="'+savedIdentifier+'"></div><div class="input-group"><input type="password" id="loginPassword" placeholder="Password" value="'+savedPassword+'"><span class="toggle-pwd" onclick="togglePwd(\'loginPassword\')"><i class="fas fa-eye"></i></span></div><button onclick="handleLogin()"><i class="fas fa-sign-in-alt"></i> Sign in</button><button class="secondary" onclick="resetReg()"><i class="fas fa-user-plus"></i> Create new account</button></div>';
    }
    else if(step === 'register'){
        let current = questions[q];
        let isLast = (q === questions.length - 1);
        let stepMsg = getStepMsg(current);
        let html = '<div class="step-bars">'+questions.map(function(_,i){return '<div class="bar '+(i===q?'active':(i<q?'completed':''))+'"></div>';}).join('')+'</div><div class="card"><h2><i class="fas fa-user-plus"></i> '+current+'</h2><div class="subtitle">'+stepMsg+'</div>';
        
        if(current === 'Contact method'){
            html += `
            <div class="contact-method">
                <div class="method-btn ${contactMethod === 'phone' ? 'active' : ''}" onclick="setContactMethod('phone')">
                    <i class="fas fa-phone-alt"></i>
                    <span>Phone Only</span>
                    <small>Verification via SMS</small>
                </div>
                <div class="method-btn ${contactMethod === 'email' ? 'active' : ''}" onclick="setContactMethod('email')">
                    <i class="fas fa-envelope"></i>
                    <span>Email Only</span>
                    <small>Verification via Email</small>
                </div>
            </div>`;
        }
        else if(current === 'Phone number'){
            html += '<div class="input-group"><input type="tel" id="ans" placeholder="9123456789" maxlength="10" value="'+(regData.phone || '')+'"></div>';
            html += '<div class="subtitle" style="font-size:12px;color:#8ba88b;margin-top:8px"><i class="fas fa-info-circle"></i> We will send a 6-digit code via SMS</div>';
        }
        else if(current === 'Email address'){
            html += '<div class="input-group"><input type="email" id="ans" placeholder="you@example.com" value="'+(regData.email || '')+'"></div>';
            html += '<div class="subtitle" style="font-size:12px;color:#8ba88b;margin-top:8px"><i class="fas fa-info-circle"></i> We will send a 6-digit code via email</div>';
        }
        else if(current === 'Your name'){
            html += '<div class="input-group"><input type="text" id="ans" placeholder="How should we call you?" value="'+(regData.full_name||'')+'"></div>';
        }
        else if(current === 'Business name'){
            html += '<div class="input-group"><input type="text" id="ans" placeholder="Your business name" value="'+(regData.business_name||'')+'"></div>';
        }
        else if(current === 'Business category'){
            html += '<div class="category-grid">'+CATEGORIES.map(function(c){return '<div class="category-chip '+(regData.category===c?'selected':'')+'" onclick="selectCategory(\''+c+'\')">'+c+'</div>';}).join('')+'</div>';
        }
        else if(current === 'Business location'){
            html += '<div class="map-container" id="locationMap"></div>';
            html += '<div class="location-badge"><i class="fas fa-location-dot"></i><div class="location-text" id="locationText">Tap on the map to pin your location</div><button class="refresh-loc" onclick="centerOnUser()"><i class="fas fa-crosshairs"></i></button></div>';
            html += '<button class="confirm-loc" id="confirmLocBtn" onclick="confirmLocation()" disabled><i class="fas fa-map-pin"></i> Confirm Location</button>';
            setTimeout(initLocationMap, 100);
        }
        else if(current === 'Profile photo'){
            html += '<div class="upload-area" onclick="document.getElementById(\'photoFile\').click()"><i class="fas fa-camera"></i><div>Tap to upload your profile photo</div><div style="font-size:11px">JPG, PNG (max 5MB)</div></div><input type="file" id="photoFile" style="display:none" accept="image/*" onchange="handlePhotoUpload(this,\'photo\')"><div id="photoPreview"></div><div class="skip-link" style="text-align:center;margin-top:12px"><a href="#" onclick="skipPhoto(\'photo\')" style="color:#8ba88b;text-decoration:none;font-size:13px"><i class="fas fa-forward"></i> Skip for now</a></div>';
            if(regData.profilePhoto){
                setTimeout(function(){
                    let preview = document.getElementById('photoPreview');
                    if(preview) preview.innerHTML = '<div class="file-info"><img class="thumbnail" src="'+regData.profilePhoto+'"><span>'+regData.profilePhotoName+'</span><button onclick="removePhoto(\'photo\')"><i class="fas fa-times"></i></button></div>';
                },10);
            }
        }
        else if(current === 'Business logo'){
            html += '<div class="upload-area" onclick="document.getElementById(\'logoFile\').click()"><i class="fas fa-image"></i><div>Tap to upload your business logo</div><div style="font-size:11px">JPG, PNG (max 5MB)</div></div><input type="file" id="logoFile" style="display:none" accept="image/*" onchange="handlePhotoUpload(this,\'logo\')"><div id="logoPreview"></div><div class="skip-link" style="text-align:center;margin-top:12px"><a href="#" onclick="skipPhoto(\'logo\')" style="color:#8ba88b;text-decoration:none;font-size:13px"><i class="fas fa-forward"></i> Skip for now</a></div>';
            if(regData.logo){
                setTimeout(function(){
                    let preview = document.getElementById('logoPreview');
                    if(preview) preview.innerHTML = '<div class="file-info"><img class="thumbnail" src="'+regData.logo+'"><span>'+regData.logoName+'</span><button onclick="removePhoto(\'logo\')"><i class="fas fa-times"></i></button></div>';
                },10);
            }
        }
        else if(current === 'Create password'){
            html += '<div class="input-group"><input type="password" id="pwdInput" placeholder="Create a password" oninput="checkPasswordStrength()" value="'+(regData.password||'')+'"><span class="toggle-pwd" onclick="togglePwd(\'pwdInput\')"><i class="fas fa-eye"></i></span></div>';
            html += '<div class="input-group"><input type="password" id="confirmPwdInput" placeholder="Confirm your password" oninput="checkConfirmMatch()" value="'+(regData.password||'')+'"><span class="toggle-pwd" onclick="togglePwd(\'confirmPwdInput\')"><i class="fas fa-eye"></i></span></div>';
            html += '<div class="strength-bar"><div class="strength-fill" id="strengthFill"></div></div>';
            html += '<div class="strength-text" id="strengthText"></div>';
            html += '<div id="matchMsg" style="font-size:12px;margin-top:8px"></div>';
        }
        else if(current === 'Your preferences'){
            let prefCats = ["Coffee","Pancit","Street Food","Bakery","Lomi","Beverages","Desserts","Siomai","Taho","Fruit Shakes"];
            html += '<div class="subtitle"><i class="fas fa-heart"></i> Select the types of food you love (tap to select multiple)</div><div class="category-grid" id="prefGrid">'+prefCats.map(function(c){return '<div class="category-chip '+(regData.preferences.categories.indexOf(c)!==-1?'selected':'')+'" onclick="togglePref(\''+c+'\')">'+c+'</div>';}).join('')+'</div>';
            html += '<div class="subtitle" style="margin-top:16px"><i class="fas fa-coins"></i> What is your budget per person?</div>';
            html += '<input type="range" id="priceMin" class="slider" min="0" max="1000" step="50" value="'+regData.preferences.priceMin+'" oninput="updateRange()">';
            html += '<input type="range" id="priceMax" class="slider" min="0" max="1000" step="50" value="'+regData.preferences.priceMax+'" oninput="updateRange()">';
            html += '<div class="slider-values" style="display:flex;justify-content:space-between;margin:8px 0;font-size:13px;color:#6b8c6b"><span>₱0</span><span id="priceDisplay">₱'+regData.preferences.priceMin+'-₱'+regData.preferences.priceMax+'</span><span>₱1000+</span></div>';
            html += '<div class="subtitle" style="margin-top:16px"><i class="fas fa-road"></i> How far are you willing to travel?</div>';
            html += '<input type="range" id="distance" class="slider" min="1" max="50" step="1" value="'+regData.preferences.maxDistance+'" oninput="updateDist()">';
            html += '<div class="slider-values" style="display:flex;justify-content:space-between;margin:8px 0;font-size:13px;color:#6b8c6b"><span>1km</span><span id="distDisplay">'+regData.preferences.maxDistance+'km</span><span>50km</span></div>';
        }
        
        if(isLast){
            html += '<div class="checkbox-row"><input type="checkbox" id="eula" onchange="regData.agreedToEula=this.checked"> <span>I agree to the <a href="#" onclick="showEULA()" style="color:#2d8c3c">Terms of Service</a></span></div>';
        }
        
        html += '<div class="flex">'+(q>0?'<button class="secondary" onclick="prev()"><i class="fas fa-arrow-left"></i> Back</button>':'')+'<button onclick="next(\''+current+'\')">'+(isLast?'<i class="fas fa-check"></i> Create account':'<i class="fas fa-arrow-right"></i> Continue')+'</button></div></div>';
        c.innerHTML = html;
        
        if(current === 'Your name' && regData.full_name && !regData.autoGeneratedEmail){
            regData.autoGeneratedEmail = generateAutoEmail(regData.full_name, userRole);
        }
        if(current === 'Business name' && regData.business_name){
            regData.autoGeneratedEmail = generateAutoEmail(regData.business_name, 'vendor');
        }
        if(current === 'Create password' && regData.password){
            setTimeout(function(){
                let pwd = document.getElementById('pwdInput');
                let confirm = document.getElementById('confirmPwdInput');
                if(pwd) pwd.value = regData.password;
                if(confirm) confirm.value = regData.password;
                checkPasswordStrength();
                checkConfirmMatch();
            },10);
        }
        if(current === 'Your preferences'){ updateRange(); updateDist(); }
    }
    else if(step === 'otp'){
        let contactInfo = contactMethod === 'phone' ? regData.phone : regData.email;
        let displayInfo = contactMethod === 'phone' ? '+63' + regData.phone : regData.email;
        c.innerHTML = '<div class="card"><h2><i class="fas '+(contactMethod === 'phone' ? 'fa-phone-alt' : 'fa-envelope')+'"></i> Verify your account</h2><div class="subtitle">We sent a 6-digit verification code to '+displayInfo+'.</div><div class="otp-box">'+Array(6).fill().map(function(_,i){return '<input type="text" maxlength="1" class="otp-input" oninput="moveNext(this,'+i+')">';}).join('')+'</div><button onclick="verifyOTP()"><i class="fas fa-check"></i> Verify account</button><button class="secondary" id="resendBtn" onclick="resendOTP()"><i class="fas fa-redo"></i> Resend code</button></div>';
        startAutoOTP();
    }
}

function setContactMethod(method){
    contactMethod = method;
    questions = getQuestions();
    q = 0;
    render();
}

function selectCategory(cat){
    regData.category = cat;
    render();
}

function togglePref(cat){
    let idx = regData.preferences.categories.indexOf(cat);
    if(idx === -1) regData.preferences.categories.push(cat);
    else regData.preferences.categories.splice(idx,1);
    render();
}

function updateRange(){
    let min = parseInt(document.getElementById('priceMin')?.value||0);
    let max = parseInt(document.getElementById('priceMax')?.value||500);
    if(min > max) document.getElementById('priceMax').value = min;
    regData.preferences.priceMin = min;
    regData.preferences.priceMax = max;
    let d = document.getElementById('priceDisplay');
    if(d) d.innerText = '₱'+min+'-₱'+max;
}

function updateDist(){
    let v = parseInt(document.getElementById('distance')?.value||10);
    regData.preferences.maxDistance = v;
    let d = document.getElementById('distDisplay');
    if(d) d.innerText = v+'km';
}

function centerOnUser(){
    if(navigator.geolocation){
        navigator.geolocation.getCurrentPosition(
            function(pos){
                pinLocation(pos.coords.latitude, pos.coords.longitude);
                showToast('📍 Location updated');
            },
            function(){
                showToast('Could not get your location. Tap on the map to pin manually.');
            }
        );
    }
}

function prev(){ if(q > 0){ q--; render(); } }

function next(qName){
    let val = document.getElementById('ans')?.value;
    
    if(qName === 'Phone number'){
        if(!val || val.length !== 10){ showToast('Please enter a valid 10-digit phone number'); return; }
        regData.phone = val;
    }
    else if(qName === 'Email address'){
        if(!val || !val.includes('@')){ showToast('Please enter a valid email address'); return; }
        regData.email = val;
    }
    else if(qName === 'Create password'){
        let pwdVal = document.getElementById('pwdInput')?.value;
        let confirmVal = document.getElementById('confirmPwdInput')?.value;
        if(!pwdVal || pwdVal.length === 0){ showToast('Please create a password'); return; }
        if(pwdVal !== confirmVal){ showToast('Passwords do not match'); return; }
        let strength = 0;
        if(pwdVal.length >= 6) strength++;
        if(pwdVal.length >= 10) strength++;
        if(/[a-z]/.test(pwdVal)) strength++;
        if(/[A-Z]/.test(pwdVal)) strength++;
        if(/[0-9]/.test(pwdVal)) strength++;
        if(/[^a-zA-Z0-9]/.test(pwdVal)) strength++;
        if(strength <= 3){ showToast('Please use a stronger password (Good or Strong)'); return; }
        regData.password = pwdVal;
    }
    else if(qName === 'Your name'){
        if(!val || val.trim() === ''){ showToast('Please enter your name'); return; }
        regData.full_name = val.trim();
        regData.autoGeneratedEmail = generateAutoEmail(regData.full_name, userRole);
    }
    else if(qName === 'Business name'){
        if(!val || val.trim() === ''){ showToast('Please enter your business name'); return; }
        regData.business_name = val.trim();
        regData.autoGeneratedEmail = generateAutoEmail(regData.business_name, 'vendor');
    }
    else if(qName === 'Business category'){
        if(!regData.category){ showToast('Please select a business category'); return; }
    }
    else if(qName === 'Business location'){
        if(!regData.locationConfirmed){ showToast('Please confirm your business location on the map'); return; }
    }
    else if(qName === 'Profile photo'){
        if(!regData.profilePhoto && !regData.skippedPhoto){ 
            regData.skippedPhoto = true;
        }
    }
    else if(qName === 'Business logo'){
        if(!regData.logo && !regData.skippedLogo){
            regData.skippedLogo = true;
        }
    }
    
    if(q < questions.length - 1){
        q++;
        render();
    } else {
        if(!regData.agreedToEula){ showEULA(); return; }
        register();
    }
}

function skipPhoto(type){
    if(type === 'photo'){
        regData.skippedPhoto = true;
        regData.profilePhoto = null;
        regData.profilePhotoName = null;
        let preview = document.getElementById('photoPreview');
        if(preview) preview.innerHTML = '';
        showToast('Profile photo skipped');
        q++;
        render();
    }
    if(type === 'logo'){
        regData.skippedLogo = true;
        regData.logo = null;
        regData.logoName = null;
        let preview = document.getElementById('logoPreview');
        if(preview) preview.innerHTML = '';
        showToast('Business logo skipped');
        q++;
        render();
    }
}

function handlePhotoUpload(input, type){
    if(input.files && input.files[0]){
        let file = input.files[0];
        if(file.size > 5*1024*1024){ showToast('File too large. Max 5MB'); return; }
        let r = new FileReader();
        r.onload = function(e){
            if(type === 'photo'){
                regData.profilePhoto = e.target.result;
                regData.profilePhotoName = file.name;
                regData.skippedPhoto = false;
                let preview = document.getElementById('photoPreview');
                if(preview) preview.innerHTML = '<div class="file-info"><img class="thumbnail" src="'+regData.profilePhoto+'"><span>'+file.name+'</span><button onclick="removePhoto(\'photo\')"><i class="fas fa-times"></i></button></div>';
                showToast('Profile photo uploaded');
                q++;
                render();
            } else {
                regData.logo = e.target.result;
                regData.logoName = file.name;
                regData.skippedLogo = false;
                let preview = document.getElementById('logoPreview');
                if(preview) preview.innerHTML = '<div class="file-info"><img class="thumbnail" src="'+regData.logo+'"><span>'+file.name+'</span><button onclick="removePhoto(\'logo\')"><i class="fas fa-times"></i></button></div>';
                showToast('Business logo uploaded');
                q++;
                render();
            }
        };
        r.readAsDataURL(file);
    }
}

function removePhoto(type){
    if(type === 'photo'){
        regData.profilePhoto = null;
        regData.profilePhotoName = null;
        let preview = document.getElementById('photoPreview');
        if(preview) preview.innerHTML = '';
    }
    if(type === 'logo'){
        regData.logo = null;
        regData.logoName = null;
        let preview = document.getElementById('logoPreview');
        if(preview) preview.innerHTML = '';
    }
}

async function register(){
    showLoading(true, 'Creating your account...');
    
    let endpoint = userRole === 'customer' ? '/api/auth/register/customer' : (userRole === 'vendor' ? '/api/auth/register/vendor' : '/api/auth/register/admin');
    
    let body;
    if(userRole === 'customer'){
        body = {
            full_name: regData.full_name,
            password: regData.password,
            preferences: regData.preferences,
            profile_photo: regData.profilePhoto || null
        };
        if(contactMethod === 'phone'){
            body.phone = regData.phone;
            body.email = regData.autoGeneratedEmail;
        } else {
            body.email = regData.email;
            body.phone = null;
        }
    } else if(userRole === 'vendor') {
        body = {
            business_name: regData.business_name,
            user_name: regData.full_name,
            password: regData.password,
            business_category: regData.category,
            address: regData.location.address,
            latitude: regData.location.lat,
            longitude: regData.location.lng,
            profile_photo: regData.profilePhoto || null,
            logo: regData.logo || null
        };
        if(contactMethod === 'phone'){
            body.phone = regData.phone;
            body.email = regData.autoGeneratedEmail;
        } else {
            body.email = regData.email;
            body.phone = null;
        }
    } else {
        body = {
            email: regData.email,
            password: regData.password,
            full_name: 'Admin User'
        };
    }
    
    let res = await fetch(endpoint, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    let data = await res.json();
    showLoading(false);
    
    if(res.ok && data.requires_verification){
        step = 'otp';
        render();
    } else if(res.ok){
        localStorage.setItem('session_token', data.session_token);
        localStorage.setItem('user_role', userRole);
        
        if (userRole === 'admin') {
            window.location.href = '/admin';
        } else if (userRole === 'customer') {
            window.location.href = '/customer';
        } else if (userRole === 'vendor') {
            window.location.href = '/vendor';
        } else {
            window.location.href = '/auth';
        }
    } else {
        showToast(data.error || 'Registration failed');
    }
}

function togglePwd(id){
    let i = document.getElementById(id);
    if(i.type === 'password'){ i.type='text'; event.target.classList.remove('fa-eye'); event.target.classList.add('fa-eye-slash'); }
    else{ i.type='password'; event.target.classList.remove('fa-eye-slash'); event.target.classList.add('fa-eye'); }
}

function checkPasswordStrength(){
    let pwd = document.getElementById('pwdInput')?.value||'';
    let strength = 0;
    if(pwd.length >= 6) strength++;
    if(pwd.length >= 10) strength++;
    if(/[a-z]/.test(pwd)) strength++;
    if(/[A-Z]/.test(pwd)) strength++;
    if(/[0-9]/.test(pwd)) strength++;
    if(/[^a-zA-Z0-9]/.test(pwd)) strength++;
    
    let percent = 0, color = '', text = '';
    if(strength <= 2){ percent = 25; color = '#e53935'; text = 'Weak'; }
    else if(strength <= 3){ percent = 50; color = '#fb8c00'; text = 'Fair'; }
    else if(strength <= 4){ percent = 75; color = '#1e88e5'; text = 'Good'; }
    else{ percent = 100; color = '#2d8c3c'; text = 'Strong'; }
    
    let fill = document.getElementById('strengthFill');
    let textEl = document.getElementById('strengthText');
    if(fill){ fill.style.width = percent+'%'; fill.style.background = color; }
    if(textEl){ textEl.innerHTML = 'Strength: <span style="color:'+color+'">'+text+'</span>'; }
    
    let confirmPwd = document.getElementById('confirmPwdInput')?.value;
    let matchMsg = document.getElementById('matchMsg');
    if(confirmPwd){
        if(pwd === confirmPwd && pwd.length > 0){
            matchMsg.innerHTML = '✓ Passwords match';
            matchMsg.style.color = '#4caf50';
        } else if(confirmPwd.length > 0){
            matchMsg.innerHTML = '✗ Passwords do not match';
            matchMsg.style.color = '#e53935';
        }
    }
}

function checkConfirmMatch(){
    let pwd = document.getElementById('pwdInput')?.value||'';
    let confirm = document.getElementById('confirmPwdInput')?.value||'';
    let msg = document.getElementById('matchMsg');
    if(pwd === confirm && pwd.length > 0){
        msg.innerHTML = '✓ Passwords match';
        msg.style.color = '#4caf50';
        return true;
    } else if(confirm.length > 0){
        msg.innerHTML = '✗ Passwords do not match';
        msg.style.color = '#e53935';
        return false;
    }
    msg.innerHTML = '';
    return false;
}

async function handleLogin(){
    let identifier = document.getElementById('loginIdentifier').value;
    let password = document.getElementById('loginPassword').value;
    
    if(!identifier || !password){ 
        showErrorModal('Please enter both email/phone and password.', identifier, password);
        return; 
    }
    
    showLoading(true, 'Signing in...');
    
    let isPhone = /^\d{10}$/.test(identifier);
    let body = isPhone ? { phone: '+63'+identifier, password: password } : { email: identifier, password: password };
    
    try {
        let res = await fetch('/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
        let data = await res.json();
        showLoading(false);
        
        if(res.ok){
            // Clear saved failed login attempts on success
            localStorage.removeItem('saved_login_identifier');
            localStorage.removeItem('saved_login_password');
            
            localStorage.setItem('session_token', data.session_token);
            localStorage.setItem('user_role', data.role);
            
            if (data.role === 'admin') {
                window.location.href = '/admin';
            } else if (data.role === 'customer') {
                window.location.href = '/customer';
            } else if (data.role === 'vendor') {
                window.location.href = '/vendor';
            } else {
                window.location.href = '/auth';
            }
        } else {
            // Show error modal and save failed inputs for retry
            showErrorModal(data.error || 'Invalid credentials. Please check your email/phone and password.', identifier, password);
        }
    } catch (error) {
        showLoading(false);
        showErrorModal('Network error. Please check your connection.', identifier, password);
    }
}

function moveNext(i, idx){ if(i.value.length === 1){ let inp = document.querySelectorAll('.otp-input'); if(idx < 5) inp[idx+1].focus(); } }
function getOTP(){ return Array.from(document.querySelectorAll('.otp-input')).map(function(i){ return i.value; }).join(''); }

function startAutoOTP(){
    otpInterval = setInterval(async function(){
        let url = contactMethod === 'phone' ? '/api/auth/check-otp?phone=+63'+regData.phone : '/api/auth/check-otp?email='+encodeURIComponent(regData.email);
        let res = await fetch(url);
        let data = await res.json();
        if(data.found){
            clearInterval(otpInterval);
            let inp = document.querySelectorAll('.otp-input');
            let otp = data.otp.toString();
            otp.split('').forEach(function(d,i){ if(inp[i]) inp[i].value = d; });
            setTimeout(function(){ verifyOTP(); },500);
        }
    }, 3000);
}

async function verifyOTP(){
    let otp = getOTP(); if(otp.length !== 6){ showToast('Enter 6-digit code'); return; }
    showLoading(true, 'Verifying...');
    let body = contactMethod === 'phone' ? {phone: '+63'+regData.phone, otp: otp} : {email: regData.email, otp: otp};
    let res = await fetch('/api/auth/verify-otp', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    let data = await res.json();
    showLoading(false);
    if(res.ok){
        localStorage.setItem('session_token', data.session_token);
        localStorage.setItem('user_role', userRole);
        
        if (userRole === 'admin') {
            window.location.href = '/admin';
        } else if (userRole === 'customer') {
            window.location.href = '/customer';
        } else if (userRole === 'vendor') {
            window.location.href = '/vendor';
        } else {
            window.location.href = '/auth';
        }
    } else {
        showToast('Invalid code');
    }
}

async function resendOTP(){
    let body = contactMethod === 'phone' ? {phone: '+63'+regData.phone} : {email: regData.email};
    await fetch('/api/auth/resend-otp', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    showToast('New code sent');
}

function resetReg(){
    step = 'register';
    q = 0;
    contactMethod = 'phone';
    regData = {
        email: '',
        phone: '',
        autoGeneratedEmail: '',
        password: '',
        full_name: '',
        business_name: '',
        user_name: '',
        category: '',
        location: {lat: null, lng: null, address: ''},
        locationConfirmed: false,
        agreedToEula: false,
        profilePhoto: null,
        profilePhotoName: null,
        skippedPhoto: false,
        logo: null,
        logoName: null,
        skippedLogo: false,
        preferences: {categories: [], priceMin: 0, priceMax: 500, maxDistance: 10}
    };
    questions = getQuestions();
    render();
}

let fa = document.createElement('link'); fa.rel='stylesheet'; fa.href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'; document.head.appendChild(fa);
let leaflet = document.createElement('link'); leaflet.rel='stylesheet'; leaflet.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'; document.head.appendChild(leaflet);
let leafletScript = document.createElement('script'); leafletScript.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'; leafletScript.onload=function(){ if(step==='register' && questions[q]==='Business location') setTimeout(initLocationMap,100); }; document.head.appendChild(leafletScript);

render();
</script>
''')
# ============================================
# GUEST PAGE (Updated with modern GUI)
# ============================================
GUEST = render_page("Guest Mode", '''
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#f8faf8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
.app-bar{background:white;padding:16px;display:flex;gap:16px;border-bottom:1px solid #e8ece8;position:sticky;top:0;z-index:100}
.back-btn{background:#f0f4f0;border:none;width:40px;height:40px;border-radius:50%;cursor:pointer;font-size:18px;color:#2d8c3c}
.app-bar-title{font-size:18px;font-weight:600;color:#1a2e1a;flex:1}
.menu-btn{background:#f0f4f0;border:none;width:40px;height:40px;border-radius:50%;cursor:pointer;font-size:18px;color:#2d8c3c}
.content{padding:20px;max-width:500px;margin:0 auto;min-height:calc(100vh - 140px);padding-bottom:80px}
.bottom-nav{position:fixed;bottom:0;left:0;right:0;background:white;display:flex;justify-content:space-around;padding:10px 16px 20px;border-top:1px solid #e8ece8;max-width:500px;margin:0 auto;box-shadow:0 -2px 10px rgba(0,0,0,0.05);z-index:99}
.nav-item{display:flex;flex-direction:column;align-items:center;gap:4px;color:#8ba88b;font-size:12px;cursor:pointer;transition:all 0.2s}
.nav-item i{font-size:22px}
.nav-item.active{color:#2d8c3c}
.nav-item span{font-size:11px;font-weight:500}
.card{background:white;border-radius:20px;padding:16px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,0.03);border:0.5px solid rgba(0,0,0,0.03);cursor:pointer;transition:all 0.2s}
.card:active{transform:scale(0.98)}
.search-bar{background:white;border:1px solid #e0e8e0;border-radius:30px;padding:10px 16px;display:flex;align-items:center;gap:10px;margin-bottom:16px}
.search-bar i{color:#8ba88b;font-size:16px}
.search-bar input{flex:1;border:none;background:transparent;font-size:15px;outline:none}
.filter-chips{display:flex;gap:8px;overflow-x:auto;padding-bottom:8px;margin-bottom:16px;-webkit-overflow-scrolling:touch}
.chip{background:#f0f4f0;border:none;border-radius:30px;padding:6px 14px;font-size:13px;white-space:nowrap;cursor:pointer;transition:all 0.2s;color:#4a5e4a}
.chip.active{background:#2d8c3c;color:white}
.map-wrapper{position:relative;border-radius:20px;overflow:hidden;margin-bottom:16px}
.map-container{height:350px;width:100%;position:relative;background:#e8ece8;border-radius:20px}
#map{height:100%;width:100%;border-radius:20px}
.map-controls{position:absolute;bottom:16px;right:16px;display:flex;flex-direction:column;gap:8px;z-index:400}
.map-control-btn{width:44px;height:44px;background:white;border:none;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.15);cursor:pointer;color:#2d8c3c;font-size:18px;transition:all 0.2s;z-index:401}
.map-control-btn:active{transform:scale(0.95)}
.btn{width:100%;padding:12px;background:#2d8c3c;color:white;border:none;border-radius:30px;font-size:15px;font-weight:600;cursor:pointer;transition:all 0.2s}
.btn:active{transform:scale(0.97)}
.btn-outline{background:white;border:1px solid #2d8c3c;color:#2d8c3c;padding:10px;border-radius:30px;font-size:14px;font-weight:500;cursor:pointer;transition:all 0.2s}
.btn-sm{padding:6px 14px;font-size:13px;width:auto}
.vendor-status{display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:600}
.vendor-status.open{background:#e8f5e9;color:#2d8c3c}
.vendor-status.closed{background:#ffebee;color:#e53935}
.stars{color:#ffb800;font-size:12px;letter-spacing:1px}
.badge{background:#f0f4f0;padding:2px 10px;border-radius:20px;font-size:11px;color:#4a5e4a}
.text-secondary{color:#8ba88b;font-size:12px}
.text-center{text-align:center}
.mt-1{margin-top:4px}
.mt-2{margin-top:8px}
.mt-3{margin-top:12px}
.mb-2{margin-bottom:8px}
.flex{display:flex}
.justify-between{justify-content:space-between}
.items-center{align-items:center}
.gap-2{gap:8px}
.gap-3{gap:12px}
.avatar{width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,#2d8c3c,#1a6b28);display:flex;align-items:center;justify-content:center;color:white;font-size:20px;object-fit:cover}
.image-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
.image-thumb{width:100%;aspect-ratio:1;border-radius:12px;overflow:hidden;background:#f0f4f0}
.image-thumb img{width:100%;height:100%;object-fit:cover}
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:1000;align-items:center;justify-content:center;padding:20px}
.modal.show{display:flex}
.modal-content{background:white;border-radius:24px;max-width:500px;width:100%;max-height:85vh;overflow-y:auto;padding:20px;position:relative;z-index:1001}
.modal-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;font-size:18px;font-weight:700;color:#1a2e1a}
.modal-close{font-size:24px;cursor:pointer;color:#8ba88b;padding:8px}
.hamburger-menu{position:fixed;top:0;right:-280px;width:280px;height:100vh;background:white;z-index:200;box-shadow:-2px 0 10px rgba(0,0,0,0.1);transition:right 0.3s ease;padding:60px 20px}
.hamburger-menu.show{right:0}
.menu-item{padding:14px;display:flex;align-items:center;gap:12px;cursor:pointer;border-radius:12px;font-size:14px}
.menu-item:hover{background:#f0f4f0}
.menu-divider{height:1px;background:#e8ece8;margin:12px 0}
.toast{position:fixed;bottom:80px;left:20px;right:20px;background:#1a2e1a;color:white;padding:12px;border-radius:30px;text-align:center;z-index:1000;font-size:13px}
.avatar-select{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:20px 0}
.avatar-option{width:60px;height:60px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:28px;cursor:pointer;border:3px solid transparent;transition:all 0.2s}
.avatar-option.selected{border-color:#2d8c3c;transform:scale(1.05)}
.avatar-option i{color:white}
.input{width:100%;padding:12px 14px;border:1px solid #e0e8e0;border-radius:14px;font-size:14px;margin-bottom:12px;background:#f8faf8}
.input:focus{outline:none;border-color:#2d8c3c}
.eula-text{max-height:300px;overflow-y:auto;background:#f8faf8;padding:16px;border-radius:16px;margin:16px 0;font-size:13px;line-height:1.6;color:#4a5e4a}
.eula-text h4{color:#1a2e1a;margin-bottom:12px}
.eula-text p{margin-bottom:10px}
.eula-text ul{margin-left:20px;margin-bottom:10px}
.eula-text li{margin-bottom:5px}
.checkbox-row{display:flex;align-items:center;gap:12px;margin:16px 0}
.checkbox-row input{width:18px;height:18px;accent-color:#2d8c3c}
.leaflet-control-container .leaflet-top.leaflet-right{z-index:10}
.leaflet-popup{z-index:20}
.leaflet-control-attribution{z-index:10}
.leaflet-control-zoom{z-index:20}
</style>

<div class="app-bar">
    <button class="back-btn" onclick="window.location.href='/'"><i class="fas fa-arrow-left"></i></button>
    <div class="app-bar-title">Guest Mode</div>
    <button class="menu-btn" onclick="toggleMenu()"><i class="fas fa-bars"></i></button>
</div>

<div id="hamburgerMenu" class="hamburger-menu">
    <div class="menu-item" onclick="location.href='/auth'"><i class="fas fa-sign-in-alt"></i> Sign Up / Login</div>
    <div class="menu-divider"></div>
    <div class="menu-item" onclick="location.href='/'"><i class="fas fa-home"></i> Home</div>
</div>

<div class="content" id="content"></div>

<!-- Avatar & EULA Modal -->
<div id="welcomeModal" class="modal">
    <div class="modal-content">
        <div class="modal-header">
            <h3><i class="fas fa-user-plus"></i> Welcome to Lako</h3>
            <span class="modal-close" onclick="closeWelcomeModal()">&times;</span>
        </div>
        <div id="welcomeStep1">
            <div class="text-center mb-3">
                <div style="font-size:48px;margin-bottom:8px"><i class="fas fa-user-astronaut"></i></div>
                <h3>Choose Your Avatar</h3>
                <p class="text-secondary">Pick a character to represent you</p>
            </div>
            <div class="avatar-select" id="avatarSelect">
                <div class="avatar-option" style="background:#667eea" data-icon="user-circle" onclick="selectAvatar(this)"><i class="fas fa-user-circle"></i></div>
                <div class="avatar-option" style="background:#f093fb" data-icon="cat" onclick="selectAvatar(this)"><i class="fas fa-cat"></i></div>
                <div class="avatar-option" style="background:#4facfe" data-icon="dog" onclick="selectAvatar(this)"><i class="fas fa-dog"></i></div>
                <div class="avatar-option" style="background:#43e97b" data-icon="pizza-slice" onclick="selectAvatar(this)"><i class="fas fa-pizza-slice"></i></div>
                <div class="avatar-option" style="background:#fa709a" data-icon="ice-cream" onclick="selectAvatar(this)"><i class="fas fa-ice-cream"></i></div>
                <div class="avatar-option" style="background:#f6d365" data-icon="hamburger" onclick="selectAvatar(this)"><i class="fas fa-hamburger"></i></div>
                <div class="avatar-option" style="background:#30cfd0" data-icon="fish" onclick="selectAvatar(this)"><i class="fas fa-fish"></i></div>
                <div class="avatar-option" style="background:#a8edea" data-icon="apple-alt" onclick="selectAvatar(this)"><i class="fas fa-apple-alt"></i></div>
            </div>
            <input type="text" id="guestName" class="input" placeholder="Your display name" maxlength="20">
            <button class="btn" onclick="showEULAStep()"><i class="fas fa-arrow-right"></i> Continue</button>
        </div>
        
        <div id="welcomeStep2" style="display:none">
            <div class="text-center mb-3">
                <div style="font-size:48px;margin-bottom:8px"><i class="fas fa-file-contract"></i></div>
                <h3>Terms of Service</h3>
                <p class="text-secondary">Please read and accept our terms</p>
            </div>
            <div class="eula-text">
                <h4>📜 LAKO TERMS OF SERVICE</h4>
                <p>Welcome to Lako, the GPS-based vendor discovery app for Tiaong, Quezon!</p>
                <p><strong>1. Acceptance of Terms</strong><br>By using Lako, you agree to these terms.</p>
                <p><strong>2. User Conduct</strong><br>You agree to use the app responsibly and respectfully.</p>
                <p><strong>3. Privacy</strong><br>Your location data is used only for finding nearby vendors. We never share your personal information.</p>
                <p><strong>4. Vendor Information</strong><br>Vendors are responsible for the accuracy of their business information.</p>
                <p><strong>5. Location Sharing</strong><br>You can choose to share your location for better vendor recommendations.</p>
                <p><strong>6. Account Security</strong><br>You are responsible for maintaining the security of your account.</p>
                <p><strong>7. Content Ownership</strong><br>You retain ownership of content you post, but grant Lako a license to display it.</p>
                <p><strong>8. Prohibited Activities</strong><br>Do not harass users, post false information, or attempt to hack the app.</p>
                <p><strong>9. Termination</strong><br>We may terminate accounts that violate these terms.</p>
                <p><strong>10. Changes to Terms</strong><br>We may update these terms. Continued use means acceptance.</p>
                <p><strong>11. Disclaimer</strong><br>Lako is provided "as is" without warranties.</p>
                <p><strong>12. Contact</strong><br>Questions? Email support@lako.app</p>
                <p style="margin-top:16px"><strong>By continuing, you agree to all terms above.</strong></p>
            </div>
            <div class="checkbox-row">
                <input type="checkbox" id="agreeEULA" onchange="toggleCompleteButton()"> 
                <span>I have read and agree to the <strong>Terms of Service</strong></span>
            </div>
            <div class="flex gap-2">
                <button class="btn-outline" onclick="backToAvatar()"><i class="fas fa-arrow-left"></i> Back</button>
                <button class="btn" onclick="completeGuestSetup()" id="completeBtn" disabled><i class="fas fa-check"></i> Start Exploring</button>
            </div>
        </div>
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
    <div class="nav-item" onclick="showPage('feed')"><i class="fas fa-newspaper"></i><span>Feed</span></div>
</div>

<script>
let userLocation = null, allVendors = [], allProducts = [];
let page = 'map', map = null;
let heatLayer = null, fenceLayer = null, markerCluster = null;
let heatActive = false, fenceActive = false;
let guestProfile = null;
let selectedAvatarObj = null;

const CATEGORIES = ["Coffee","Pancit","Tusok Tusok","Contemporary Street food","Bread and Pastry","Lomi","Beverage","Sarisari Store","Karendirya","Traditional Desserts","Contemporary Desserts","Squidball","Siomai","Siopao","Taho","Balut and other poultry","Corn","Fruit shakes","Fruit Juice"];

function showToast(msg){
    let t=document.querySelector('.toast');
    if(t)t.remove();
    t=document.createElement('div');
    t.className='toast';
    t.innerHTML='<i class="fas fa-info-circle"></i> '+msg;
    document.body.appendChild(t);
    setTimeout(()=>t.remove(),3000);
}

function selectAvatar(el) {
    document.querySelectorAll('.avatar-option').forEach(a => a.classList.remove('selected'));
    el.classList.add('selected');
    selectedAvatarObj = { icon: el.dataset.icon, color: el.style.background };
}

function toggleCompleteButton() {
    const checkbox = document.getElementById('agreeEULA');
    const btn = document.getElementById('completeBtn');
    btn.disabled = !checkbox.checked;
}

function showEULAStep() {
    const name = document.getElementById('guestName').value.trim();
    if (!name) { 
        showToast('Please enter your name'); 
        return; 
    }
    if (!selectedAvatarObj) { 
        showToast('Please select an avatar'); 
        return; 
    }
    
    guestProfile = { name: name, avatar: selectedAvatarObj };
    
    document.getElementById('welcomeStep1').style.display = 'none';
    document.getElementById('welcomeStep2').style.display = 'block';
}

function backToAvatar() {
    document.getElementById('welcomeStep2').style.display = 'none';
    document.getElementById('welcomeStep1').style.display = 'block';
}

function completeGuestSetup() {
    if (!document.getElementById('agreeEULA').checked) {
        showToast('Please agree to the Terms of Service');
        return;
    }
    
    localStorage.setItem('guest_profile', JSON.stringify(guestProfile));
    closeWelcomeModal();
    document.querySelector('.bottom-nav').style.display = 'flex';
    loadData();
    showToast('Welcome to Lako! 🍢');
}

function closeWelcomeModal() {
    document.getElementById('welcomeModal').classList.remove('show');
}

function checkFirstTime() {
    const savedProfile = localStorage.getItem('guest_profile');
    if (!savedProfile) {
        document.getElementById('welcomeModal').classList.add('show');
        document.querySelector('.bottom-nav').style.display = 'none';
        document.getElementById('welcomeStep1').style.display = 'block';
        document.getElementById('welcomeStep2').style.display = 'none';
        document.getElementById('agreeEULA').checked = false;
        document.getElementById('completeBtn').disabled = true;
        document.getElementById('guestName').value = '';
        selectedAvatarObj = null;
        document.querySelectorAll('.avatar-option').forEach(a => a.classList.remove('selected'));
    } else {
        guestProfile = JSON.parse(savedProfile);
        document.querySelector('.bottom-nav').style.display = 'flex';
        loadData();
    }
}

async function loadData() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(p => {
            userLocation = { lat: p.coords.latitude, lng: p.coords.longitude };
            loadVendorsAndProducts();
            showToast('📍 Location detected!');
        }, () => {
            userLocation = { lat: 14.5995, lng: 120.9842 };
            loadVendorsAndProducts();
            showToast('📍 Using default location (Tiaong)');
        });
    } else {
        userLocation = { lat: 14.5995, lng: 120.9842 };
        loadVendorsAndProducts();
    }
}

async function loadVendorsAndProducts() {
    const res = await fetch(`/api/guest/map/vendors?lat=${userLocation.lat}&lng=${userLocation.lng}`);
    const data = await res.json();
    if (data && data.vendors) {
        allVendors = data.vendors;
        allProducts = [];
        for (let vendor of allVendors) {
            const productsRes = await fetch(`/api/customer/products/${vendor.id}`);
            const products = await productsRes.json();
            for (let product of (products.products || [])) {
                product.vendor = vendor;
                allProducts.push(product);
            }
        }
        if (page === 'map') showMap();
        else if (page === 'vendors') showVendors();
        else if (page === 'feed') showFeed();
    }
}

function showPage(p) {
    page = p;
    document.querySelectorAll('.nav-item').forEach((el, i) => {
        const pages = ['map', 'vendors', 'feed'];
        el.classList.toggle('active', pages[i] === p);
    });
    if (p === 'map') showMap();
    else if (p === 'vendors') showVendors();
    else if (p === 'feed') showFeed();
}

function showMap() {
    document.getElementById('content').innerHTML = `
        <div class="search-bar"><i class="fas fa-search"></i><input type="text" id="searchBox" placeholder="Search vendors..." oninput="filterMarkers()"></div>
        <div class="map-wrapper"><div class="map-container"><div id="map"></div><div class="map-controls"><button class="map-control-btn" onclick="centerOnUser()"><i class="fas fa-location-dot"></i></button><button class="map-control-btn" id="heatBtn" onclick="toggleHeatmap()"><i class="fas fa-fire"></i></button><button class="map-control-btn" id="fenceBtn" onclick="toggleGeofence()"><i class="fas fa-circle"></i></button><button class="map-control-btn" id="clusterBtn" onclick="toggleCluster()"><i class="fas fa-layer-group"></i></button></div></div></div>
        <div class="flex justify-between items-center mb-2"><h4><i class="fas fa-store"></i> Nearby Vendors</h4><span class="text-secondary">${allVendors.length} found</span></div>
        <div id="nearbyList"></div>`;
    
    setTimeout(() => {
        if (map) map.remove();
        map = L.map('map').setView([userLocation.lat, userLocation.lng], 14);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png').addTo(map);
        
        L.circle([userLocation.lat, userLocation.lng], {
            radius: 50, color: '#2d8c3c', fillColor: '#2d8c3c', fillOpacity: 0.3, weight: 3
        }).addTo(map).bindPopup('<b>You are here</b>').openPopup();
        
        markerCluster = L.markerClusterGroup();
        allVendors.forEach(v => {
            if (v.latitude && v.longitude) {
                const marker = L.marker([v.latitude, v.longitude])
                    .bindPopup(`<b>${v.business_name}</b><br>${v.category}<br>⭐ ${v.rating || 'New'}`)
                    .on('click', () => showVendorModal(v.id));
                markerCluster.addLayer(marker);
            }
        });
        map.addLayer(markerCluster);
        updateNearbyList();
    }, 100);
}

function filterMarkers() {
    const query = document.getElementById('searchBox')?.value.toLowerCase() || '';
    if (markerCluster) map.removeLayer(markerCluster);
    markerCluster = L.markerClusterGroup();
    allVendors.forEach(v => {
        if (v.latitude && v.longitude && (v.business_name.toLowerCase().includes(query) || v.category.toLowerCase().includes(query))) {
            const marker = L.marker([v.latitude, v.longitude]).bindPopup(`<b>${v.business_name}</b>`).on('click', () => showVendorModal(v.id));
            markerCluster.addLayer(marker);
        }
    });
    map.addLayer(markerCluster);
}

function updateNearbyList() {
    const list = document.getElementById('nearbyList');
    if (list) {
        const sorted = [...allVendors].sort((a,b) => (a.distance || 999) - (b.distance || 999));
        list.innerHTML = sorted.slice(0,10).map(v => `
            <div class="card" onclick="showVendorModal('${v.id}')">
                <div class="flex justify-between items-center">
                    <div><strong><i class="fas fa-store"></i> ${v.business_name}</strong><br><span class="text-secondary"><i class="fas fa-tag"></i> ${v.category}</span></div>
                    <div><div class="stars">${'★'.repeat(Math.floor(v.rating || 0))}</div><div class="text-secondary">${v.distance ? v.distance + 'km' : ''}</div></div>
                </div>
            </div>
        `).join('') || '<div class="card text-center text-secondary"><i class="fas fa-info-circle"></i> No vendors nearby</div>';
    }
}

function showVendors() {
    document.getElementById('content').innerHTML = `
        <div class="search-bar"><i class="fas fa-search"></i><input type="text" id="vendorSearch" placeholder="Search vendors..." oninput="filterVendorList()"></div>
        <div class="filter-chips" id="categoryFilters">${CATEGORIES.slice(0,8).map(c => `<div class="chip" onclick="filterByCategory('${c}')">${c}</div>`).join('')}<div class="chip" onclick="filterByCategory('all')">All</div></div>
        <div id="vendorList"></div>`;
    filterVendorList();
}

let activeCategory = 'all';

function filterByCategory(cat) {
    activeCategory = cat;
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    if (cat !== 'all') event.target.classList.add('active');
    filterVendorList();
}

function filterVendorList() {
    const query = document.getElementById('vendorSearch')?.value.toLowerCase() || '';
    let filtered = allVendors.filter(v => v.business_name.toLowerCase().includes(query) || v.category.toLowerCase().includes(query));
    if (activeCategory !== 'all') filtered = filtered.filter(v => v.category === activeCategory);
    document.getElementById('vendorList').innerHTML = filtered.map(v => `
        <div class="card" onclick="showVendorModal('${v.id}')">
            <div class="flex justify-between items-center">
                <div><strong><i class="fas fa-store"></i> ${v.business_name}</strong><br><span class="text-secondary"><i class="fas fa-tag"></i> ${v.category}</span><div class="stars mt-1">${'★'.repeat(Math.floor(v.rating || 0))}</div></div>
                <span class="vendor-status ${v.is_open ? 'open' : 'closed'}">${v.is_open ? 'Open' : 'Closed'}</span>
            </div>
        </div>
    `).join('') || '<div class="card text-center text-secondary"><i class="fas fa-info-circle"></i> No vendors found</div>';
}

async function showFeed() {
    const res = await fetch('/api/guest/feed');
    const data = await res.json();
    document.getElementById('content').innerHTML = `
        <div class="text-center mb-3"><p class="text-secondary"><i class="fas fa-info-circle"></i> Login to like, comment, and interact with posts</p></div>
        <div id="feedList"></div>`;
    document.getElementById('feedList').innerHTML = (data.posts || []).map(p => `
        <div class="card">
            <div class="flex items-center gap-3">
                <div class="avatar" style="background:#f0f4f0;color:#2d8c3c"><i class="fas fa-user-circle"></i></div>
                <div><strong>${p.author || 'User'}</strong><br><span class="text-secondary"><i class="far fa-clock"></i> ${new Date(p.created_at).toLocaleDateString()}</span></div>
            </div>
            <p class="mt-2">${p.content}</p>
            ${p.images && p.images.length ? `<div class="image-grid mt-2">${p.images.slice(0,3).map(img => `<div class="image-thumb"><img src="${img.thumbnail}"></div>`).join('')}</div>` : ''}
            <div class="flex gap-3 mt-3">
                <span class="text-secondary"><i class="far fa-heart"></i> ${p.likes || 0}</span>
                <span class="text-secondary"><i class="far fa-comment"></i> ${p.comment_count || 0}</span>
            </div>
            <div class="mt-2 text-secondary" style="font-size:11px"><i class="fas fa-lock"></i> Login to interact</div>
        </div>
    `).join('') || '<div class="card text-center text-secondary"><i class="fas fa-info-circle"></i> No posts yet</div>';
}

async function showVendorModal(vendorId) {
    const v = allVendors.find(v => v.id === vendorId);
    if (!v) return;
    const products = allProducts.filter(p => p.vendor?.id === vendorId);
    
    document.getElementById('modalTitle').innerHTML = `<i class="fas fa-store"></i> ${v.business_name}`;
    document.getElementById('modalBody').innerHTML = `
        <p><span class="badge">${v.category}</span> <span class="vendor-status ${v.is_open ? 'open' : 'closed'}">${v.is_open ? 'Open Now' : 'Closed'}</span></p>
        <p><i class="fas fa-map-marker-alt"></i> ${v.address || 'No address'}</p>
        <p><i class="fas fa-star" style="color:#ffb800;"></i> ${v.rating || 'New'} (${v.review_count || 0} reviews)</p>
        <div class="flex gap-2 mt-2">
            <button class="btn-outline btn-sm" onclick="window.open('https://www.google.com/maps/dir/${userLocation.lat},${userLocation.lng}/${v.latitude},${v.longitude}', '_blank')"><i class="fas fa-directions"></i> Directions</button>
            <button class="btn-outline btn-sm" onclick="location.href='/auth'"><i class="fas fa-heart"></i> Login to Save</button>
        </div>
        <div class="mt-3"><strong><i class="fas fa-utensils"></i> Menu</strong></div>
        <div id="menuItems">${products.map(p => `
            <div class="flex gap-3 p-3" style="border-bottom:1px solid #e8ece8">
                ${p.images && p.images[0] ? `<div style="width:60px;height:60px;border-radius:12px;overflow:hidden"><img src="${p.images[0].thumbnail}" style="width:100%;height:100%;object-fit:cover"></div>` : `<div style="width:60px;height:60px;border-radius:12px;background:#f0f4f0;display:flex;align-items:center;justify-content:center"><i class="fas fa-utensils"></i></div>`}
                <div>
                    <div style="font-weight:600">${p.name}</div>
                    <div style="color:#2d8c3c;font-weight:700">₱${p.price}</div>
                </div>
            </div>
        `).join('') || '<p class="text-secondary">No menu items yet</p>'}</div>
        <div class="mt-3 text-secondary text-center"><i class="fas fa-lock"></i> Login to write reviews and save vendors</div>
    `;
    document.getElementById('vendorModal').classList.add('show');
}

function closeModal() { document.getElementById('vendorModal').classList.remove('show'); }
function centerOnUser() { if (map && userLocation) { map.setView([userLocation.lat, userLocation.lng], 15); showToast('Recentered'); } }
function toggleHeatmap() { 
    heatActive = !heatActive; 
    const btn = document.getElementById('heatBtn'); 
    if (heatActive) { 
        const points = allVendors.filter(v => v.latitude).map(v => [v.latitude, v.longitude, 0.5]); 
        heatLayer = L.heatLayer(points, { radius: 25 }).addTo(map); 
        btn.style.background = '#2d8c3c'; 
        btn.style.color = 'white'; 
    } else { 
        if (heatLayer) map.removeLayer(heatLayer); 
        btn.style.background = 'white'; 
        btn.style.color = '#2d8c3c'; 
    } 
}
function toggleGeofence() { 
    fenceActive = !fenceActive; 
    const btn = document.getElementById('fenceBtn'); 
    if (fenceActive) { 
        fenceLayer = L.circle([userLocation.lat, userLocation.lng], { radius: 3000, color: '#2d8c3c', fillColor: '#2d8c3c', fillOpacity: 0.05 }).addTo(map); 
        btn.style.background = '#2d8c3c'; 
        btn.style.color = 'white'; 
    } else { 
        if (fenceLayer) map.removeLayer(fenceLayer); 
        btn.style.background = 'white'; 
        btn.style.color = '#2d8c3c'; 
    } 
}
function toggleCluster() { location.reload(); }
function toggleMenu() { document.getElementById('hamburgerMenu').classList.toggle('show'); }

let fa=document.createElement('link');fa.rel='stylesheet';fa.href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css';document.head.appendChild(fa);
let leaflet=document.createElement('link');leaflet.rel='stylesheet';leaflet.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';document.head.appendChild(leaflet);
let leafletScript=document.createElement('script');leafletScript.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';leafletScript.onload=()=>{if(page==='map') setTimeout(showMap,100);};document.head.appendChild(leafletScript);
let leafletCluster=document.createElement('link');leafletCluster.rel='stylesheet';leafletCluster.href='https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css';document.head.appendChild(leafletCluster);
let leafletClusterScript=document.createElement('script');leafletClusterScript.src='https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js';document.head.appendChild(leafletClusterScript);
let heatScript=document.createElement('script');heatScript.src='https://cdnjs.cloudflare.com/ajax/libs/leaflet.heat/0.2.0/leaflet-heat.js';document.head.appendChild(heatScript);

checkFirstTime();
</script>
''')

CUSTOMER_DASH = render_page("Customer Dashboard", '''
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#f5f8f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
.app-bar{background:white;padding:14px 20px;display:flex;gap:16px;border-bottom:1px solid #e8ece8;position:sticky;top:0;z-index:100}
.back-btn,.menu-btn{background:#eff3ef;border:none;width:40px;height:40px;border-radius:50%;cursor:pointer;font-size:18px;color:#3a7b4d}
.app-bar-title{font-size:18px;font-weight:600;color:#2c3e2c;flex:1}
.content{padding:20px 16px;max-width:500px;margin:0 auto;min-height:calc(100vh - 140px);padding-bottom:90px}
.bottom-nav{position:fixed;bottom:0;left:0;right:0;background:white;display:flex;justify-content:space-around;padding:8px 16px 22px;border-top:1px solid #e8ece8;max-width:500px;margin:0 auto;z-index:99}
.nav-item{display:flex;flex-direction:column;align-items:center;gap:5px;color:#9aae9a;font-size:11px;cursor:pointer}
.nav-item i{font-size:22px}
.nav-item.active{color:#3a7b4d}
.nav-item span{font-size:11px;font-weight:500}
.card{background:white;border-radius:20px;padding:16px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,0.03);border:1px solid #eef2ee;cursor:pointer}
.search-bar{background:white;border:1px solid #e0e8e0;border-radius:30px;padding:10px 16px;display:flex;align-items:center;gap:10px;margin-bottom:16px}
.search-bar input{flex:1;border:none;background:transparent;font-size:15px;outline:none}
.filter-chips{display:flex;gap:8px;overflow-x:auto;padding-bottom:8px;margin-bottom:16px}
.filter-chips::-webkit-scrollbar{display:none}
.chip{background:#f0f4f0;border:none;border-radius:30px;padding:6px 14px;font-size:13px;white-space:nowrap;cursor:pointer;color:#4a5e4a}
.chip.active{background:#3a7b4d;color:white}
.map-wrapper{position:relative;border-radius:20px;overflow:hidden;margin-bottom:16px}
.map-container{height:400px;width:100%;background:#e8ece8;border-radius:20px;position:relative}
#map{height:100%;width:100%;border-radius:20px}
.map-controls{position:absolute;bottom:16px;right:16px;display:flex;flex-direction:column;gap:8px;z-index:400}
.map-control-btn{width:44px;height:44px;background:white;border:none;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.15);cursor:pointer;color:#3a7b4d;font-size:18px}
.map-control-btn.active{background:#3a7b4d;color:white}
.btn{width:100%;padding:12px;background:#3a7b4d;color:white;border:none;border-radius:30px;font-size:15px;font-weight:600;cursor:pointer}
.btn-outline{background:white;border:1px solid #3a7b4d;color:#3a7b4d;padding:10px;border-radius:30px;font-size:14px;font-weight:500;cursor:pointer}
.btn-sm{padding:6px 14px;font-size:13px;width:auto}
.vendor-status{display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:600}
.vendor-status.open{background:#e3f5e3;color:#3a7b4d}
.vendor-status.closed{background:#ffe8e6;color:#e57373}
.stars{color:#f5b042;font-size:12px;letter-spacing:1px}
.text-secondary{color:#8da38d;font-size:12px}
.flex{display:flex}
.justify-between{justify-content:space-between}
.items-center{align-items:center}
.gap-2{gap:8px}
.mt-2{margin-top:8px}
.mt-3{margin-top:12px}
.mb-2{margin-bottom:8px}
.avatar{width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,#3a7b4d,#2e6640);display:flex;align-items:center;justify-content:center;color:white;font-size:20px}
.avatar-sm{width:32px;height:32px;font-size:14px}
.avatar-lg{width:80px;height:80px;border-radius:50%;margin:0 auto 16px;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#3a7b4d,#2e6640);color:white;font-size:36px}
.product-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
.product-card{background:white;border-radius:16px;overflow:hidden;cursor:pointer;border:1px solid #eef2ee}
.product-card:active{transform:scale(0.98)}
.product-image{width:100%;aspect-ratio:1;background:#f4f7f4;display:flex;align-items:center;justify-content:center}
.product-image img{width:100%;height:100%;object-fit:cover}
.product-info{padding:10px}
.product-name{font-size:13px;font-weight:600}
.product-price{font-size:14px;font-weight:700;color:#3a7b4d}
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:1000;align-items:center;justify-content:center;padding:20px}
.modal.show{display:flex}
.modal-content{background:white;border-radius:24px;max-width:500px;width:100%;max-height:85vh;overflow-y:auto;padding:20px}
.modal-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;font-weight:700}
.modal-close{font-size:24px;cursor:pointer;color:#8ba88b;padding:8px}
.hamburger-menu{position:fixed;top:0;right:-280px;width:280px;height:100vh;background:white;z-index:200;box-shadow:-2px 0 10px rgba(0,0,0,0.1);transition:right 0.3s ease;padding:60px 20px}
.hamburger-menu.show{right:0}
.close-hamburger{position:absolute;top:20px;right:20px;background:#eff3ef;border:none;width:36px;height:36px;border-radius:50%;cursor:pointer;font-size:16px;color:#3a7b4d}
.menu-item{padding:14px;display:flex;align-items:center;gap:12px;cursor:pointer;border-radius:12px}
.menu-item:active{background:#eff3ef}
.menu-divider{height:1px;background:#e8ece8;margin:12px 0}
.post-actions{display:flex;gap:16px;margin-top:12px;padding-top:12px;border-top:1px solid #e8ece8}
.post-action-btn{background:transparent;border:none;padding:8px;border-radius:30px;cursor:pointer;color:#8ba88b;font-size:14px;display:flex;align-items:center;gap:8px}
.post-action-btn:active{background:#f0f4f0}
.post-action-btn.liked{color:#e53935}
.comment-thread{margin-top:12px;padding-left:20px;border-left:2px solid #e0e8e0}
.comment-item{background:#f8faf8;border-radius:16px;padding:12px;margin-bottom:8px}
.comment-author{font-weight:600;font-size:13px;cursor:pointer}
.toast{position:fixed;bottom:80px;left:20px;right:20px;background:#2c3e2c;color:white;padding:12px;border-radius:30px;text-align:center;z-index:1000;font-size:13px;animation:fadeInUp 0.3s}
@keyframes fadeInUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
.input{width:100%;padding:12px 14px;border:1px solid #e0e8e0;border-radius:14px;font-size:14px;margin-bottom:12px;background:#f8faf8}
.image-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:8px}
.image-thumb{width:100%;aspect-ratio:1;border-radius:12px;overflow:hidden;background:#f0f4f0}
.image-thumb img{width:100%;height:100%;object-fit:cover}
.profile-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:16px 0}
.stat-card{background:#f8faf8;padding:12px;border-radius:16px;text-align:center;cursor:pointer}
.stat-card:active{background:#e8ece8}
.stat-value{font-size:24px;font-weight:800;color:#3a7b4d}
.stat-label{font-size:11px;color:#8da38d;margin-top:4px}
.activity-item{background:#f8faf8;border-radius:16px;padding:12px;margin-bottom:8px;display:flex;align-items:center;gap:12px}
.activity-icon{width:40px;height:40px;background:#e3f5e3;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#3a7b4d}
.delete-btn{color:#e53935;border-color:#e53935}
.upload-area{background:#fafdfa;border:2px dashed #cde0cd;border-radius:16px;padding:16px;text-align:center;cursor:pointer}
.price-range{display:flex;gap:12px;margin-bottom:16px}
.price-range input{flex:1}
.suggestion-card{background:#f0f7f0;border:1px solid #c8e0c8;margin-bottom:20px}
.custom-marker{display:flex;align-items:center;justify-content:center;width:44px;height:44px;border-radius:50%;background:white;border:3px solid;box-shadow:0 2px 5px rgba(0,0,0,0.2);font-weight:bold;font-size:18px}
.user-marker{background:#3a7b4d;border-color:#2e6640;color:white}
.vendor-marker-open{border-color:#3a7b4d;background:#3a7b4d;color:white}
.vendor-marker-closed{border-color:#8da38d;background:#8da38d;color:white}
</style>

<div class="app-bar">
    <button class="back-btn" onclick="confirmLogout()"><i class="fas fa-sign-out-alt"></i></button>
    <div class="app-bar-title">Lako</div>
    <button class="menu-btn" onclick="toggleMenu()"><i class="fas fa-bars"></i></button>
</div>

<div id="hamburgerMenu" class="hamburger-menu">
    <button class="close-hamburger" onclick="closeMenu()"><i class="fas fa-times"></i></button>
    <div class="menu-item" onclick="closeMenu(); showSavedVendors()"><i class="fas fa-bookmark"></i> Saved Vendors (<span id="savedCount">0</span>)</div>
    <div class="menu-item" onclick="closeMenu(); showFollowedVendors()"><i class="fas fa-bell"></i> Following (<span id="followedCount">0</span>)</div>
    <div class="menu-divider"></div>
    <div class="menu-item" onclick="closeMenu(); showPreferences()"><i class="fas fa-sliders-h"></i> Preferences</div>
    <div class="menu-item" onclick="closeMenu(); showAnalytics()"><i class="fas fa-chart-line"></i> My Activity</div>
    <div class="menu-divider"></div>
    <div class="menu-item" onclick="confirmLogout()"><i class="fas fa-sign-out-alt"></i> Logout</div>
</div>

<div class="bottom-nav">
    <div class="nav-item active" onclick="showPage('map')"><i class="fas fa-map"></i><span>Map</span></div>
    <div class="nav-item" onclick="showPage('vendors')"><i class="fas fa-store"></i><span>Vendors</span></div>
    <div class="nav-item" onclick="showPage('products')"><i class="fas fa-search"></i><span>Products</span></div>
    <div class="nav-item" onclick="showPage('feed')"><i class="fas fa-newspaper"></i><span>Feed</span></div>
    <div class="nav-item" onclick="showPage('profile')"><i class="fas fa-user"></i><span>Profile</span></div>
</div>

<div class="content" id="content"></div>

<div id="vendorModal" class="modal"><div class="modal-content"><div class="modal-header"><h3 id="modalTitle"></h3><span class="modal-close" onclick="closeModal()">&times;</span></div><div id="modalBody"></div></div></div>
<div id="postModal" class="modal"><div class="modal-content"><div class="modal-header"><h3>Create Post</h3><span class="modal-close" onclick="closePostModal()">&times;</span></div><textarea id="postContent" class="input" rows="4" placeholder="Share your food experience..."></textarea><div class="upload-area" onclick="document.getElementById('postImages').click()"><i class="fas fa-camera"></i> Add Photos</div><input type="file" id="postImages" multiple accept="image/*" style="display:none" onchange="previewPostImages(this)"><div id="postImagePreview" class="image-grid" style="margin-top:8px"></div><button class="btn mt-2" onclick="createPost()">Post</button></div></div>
<div id="replyModal" class="modal"><div class="modal-content"><div class="modal-header"><h3>Write Reply</h3><span class="modal-close" onclick="closeReplyModal()">&times;</span></div><textarea id="replyContent" class="input" rows="3" placeholder="Write your reply..."></textarea><input type="hidden" id="replyPostId"><button class="btn" onclick="submitReply()">Post Reply</button></div></div>
<div id="reviewModal" class="modal"><div class="modal-content"><div class="modal-header"><h3>Write Review</h3><span class="modal-close" onclick="closeReviewModal()">&times;</span></div><div id="reviewStars" style="display:flex;gap:8px;justify-content:center;margin:12px 0"><i class="fas fa-star review-star" data-rating="1" style="font-size:32px;cursor:pointer;color:#ddd"></i><i class="fas fa-star review-star" data-rating="2" style="font-size:32px;cursor:pointer;color:#ddd"></i><i class="fas fa-star review-star" data-rating="3" style="font-size:32px;cursor:pointer;color:#ddd"></i><i class="fas fa-star review-star" data-rating="4" style="font-size:32px;cursor:pointer;color:#ddd"></i><i class="fas fa-star review-star" data-rating="5" style="font-size:32px;cursor:pointer;color:#ddd"></i></div><textarea id="reviewComment" class="input" rows="4" placeholder="Share your experience..."></textarea><input type="hidden" id="reviewVendorId"><button class="btn" onclick="submitReview()">Submit Review</button></div></div>
<div id="preferencesModal" class="modal"><div class="modal-content"><div class="modal-header"><h3>Your Preferences</h3><span class="modal-close" onclick="closePreferencesModal()">&times;</span></div><div><strong>Food Categories</strong></div><div id="prefCategories" class="filter-chips" style="flex-wrap:wrap"></div><div class="mt-3"><strong>Budget Range (₱)</strong></div><div class="price-range"><input type="range" id="prefPriceMin" min="0" max="1000" step="50" style="flex:1"><input type="range" id="prefPriceMax" min="0" max="1000" step="50" style="flex:1"></div><div class="flex justify-between"><span>₱<span id="prefPriceMinVal">0</span></span><span>₱<span id="prefPriceMaxVal">500</span></span></div><div class="mt-3"><strong>Max Distance (meters)</strong></div><input type="range" id="prefDistance" min="5" max="200" step="5" value="50" style="width:100%"><div class="flex justify-between"><span>5m</span><span id="prefDistanceVal">50m</span><span>200m</span></div><button class="btn mt-4" onclick="savePreferences()">Save Preferences</button></div></div>
<div id="profileModal" class="modal"><div class="modal-content"><div class="modal-header"><h3>Edit Profile</h3><span class="modal-close" onclick="closeProfileModal()">&times;</span></div><input id="profileName" class="input" placeholder="Full Name"><input id="profilePhone" class="input" placeholder="Phone Number"><button class="btn" onclick="saveProfile()">Save Changes</button></div></div>
<div id="userProfileModal" class="modal"><div class="modal-content"><div class="modal-header"><h3 id="userProfileTitle"></h3><span class="modal-close" onclick="closeUserProfileModal()">&times;</span></div><div id="userProfileBody"></div></div></div>
<div id="analyticsModal" class="modal"><div class="modal-content"><div class="modal-header"><h3>Your Activity</h3><span class="modal-close" onclick="closeAnalyticsModal()">&times;</span></div><div id="analyticsContent"></div></div></div>
<div id="minimapModal" class="modal"><div class="modal-content" style="padding:0"><div class="modal-header" style="padding:16px"><h3><i class="fas fa-directions"></i> Navigation</h3><span class="modal-close" onclick="closeMinimap()">&times;</span></div><div id="minimapContainer" style="height:400px;width:100%"></div><div class="flex gap-2 p-3"><button class="btn-outline btn-sm" onclick="centerMinimap()"><i class="fas fa-location-dot"></i> My Location</button><button class="btn btn-sm" onclick="openGoogleMaps()"><i class="fab fa-google"></i> Google Maps</button></div></div></div>

<script>
let sessionToken = localStorage.getItem('session_token');
let userLocation = null, watchId = null;
let allVendors = [], allProducts = [], savedVendors = [], followedVendors = [], vendorPosts = {};
let currentUserId = null, allPosts = [], userProfile = null;
let page = 'map', map = null, markerCluster = null, heatLayer = null, userMarker = null, minimap = null;
let heatActive = true;
let userPreferences = {categories: [], priceMin: 0, priceMax: 500, maxDistance: 50};
let currentRating = 0, currentReviewVendorId = null;
let activityLog = {lastViewedVendor: null, lastViewedProduct: null};

if (!sessionToken) window.location.href = '/auth';

if (navigator.geolocation) {
    watchId = navigator.geolocation.watchPosition(function(pos) {
        let newLoc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        if (!userLocation) {
            userLocation = newLoc;
            loadData();
        } else {
            userLocation = newLoc;
            if (map && userMarker) userMarker.setLatLng([userLocation.lat, userLocation.lng]);
            if (page === 'map') updateNearbyList();
        }
    }, null, { enableHighAccuracy: true });
}

function showToast(msg){
    let t=document.querySelector('.toast');
    if(t)t.remove();
    t=document.createElement('div');
    t.className='toast';
    t.innerHTML='<i class="fas fa-info-circle"></i> '+msg;
    document.body.appendChild(t);
    setTimeout(()=>t.remove(),3000);
}

function escapeHtml(text) {
    if (!text) return '';
    let div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function timeAgo(date) {
    let seconds = Math.floor((new Date() - new Date(date)) / 1000);
    if (seconds < 60) return seconds + 's ago';
    let minutes = Math.floor(seconds / 60);
    if (minutes < 60) return minutes + 'm ago';
    let hours = Math.floor(minutes / 60);
    if (hours < 24) return hours + 'h ago';
    return Math.floor(hours / 24) + 'd ago';
}

async function api(url, options = {}) {
    if (!sessionToken && !url.includes('/auth/')) { window.location.href = '/auth'; return null; }
    const headers = {'Content-Type': 'application/json'};
    if (sessionToken) headers['X-Session-Token'] = sessionToken;
    try {
        const res = await fetch(url, {...options, headers});
        if (res.status === 401) { localStorage.clear(); window.location.href = '/auth'; return null; }
        return res.json();
    } catch (e) { console.error('API error:', e); return null; }
}

async function loadData() {
    await loadVendorsAndProducts();
    await loadSaved();
    await loadFollows();
    await loadUserPreferences();
    await loadProfile();
    await loadFeed();
}

async function loadProfile() {
    const data = await api('/api/customer/profile');
    if (data) { currentUserId = data.id; userProfile = data; }
}

async function loadFeed() {
    const data = await api('/api/customer/feed');
    if (data && data.posts) allPosts = data.posts;
}

async function loadVendorPosts(vendorId) {
    if (vendorPosts[vendorId]) return vendorPosts[vendorId];
    const data = await api(`/api/customer/vendor/posts/${vendorId}`);
    if (data && data.posts) {
        vendorPosts[vendorId] = data.posts;
        return data.posts;
    }
    return [];
}

async function loadVendorsAndProducts() {
    const vendorsData = await api(`/api/customer/map/vendors?lat=${userLocation?.lat || 14.5995}&lng=${userLocation?.lng || 120.9842}`);
    
    if (vendorsData && vendorsData.vendors) {
        allVendors = vendorsData.vendors;
        allProducts = [];
        
        for (let vendor of allVendors) {
            const productsRes = await api(`/api/customer/products/${vendor.id}`);
            if (productsRes?.products) {
                for (let product of productsRes.products) { 
                    product.vendor = vendor; 
                    allProducts.push(product); 
                }
            }
        }
        
        if (page === 'map') showMap();
        else if (page === 'vendors') showVendors();
        else if (page === 'products') showProducts();
        else if (page === 'feed') showFeed();
        else showProfile();
    }
}

async function loadSaved() { 
    const data = await api('/api/customer/shortlist'); 
    if (data) { 
        savedVendors = data.vendors || []; 
        let el = document.getElementById('savedCount');
        if (el) el.innerText = savedVendors.length;
    } 
}

async function loadFollows() { 
    const data = await api('/api/customer/follows'); 
    if (data) { 
        followedVendors = data.vendors || []; 
        let el = document.getElementById('followedCount');
        if (el) el.innerText = followedVendors.length;
    } 
}

async function loadUserPreferences() { 
    const data = await api('/api/customer/preferences'); 
    if (data) { 
        userPreferences = data; 
        if (!userPreferences.maxDistance) userPreferences.maxDistance = 50;
        if (!userPreferences.priceMin) userPreferences.priceMin = 0;
        if (!userPreferences.priceMax) userPreferences.priceMax = 500;
    } 
}

function showPage(p) {
    page = p;
    let pages = ['map','vendors','products','feed','profile'];
    document.querySelectorAll('.nav-item').forEach((el,i)=> el.classList.toggle('active', pages[i]===p));
    closeMenu();
    if(p==='map') showMap();
    else if(p==='vendors') showVendors();
    else if(p==='products') showProducts();
    else if(p==='feed') showFeed();
    else showProfile();
}

function showMap() {
    document.getElementById('content').innerHTML = `
        <div class="search-bar"><i class="fas fa-search"></i><input type="text" id="searchBox" placeholder="Search vendors..." oninput="filterMapMarkers()"></div>
        <div class="map-wrapper"><div class="map-container"><div id="map"></div><div class="map-controls"><button class="map-control-btn" onclick="centerOnUser()"><i class="fas fa-location-dot"></i></button><button class="map-control-btn ${heatActive ? 'active' : ''}" id="heatBtn" onclick="toggleHeatmap()"><i class="fas fa-fire"></i></button></div></div></div>
        <div id="nearbyList"></div>`;
    
    setTimeout(() => {
        if (map) map.remove();
        let centerLat = (userLocation && userLocation.lat) ? userLocation.lat : 14.5995;
        let centerLng = (userLocation && userLocation.lng) ? userLocation.lng : 120.9842;
        map = L.map('map', { zoomControl: false }).setView([centerLat, centerLng], 15);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
        }).addTo(map);
        
        if (userLocation && userLocation.lat) {
            let userIcon = L.divIcon({
                html: `<div class="custom-marker user-marker"><i class="fas fa-user"></i></div>`,
                iconSize: [44, 44],
                className: ''
            });
            userMarker = L.marker([userLocation.lat, userLocation.lng], { icon: userIcon }).addTo(map).bindPopup('<b>You are here</b>');
        }
        
        markerCluster = L.markerClusterGroup({ spiderfyOnMaxZoom: true, maxClusterRadius: 50 });
        
        allVendors.forEach(v => {
            if (v.latitude && v.longitude) {
                let isOpen = v.is_open;
                let firstLetter = (v.business_name && v.business_name.charAt(0)) || 'V';
                let vendorIcon = L.divIcon({
                    html: `<div class="custom-marker vendor-marker-${isOpen ? 'open' : 'closed'}">${firstLetter}</div>`,
                    iconSize: [44, 44],
                    className: ''
                });
                let marker = L.marker([v.latitude, v.longitude], { icon: vendorIcon }).bindPopup(`
                    <b>${escapeHtml(v.business_name)}</b><br>
                    ${escapeHtml(v.category)}<br>
                    <span class="vendor-status ${isOpen?'open':'closed'}">${isOpen?'Open Now':'Closed'}</span><br>
                    <button class="btn-outline btn-sm mt-1" onclick="showVendorModal('${v.id}'); map.closePopup();">View</button>
                    <button class="btn-outline btn-sm mt-1" onclick="getDirections(${v.latitude}, ${v.longitude}, '${escapeHtml(v.business_name)}'); map.closePopup();">Directions</button>
                `);
                markerCluster.addLayer(marker);
            }
        });
        map.addLayer(markerCluster);
        
        if (heatActive) {
            let points = [];
            allVendors.forEach(v => { if (v.latitude) points.push([v.latitude, v.longitude, Math.min(0.8, (v.rating || 0) / 5 + 0.2)]); });
            heatLayer = L.heatLayer(points, { radius: 35, blur: 20 }).addTo(map);
        }
        updateNearbyList();
    }, 100);
}

function updateNearbyList() {
    let list = document.getElementById('nearbyList');
    if (list && allVendors.length) {
        let filtered = allVendors.filter(v => v.distance && v.distance <= userPreferences.maxDistance);
        let sorted = [...filtered].sort((a,b) => (a.distance||999) - (b.distance||999)).slice(0,8);
        list.innerHTML = `<h4 class="mb-2">Nearby (within ${userPreferences.maxDistance}m)</h4>` + sorted.map(v => `<div class="card" onclick="showVendorModal('${v.id}')"><div class="flex justify-between"><strong>${escapeHtml(v.business_name)}</strong><span class="text-secondary">${Math.round(v.distance)}m</span></div><div class="text-secondary">${escapeHtml(v.category)}</div><div class="stars mt-1">${'★'.repeat(Math.floor(v.rating||0))}</div></div>`).join('');
    }
}

function filterMapMarkers() {
    let query = document.getElementById('searchBox')?.value.toLowerCase() || '';
    if (!markerCluster) return;
    markerCluster.clearLayers();
    allVendors.forEach(v => {
        if (v.latitude && v.longitude && (v.business_name.toLowerCase().includes(query) || v.category.toLowerCase().includes(query))) {
            let isOpen = v.is_open;
            let firstLetter = (v.business_name && v.business_name.charAt(0)) || 'V';
            let vendorIcon = L.divIcon({
                html: `<div class="custom-marker vendor-marker-${isOpen ? 'open' : 'closed'}">${firstLetter}</div>`,
                iconSize: [44, 44],
                className: ''
            });
            markerCluster.addLayer(L.marker([v.latitude, v.longitude], { icon: vendorIcon }));
        }
    });
}

function centerOnUser() { if(map && userLocation) map.setView([userLocation.lat, userLocation.lng], 16); }

function toggleHeatmap() {
    heatActive = !heatActive;
    let btn = document.getElementById('heatBtn');
    if (heatActive) {
        let points = [];
        allVendors.forEach(v => { if (v.latitude) points.push([v.latitude, v.longitude, Math.min(0.8, (v.rating || 0) / 5 + 0.2)]); });
        heatLayer = L.heatLayer(points, { radius: 35, blur: 20 }).addTo(map);
        btn.classList.add('active');
        showToast('Heatmap enabled');
    } else {
        if (heatLayer) map.removeLayer(heatLayer);
        btn.classList.remove('active');
        showToast('Heatmap disabled');
    }
}

function showVendors() {
    let vendorCategories = [...new Set(allVendors.map(v => v.category).filter(c => c))].sort();
    document.getElementById('content').innerHTML = `
        <div class="search-bar"><i class="fas fa-search"></i><input type="text" id="vendorSearch" placeholder="Search vendors..." oninput="filterVendorList()"></div>
        <div class="filter-chips" id="categoryFilters">${vendorCategories.slice(0,12).map(c => `<div class="chip" onclick="filterByCategory('${c}')">${c}</div>`).join('')}<div class="chip active" onclick="filterByCategory('all')">All</div></div>
        <div id="vendorsContainer"></div>`;
    filterVendorList();
}

let activeVendorCat = 'all';
function filterByCategory(cat) { 
    activeVendorCat = cat; 
    let chips = document.querySelectorAll('#categoryFilters .chip');
    chips.forEach(c => c.classList.remove('active'));
    if(cat !== 'all') event.target.classList.add('active');
    else chips[chips.length-1].classList.add('active');
    filterVendorList(); 
}

function filterVendorList() {
    let query = document.getElementById('vendorSearch')?.value.toLowerCase() || '';
    let filtered = allVendors.filter(v => (v.business_name.toLowerCase().includes(query) || v.category.toLowerCase().includes(query)));
    if (activeVendorCat !== 'all') filtered = filtered.filter(v => v.category === activeVendorCat);
    
    let savedIds = new Set(savedVendors.map(v => v.id));
    let followedIds = new Set(followedVendors.map(v => v.id));
    let saved = filtered.filter(v => savedIds.has(v.id));
    let followed = filtered.filter(v => followedIds.has(v.id) && !savedIds.has(v.id));
    let others = filtered.filter(v => !savedIds.has(v.id) && !followedIds.has(v.id));
    
    let container = document.getElementById('vendorsContainer');
    if (container) {
        container.innerHTML = `
            ${saved.length ? `<h4 class="mt-2">Saved Vendors</h4>${saved.map(v => vendorCardWithActions(v)).join('')}` : ''}
            ${followed.length ? `<h4 class="mt-3">Following</h4>${followed.map(v => vendorCardWithActions(v)).join('')}` : ''}
            ${others.length ? `<h4 class="mt-3">All Vendors</h4>${others.map(v => vendorCard(v)).join('')}` : ''}
            ${!saved.length && !followed.length && !others.length ? '<div class="card text-center">No vendors found</div>' : ''}
        `;
    }
}

function vendorCard(v) {
    return `<div class="card" onclick="showVendorModal('${v.id}')"><div class="flex justify-between items-center"><div><strong>${escapeHtml(v.business_name)}</strong><div class="text-secondary">${escapeHtml(v.category)}</div><div class="stars mt-1">${'★'.repeat(Math.floor(v.rating||0))}</div></div><span class="vendor-status ${v.is_open?'open':'closed'}">${v.is_open?'Open':'Closed'}</span></div></div>`;
}

function vendorCardWithActions(v) {
    return `<div class="card"><div class="flex justify-between items-center"><div onclick="showVendorModal('${v.id}')" style="flex:1"><strong>${escapeHtml(v.business_name)}</strong><div class="text-secondary">${escapeHtml(v.category)}</div><div class="stars mt-1">${'★'.repeat(Math.floor(v.rating||0))}</div></div><div class="flex gap-2"><button class="btn-outline btn-sm" onclick="event.stopPropagation(); unsaveVendor('${v.id}')"><i class="fas fa-trash-alt"></i> Unsave</button><button class="btn-outline btn-sm" onclick="event.stopPropagation(); unfollowVendor('${v.id}')"><i class="fas fa-bell-slash"></i> Unfollow</button></div></div></div>`;
}

async function unsaveVendor(vendorId) {
    await api('/api/customer/shortlist/toggle', { method: 'POST', body: JSON.stringify({ vendor_id: vendorId }) });
    await loadSaved();
    showToast('Removed from saved');
    if (page === 'vendors') showVendors();
}

async function unfollowVendor(vendorId) {
    await api('/api/customer/follow-vendor', { method: 'POST', body: JSON.stringify({ vendor_id: vendorId }) });
    await loadFollows();
    showToast('Unfollowed vendor');
    if (page === 'vendors') showVendors();
}

function showSavedVendors() {
    let savedList = allVendors.filter(v => savedVendors.some(s => s.id === v.id));
    document.getElementById('content').innerHTML = `<div class="flex justify-between items-center mb-3"><h3>Saved Vendors</h3><button class="btn-outline btn-sm" onclick="showPage('vendors')">Back</button></div>${savedList.map(v => `<div class="card flex justify-between items-center"><div><strong>${escapeHtml(v.business_name)}</strong><div class="text-secondary">${escapeHtml(v.category)}</div></div><button class="btn-outline btn-sm" onclick="unsaveVendor('${v.id}'); this.closest('.card').remove()">Unsave</button></div>`).join('') || '<div class="card text-center">No saved vendors</div>'}`;
}

function showFollowedVendors() {
    let followedList = allVendors.filter(v => followedVendors.some(f => f.id === v.id));
    document.getElementById('content').innerHTML = `<div class="flex justify-between items-center mb-3"><h3>Following Vendors</h3><button class="btn-outline btn-sm" onclick="showPage('vendors')">Back</button></div>${followedList.map(v => `<div class="card flex justify-between items-center"><div><strong>${escapeHtml(v.business_name)}</strong><div class="text-secondary">${escapeHtml(v.category)}</div></div><button class="btn-outline btn-sm" onclick="unfollowVendor('${v.id}'); this.closest('.card').remove()">Unfollow</button></div>`).join('') || '<div class="card text-center">Not following any vendors</div>'}`;
}

function showProducts() {
    let productCategories = [...new Set(allProducts.map(p => p.category).filter(c => c))].sort();
    document.getElementById('content').innerHTML = `
        <div class="search-bar"><i class="fas fa-search"></i><input id="productSearch" placeholder="Search products..." oninput="filterProductList()"></div>
        <div class="filter-chips" id="productFilters">${productCategories.slice(0,10).map(c => `<div class="chip" onclick="filterProductByCat('${c}')">${c}</div>`).join('')}<div class="chip active" onclick="filterProductByCat('all')">All</div></div>
        <div id="recommendedSection"></div>
        <div id="allProductsSection"></div>`;
    filterProductList();
}

let activeProductCat = 'all';
function filterProductByCat(cat) { 
    activeProductCat = cat; 
    let chips = document.querySelectorAll('#productFilters .chip');
    chips.forEach(c => c.classList.remove('active'));
    if(cat !== 'all') event.target.classList.add('active');
    else chips[chips.length-1].classList.add('active');
    filterProductList(); 
}

function getRecommendationScore(product) {
    let score = 0;
    if (userPreferences.categories.includes(product.category)) score += 30;
    if (savedVendors.some(s => s.id === product.vendor?.id)) score += 25;
    if (followedVendors.some(f => f.id === product.vendor?.id)) score += 20;
    if (activityLog.lastViewedVendor && product.vendor?.business_name === activityLog.lastViewedVendor) score += 15;
    if (activityLog.lastViewedProduct && product.name === activityLog.lastViewedProduct) score += 10;
    if (product.price >= userPreferences.priceMin && product.price <= userPreferences.priceMax) score += 5;
    return score;
}

function filterProductList() {
    let query = document.getElementById('productSearch')?.value.toLowerCase() || '';
    let filtered = allProducts.filter(p => {
        let matchesSearch = p.name.toLowerCase().includes(query) || (p.category && p.category.toLowerCase().includes(query));
        let matchesCategory = (activeProductCat === 'all') || (p.category === activeProductCat);
        return matchesSearch && matchesCategory;
    });
    
    let recommended = filtered.filter(p => getRecommendationScore(p) > 0).sort((a,b) => getRecommendationScore(b) - getRecommendationScore(a)).slice(0,8);
    let allFiltered = filtered.sort((a,b) => a.name.localeCompare(b.name));
    
    let recSection = document.getElementById('recommendedSection');
    if (recSection) {
        if (recommended.length > 0) {
            recSection.innerHTML = `<div class="card suggestion-card"><h4><i class="fas fa-star" style="color:#3a7b4d"></i> Recommended for You</h4><p class="text-secondary" style="font-size:12px">Based on your preferences and activity</p><div class="product-grid mt-2">${recommended.map(p => productCard(p)).join('')}</div></div>`;
        } else {
            recSection.innerHTML = '';
        }
    }
    
    let allSection = document.getElementById('allProductsSection');
    if (allSection) {
        if (allFiltered.length > 0) {
            allSection.innerHTML = `<h4 class="mt-3">All Products (${allFiltered.length})</h4><div class="product-grid">${allFiltered.map(p => productCard(p)).join('')}</div>`;
        } else {
            allSection.innerHTML = '<div class="card text-center">No products found. Try adjusting your filters.</div>';
        }
    }
}

function productCard(p) {
    let imageUrl = '';
    if (p.images && p.images.length > 0) {
        if (typeof p.images[0] === 'string') imageUrl = p.images[0];
        else if (p.images[0].thumbnail) imageUrl = p.images[0].thumbnail;
        else if (p.images[0].full) imageUrl = p.images[0].full;
    }
    
    let priceHtml = `<span class="product-price">₱${p.price}</span>`;
    if (p.priceTiers && p.priceTiers.length > 0) {
        let bestTier = p.priceTiers.reduce((best, tier) => (tier.price < best.price ? tier : best), p.priceTiers[0]);
        priceHtml = `<span class="product-price">₱${bestTier.price}</span> <span class="badge" style="background:#e3f5e3;padding:2px 6px;border-radius:12px;font-size:10px">${bestTier.minQty}+ for ₱${bestTier.price}</span>`;
    }
    
    return `<div class="product-card" onclick="showProductAndVendor('${p.id}', '${p.vendor?.id}')">
        <div class="product-image">${imageUrl ? `<img src="${imageUrl}" onerror="this.src='https://placehold.co/400x400/f0f4f0/8da38d?text=No+Image'">` : '<i class="fas fa-utensils" style="font-size:32px;color:#8da38d"></i>'}</div>
        <div class="product-info">
            <div class="product-name">${escapeHtml(p.name)}</div>
            <div>${priceHtml}</div>
            <div class="text-secondary" style="font-size:10px">${escapeHtml(p.vendor?.business_name || '')}</div>
        </div>
    </div>`;
}

function showProductAndVendor(productId, vendorId) {
    let product = allProducts.find(p => p.id == productId);
    if(product) {
        activityLog.lastViewedProduct = product.name;
        let priceInfo = `₱${product.price}`;
        if (product.priceTiers && product.priceTiers.length) {
            priceInfo += ` (bulk: ${product.priceTiers.map(t => `${t.minQty}+ = ₱${t.price}`).join(', ')})`;
        }
        showToast(`${product.name} - ${priceInfo}`);
        if(vendorId) showVendorModal(vendorId);
    }
}

async function showVendorModal(vendorId) {
    let v = allVendors.find(v => v.id === vendorId);
    if (!v) return;
    activityLog.lastViewedVendor = v.business_name;
    let isSaved = savedVendors.some(s => s.id === v.id);
    let isFollowed = followedVendors.some(f => f.id === vendorId);
    let products = allProducts.filter(p => p.vendor?.id === vendorId);
    let vendorPostsList = await loadVendorPosts(vendorId);
    
    document.getElementById('modalTitle').innerHTML = escapeHtml(v.business_name);
    document.getElementById('modalBody').innerHTML = `
        <div class="flex gap-2 mb-3">
            <button class="btn-outline btn-sm" onclick="followVendor('${v.id}')"><i class="fas ${isFollowed ? 'fa-bell-slash' : 'fa-bell'}"></i> ${isFollowed ? 'Unfollow' : 'Follow'}</button>
            <button class="btn-outline btn-sm" onclick="toggleSave('${v.id}')"><i class="fas ${isSaved ? 'fa-trash' : 'fa-bookmark'}"></i> ${isSaved ? 'Unsave' : 'Save'}</button>
            <button class="btn-outline btn-sm" onclick="getDirections(${v.latitude}, ${v.longitude}, '${escapeHtml(v.business_name)}')"><i class="fas fa-directions"></i> Directions</button>
        </div>
        <div class="text-secondary">${escapeHtml(v.category)} • ${Math.round(v.distance) || '?'}m away</div>
        <div class="stars mt-1">${'★'.repeat(Math.floor(v.rating||0))} <span class="text-secondary">(${v.review_count||0} reviews)</span></div>
        <div class="mt-3"><strong>Menu</strong></div>
        ${products.map(p => `<div class="flex justify-between items-center py-2 border-b cursor-pointer" onclick="showProductAndVendor('${p.id}', '${v.id}')"><div>${escapeHtml(p.name)}${p.priceTiers && p.priceTiers.length ? `<small class="price-tier-badge">${p.priceTiers[0].minQty}+ for ₱${p.priceTiers[0].price}</small>` : ''}</div><div class="product-price">₱${p.price}</div></div>`).join('') || '<div class="text-secondary">No menu items yet</div>'}
        ${vendorPostsList.length ? `<div class="mt-3"><strong>Vendor Posts</strong></div>${vendorPostsList.slice(0,3).map(post => `<div class="mt-2 pt-2 border-t"><div class="post-content" style="font-size:13px">${escapeHtml(post.content.substring(0,100))}${post.content.length>100?'...':''}</div><div class="text-secondary" style="font-size:11px">${timeAgo(post.created_at)} • ${post.likes || 0} likes</div></div>`).join('')}` : ''}
        <button class="btn-outline mt-3" onclick="openReviewModal('${v.id}')"><i class="fas fa-star"></i> Write a Review</button>
        <div id="reviewsList" class="mt-3"></div>`;
    document.getElementById('vendorModal').classList.add('show');
    loadVendorReviews(vendorId);
}

async function loadVendorReviews(vendorId) {
    let data = await api(`/api/customer/reviews/${vendorId}`);
    let reviewsDiv = document.getElementById('reviewsList');
    if (data?.reviews && data.reviews.length) {
        reviewsDiv.innerHTML = `<strong>Customer Reviews</strong>` + data.reviews.slice(0,5).map(r => `<div class="mt-2 pt-2 border-t"><div class="stars">${'★'.repeat(r.rating)}</div><p class="text-secondary">${escapeHtml(r.comment || '')}</p><small>${new Date(r.created_at).toLocaleDateString()}</small></div>`).join('');
    }
}

async function followVendor(id) {
    await api('/api/customer/follow-vendor', { method: 'POST', body: JSON.stringify({ vendor_id: id }) });
    await loadFollows();
    closeModal();
    showVendorModal(id);
}

async function toggleSave(id) {
    await api('/api/customer/shortlist/toggle', { method: 'POST', body: JSON.stringify({ vendor_id: id }) });
    await loadSaved();
    closeModal();
    showVendorModal(id);
}

function openReviewModal(vendorId) {
    currentReviewVendorId = vendorId;
    currentRating = 0;
    document.querySelectorAll('.review-star').forEach(s => s.style.color = '#ddd');
    document.getElementById('reviewModal').classList.add('show');
}

async function submitReview() {
    if (currentRating === 0) { showToast('Please select a rating'); return; }
    let comment = document.getElementById('reviewComment').value;
    await api('/api/customer/review/create', { method: 'POST', body: JSON.stringify({ vendor_id: currentReviewVendorId, rating: currentRating, comment: comment }) });
    showToast('Thank you for your review!');
    closeReviewModal();
    closeModal();
}

document.addEventListener('click', function(e) {
    let star = e.target.closest('.review-star');
    if (star && document.getElementById('reviewModal').classList.contains('show')) {
        currentRating = parseInt(star.dataset.rating);
        document.querySelectorAll('.review-star').forEach((s, i) => { s.style.color = i < currentRating ? '#f5b042' : '#ddd'; });
    }
});

function getDirections(lat, lng, name) {
    if (!userLocation) { showToast('Getting your location...'); return; }
    let modal = document.getElementById('minimapModal');
    modal.classList.add('show');
    setTimeout(() => {
        if (minimap) minimap.remove();
        minimap = L.map('minimapContainer', { zoomControl: true }).setView([(userLocation.lat + lat)/2, (userLocation.lng + lng)/2], 13);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png').addTo(minimap);
        L.circle([userLocation.lat, userLocation.lng], { radius: 10, color: '#3a7b4d', fillColor: '#3a7b4d', fillOpacity: 0.8 }).addTo(minimap).bindPopup('You are here');
        L.marker([lat, lng]).bindPopup(`<b>${escapeHtml(name)}</b>`).addTo(minimap);
    }, 100);
}

function centerMinimap() { if (minimap && userLocation) minimap.setView([userLocation.lat, userLocation.lng], 15); }
function openGoogleMaps() { if (userLocation) window.open(`https://www.google.com/maps/dir/${userLocation.lat},${userLocation.lng}`, '_blank'); }
function closeMinimap() { document.getElementById('minimapModal').classList.remove('show'); }

async function showFeed() {
    await loadFeed();
    document.getElementById('content').innerHTML = `<div class="flex justify-between items-center mb-3"><h3>Community Feed</h3><button class="btn-outline btn-sm" onclick="openPostModal()"><i class="fas fa-plus"></i> Create Post</button></div><div id="feedList"></div>`;
    
    document.getElementById('feedList').innerHTML = allPosts.map(p => `
        <div class="card">
            <div class="flex justify-between items-start">
                <div class="flex items-center gap-2">
                    <div class="avatar avatar-sm" style="width:40px;height:40px;font-size:18px;cursor:pointer" onclick="showUserProfile('${p.user_id}')"><i class="fas fa-user-circle"></i></div>
                    <div style="cursor:pointer" onclick="showUserProfile('${p.user_id}')"><strong>${escapeHtml(p.author || 'Food Lover')}</strong><div class="text-secondary">${timeAgo(p.created_at)}</div></div>
                </div>
            </div>
            <p class="mt-2">${escapeHtml(p.content)}</p>
            ${p.images && p.images.length ? `<div class="image-grid mt-2">${p.images.slice(0,3).map(img => `<div class="image-thumb"><img src="${img.thumbnail || img}"></div>`).join('')}</div>` : ''}
            <div class="post-actions">
                <button class="post-action-btn ${p.user_liked ? 'liked' : ''}" onclick="likePost('${p.id}', this)"><i class="far fa-heart"></i> <span class="like-count">${p.likes || 0}</span></button>
                <button class="post-action-btn" onclick="toggleComments('${p.id}')"><i class="far fa-comment"></i> <span id="commentCount-${p.id}">${p.comment_count || 0}</span></button>
                <button class="post-action-btn" onclick="openShareModal('${p.id}')"><i class="far fa-share-alt"></i> Share</button>
            </div>
            <div id="comments-${p.id}" style="display:none" class="comment-thread"></div>
        </div>
    `).join('');
}

async function loadComments(postId) {
    let data = await api(`/api/customer/post/comments/${postId}`);
    let comments = data?.comments || [];
    let div = document.getElementById(`comments-${postId}`);
    if (div) {
        if (comments.length === 0) div.innerHTML = '<div class="text-secondary text-center">No comments yet. Be the first!</div>';
        else div.innerHTML = comments.map(c => `
            <div class="comment-item">
                <div class="comment-author" onclick="showUserProfile('${c.user_id}')"><strong>${escapeHtml(c.author || 'User')}</strong></div>
                <div>${escapeHtml(c.content)}</div>
                <div class="flex justify-between mt-1">
                    <small>${timeAgo(c.created_at)}</small>
                    ${c.user_id === currentUserId ? `<button class="btn-outline btn-sm delete-btn" onclick="deleteComment('${c.id}', '${postId}')" style="color:#e53935;border-color:#e53935">Delete</button>` : ''}
                </div>
            </div>
        `).join('');
        div.innerHTML += `<div class="mt-2"><button class="btn-outline btn-sm" onclick="openReplyModal('${postId}')"><i class="fas fa-reply"></i> Write a reply</button></div>`;
    }
}

async function deleteComment(commentId, postId) {
    if (!confirm('Delete this comment?')) return;
    let res = await api('/api/customer/comment/delete', { method: 'POST', body: JSON.stringify({ comment_id: commentId }) });
    if (res && res.success) {
        await loadComments(postId);
        await loadFeed();
        let countSpan = document.getElementById(`commentCount-${postId}`);
        if (countSpan) countSpan.innerText = Math.max(0, (parseInt(countSpan.innerText) || 0) - 1);
        showToast('Comment deleted');
    }
}

async function likePost(postId, btn) {
    let res = await api('/api/customer/like', { method: 'POST', body: JSON.stringify({ post_id: postId }) });
    if (res && res.success) {
        let span = btn.querySelector('.like-count');
        let count = parseInt(span.innerText) || 0;
        if (res.liked) { btn.classList.add('liked'); span.innerText = count + 1; }
        else { btn.classList.remove('liked'); span.innerText = Math.max(0, count - 1); }
        await loadFeed();
    }
}

function toggleComments(postId) {
    let el = document.getElementById(`comments-${postId}`);
    if (el.style.display === 'none') { el.style.display = 'block'; loadComments(postId); }
    else el.style.display = 'none';
}

function openReplyModal(postId) { document.getElementById('replyPostId').value = postId; document.getElementById('replyContent').value = ''; document.getElementById('replyModal').classList.add('show'); }
async function submitReply() {
    let postId = document.getElementById('replyPostId').value;
    let content = document.getElementById('replyContent').value;
    if (!content) { showToast('Write something'); return; }
    let res = await api('/api/customer/comment', { method: 'POST', body: JSON.stringify({ post_id: postId, comment: content }) });
    if (res && res.success) {
        closeReplyModal();
        await loadComments(postId);
        await loadFeed();
        let countSpan = document.getElementById(`commentCount-${postId}`);
        if (countSpan) countSpan.innerText = (parseInt(countSpan.innerText) || 0) + 1;
        showToast('Reply posted!');
    }
}
function closeReplyModal() { document.getElementById('replyModal').classList.remove('show'); }
function openPostModal() { document.getElementById('postModal').classList.add('show'); }
function closePostModal() { document.getElementById('postModal').classList.remove('show'); }
function previewPostImages(input) { let preview = document.getElementById('postImagePreview'); preview.innerHTML = ''; for(let f of input.files){ let reader=new FileReader(); reader.onload=e=>{ preview.innerHTML+=`<div class="image-thumb"><img src="${e.target.result}"></div>`; }; reader.readAsDataURL(f); } }
async function createPost() {
    let content = document.getElementById('postContent').value;
    if (!content) { showToast('Write something first!'); return; }
    let files = document.getElementById('postImages').files;
    let images = [];
    for(let file of files){
        let imgData = await new Promise(resolve => { let reader = new FileReader(); reader.onload = e => resolve(e.target.result); reader.readAsDataURL(file); });
        images.push(imgData);
    }
    let res = await api('/api/customer/post/create', { method: 'POST', body: JSON.stringify({ content, images }) });
    if(res && res.success){ closePostModal(); await loadFeed(); showFeed(); showToast('Post shared!'); }
}
function showProfile() {
    let myPostsCount = allPosts.filter(p => p.user_id === currentUserId).length;
    let likedCount = allPosts.filter(p => p.user_liked).length;
    document.getElementById('content').innerHTML = `
        <div class="card text-center"><div class="avatar-lg"><i class="fas fa-user-circle"></i></div><h3 class="mt-2">${escapeHtml(userProfile?.full_name || 'Food Explorer')}</h3><p class="text-secondary">${escapeHtml(userProfile?.email || '')}</p><div class="profile-stats"><div class="stat-card" onclick="showSavedVendors()"><div class="stat-value">${savedVendors.length}</div><div class="stat-label">Saved</div></div><div class="stat-card" onclick="showFollowedVendors()"><div class="stat-value">${followedVendors.length}</div><div class="stat-label">Following</div></div><div class="stat-card" onclick="showMyPosts()"><div class="stat-value">${myPostsCount}</div><div class="stat-label">Posts</div></div></div><button class="btn-outline mt-2" onclick="openProfileModal()">Edit Profile</button></div>
        <div class="card mt-3"><h4>Recent Activity</h4>${activityLog.lastViewedVendor ? `<div class="activity-item"><div class="activity-icon"><i class="fas fa-store"></i></div><div>Last viewed vendor: <strong>${escapeHtml(activityLog.lastViewedVendor)}</strong></div></div>` : ''}${activityLog.lastViewedProduct ? `<div class="activity-item"><div class="activity-icon"><i class="fas fa-utensils"></i></div><div>Last viewed product: <strong>${escapeHtml(activityLog.lastViewedProduct)}</strong></div></div>` : ''}${!activityLog.lastViewedVendor && !activityLog.lastViewedProduct ? '<div class="text-secondary text-center">No recent activity yet</div>' : ''}</div>
        <div class="card"><div class="flex justify-between items-center"><h4>Liked Posts (${likedCount})</h4>${likedCount > 0 ? `<button class="btn-outline btn-sm" onclick="showLikedPosts()">View All</button>` : ''}</div><div id="likedPreview"></div></div>`;
    let likedPreview = document.getElementById('likedPreview');
    if(likedPreview){
        let liked = allPosts.filter(p => p.user_liked).slice(0,3);
        likedPreview.innerHTML = liked.map(p => `<div class="activity-item" style="cursor:pointer" onclick="showFeed()"><div class="activity-icon"><i class="fas fa-heart" style="color:#e53935"></i></div><div><div>${escapeHtml(p.content.substring(0,60))}${p.content.length>60?'...':''}</div><div class="text-secondary" style="font-size:11px">by ${escapeHtml(p.author || 'User')}</div></div></div>`).join('') || '<div class="text-secondary text-center">No liked posts yet</div>';
    }
}
function showMyPosts() { let myPosts = allPosts.filter(p => p.user_id === currentUserId); document.getElementById('content').innerHTML = `<div class="flex justify-between items-center mb-3"><h3>My Posts (${myPosts.length})</h3><button class="btn-outline btn-sm" onclick="showPage('profile')">Back</button></div>${myPosts.map(p => `<div class="card"><p>${escapeHtml(p.content)}</p><div class="text-secondary mt-1">${p.likes || 0} likes · ${p.comment_count || 0} comments</div><div class="text-secondary mt-1"><small>${new Date(p.created_at).toLocaleString()}</small></div></div>`).join('') || '<div class="card text-center">No posts yet</div>'}`; }
function showLikedPosts() { let likedPostsList = allPosts.filter(p => p.user_liked); document.getElementById('content').innerHTML = `<div class="flex justify-between items-center mb-3"><h3>Liked Posts (${likedPostsList.length})</h3><button class="btn-outline btn-sm" onclick="showPage('profile')">Back</button></div>${likedPostsList.map(p => `<div class="card" onclick="showFeed()"><p>${escapeHtml(p.content)}</p><div class="text-secondary mt-1">by ${escapeHtml(p.author || 'User')} · ${p.likes || 0} likes</div></div>`).join('') || '<div class="card text-center">No liked posts yet</div>'}`; }
async function openProfileModal() { let profile = await api('/api/customer/profile'); document.getElementById('profileName').value = profile?.full_name || ''; document.getElementById('profilePhone').value = profile?.phone || ''; document.getElementById('profileModal').classList.add('show'); }
async function saveProfile() { await api('/api/customer/update-profile', { method: 'POST', body: JSON.stringify({ full_name: document.getElementById('profileName').value, phone: document.getElementById('profilePhone').value }) }); showToast('Profile updated'); closeProfileModal(); await loadProfile(); showProfile(); }
function closeProfileModal() { document.getElementById('profileModal').classList.remove('show'); }
function closeReviewModal() { document.getElementById('reviewModal').classList.remove('show'); }
function closePreferencesModal() { document.getElementById('preferencesModal').classList.remove('show'); }
function closeAnalyticsModal() { document.getElementById('analyticsModal').classList.remove('show'); }
function closeModal() { document.getElementById('vendorModal').classList.remove('show'); }
function closeUserProfileModal() { document.getElementById('userProfileModal').classList.remove('show'); }
function toggleMenu() { document.getElementById('hamburgerMenu').classList.toggle('show'); }
function closeMenu() { document.getElementById('hamburgerMenu').classList.remove('show'); }
function openShareModal(postId) { window.open(`https://www.facebook.com/sharer/sharer.php?u=${window.location.origin}/post/${postId}`, '_blank'); }
async function showUserProfile(userId) {
    if (userId === currentUserId) { showPage('profile'); return; }
    let data = await api(`/api/customer/user/profile/${userId}`);
    if(data){
        document.getElementById('userProfileTitle').innerHTML = escapeHtml(data.full_name || 'User Profile');
        document.getElementById('userProfileBody').innerHTML = `<div class="text-center"><div class="avatar-lg" style="margin:0 auto 16px"><i class="fas fa-user-circle"></i></div><h3>${escapeHtml(data.full_name || 'Food Lover')}</h3><p class="text-secondary">${escapeHtml(data.email || '')}</p><div class="profile-stats"><div class="stat-card"><div class="stat-value">${data.post_count || 0}</div><div class="stat-label">Posts</div></div><div class="stat-card"><div class="stat-value">${data.follower_count || 0}</div><div class="stat-label">Followers</div></div><div class="stat-card"><div class="stat-value">${data.following_count || 0}</div><div class="stat-label">Following</div></div></div></div>`;
        document.getElementById('userProfileModal').classList.add('show');
    }
}
function showPreferences() {
    let allCategories = [...new Set(allProducts.map(p => p.category).filter(c => c))].sort();
    document.getElementById('prefCategories').innerHTML = allCategories.map(c => `<div class="chip ${userPreferences.categories.includes(c) ? 'active' : ''}" onclick="togglePrefCategory('${c}')">${c}</div>`).join('');
    document.getElementById('prefPriceMin').value = userPreferences.priceMin;
    document.getElementById('prefPriceMax').value = userPreferences.priceMax;
    document.getElementById('prefDistance').value = userPreferences.maxDistance;
    document.getElementById('prefPriceMinVal').innerText = userPreferences.priceMin;
    document.getElementById('prefPriceMaxVal').innerText = userPreferences.priceMax;
    document.getElementById('prefDistanceVal').innerText = userPreferences.maxDistance + 'm';
    document.getElementById('prefPriceMin').oninput = () => { document.getElementById('prefPriceMinVal').innerText = document.getElementById('prefPriceMin').value; };
    document.getElementById('prefPriceMax').oninput = () => { document.getElementById('prefPriceMaxVal').innerText = document.getElementById('prefPriceMax').value; };
    document.getElementById('prefDistance').oninput = () => { document.getElementById('prefDistanceVal').innerText = document.getElementById('prefDistance').value + 'm'; };
    document.getElementById('preferencesModal').classList.add('show');
}
function togglePrefCategory(cat) { let idx = userPreferences.categories.indexOf(cat); if (idx === -1) userPreferences.categories.push(cat); else userPreferences.categories.splice(idx, 1); showPreferences(); }
async function savePreferences() { userPreferences.priceMin = parseInt(document.getElementById('prefPriceMin').value); userPreferences.priceMax = parseInt(document.getElementById('prefPriceMax').value); userPreferences.maxDistance = parseInt(document.getElementById('prefDistance').value); await api('/api/customer/update-preferences', { method: 'POST', body: JSON.stringify(userPreferences) }); showToast('Preferences saved!'); closePreferencesModal(); if (page === 'map') updateNearbyList(); if (page === 'products') filterProductList(); }
function showAnalytics() {
    let myPostsCount = allPosts.filter(p => p.user_id === currentUserId).length;
    let likedCount = allPosts.filter(p => p.user_liked).length;
    document.getElementById('analyticsContent').innerHTML = `<div class="profile-stats"><div class="stat-card"><div class="stat-value">${savedVendors.length + followedVendors.length}</div><div class="stat-label">Interactions</div></div><div class="stat-card"><div class="stat-value">${myPostsCount}</div><div class="stat-label">My Posts</div></div><div class="stat-card"><div class="stat-value">${likedCount}</div><div class="stat-label">Liked</div></div></div><div class="card mt-3"><h4>Recent Activity</h4>${activityLog.lastViewedVendor ? `<div class="activity-item"><div class="activity-icon"><i class="fas fa-store"></i></div><div>Last vendor: ${escapeHtml(activityLog.lastViewedVendor)}</div></div>` : ''}${activityLog.lastViewedProduct ? `<div class="activity-item"><div class="activity-icon"><i class="fas fa-utensils"></i></div><div>Last product: ${escapeHtml(activityLog.lastViewedProduct)}</div></div>` : ''}</div>`;
    document.getElementById('analyticsModal').classList.add('show');
}
function confirmLogout() { if(confirm('Logout from Lako?')) { if(watchId) navigator.geolocation.clearWatch(watchId); localStorage.clear(); window.location.href = '/'; } }

// Load Leaflet and dependencies
(function loadLibraries() {
    if(document.querySelector('link[href*="leaflet.css"]')) return;
    let leafletCSS = document.createElement('link');
    leafletCSS.rel = 'stylesheet';
    leafletCSS.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    document.head.appendChild(leafletCSS);
    
    let leafletScript = document.createElement('script');
    leafletScript.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    leafletScript.onload = () => {
        let clusterScript = document.createElement('script');
        clusterScript.src = 'https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js';
        document.head.appendChild(clusterScript);
        
        let heatScript = document.createElement('script');
        heatScript.src = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet.heat/0.2.0/leaflet-heat.js';
        document.head.appendChild(heatScript);
        
        if(page === 'map') setTimeout(showMap, 100);
    };
    document.head.appendChild(leafletScript);
})();

loadData();
</script>
''')

VENDOR_DASH = render_page("Vendor Dashboard", '''
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#f5f8f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
.app-bar{background:white;padding:14px 20px;display:flex;gap:16px;border-bottom:1px solid #e8ece8;position:sticky;top:0;z-index:100}
.back-btn{background:#eff3ef;border:none;width:40px;height:40px;border-radius:50%;cursor:pointer;font-size:18px;color:#3a7b4d}
.back-btn:active{transform:scale(0.95)}
.app-bar-title{font-size:18px;font-weight:600;color:#2c3e2c;flex:1}
.menu-btn{background:#eff3ef;border:none;width:40px;height:40px;border-radius:50%;cursor:pointer;font-size:18px;color:#3a7b4d}
.content{padding:20px 16px;max-width:500px;margin:0 auto;min-height:calc(100vh - 140px);padding-bottom:90px}
.bottom-nav{position:fixed;bottom:0;left:0;right:0;background:white;display:flex;justify-content:space-around;padding:8px 16px 22px;border-top:1px solid #e8ece8;max-width:500px;margin:0 auto;z-index:99}
.nav-item{display:flex;flex-direction:column;align-items:center;gap:5px;color:#9aae9a;font-size:11px;cursor:pointer}
.nav-item i{font-size:22px}
.nav-item.active{color:#3a7b4d}
.nav-item span{font-size:11px;font-weight:500}
.card{background:white;border-radius:24px;padding:20px;margin-bottom:16px;box-shadow:0 2px 8px rgba(0,0,0,0.04);border:1px solid #edf2ed}
.btn{width:100%;padding:14px;background:#3a7b4d;color:white;border:none;border-radius:44px;font-size:15px;font-weight:600;cursor:pointer}
.btn:active{transform:scale(0.97);background:#2e6640}
.btn-outline{background:white;border:1.5px solid #3a7b4d;color:#3a7b4d;padding:12px;border-radius:44px;font-size:14px;font-weight:500;cursor:pointer}
.btn-outline:active{background:#f0f6f0}
.btn-sm{padding:8px 18px;font-size:13px;width:auto}
.badge{background:#eff6ef;padding:4px 14px;border-radius:30px;font-size:12px;color:#3a7b4d}
.text-secondary{color:#8da38d;font-size:13px}
.text-center{text-align:center}
.mt-1{margin-top:4px}.mt-2{margin-top:8px}.mt-3{margin-top:12px}.mt-4{margin-top:16px}
.flex{display:flex}.justify-between{justify-content:space-between}.items-center{align-items:center}.gap-2{gap:8px}.gap-3{gap:12px}
.stats-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:20px}
.stat-card{background:linear-gradient(145deg,#ffffff,#f8fbf8);border-radius:24px;padding:18px 12px;text-align:center;border:1px solid rgba(58,123,77,0.1)}
.stat-value{font-size:32px;font-weight:800;color:#3a7b4d}
.stat-label{font-size:12px;color:#8da38d;margin-top:6px}
.product-card{background:white;border-radius:20px;padding:16px;margin-bottom:12px;border:1px solid #edf2ed}
.product-price{font-size:20px;font-weight:700;color:#3a7b4d}
.image-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.image-thumb{width:100%;aspect-ratio:1;border-radius:12px;overflow:hidden;background:#f4f7f4}
.image-thumb img{width:100%;height:100%;object-fit:cover}
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.4);backdrop-filter:blur(4px);z-index:1000;align-items:center;justify-content:center;padding:20px}
.modal.show{display:flex}
.modal-content{background:white;border-radius:28px;max-width:500px;width:100%;max-height:85vh;overflow-y:auto;padding:24px}
.modal-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;font-size:20px;font-weight:700;color:#2c3e2c}
.modal-close{font-size:28px;cursor:pointer;color:#9aae9a;padding:8px}
.hamburger-menu{position:fixed;top:0;right:-280px;width:280px;height:100vh;background:white;z-index:200;box-shadow:-2px 0 10px rgba(0,0,0,0.1);transition:right 0.3s;padding:60px 20px}
.hamburger-menu.show{right:0}
.close-hamburger{position:absolute;top:20px;right:20px;background:#eff3ef;border:none;width:36px;height:36px;border-radius:50%;cursor:pointer;font-size:16px;color:#3a7b4d}
.menu-item{padding:14px 16px;display:flex;align-items:center;gap:14px;cursor:pointer;border-radius:16px;font-size:15px}
.menu-item:active{background:#eff3ef}
.menu-divider{height:1px;background:#edf2ed;margin:12px 0}
.toast{position:fixed;bottom:90px;left:20px;right:20px;background:#2c3e2c;color:white;padding:14px 20px;border-radius:60px;text-align:center;z-index:1000;animation:fadeInUp 0.3s}
@keyframes fadeInUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
.input{width:100%;padding:14px 16px;border:1.5px solid #e3eae3;border-radius:16px;font-size:15px;margin-bottom:12px;background:#fefefe}
.input:focus{outline:none;border-color:#3a7b4d}
.product-images-container{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
.image-preview{position:relative;width:80px;height:80px}
.image-preview img{width:100%;height:100%;border-radius:12px;object-fit:cover;border:1px solid #edf2ed}
.remove-img{position:absolute;top:-8px;right:-8px;background:#e57373;color:white;border-radius:50%;width:20px;height:20px;display:flex;align-items:center;justify-content:center;font-size:11px;cursor:pointer}
.open-toggle{display:flex;align-items:center;justify-content:space-between;padding:14px 18px;background:#fafdfa;border-radius:30px;margin-bottom:20px;border:1px solid #e3eae3}
.toggle-switch{position:relative;display:inline-block;width:52px;height:26px}
.toggle-switch input{opacity:0;width:0;height:0}
.slider{position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;background-color:#d0dfd0;transition:0.3s;border-radius:26px}
.slider:before{position:absolute;content:"";height:20px;width:20px;left:3px;bottom:3px;background-color:white;border-radius:50%}
input:checked+.slider{background-color:#3a7b4d}
input:checked+.slider:before{transform:translateX(26px)}
.open-status{display:inline-block;padding:5px 14px;border-radius:30px;font-size:12px;font-weight:600}
.open-status.open{background:#e3f5e3;color:#3a7b4d}
.open-status.closed{background:#ffe8e6;color:#e57373}
.post-card{background:white;border-radius:20px;padding:16px;margin-bottom:12px;border:1px solid #edf2ed}
.post-header{display:flex;align-items:center;gap:12px;margin-bottom:12px}
.post-avatar{width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,#3a7b4d,#2e6640);display:flex;align-items:center;justify-content:center;color:white;font-size:20px}
.post-stats{display:flex;gap:18px;margin-top:8px;padding-top:8px;border-top:1px solid #edf2ed}
.post-stats span{font-size:12px;color:#9aae9a}
.upload-area{background:#fafdfa;border:2px dashed #cde0cd;border-radius:20px;padding:20px;text-align:center;cursor:pointer;margin:12px 0}
.upload-area i{font-size:32px;color:#3a7b4d;margin-bottom:10px;display:block}
.confirm-modal{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.4);z-index:4000;display:flex;align-items:center;justify-content:center;padding:20px}
.confirm-content{background:white;border-radius:28px;max-width:320px;width:100%;padding:24px;text-align:center}
.confirm-buttons{display:flex;gap:12px;margin-top:16px}
.heatmap-container{height:180px;background:#eef2ee;border-radius:24px;margin:16px 0;display:flex;align-items:center;justify-content:center}
</style>

<div class="app-bar">
    <button class="back-btn" onclick="confirmLogout()"><i class="fas fa-sign-out-alt"></i></button>
    <div class="app-bar-title">Lako Vendor</div>
    <button class="menu-btn" onclick="toggleMenu()"><i class="fas fa-bars"></i></button>
</div>

<div id="hamburgerMenu" class="hamburger-menu">
    <button class="close-hamburger" onclick="toggleMenu()"><i class="fas fa-times"></i></button>
    <div class="menu-item" onclick="showAnalytics()"><i class="fas fa-chart-line"></i> Analytics</div>
    <div class="menu-divider"></div>
    <div class="menu-item" onclick="showTutorial()"><i class="fas fa-question-circle"></i> Tutorial</div>
    <div class="menu-divider"></div>
    <div class="menu-item" onclick="confirmLogout()"><i class="fas fa-sign-out-alt"></i> Logout</div>
</div>

<div class="bottom-nav">
    <div class="nav-item active" onclick="showPage('dashboard')"><i class="fas fa-home"></i><span>Home</span></div>
    <div class="nav-item" onclick="showPage('products')"><i class="fas fa-utensils"></i><span>Menu</span></div>
    <div class="nav-item" onclick="showPage('reviews')"><i class="fas fa-star"></i><span>Reviews</span></div>
    <div class="nav-item" onclick="showPage('posts')"><i class="fas fa-newspaper"></i><span>Posts</span></div>
    <div class="nav-item" onclick="showPage('profile')"><i class="fas fa-user"></i><span>Profile</span></div>
    <div class="nav-item" onclick="showPage('settings')"><i class="fas fa-sliders-h"></i><span>Settings</span></div>
</div>

<div class="content" id="content"></div>

<!-- Modals -->
<div id="productModal" class="modal"><div class="modal-content"><div class="modal-header"><h3 id="modalTitle">Add Product</h3><span class="modal-close" onclick="closeProductModal()">&times;</span></div><div id="modalBody"></div></div></div>
<div id="postModal" class="modal"><div class="modal-content"><div class="modal-header"><h3>Create Post</h3><span class="modal-close" onclick="closePostModal()">&times;</span></div><textarea id="postContent" class="input" rows="4" placeholder="Share news, promotions, or updates..."></textarea><div class="upload-area" onclick="document.getElementById('postImages').click()"><i class="fas fa-image"></i><div>Add photos (required)</div></div><input type="file" id="postImages" multiple accept="image/*" style="display:none" onchange="previewPostImages(this)"><div id="postImagePreview" class="product-images-container"></div><button class="btn" onclick="createPost()">Publish Post</button></div></div>
<div id="locationModal" class="modal"><div class="modal-content"><div class="modal-header"><h3>Update Location</h3><span class="modal-close" onclick="closeLocationModal()">&times;</span></div><div id="locationMap" style="height:280px;background:#eef2ee;border-radius:20px"></div><button class="btn mt-3" onclick="saveNewLocation()">Confirm Location</button></div></div>
<div id="logoModal" class="modal"><div class="modal-content"><div class="modal-header"><h3>Update Logo</h3><span class="modal-close" onclick="closeLogoModal()">&times;</span></div><div class="upload-area" onclick="document.getElementById('logoInput').click()"><i class="fas fa-image"></i><div>Upload new logo</div></div><input type="file" id="logoInput" accept="image/*" style="display:none" onchange="updateLogo(this)"><div id="logoPreview"></div><button class="btn-outline mt-3" onclick="removeLogo()">Remove Logo</button></div></div>
<div id="hoursModal" class="modal"><div class="modal-content"><div class="modal-header"><h3>Set Hours</h3><span class="modal-close" onclick="closeHoursModal()">&times;</span></div><div id="hoursBody"></div></div></div>
<div id="analyticsModal" class="modal"><div class="modal-content"><div class="modal-header"><h3>Analytics</h3><span class="modal-close" onclick="closeAnalyticsModal()">&times;</span></div><div id="analyticsContent"></div></div></div>
<div id="tutorialModal" class="tutorial-overlay" style="display:none"><div class="tutorial-card"><div id="tutorialContent"></div></div></div>

<script>
let sessionToken = localStorage.getItem('session_token');
let vendorData = null, products = [], posts = [];
let currentProductId = null, currentImages = [];
let isOpen = false;
let vendorProfile = null;

if (!sessionToken) window.location.href = '/auth';

function showToast(msg){ let t=document.querySelector('.toast'); if(t)t.remove(); t=document.createElement('div'); t.className='toast'; t.innerHTML='<i class="fas fa-info-circle"></i> '+msg; document.body.appendChild(t); setTimeout(()=>t.remove(),3000); }

async function api(url, options = {}) {
    const res = await fetch(url, { ...options, headers: { 'Content-Type': 'application/json', 'X-Session-Token': sessionToken, ...options.headers } });
    if (res.status === 401) { localStorage.clear(); window.location.href = '/auth'; return null; }
    return res.json();
}

async function loadData() { 
    const data = await api('/api/vendor/data'); 
    if (data) { 
        vendorData = data.vendor; 
        products = data.products || []; 
        posts = data.posts || [];
        isOpen = vendorData?.is_open || false;
    } 
}

async function loadVendorProfile() { const data = await api('/api/vendor/profile'); if (data) vendorProfile = data; }

function showPage(p) {
    const pages = ['dashboard', 'products', 'reviews', 'posts', 'profile', 'settings'];
    document.querySelectorAll('.nav-item').forEach((el, i) => el.classList.toggle('active', pages[i] === p));
    if (p === 'dashboard') showDashboard();
    else if (p === 'products') showProducts();
    else if (p === 'reviews') showReviews();
    else if (p === 'posts') showPosts();
    else if (p === 'profile') showProfile();
    else if (p === 'settings') showSettings();
}

async function showDashboard() {
    document.getElementById('content').innerHTML = '<div class="text-center mt-5"><i class="fas fa-spinner fa-pulse fa-2x"></i></div>';
    await loadData(); await loadVendorProfile();
    const analytics = await api('/api/vendor/analytics');
    const logoUrl = vendorData?.logo || null;
    document.getElementById('content').innerHTML = `
        <div class="card" style="background:linear-gradient(135deg,#3a7b4d,#2e6640);color:white">
            <div class="flex justify-between items-center">
                <div class="flex items-center gap-3">
                    ${logoUrl ? `<img src="${logoUrl}" style="width:60px;height:60px;border-radius:50%;object-fit:cover;border:2px solid white">` : `<div style="width:60px;height:60px;border-radius:50%;background:rgba(255,255,255,0.2);display:flex;align-items:center;justify-content:center"><i class="fas fa-store fa-2x"></i></div>`}
                    <div><p style="opacity:0.9;font-size:13px">Welcome,</p><h2 style="font-size:22px">${vendorProfile?.user_name || vendorData?.user_name || 'Vendor'}!</h2><p style="opacity:0.85;font-size:12px">${vendorData?.business_name}</p></div>
                </div>
                <button class="btn-outline btn-sm" style="background:rgba(255,255,255,0.2);border:none;color:white" onclick="openLogoModal()"><i class="fas fa-edit"></i></button>
            </div>
        </div>
        <div class="open-toggle"><div><label>Shop Status</label><div id="openStatusDisplay" class="mt-1">${isOpen ? '<span class="open-status open"> Open Now</span>' : '<span class="open-status closed"> Closed</span>'}</div></div><label class="toggle-switch"><input type="checkbox" id="openToggle" ${isOpen ? 'checked' : ''} onchange="toggleOpenStatus()"><span class="slider"></span></label></div>
        <div class="stats-grid"><div class="stat-card"><div class="stat-value">${vendorData?.rating || 'New'}</div><div class="stat-label">Rating</div></div><div class="stat-card"><div class="stat-value">${vendorData?.review_count || 0}</div><div class="stat-label">Reviews</div></div><div class="stat-card"><div class="stat-value">${analytics?.total_saves || 0}</div><div class="stat-label">Saves</div></div><div class="stat-card"><div class="stat-value">${analytics?.total_likes || 0}</div><div class="stat-label">Likes</div></div></div>
        <div class="card"><h3>Foot Traffic</h3><canvas id="trafficChart" style="height:160px"></canvas></div>
        <div class="heatmap-container"><i class="fas fa-map-marker-alt" style="font-size:36px;color:#3a7b4d;opacity:0.3"></i><span class="text-secondary ml-2">Heatmap based on customer GPS</span></div>
    `;
    setTimeout(() => {
        new Chart(document.getElementById('trafficChart'), { type: 'line', data: { labels: analytics?.weekly_labels || ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'], datasets: [{ label: 'Visitors', data: analytics?.weekly_traffic || [5,8,12,15,20,25,18], borderColor: '#3a7b4d', backgroundColor: 'rgba(58,123,77,0.05)', fill: true, tension: 0.3 }] } });
    }, 100);
}

async function toggleOpenStatus() { isOpen = !isOpen; await api('/api/vendor/update-open-status', { method: 'POST', body: JSON.stringify({ is_open: isOpen }) }); showDashboard(); showToast(isOpen ? 'Shop is OPEN' : 'Shop is CLOSED'); }

// ==================== PRODUCTS WITH IMAGE SUPPORT ====================
async function showProducts() {
    await loadData();
    document.getElementById('content').innerHTML = `<button class="btn" onclick="openAddProductModal()"><i class="fas fa-plus-circle"></i> Add Product</button><div id="productsList" class="mt-4">${products.map(p => `
        <div class="product-card">
            <div class="flex justify-between"><div><h4>${escapeHtml(p.name)}</h4><p class="text-secondary">${escapeHtml(p.description || '')}</p><span class="badge">${escapeHtml(p.category || 'Uncategorized')}</span></div><div class="product-price">₱${p.price}</div></div>
            ${p.images && p.images.length ? `<div class="image-grid mt-2">${p.images.slice(0,3).map(img => `<div class="image-thumb"><img src="${img.thumbnail || img}" onerror="this.src='https://placehold.co/200x200/f0f4f0/8da38d?text=No+Image'"></div>`).join('')}</div>` : ''}
            <div class="flex gap-2 mt-3"><button class="btn-outline btn-sm" onclick="openEditProductModal('${p.id}')"><i class="fas fa-edit"></i> Edit</button><button class="btn-outline btn-sm" onclick="deleteProduct('${p.id}')"><i class="fas fa-trash"></i> Delete</button></div>
        </div>
    `).join('') || '<div class="card text-center">No products yet. Click "Add Product" to get started!</div>'}</div>`;
}

function escapeHtml(str) { if(!str) return ''; return str.replace(/[&<>]/g, function(m) { if(m === '&') return '&amp;'; if(m === '<') return '&lt;'; if(m === '>') return '&gt;'; return m; }); }

function openAddProductModal() { 
    currentProductId = null; 
    currentImages = []; 
    renderProductModal(); 
}

async function openEditProductModal(id) { 
    await loadData();
    const p = products.find(x => x.id == id); 
    if(p) { 
        currentProductId = id; 
        currentImages = p.images ? [...p.images] : []; 
        renderProductModal(p); 
    } 
}

function renderProductModal(ex = null) {
    const nameValue = ex ? ex.name.replace(/"/g, '&quot;') : '';
    const descValue = ex ? (ex.description || '') : '';
    const categoryValue = ex ? (ex.category || '') : '';
    const priceValue = ex ? ex.price : '';
    
    document.getElementById('modalTitle').innerHTML = ex ? 'Edit Product' : 'Add Product';
    document.getElementById('modalBody').innerHTML = `
        <input id="prodName" class="input" placeholder="Product name *" value="${nameValue}">
        <textarea id="prodDesc" class="input" placeholder="Description" rows="3">${descValue}</textarea>
        <input id="prodCategory" class="input" placeholder="Category (e.g., Pancit, Siomai, Coffee)" value="${escapeHtml(categoryValue)}">
        <input id="prodPrice" type="number" class="input" placeholder="Price (₱) *" step="0.01" value="${priceValue}">
        
        <div style="margin:12px 0">
            <label class="text-secondary" style="font-size:13px">Product Photos (PNG, JPG, JPEG)</label>
            <div class="upload-area" onclick="document.getElementById('prodImages').click()" style="margin-top:8px">
                <i class="fas fa-camera"></i>
                <div>Click to upload photos</div>
                <div style="font-size:11px">PNG, JPG, JPEG up to 5MB each</div>
            </div>
            <input type="file" id="prodImages" multiple accept="image/png,image/jpeg,image/jpg" style="display:none" onchange="previewImages(this)">
            <div id="imagePreview" class="product-images-container"></div>
        </div>
        
        <div class="flex gap-2 mt-4">
            <button class="btn" onclick="saveProduct()"><i class="fas fa-save"></i> Save Product</button>
            <button class="btn-outline" onclick="closeProductModal()">Cancel</button>
        </div>
    `;
    
    // Display existing images
    const previewDiv = document.getElementById('imagePreview');
    if (previewDiv) {
        previewDiv.innerHTML = '';
        if (currentImages.length > 0) {
            currentImages.forEach((img, idx) => {
                const imgUrl = typeof img === 'string' ? img : (img.thumbnail || img.full || img);
                previewDiv.innerHTML += `<div class="image-preview"><img src="${imgUrl}" onerror="this.src='https://placehold.co/200x200/f0f4f0/8da38d?text=Bad+Image'"><div class="remove-img" onclick="removeImage(${idx})">✖</div></div>`;
            });
        }
    }
    
    document.getElementById('productModal').classList.add('show');
    
    setTimeout(() => {
        const chooseBtn = document.getElementById('prodImages');
        if (chooseBtn) {
            chooseBtn.onchange = () => previewImages(chooseBtn);
        }
    }, 100);
}

function previewImages(input) {
    const previewDiv = document.getElementById('imagePreview');
    if (!previewDiv) return;
    
    for (let i = 0; i < input.files.length; i++) {
        const file = input.files[i];
        
        // Validate file type
        if (!file.type.match('image.*')) {
            showToast('Please select an image file (PNG, JPG, JPEG)');
            continue;
        }
        
        // Validate file size (max 5MB)
        if (file.size > 5 * 1024 * 1024) {
            showToast('File too large. Max 5MB');
            continue;
        }
        
        const reader = new FileReader();
        reader.onload = function(e) {
            previewDiv.innerHTML += `
                <div class="image-preview">
                    <img src="${e.target.result}">
                    <div class="remove-img" onclick="this.parentElement.remove()">✖</div>
                </div>
            `;
        };
        reader.readAsDataURL(file);
    }
    // Clear the input to allow re-uploading same files
    input.value = '';
}

function removeImage(index) {
    currentImages.splice(index, 1);
    const previewDiv = document.getElementById('imagePreview');
    if (previewDiv && previewDiv.children[index]) {
        previewDiv.children[index].remove();
    }
}

async function saveProduct() {
    const name = document.getElementById('prodName').value.trim();
    const category = document.getElementById('prodCategory').value.trim();
    const price = parseFloat(document.getElementById('prodPrice').value);
    
    if (!name || isNaN(price) || price <= 0) {
        showToast('Product name and valid price are required');
        return;
    }
    
    if (!category) {
        showToast('Please enter a category');
        return;
    }
    
    // Collect images from preview (new ones added)
    const newImages = [];
    const previewDiv = document.getElementById('imagePreview');
    if (previewDiv) {
        const previewImgs = previewDiv.querySelectorAll('.image-preview img');
        for (let i = 0; i < previewImgs.length; i++) {
            const src = previewImgs[i].src;
            // If it's a data URL (new upload) or existing image URL
            if (src && src.startsWith('data:image')) {
                newImages.push({ thumbnail: src, full: src });
            } else if (src && !src.startsWith('data:image')) {
                // This is an existing image from server, preserve it
                newImages.push({ thumbnail: src, full: src });
            }
        }
    }
    
    // Also include any existing images that weren't removed
    // We need to track which existing images are still in the preview
    // For simplicity, we'll use newImages as the final list
    
    const productData = {
        name: name,
        description: document.getElementById('prodDesc').value || '',
        category: category,
        price: price,
        images: newImages.length > 0 ? newImages : currentImages
    };
    
    console.log('Saving product:', productData);
    
    const endpoint = currentProductId ? '/api/vendor/product/update' : '/api/vendor/product/create';
    const body = currentProductId ? { product_id: currentProductId, ...productData } : productData;
    
    const res = await api(endpoint, { method: 'POST', body: JSON.stringify(body) });
    
    if (res && res.success) {
        showToast(currentProductId ? 'Product updated successfully!' : 'Product created successfully!');
        closeProductModal();
        await showProducts();
    } else {
        showToast('Failed to save product. Please try again.');
        console.error('Save error:', res);
    }
}

async function deleteProduct(id) {
    if (confirm('Delete this product permanently?')) {
        const res = await api('/api/vendor/product/delete', { method: 'POST', body: JSON.stringify({ product_id: id }) });
        if (res && res.success) { showToast('Product deleted'); showProducts(); }
        else showToast('Failed to delete product');
    }
}

// ==================== REVIEWS ====================
async function showReviews() {
    const data = await api('/api/vendor/reviews');
    document.getElementById('content').innerHTML = (data?.reviews || []).map(r => `
        <div class="card">
            <div class="flex justify-between items-center"><div><strong><i class="fas fa-user-circle"></i> ${escapeHtml(r.customer_name)}</strong><div class="stars mt-1">${'★'.repeat(r.rating)}${'☆'.repeat(5-r.rating)}</div></div><span class="text-secondary">${new Date(r.created_at).toLocaleDateString()}</span></div>
            <p class="mt-2">${escapeHtml(r.comment || 'No comment provided')}</p>
        </div>
    `).join('') || '<div class="card text-center">No reviews yet.</div>';
}

// ==================== POSTS ====================
async function showPosts() {
    await loadData();
    const feed = await api('/api/vendor/posts');
    document.getElementById('content').innerHTML = `
        <button class="btn" onclick="openPostModal()"><i class="fas fa-plus"></i> Create Post</button>
        <div id="postsList" class="mt-4">${(feed?.posts || []).map(p => `
            <div class="post-card">
                <div class="post-header">
                    ${vendorData?.logo ? `<img src="${vendorData.logo}" style="width:48px;height:48px;border-radius:50%;object-fit:cover">` : `<div class="post-avatar"><i class="fas fa-store"></i></div>`}
                    <div><strong>${escapeHtml(vendorData?.business_name || 'Store')}</strong><br><span class="text-secondary">${new Date(p.created_at).toLocaleDateString()}</span></div>
                </div>
                <div class="post-content">${escapeHtml(p.content)}</div>
                ${p.images && p.images.length ? `<div class="image-grid mt-2">${p.images.slice(0,3).map(img => `<div class="image-thumb"><img src="${img.thumbnail || img}"></div>`).join('')}</div>` : ''}
                <div class="post-stats"><span><i class="far fa-heart"></i> ${p.likes || 0}</span><span><i class="far fa-comment"></i> ${p.comment_count || 0}</span><span><i class="far fa-bookmark"></i> ${p.saves || 0}</span></div>
                <div class="flex gap-2 mt-3"><button class="btn-outline btn-sm" onclick="deletePost('${p.id}')"><i class="fas fa-trash"></i> Delete</button></div>
            </div>
        `).join('') || '<div class="card text-center">No posts yet. Create your first post!</div>'}</div>`;
}

function previewPostImages(input) {
    const preview = document.getElementById('postImagePreview');
    preview.innerHTML = '';
    for (let f of input.files) {
        if (!f.type.match('image.*')) continue;
        if (f.size > 5 * 1024 * 1024) { showToast('File too large'); continue; }
        const reader = new FileReader();
        reader.onload = (e) => {
            preview.innerHTML += `<div class="image-preview"><img src="${e.target.result}"><div class="remove-img" onclick="this.parentElement.remove()">✖</div></div>`;
        };
        reader.readAsDataURL(f);
    }
}

async function createPost() {
    const content = document.getElementById('postContent').value.trim();
    const files = document.getElementById('postImages').files;
    if (!content) { showToast('Please write something'); return; }
    if (files.length === 0) { showToast('Please add at least 1 photo'); return; }
    
    const images = [];
    for (let f of files) {
        if (!f.type.match('image.*')) continue;
        const imgData = await new Promise(resolve => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.readAsDataURL(f);
        });
        images.push(imgData);
    }
    
    const res = await api('/api/vendor/post/create', { method: 'POST', body: JSON.stringify({ content, images }) });
    if (res && res.success) {
        showToast('Post published!');
        closePostModal();
        document.getElementById('postContent').value = '';
        document.getElementById('postImages').value = '';
        document.getElementById('postImagePreview').innerHTML = '';
        showPosts();
    } else {
        showToast('Failed to create post');
    }
}

async function deletePost(id) {
    if (confirm('Delete this post?')) {
        await api('/api/vendor/post/delete', { method: 'POST', body: JSON.stringify({ post_id: id }) });
        showToast('Post deleted');
        showPosts();
    }
}

function openPostModal() {
    document.getElementById('postModal').classList.add('show');
    document.getElementById('postContent').value = '';
    document.getElementById('postImages').value = '';
    document.getElementById('postImagePreview').innerHTML = '';
}

// ==================== PROFILE & SETTINGS ====================
async function showProfile() {
    await loadData(); await loadVendorProfile();
    document.getElementById('content').innerHTML = `
        <div class="card text-center">
            <div class="business-logo" style="width:100px;height:100px;margin:0 auto 16px;background:#eff3ef;border-radius:50%;display:flex;align-items:center;justify-content:center">${vendorData?.logo ? `<img src="${vendorData.logo}" style="width:100px;height:100px;border-radius:50%;object-fit:cover">` : '<i class="fas fa-store fa-3x" style="color:#3a7b4d"></i>'}</div>
            <h2>${escapeHtml(vendorData?.business_name || '')}</h2>
            <p class="text-secondary">${vendorData?.email || ''}</p>
            <div class="stats-grid mt-4"><div class="stat-card"><div class="stat-value">${vendorData?.rating || 'New'}</div><div class="stat-label">Rating</div></div><div class="stat-card"><div class="stat-value">${vendorData?.review_count || 0}</div><div class="stat-label">Reviews</div></div></div>
            <button class="btn-outline mt-3" onclick="showPage('settings')">Edit Profile</button>
        </div>
    `;
}

async function showSettings() {
    await loadData(); await loadVendorProfile();
    const hours = vendorData?.operating_hours || {};
    document.getElementById('content').innerHTML = `
        <div class="card"><h3>Operating Hours</h3><div id="hoursPreview" class="hours-grid"></div><button class="btn-outline mt-3" onclick="openHoursModal()">Set Hours</button></div>
        <div class="card"><h3>Business Location</h3><p class="text-secondary">Current: ${vendorData?.latitude || 'Not set'}, ${vendorData?.longitude || 'Not set'}</p><button class="btn-outline" onclick="openLocationModal()">Update Location</button></div>
        <div class="card"><h3>Business Logo</h3>${vendorData?.logo ? `<img src="${vendorData.logo}" style="width:80px;height:80px;border-radius:50%;object-fit:cover;margin-bottom:12px">` : '<p class="text-secondary">No logo uploaded</p>'}<button class="btn-outline" onclick="openLogoModal()">Update Logo</button></div>
        <div class="card"><h3>Business Info</h3><p><strong>${escapeHtml(vendorData?.business_name || '')}</strong><br><i class="fas fa-tag"></i> ${escapeHtml(vendorData?.category) || 'Not set'}<br><i class="fas fa-phone"></i> ${vendorProfile?.phone || vendorData?.phone || 'No phone'}<br><i class="fas fa-envelope"></i> ${vendorProfile?.email || vendorData?.email}</p></div>
    `;
    const preview = document.getElementById('hoursPreview');
    const days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    if (preview) preview.innerHTML = days.map(day => `<div class="hours-item"><span class="hours-day">${day}</span><span>${hours[day] || 'closed'}</span></div>`).join('');
}

function openLogoModal() { document.getElementById('logoModal').classList.add('show'); if(vendorData?.logo) document.getElementById('logoPreview').innerHTML = `<img src="${vendorData.logo}" style="width:100px;height:100px;border-radius:50%;object-fit:cover">`; }
async function updateLogo(input) { if(input.files[0]){ const file=input.files[0]; if(file.size>5*1024*1024){ showToast('File too large. Max 5MB'); return; } const r=new FileReader(); r.onload=async(e)=>{ const res=await api('/api/vendor/update-logo',{method:'POST',body:JSON.stringify({logo:e.target.result})}); if(res?.success){ showToast('Logo updated!'); closeLogoModal(); showSettings(); showDashboard(); } else showToast('Failed to update logo'); }; r.readAsDataURL(file); } }
async function removeLogo(){ if(confirm('Remove your business logo?')){ const res=await api('/api/vendor/update-logo',{method:'POST',body:JSON.stringify({logo:null})}); if(res?.success){ showToast('Logo removed'); closeLogoModal(); showSettings(); showDashboard(); } } }
function openHoursModal() { const hours=vendorData?.operating_hours||{}; const days=['monday','tuesday','wednesday','thursday','friday','saturday','sunday']; let html=''; days.forEach(day=>{ const val=hours[day]||'closed'; const closed=val==='closed'; let [openH=9,closeH=18]=val!=='closed'?val.split('-').map(parseInt):[9,18]; html+=`<div class="card"><div class="flex justify-between"><h4>${day}</h4><label><input type="checkbox" id="closed_${day}" ${closed?'checked':''} onchange="toggleDay('${day}')"> Closed</label></div><div id="sliders_${day}" ${closed?'style="display:none"':''}><div><span>Open</span><input type="range" id="open_${day}" min="0" max="23" value="${openH}" oninput="document.getElementById('open_val_${day}').innerText=this.value+':00'"><span id="open_val_${day}">${openH}:00</span></div><div><span>Close</span><input type="range" id="close_${day}" min="0" max="23" value="${closeH}" oninput="document.getElementById('close_val_${day}').innerText=this.value+':00'"><span id="close_val_${day}">${closeH}:00</span></div></div></div>`; }); document.getElementById('hoursBody').innerHTML=html+'<button class="btn mt-4" onclick="saveHours()">Save Hours</button>'; document.getElementById('hoursModal').classList.add('show'); window.toggleDay=(day)=>{ const closed=document.getElementById(`closed_${day}`).checked; document.getElementById(`sliders_${day}`).style.display=closed?'none':'block'; }; }
function updateTime(type,day,value){ document.getElementById(`${type}_val_${day}`).innerText=`${value}:00`; }
async function saveHours(){ const hours={}; const days=['monday','tuesday','wednesday','thursday','friday','saturday','sunday']; days.forEach(day=>{ const closed=document.getElementById(`closed_${day}`)?.checked; if(closed) hours[day]='closed'; else{ const openH=document.getElementById(`open_${day}`)?.value||9; const closeH=document.getElementById(`close_${day}`)?.value||18; hours[day]=`${openH}:00-${closeH}:00`; } }); const res=await api('/api/vendor/update-hours',{method:'POST',body:JSON.stringify({hours})}); if(res?.success){ showToast('Hours saved!'); closeHoursModal(); showSettings(); } }
function openLocationModal(){ document.getElementById('locationModal').classList.add('show'); setTimeout(()=>{ if(typeof L!=='undefined'){ if(window.locationMap) window.locationMap.remove(); window.locationMap=L.map('locationMap').setView([vendorData?.latitude||14.5995,vendorData?.longitude||120.9842],16); L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png').addTo(window.locationMap); window.locationMarker=L.marker([vendorData?.latitude||14.5995,vendorData?.longitude||120.9842],{draggable:true}).addTo(window.locationMap); window.locationMarker.on('dragend',e=>{ const pos=e.target.getLatLng(); document.getElementById('locationText').innerHTML=`${pos.lat.toFixed(6)}, ${pos.lng.toFixed(6)}`; }); document.getElementById('locationText').innerHTML=`${vendorData?.latitude||'Tap to set'}, ${vendorData?.longitude||'Tap to set'}`; } },100); }
async function saveNewLocation(){ if(window.locationMarker){ const pos=window.locationMarker.getLatLng(); const res=await api('/api/vendor/update-location',{method:'POST',body:JSON.stringify({latitude:pos.lat,longitude:pos.lng})}); if(res?.success){ showToast('Location updated!'); closeLocationModal(); showSettings(); } } }
async function showAnalytics(){ const data=await api('/api/vendor/analytics'); document.getElementById('analyticsContent').innerHTML=`<div class="stats-grid"><div class="stat-card"><div class="stat-value">${data.total_visits||0}</div><div class="stat-label">Visits</div></div><div class="stat-card"><div class="stat-value">${data.avg_rating||'N/A'}</div><div class="stat-label">Rating</div></div></div><canvas id="analyticsChart"></canvas>`; document.getElementById('analyticsModal').classList.add('show'); setTimeout(()=>{ new Chart(document.getElementById('analyticsChart'),{type:'bar',data:{labels:data.weekly_labels||['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],datasets:[{label:'Traffic',data:data.weekly_traffic||[5,8,12,15,20,25,18],backgroundColor:'#3a7b4d',borderRadius:8}]}}); },100); }
function showTutorial() { alert("Vendor Dashboard Tutorial\\n\\n✓ Add products with photos (PNG, JPG, JPEG)\\n✓ Edit existing products\\n✓ Create posts to engage customers\\n✓ View customer reviews\\n✓ Toggle open/close status\\n✓ Set operating hours and location"); }
function closeProductModal(){ document.getElementById('productModal').classList.remove('show'); }
function closePostModal(){ document.getElementById('postModal').classList.remove('show'); }
function closeLocationModal(){ document.getElementById('locationModal').classList.remove('show'); }
function closeLogoModal(){ document.getElementById('logoModal').classList.remove('show'); }
function closeHoursModal(){ document.getElementById('hoursModal').classList.remove('show'); }
function closeAnalyticsModal(){ document.getElementById('analyticsModal').classList.remove('show'); }
function toggleMenu(){ document.getElementById('hamburgerMenu').classList.toggle('show'); }
function confirmLogout(){ if(confirm('Logout?')){ localStorage.clear(); window.location.href='/'; } }

let fa=document.createElement('link');fa.rel='stylesheet';fa.href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css';document.head.appendChild(fa);
let chartScript=document.createElement('script');chartScript.src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js';document.head.appendChild(chartScript);
let leaflet=document.createElement('link');leaflet.rel='stylesheet';leaflet.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';document.head.appendChild(leaflet);
let leafletScript=document.createElement('script');leafletScript.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';document.head.appendChild(leafletScript);
if(sessionToken){ showDashboard(); } else window.location.href='/auth';
</script>
''')
# ============================================
# ADMIN DASHBOARD (Updated with modern GUI)
# ============================================

ADMIN_DASH = render_page("Admin Panel", '''
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#f8faf8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
.app-bar{background:white;padding:16px;display:flex;gap:16px;border-bottom:1px solid #e8ece8;position:sticky;top:0;z-index:100}
.back-btn{background:#f0f4f0;border:none;width:40px;height:40px;border-radius:50%;cursor:pointer;font-size:18px;color:#2d8c3c}
.app-bar-title{font-size:18px;font-weight:600;color:#1a2e1a;flex:1}
.menu-btn{background:#f0f4f0;border:none;width:40px;height:40px;border-radius:50%;cursor:pointer;font-size:18px;color:#2d8c3c}
.content{padding:20px;max-width:500px;margin:0 auto;min-height:calc(100vh - 140px);padding-bottom:80px}
.bottom-nav{position:fixed;bottom:0;left:0;right:0;background:white;display:flex;justify-content:space-around;padding:10px 16px 20px;border-top:1px solid #e8ece8;max-width:500px;margin:0 auto;box-shadow:0 -2px 10px rgba(0,0,0,0.05);z-index:99}
.nav-item{display:flex;flex-direction:column;align-items:center;gap:4px;color:#8ba88b;font-size:12px;cursor:pointer;transition:all 0.2s}
.nav-item i{font-size:22px}
.nav-item.active{color:#2d8c3c}
.nav-item span{font-size:11px;font-weight:500}
.card{background:white;border-radius:20px;padding:16px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,0.03);border:0.5px solid rgba(0,0,0,0.03);cursor:pointer;transition:all 0.2s}
.card:active{transform:scale(0.98)}
.stats-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:20px}
.stat-card{background:linear-gradient(135deg,#2d8c3c,#1a6b28);border-radius:20px;padding:16px;text-align:center;color:white}
.stat-value{font-size:28px;font-weight:800}
.stat-label{font-size:12px;opacity:0.9;margin-top:4px}
.chart-container{background:white;border-radius:20px;padding:16px;margin-bottom:20px}
.search-bar{background:white;border:1px solid #e0e8e0;border-radius:30px;padding:10px 16px;display:flex;align-items:center;gap:10px;margin-bottom:16px}
.search-bar i{color:#8ba88b}
.search-bar input{flex:1;border:none;background:transparent;font-size:15px;outline:none}
.btn-outline{background:white;border:1px solid #2d8c3c;color:#2d8c3c;padding:6px 14px;border-radius:30px;font-size:12px;cursor:pointer}
.btn{width:100%;padding:12px;background:#2d8c3c;color:white;border:none;border-radius:30px;font-size:14px;font-weight:600;cursor:pointer;transition:all 0.2s}
.btn:active{transform:scale(0.97)}
.btn-sm{padding:6px 12px;font-size:12px;width:auto}
.flex{display:flex}
.justify-between{justify-content:space-between}
.items-center{align-items:center}
.gap-2{gap:8px}
.gap-3{gap:12px}
.mt-1{margin-top:4px}
.mt-2{margin-top:8px}
.mt-3{margin-top:12px}
.mt-4{margin-top:16px}
.mb-2{margin-bottom:8px}
.text-secondary{color:#8ba88b;font-size:12px}
.text-center{text-align:center}
.hamburger-menu{position:fixed;top:0;right:-280px;width:280px;height:100vh;background:white;z-index:200;box-shadow:-2px 0 10px rgba(0,0,0,0.1);transition:right 0.3s ease;padding:60px 20px}
.hamburger-menu.show{right:0}
.menu-item{padding:14px;display:flex;align-items:center;gap:12px;cursor:pointer;border-radius:12px;font-size:14px}
.menu-item:hover{background:#f0f4f0}
.menu-divider{height:1px;background:#e8ece8;margin:12px 0}
.loading{text-align:center;padding:40px;color:#8ba88b}
.toast{position:fixed;bottom:80px;left:20px;right:20px;background:#1a2e1a;color:white;padding:12px;border-radius:30px;text-align:center;z-index:1000;font-size:13px}
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:1000;align-items:center;justify-content:center;padding:20px}
.modal.show{display:flex}
.modal-content{background:white;border-radius:24px;max-width:500px;width:100%;max-height:85vh;overflow-y:auto;padding:20px;position:relative;z-index:1001}
.modal-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;font-size:18px;font-weight:700;color:#1a2e1a}
.modal-close{font-size:24px;cursor:pointer;color:#8ba88b;padding:8px}
.input{width:100%;padding:12px 14px;border:1px solid #e0e8e0;border-radius:14px;font-size:14px;margin-bottom:12px;background:#f8faf8}
.input:focus{outline:none;border-color:#2d8c3c}
textarea.input{min-height:80px;resize:vertical}
.product-card{background:#f8faf8;border-radius:16px;padding:12px;margin-bottom:10px}
.product-name{font-weight:600;color:#1a2e1a}
.product-price{color:#2d8c3c;font-weight:700}
.image-preview{width:60px;height:60px;border-radius:8px;object-fit:cover}
.close-hamburger{position:absolute;top:20px;right:20px;background:#f0f4f0;border:none;width:36px;height:36px;border-radius:50%;cursor:pointer;font-size:16px;color:#2d8c3c}
</style>

<div class="app-bar">
    <button class="back-btn" onclick="logout()"><i class="fas fa-sign-out-alt"></i></button>
    <div class="app-bar-title">Admin Panel</div>
    <button class="menu-btn" onclick="toggleMenu()"><i class="fas fa-bars"></i></button>
</div>

<div id="hamburgerMenu" class="hamburger-menu">
    <button class="close-hamburger" onclick="toggleMenu()"><i class="fas fa-times"></i></button>
    <div class="menu-item" onclick="showStats()"><i class="fas fa-chart-line"></i> Dashboard</div>
    <div class="menu-item" onclick="showUsers()"><i class="fas fa-users"></i> Users</div>
    <div class="menu-item" onclick="showVendors()"><i class="fas fa-store"></i> Vendors</div>
    <div class="menu-divider"></div>
    <div class="menu-item" onclick="logout()"><i class="fas fa-sign-out-alt"></i> Logout</div>
</div>

<div class="bottom-nav">
    <div class="nav-item active" onclick="showStats()"><i class="fas fa-chart-line"></i><span>Stats</span></div>
    <div class="nav-item" onclick="showUsers()"><i class="fas fa-users"></i><span>Users</span></div>
    <div class="nav-item" onclick="showVendors()"><i class="fas fa-store"></i><span>Vendors</span></div>
</div>

<div class="content" id="content"></div>

<!-- Vendor Products Modal -->
<div class="modal" id="vendorProductsModal">
    <div class="modal-content">
        <div class="modal-header">
            <h3 id="vendorProductsTitle"><i class="fas fa-store"></i> Vendor Products</h3>
            <span class="modal-close" onclick="closeVendorProductsModal()">&times;</span>
        </div>
        <div id="vendorProductsBody">
            <div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading products...</div>
        </div>
    </div>
</div>

<!-- Add/Edit Product Modal -->
<div class="modal" id="adminProductModal">
    <div class="modal-content">
        <div class="modal-header">
            <h3 id="adminProductModalTitle">Add Product</h3>
            <span class="modal-close" onclick="closeAdminProductModal()">&times;</span>
        </div>
        <div id="adminProductModalBody">
            <input type="text" id="adminProdName" class="input" placeholder="Product name *">
            <textarea id="adminProdDesc" class="input" placeholder="Description"></textarea>
            <select id="adminProdCategory" class="input">
                <option value="">Select Category</option>
                <option value="Coffee">Coffee</option>
                <option value="Pancit">Pancit</option>
                <option value="Tusok Tusok">Tusok Tusok</option>
                <option value="Contemporary Street food">Contemporary Street food</option>
                <option value="Bread and Pastry">Bread and Pastry</option>
                <option value="Lomi">Lomi</option>
                <option value="Beverage">Beverage</option>
                <option value="Sarisari Store">Sarisari Store</option>
                <option value="Karendirya">Karendirya</option>
                <option value="Traditional Desserts">Traditional Desserts</option>
                <option value="Contemporary Desserts">Contemporary Desserts</option>
                <option value="Squidball">Squidball</option>
                <option value="Siomai">Siomai</option>
                <option value="Siopao">Siopao</option>
                <option value="Taho">Taho</option>
                <option value="Fruit shakes">Fruit shakes</option>
            </select>
            <div class="flex gap-2">
                <input type="number" id="adminProdPrice" class="input" placeholder="Price (₱) *" step="0.01">
            </div>
            <div class="upload-area" onclick="document.getElementById('adminProdImages').click()" style="background:#f8faf8;border:1px dashed #c0d0c0;border-radius:16px;padding:16px;text-align:center;cursor:pointer;margin:12px 0">
                <i class="fas fa-image" style="font-size:24px;color:#2d8c3c"></i>
                <div>Add Product Images</div>
            </div>
            <input type="file" id="adminProdImages" multiple accept="image/*" style="display:none" onchange="previewAdminProductImages(this)">
            <div id="adminProductImagePreview" class="product-images-container" style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px"></div>
            <div class="flex gap-2 mt-4">
                <button class="btn" onclick="saveAdminProduct()"><i class="fas fa-save"></i> Save Product</button>
                <button class="btn-outline" onclick="closeAdminProductModal()">Cancel</button>
            </div>
        </div>
    </div>
</div>

<script>
let sessionToken = localStorage.getItem('session_token');
let adminData = null;
let currentPage = 'stats';
let currentVendorForProducts = null;
let currentEditingProduct = null;
let adminProductImages = [];

if (!sessionToken) window.location.href = '/auth';

function showToast(msg){
    let t=document.querySelector('.toast');
    if(t)t.remove();
    t=document.createElement('div');
    t.className='toast';
    t.innerHTML='<i class="fas fa-info-circle"></i> '+msg;
    document.body.appendChild(t);
    setTimeout(()=>t.remove(),3000);
}

async function api(url, options = {}) {
    const res = await fetch(url, {
        ...options,
        headers: { 'Content-Type': 'application/json', 'X-Session-Token': sessionToken, ...options.headers }
    });
    if (res.status === 401) { localStorage.clear(); window.location.href = '/auth'; return null; }
    return res.json();
}

async function loadAdminProfile() {
    const data = await api('/api/admin/profile');
    if (data) { adminData = data; }
}

async function showStats() {
    currentPage = 'stats';
    document.getElementById('content').innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading stats...</div>';
    const data = await api('/api/admin/stats');
    document.getElementById('content').innerHTML = `
        <div class="card" style="background:linear-gradient(135deg,#2d8c3c,#1a6b28);color:white;margin-bottom:20px">
            <div class="flex items-center gap-3">
                <div style="font-size:48px"><i class="fas fa-user-shield"></i></div>
                <div>
                    <p style="opacity:0.9;font-size:13px">Welcome back,</p>
                    <h2 style="font-size:22px">${adminData?.full_name || 'Admin'}!</h2>
                    <p style="opacity:0.9;font-size:12px">System Administrator</p>
                </div>
            </div>
        </div>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value">${data.total_users || 0}</div><div class="stat-label">Total Users</div></div>
            <div class="stat-card"><div class="stat-value">${data.total_vendors || 0}</div><div class="stat-label">Total Vendors</div></div>
            <div class="stat-card"><div class="stat-value">${data.total_products || 0}</div><div class="stat-label">Total Products</div></div>
            <div class="stat-card"><div class="stat-value">${data.total_reviews || 0}</div><div class="stat-label">Total Reviews</div></div>
            <div class="stat-card"><div class="stat-value">${data.total_posts || 0}</div><div class="stat-label">Total Posts</div></div>
        </div>
        <div class="chart-container"><canvas id="growthChart"></canvas></div>`;
    setTimeout(() => {
        new Chart(document.getElementById('growthChart'), {
            type: 'line',
            data: { labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'], datasets: [{ label: 'Users', data: data.user_growth || [10, 25, 45, 70, 100, 150], borderColor: '#2d8c3c', fill: true, tension: 0.4 }] },
            options: { responsive: true }
        });
    }, 100);
    updateActiveNav('stats');
}

async function showUsers() {
    currentPage = 'users';
    document.getElementById('content').innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading users...</div>';
    const data = await api('/api/admin/users');
    document.getElementById('content').innerHTML = `
        <div class="search-bar"><i class="fas fa-search"></i><input type="text" id="userSearch" placeholder="Search users..." oninput="filterUsers()"></div>
        <div id="usersList">${(data.users || []).map(u => `
            <div class="card" data-email="${u.email.toLowerCase()}">
                <div class="flex justify-between items-center">
                    <div><strong><i class="fas fa-user-circle"></i> ${u.email}</strong><br><span class="text-secondary">${u.full_name || 'No name'} • ${u.role}</span><br><small>Joined: ${new Date(u.created_at).toLocaleDateString()}</small></div>
                    <button class="btn-outline" onclick="suspendUser('${u.id}', ${u.is_suspended})"><i class="fas ${u.is_suspended ? 'fa-user-check' : 'fa-user-slash'}"></i> ${u.is_suspended ? 'Unsuspend' : 'Suspend'}</button>
                </div>
            </div>
        `).join('') || '<div class="card text-center text-secondary">No users found</div>'}</div>`;
    updateActiveNav('users');
}

function filterUsers() {
    const query = document.getElementById('userSearch')?.value.toLowerCase() || '';
    document.querySelectorAll('#usersList .card').forEach(card => {
        card.style.display = card.dataset.email.includes(query) ? 'block' : 'none';
    });
}

async function showVendors() {
    currentPage = 'vendors';
    document.getElementById('content').innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading vendors...</div>';
    const data = await api('/api/admin/vendors');
    document.getElementById('content').innerHTML = `
        <div class="search-bar"><i class="fas fa-search"></i><input type="text" id="vendorSearch" placeholder="Search vendors..." oninput="filterVendorList()"></div>
        <div id="vendorsList">${(data.vendors || []).map(v => `
            <div class="card" data-name="${v.business_name.toLowerCase()}" data-id="${v.id}">
                <div class="flex justify-between items-center">
                    <div><strong><i class="fas fa-store"></i> ${v.business_name}</strong><br><span class="text-secondary">${v.category} • ${v.is_active ? 'Active' : 'Inactive'} • Rating: ${v.rating || 'New'}</span><br><small>Owner: ${v.user_name || 'N/A'}</small></div>
                    <div class="flex gap-2">
                        <button class="btn-outline" onclick="event.stopPropagation(); openVendorProducts('${v.id}', '${v.business_name}')"><i class="fas fa-utensils"></i> Products</button>
                        <button class="btn-outline" onclick="event.stopPropagation(); toggleVendor('${v.id}', ${v.is_active})"><i class="fas ${v.is_active ? 'fa-ban' : 'fa-check-circle'}"></i> ${v.is_active ? 'Disable' : 'Enable'}</button>
                    </div>
                </div>
            </div>
        `).join('') || '<div class="card text-center text-secondary">No vendors found</div>'}</div>`;
    updateActiveNav('vendors');
}

function filterVendorList() {
    const query = document.getElementById('vendorSearch')?.value.toLowerCase() || '';
    document.querySelectorAll('#vendorsList .card').forEach(card => {
        card.style.display = card.dataset.name.includes(query) ? 'block' : 'none';
    });
}

async function openVendorProducts(vendorId, vendorName) {
    currentVendorForProducts = vendorId;
    document.getElementById('vendorProductsTitle').innerHTML = `<i class="fas fa-store"></i> ${vendorName} - Products`;
    document.getElementById('vendorProductsBody').innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading products...</div>';
    document.getElementById('vendorProductsModal').classList.add('show');
    
    const products = await api(`/api/admin/vendor/${vendorId}/products`);
    renderVendorProducts(products);
}

function renderVendorProducts(products) {
    const container = document.getElementById('vendorProductsBody');
    container.innerHTML = `
        <button class="btn mb-3" onclick="openAddProductForVendor()"><i class="fas fa-plus"></i> Add Product</button>
        <div id="vendorProductsList">
            ${(products || []).map(p => `
                <div class="product-card">
                    <div class="flex justify-between items-start">
                        <div class="flex-1">
                            <div class="product-name">${p.name}</div>
                            <div class="product-price">₱${p.price}</div>
                            <div class="text-secondary" style="font-size:11px">${p.category || 'Uncategorized'}</div>
                            ${p.description ? `<div class="text-secondary mt-1" style="font-size:11px">${p.description.substring(0, 60)}${p.description.length > 60 ? '...' : ''}</div>` : ''}
                        </div>
                        ${p.images && p.images[0] ? `<img src="${p.images[0].thumbnail}" class="image-preview" style="width:50px;height:50px;object-fit:cover;border-radius:8px">` : `<div style="width:50px;height:50px;background:#f0f4f0;border-radius:8px;display:flex;align-items:center;justify-content:center"><i class="fas fa-utensils"></i></div>`}
                    </div>
                    <div class="flex gap-2 mt-3">
                        <button class="btn-outline btn-sm" onclick="editProductForVendor('${p.id}', '${p.name}', '${p.description || ''}', '${p.category || ''}', ${p.price})"><i class="fas fa-edit"></i> Edit</button>
                        <button class="btn-outline btn-sm" onclick="deleteProductForVendor('${p.id}')"><i class="fas fa-trash"></i> Delete</button>
                    </div>
                </div>
            `).join('') || '<div class="card text-center text-secondary"><i class="fas fa-info-circle"></i> No products for this vendor</div>'}
        </div>
    `;
}

function openAddProductForVendor() {
    currentEditingProduct = null;
    document.getElementById('adminProductModalTitle').innerText = 'Add Product';
    document.getElementById('adminProdName').value = '';
    document.getElementById('adminProdDesc').value = '';
    document.getElementById('adminProdCategory').value = '';
    document.getElementById('adminProdPrice').value = '';
    document.getElementById('adminProductImagePreview').innerHTML = '';
    adminProductImages = [];
    document.getElementById('adminProductModal').classList.add('show');
}

function editProductForVendor(productId, name, description, category, price) {
    currentEditingProduct = productId;
    document.getElementById('adminProductModalTitle').innerText = 'Edit Product';
    document.getElementById('adminProdName').value = name;
    document.getElementById('adminProdDesc').value = description || '';
    document.getElementById('adminProdCategory').value = category || '';
    document.getElementById('adminProdPrice').value = price;
    document.getElementById('adminProductImagePreview').innerHTML = '';
    adminProductImages = [];
    document.getElementById('adminProductModal').classList.add('show');
}

function previewAdminProductImages(input) {
    const previewDiv = document.getElementById('adminProductImagePreview');
    previewDiv.innerHTML = '';
    for (let i = 0; i < input.files.length; i++) {
        const reader = new FileReader();
        reader.onload = function(e) {
            previewDiv.innerHTML += `<div class="image-preview"><img src="${e.target.result}" style="width:70px;height:70px;object-fit:cover;border-radius:8px"></div>`;
        };
        reader.readAsDataURL(input.files[i]);
    }
}

async function saveAdminProduct() {
    const name = document.getElementById('adminProdName').value.trim();
    const price = parseFloat(document.getElementById('adminProdPrice').value);
    
    if (!name || !price) {
        showToast('Name and price are required!');
        return;
    }
    
    const images = [];
    const fileInput = document.getElementById('adminProdImages');
    for (let i = 0; i < fileInput.files.length; i++) {
        const reader = new FileReader();
        const imgData = await new Promise((resolve) => {
            reader.onload = (e) => resolve(e.target.result);
            reader.readAsDataURL(fileInput.files[i]);
        });
        images.push(imgData);
    }
    
    const productData = {
        vendor_id: currentVendorForProducts,
        name: name,
        description: document.getElementById('adminProdDesc').value,
        category: document.getElementById('adminProdCategory').value,
        price: price,
        stock: 0,
        images: images
    };
    
    if (currentEditingProduct) {
        productData.product_id = currentEditingProduct;
    }
    
    const endpoint = currentEditingProduct ? '/api/admin/product/update' : '/api/admin/product/create';
    const res = await api(endpoint, { method: 'POST', body: JSON.stringify(productData) });
    
    if (res && res.success) {
        showToast(currentEditingProduct ? 'Product updated!' : 'Product created!');
        closeAdminProductModal();
        openVendorProducts(currentVendorForProducts, '');
    } else {
        showToast('Failed to save product');
    }
}

async function deleteProductForVendor(productId) {
    if (confirm('Delete this product permanently?')) {
        const res = await api('/api/admin/product/delete', { method: 'POST', body: JSON.stringify({ product_id: productId }) });
        if (res && res.success) {
            showToast('Product deleted');
            openVendorProducts(currentVendorForProducts, '');
        } else {
            showToast('Failed to delete product');
        }
    }
}

async function suspendUser(userId, currentlySuspended) {
    await api('/api/admin/user/suspend', { method: 'POST', body: JSON.stringify({ user_id: userId, suspend: !currentlySuspended }) });
    showToast(currentlySuspended ? 'User unsuspended' : 'User suspended');
    showUsers();
}

async function toggleVendor(vendorId, active) {
    await api('/api/admin/vendor/toggle', { method: 'POST', body: JSON.stringify({ vendor_id: vendorId, active: !active }) });
    showToast(active ? 'Vendor disabled' : 'Vendor enabled');
    showVendors();
}

function closeVendorProductsModal() {
    document.getElementById('vendorProductsModal').classList.remove('show');
    currentVendorForProducts = null;
}

function closeAdminProductModal() {
    document.getElementById('adminProductModal').classList.remove('show');
    currentEditingProduct = null;
    adminProductImages = [];
}

function updateActiveNav(page) {
    document.querySelectorAll('.nav-item').forEach((el, i) => {
        const pages = ['stats', 'users', 'vendors'];
        el.classList.toggle('active', pages[i] === page);
    });
}

function toggleMenu() { 
    document.getElementById('hamburgerMenu').classList.toggle('show'); 
}

function logout() { localStorage.clear(); window.location.href = '/'; }

let fa=document.createElement('link');fa.rel='stylesheet';fa.href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css';document.head.appendChild(fa);
let chartScript=document.createElement('script');chartScript.src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js';document.head.appendChild(chartScript);

loadAdminProfile();
showStats();
</script>
''')

@app.route('/')
def index(): 
    return LANDING

@app.route('/auth')
def auth_page(): 
    return AUTH

@app.route('/guest')
def guest_page(): 
    return GUEST

@app.route('/customer')
def customer_page(): 
    return CUSTOMER_DASH  # NOT a placeholder - returns full customer dashboard

@app.route('/vendor')
def vendor_page(): 
    return VENDOR_DASH    # NOT a placeholder - returns full vendor dashboard

@app.route('/admin')
def admin_page(): 
    return ADMIN_DASH     # NOT a placeholder - returns full admin panel

# AUTH API

# ============================================
# COMPLETE WORKING REGISTRATION ENDPOINTS
# ============================================

# ============================================
# AUTH API ROUTES
# ============================================

@app.route('/api/auth/register/customer', methods=['POST'])
def register_customer():
    data = request.json
    otp = str(random.randint(100000, 999999))
    phone = data.get('phone')
    email = data.get('email')
    full_name = data.get('full_name')
    password = data.get('password')
    profile_photo = data.get('profile_photo')
    
    user_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    is_phone_only = email and email.endswith('@lako.customer')
    
    user_data = {
        'id': user_id,
        'email': email,
        'password': hashed,
        'role': 'customer',
        'full_name': full_name,
        'phone': phone,
        'profile_photo': profile_photo,
        'email_verified': is_phone_only,
        'phone_verified': is_phone_only,
        'is_suspended': False,
        'otp_code': otp,
        'otp_expiry': (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        'created_at': utc_now(),
        'updated_at': utc_now()
    }
    
    try:
        supabase.table('users').insert(user_data).execute()
        
        # Send OTP via Brevo and/or TextBee
        notifications.send_verification_code(email, phone, otp)
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'requires_verification': not is_phone_only
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/customer/vendor/posts/<vendor_id>', methods=['GET'])
def get_vendor_posts(vendor_id):
    """Get all posts for a specific vendor to display in vendor modal"""
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Get vendor by ID
    vendor_result = supabase.table('vendors').select('*').eq('id', vendor_id).execute()
    if not vendor_result.data:
        return jsonify({'error': 'Vendor not found'}), 404
    
    vendor = vendor_result.data[0]
    
    # Get posts for this vendor using user_id (since posts are tied to user_id, not vendor_id)
    # Assuming vendor has a user_id foreign key
    user_id = vendor.get('user_id')
    
    if not user_id:
        # If no user_id, return empty posts
        return jsonify({'posts': []})
    
    # Get posts by this vendor
    posts_result = supabase.table('posts')\
        .select('*')\
        .eq('user_id', user_id)\
        .order('created_at', desc=True)\
        .execute()
    
    posts = []
    for post in posts_result.data:
        # Get images for each post
        images_result = supabase.table('post_images')\
            .select('*')\
            .eq('post_id', post['id'])\
            .execute() if 'post_images' in supabase.table_names() else []
        
        posts.append({
            'id': post.get('id'),
            'content': post.get('content', ''),
            'images': post.get('images', []),  # If images stored directly in post
            'likes': post.get('likes', 0),
            'comment_count': post.get('comment_count', 0),
            'saves': post.get('saves', 0),
            'created_at': post.get('created_at')
        })
    
    return jsonify({
        'posts': posts,
        'vendor': {
            'id': vendor.get('id'),
            'business_name': vendor.get('business_name'),
            'category': vendor.get('category')
        }
    })

@app.route('/api/auth/register/vendor', methods=['POST'])
def register_vendor():
    data = request.json
    otp = str(random.randint(100000, 999999))
    phone = data.get('phone')
    email = data.get('email')
    business_name = data.get('business_name')
    user_name = data.get('user_name')
    password = data.get('password')
    business_category = data.get('business_category')
    address = data.get('address')
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    profile_photo = data.get('profile_photo')
    logo = data.get('logo')
    
    user_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    is_phone_only = email and email.endswith('@lako.vendor')
    
    user_data = {
        'id': user_id,
        'email': email,
        'password': hashed,
        'role': 'vendor',
        'full_name': user_name,
        'phone': phone,
        'profile_photo': profile_photo,
        'email_verified': is_phone_only,
        'phone_verified': is_phone_only,
        'is_suspended': False,
        'otp_code': otp,
        'otp_expiry': (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        'created_at': utc_now(),
        'updated_at': utc_now()
    }
    
    try:
        supabase.table('users').insert(user_data).execute()
        
        vendor_id = str(uuid.uuid4())
        vendor_data = {
            'id': vendor_id,
            'user_id': user_id,
            'business_name': business_name,
            'category': business_category,
            'address': address,
            'latitude': latitude,
            'longitude': longitude,
            'phone': phone,
            'email': email,
            'logo': logo,
            'rating': 0,
            'review_count': 0,
            'traffic_count': 0,
            'is_active': True,
            'is_verified': False,
            'operating_hours': {
                'monday': '9:00-18:00', 'tuesday': '9:00-18:00', 'wednesday': '9:00-18:00',
                'thursday': '9:00-18:00', 'friday': '9:00-18:00', 'saturday': '9:00-18:00', 
                'sunday': 'closed'
            },
            'created_at': utc_now()
        }
        supabase.table('vendors').insert(vendor_data).execute()
        
        # Send OTP via Brevo and/or TextBee
        notifications.send_verification_code(email, phone, otp)
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'vendor_id': vendor_id,
            'requires_verification': not is_phone_only
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/verify-otp', methods=['POST'])
def verify_otp_route():
    data = request.json
    email = data.get('email')
    otp = data.get('otp')
    
    if not email or not otp:
        return jsonify({'error': 'Email and OTP required'}), 400
    
    try:
        user = supabase.table('users').select('*').eq('email', email).execute()
        if not user.data:
            return jsonify({'error': 'User not found'}), 404
        
        user = user.data[0]
        
        # Check if already verified
        if user.get('email_verified'):
            # Already verified, just create session
            session_token = str(uuid.uuid4())
            sessions[session_token] = {'user_id': user['id'], 'role': user['role']}
            return jsonify({
                'success': True,
                'session_token': session_token,
                'role': user['role']
            })
        
        if user.get('otp_code') != otp:
            return jsonify({'error': 'Invalid OTP'}), 400
        
        expiry = user.get('otp_expiry')
        if expiry and datetime.fromisoformat(expiry.replace('Z', '+00:00')) < datetime.now(timezone.utc):
            return jsonify({'error': 'OTP expired'}), 400
        
        # Mark email as verified
        supabase.table('users').update({
            'email_verified': True,
            'otp_code': None,
            'otp_expiry': None
        }).eq('id', user['id']).execute()
        
        # Create session
        session_token = str(uuid.uuid4())
        sessions[session_token] = {'user_id': user['id'], 'role': user['role']}
        
        # Send welcome email (only for real emails)
        if email and not email.endswith('@lako.customer') and not email.endswith('@lako.vendor'):
            if user['role'] == 'customer':
                notifications.send_welcome_email(email, user.get('full_name', 'User'), 'customer')
            else:
                vendor = get_vendor_by_user_id(user['id'])
                business_name = vendor.get('business_name') if vendor else None
                notifications.send_welcome_email(email, user.get('full_name', 'User'), 'vendor', business_name)
        
        # Send welcome SMS
        if user.get('phone'):
            if user['role'] == 'customer':
                notifications.send_welcome_sms(user['phone'], user.get('full_name', 'User'), 'customer')
            else:
                vendor = get_vendor_by_user_id(user['id'])
                business_name = vendor.get('business_name') if vendor else None
                notifications.send_welcome_sms(user['phone'], user.get('full_name', 'User'), 'vendor', business_name)
        
        return jsonify({
            'success': True,
            'session_token': session_token,
            'role': user['role']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# ADMIN API ENDPOINTS - ADD THESE TO server.py
# ============================================

@app.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    return jsonify(get_admin_stats())

@app.route('/api/admin/users', methods=['GET'])
def admin_users():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    users = get_all_users_admin()
    return jsonify({'users': users})

@app.route('/api/admin/vendors', methods=['GET'])
def admin_vendors():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    vendors = get_all_vendors_admin()
    return jsonify({'vendors': vendors})

@app.route('/api/admin/user/suspend', methods=['POST'])
def admin_suspend_user():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    if data.get('suspend'):
        suspend_user(data.get('user_id'))
    else:
        unsuspend_user(data.get('user_id'))
    return jsonify({'success': True})

@app.route('/api/admin/vendor/toggle', methods=['POST'])
def admin_toggle_vendor():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    toggle_vendor_active(data.get('vendor_id'), data.get('active'))
    return jsonify({'success': True})

@app.route('/api/auth/check-otp', methods=['GET'])
def check_otp():
    email = request.args.get('email')
    phone = request.args.get('phone')
    
    try:
        if email:
            user = supabase.table('users').select('*').eq('email', email).execute()
            if user.data and user.data[0].get('otp_code'):
                return jsonify({
                    'found': True, 
                    'otp': user.data[0]['otp_code'],
                    'email_verified': user.data[0].get('email_verified', False)
                })
        
        if phone:
            # Clean phone for lookup
            clean_phone = phone.replace('+63', '').replace('-', '').replace(' ', '')
            if clean_phone.startswith('0'):
                clean_phone = clean_phone[1:]
            if len(clean_phone) == 10:
                clean_phone = '+63' + clean_phone
            
            user = supabase.table('users').select('*').eq('phone', clean_phone).execute()
            if user.data and user.data[0].get('otp_code'):
                return jsonify({
                    'found': True, 
                    'otp': user.data[0]['otp_code'],
                    'phone_verified': user.data[0].get('phone_verified', False)
                })
        
        return jsonify({'found': False})
    except Exception as e:
        print(f"Check OTP error: {e}")
        return jsonify({'found': False}), 500

@app.route('/api/auth/resend-otp', methods=['POST'])
def resend_otp():
    data = request.json
    email = data.get('email')
    phone = data.get('phone')
    
    otp = str(random.randint(100000, 999999))
    expiry = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    
    try:
        if email:
            user = supabase.table('users').select('*').eq('email', email).execute()
            if user.data:
                supabase.table('users').update({
                    'otp_code': otp, 
                    'otp_expiry': expiry
                }).eq('email', email).execute()
                
                if not email.endswith('@lako.customer') and not email.endswith('@lako.vendor'):
                    notifications.send_verification_code_email(email, otp)
        
        if phone:
            # Clean phone for lookup
            clean_phone = phone.replace('+63', '').replace('-', '').replace(' ', '')
            if clean_phone.startswith('0'):
                clean_phone = clean_phone[1:]
            if len(clean_phone) == 10:
                clean_phone = '+63' + clean_phone
            
            user = supabase.table('users').select('*').eq('phone', clean_phone).execute()
            if user.data:
                supabase.table('users').update({
                    'otp_code': otp, 
                    'otp_expiry': expiry
                }).eq('phone', clean_phone).execute()
                
                notifications.send_verification_code_sms(clean_phone, otp)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')
    
    try:
        if email:
            user = supabase.table('users').select('*').eq('email', email).execute()
        elif phone:
            # Clean phone for lookup
            clean_phone = phone.replace('+63', '').replace('-', '').replace(' ', '')
            if clean_phone.startswith('0'):
                clean_phone = clean_phone[1:]
            if len(clean_phone) == 10:
                clean_phone = '+63' + clean_phone
            
            user = supabase.table('users').select('*').eq('phone', clean_phone).execute()
        else:
            return jsonify({'error': 'Email or phone required'}), 400
        
        if not user.data:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        user = user.data[0]
        
        if not bcrypt.checkpw(password.encode(), user['password'].encode()):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if user.get('is_suspended'):
            return jsonify({'error': 'Account suspended'}), 403
        
        session_token = str(uuid.uuid4())
        sessions[session_token] = {'user_id': user['id'], 'role': user['role']}
        
        return jsonify({
            'success': True,
            'session_token': session_token,
            'role': user['role']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# ============================================
# CUSTOMER API
# ============================================

@app.route('/api/customer/map/vendors')
def get_nearby_vendors():
    lat = float(request.args.get('lat', 14.5995))
    lng = float(request.args.get('lng', 120.9842))
    vendors = get_vendors_nearby(lat, lng, 50)
    return jsonify({'vendors': vendors})


@app.route('/api/guest/feed')
def guest_feed():
    return jsonify({'posts': get_feed_posts(30)})

@app.route('/health')
def health():
    return jsonify({"status": "ok", "supabase": supabase is not None})

# ============================================
# MISSING API ENDPOINTS - ADD THESE
# ============================================

# ============================================
# COMPLETE CUSTOMER API ENDPOINTS
# Add these to your server.py
# ============================================

# ============================================
# PROFILE ENDPOINTS
# ============================================

@app.route('/api/customer/profile', methods=['GET'])
def get_customer_profile():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = get_user_by_id(session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'full_name': user.get('full_name', ''),
        'phone': user.get('phone', ''),
        'profile_photo': user.get('profile_photo', ''),
        'email': user.get('email', '')
    })

@app.route('/api/customer/update-profile', methods=['POST'])
def update_customer_profile():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    update_data = {}
    if data.get('full_name'):
        update_data['full_name'] = data['full_name']
    if data.get('phone'):
        update_data['phone'] = data['phone']
    
    supabase.table('users').update(update_data).eq('id', session['user_id']).execute()
    return jsonify({'success': True})

@app.route('/api/customer/update-profile-photo', methods=['POST'])
def update_profile_photo():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    photo = data.get('photo')
    
    supabase.table('users').update({'profile_photo': photo}).eq('id', session['user_id']).execute()
    return jsonify({'success': True})

# ============================================
# PREFERENCES ENDPOINTS
# ============================================

@app.route('/api/customer/preferences', methods=['GET'])
def get_customer_preferences():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = get_user_by_id(session['user_id'])
    prefs = user.get('preferences', {})
    if not prefs:
        prefs = {'categories': [], 'priceMin': 0, 'priceMax': 500, 'maxDistance': 10}
    return jsonify(prefs)

@app.route('/api/customer/update-preferences', methods=['POST'])
def update_customer_preferences():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    supabase.table('users').update({'preferences': data}).eq('id', session['user_id']).execute()
    return jsonify({'success': True})

# ============================================
# FOLLOW ENDPOINTS
# ============================================

@app.route('/api/customer/follows', methods=['GET'])
def get_follows():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Get followed vendors
    vendor_follows = supabase.table('vendor_follows').select('vendor_id').eq('user_id', session['user_id']).execute()
    vendors = []
    for vf in (vendor_follows.data or []):
        vendor = get_vendor_by_id(vf['vendor_id'])
        if vendor:
            vendors.append(vendor)
    
    # Get followed users
    user_follows = supabase.table('user_follows').select('followed_id').eq('follower_id', session['user_id']).execute()
    users = [uf['followed_id'] for uf in (user_follows.data or [])]
    
    return jsonify({'vendors': vendors, 'users': users})

@app.route('/api/guest/map/vendors', methods=['GET'])
def guest_nearby_vendors():
    lat = float(request.args.get('lat', 14.5995))
    lng = float(request.args.get('lng', 120.9842))
    vendors = get_vendors_nearby(lat, lng, 50)
    return jsonify({'vendors': vendors})

@app.route('/api/customer/follow-vendor', methods=['POST'])
def follow_vendor():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    vendor_id = data.get('vendor_id')
    
    existing = supabase.table('vendor_follows').select('*').eq('user_id', session['user_id']).eq('vendor_id', vendor_id).execute()
    if existing.data:
        supabase.table('vendor_follows').delete().eq('user_id', session['user_id']).eq('vendor_id', vendor_id).execute()
        return jsonify({'success': True, 'action': 'unfollowed'})
    else:
        supabase.table('vendor_follows').insert({
            'id': str(uuid.uuid4()),
            'user_id': session['user_id'],
            'vendor_id': vendor_id,
            'created_at': utc_now()
        }).execute()
        return jsonify({'success': True, 'action': 'followed'})

@app.route('/api/customer/follow', methods=['POST'])
def follow_user():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    followed_id = data.get('user_id')
    
    existing = supabase.table('user_follows').select('*').eq('follower_id', session['user_id']).eq('followed_id', followed_id).execute()
    if existing.data:
        supabase.table('user_follows').delete().eq('follower_id', session['user_id']).eq('followed_id', followed_id).execute()
        return jsonify({'success': True, 'action': 'unfollowed'})
    else:
        supabase.table('user_follows').insert({
            'id': str(uuid.uuid4()),
            'follower_id': session['user_id'],
            'followed_id': followed_id,
            'created_at': utc_now()
        }).execute()
        return jsonify({'success': True, 'action': 'followed'})

# ============================================
# LOCATION ENDPOINTS
# ============================================

@app.route('/api/customer/update-location', methods=['POST'])
def update_customer_location():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    supabase.table('users').update({
        'last_location_lat': data.get('lat'),
        'last_location_lng': data.get('lng'),
        'last_location_updated': utc_now()
    }).eq('id', session['user_id']).execute()
    
    return jsonify({'success': True})

@app.route('/api/customer/map/vendors', methods=['GET'])
def get_nearby_vendors_api():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    lat = float(request.args.get('lat', 14.5995))
    lng = float(request.args.get('lng', 120.9842))
    
    # Use stored procedure for distance calculation
    result = supabase.rpc('get_nearby_vendors', {
        'lat': lat,
        'lng': lng,
        'radius_km': 50
    }).execute()
    
    vendors = result.data or []
    
    # Get open status for each vendor
    for v in vendors:
        hours = v.get('operating_hours', {})
        if isinstance(hours, str):
            try:
                hours = json.loads(hours)
            except:
                hours = {}
        
        now = datetime.now(timezone.utc)
        day = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'][now.weekday()]
        day_hours = hours.get(day, 'closed')
        
        if day_hours == 'closed':
            v['is_open'] = False
        else:
            try:
                open_h, close_h = map(int, day_hours.split('-')[0].split(':')[0]), map(int, day_hours.split('-')[1].split(':')[0])
                v['is_open'] = open_h <= now.hour < close_h
            except:
                v['is_open'] = False
    
    return jsonify({'vendors': vendors})

# ============================================
# POSTS & FEED ENDPOINTS
# ============================================

@app.route('/api/customer/feed', methods=['GET'])
def customer_feed():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Use the posts_with_users view to get author names
    posts = supabase.table('posts_with_users').select('*').order('created_at', desc=True).execute()
    
    # Get user's liked posts
    user_likes = supabase.table('post_likes').select('post_id').eq('user_id', session['user_id']).execute()
    liked_ids = [like['post_id'] for like in user_likes.data]
    
    formatted_posts = []
    for p in posts.data:
        formatted_posts.append({
            'id': p['id'],
            'user_id': p['user_id'],
            'author': p.get('author_name', 'User'),
            'content': p['content'],
            'images': p.get('images', []),
            'likes': p.get('likes', 0),
            'comment_count': p.get('comment_count', 0),
            'user_liked': p['id'] in liked_ids,
            'created_at': p['created_at']
        })
    
    return jsonify({'posts': formatted_posts})

@app.route('/api/customer/post/create', methods=['POST'])
def create_post():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    post_id = str(uuid.uuid4())
    
    post_data = {
        'id': post_id,
        'user_id': session['user_id'],
        'content': data.get('content'),
        'images': data.get('images', []),
        'likes': 0,
        'comment_count': 0,
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    supabase.table('posts').insert(post_data).execute()
    
    return jsonify({'success': True, 'post_id': post_id})

@app.route('/api/customer/like', methods=['POST'])
def like_post():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    post_id = data.get('post_id')
    
    # Check if already liked
    existing = supabase.table('post_likes').select('*').eq('post_id', post_id).eq('user_id', session['user_id']).execute()
    
    if existing.data:
        # Unlike - remove the like
        supabase.table('post_likes').delete().eq('post_id', post_id).eq('user_id', session['user_id']).execute()
        return jsonify({'success': True, 'liked': False})
    else:
        # Like - add the like
        like_id = str(uuid.uuid4())
        supabase.table('post_likes').insert({
            'id': like_id,
            'post_id': post_id,
            'user_id': session['user_id'],
            'created_at': datetime.now(timezone.utc).isoformat()
        }).execute()
        return jsonify({'success': True, 'liked': True})

@app.route('/api/customer/user/profile/<user_id>', methods=['GET'])
def get_user_profile(user_id):
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Get user info
    user = supabase.table('users').select('id, full_name, email').eq('id', user_id).execute()
    if not user.data:
        return jsonify({'error': 'User not found'}), 404
    
    # Get post count
    posts = supabase.table('posts').select('id', count='exact').eq('user_id', user_id).execute()
    post_count = posts.count if hasattr(posts, 'count') else len(posts.data)
    
    # Get follower count (users who follow this user)
    followers = supabase.table('user_follows').select('id', count='exact').eq('following_id', user_id).execute()
    follower_count = followers.count if hasattr(followers, 'count') else len(followers.data)
    
    # Get following count (users this user follows)
    following = supabase.table('user_follows').select('id', count='exact').eq('follower_id', user_id).execute()
    following_count = following.count if hasattr(following, 'count') else len(following.data)
    
    return jsonify({
        'id': user.data[0]['id'],
        'full_name': user.data[0].get('full_name', 'User'),
        'email': user.data[0].get('email', ''),
        'post_count': post_count,
        'follower_count': follower_count,
        'following_count': following_count
    })

@app.route('/api/customer/profile', methods=['GET'])
def get_my_profile():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = supabase.table('users').select('id, full_name, email, phone').eq('id', session['user_id']).execute()
    
    if not user.data:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'id': user.data[0]['id'],
        'full_name': user.data[0].get('full_name', ''),
        'email': user.data[0].get('email', ''),
        'phone': user.data[0].get('phone', '')
    })

@app.route('/api/customer/update-profile', methods=['POST'])
def update_profile():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    
    update_data = {}
    if 'full_name' in data:
        update_data['full_name'] = data['full_name']
    if 'phone' in data:
        update_data['phone'] = data['phone']
    
    supabase.table('users').update(update_data).eq('id', session['user_id']).execute()
    
    return jsonify({'success': True})

@app.route('/api/customer/post/comments/<post_id>', methods=['GET'])
def get_post_comments(post_id):
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Use the comments_with_users view to get author names
    comments = supabase.table('comments_with_users').select('*').eq('post_id', post_id).order('created_at', desc=False).execute()
    
    formatted_comments = []
    for c in comments.data:
        formatted_comments.append({
            'id': c['id'],
            'post_id': c['post_id'],
            'user_id': c['user_id'],
            'author': c.get('author_name', 'User'),
            'content': c['content'],
            'created_at': c['created_at']
        })
    
    return jsonify({'comments': formatted_comments})

@app.route('/api/customer/comment', methods=['POST'])
def add_comment():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    comment_id = str(uuid.uuid4())
    
    comment_data = {
        'id': comment_id,
        'post_id': data.get('post_id'),
        'user_id': session['user_id'],
        'content': data.get('comment'),
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    supabase.table('comments').insert(comment_data).execute()
    
    return jsonify({'success': True, 'comment_id': comment_id})

@app.route('/api/customer/post/delete', methods=['POST'])
def delete_post():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    post_id = data.get('post_id')
    
    # Verify ownership
    post = supabase.table('posts').select('user_id').eq('id', post_id).execute()
    if not post.data:
        return jsonify({'error': 'Post not found'}), 404
    
    if post.data[0]['user_id'] != session['user_id']:
        return jsonify({'error': 'Not authorized to delete this post'}), 403
    
    # Delete post (cascade will delete comments and likes)
    supabase.table('posts').delete().eq('id', post_id).execute()
    
    return jsonify({'success': True})

@app.route('/api/vendor/profile', methods=['GET'])
def get_vendor_profile():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor':
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = get_user_by_id(session['user_id'])
    return jsonify({
        'user_name': user.get('full_name', ''),
        'email': user.get('email', ''),
        'phone': user.get('phone', '')
    })

@app.route('/api/customer/reviews/<vendor_id>', methods=['GET'])
def get_customer_reviews(vendor_id):
    reviews = get_reviews_by_vendor(vendor_id)
    return jsonify({'reviews': reviews})

@app.route('/api/customer/review/create', methods=['POST'])
def create_customer_review():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'customer':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    review_id = create_review(session['user_id'], data.get('vendor_id'), data.get('rating'), data.get('comment'))
    
    if review_id:
        return jsonify({'success': True, 'review_id': review_id})
    return jsonify({'error': 'Failed to create review'}), 500

# ============================================
# PRODUCTS ENDPOINTS
# ============================================

@app.route('/api/customer/products/<vendor_id>', methods=['GET'])
def get_vendor_products(vendor_id):
    """Get products for a specific vendor"""
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    products_result = supabase.table('products')\
        .select('*')\
        .eq('vendor_id', vendor_id)\
        .execute()
    
    return jsonify({'products': products_result.data})

# ============================================
# SHORTLIST ENDPOINTS
# ============================================

@app.route('/api/customer/shortlist', methods=['GET'])
def get_shortlist_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    vendors = get_shortlist(session['user_id'])
    return jsonify({'vendors': vendors})

@app.route('/api/customer/shortlist/toggle', methods=['POST'])
def toggle_shortlist_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    vendor_id = data.get('vendor_id')
    existing = get_shortlist(session['user_id'])
    
    if any(v['id'] == vendor_id for v in existing):
        remove_from_shortlist(session['user_id'], vendor_id)
        return jsonify({'success': True, 'action': 'removed'})
    else:
        add_to_shortlist(session['user_id'], vendor_id)
        return jsonify({'success': True, 'action': 'added'})

# ============================================
# ANALYTICS ENDPOINTS
# ============================================

@app.route('/api/customer/analytics', methods=['GET'])
def get_customer_analytics():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    
    # Get reviews written
    reviews = supabase.table('reviews').select('*', count='exact').eq('customer_id', user_id).execute()
    reviews_written = reviews.count or 0
    
    # Get posts created
    posts = supabase.table('posts').select('*', count='exact').eq('user_id', user_id).is_('parent_id', 'null').execute()
    posts_created = posts.count or 0
    
    # Get likes given
    likes = supabase.table('post_likes').select('*', count='exact').eq('user_id', user_id).execute()
    likes_given = likes.count or 0
    
    # Get vendors visited (from reviews)
    visited_vendors = supabase.table('reviews').select('vendor_id').eq('customer_id', user_id).execute()
    total_visits = len(set([v['vendor_id'] for v in (visited_vendors.data or [])]))
    
    # Weekly activity (last 7 days)
    weekly_activity = []
    today = datetime.now(timezone.utc).date()
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        day_start = datetime.combine(date, datetime.min.time()).replace(tzinfo=timezone.utc).isoformat()
        day_end = datetime.combine(date + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc).isoformat()
        
        day_posts = supabase.table('posts').select('*', count='exact').eq('user_id', user_id).gte('created_at', day_start).lt('created_at', day_end).execute()
        day_likes = supabase.table('post_likes').select('*', count='exact').eq('user_id', user_id).gte('created_at', day_start).lt('created_at', day_end).execute()
        weekly_activity.append((day_posts.count or 0) + (day_likes.count or 0))
    
    return jsonify({
        'total_visits': total_visits,
        'reviews_written': reviews_written,
        'posts_created': posts_created,
        'likes_given': likes_given,
        'weekly_activity': weekly_activity
    })

# ============================================
# VENDOR API ROUTES - COMPLETE WITH REAL DATA
# ============================================

@app.route('/api/vendor/data', methods=['GET'])
def get_vendor_data():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor':
        return jsonify({'error': 'Unauthorized'}), 401
    
    vendor = get_vendor_by_user_id(session['user_id'])
    if not vendor:
        return jsonify({'error': 'Vendor not found'}), 404
    
    # Get products
    products_result = supabase.table('products')\
        .select('*')\
        .eq('vendor_id', vendor['id'])\
        .execute()
    
    products = []
    for p in products_result.data:
        products.append({
            'id': p.get('id'),
            'name': p.get('name'),
            'description': p.get('description', ''),
            'category': p.get('category', ''),
            'price': float(p.get('price', 0)),
            'stock': p.get('stock', 0),
            'images': p.get('images', []),
            'priceTiers': p.get('priceTiers', [])  # Add priceTiers
        })
    
    # Get posts
    posts_result = supabase.table('posts')\
        .select('*')\
        .eq('user_id', session['user_id'])\
        .order('created_at', desc=True)\
        .execute()
    
    posts = []
    for post in posts_result.data:
        posts.append({
            'id': post.get('id'),
            'content': post.get('content'),
            'images': post.get('images', []),
            'likes': post.get('likes', 0),
            'comment_count': post.get('comment_count', 0),
            'saves': post.get('saves', 0),
            'created_at': post.get('created_at')
        })
    
    return jsonify({
        'vendor': vendor,
        'products': products,
        'posts': posts
    })

@app.route('/api/vendor/update-open-status', methods=['POST'])
def update_open_status():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    vendor = get_vendor_by_user_id(session['user_id'])
    if not vendor:
        return jsonify({'error': 'Vendor not found'}), 404
    
    supabase.table('vendors').update({'is_open': data.get('is_open')}).eq('id', vendor['id']).execute()
    return jsonify({'success': True})

@app.route('/api/vendor/posts', methods=['GET'])
def get_vendor_posts_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor':
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Fix: Use specific foreign key name or fetch separately
    posts = supabase.table('posts')\
        .select('*')\
        .eq('user_id', session['user_id'])\
        .order('created_at', desc=True)\
        .execute()
    
    # Get user names separately if needed
    posts_data = []
    for post in posts.data:
        # Get vendor name from vendors table
        vendor = get_vendor_by_user_id(session['user_id'])
        posts_data.append({
            'id': post.get('id'),
            'content': post.get('content'),
            'images': post.get('images', []),
            'likes': post.get('likes', 0),
            'comment_count': post.get('comment_count', 0),
            'saves': post.get('saves', 0),
            'created_at': post.get('created_at'),
            'business_name': vendor.get('business_name') if vendor else 'Vendor'
        })
    
    return jsonify({'posts': posts_data})

@app.route('/api/vendor/post/create', methods=['POST'])
def create_vendor_post():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    post_id = create_post(session['user_id'], session['role'], data.get('content'), data.get('images', []))
    return jsonify({'success': True, 'post_id': post_id}) if post_id else jsonify({'error': 'Failed'}), 500

@app.route('/api/vendor/post/delete', methods=['POST'])
def delete_vendor_post():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    try:
        # Delete post and its likes
        supabase.table('post_likes').delete().eq('post_id', data.get('post_id')).execute()
        supabase.table('posts').delete().eq('id', data.get('post_id')).eq('user_id', session['user_id']).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vendor/analytics', methods=['GET'])
def get_vendor_analytics():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor':
        return jsonify({'error': 'Unauthorized'}), 401
    
    vendor = get_vendor_by_user_id(session['user_id'])
    if not vendor:
        return jsonify({'error': 'Vendor not found'}), 404
    
    vendor_id = vendor['id']
    
    # ============================================
    # 1. GET SAVES COUNT (how many customers saved this shop)
    # ============================================
    saves = supabase.table('shortlists').select('*', count='exact').eq('vendor_id', vendor_id).execute()
    total_saves = saves.count or 0
    
    # ============================================
    # 2. GET POST LIKES AND ENGAGEMENT
    # ============================================
    vendor_posts = supabase.table('posts').select('id').eq('user_id', session['user_id']).execute()
    post_ids = [p['id'] for p in (vendor_posts.data or [])]
    
    total_likes = 0
    total_comments = 0
    if post_ids:
        likes = supabase.table('post_likes').select('*', count='exact').in_('post_id', post_ids).execute()
        total_likes = likes.count or 0
        
        comments = supabase.table('posts').select('*', count='exact').in_('parent_id', post_ids).execute()
        total_comments = comments.count or 0
    
    post_engagement = total_likes + total_comments
    
    # ============================================
    # 3. GET WEEKLY TRAFFIC (last 7 days)
    # ============================================
    weekly_labels = []
    weekly_traffic = []
    today = datetime.now(timezone.utc).date()
    
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        weekly_labels.append(date.strftime('%a'))
        
        # Count views from traffic_log or from vendor's traffic_count by day
        # For now, get from reviews created per day as proxy
        day_start = datetime.combine(date, datetime.min.time()).replace(tzinfo=timezone.utc).isoformat()
        day_end = datetime.combine(date + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc).isoformat()
        
        views = supabase.table('reviews').select('*', count='exact').eq('vendor_id', vendor_id).gte('created_at', day_start).lt('created_at', day_end).execute()
        weekly_traffic.append(views.count or 0)
    
    # ============================================
    # 4. GET PEAK HOURS (from reviews and traffic)
    # ============================================
    peak_hours = {str(h): 0 for h in range(8, 22)}
    
    # Get all reviews for this vendor to analyze peak hours
    all_reviews = supabase.table('reviews').select('created_at').eq('vendor_id', vendor_id).execute()
    
    for review in (all_reviews.data or []):
        try:
            created_at = review.get('created_at')
            if created_at:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                hour = dt.hour
                if 8 <= hour <= 21:
                    peak_hours[str(hour)] = peak_hours.get(str(hour), 0) + 1
        except:
            pass
    
    # Filter out hours with zero activity
    peak_hours = {k: v for k, v in peak_hours.items() if v > 0}
    
    # ============================================
    # 5. SUGGESTED OPERATING HOURS (based on peak hours)
    # ============================================
    suggested_hours = None
    if peak_hours:
        hours_list = [(int(h), count) for h, count in peak_hours.items()]
        hours_list.sort(key=lambda x: x[1], reverse=True)
        
        if hours_list:
            peak_start = hours_list[0][0]
            # Find continuous block of high traffic
            suggested_start = max(8, peak_start - 1)
            suggested_end = min(21, peak_start + 3)
            suggested_hours = f"{suggested_start}:00 AM - {suggested_end}:00 PM"
    
    # ============================================
    # 6. TREND SCORE (based on recent activity)
    # ============================================
    # Calculate trend score from last 30 days
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    
    recent_reviews = supabase.table('reviews').select('*', count='exact').eq('vendor_id', vendor_id).gte('created_at', thirty_days_ago).execute()
    recent_saves = supabase.table('shortlists').select('*', count='exact').eq('vendor_id', vendor_id).gte('created_at', thirty_days_ago).execute()
    recent_posts = supabase.table('posts').select('*', count='exact').eq('user_id', session['user_id']).gte('created_at', thirty_days_ago).execute()
    recent_likes = total_likes  # Already from all time, but could be filtered
    
    trend_score = min(100, int(
        (recent_reviews.count or 0) * 3 +
        (recent_saves.count or 0) * 2 +
        (recent_posts.count or 0) * 5 +
        (total_likes * 1)
    ))
    
    # ============================================
    # 7. MONTHLY ENGAGEMENT (last 4 weeks)
    # ============================================
    monthly_engagement = []
    for week in range(4):
        week_start = (datetime.now(timezone.utc) - timedelta(days=(week+1)*7)).isoformat()
        week_end = (datetime.now(timezone.utc) - timedelta(days=week*7)).isoformat()
        
        week_likes = 0
        if post_ids:
            week_likes_data = supabase.table('post_likes').select('*', count='exact').in_('post_id', post_ids).gte('created_at', week_start).lt('created_at', week_end).execute()
            week_likes = week_likes_data.count or 0
        
        monthly_engagement.append(week_likes)
    
    monthly_engagement.reverse()
    
    # ============================================
    # 8. CUSTOMER HEATMAP DATA (locations where customers viewed)
    # ============================================
    # Get unique customer locations from reviews and shortlists
    heatmap_locations = []
    
    # Get customers who reviewed
    reviewers = supabase.table('reviews').select('customer_id').eq('vendor_id', vendor_id).execute()
    customer_ids = list(set([r['customer_id'] for r in (reviewers.data or [])]))
    
    # Get customer locations from their profile or activity
    for customer_id in customer_ids[:50]:  # Limit for performance
        customer = get_user_by_id(customer_id)
        if customer and customer.get('last_location_lat') and customer.get('last_location_lng'):
            heatmap_locations.append({
                'lat': customer['last_location_lat'],
                'lng': customer['last_location_lng'],
                'intensity': 0.5
            })
    
    return jsonify({
        'total_visits': vendor.get('traffic_count', 0),
        'avg_rating': vendor.get('rating', 0),
        'total_saves': total_saves,
        'total_likes': total_likes,
        'post_engagement': post_engagement,
        'trend_score': trend_score,
        'weekly_labels': weekly_labels,
        'weekly_traffic': weekly_traffic,
        'peak_hours': peak_hours,
        'suggested_hours': suggested_hours,
        'monthly_engagement': monthly_engagement,
        'heatmap_locations': heatmap_locations
    })

@app.route('/api/vendor/reviews', methods=['GET'])
def get_vendor_reviews_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor':
        return jsonify({'error': 'Unauthorized'}), 401
    
    vendor = get_vendor_by_user_id(session['user_id'])
    if not vendor:
        return jsonify({'error': 'Vendor not found'}), 404
    
    # Fetch reviews from Supabase reviews table
    reviews_result = supabase.table('reviews')\
        .select('*')\
        .eq('vendor_id', vendor['id'])\
        .order('created_at', desc=True)\
        .execute()
    
    reviews = []
    for r in reviews_result.data:
        # Get customer name from users table if available
        customer_name = 'Customer'
        if r.get('user_id'):
            user_result = supabase.table('users').select('name').eq('id', r['user_id']).execute()
            if user_result.data:
                customer_name = user_result.data[0].get('name', 'Customer')
        elif r.get('customer_name'):
            customer_name = r['customer_name']
        
        reviews.append({
            'id': r['id'],
            'customer_name': customer_name,
            'rating': r.get('rating', 0),
            'comment': r.get('comment', ''),
            'created_at': r.get('created_at')
        })
    
    return jsonify({'reviews': reviews})

@app.route('/api/vendor/product/create', methods=['POST'])
def create_product_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor':
        return jsonify({'error': 'Unauthorized'}), 401
    
    vendor = get_vendor_by_user_id(session['user_id'])
    if not vendor:
        return jsonify({'error': 'Vendor not found'}), 404
    
    data = request.json
    
    # Create product with priceTiers
    product_data = {
        'vendor_id': vendor['id'],
        'name': data.get('name'),
        'description': data.get('description'),
        'category': data.get('category'),
        'price': data.get('price'),
        'images': data.get('images', []),
        'stock': 0,
        'priceTiers': data.get('priceTiers', [])  # ADD THIS LINE
    }
    
    result = supabase.table('products').insert(product_data).execute()
    
    if result.data:
        return jsonify({'success': True, 'product_id': result.data[0]['id']})
    return jsonify({'error': 'Failed to create product'}), 500

@app.route('/api/vendor/product/update', methods=['POST'])
def update_product_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    product_id = data.get('product_id')
    
    # Verify product belongs to this vendor
    product = supabase.table('products').select('vendor_id').eq('id', product_id).execute()
    if not product.data:
        return jsonify({'error': 'Product not found'}), 404
    
    vendor = get_vendor_by_user_id(session['user_id'])
    if product.data[0]['vendor_id'] != vendor['id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Update product data INCLUDING priceTiers
    product_data = {
        'name': data.get('name'),
        'description': data.get('description'),
        'category': data.get('category'),
        'price': data.get('price'),
        'stock': 0,
        'images': data.get('images', []),
        'priceTiers': data.get('priceTiers', [])  # ADD THIS LINE
    }
    
    # Remove None values
    product_data = {k: v for k, v in product_data.items() if v is not None}
    
    result = supabase.table('products').update(product_data).eq('id', product_id).execute()
    
    if result.data:
        return jsonify({'success': True})
    return jsonify({'error': 'Failed to update product'}), 500

@app.route('/api/vendor/product/delete', methods=['POST'])
def delete_product_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    product_id = data.get('product_id')
    
    # Verify product belongs to this vendor
    product = supabase.table('products').select('vendor_id').eq('id', product_id).execute()
    if not product.data:
        return jsonify({'error': 'Product not found'}), 404
    
    vendor = get_vendor_by_user_id(session['user_id'])
    if product.data[0]['vendor_id'] != vendor['id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    result = supabase.table('products').delete().eq('id', product_id).execute()
    
    if result.data or not result.error:
        return jsonify({'success': True})
    return jsonify({'error': 'Failed to delete product'}), 500

@app.route('/api/vendor/update-hours', methods=['POST'])
def update_hours_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor':
        return jsonify({'error': 'Unauthorized'}), 401
    
    vendor = get_vendor_by_user_id(session['user_id'])
    if not vendor:
        return jsonify({'error': 'Vendor not found'}), 404
    
    data = request.json
    try:
        supabase.table('vendors').update({'operating_hours': data.get('hours')}).eq('id', vendor['id']).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vendor/update-location', methods=['POST'])
def update_location_route():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'vendor':
        return jsonify({'error': 'Unauthorized'}), 401
    
    vendor = get_vendor_by_user_id(session['user_id'])
    if not vendor:
        return jsonify({'error': 'Vendor not found'}), 404
    
    data = request.json
    try:
        supabase.table('vendors').update({
            'latitude': data.get('latitude'),
            'longitude': data.get('longitude')
        }).eq('id', vendor['id']).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
# ============================================
# ADMIN ADDITIONAL ENDPOINTS
# ============================================

@app.route('/api/admin/profile', methods=['GET'])
def get_admin_profile():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = get_user_by_id(session['user_id'])
    return jsonify({
        'full_name': user.get('full_name', 'Admin'),
        'email': user.get('email', '')
    })

@app.route('/api/admin/vendor/<vendor_id>/products', methods=['GET'])
def admin_get_vendor_products(vendor_id):
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    products = get_products_by_vendor(vendor_id)
    return jsonify(products)

@app.route('/api/admin/product/create', methods=['POST'])
def admin_create_product():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    product_id = create_product(
        data.get('vendor_id'),
        data.get('name'),
        data.get('description'),
        data.get('category'),
        data.get('price'),
        data.get('images', []),
        0
    )
    
    if product_id:
        return jsonify({'success': True, 'product_id': product_id})
    return jsonify({'error': 'Failed to create product'}), 500

@app.route('/api/admin/product/update', methods=['POST'])
def admin_update_product():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    success = update_product(data.get('product_id'), {
        'name': data.get('name'),
        'description': data.get('description'),
        'category': data.get('category'),
        'price': data.get('price'),
        'stock': 0,
        'images': data.get('images', [])
    })
    
    return jsonify({'success': success})

@app.route('/api/admin/product/delete', methods=['POST'])
def admin_delete_product():
    session = require_session(request.headers.get('X-Session-Token'))
    if not session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    success = delete_product(data.get('product_id'))
    return jsonify({'success': success})
# ============================================
# RUN APP
# ============================================

if __name__ == '__main__':
    admin = get_user_by_email('admin@lako.app')
    if not admin:
        create_user('admin@lako.app', 'admin123', 'admin', 'System Admin', '')
        print("✓ Created admin user: admin@lako.app / admin123")
    
    print("=" * 60)
    print("🍢 Lako Server - Complete Edition")
    print("=" * 60)
    print(f"✓ Supabase: Connected")
    print(f"✓ Admin Login: admin@lako.app / admin123")
    print("=" * 60)
    print("🌐 Server running at http://localhost:5000")
    print("=" * 60)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=DEBUG)