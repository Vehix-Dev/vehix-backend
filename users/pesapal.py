import sys
import os
import json
import importlib.util
from django.conf import settings

def _import_requests_safely():
    # Attempt to find requests in site-packages specifically to avoid shadowing by local 'requests' app
    for path in sys.path:
        if 'site-packages' in path.lower():
            requests_init = os.path.join(path, 'requests', '__init__.py')
            if os.path.exists(requests_init):
                try:
                    spec = importlib.util.spec_from_file_location("requests_standard_lib", requests_init)
                    lib = importlib.util.module_from_spec(spec)
                    # Add to sys.modules under a unique name to avoid further conflicts
                    sys.modules["requests_standard_lib"] = lib
                    spec.loader.exec_module(lib)
                    if hasattr(lib, 'post'):
                        return lib
                except Exception:
                    continue
    
    # Fallback: try standard import but check for post attribute
    try:
        import requests as lib
        if hasattr(lib, 'post'):
            return lib
    except ImportError:
        pass
    
    # Extreme fallback: return something that won't cause immediate crash if possible, 
    # but at this point we are in trouble.
    return None

# Get the real requests library
requests_lib = _import_requests_safely()

class PesapalClient:
    # Switch to https://cybqa.pesapal.com/pesapalv3 for sandbox
    BASE_URL = getattr(settings, 'PESAPAL_URL', 'https://pay.pesapal.com/v3')
    CONSUMER_KEY = getattr(settings, 'PESAPAL_CONSUMER_KEY', '')
    CONSUMER_SECRET = getattr(settings, 'PESAPAL_CONSUMER_SECRET', '')
    IPN_ID = getattr(settings, 'PESAPAL_IPN_ID', '')

    def get_token(self):
        url = f"{self.BASE_URL}/api/Auth/RequestToken"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {
            "consumer_key": self.CONSUMER_KEY,
            "consumer_secret": self.CONSUMER_SECRET
        }
        response = requests_lib.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            return response.json().get('token')
        print(f"Pesapal Auth Failed: {response.status_code} - {response.text}")
        return None

    def submit_order(self, payment, callback_url, phone_number=None):
        token = self.get_token()
        if not token:
            raise Exception("Failed to authenticate with Pesapal")

        url = f"{self.BASE_URL}/api/Transactions/SubmitOrderRequest"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        # Use provided phone number or fall back to user's phone
        payment_phone = phone_number or payment.user.phone or ""
        
        # Construct payload
        payload = {
            "id": payment.reference,
            "currency": "UGX",  # Changed to UGX for Uganda Shillings
            "amount": "{:.2f}".format(float(payment.amount)),
            "description": payment.description or "Wallet Deposit",
            "callback_url": callback_url,
            "notification_id": self.IPN_ID,
            "billing_address": {
                "email_address": payment.user.email or "user@example.com",
                "phone_number": payment_phone,  # Use the provided phone number
                "country_code": "UG",  # Changed to Uganda
                "first_name": payment.user.first_name or "User",
                "middle_name": "",
                "last_name": payment.user.last_name or "Name",
                "line_1": "",
                "line_2": "",
                "city": "Kampala",  # Added default city
                "state": "",
                "postal_code": "",
                "zip_code": ""
            }
        }

        print(f"Pesapal SubmitOrder Payload: {json.dumps(payload)}")
        response = requests_lib.post(url, json=payload, headers=headers)
        print(f"Pesapal SubmitOrder Status: {response.status_code}")
        print(f"Pesapal SubmitOrder Response: {response.text}")
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Pesapal Error: {response.text}")

    def get_transaction_status(self, order_tracking_id):
        token = self.get_token()
        if not token:
            return None

        url = f"{self.BASE_URL}/api/Transactions/GetTransactionStatus?orderTrackingId={order_tracking_id}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        }

        response = requests_lib.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        return None

    def submit_mobile_payment(self, order_tracking_id, phone_number, payment_method="MPESA"):
        token = self.get_token()
        if not token:
            raise Exception("Failed to authenticate with Pesapal")

        url = f"{self.BASE_URL}/api/Transactions/SubmitMobileMoneyPayment"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        payload = {
            "order_tracking_id": order_tracking_id,
            "phone_number": phone_number,
            "payment_method": payment_method
        }
        response = requests_lib.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Pesapal Mobile Payment Error: {response.text}")
