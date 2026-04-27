#!/usr/bin/env python3
"""
Test script for Brevo Email and TextBee SMS
Run: python test_notifications.py
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================================
# CONFIGURATION (from .env)
# ============================================

BREVO_API_KEY = os.environ.get('BREVO_API_KEY')
BREVO_SENDER_EMAIL = os.environ.get('BREVO_SENDER_EMAIL')
BREVO_SENDER_NAME = os.environ.get('BREVO_SENDER_NAME', 'Lako')
TEXTBEE_API_KEY = os.environ.get('TEXTBEE_API_KEY')
TEXTBEE_SENDER_ID = os.environ.get('TEXTBEE_SENDER_ID', 'Lako')
APP_NAME = os.environ.get('APP_NAME', 'Lako')
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# ============================================
# EMAIL FUNCTION (Brevo)
# ============================================

def send_test_email(email):
    """Test sending email via Brevo"""
    print("\n" + "="*60)
    print("📧 TESTING BREVO EMAIL")
    print("="*60)
    
    if not BREVO_API_KEY:
        print("❌ BREVO_API_KEY not found in .env file!")
        return False
    
    if not BREVO_SENDER_EMAIL:
        print("❌ BREVO_SENDER_EMAIL not found in .env file!")
        return False
    
    print(f"📧 Sending test email to: {email}")
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{APP_NAME} Test Email</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f5faf5; }}
            .container {{ max-width: 500px; margin: 0 auto; padding: 20px; }}
            .card {{ background: white; border-radius: 24px; padding: 30px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
            .icon {{ font-size: 48px; margin-bottom: 16px; }}
            h2 {{ color: #2d8c3c; }}
            .code {{ font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #2d8c3c; background: #f0f4f0; padding: 16px; border-radius: 12px; display: inline-block; }}
            .footer {{ margin-top: 20px; font-size: 11px; color: #8ba88b; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div class="icon">🍢</div>
                <h2>{APP_NAME} Test Email</h2>
                <p>This is a test email from your {APP_NAME} application!</p>
                <p>Your verification code would be:</p>
                <div class="code">123456</div>
                <p class="footer">Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    payload = {
        "sender": {"name": BREVO_SENDER_NAME, "email": BREVO_SENDER_EMAIL},
        "to": [{"email": email}],
        "subject": f"🧪 {APP_NAME} Test Email",
        "htmlContent": html_content
    }
    
    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    print(f"\n📤 Sending request to Brevo...")
    print(f"   From: {BREVO_SENDER_NAME} <{BREVO_SENDER_EMAIL}>")
    print(f"   To: {email}")
    
    try:
        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"\n📥 Response Status: {response.status_code}")
        
        if response.status_code in [200, 201, 202]:
            print("✅ Email sent successfully!")
            print("   📧 Check your inbox (and spam folder)")
            return True
        else:
            print(f"❌ Email failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False

# ============================================
# SMS FUNCTION (TextBee)
# ============================================

def send_test_sms(phone):
    """Test sending SMS via TextBee using Sender ID"""
    print("\n" + "="*60)
    print("📱 TESTING TEXTBEE SMS")
    print("="*60)
    
    if not TEXTBEE_API_KEY:
        print("❌ TEXTBEE_API_KEY not found in .env file!")
        return False
    
    print(f"📱 Sending test SMS to: {phone}")
    
    # Clean phone number to 63XXXXXXXXXX format
    original_phone = phone
    phone = phone.replace('+63', '').replace('-', '').replace(' ', '')
    if phone.startswith('0'):
        phone = phone[1:]
    if len(phone) == 10:
        phone = '63' + phone
    
    message = f"🧪 {APP_NAME} Test SMS!\n\nThis is a test message from your {APP_NAME} application.\n\nYour verification code would be: 123456\n\n{APP_NAME} - Find the best street food in Tiaong!"
    
    payload = {
        "to": phone,
        "sender_id": TEXTBEE_SENDER_ID,
        "message": message
    }
    
    headers = {
        "Authorization": f"Bearer {TEXTBEE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    print(f"\n📤 Sending request to TextBee...")
    print(f"   From Sender ID: {TEXTBEE_SENDER_ID}")
    print(f"   To: {original_phone} -> {phone}")
    
    try:
        response = requests.post(
            "https://api.textbee.dev/api/v1/sms/send",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"\n📥 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SMS sent successfully!")
            result = response.json() if response.text else {"status": "ok"}
            print(f"   Response: {result}")
            return True
        else:
            print(f"❌ SMS failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ SMS error: {e}")
        return False

# ============================================
# OTP TEST (Email + SMS together)
# ============================================

def send_test_otp(email, phone):
    """Send test OTP via both email and SMS"""
    print("\n" + "="*60)
    print("🔐 TESTING OTP (Email + SMS)")
    print("="*60)
    
    otp = "123456"
    results = {'email': False, 'sms': False}
    
    # Send email
    if email:
        print(f"\n📧 Sending OTP to email: {email}")
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{APP_NAME} OTP Test</title>
            <style>
                body {{ font-family: Arial, sans-serif; background: #f5faf5; }}
                .container {{ max-width: 500px; margin: 0 auto; padding: 20px; }}
                .card {{ background: white; border-radius: 24px; padding: 30px; text-align: center; }}
                .otp {{ font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #2d8c3c; background: #f0f4f0; padding: 16px; border-radius: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <h2>🔐 {APP_NAME} OTP Test</h2>
                    <p>Your test OTP code is:</p>
                    <div class="otp">{otp}</div>
                    <p>This code expires in 10 minutes.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        try:
            response = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
                json={
                    "sender": {"name": BREVO_SENDER_NAME, "email": BREVO_SENDER_EMAIL},
                    "to": [{"email": email}],
                    "subject": f"🔐 Your {APP_NAME} OTP Code",
                    "htmlContent": html_content
                },
                timeout=30
            )
            results['email'] = response.status_code in [200, 201, 202]
            print("✅ Email OTP sent!" if results['email'] else "❌ Email OTP failed")
        except Exception as e:
            print(f"❌ Email error: {e}")
    
    # Send SMS
    if phone:
        print(f"\n📱 Sending OTP to phone: {phone}")
        clean_phone = phone.replace('+63', '').replace('-', '').replace(' ', '')
        if clean_phone.startswith('0'):
            clean_phone = clean_phone[1:]
        if len(clean_phone) == 10:
            clean_phone = '63' + clean_phone
        
        message = f"🔐 Your {APP_NAME} OTP code is: {otp}\nValid for 10 minutes.\n\n{APP_NAME} - Find the best street food in Tiaong!"
        
        try:
            response = requests.post(
                "https://api.textbee.dev/api/v1/sms/send",
                headers={"Authorization": f"Bearer {TEXTBEE_API_KEY}", "Content-Type": "application/json"},
                json={"to": clean_phone, "sender_id": TEXTBEE_SENDER_ID, "message": message},
                timeout=30
            )
            results['sms'] = response.status_code == 200
            print("✅ SMS OTP sent!" if results['sms'] else "❌ SMS OTP failed")
        except Exception as e:
            print(f"❌ SMS error: {e}")
    
    return results

# ============================================
# MAIN MENU
# ============================================

def main():
    print("\n" + "="*60)
    print(f"   {APP_NAME} - Notification Test Suite")
    print("="*60)
    print("\n📋 Checking environment variables...")
    
    # Display loaded config
    print(f"   BREVO_API_KEY: {'✅ Loaded' if BREVO_API_KEY else '❌ Missing'}")
    print(f"   BREVO_SENDER_EMAIL: {BREVO_SENDER_EMAIL if BREVO_SENDER_EMAIL else '❌ Missing'}")
    print(f"   BREVO_SENDER_NAME: {BREVO_SENDER_NAME}")
    print(f"   TEXTBEE_API_KEY: {'✅ Loaded' if TEXTBEE_API_KEY else '❌ Missing'}")
    print(f"   TEXTBEE_SENDER_ID: {TEXTBEE_SENDER_ID}")
    print(f"   DEBUG: {DEBUG}")
    
    if BREVO_API_KEY and BREVO_SENDER_EMAIL:
        print("\n💡 Email will be sent from: {} <{}>".format(BREVO_SENDER_NAME, BREVO_SENDER_EMAIL))
        print("   Check your spam folder if you don't see the email!")
    
    while True:
        print("\n" + "-"*40)
        print("📱 Choose test option:")
        print("   1) Send test EMAIL only")
        print("   2) Send test SMS only")
        print("   3) Send test OTP (Email + SMS together)")
        print("   4) Exit")
        print("-"*40)
        
        choice = input("\n👉 Enter your choice (1-4): ").strip()
        
        if choice == '1':
            email = input("📧 Enter email address: ").strip()
            if email:
                send_test_email(email)
            else:
                print("❌ Email cannot be empty!")
        
        elif choice == '2':
            phone = input("📱 Enter phone number (e.g., 09123456789): ").strip()
            if phone:
                send_test_sms(phone)
            else:
                print("❌ Phone number cannot be empty!")
        
        elif choice == '3':
            email = input("📧 Enter email address (or press Enter to skip): ").strip()
            phone = input("📱 Enter phone number (e.g., 09123456789, or press Enter to skip): ").strip()
            
            if not email and not phone:
                print("❌ At least one of email or phone is required!")
            else:
                results = send_test_otp(email if email else None, phone if phone else None)
                print("\n📊 Results:")
                print(f"   Email: {'✅ Sent' if results['email'] else '❌ Failed or skipped'}")
                print(f"   SMS: {'✅ Sent' if results['sms'] else '❌ Failed or skipped'}")
        
        elif choice == '4':
            print("\n👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid choice. Please enter 1-4")

if __name__ == "__main__":
    main()