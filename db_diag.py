import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from users.models import User
from services.models import ServiceType, RodieService
from requests.models import ServiceRequest
from locations.models import RodieLocation

def check_dispatch():
    print("--- User Status ---")
    users = User.objects.all()
    for u in users:
        print(f"User: {u.username}, Role: {u.role}, Active: {u.is_active}, Online: {u.is_online}, Lat: {u.lat}, Lng: {u.lng}")

    print("\n--- Services ---")
    services = ServiceType.objects.all()
    for s in services:
        print(f"Service: {s.name} (ID: {s.id})")

    print("\n--- Roadie Services ---")
    rs = RodieService.objects.all()
    for item in rs:
        print(f"Roadie: {item.rodie.username}, Service: {item.service.name} (ID: {item.service.id})")

    print("\n--- Rodie Locations ---")
    locs = RodieLocation.objects.all()
    for l in locs:
        print(f"Roadie: {l.rodie.username}, Lat: {l.lat}, Lng: {l.lng}")

    print("\n--- Recent Requests ---")
    reqs = ServiceRequest.objects.all().order_by('-created_at')[:5]
    for r in reqs:
        print(f"Req ID: {r.id}, Status: {r.status}, Service: {r.service_type}, Rider Lat/Lng: {r.rider_lat}/{r.rider_lng}")

if __name__ == "__main__":
    check_dispatch()
