import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from services.models import RodieService, ServiceType
from users.models import User

def fix_services():
    services = list(ServiceType.objects.all())
    roadies = User.objects.filter(role__in=['RODIE', 'MECHANIC'])
    count = 0
    for r in roadies:
        for s in services:
            obj, created = RodieService.objects.get_or_create(rodie=r, service=s)
            if created:
                count += 1
    print(f"Successfully assigned {count} missing service associations to {len(roadies)} users.")

if __name__ == "__main__":
    fix_services()
