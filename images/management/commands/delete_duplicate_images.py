import logging
from django.core.management.base import BaseCommand
from django.db.models import Count
from images.models import UserImage

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Identifies and deletes duplicate user images (profile photos, NINs, licenses, vehicles), keeping only the latest version.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate the deletion process and list duplicate images without modifying the database or filesystem.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING("--- DRY RUN MODE: No database or filesystem changes will be made ---"))

        # Find groupings of (user, image_type) for singular types that have more than 1 image
        singular_types = ['PROFILE', 'NIN_FRONT', 'NIN_BACK', 'LICENSE', 'VEHICLE']
        
        duplicate_groups = (
            UserImage.objects.filter(image_type__in=singular_types)
            .values('user_id', 'image_type')
            .annotate(image_count=Count('id'))
            .filter(image_count__gt=1)
        )
        
        total_groups = duplicate_groups.count()
        
        if total_groups == 0:
            self.stdout.write(self.style.SUCCESS("No duplicate images found in the system."))
            return

        self.stdout.write(f"Found {total_groups} users/groups with duplicate images of unique types.\n")
        
        deleted_count = 0
        total_space_freed = 0

        for group in duplicate_groups:
            user_id = group['user_id']
            image_type = group['image_type']
            count = group['image_count']

            # Get all images for this user of this type, ordered by latest first (created_at desc, then id desc)
            images = UserImage.objects.filter(
                user_id=user_id,
                image_type=image_type
            ).order_by('-created_at', '-id')

            # The first one is the newest (we want to keep this one)
            kept_image = images[0]
            # The rest are duplicates that should be removed
            duplicates_to_delete = images[1:]

            username = kept_image.user.username if kept_image.user else f"UserID {user_id}"
            self.stdout.write(
                self.style.SUCCESS(
                    f"User '{username}' has {count} '{image_type}' images. "
                    f"Keeping latest (ID: {kept_image.id}, Created: {kept_image.created_at})"
                )
            )

            for dup in duplicates_to_delete:
                file_size_kb = round(dup.file_size / 1024, 2) if dup.file_size else 0
                total_space_freed += dup.file_size
                deleted_count += 1

                if dry_run:
                    self.stdout.write(
                        self.style.NOTICE(
                            f"  [DRY RUN] Would delete duplicate '{image_type}' image (ID: {dup.id}, Created: {dup.created_at}, Size: {file_size_kb} KB)"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Deleting duplicate '{image_type}' image (ID: {dup.id}, Created: {dup.created_at}, Size: {file_size_kb} KB)..."
                        )
                    )
                    dup.delete()

        # Summary of the operation
        space_freed_mb = round(total_space_freed / (1024 * 1024), 2)
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n[DRY RUN COMPLETED] Simulated deletion of {deleted_count} duplicate images. "
                    f"Estimated disk space saved: {space_freed_mb} MB"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n[CLEANUP COMPLETED] Successfully deleted {deleted_count} duplicate images. "
                    f"Disk space saved: {space_freed_mb} MB"
                )
            )
