import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from users.models import User
from services.models import ServiceType, RodieService

def check_all():
    roadies = User.objects.filter(role__in=['RODIE', 'MECHANIC'])
    services = list(ServiceType.objects.all())
    
    print(f"Checking {len(roadies)} Roadies...")
    for r in roadies:
        # Ensure services are assigned
        for s in services:
            RodieService.objects.get_or_create(rodie=r, service=s)
        
        count = RodieService.objects.filter(rodie=r).count()
        print(f"User: {r.username}, Online: {r.is_online}, Lat/Lng: {r.lat}/{r.lng}, Services: {count}")

if __name__ == "__main__":
    check_all()
