import requests
import logging
from django.conf import settings
from decimal import Decimal

logger = logging.getLogger(__name__)

class FlutterwaveClient:
    """
    Client for Flutterwave Payouts API.
    Used for automated mobile money disbursements in Uganda.
    """
    
    def __init__(self):
        self.base_url = getattr(settings, 'FLUTTERWAVE_BASE_URL', 'https://api.flutterwave.com/v3')
        self.secret_key = getattr(settings, 'FLUTTERWAVE_SECRET_KEY', '')
        self._token = None

    def _get_headers(self):
        """Returns headers with Flutterwave secret key."""
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

    def transfer_to_mobile_money(self, phone_number, amount, reference, description=""):
        """
        Initiates a mobile money transfer (Payout) via Flutterwave.
        
        Args:
            phone_number (str): Recipient phone in format 2567XXXXXXXX
            amount (Decimal): Amount to send
            reference (str): Internal unique reference (e.g. WTH-XXXX)
            description (str): Optional memo
            
        Returns:
            dict: Response from Flutterwave API
        """
        if not self.secret_key:
            return {"success": False, "error": "Flutterwave secret key not configured"}

        url = f"{self.base_url}/transfers"
        
        # Flutterwave transfer payload structure
        payload = {
            "account_bank": self._detect_bank_code(phone_number),
            "account_number": phone_number,
            "amount": float(amount),
            "currency": "UGX",
            "reference": reference,
            "narration": description or f"Vehix Withdrawal: {reference}",
            "debit_currency": "UGX"
        }

        try:
            headers = self._get_headers()
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            data = response.json()
            
            if response.status_code in [200, 201, 202] and data.get('status') == 'success':
                return {
                    "success": True,
                    "transaction_id": data.get('data', {}).get('id'),
                    "status": data.get('data', {}).get('status', 'PENDING'),
                    "raw_response": data
                }
            else:
                return {
                    "success": False,
                    "error": data.get('message', 'Transfer failed'),
                    "raw_response": data
                }
        except Exception as e:
            logger.error(f"Flutterwave Transfer Error: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_transfer_status(self, transaction_id):
        """Checks the status of a previous transfer."""
        if not self.secret_key:
            return None
        
        url = f"{self.base_url}/transfers/{transaction_id}"
        try:
            headers = self._get_headers()
            response = requests.get(url, headers=headers, timeout=15)
            return response.json()
        except Exception as e:
            logger.error(f"Flutterwave Status Check Error: {str(e)}")
            return None

    def _detect_bank_code(self, phone):
        """
        Returns Flutterwave bank code for mobile money providers in Uganda.
        Flutterwave uses specific bank codes for mobile money.
        """
        phone = str(phone)
        # MTN Uganda Mobile Money
        if '77' in phone or '78' in phone or '76' in phone:
            return "UGMTH"
        # Airtel Uganda Mobile Money
        if '75' in phone or '70' in phone or '74' in phone:
            return "UGARL"
        # Default fallback
        return "UGMTH"
