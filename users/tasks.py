from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

@shared_task
def permanent_deletion_of_old_requests():
    """
    Permanently delete users who requested deletion more than 30 days ago.
    """
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    users_to_delete = User.objects.filter(
        deletion_status='PENDING',
        deletion_requested_at__lte=thirty_days_ago,
        is_deleted=True
    )
    
    count = users_to_delete.count()
    if count > 0:
        logger.info(f"🗑️ Found {count} users eligible for permanent deletion.")
        for user in users_to_delete:
            logger.info(f"🚮 Permanently deleting User ID: {user.id}, Username: {user.username}")
            user.delete()
        logger.info(f"✅ Successfully deleted {count} accounts.")
    else:
        logger.info("ℹ️ No accounts eligible for permanent deletion today.")
    
    return count
