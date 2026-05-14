
import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from service_requests.models import ServiceRequest
from services.models import RodieService, ServiceType
from users.models import User
from django.core.cache import cache
from service_requests.services import find_nearby_rodies

def debug_genesis_matching():
    # 1. Get the latest request
    latest_req = ServiceRequest.objects.order_by('-created_at').first()
    if not latest_req:
        print("❌ No service requests found in database.")
        return

    print(f"📦 Latest Request ID: {latest_req.id}")
    print(f"📍 Location: ({latest_req.rider_lat}, {latest_req.rider_lng})")
    print(f"🛠 Service: {latest_req.service_type.name}")
    print(f"👤 Rider: {latest_req.rider.username}")

    # 2. Check Genesis Status
    try:
        genesis = User.objects.get(username='genesis')
        print(f"\n👤 Roadie 'genesis' Status:")
        print(f"  - Online: {genesis.is_online}")
        print(f"  - Active: {genesis.is_active}")
        print(f"  - Approved: {genesis.is_approved}")
        print(f"  - Deleted: {genesis.is_deleted}")
        
        # Check heartbeat
        heartbeat = cache.get(f"rodie_heartbeat:{genesis.id}")
        print(f"  - Heartbeat: {'✅ OK' if heartbeat else '❌ Missing (Skipped if missing)'}")

        # Check location
        loc = cache.get(f"rodie_loc:{genesis.id}")
        print(f"  - Cache Location: {loc}")
        
        # Check if offering this service
        offers_service = RodieService.objects.filter(rodie=genesis, service=latest_req.service_type).exists()
        print(f"  - Offers this service: {'✅ Yes' if offers_service else '❌ No'}")

        # Check if busy
        busy = ServiceRequest.objects.filter(
            rodie=genesis, 
            status__in=['ACCEPTED', 'EN_ROUTE', 'ARRIVED', 'STARTED']
        ).exists()
        print(f"  - Busy with another request: {'❌ Yes' if busy else '✅ No'}")
        
        # Check if locked
        is_locked = cache.get(f"rodie_locked:{genesis.id}")
        print(f"  - Offer Lock: {'🔒 Locked' if is_locked else '✅ Available'}")

    except User.DoesNotExist:
        print("\n❌ User 'genesis' not found.")

    # 3. Run full matching simulation
    print("\n🔍 Running full matching simulation...")
    results = find_nearby_rodies(latest_req.service_type, latest_req.rider_lat, latest_req.rider_lng)
    
    if not results:
        print("❌ No matching roadies found by the engine.")
    else:
        print(f"✅ Found {len(results)} eligible roadies:")
        for r in results:
            print(f"  - {r['rodie'].username} ({r['distance']:.2f}km away)")

if __name__ == "__main__":
    debug_genesis_matching()
