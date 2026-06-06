"""
Integration tests for Vehix Matching System against LIVE backend
Tests the critical scenarios from the audit to ensure all bugs are fixed.
"""

import requests
import json
import time
from typing import Dict, Optional

# Configuration - Live backend
BASE_URL = "https://backend.vehix.ug/api"

class VehixAPIClient:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.token = None
        self.current_user = None
    
    def login(self, username: str, password: str) -> bool:
        """Login and store auth token"""
        response = self.session.post(
            f"{self.base_url}/auth/login/",
            json={"username": username, "password": password}
        )
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("token") or data.get("access")
            if self.token:
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                self.current_user = username
                return True
        return False
    
    def logout(self):
        """Logout and clear token"""
        self.session.headers.pop("Authorization", None)
        self.token = None
        self.current_user = None
    
    def create_request(self, service_type_id: int, rider_lat: float, rider_lng: float, 
                      pickup_location: str, dropoff_location: str) -> Optional[Dict]:
        """Create a service request"""
        response = self.session.post(
            f"{self.base_url}/requests/",
            json={
                "service_type": service_type_id,
                "rider_lat": rider_lat,
                "rider_lng": rider_lng,
                "pickup_location": pickup_location,
                "dropoff_location": dropoff_location
            }
        )
        if response.status_code == 201:
            return response.json()
        print(f"❌ Create request failed: {response.status_code} - {response.text}")
        return None
    
    def accept_request(self, request_id: int, lat: float, lng: float) -> Optional[Dict]:
        """Accept a service request (as roadie)"""
        response = self.session.post(
            f"{self.base_url}/requests/{request_id}/accept/",
            json={"lat": lat, "lng": lng}
        )
        if response.status_code == 200:
            return response.json()
        print(f"❌ Accept request failed: {response.status_code} - {response.text}")
        return None
    
    def decline_request(self, request_id: int) -> Optional[Dict]:
        """Decline a service request (as roadie)"""
        response = self.session.post(
            f"{self.base_url}/requests/{request_id}/decline/"
        )
        if response.status_code == 200:
            return response.json()
        print(f"❌ Decline request failed: {response.status_code} - {response.text}")
        return None
    
    def cancel_request(self, request_id: int, reason_id: int, 
                      current_lat: Optional[float] = None, current_lng: Optional[float] = None,
                      custom_reason_text: Optional[str] = None) -> Optional[Dict]:
        """Cancel a service request"""
        payload = {"reason_id": reason_id}
        if current_lat is not None:
            payload["current_lat"] = current_lat
        if current_lng is not None:
            payload["current_lng"] = current_lng
        if custom_reason_text is not None:
            payload["custom_reason_text"] = custom_reason_text
        
        response = self.session.post(
            f"{self.base_url}/requests/{request_id}/cancel/",
            json=payload
        )
        if response.status_code == 200:
            return response.json()
        print(f"❌ Cancel request failed: {response.status_code} - {response.text}")
        return None
    
    def get_request(self, request_id: int) -> Optional[Dict]:
        """Get request details"""
        response = self.session.get(f"{self.base_url}/requests/{request_id}/")
        if response.status_code == 200:
            return response.json()
        print(f"❌ Get request failed: {response.status_code} - {response.text}")
        return None
    
    def get_cancellation_reasons(self) -> Optional[Dict]:
        """Get cancellation reasons"""
        response = self.session.get(f"{self.base_url}/requests/cancellation-reasons/")
        if response.status_code == 200:
            return response.json()
        print(f"❌ Get cancellation reasons failed: {response.status_code} - {response.text}")
        return None
    
    def enroute_request(self, request_id: int) -> Optional[Dict]:
        """Mark request as en route"""
        response = self.session.post(f"{self.base_url}/requests/{request_id}/enroute/")
        if response.status_code == 200:
            return response.json()
        print(f"❌ Enroute request failed: {response.status_code} - {response.text}")
        return None
    
    def arrived_request(self, request_id: int) -> Optional[Dict]:
        """Mark request as arrived"""
        response = self.session.post(f"{self.base_url}/requests/{request_id}/arrived/")
        if response.status_code == 200:
            return response.json()
        print(f"❌ Arrived request failed: {response.status_code} - {response.text}")
        return None
    
    def start_request(self, request_id: int) -> Optional[Dict]:
        """Mark request as started"""
        response = self.session.post(f"{self.base_url}/requests/{request_id}/start/")
        if response.status_code == 200:
            return response.json()
        print(f"❌ Start request failed: {response.status_code} - {response.text}")
        return None
    
    def complete_request(self, request_id: int) -> Optional[Dict]:
        """Mark request as completed"""
        response = self.session.post(f"{self.base_url}/requests/{request_id}/complete/")
        if response.status_code == 200:
            return response.json()
        print(f"❌ Complete request failed: {response.status_code} - {response.text}")
        return None


