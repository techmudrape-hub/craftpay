"""
Kortyapay Payout Service
Handles authentication (POST /user/login), payout remittance (POST /payout/process),
and status inquiry (GET /payout/status/{txn_id}) for Kortya Pay portal integration.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import time
from datetime import datetime
from config import Config
from database import get_db_connection


class KortyapayPayoutService:

    def __init__(self):
        """
        Initialize Kortyapay Payout Service
        """
        self.base_url = getattr(Config, 'KORTYAPAY_BASE_URL', 'https://cms.kortyapayultra.com/api').rstrip('/')
        self.email = getattr(Config, 'KORTYAPAY_EMAIL', '')
        self.password = getattr(Config, 'KORTYAPAY_PASSWORD', '')
        self.token = getattr(Config, 'KORTYAPAY_TOKEN', getattr(Config, 'KORTYAPAY_API_KEY', ''))
        self.client_id = getattr(Config, 'KORTYAPAY_CLIENT_ID', '')
        self.secret_key = getattr(Config, 'KORTYAPAY_SECRET_KEY', '')
        
        # Create a session with retry logic and connection pooling
        self.session = self._create_session_with_retries()
    
    def _create_session_with_retries(self):
        """
        Create a requests session with retry logic and connection pooling
        """
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

    def _get_token(self, force_refresh=False):
        """
        Get or generate API Bearer Token via POST /user/login
        Endpoint: /user/login
        """
        if force_refresh:
            self.token = None

        if not force_refresh and self.token:
            return self.token

        import os
        email = getattr(Config, 'KORTYAPAY_EMAIL', '') or os.getenv('KORTYAPAY_EMAIL', '')
        password = getattr(Config, 'KORTYAPAY_PASSWORD', '') or os.getenv('KORTYAPAY_PASSWORD', '')

        if not email or not password:
            return self.token

        try:
            url = f"{self.base_url}/user/login"
            print(f"[Kortyapay Payout] Authenticating via POST {url} for email: {email}")
            payload = {
                "email": email,
                "password": password
            }
            response = self.session.post(
                url,
                json=payload,
                headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                timeout=(10, 30)
            )
            if response.status_code == 200:
                resp_json = response.json()
                if resp_json.get('status') is True:
                    data = resp_json.get('data', {})
                    token = data.get('token')
                    if token:
                        self.token = token
                        print("[Kortyapay Payout] Token generated successfully via /user/login.")
                        return self.token
            print(f"[Kortyapay Payout] Login failed ({response.status_code}): {response.text}")
        except Exception as e:
            print(f"[Kortyapay Payout] Error generating token via /user/login: {e}")
        return self.token

    def _get_headers(self, force_refresh=False):
        """
        Get request headers for Kortyapay API (ONLY Authorization: Bearer {token})
        An Authorization header with Bearer {token} is required for all endpoints except login.
        """
        token = self._get_token(force_refresh=force_refresh)
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if token:
            headers['Authorization'] = f"Bearer {token}"
        return headers

    def call_payout_api(self, account_number, ifsc_code, bank_name, merchant_order_id,
                        amount, payee_name, mobile, mode='IMPS', email=''):
        """
        Call Kortyapay Payout Process API
        POST /payout/process
        
        Body Parameters:
        - account_number: Required
        - ifsc_code: Required (11 Char)
        - account_holder: Required
        - amount: Required (between 101 and 100,000)
        - transfer_type: Required (IMPS, NEFT, RTGS)
        - order_id: Optional
        """
        try:
            print(f"[Kortyapay Payout] Creating payout:")
            print(f"  Order ID: {merchant_order_id}")
            print(f"  Amount: {amount}")
            print(f"  Payee: {payee_name}")
            print(f"  Account: {account_number}")
            print(f"  IFSC: {ifsc_code}")
            print(f"  Transfer Type: {mode}")

            try:
                numeric_amount = float(amount)
                if not (101 <= numeric_amount <= 100000):
                    print(f"[Kortyapay Payout] Warning: Amount {numeric_amount} is outside recommended range 101 - 100,000")
            except (ValueError, TypeError):
                pass

            transfer_type = mode.upper() if mode else 'IMPS'
            if transfer_type not in ['IMPS', 'NEFT', 'RTGS']:
                transfer_type = 'IMPS'

            payload = {
                "account_number": str(account_number).strip(),
                "ifsc_code": str(ifsc_code).strip().upper(),
                "account_holder": str(payee_name).strip(),
                "amount": float(amount),
                "transfer_type": transfer_type,
                "order_id": str(merchant_order_id).strip()
            }

            url = f"{self.base_url}/payout/process"

            print(f"[Kortyapay Payout] Calling API: {url}")
            print(f"[Kortyapay Payout] Payload: {json.dumps(payload, indent=2)}")

            response = self.session.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=(10, 60)
            )

            if response.status_code in [401, 403]:
                print("[Kortyapay Payout] 401/403 Unauthenticated encountered. Re-authenticating via /user/login...")
                response = self.session.post(
                    url,
                    headers=self._get_headers(force_refresh=True),
                    json=payload,
                    timeout=(10, 60)
                )

            print(f"[Kortyapay Payout] Response Status: {response.status_code}")
            print(f"[Kortyapay Payout] Response Text: {response.text}")

            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'Kortyapay API error ({response.status_code}): {response.text}'
                }

            resp_json = response.json()
            is_status = resp_json.get('status', False)
            message = resp_json.get('message', 'Payout processed')
            data = resp_json.get('data', {})
            if not isinstance(data, dict):
                data = {}

            if is_status is True or str(is_status).lower() in ['true', 'success', 'ok', '1']:
                txn_id = data.get('txn_id', merchant_order_id)
                rrn = data.get('rrn', '')
                api_status = str(data.get('status', 'PENDING')).upper()
                charges = data.get('charges', 0)
                total_deducted = data.get('total_deducted', float(amount))
                
                mapped_status = 'INITIATED'
                if api_status in ['SUCCESS', 'SUCCESSFUL', 'COMPLETED', 'TRUE']:
                    mapped_status = 'SUCCESS'
                elif api_status in ['FAILED', 'FAILURE', 'REJECTED', 'FALSE']:
                    mapped_status = 'FAILED'
                elif api_status in ['PENDING', 'INITIATED', 'PROCESSING', 'IN_PROCESS', 'QUEUED']:
                    mapped_status = 'INITIATED'

                return {
                    'success': True,
                    'status': mapped_status,
                    'merchant_order_id': merchant_order_id,
                    'pg_txn_id': txn_id,
                    'utr': rrn,
                    'amount': str(data.get('amount', amount)),
                    'charges': charges,
                    'total_deducted': total_deducted,
                    'message': message,
                    'data': resp_json
                }
            else:
                return {
                    'success': False,
                    'message': message or 'Payout initiation failed',
                    'data': resp_json
                }

        except requests.exceptions.Timeout as e:
            print(f"[Kortyapay Payout] API call timeout error: {e}")
            return {
                'success': False,
                'message': 'Payout request timed out. Please check status.'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[Kortyapay Payout] API call connection error: {e}")
            return {
                'success': False,
                'message': 'Unable to connect to Kortyapay payout gateway.'
            }
        except Exception as e:
            print(f"[Kortyapay Payout] API call error: {e}")
            return {
                'success': False,
                'message': f'Kortyapay API error: {str(e)}'
            }

    def check_payout_status(self, merchant_order_id):
        """
        Check Kortyapay payout status
        GET /payout/status/{txn_id}
        """
        try:
            url = f"{self.base_url}/payout/status/{merchant_order_id}"
            print(f"[Kortyapay Payout] Checking status API: {url}")

            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=(10, 30)
            )

            if response.status_code in [401, 403]:
                print("[Kortyapay Payout] 401/403 Unauthenticated encountered during status check. Re-authenticating...")
                response = self.session.get(
                    url,
                    headers=self._get_headers(force_refresh=True),
                    timeout=(10, 30)
                )

            print(f"[Kortyapay Payout] Status Response ({response.status_code}): {response.text}")

            if response.status_code != 200:
                return {
                    'success': False,
                    'message': f'Status check failed ({response.status_code}): {response.text}'
                }

            resp_json = response.json()
            is_status = resp_json.get('status', False)
            data = resp_json.get('data', {})
            if not isinstance(data, dict):
                data = {}

            if is_status is True or str(is_status).lower() in ['true', 'success', 'ok', '1']:
                api_status = str(data.get('status', 'PENDING')).upper()
                rrn = data.get('rrn', '')
                txn_id = data.get('txn_id', merchant_order_id)
                amount = data.get('amount', 0)
                charges = data.get('charges', 0)
                created_at = data.get('created_at', '')

                mapped_status = 'INITIATED'
                if api_status in ['SUCCESS', 'SUCCESSFUL', 'COMPLETED', 'TRUE']:
                    mapped_status = 'SUCCESS'
                elif api_status in ['FAILED', 'FAILURE', 'REJECTED', 'FALSE']:
                    mapped_status = 'FAILED'
                elif api_status in ['PENDING', 'INITIATED', 'PROCESSING', 'IN_PROCESS', 'QUEUED']:
                    mapped_status = 'INITIATED'

                return {
                    'success': True,
                    'status': mapped_status,
                    'merchant_order_id': merchant_order_id,
                    'pg_txn_id': txn_id,
                    'utr': rrn,
                    'amount': float(amount) if amount else 0,
                    'charges': charges,
                    'created_at': created_at,
                    'message': 'Status retrieved successfully',
                    'data': resp_json
                }
            else:
                return {
                    'success': False,
                    'message': resp_json.get('message', 'Status check unsuccessful'),
                    'data': resp_json
                }

        except Exception as e:
            print(f"[Kortyapay Payout] Check status error: {e}")
            return {
                'success': False,
                'message': f'Status check error: {str(e)}'
            }


# Create singleton instance
kortyapay_payout_service = KortyapayPayoutService()
