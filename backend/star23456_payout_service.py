"""
Star23456 Payout Service
Handles payout transactions through Star23456
"""

import requests
import json
import time
from datetime import datetime, timedelta
from config import Config

class Star23456PayoutService:
    def __init__(self):
        self.base_url = Config.STAR23456_BASE_URL
        self.merchant_id = Config.STAR23456_MERCHANT_ID
        self.api_key = Config.STAR23456_API_KEY
        
        self.session = requests.Session()
        
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=2,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["POST", "GET"],
            raise_on_status=False
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Token caching
        self._token = None
        self._token_expiry = None

    def get_token(self):
        """Get or refresh the authentication token"""
        if self._token and self._token_expiry and datetime.now() < self._token_expiry:
            return self._token
            
        url = f"{self.base_url}/Auth/login"
        payload = {
            "username": self.merchant_id,
            "password": self.api_key
        }
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            response = self.session.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if "token" in data:
                self._token = data["token"]
                self._token_expiry = datetime.now() + timedelta(minutes=105)
                return self._token
            return None
        except Exception as e:
            print(f"[Star23456 Payout] Error getting token: {e}")
            return None

    def call_payout_api(self, account_number, ifsc_code, bank_name, merchant_order_id, amount, payee_name, email, mobile):
        """
        Call Star23456 payout API
        """
        token = self.get_token()
        if not token:
            return {'success': False, 'message': 'Failed to authenticate'}
            
        url = f"{self.base_url}/payout/create"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        payload = {
            "description": "Payout",
            "amount": str(amount),
            "txnMode": "IMPS",  # Defaulting to IMPS, can be made dynamic if needed
            "paymentType": "NB", # Bank transfer
            "clientTxnId": merchant_order_id,
            "beneName": payee_name or "Beneficiary",
            "beneAccNum": account_number,
            "beneIfscCode": ifsc_code,
            "beneEmail": email or "bene@example.com",
            "beneMobile": mobile or "9999999999",
            "bankName": bank_name or "Bank"
        }
        
        try:
            response = self.session.post(url, headers=headers, json=payload, timeout=30)
            data = response.json()
            
            if response.status_code == 200 and data.get('status') == True:
                return {
                    'success': True,
                    'message': data.get('message', 'Payout initiated successfully'),
                    'transaction_id': data.get('transactionId'),
                    'status': data.get('statusCode', 'PENDING')
                }
            else:
                return {
                    'success': False,
                    'message': data.get('error') or data.get('message', 'Payout API failed')
                }
        except Exception as e:
            print(f"[Star23456 Payout] API Error: {e}")
            return {'success': False, 'message': 'Payout request failed due to an exception'}

    def check_payout_status(self, merchant_order_id):
        """Check status of a payout"""
        token = self.get_token()
        if not token:
            return {'success': False, 'message': 'Failed to authenticate'}
            
        url = f"{self.base_url}/payout/status/{merchant_order_id}"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        try:
            response = self.session.get(url, headers=headers, timeout=15)
            data = response.json()
            
            if response.status_code == 200 and data.get('status') == True:
                status_code = data.get('statusCode', '')
                status = 'FAILED'
                
                if status_code in ['COMPLETED']:
                    status = 'SUCCESS'
                elif status_code in ['ACCEPTED', 'PENDING', 'PROCESSING']:
                    status = 'PENDING'
                elif status_code in ['FAILED', 'REVERSED']:
                    status = 'FAILED'
                
                return {
                    'success': True,
                    'status': status,
                    'raw_status': status_code,
                    'transaction_id': data.get('transactionId'),
                    'merchant_order_id': data.get('orderId', merchant_order_id),
                    'utr': data.get('bankId'),
                    'amount': data.get('amount'),
                    'created_at': data.get('createdAt'),
                    'message': data.get('message')
                }
            return {'success': False, 'message': data.get('error', 'Failed to check status')}
            
        except Exception as e:
            print(f"[Star23456 Payout] Status check error: {e}")
            return {'success': False, 'message': str(e)}

star23456_payout_service = Star23456PayoutService()

def get_payout_service():
    """Return the payout service instance"""
    return star23456_payout_service
