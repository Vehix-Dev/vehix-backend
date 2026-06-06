import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vehix.settings")
django.setup()

from django.test import TestCase
from users.models import User
from services.models import ServiceType, RodieService
from service_requests.models import ServiceRequest
from locations.models import RodieLocation
from django.core.cache import cache

class MatchmakingTestCase(TestCase):
    def setUp(self):
        # Create test users
        self.rider = User.objects.create_user(username='rider1', phone='1234567890', password='password', role='RIDER')
        self.roadie1 = User.objects.create_user(username='roadie1', phone='0987654321', password='password', role='RODIE', is_online=True, is_approved=True, services_selected=True)
        self.roadie2 = User.objects.create_user(username='roadie2', phone='1112223333', password='password', role='RODIE', is_online=True, is_approved=True, services_selected=True)
        
        # Create Service
        self.service = ServiceType.objects.create(name='Towing', base_price=100)
        RodieService.objects.create(rodie=self.roadie1, service=self.service)
        RodieService.objects.create(rodie=self.roadie2, service=self.service)
        
        # Set locations
        RodieLocation.objects.create(rodie=self.roadie1, lat=0.001, lng=0.001)
        RodieLocation.objects.create(rodie=self.roadie2, lat=0.002, lng=0.002)
        
        cache.clear()
        
    def test_find_nearby_rodies(self):
        from service_requests.services import find_nearby_rodies
        
        # Add heartbeat
        cache.set(f"rodie_heartbeat:{self.roadie1.id}", True, timeout=600)
        cache.set(f"rodie_heartbeat:{self.roadie2.id}", True, timeout=600)
        
        cache.set(f"rodie_loc:{self.roadie1.id}", {'lat': 0.001, 'lng': 0.001}, timeout=600)
        cache.set(f"rodie_loc:{self.roadie2.id}", {'lat': 0.002, 'lng': 0.002}, timeout=600)
        
        rodies = find_nearby_rodies(self.service, 0.0, 0.0)
        self.assertEqual(len(rodies), 2)
        self.assertEqual(rodies[0]['rodie'].id, self.roadie1.id)
        
        print("✅ test_find_nearby_rodies passed")

    def test_double_accept_protection(self):
        # Create request
        req = ServiceRequest.objects.create(rider=self.rider, service_type=self.service, lat=0.0, lng=0.0, status='REQUESTED')
        
        # Simulate active offer for roadie1
        cache.set(f"active_offer:{self.roadie1.id}", {'id': req.id}, timeout=60)
        
        # Accept using API logic
        from django.test.client import RequestFactory
        from service_requests.views import AcceptRequestView
        
        factory = RequestFactory()
        
        # Roadie 1 accepts
        request1 = factory.post(f'/api/requests/{req.id}/accept/')
        request1.user = self.roadie1
        view = AcceptRequestView.as_view()
        response1 = view(request1, pk=req.id)
        self.assertEqual(response1.status_code, 200)
        
        # Roadie 2 tries to accept the SAME request (even if they somehow bypassed the cache)
        cache.set(f"active_offer:{self.roadie2.id}", {'id': req.id}, timeout=60)
        request2 = factory.post(f'/api/requests/{req.id}/accept/')
        request2.user = self.roadie2
        response2 = view(request2, pk=req.id)
        
        # Should be 400 because status is no longer REQUESTED
        self.assertEqual(response2.status_code, 400)
        print("✅ test_double_accept_protection passed")

    def test_cancellation_during_offer(self):
        req = ServiceRequest.objects.create(rider=self.rider, service_type=self.service, lat=0.0, lng=0.0, status='REQUESTED')
        
        # Roadie has an active offer
        cache.set(f"active_offer:{self.roadie1.id}", {'id': req.id}, timeout=60)
        cache.set(f"rodie_locked:{self.roadie1.id}", req.id, timeout=60)
        
        from service_requests.models import CancellationReason
        reason = CancellationReason.objects.create(reason="Test", user_type='RIDER')
        
        from django.test.client import RequestFactory
        from service_requests.views import CancelRequestView
        factory = RequestFactory()
        request = factory.post(f'/api/requests/{req.id}/cancel/', {'reason_id': reason.id}, format='json')
        request.user = self.rider
        view = CancelRequestView.as_view()
        response = view(request, pk=req.id)
        
        self.assertEqual(response.status_code, 200)
        
        # Assert locks are cleared
        self.assertIsNone(cache.get(f"rodie_locked:{self.roadie1.id}"))
        print("✅ test_cancellation_during_offer passed")
        
    def test_rider_cancel_post_arrival(self):
        req = ServiceRequest.objects.create(rider=self.rider, rodie=self.roadie1, service_type=self.service, lat=0.0, lng=0.0, status='ARRIVED')
        
        from service_requests.models import CancellationReason
        reason = CancellationReason.objects.create(reason="Test", user_type='RIDER')
        
        from django.test.client import RequestFactory
        from service_requests.views import CancelRequestView
        factory = RequestFactory()
        request = factory.post(f'/api/requests/{req.id}/cancel/', {'reason_id': reason.id}, format='json')
        request.user = self.rider
        view = CancelRequestView.as_view()
        response = view(request, pk=req.id)
        
        self.assertEqual(response.status_code, 200) # Should succeed because business logic allows it
        print("✅ test_rider_cancel_post_arrival passed")

if __name__ == '__main__':
    from django.core.management import call_command
    # Suppress logging
    import logging
    logging.disable(logging.CRITICAL)
    
    t = MatchmakingTestCase()
    t.setUp()
    t.test_find_nearby_rodies()
    t.test_double_accept_protection()
    t.test_cancellation_during_offer()
    t.test_rider_cancel_post_arrival()
    print("All tests passed successfully.")
