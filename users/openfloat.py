import requests
import json
import logging
from django.conf import settings
from decimal import Decimal

logger = logging.getLogger(__name__)

class OpenFloatClient:
    """
    Client for OpenFloat (Pesapal) Payouts API.
    Used for automated mobile money disbursements in Uganda.
    """
    
    def __init__(self):
        self.base_url = getattr(settings, 'OPENFLOAT_BASE_URL', 'https://api.openfloat.africa/v1')
        self.client_id = getattr(settings, 'OPENFLOAT_CLIENT_ID', '')
        self.client_secret = getattr(settings, 'OPENFLOAT_CLIENT_SECRET', '')
        self.account_id = getattr(settings, 'OPENFLOAT_ACCOUNT_ID', '') # Source float account
        self._token = None

    def _get_token(self):
        """Authenticates and returns the bearer token."""
        if self._token:
            return self._token
            
        url = f"{self.base_url}/auth/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        try:
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            self._token = data.get('access_token')
            return self._token
        except Exception as e:
            logger.error(f"OpenFloat Auth Error: {str(e)}")
            return None

    def transfer_to_mobile_money(self, phone_number, amount, reference, description=""):
        """
        Initiates a mobile money transfer (Payout).
        
        Args:
            phone_number (str): Recipient phone in format 2567XXXXXXXX
            amount (Decimal): Amount to send
            reference (str): Internal unique reference (e.g. WTH-XXXX)
            description (str): Optional memo
            
        Returns:
            dict: Response from OpenFloat API
        """
        token = self._get_token()
        if not token:
            return {"success": False, "error": "Authentication failed"}

        url = f"{self.base_url}/transfers/mobile"
        
        # Standard OpenFloat/Pesapal Payout payload structure
        payload = {
            "account_id": self.account_id,
            "amount": float(amount),
            "currency": "UGX",
            "reference": reference,
            "recipient": {
                "phone_number": phone_number,
                "country_code": "UG",
                "network": self._detect_network(phone_number)
            },
            "description": description or f"Withdrawal {reference}"
        }

        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            data = response.json()
            
            if response.status_code in [200, 201, 202]:
                return {
                    "success": True,
                    "transaction_id": data.get('transaction_id'),
                    "status": data.get('status', 'PENDING'),
                    "raw_response": data
                }
            else:
                return {
                    "success": False,
                    "error": data.get('message', 'Transfer failed'),
                    "raw_response": data
                }
        except Exception as e:
            logger.error(f"OpenFloat Transfer Error: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_transfer_status(self, transaction_id):
        """Checks the status of a previous transfer."""
        token = self._get_token()
        if not token: return None
        
        url = f"{self.base_url}/transfers/{transaction_id}/status"
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(url, headers=headers, timeout=15)
            return response.json()
        except Exception as e:
            logger.error(f"OpenFloat Status Check Error: {str(e)}")
            return None

    def _detect_network(self, phone):
        """Simple helper to detect MTN vs Airtel in Uganda."""
        phone = str(phone)
        if '77' in phone or '78' in phone or '76' in phone:
            return "MTN"
        if '75' in phone or '70' in phone or '74' in phone:
            return "AIRTEL"
        return "GENERIC"
