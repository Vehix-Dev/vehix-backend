import requests
import json
from django.conf import settings
from .models import User

def send_push_notification(user, title, message, data=None):
    """
    Sends a push notification to a user's fcm_token using Firebase Legacy server key 
    or FCM V1 (implementation depends on credentials).
    """
    if not user.fcm_token:
        print(f"DEBUG: No FCM token for user {user.username}. Skipping push.")
        return False

    # Get server key from settings (YOU MUST SET THIS IN settings.py)
    server_key = getattr(settings, 'FCM_SERVER_KEY', None)
    if not server_key:
        print("DEBUG: FCM_SERVER_KEY not set in settings.py")
        return False

    fcm_url = "https://fcm.googleapis.com/fcm/send"
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'key={server_key}'
    }

    payload = {
        'to': user.fcm_token,
        'notification': {
            'title': title,
            'body': message,
            'sound': 'default',
            'click_action': 'FLUTTER_NOTIFICATION_CLICK'
        },
        'data': data or {},
        'priority': 'high'
    }

    try:
        response = requests.post(fcm_url, headers=headers, data=json.dumps(payload), timeout=10)
        print(f"DEBUG: FCM response for {user.username}: {response.status_code} {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"DEBUG Error sending FCM: {str(e)}")
        return False

def broadcast_role_push(role, title, message, data=None):
    """
    Sends a push notification to all users of a specific role (RIDER/RODIE)
    """
    tokens = User.objects.filter(role=role, fcm_token__isnull=False).exclude(fcm_token='').values_list('fcm_token', flat=True)
    
    if not tokens:
        return False
        
    # FCM allows multicast up to 1000 tokens
    server_key = getattr(settings, 'FCM_SERVER_KEY', None)
    if not server_key:
        return False

    fcm_url = "https://fcm.googleapis.com/fcm/send"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'key={server_key}'
    }

    payload = {
        'registration_ids': list(tokens),
        'notification': {
            'title': title,
            'body': message,
            'sound': 'default',
        },
        'data': data or {},
        'priority': 'high'
    }

    try:
        response = requests.post(fcm_url, headers=headers, data=json.dumps(payload), timeout=10)
        return response.status_code == 200
    except Exception:
        return False
