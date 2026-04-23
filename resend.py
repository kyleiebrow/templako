import requests

# Your Resend API key
RESEND_API_KEY = "re_KmE3GTUi_LE7zWThzF4P53QSNteJ6Hk5E"

# API endpoint
url = "https://api.resend.com/emails"

# Headers
headers = {
    "Authorization": f"Bearer {RESEND_API_KEY}",
    "Content-Type": "application/json"
}

# Email data
data = {
    "from": "Lako <onboarding@resend.dev>",
    "to": ["morillokylebrian@gmail.com"],
    "subject": "Test Email from Lako",
    "html": "<h1 style='color: #2d8c3c;'>🎉 Test Successful!</h1><p>Your Resend API key is working!</p>"
}

print("Sending test email...")
print(f"To: morillokylebrian@gmail.com")
print(f"From: Lako <onboarding@resend.dev>")

try:
    response = requests.post(url, headers=headers, json=data)
    
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ EMAIL SENT SUCCESSFULLY!")
        print(f"Email ID: {result.get('id')}")
        print(f"\nCheck your inbox at: morillokylebrian@gmail.com")
    else:
        print(f"❌ Failed to send email")
        print(f"Error: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")