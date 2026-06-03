import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Notification

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Notification)
def trigger_notification_fcm(sender, instance, created, **kwargs):
    """
    Automatically sends FCM push notification for any created Notification instance,
    and logs the delivery status in NotificationHistory.
    """
    if created:
        try:
            from users.models import User, NotificationHistory
            from users.fcm import _get_firebase_app, messaging
            
            # Determine target users
            if instance.target_role == 'ALL':
                recipients = User.objects.filter(role__in=['RIDER', 'RODIE'], is_deleted=False)
            elif instance.target_role in ['RIDER', 'RODIE']:
                recipients = User.objects.filter(role=instance.target_role, is_deleted=False)
            elif instance.recipient:
                recipients = [instance.recipient]
            else:
                recipients = []

            app = _get_firebase_app()
            
            for user in recipients:
                token = getattr(user, 'fcm_token', None)
                
                # Create a pending NotificationHistory record
                history = NotificationHistory.objects.create(
                    notification=instance,
                    recipient=user,
                    delivery_status='PENDING'
                )
                
                if not token:
                    history.delivery_status = 'FAILED'
                    history.delivery_error = 'No FCM token registered'
                    history.save()
                    continue

                if not app or not messaging:
                    history.delivery_status = 'FAILED'
                    history.delivery_error = 'Firebase Admin SDK not initialized'
                    history.save()
                    continue
                    
                # Send push notification
                msg = messaging.Message(
                    token=token,
                    notification=messaging.Notification(title=instance.title, body=instance.message),
                    data={
                        'notification_id': str(instance.id),
                        'type': str(instance.notification_type),
                        'url': str(instance.url or '')
                    },
                    android=messaging.AndroidConfig(
                        priority='high',
                        notification=messaging.AndroidNotification(
                            click_action='FLUTTER_NOTIFICATION_CLICK',
                            sound='default'
                        )
                    ),
                    apns=messaging.APNSConfig(
                        payload=messaging.APNSPayload(aps=messaging.Aps(sound='default'))
                    ),
                )
                
                try:
                    response = messaging.send(msg, app=app)
                    history.delivery_status = 'DELIVERED'
                    logger.info(f"Notification {instance.id} delivered to user {user.username} (FCM ID: {response})")
                    history.save()
                except Exception as exc:
                    history.delivery_status = 'FAILED'
                    history.delivery_error = str(exc)
                    history.save()
                    logger.error(f"Failed to deliver notification {instance.id} to user {user.username}: {exc}")
        except Exception as e:
            logger.error(f"Error in Notification FCM trigger signal: {e}")


from django.db.models.signals import pre_save

@receiver(pre_save, sender='users.User')
def clear_duplicate_fcm_tokens(sender, instance, **kwargs):
    """
    Clears the FCM token from any other users if a user registers a non-empty token.
    This prevents shared device notification leaks during testing or multi-account logins.
    """
    if instance.fcm_token:
        sender.objects.filter(fcm_token=instance.fcm_token).exclude(id=instance.id).update(fcm_token="")
