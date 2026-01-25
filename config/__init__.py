from .celery import app as celery_app

# Ensure the Celery app is imported when Django starts
__all__ = ('celery_app',)
