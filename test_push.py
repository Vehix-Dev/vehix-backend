import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from users.models import User
from users.fcm import send_push_notification

# Get the most recently logged in roadie
roadie = User.objects.filter(role='RODIE').exclude(fcm_token='').order_by('-last_login').first()
if roadie:
    print(f"Testing push to Roadie: {roadie.username}")
    print(f"Token: {roadie.fcm_token[:20]}...")
    try:
        send_push_notification(roadie, "Test Push", "This is a direct FCM test", {"type": "TEST"})
        print("Push sent successfully!")
    except Exception as e:
        print(f"Push failed: {e}")
else:
    print("No Roadie with a token found.")
