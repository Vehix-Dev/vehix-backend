import os
import django
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from users.models import User
from users.serializers import UserSerializer
from rest_framework.test import APIRequestFactory

def check():
    username = 'kebo222'
    print(f"--- Checking user: {username} ---")
    try:
        u = User.objects.get(username=username)
        factory = APIRequestFactory()
        request = factory.get('/api/me/')
        
        # We need to simulate the request context
        serializer = UserSerializer(u, context={'request': request})
        data = serializer.data
        print("✅ Success! Profile data:")
        print(data)
    except Exception:
        print("❌ CRASH DETECTED:")
        traceback.print_exc()

if __name__ == "__main__":
    check()
