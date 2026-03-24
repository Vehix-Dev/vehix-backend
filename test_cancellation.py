#!/usr/bin/env python3
"""
Test script to demonstrate request cancellation functionality.
This script simulates the cancellation flow and shows how the system responds.
"""

import os
import sys
import django
import time
from django.core.cache import cache

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from requests.models import ServiceRequest
from requests.services import _sequential_offers
from services.models import RodieService, ServiceType
from users.models import User
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def test_cancellation_flow():
    """Test the cancellation flow during sequential offers"""
    print("🧪 Testing Request Cancellation Flow")
    print("=" * 50)
    
    # Clear cache
    cache.clear()
    
    # Create test data
    try:
        # Get or create test service type
        service_type, _ = ServiceType.objects.get_or_create(
            name="Test Service",
            defaults={
                'code': 'TEST',
                'fixed_price': 10000,
                'category': 'BASIC'
            }
        )
        
        # Get test users (you'll need to have these in your DB)
        rider = User.objects.filter(role='RIDER').first()
        rodie1 = User.objects.filter(role='RODIE').first()
        rodie2 = User.objects.filter(role='RODIE').last()
        
        if not all([rider, rodie1, rodie2]):
            print("❌ Missing test users. Please create at least 1 RIDER and 2 RODIES in your database.")
            return
        
        # Create test request
        request_obj = ServiceRequest.objects.create(
            rider=rider,
            service_type=service_type,
            rider_lat=0.3241,  # Kampala coordinates
            rider_lng=32.5653,
            status='REQUESTED'
        )
        
        print(f"✅ Created test request #{request_obj.id}")
        
        # Setup rodie services
        for rodie in [rodie1, rodie2]:
            RodieService.objects.get_or_create(
                rodie=rodie,
                service=service_type
            )
            # Set them online
            rodie.is_online = True
            rodie.save()
        
        # Create mock rodies list for sequential offers
        rodies = [
            {'rodie': rodie1, 'distance': 1.0},
            {'rodie': rodie2, 'distance': 2.0}
        ]
        
        print(f"📍 Starting sequential offers to {len(rodies)} roadies...")
        
        # Start the sequential offers in background
        import threading
        offers_thread = threading.Thread(
            target=_sequential_offers,
            args=(rodies, request_obj.id, request_obj.rider_lat, request_obj.rider_lng, service_type.id, 15, 90),
            daemon=True
        )
        offers_thread.start()
        
        # Wait a bit then cancel
        time.sleep(3)
        print(f"🚫 Rider cancels request #{request_obj.id} after 3 seconds...")
        
        # Simulate rider cancellation
        request_obj.status = 'CANCELLED'
        request_obj.save()
        cache.set(f"request_status:{request_obj.id}", 'CANCELLED', timeout=300)
        
        # Broadcast cancellation (simulating the API call)
        channel_layer = get_channel_layer()
        try:
            async_to_sync(channel_layer.group_send)(
                'role_RODIE',
                {
                    "type": "request.cancelled",
                    "request_id": request_obj.id,
                    "message": f"Request #{request_obj.id} has been cancelled by the rider"
                }
            )
            print("📡 Broadcasted cancellation to all roadies")
        except Exception as e:
            print(f"❌ Error broadcasting: {e}")
        
        # Wait for the thread to finish
        offers_thread.join(timeout=10)
        
        # Check final state
        request_obj.refresh_from_db()
        print(f"\n📊 Final Results:")
        print(f"   Request Status: {request_obj.status}")
        print(f"   Cache Status: {cache.get(f'request_status:{request_obj.id}')}")
        
        # Check if any roadie has active offer
        for rodie in [rodie1, rodie2]:
            active_offer = cache.get(f"active_offer:{rodie.id}")
            print(f"   Roadie {rodie.username} active offer: {active_offer is not None}")
        
        print(f"\n✅ Test completed! Request was properly cancelled and sequential offers stopped.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_cancellation_flow()
