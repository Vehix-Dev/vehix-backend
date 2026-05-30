import os
import logging
from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import UserImage

logger = logging.getLogger(__name__)

@receiver(post_delete, sender=UserImage)
def delete_user_image_files(sender, instance, **kwargs):
    """
    Delete original and thumbnail image files from storage when a UserImage record is deleted.
    Works for both individual deletes and bulk QuerySet deletes.
    """
    # Delete original image file
    if instance.original_image:
        try:
            name = instance.original_image.name
            storage = instance.original_image.storage
            if name and storage.exists(name):
                storage.delete(name)
                logger.info(f"Successfully deleted original image file: {name}")
        except Exception as e:
            # Fallback to direct os removal
            try:
                if hasattr(instance.original_image, 'path') and os.path.isfile(instance.original_image.path):
                    os.remove(instance.original_image.path)
                    logger.info(f"Successfully deleted original image file via os.remove: {instance.original_image.path}")
            except Exception as os_err:
                logger.error(f"Failed to delete original image file for UserImage {instance.id}: {e} | OS error: {os_err}")

    # Delete thumbnail file
    if instance.thumbnail:
        try:
            name = instance.thumbnail.name
            storage = instance.thumbnail.storage
            if name and storage.exists(name):
                storage.delete(name)
                logger.info(f"Successfully deleted thumbnail file: {name}")
        except Exception as e:
            # Fallback to direct os removal
            try:
                if hasattr(instance.thumbnail, 'path') and os.path.isfile(instance.thumbnail.path):
                    os.remove(instance.thumbnail.path)
                    logger.info(f"Successfully deleted thumbnail file via os.remove: {instance.thumbnail.path}")
            except Exception as os_err:
                logger.error(f"Failed to delete thumbnail file for UserImage {instance.id}: {e} | OS error: {os_err}")
