"""
Notification system - Email (Gmail) and SMS (Twilio)
Handles user notifications, alerts, and announcements
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os
from config import SMTP_USERNAME, SMTP_PASSWORD, SMTP_SERVER, SMTP_PORT

# Try to import Twilio (optional)
try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

class Notifier:
    """Handle all notifications"""
    
    def __init__(self):
        self.smtp_server = SMTP_SERVER
        self.smtp_port = SMTP_PORT
        self.sender_email = SMTP_USERNAME
        self.sender_password = SMTP_PASSWORD
        
        # Twilio configuration (optional - free SMS)
        if TWILIO_AVAILABLE:
            self.twilio_client = Client(
                os.getenv('TWILIO_ACCOUNT_SID', ''),
                os.getenv('TWILIO_AUTH_TOKEN', '')
            )
            self.twilio_number = os.getenv('TWILIO_PHONE_NUMBER', '')
        else:
            self.twilio_client = None
    
    # ============== EMAIL NOTIFICATIONS ==============
    
    def send_account_suspension_email(self, user_email, full_name, reason="Violating community guidelines"):
        """Notify user of account suspension"""
        subject = "⚠️ Account Suspension Notice - Lako"
        
        html_body = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
              <h2 style="color: #d32f2f;">Account Suspension</h2>
              
              <p>Hi {full_name},</p>
              
              <p>Your Lako account has been suspended due to:</p>
              <p style="background: #ffebee; padding: 10px; border-left: 4px solid #d32f2f;">
                <strong>{reason}</strong>
              </p>
              
              <p><strong>What this means:</strong></p>
              <ul>
                <li>You cannot access your account</li>
                <li>Your listings/posts are hidden</li>
                <li>You cannot post or comment</li>
              </ul>
              
              <p><strong>Next steps:</strong></p>
              <p>To appeal this decision, please contact us at support@lako.com with:</p>
              <ul>
                <li>Your account email</li>
                <li>Why you believe this was a mistake</li>
                <li>Any relevant context</li>
              </ul>
              
              <p>We review appeals within 48 hours.</p>
              
              <p>Best regards,<br/>Lako Trust & Safety Team</p>
              <hr/>
              <p style="font-size: 12px; color: #666;">
                Timestamp: {datetime.now().isoformat()}
              </p>
            </div>
          </body>
        </html>
        """
        
        return self.send_email(user_email, subject, html_body)
    
    def send_important_announcement_email(self, user_email, full_name, title, content):
        """Send important announcement to user"""
        subject = f"📢 {title} - Lako Announcement"
        
        html_body = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
              <h2 style="color: #1f2937;">{title}</h2>
              
              <p>Hi {full_name},</p>
              
              <div style="background: #f0f9ff; padding: 15px; border-left: 4px solid #3b82f6; margin: 20px 0;">
                {content}
              </div>
              
              <p>Thank you for being part of the Lako community.</p>
              
              <p>Best regards,<br/>Lako Team</p>
              <hr/>
              <p style="font-size: 12px; color: #666;">
                Timestamp: {datetime.now().isoformat()}
              </p>
            </div>
          </body>
        </html>
        """
        
        return self.send_email(user_email, subject, html_body)
    
    def send_promotional_email(self, user_email, full_name, promo_title, promo_content, promo_link=""):
        """Send promotional/ad email"""
        subject = f"🎉 {promo_title} - Special Offer from Lako"
        
        cta_button = f'<a href="{promo_link}" style="background: #10b981; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">Learn More</a>' if promo_link else ""
        
        html_body = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
              <h2 style="color: #10b981;">{promo_title}</h2>
              
              <p>Hi {full_name},</p>
              
              <div style="background: #f0fdf4; padding: 20px; border-radius: 8px; margin: 20px 0;">
                {promo_content}
              </div>
              
              <center style="margin: 20px 0;">
                {cta_button}
              </center>
              
              <p><em>This is a promotional message. You can manage your preferences in your account settings.</em></p>
              
              <p>Best regards,<br/>Lako Team</p>
              <hr/>
              <p style="font-size: 12px; color: #666;">
                Timestamp: {datetime.now().isoformat()}
              </p>
            </div>
          </body>
        </html>
        """
        
        return self.send_email(user_email, subject, html_body)
    
    def send_email(self, recipient_email, subject, html_body):
        """Generic email sender"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            
            # Attach HTML
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, recipient_email, msg.as_string())
            
            print(f"✓ Email sent to {recipient_email}")
            return True
        except Exception as e:
            print(f"✗ Email error: {e}")
            return False
    
    # ============== SMS NOTIFICATIONS ==============
    
    def send_account_suspension_sms(self, phone_number, reason="Policy violation"):
        """Send account suspension SMS (if Twilio available)"""
        if not self.twilio_client:
            return False
        
        message_text = f"Lako Alert: Your account has been suspended. Reason: {reason}. Contact support@lako.com to appeal."
        
        return self.send_sms(phone_number, message_text)
    
    def send_promotional_sms(self, phone_number, promo_text):
        """Send promotional SMS"""
        if not self.twilio_client:
            return False
        
        return self.send_sms(phone_number, promo_text)
    
    def send_otp_sms(self, phone_number, otp_code):
        """Send OTP via SMS"""
        if not self.twilio_client:
            return False
        
        message_text = f"Lako: Your verification code is {otp_code}. Valid for 10 minutes."
        return self.send_sms(phone_number, message_text)
    
    def send_sms(self, phone_number, message_text):
        """Generic SMS sender"""
        try:
            if not self.twilio_client or not self.twilio_number:
                print(f"⚠️ SMS not configured. Would send to {phone_number}: {message_text}")
                return False
            
            message = self.twilio_client.messages.create(
                body=message_text,
                from_=self.twilio_number,
                to=phone_number
            )
            
            print(f"✓ SMS sent to {phone_number}")
            return True
        except Exception as e:
            print(f"✗ SMS error: {e}")
            return False
    
    # ============== READ EMAIL & EXTRACT CODE ==============
    
    def read_email_for_code(self, email, code_type="otp"):
        """
        Read email and extract code (OTP, verification, etc.)
        This simulates reading from the user's email
        
        In production, you'd use Gmail API or IMAP
        """
        try:
            # This is a placeholder - in production:
            # 1. Use Gmail API to read recent emails
            # 2. Parse email body for OTP/code
            # 3. Extract and return code
            
            print(f"⚠️ Email reading not fully implemented. Would scan {email} for {code_type}")
            return None
        except Exception as e:
            print(f"✗ Email read error: {e}")
            return None

# Global notifier instance
notifier = Notifier()

def send_suspension_alert(user_email, full_name, reason="Violating community guidelines", phone_number=None):
    """Send account suspension alert via email and SMS"""
    email_sent = notifier.send_account_suspension_email(user_email, full_name, reason)
    sms_sent = notifier.send_account_suspension_sms(phone_number, reason) if phone_number else False
    
    return {
        'email_sent': email_sent,
        'sms_sent': sms_sent
    }

def send_announcement(user_email, full_name, title, content, phone_number=None):
    """Send announcement via email and SMS"""
    email_sent = notifier.send_important_announcement_email(user_email, full_name, title, content)
    sms_sent = False  # SMS for announcements optional
    
    return {
        'email_sent': email_sent,
        'sms_sent': sms_sent
    }

def send_promo(user_email, full_name, title, content, link="", phone_promo=None):
    """Send promotional content"""
    email_sent = notifier.send_promotional_email(user_email, full_name, title, content, link)
    sms_sent = notifier.send_promotional_sms(phone_number, phone_promo) if phone_promo else False
    
    return {
        'email_sent': email_sent,
        'sms_sent': sms_sent
    }
