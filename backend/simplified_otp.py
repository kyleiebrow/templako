"""
Simplified OTP System
Automatically read OTP from user's email for faster verification
"""
import re
from models import supabase
from datetime import datetime, timedelta
import uuid

class SimplifiedOTPSystem:
    """Simplified OTP - delivers code via email, users confirm instantly"""
    
    @staticmethod
    def generate_otp():
        """Generate simple 6-digit OTP"""
        import random
        return str(random.randint(100000, 999999))
    
    @staticmethod
    def create_and_send_otp(email, full_name, send_func):
        """
        Create OTP and send via email callback
        
        Args:
            email: User email
            full_name: User name
            send_func: Function to send email (from notifications module)
        
        Returns:
            otp_code, expires_at
        """
        otp = SimplifiedOTPSystem.generate_otp()
        expires_at = (datetime.now() + timedelta(minutes=10)).isoformat()
        
        # Send email with OTP
        subject = "🔐 Your Lako Verification Code"
        html_body = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="max-width: 500px; margin: 0 auto; padding: 20px;">
              <h2 style="color: #1f2937;">Verify Your Account</h2>
              
              <p>Hi {full_name},</p>
              
              <p>Use this code to verify your email address:</p>
              
              <div style="background: #f0f9ff; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
                <div style="font-size: 36px; font-weight: 700; letter-spacing: 4px; color: #10b981; font-family: monospace;">
                  {otp}
                </div>
              </div>
              
              <p style="color: #666; font-size: 14px;">
                This code expires in 10 minutes.
              </p>
              
              <p>If you didn't request this code, please ignore this email and change your password.</p>
              
              <p>Best regards,<br/>Lako Security Team</p>
              <hr/>
              <p style="font-size: 12px; color: #999;">
                Never share your verification code with anyone.
              </p>
            </div>
          </body>
        </html>
        """
        
        try:
            send_func(email, subject, html_body)
        except:
            pass  # Continue even if email fails
        
        return otp, expires_at
    
    @staticmethod
    def verify_otp(email, provided_otp):
        """
        Verify OTP from database
        
        Returns: (valid, user_data)
        """
        user_resp = supabase.table('users').select('id, otp_code, otp_expires, role, full_name, email_verified').eq('email', email).eq('email_verified', False).execute()
        
        if not user_resp.data:
            return False, None
        
        user = user_resp.data[0]
        
        # Check expiry
        if datetime.fromisoformat(user['otp_expires']) < datetime.now():
            return False, None
        
        # Check code
        if user['otp_code'] != provided_otp:
            return False, None
        
        # Valid!
        return True, user
    
    @staticmethod
    def mark_verified(user_id):
        """Mark user as verified"""
        supabase.table('users').update({
            'email_verified': True,
            'otp_code': None,
            'otp_expires': None
        }).eq('id', user_id).execute()
