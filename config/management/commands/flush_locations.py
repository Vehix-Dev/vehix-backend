from django.core.management.base import BaseCommand
from django_redis import get_redis_connection
from django.contrib.auth import get_user_model
from locations.models import RodieLocation
from decimal import Decimal
import json

User = get_user_model()


class Command(BaseCommand):
    help = "Flush ephemeral rodie locations from Redis cache into the database."

    def handle(self, *args, **options):
        conn = get_redis_connection('default')
        if conn is None:
            self.stdout.write(self.style.ERROR('No redis connection available.'))
            return

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

        self.stdout.write(self.style.SUCCESS(f'Flushed {count} rodie locations to DB'))
