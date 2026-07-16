"""
Nextpay Payout Service
Handles payout transactions through Nextpay
"""

import requests
import json
import time
import hmac
import hashlib
import uuid
from datetime import datetime
from config import Config
from database import get_db_connection

class NextpayPayoutService:
    def __init__(self):
        self.base_url = Config.NEXTPAY_BASE_URL
        self.client_id = Config.NEXTPAY_CLIENT_ID
        self.api_secret = Config.NEXTPAY_API_SECRET
        
        self.session = requests.Session()
        
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["POST", "GET"],
            raise_on_status=False
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def generate_request_id(self):
        """Generate unique request id"""
        return f"REQ_{uuid.uuid4().hex[:12].upper()}"

    def generate_signature(self, data_to_sign):
        """
        Generate HMAC SHA256 signature for Nextpay API
        """
        sorted_keys = sorted(data_to_sign.keys())
        
        canonical_parts = []
        for key in sorted_keys:
            value = str(data_to_sign[key])
            canonical_parts.append(f"{key}={value}")
            
        canonical_string = "&".join(canonical_parts)
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            canonical_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature

    def get_headers(self, timestamp, request_id, signature):
        """
        Get request headers for Nextpay API
        """
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Client-ID': self.client_id,
            'X-Timestamp': str(timestamp),
            'X-Request-ID': request_id,
            'X-Signature': signature
        }
        return headers

    def call_payout_api(self, account_number, ifsc_code, bank_name, merchant_order_id,
                        amount, payee_name, email, mobile):
        """
        Call Nextpay payout API
        """
        try:
            timestamp = int(time.time())
            request_id = self.generate_request_id()
            
            # Nextpay documentation requires these fields
            payload = {
                'transaction_id': merchant_order_id.strip(),
                'account_holder_name': payee_name.strip(),
                'account_number': account_number.strip(),
                'ifsc_code': ifsc_code.upper().strip(),
                'amount': amount,
                'mode': 'IMPS',  # Default to IMPS
                'mobile': mobile.strip() if mobile else '9999999999',
                'remarks': 'Payout',
                'latitude': 28.7041,
                'longitude': 77.1025,
                'purpose': 'Payment'
            }
            
            data_to_sign = payload.copy()
            data_to_sign['timestamp'] = str(timestamp)
            data_to_sign['request_id'] = request_id
            
            signature = self.generate_signature(data_to_sign)
            
            url = f"{self.base_url}/api/v1/payout/transfer"
            
            response = self.session.post(
                url,
                headers=self.get_headers(timestamp, request_id, signature),
                json=payload,
                timeout=(10, 60)
            )
            
            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'Nextpay API error: {response.text}'
                }
                
            nextpay_response = response.json()
            
            if not nextpay_response.get('success'):
                error_msg = nextpay_response.get('message', 'Payout creation failed')
                return {'success': False, 'message': error_msg}
                
            data = nextpay_response.get('data', {})
            payout_status = data.get('status', 'INITIATED').upper()
            
            merchant_order_id_resp = data.get('reference_id', data.get('transaction_id', merchant_order_id))
            amount_resp = data.get('amount', str(amount))
            charge = data.get('charge', '0')
            gst = data.get('gst', '0')
            total_debit = data.get('total_deducted', str(amount))
            utr = data.get('utr_number', '')
            
            if payout_status == 'SUCCESS':
                mapped_status = 'SUCCESS'
            elif payout_status in ['FAILED', 'FAILURE']:
                mapped_status = 'FAILED'
            else:
                mapped_status = 'INITIATED'
                
            return {
                'success': True,
                'status': mapped_status,
                'merchant_order_id': merchant_order_id_resp,
                'amount': amount_resp,
                'charge': charge,
                'gst': gst,
                'total_debit_amount': total_debit,
                'utr': utr,
                'message': nextpay_response.get('message', 'Payout initiated successfully'),
                'data': nextpay_response
            }
            
        except requests.exceptions.Timeout as e:
            print(f"Nextpay Payout API timeout error: {e}")
            return {
                'success': False,
                'message': 'Payout gateway timeout.'
            }
        except Exception as e:
            print(f"Nextpay Payout API error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'API call error: {str(e)}'
            }

    def check_payout_status(self, merchant_order_id):
        """
        Check payout status on Nextpay
        """
        try:
            url = f"{self.base_url}/api/v1/payout/status"
            
            timestamp = int(time.time())
            request_id = self.generate_request_id()
            
            payload = {
                'transaction_id': merchant_order_id
            }
            
            data_to_sign = payload.copy()
            data_to_sign['timestamp'] = str(timestamp)
            data_to_sign['request_id'] = request_id
            
            signature = self.generate_signature(data_to_sign)
            
            response = self.session.post(
                url,
                headers=self.get_headers(timestamp, request_id, signature),
                json=payload,
                timeout=(10, 60)
            )
            
            if response.status_code not in [200, 201]:
                return {'success': False, 'message': f'Status check failed: {response.text}'}
                
            nextpay_response = response.json()
            if not nextpay_response.get('success'):
                return {'success': False, 'message': nextpay_response.get('message', 'Status check failed')}
                
            data = nextpay_response.get('data', {})
            transaction_status = data.get('status', 'PENDING').upper()
            
            if transaction_status == 'SUCCESS':
                mapped_status = 'SUCCESS'
            elif transaction_status in ['FAILED', 'FAILURE']:
                mapped_status = 'FAILED'
            else:
                mapped_status = 'INITIATED'
                
            return {
                'success': True,
                'status': mapped_status,
                'merchant_order_id': data.get('transaction_id', merchant_order_id),
                'amount': float(data.get('amount', 0)),
                'utr': data.get('utr_number', ''),
                'created_at': data.get('created_at', ''),
                'message': nextpay_response.get('message', 'Status retrieved successfully')
            }
            
        except Exception as e:
            print(f"Nextpay Check status error: {e}")
            return {'success': False, 'message': f'Status check error: {str(e)}'}

nextpay_payout_service = NextpayPayoutService()

def get_payout_service():
    return nextpay_payout_service
