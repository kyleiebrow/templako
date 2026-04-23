import os
import secrets

# Flask Config
SECRET_KEY = secrets.token_hex(16)

# Database
DB_NAME = os.path.join(os.path.dirname(__file__), 'lako.db')

# Gmail SMTP
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "morillokylebrian@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "khug erxu dhxa ugut")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://emsmhgfzmgnpadpremkq.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_hBlCZ6Ri3WZci17dWPLzug_dUX8Btzi")