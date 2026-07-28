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

@shared_task
def sweep_offline_rodies():
    """
    Finds roadies who are marked online in the database but have not sent a heartbeat
    in 10+ minutes, and securely logs them off to fix analytics and 'Ghost Driver' bugs.
    """
    from django.core.cache import cache
    from users.models import RodieAvailabilityLog
    
    online_rodies = User.objects.filter(role='RODIE', is_online=True)
    swept_count = 0
    
    for rodie in online_rodies:
        # Check if heartbeat exists
        if not cache.get(f"rodie_heartbeat:{rodie.id}"):
            # Ghost roadie detected
            logger.info(f"👻 Sweeping ghost roadie {rodie.username} (ID: {rodie.id}) offline.")
            
            # Update DB
            rodie.is_online = False
            rodie.save(update_fields=['is_online'])
            
            # Close availability log
            RodieAvailabilityLog.objects.filter(
                user=rodie, 
                went_offline_at__isnull=True
            ).update(went_offline_at=timezone.now())
            
            swept_count += 1
            
    if swept_count > 0:
        logger.info(f"🧹 Successfully swept {swept_count} disconnected roadies offline.")
    return swept_count
