import os
import uuid
from django.db import models
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import logging

logger = logging.getLogger(__name__)

class UserImageStorage(FileSystemStorage):
    def get_user_path(self, external_id, filename):
        """Generate path based on external_id"""
        if external_id.startswith('R'):
            user_type = 'riders'
        elif external_id.startswith('BS'):
            user_type = 'roadies'
        else:
            user_type = 'others'
        
        return os.path.join('user_images', user_type, external_id, 'originals', filename)
    
    def get_thumbnail_path(self, external_id, filename):
        """Generate thumbnail path based on external_id"""
        if external_id.startswith('R'):
            user_type = 'riders'
        elif external_id.startswith('BS'):
            user_type = 'roadies'
        else:
            user_type = 'others'
        
        return os.path.join('user_images', user_type, external_id, 'thumbnails', filename)


class UserImage(models.Model):
    IMAGE_TYPE_CHOICES = (
        ('PROFILE', 'Profile Picture'),
        ('NIN_FRONT', 'NIN Front'),
        ('NIN_BACK', 'NIN Back'),
        ('LICENSE', 'License'),
        ('VEHICLE', 'Vehicle'),
        ('OTHER', 'Other'),
    )
    
    STATUS_CHOICES = (
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='images'
    )
    
    external_id = models.CharField(
        max_length=10,
        help_text="User's external ID (R001, BS001, etc.)"
    )
    
    image_type = models.CharField(
        max_length=20,
        choices=IMAGE_TYPE_CHOICES,
        default='OTHER'
    )
    
    original_image = models.ImageField(
        upload_to='temp_uploads/',
        storage=UserImageStorage()
    )
    
    thumbnail = models.ImageField(
        upload_to='temp_thumbnails/',
        storage=UserImageStorage(),
        null=True,
        blank=True
    )
    
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='APPROVED'
    )
    
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    file_size = models.PositiveIntegerField(default=0)  
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    mime_type = models.CharField(max_length=50, blank=True)
    original_filename = models.CharField(max_length=255)
    storage_path = models.CharField(max_length=500, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['external_id', 'image_type']),
            models.Index(fields=['external_id', 'status']),
        ]
    
    def save(self, *args, **kwargs):
        if self.user and not self.external_id:
            self.external_id = self.user.external_id or ''
        
        is_new = self.pk is None
        
        if is_new and self.original_image:
            self.original_filename = os.path.basename(self.original_image.name)
            self.file_size = self.original_image.size
            ext = os.path.splitext(self.original_filename)[1]
            unique_filename = f"{uuid.uuid4().hex}{ext}"
        
            storage = UserImageStorage()
            original_path = storage.get_user_path(self.external_id, unique_filename)
            thumbnail_path = storage.get_thumbnail_path(self.external_id, f"thumb_{unique_filename}")
            
            try:
                img = Image.open(self.original_image)
                self.width, self.height = img.size
                self.mime_type = Image.MIME.get(img.format, '')
                original_content = BytesIO()
                img.save(original_content, format=img.format or 'JPEG')
                self.original_image.save(
                    original_path,
                    ContentFile(original_content.getvalue()),
                    save=False
                )
        
                thumbnail_size = (300, 300)
                img.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
                
                thumbnail_content = BytesIO()
                img.save(thumbnail_content, format=img.format or 'JPEG')
                self.thumbnail.save(
                    thumbnail_path,
                    ContentFile(thumbnail_content.getvalue()),
                    save=False
                )
                
                self.storage_path = original_path
                
            except Exception as e:
                logger.error(f"Error processing image: {e}")
                pass
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Delete both original and thumbnail files"""
        if self.original_image:
            if os.path.isfile(self.original_image.path):
                os.remove(self.original_image.path)
        if self.thumbnail:
            if os.path.isfile(self.thumbnail.path):
                os.remove(self.thumbnail.path)
        super().delete(*args, **kwargs)
    
    
    def get_original_url(self):
        """Get URL for original image"""
        if self.original_image:
            return self.original_image.url
        return None
    
    def get_thumbnail_url(self):
        """Get URL for thumbnail"""
        if self.thumbnail:
            return self.thumbnail.url
        return None
    
    @property
    def original_url(self):
        """Property for admin display"""
        return self.get_original_url()
    
    @property
    def thumbnail_url(self):
        """Property for admin display"""
        return self.get_thumbnail_url()
    
    def admin_thumbnail_preview(self):
        """HTML for thumbnail preview in admin"""
        if self.thumbnail:
            return f'<img src="{self.thumbnail.url}" width="50" height="50" style="object-fit: cover;" />'
        return "No thumbnail"
    admin_thumbnail_preview.allow_tags = True
    admin_thumbnail_preview.short_description = 'Thumbnail Preview'
    
    def admin_original_preview(self):
        """HTML for original image preview in admin"""
        if self.original_image:
            return f'<img src="{self.original_image.url}" width="200" style="max-height: 200px; object-fit: contain;" />'
        return "No original image"
    admin_original_preview.allow_tags = True
    admin_original_preview.short_description = 'Original Image Preview'
    
    @property
    def user_info(self):
        """Formatted user information for admin"""
        if self.user:
            return f"{self.user.username} ({self.user.phone})"
        return "No user"
    
    def __str__(self):
        return f"{self.external_id} - {self.get_image_type_display()} - {self.status}"