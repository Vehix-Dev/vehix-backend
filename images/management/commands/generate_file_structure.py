import os
import json
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate the file structure for user images based on existing users'
    
    def handle(self, *args, **kwargs):
        base_path = os.path.join(settings.MEDIA_ROOT, 'user_images')
        
        # Create base structure
        directories = [
            os.path.join(base_path, 'riders'),
            os.path.join(base_path, 'roadies'),
            os.path.join(base_path, 'others'),
        ]
        
        # Get all users with external_id
        users = User.objects.filter(external_id__isnull=False)
        
        for user in users:
            if user.external_id.startswith('R'):
                user_type = 'riders'
            elif user.external_id.startswith('BS'):
                user_type = 'roadies'
            else:
                user_type = 'others'
            
            user_dir = os.path.join(base_path, user_type, user.external_id)
            originals_dir = os.path.join(user_dir, 'originals')
            thumbnails_dir = os.path.join(user_dir, 'thumbnails')
            
            directories.extend([user_dir, originals_dir, thumbnails_dir])
        
        # Create all directories
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            self.stdout.write(f'Created directory: {directory}')
        
        # Create README files
        readme_path = os.path.join(base_path, 'README.txt')
        with open(readme_path, 'w') as f:
            f.write("""User Images File Structure
============================

This directory contains user-uploaded images organized by:
1. User type (riders, roadies, others)
2. External ID (R001, BS001, etc.)
3. Image type (originals, thumbnails)

Structure:
- user_images/
  - riders/
    - R001/
      - originals/
      - thumbnails/
    - R002/
      - originals/
      - thumbnails/
  - roadies/
    - BS001/
      - originals/
      - thumbnails/
  - others/
    - [other_ids]/
      - originals/
      - thumbnails/

Thumbnails are automatically generated at 300x300 pixels.
""")
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created file structure for {users.count()} users'
            )
        )