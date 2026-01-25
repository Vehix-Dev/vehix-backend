import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.conf import settings

app = Celery('vehix')
app.conf.broker_url = getattr(settings, 'REDIS_URL', 'redis://127.0.0.1:6379/1')
app.conf.result_backend = getattr(settings, 'REDIS_URL', 'redis://127.0.0.1:6379/1')
app.conf.accept_content = ['json']
app.conf.task_serializer = 'json'
app.conf.result_serializer = 'json'

try:
    from . import tasks  # ensure tasks in this package are imported
except Exception:
    pass

app.autodiscover_tasks()

if __name__ == '__main__':
    app.start()
