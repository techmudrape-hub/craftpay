"""
ORO Payout Service
Handles payout transactions through ORO Payout API
Uses same credentials as ORO payin
"""

import requests
import json
import time
from datetime import datetime
from config import Config
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class OroPayoutService:

    def __init__(self):
        """
        Initialize ORO Payout Service.
        Uses same credentials as payin.
        """
        self.service_provider = 'ORO'
        self.base_url = Config.ORO_BASE_URL
        self.client_id = Config.ORO_CLIENT_ID
        self.secret_id = Config.ORO_SECRET_ID

        # Session with retry logic
        self.session = self._create_session()

    def _create_session(self):
        """Create requests session with retry logic and connection pooling."""
        session = requests.Session()

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

        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _get_headers(self):
        """Build request headers required by ORO Payout API."""
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Client-Id': self.client_id,
            'X-Secret-Id': self.secret_id
        }

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def call_payout_api(self, account_number, ifsc_code, bank_name,
                        merchant_order_id, amount, payee_name,
                        email=None, mobile=None, mode='IMPS'):
        """
        Initiate a payout via ORO API.
        """
        try:
            url = f"{self.base_url}/payout/data"
            
            payload = {
                "account_name": payee_name or "Customer",
                "account_number": account_number,
                "ifsc_code": ifsc_code,
                "amount": float(amount),
                "trxid": str(merchant_order_id)
            }
            
            headers = self._get_headers()

            print(f"[ORO Payout] Initiating transfer for {merchant_order_id} to {url}")
            print(f"[ORO Payout] Payload: {json.dumps(payload)}")
            
            api_start = time.time()
            response = self.session.post(url, json=payload, headers=headers, timeout=(10, 60))
            api_elapsed = time.time() - api_start
            
            print(f"[ORO Payout] Response Status: {response.status_code}")
            print(f"[ORO Payout] Response Time: {api_elapsed:.2f}s")
            print(f"[ORO Payout] Response Body: {response.text}")
            
            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'API error: {response.text}'
                }
                
            resp_data = response.json()
            
            # Response Check
            status_val = str(resp_data.get('status', '')).lower()
            msg_val = str(resp_data.get('message', '')).lower()
            
            is_success = False
            if status_val in ['success', 'true', '1', 'pending']:
                is_success = True
            elif 'processed successfully' in msg_val or 'success' in msg_val:
                is_success = True
            elif resp_data.get('data') and isinstance(resp_data.get('data'), dict) and resp_data['data'].get('trx_id'):
                is_success = True
                
            if not is_success:
                return {
                    'success': False,
                    'message': resp_data.get('message', 'Payout failed')
                }
                
            data = resp_data.get('data', {})
            status_map = {
                'pending': 'INITIATED',
                'success': 'SUCCESS',
                'failed': 'FAILED'
            }
            
            pg_status = str(data.get('status', 'pending')).lower()
            mapped_status = status_map.get(pg_status, 'INITIATED')
            
            return {
                'success': True,
                'status': mapped_status,
                'merchant_order_id': merchant_order_id,
                'pg_txn_id': data.get('trx_id', ''),
                'amount': amount,
                'utr': data.get('utr', ''),
                'message': resp_data.get('message', 'Payout initiated successfully'),
                'data': data
            }

        except Exception as e:
            print(f"[ORO Payout] Error: {e}")
            import traceback; traceback.print_exc()
            return {
                'success': False,
                'message': f'API call error: {str(e)}'
            }

    def check_payout_status(self, merchant_order_id, pg_txn_id=None, txn_date=None):
        """
        Check payout status via ORO Check Payout Status API.
        """
        try:
            # We need the API ref num (trx_id from ORO). 
            # If pg_txn_id is not passed, it might fail or we should use merchant_order_id.
            # Usually pg_txn_id is the API Ref Num.
            api_ref_num = pg_txn_id if pg_txn_id else merchant_order_id
            
            url = f"{self.base_url}/payout/v1/check-status"
            payload = {
                "apiRefNum": api_ref_num
            }
            
            headers = self._get_headers()
            
            print(f"[ORO Payout] Checking status for {api_ref_num} to {url}")
            
            response = self.session.post(url, json=payload, headers=headers, timeout=(10, 30))
            
            print(f"[ORO Payout] Status Check Response Code: {response.status_code}")
            print(f"[ORO Payout] Status Check Response: {response.text}")
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'message': f'API error: {response.text}'
                }
                
            resp_data = response.json()
            
            if str(resp_data.get('status')).lower() != 'success':
                return {
                    'success': False,
                    'message': resp_data.get('message', 'Status check failed')
                }
                
            inner_data = resp_data.get('data', {})
            if str(inner_data.get('resultStatus')).lower() != 'success':
                # Sometimes pending txns show failure in check status, be careful.
                # Just return what we can
                pass
                
            txns = inner_data.get('data', [])
            if not txns or len(txns) == 0:
                return {
                    'success': False,
                    'message': 'No transaction data found in status response'
                }
                
            txn_details = txns[0]
            
            status_map = {
                'pending': 'INITIATED',
                'success': 'SUCCESS',
                'failed': 'FAILED'
            }
            
            pg_status = str(txn_details.get('TxnStatus', 'pending')).lower()
            mapped_status = status_map.get(pg_status, 'INITIATED')
            
            return {
                'success': True,
                'status': mapped_status,
                'merchant_order_id': merchant_order_id,
                'pg_txn_id': txn_details.get('TransactionId', ''),
                'amount': txn_details.get('Amount', 0),
                'utr': txn_details.get('UTR', ''),
                'created_at': txn_details.get('TransactionDate', ''),
                'message': inner_data.get('resultMessage', 'Status check successful')
            }

        except Exception as e:
            print(f"[ORO Payout] Status check error: {e}")
            import traceback; traceback.print_exc()
            return {
                'success': False,
                'message': f'Status check error: {str(e)}'
            }

# Singleton instance
oro_payout_service = OroPayoutService()
