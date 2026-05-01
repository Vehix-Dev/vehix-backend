from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from users.models import User
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Permanently delete accounts that have been in PENDING deletion status for more than 30 days'

    def handle(self, *args, **options):
        # Calculate the cutoff date (30 days ago)
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # Find users who requested deletion more than 30 days ago
        pending_users = User.objects.filter(
            deletion_status='PENDING',
            deletion_requested_at__lte=cutoff_date
        )
        
        count = pending_users.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No accounts pending permanent deletion.'))
            return

        self.stdout.write(f'Found {count} accounts pending permanent deletion. Processing...')
        
        for user in pending_users:
            username = user.username
            role = user.role
            try:
                # We do a real delete here as per the 30-day policy
                # Django's CASCADE will handle related data (Wallet, etc.)
                user.delete()
                self.stdout.write(self.style.SUCCESS(f'Successfully deleted {role} account: {username}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to delete user {username}: {str(e)}'))
                logger.exception(f"Error deleting user {username}")

        self.stdout.write(self.style.SUCCESS(f'Finished processing {count} account deletions.'))
