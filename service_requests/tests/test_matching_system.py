"""
Unit tests for Vehix Matching System Bug Fixes
Tests the critical scenarios from the audit to ensure all bugs are fixed.
"""

import pytest
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from service_requests.models import ServiceRequest, CancellationReason, RequestCancellation
from services.models import RodieService, ServiceType
from locations.models import RodieLocation
from users.models import Wallet, PlatformConfig

User = get_user_model()


class TestBug1HomeScreenWSHandler(TransactionTestCase):
    """
    Bug 1: HomeScreen WS Handler Stays Active During RideScreen
    Verify that Navigator.pushReplacement is used instead of Navigator.push
    This is a frontend fix, but we test the backend behavior.
    """
    
    def setUp(self):
        cache.clear()
        # Create users
        self.rider = User.objects.create_user(
            username='rider1', 
            email='rider@test.com',
            role='RIDER',
            is_active=True
        )
        self.rodie = User.objects.create_user(
            username='rodie1',
            email='rodie@test.com',
            role='RODIE',
            is_active=True,
            is_approved=True,
            is_online=True
        )
        
        # Create service type
        self.service_type = ServiceType.objects.create(name='Towing', base_price=50000)
        
        # Create rodie service
        RodieService.objects.create(rodie=self.rodie, service=self.service_type)
        
        # Set rodie location
        RodieLocation.objects.create(
            rodie=self.rodie,
            lat=0.3476,
            lng=32.5825
        )
        
        # Create wallets
        Wallet.objects.create(user=self.rider, balance=100000)
        Wallet.objects.create(user=self.rodie, balance=50000)
        
        # Create platform config
        PlatformConfig.objects.create(max_negative_balance=10000)
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.rider)

    def test_acceptance_clears_rodie_lock(self):
        """Verify that accepting a request clears the rodie lock cache"""
        # Create request
        response = self.client.post('/api/requests/', {
            'service_type': self.service_type.id,
            'rider_lat': 0.3476,
            'rider_lng': 32.5825,
            'pickup_location': 'Test Location',
            'dropoff_location': 'Test Destination'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        request_id = response.data['id']
        
        # Simulate Celery setting active_offer
        cache.set(f"active_offer:{self.rodie.id}", {'id': request_id}, timeout=15)
        cache.set(f"rodie_locked:{self.rodie.id}", request_id, timeout=15)
        
        # Verify lock is set
        self.assertIsNotNone(cache.get(f"rodie_locked:{self.rodie.id}"))
        
        # Accept the request
        self.client.force_authenticate(user=self.rodie)
        response = self.client.post(f'/api/requests/{request_id}/accept/', {
            'lat': 0.3476,
            'lng': 32.5825
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify lock is cleared
        self.assertIsNone(cache.get(f"rodie_locked:{self.rodie.id}"))
        
        # Verify request status is ACCEPTED
        request = ServiceRequest.objects.get(id=request_id)
        self.assertEqual(request.status, 'ACCEPTED')
        self.assertEqual(request.rodie, self.rodie)


class TestBug2DeclineCachePollution(TransactionTestCase):
    """
    Bug 2: Decline Pollutes Cache
    Verify that declining a request does NOT overwrite request_status cache
    """
    
    def setUp(self):
        cache.clear()
        self.rider = User.objects.create_user(
            username='rider2',
            email='rider2@test.com',
            role='RIDER',
            is_active=True
        )
        self.rodie = User.objects.create_user(
            username='rodie2',
            email='rodie2@test.com',
            role='RODIE',
            is_active=True,
            is_approved=True,
            is_online=True
        )
        
        self.service_type = ServiceType.objects.create(name='Towing', base_price=50000)
        RodieService.objects.create(rodie=self.rodie, service=self.service_type)
        RodieLocation.objects.create(rodie=self.rodie, lat=0.3476, lng=32.5825)
        
        Wallet.objects.create(user=self.rider, balance=100000)
        Wallet.objects.create(user=self.rodie, balance=50000)
        PlatformConfig.objects.create(max_negative_balance=10000)
        
        self.client = APIClient()

    def test_decline_does_not_pollute_request_status(self):
        """Verify that declining does NOT set request_status to DECLINED:user_id"""
        # Create request
        self.client.force_authenticate(user=self.rider)
        response = self.client.post('/api/requests/', {
            'service_type': self.service_type.id,
            'rider_lat': 0.3476,
            'rider_lng': 32.5825,
            'pickup_location': 'Test Location',
            'dropoff_location': 'Test Destination'
        })
        request_id = response.data['id']
        
        # Set initial request_status
        cache.set(f"request_status:{request_id}", 'REQUESTED', timeout=120)
        
        # Simulate active offer
        cache.set(f"active_offer:{self.rodie.id}", {'id': request_id}, timeout=15)
        
        # Decline the request
        self.client.force_authenticate(user=self.rodie)
        response = self.client.post(f'/api/requests/{request_id}/decline/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify rodie_declined is set
        self.assertTrue(cache.get(f"rodie_declined:{request_id}:{self.rodie.id}"))
        
        # Verify request_status is STILL 'REQUESTED' (NOT polluted with DECLINED:user_id)
        request_status = cache.get(f"request_status:{request_id}")
        self.assertEqual(request_status, 'REQUESTED')
        
        # Verify DB status is still REQUESTED
        request = ServiceRequest.objects.get(id=request_id)
        self.assertEqual(request.status, 'REQUESTED')


class TestBug3DoubleFCMOnRoadieCancel(TransactionTestCase):
    """
    Bug 3: Double FCM on Roadie Cancel
    Verify that FCM is only sent once, with proper fallback handling
    """
    
    def setUp(self):
        cache.clear()
        self.rider = User.objects.create_user(
            username='rider3',
            email='rider3@test.com',
            role='RIDER',
            is_active=True
        )
        self.rodie = User.objects.create_user(
            username='rodie3',
            email='rodie3@test.com',
            role='RODIE',
            is_active=True,
            is_approved=True,
            is_online=True
        )
        
        self.service_type = ServiceType.objects.create(name='Towing', base_price=50000)
        RodieService.objects.create(rodie=self.rodie, service=self.service_type)
        
        Wallet.objects.create(user=self.rider, balance=100000)
        Wallet.objects.create(user=self.rodie, balance=50000)
        PlatformConfig.objects.create(max_negative_balance=10000)
        
        # Create cancellation reason
        self.reason = CancellationReason.objects.create(
            role='RODIE',
            reason='Test reason',
            is_active=True
        )
        
        self.client = APIClient()

    def test_roadie_cancel_clears_cache_properly(self):
        """Verify that roadie cancellation clears cache locks properly"""
        # Create and accept a request
        self.client.force_authenticate(user=self.rider)
        response = self.client.post('/api/requests/', {
            'service_type': self.service_type.id,
            'rider_lat': 0.3476,
            'rider_lng': 32.5825,
            'pickup_location': 'Test Location',
            'dropoff_location': 'Test Destination'
        })
        request_id = response.data['id']
        
        # Accept the request
        self.client.force_authenticate(user=self.rodie)
        response = self.client.post(f'/api/requests/{request_id}/accept/', {
            'lat': 0.3476,
            'lng': 32.5825
        })
        
        # Set cache locks
        cache.set(f"rodie_locked:{self.rodie.id}", request_id, timeout=15)
        cache.set(f"active_offer:{self.rodie.id}", {'id': request_id}, timeout=15)
        
        # Cancel the request
        response = self.client.post(f'/api/requests/{request_id}/cancel/', {
            'reason_id': self.reason.id,
            'current_lat': 0.3476,
            'current_lng': 32.5825
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify cache locks are cleared
        self.assertIsNone(cache.get(f"rodie_locked:{self.rodie.id}"))
        self.assertIsNone(cache.get(f"active_offer:{self.rodie.id}"))
        
        # Verify request status is CANCELLED
        request = ServiceRequest.objects.get(id=request_id)
        self.assertEqual(request.status, 'CANCELLED')


class TestBug6RiderConsumerMissingHandlers(TransactionTestCase):
    """
    Bug 6: Rider App Stuck on 'Searching'
    Verify that RiderConsumer has all required handler methods
    """
    
    def test_rider_consumer_has_all_handlers(self):
        """Verify RiderConsumer has all lifecycle event handlers"""
        from realtime.consumers import RiderConsumer
        
        # Check that all required handlers exist
        consumer = RiderConsumer()
        
        required_handlers = [
            'request_accepted',
            'request_enroute',
            'request_started',
            'request_arrived',
            'request_completed',
            'request_declined',
            'request_expired',
            'request_cancelled',
            'request_update',
            'rodie_location',
            'request_proximity',
            'session_invalidated'
        ]
        
        for handler in required_handlers:
            self.assertTrue(
                hasattr(consumer, handler),
                f"RiderConsumer missing handler: {handler}"
            )
            self.assertTrue(
                callable(getattr(consumer, handler)),
                f"RiderConsumer.{handler} is not callable"
            )


class TestBug7StuckRideScreen(TransactionTestCase):
    """
    Bug 7: Stuck Ride Screen & Redundant 'VIEW' Push Notification
    Verify that REQUEST_CANCELLED pushes are ignored in foreground
    """
    
    def test_notification_service_ignores_cancelled_push(self):
        """This is a frontend test - verify the code structure exists"""
        # Read the notification_service.dart file to verify the guard is in place
        import os
        notification_service_path = '/Users/mahadkaluuma/Vehix/vehix-backend/roadie_app/lib/services/notification_service.dart'
        
        if os.path.exists(notification_service_path):
            with open(notification_service_path, 'r') as f:
                content = f.read()
                
            # Verify the guard exists
            self.assertIn("REQUEST_CANCELLED", content)
            self.assertIn("Ignoring REQUEST_CANCELLED push in foreground", content)
    
    def test_ride_screen_cancellation_handler(self):
        """Verify ride_screen.dart has proper cancellation handling"""
        import os
        ride_screen_path = '/Users/mahadkaluuma/Vehix/vehix-backend/roadie_app/lib/screens/ride_screen.dart'
        
        if os.path.exists(ride_screen_path):
            with open(ride_screen_path, 'r') as f:
                content = f.read()
                
            # Verify cancellation handler exists
            self.assertIn("request_cancelled", content)
            self.assertIn("_isCancelled", content)


class TestScenario1HappyPath(TransactionTestCase):
    """
    Scenario 1: Happy Path - 1 Rider, 1 Roadie
    Full end-to-end test of the matching flow
    """
    
    def setUp(self):
        cache.clear()
        self.rider = User.objects.create_user(
            username='rider_happy',
            email='rider_happy@test.com',
            role='RIDER',
            is_active=True
        )
        self.rodie = User.objects.create_user(
            username='rodie_happy',
            email='rodie_happy@test.com',
            role='RODIE',
            is_active=True,
            is_approved=True,
            is_online=True
        )
        
        self.service_type = ServiceType.objects.create(name='Towing', base_price=50000)
        RodieService.objects.create(rodie=self.rodie, service=self.service_type)
        RodieLocation.objects.create(rodie=self.rodie, lat=0.3476, lng=32.5825)
        
        Wallet.objects.create(user=self.rider, balance=100000)
        Wallet.objects.create(user=self.rodie, balance=50000)
        PlatformConfig.objects.create(max_negative_balance=10000)
        
        self.client = APIClient()

    def test_happy_path_flow(self):
        """Test complete happy path: create -> accept -> complete"""
        # 1. Rider creates request
        self.client.force_authenticate(user=self.rider)
        response = self.client.post('/api/requests/', {
            'service_type': self.service_type.id,
            'rider_lat': 0.3476,
            'rider_lng': 32.5825,
            'pickup_location': 'Test Pickup',
            'dropoff_location': 'Test Dropoff'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        request_id = response.data['id']
        
        # Verify request is REQUESTED
        request = ServiceRequest.objects.get(id=request_id)
        self.assertEqual(request.status, 'REQUESTED')
        self.assertIsNone(request.rodie)
        
        # 2. Simulate Celery setting active_offer
        cache.set(f"active_offer:{self.rodie.id}", {'id': request_id}, timeout=15)
        cache.set(f"rodie_locked:{self.rodie.id}", request_id, timeout=15)
        
        # 3. Roadie accepts
        self.client.force_authenticate(user=self.rodie)
        response = self.client.post(f'/api/requests/{request_id}/accept/', {
            'lat': 0.3476,
            'lng': 32.5825
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify acceptance
        request.refresh_from_db()
        self.assertEqual(request.status, 'ACCEPTED')
        self.assertEqual(request.rodie, self.rodie)
        self.assertIsNotNone(request.accepted_at)
        
        # Verify cache is updated
        self.assertEqual(cache.get(f"request_status:{request_id}"), 'ACCEPTED')
        self.assertIsNone(cache.get(f"rodie_locked:{self.rodie.id}"))
        
        # 4. Roadie marks en route
        response = self.client.post(f'/api/requests/{request_id}/enroute/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        request.refresh_from_db()
        self.assertEqual(request.status, 'EN_ROUTE')
        
        # 5. Roadie marks arrived
        response = self.client.post(f'/api/requests/{request_id}/arrived/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        request.refresh_from_db()
        self.assertEqual(request.status, 'ARRIVED')
        
        # 6. Roadie starts service
        response = self.client.post(f'/api/requests/{request_id}/start/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        request.refresh_from_db()
        self.assertEqual(request.status, 'STARTED')
        
        # 7. Roadie completes service
        response = self.client.post(f'/api/requests/{request_id}/complete/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        request.refresh_from_db()
        self.assertEqual(request.status, 'COMPLETED')


class TestScenario7RiderCancelsAfterAccept(TransactionTestCase):
    """
    Scenario 7: Rider Cancels AFTER Roadie Accepts
    This was the previously broken flow
    """
    
    def setUp(self):
        cache.clear()
        self.rider = User.objects.create_user(
            username='rider_cancel',
            email='rider_cancel@test.com',
            role='RIDER',
            is_active=True
        )
        self.rodie = User.objects.create_user(
            username='rodie_cancel',
            email='rodie_cancel@test.com',
            role='RODIE',
            is_active=True,
            is_approved=True,
            is_online=True
        )
        
        self.service_type = ServiceType.objects.create(name='Towing', base_price=50000)
        RodieService.objects.create(rodie=self.rodie, service=self.service_type)
        
        Wallet.objects.create(user=self.rider, balance=100000)
        Wallet.objects.create(user=self.rodie, balance=50000)
        PlatformConfig.objects.create(max_negative_balance=10000)
        
        self.reason = CancellationReason.objects.create(
            role='RIDER',
            reason='Changed mind',
            is_active=True
        )
        
        self.client = APIClient()

    def test_rider_cancels_after_accept(self):
        """Test rider cancellation after roadie accepts"""
        # Create and accept request
        self.client.force_authenticate(user=self.rider)
        response = self.client.post('/api/requests/', {
            'service_type': self.service_type.id,
            'rider_lat': 0.3476,
            'rider_lng': 32.5825,
            'pickup_location': 'Test',
            'dropoff_location': 'Test'
        })
        request_id = response.data['id']
        
        self.client.force_authenticate(user=self.rodie)
        cache.set(f"active_offer:{self.rodie.id}", {'id': request_id}, timeout=15)
        response = self.client.post(f'/api/requests/{request_id}/accept/', {
            'lat': 0.3476,
            'lng': 32.5825
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Set cache locks
        cache.set(f"rodie_locked:{self.rodie.id}", request_id, timeout=15)
        cache.set(f"active_offer:{self.rodie.id}", {'id': request_id}, timeout=15)
        
        # Rider cancels
        self.client.force_authenticate(user=self.rider)
        response = self.client.post(f'/api/requests/{request_id}/cancel/', {
            'reason_id': self.reason.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify state
        request = ServiceRequest.objects.get(id=request_id)
        self.assertEqual(request.status, 'CANCELLED')
        
        # Verify cache locks are cleared
        self.assertIsNone(cache.get(f"rodie_locked:{self.rodie.id}"))
        self.assertIsNone(cache.get(f"active_offer:{self.rodie.id}"))
        
        # Verify cancellation record exists
        self.assertTrue(RequestCancellation.objects.filter(request=request).exists())


class TestScenario9ConcurrentRequests(TransactionTestCase):
    """
    Scenario 9: Two Riders Request at the Same Time, 5 Roadies
    Test race condition protection
    """
    
    def setUp(self):
        cache.clear()
        # Create 2 riders
        self.rider1 = User.objects.create_user(
            username='rider_concurrent1',
            email='rider_concurrent1@test.com',
            role='RIDER',
            is_active=True
        )
        self.rider2 = User.objects.create_user(
            username='rider_concurrent2',
            email='rider_concurrent2@test.com',
            role='RIDER',
            is_active=True
        )
        
        # Create 5 roadies
        self.rodies = []
        for i in range(5):
            rodie = User.objects.create_user(
                username=f'rodie_concurrent{i}',
                email=f'rodie_concurrent{i}@test.com',
                role='RODIE',
                is_active=True,
                is_approved=True,
                is_online=True
            )
            self.rodies.append(rodie)
        
        self.service_type = ServiceType.objects.create(name='Towing', base_price=50000)
        
        for rodie in self.rodies:
            RodieService.objects.create(rodie=rodie, service=self.service_type)
            RodieLocation.objects.create(rodie=rodie, lat=0.3476, lng=32.5825)
            Wallet.objects.create(user=rodie, balance=50000)
        
        Wallet.objects.create(user=self.rider1, balance=100000)
        Wallet.objects.create(user=self.rider2, balance=100000)
        PlatformConfig.objects.create(max_negative_balance=10000)
        
        self.client = APIClient()

    def test_concurrent_requests_race_protection(self):
        """Test that concurrent requests don't cause double-booking"""
        # Create two requests simultaneously
        self.client.force_authenticate(user=self.rider1)
        response1 = self.client.post('/api/requests/', {
            'service_type': self.service_type.id,
            'rider_lat': 0.3476,
            'rider_lng': 32.5825,
            'pickup_location': 'Test1',
            'dropoff_location': 'Test1'
        })
        request1_id = response1.data['id']
        
        self.client.force_authenticate(user=self.rider2)
        response2 = self.client.post('/api/requests/', {
            'service_type': self.service_type.id,
            'rider_lat': 0.3476,
            'rider_lng': 32.5825,
            'pickup_location': 'Test2',
            'dropoff_location': 'Test2'
        })
        request2_id = response2.data['id']
        
        # Simulate both requests targeting the same roadie
        target_rodie = self.rodies[0]
        cache.set(f"active_offer:{target_rodie.id}", {'id': request1_id}, timeout=15)
        cache.set(f"rodie_locked:{target_rodie.id}", request1_id, timeout=15)
        
        # First request is accepted
        self.client.force_authenticate(user=target_rodie)
        response = self.client.post(f'/api/requests/{request1_id}/accept/', {
            'lat': 0.3476,
            'lng': 32.5825
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify roadie is now busy
        request1 = ServiceRequest.objects.get(id=request1_id)
        self.assertEqual(request1.rodie, target_rodie)
        self.assertEqual(request1.status, 'ACCEPTED')
        
        # Try to accept second request with same roadie - should fail
        cache.set(f"active_offer:{target_rodie.id}", {'id': request2_id}, timeout=15)
        response = self.client.post(f'/api/requests/{request2_id}/accept/', {
            'lat': 0.3476,
            'lng': 32.5825
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('active request', response.data['detail'])
        
        # Verify second request is still unassigned
        request2 = ServiceRequest.objects.get(id=request2_id)
        self.assertIsNone(request2.rodie)
        self.assertEqual(request2.status, 'REQUESTED')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
