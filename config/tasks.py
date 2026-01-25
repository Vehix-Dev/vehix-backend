from celery import shared_task
from django.core.cache import cache
from django_redis import get_redis_connection
from django.contrib.auth import get_user_model
from locations.models import RodieLocation
from decimal import Decimal
import json

User = get_user_model()

@shared_task(bind=True)
def flush_locations_task(self):
    """Flush rodie_loc:* keys from Redis into RodieLocation DB rows."""
    conn = get_redis_connection('default')
    if not conn:
        return 0
    keys = conn.scan_iter(match='rodie_loc:*')
    count = 0
    for key in keys:
        try:
            raw = conn.get(key)
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            if isinstance(key, bytes):
                key_str = key.decode()
            else:
                key_str = str(key)
            parts = key_str.split(':')
            if len(parts) != 2:
                continue
            user_id = parts[1]
            try:
                user = User.objects.get(id=int(user_id))
            except Exception:
                continue
            lat = data.get('lat')
            lng = data.get('lng')
            if lat is None or lng is None:
                continue
            try:
                obj, _ = RodieLocation.objects.get_or_create(rodie=user)
                obj.lat = Decimal(str(lat))
                obj.lng = Decimal(str(lng))
                obj.save(update_fields=['lat', 'lng'])
                count += 1
            except Exception:
                continue
        except Exception:
            continue
    return count


@shared_task
def clear_cache_task():
    """Clear the Django cache (Redis) — careful in production: prefer targeted key deletion."""
    try:
        cache.clear()
        return True
    except Exception:
        return False
