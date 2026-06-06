import os
import sys
import django

# Setup django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vehix.settings")
django.setup()

from django.test import Client
from users.models import User, Wallet
from service_requests.models import ServiceRequest, ServiceType, RodieService
from django.core.cache import cache

def run_test():
    client1 = Client()
    client2 = Client()

    # 1. Setup dummy users
    rider, _ = User.objects.get_or_create(username='test_rider', role='RIDER', phone='+1234567890')
    roadie1, _ = User.objects.get_or_create(username='test_roadie1', role='RODIE', phone='+1234567891', is_approved=True)
    roadie2, _ = User.objects.get_or_create(username='test_roadie2', role='RODIE', phone='+1234567892', is_approved=True)

    Wallet.objects.get_or_create(user=roadie1)
    Wallet.objects.get_or_create(user=roadie2)

    service_type, _ = ServiceType.objects.get_or_create(name="Towing", base_price=50.0)
    RodieService.objects.get_or_create(rodie=roadie1, service=service_type)
    RodieService.objects.get_or_create(rodie=roadie2, service=service_type)

    # Force authenticate
    client1.force_login(roadie1)
    client2.force_login(roadie2)

    # 2. Create a fresh request
    req = ServiceRequest.objects.create(
        rider=rider,
        service_type=service_type,
        status='REQUESTED',
        pickup_location_lat=0.0,
        pickup_location_lng=0.0,
        dropoff_location_lat=1.0,
        dropoff_location_lng=1.0
    )
    print(f"Created ServiceRequest #{req.id}")

    # Set the active offer cache so they bypass the targeted roadie check
    cache.set(f"active_offer:{roadie1.id}", {'id': req.id}, timeout=30)
    cache.set(f"active_offer:{roadie2.id}", {'id': req.id}, timeout=30)

    # 3. Roadie 1 accepts
    print("\n[Roadie 1] Attempting to accept...")
    res1 = client1.post(f"/api/requests/{req.id}/accept/")
    print(f"Roadie 1 Response Code: {res1.status_code}")
    print(f"Roadie 1 Response Body: {res1.json()}")

    # 4. Roadie 2 accepts the SAME request
    print("\n[Roadie 2] Attempting to accept (simulating slow UI/paused timer)...")
    res2 = client2.post(f"/api/requests/{req.id}/accept/")
    print(f"Roadie 2 Response Code: {res2.status_code}")
    print(f"Roadie 2 Response Body: {res2.json()}")

    # Cleanup
    req.delete()

if __name__ == "__main__":
    run_test()
