import os
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
except ImportError:
    firebase_admin = None
    credentials = None
    messaging = None


_firebase_app = None


def _get_firebase_app():
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    if not firebase_admin:
        print('DEBUG: firebase_admin package is not installed.')
        return None

    service_account = getattr(settings, 'FCM_SERVICE_ACCOUNT_FILE', '')
    if not service_account:
        print('DEBUG: No FCM service account file configured.')
        return None

    if not os.path.exists(service_account):
        print(f'DEBUG: FCM service account file not found at {service_account}')
        return None

    try:
        cred = credentials.Certificate(service_account)
        _firebase_app = firebase_admin.initialize_app(cred)
        return _firebase_app
    except Exception as exc:
        print(f'DEBUG: Failed to initialize Firebase Admin SDK: {exc}')
        return None


def _send_with_admin(token, title, message, data=None):
    app = _get_firebase_app()
    if not app or not messaging:
        return False

    if not token:
        return False

    msg = messaging.Message(
        token=token,
        notification=messaging.Notification(title=title, body=message),
        data={k: str(v) for k, v in (data or {}).items()},
        android=messaging.AndroidConfig(priority='high', notification=messaging.AndroidNotification(click_action='FLUTTER_NOTIFICATION_CLICK', sound='default')),
        apns=messaging.APNSConfig(payload=messaging.APNSPayload(aps=messaging.Aps(alert=messaging.ApsAlert(title=title, body=message), sound='default'))),
    )
    try:
        response = messaging.send(msg, app=app)
        print(f'DEBUG: Firebase Admin send response: {response}')
        return True
    except Exception as exc:
        print(f'DEBUG: Firebase Admin send error: {exc}')
        return False


def _send_multicast_with_admin(tokens, title, message, data=None):
    app = _get_firebase_app()
    if not app or not messaging:
        return False

    if not tokens:
        return False

    chunks = [tokens[i:i + 500] for i in range(0, len(tokens), 500)]
    results = []
    for chunk in chunks:
        multicast = messaging.MulticastMessage(
            tokens=chunk,
            notification=messaging.Notification(title=title, body=message),
            data={k: str(v) for k, v in (data or {}).items()},
            android=messaging.AndroidConfig(priority='high', notification=messaging.AndroidNotification(click_action='FLUTTER_NOTIFICATION_CLICK', sound='default')),
            apns=messaging.APNSConfig(payload=messaging.APNSPayload(aps=messaging.Aps(alert=messaging.ApsAlert(title=title, body=message), sound='default'))),
        )
        try:
            response = messaging.send_multicast(multicast, app=app)
            results.append(response)
            print(f'DEBUG: Firebase Admin multicast success={response.success_count} failure={response.failure_count}')
        except Exception as exc:
            print(f'DEBUG: Firebase Admin multicast error: {exc}')
            return False

    return any(response.success_count > 0 for response in results)


def send_push_notification(user, title, message, data=None):
    """Send a push notification to a single user's registered FCM token."""
    if not user or not getattr(user, 'fcm_token', None):
        print(f"DEBUG: No FCM token for user {getattr(user, 'username', 'unknown')}. Skipping push.")
        return False

    if _get_firebase_app():
        return _send_with_admin(user.fcm_token, title, message, data)

    print('DEBUG: Falling back to legacy FCM HTTP V1 path is not implemented when service account is unavailable.')
    return False


def send_push_notification_by_token(token, title, message, data=None):
    """Send a push notification directly to a raw FCM registration token."""
    if not token:
        return False
    if _get_firebase_app():
        return _send_with_admin(token, title, message, data)
    return False


def broadcast_role_push(role, title, message, data=None):
    """Send a push notification to all users belonging to a role."""
    tokens = list(User.objects.filter(role=role, fcm_token__isnull=False).exclude(fcm_token='').values_list('fcm_token', flat=True))
    if not tokens:
        return False

    if _get_firebase_app():
        return _send_multicast_with_admin(tokens, title, message, data)

    return False