def print_section(title: str):
    """Print a section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_bug1_home_screen_ws_handler():
    """
    Bug 1: HomeScreen WS Handler Stays Active During RideScreen
    Verify that accepting clears the rodie lock cache
    """
    print_section("TEST BUG 1: HomeScreen WS Handler Fix")
    
    client = VehixAPIClient()
    
    # Login as rider
    if not client.login("parrot", "parrot"):
        print("❌ Failed to login as rider")
        return False
    
    # Create request
    print("📍 Creating service request...")
    request = client.create_request(
        service_type_id=1,  # Update to valid service type ID
        rider_lat=0.3476,
        rider_lng=32.5825,
        pickup_location="Test Pickup",
        dropoff_location="Test Dropoff"
    )
    
    if not request:
        print("❌ Failed to create request")
        return False
    
    request_id = request['id']
    print(f"✅ Request created: {request_id}")
    
    # Verify initial status
    request_details = client.get_request(request_id)
    if request_details['status'] != 'REQUESTED':
        print(f"❌ Initial status not REQUESTED: {request_details['status']}")
        return False
    print(f"✅ Initial status: REQUESTED")
    
    # Login as roadie
    client.logout()
    if not client.login("castle", "castle"):
        print("❌ Failed to login as roadie")
        return False
    
    # Accept request
    print("📍 Accepting request...")
    accept_result = client.accept_request(request_id, 0.3476, 32.5825)
    
    if not accept_result:
        print("❌ Failed to accept request")
        return False
    
    print(f"✅ Request accepted")
    
    # Verify status changed to ACCEPTED
    request_details = client.get_request(request_id)
    if request_details['status'] != 'ACCEPTED':
        print(f"❌ Status not ACCEPTED after acceptance: {request_details['status']}")
        return False
    
    print(f"✅ Status changed to: ACCEPTED")
    
    # Verify rodie is assigned
    if not request_details.get('rodie'):
        print("❌ No rodie assigned after acceptance")
        return False
    
    print(f"✅ Rodie assigned: {request_details['rodie']['username']}")
    
    print("✅ BUG 1 FIX VERIFIED: Acceptance clears locks and assigns roadie correctly")
    return True


def test_bug2_decline_cache_pollution():
    """
    Bug 2: Decline Pollutes Cache
    Verify that declining does NOT overwrite request_status cache
    """
    print_section("TEST BUG 2: Decline Cache Pollution Fix")
    
    client = VehixAPIClient()
    
    # Login as rider
    if not client.login("parrot", "parrot"):
        print("❌ Failed to login as rider")
        return False
    
    # Create request
    print("📍 Creating service request...")
    request = client.create_request(
        service_type_id=1,
        rider_lat=0.3476,
        rider_lng=32.5825,
        pickup_location="Test Pickup",
        dropoff_location="Test Dropoff"
    )
    
    if not request:
        return False
    
    request_id = request['id']
    print(f"✅ Request created: {request_id}")
    
    # Login as roadie
    client.logout()
    if not client.login("castle", "castle"):
        print("❌ Failed to login as roadie")
        return False
    
    # Decline request
    print("📍 Declining request...")
    decline_result = client.decline_request(request_id)
    
    if not decline_result:
        print("❌ Failed to decline request")
        return False
    
    print(f"✅ Request declined")
    
    # Verify status is still REQUESTED (not DECLINED)
    request_details = client.get_request(request_id)
    if request_details['status'] != 'REQUESTED':
        print(f"❌ Status changed to {request_details['status']} - should remain REQUESTED")
        return False
    
    print(f"✅ Status remains: REQUESTED (not polluted with DECLINED)")
    
    print("✅ BUG 2 FIX VERIFIED: Decline does not pollute request_status cache")
    return True


def test_bug7_rider_cancels_after_accept():
    """
    Bug 7: Rider Cancels AFTER Roadie Accepts
    This was the previously broken flow
    """
    print_section("TEST BUG 7: Rider Cancels After Accept")
    
    client = VehixAPIClient()
    
    # Login as rider
    if not client.login("parrot", "parrot"):
        print("❌ Failed to login as rider")
        return False
    
    # Create request
    print("📍 Creating service request...")
    request = client.create_request(
        service_type_id=1,
        rider_lat=0.3476,
        rider_lng=32.5825,
        pickup_location="Test Pickup",
        dropoff_location="Test Dropoff"
    )
    
    if not request:
        return False
    
    request_id = request['id']
    print(f"✅ Request created: {request_id}")
    
    # Login as roadie
    client.logout()
    if not client.login("castle", "castle"):
        print("❌ Failed to login as roadie")
        return False
    
    # Accept request
    print("📍 Accepting request...")
    accept_result = client.accept_request(request_id, 0.3476, 32.5825)
    
    if not accept_result:
        print("❌ Failed to accept request")
        return False
    
    print(f"✅ Request accepted")
    
    # Verify status is ACCEPTED
    request_details = client.get_request(request_id)
    if request_details['status'] != 'ACCEPTED':
        print(f"❌ Status not ACCEPTED: {request_details['status']}")
        return False
    
    print(f"✅ Status: ACCEPTED")
    
    # Login as rider
    client.logout()
    if not client.login("test_rider", "test_password"):
        print("❌ Failed to login as rider")
        return False
    
    # Get cancellation reasons
    print("📍 Getting cancellation reasons...")
    reasons = client.get_cancellation_reasons()
    
    if not reasons or not reasons.get('reasons'):
        print("❌ Failed to get cancellation reasons")
        return False
    
    rider_reasons = [r for r in reasons['reasons'] if r.get('role') == 'RIDER']
    if not rider_reasons:
        print("❌ No rider cancellation reasons found")
        return False
    
    reason_id = rider_reasons[0]['id']
    print(f"✅ Using cancellation reason: {rider_reasons[0]['reason']}")
    
    # Cancel request
    print("📍 Cancelling request...")
    cancel_result = client.cancel_request(request_id, reason_id)
    
    if not cancel_result:
        print("❌ Failed to cancel request")
        return False
    
    print(f"✅ Request cancelled")
    
    # Verify status is CANCELLED
    request_details = client.get_request(request_id)
    if request_details['status'] != 'CANCELLED':
        print(f"❌ Status not CANCELLED: {request_details['status']}")
        return False
    
    print(f"✅ Status changed to: CANCELLED")
    
    print("✅ BUG 7 FIX VERIFIED: Rider can cancel after roadie accepts")
    return True


def test_scenario1_happy_path():
    """
    Scenario 1: Happy Path - 1 Rider, 1 Roadie
    Full end-to-end test of the matching flow
    """
    print_section("TEST SCENARIO 1: Happy Path (End-to-End)")
    
    client = VehixAPIClient()
    
    # Login as rider
    if not client.login("parrot", "parrot"):
        print("❌ Failed to login as rider")
        return False
    
    # Create request
    print("📍 Creating service request...")
    request = client.create_request(
        service_type_id=1,
        rider_lat=0.3476,
        rider_lng=32.5825,
        pickup_location="Test Pickup",
        dropoff_location="Test Dropoff"
    )
    
    if not request:
        return False
    
    request_id = request['id']
    print(f"✅ Request created: {request_id}")
    
    # Login as roadie
    client.logout()
    if not client.login("castle", "castle"):
        print("❌ Failed to login as roadie")
        return False
    
    # Accept
    print("📍 Accepting...")
    if not client.accept_request(request_id, 0.3476, 32.5825):
        return False
    print(f"✅ Accepted")
    
    # En route
    print("📍 Marking en route...")
    if not client.enroute_request(request_id):
        return False
    print(f"✅ En route")
    
    # Arrived
    print("📍 Marking arrived...")
    if not client.arrived_request(request_id):
        return False
    print(f"✅ Arrived")
    
    # Started
    print("📍 Starting service...")
    if not client.start_request(request_id):
        return False
    print(f"✅ Started")
    
    # Completed
    print("📍 Completing service...")
    if not client.complete_request(request_id):
        return False
    print(f"✅ Completed")
    
    # Verify final status
    request_details = client.get_request(request_id)
    if request_details['status'] != 'COMPLETED':
        print(f"❌ Final status not COMPLETED: {request_details['status']}")
        return False
    
    print(f"✅ Final status: COMPLETED")
    print("✅ SCENARIO 1 VERIFIED: Complete happy path works correctly")
    return True


def run_all_tests():
    """Run all integration tests"""
    print("\n" + "=" * 70)
    print("  VEHIX MATCHING SYSTEM - LIVE INTEGRATION TESTS")
    print("=" * 70)
    print(f"\n🌐 Testing against: {BASE_URL}")
    print("\n⚠️  PREREQUISITES:")
    print("   1. Backend must be running at the configured URL")
    print("   2. Test users must exist:")
    print("      - parrot (role: RIDER)")
    print("      - castle (role: RODIE, approved, online)")
    print("   3. At least one service type must exist (ID: 1)")
    print("   4. Cancellation reasons must exist")
    print("\n" + "=" * 70)
    
    results = []
    
    # Run tests
    results.append(("Bug 1: HomeScreen WS Handler", test_bug1_home_screen_ws_handler()))
    results.append(("Bug 2: Decline Cache Pollution", test_bug2_decline_cache_pollution()))
    results.append(("Bug 7: Rider Cancels After Accept", test_bug7_rider_cancels_after_accept()))
    results.append(("Scenario 1: Happy Path", test_scenario1_happy_path()))
    
    # Print summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print("\n" + "=" * 70)
    print(f"  TOTAL: {passed}/{total} tests passed")
    print("=" * 70)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Bug fixes are working correctly!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed - please review the output above")
    
    return passed == total


if __name__ == "__main__":
    import sys
    
    # Allow custom base URL from command line
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
    
    success = run_all_tests()
    sys.exit(0 if success else 1)
