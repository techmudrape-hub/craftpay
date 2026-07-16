"""
Tpipay Payout Service
Handles payout transactions through Tpipay
API Endpoint: https://banking.mytpipay.com/api/payout/v2/transfer-now
"""

import requests
import json
import time
import uuid
from config import Config
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class TpipayPayoutService:

    def __init__(self):
        """
        Initialize Tpipay Payout Service
        """
        self.service_provider = 'TPIPAY'
        self.base_url = Config.TPIPAY_BASE_URL
        self.api_token = Config.TPIPAY_API_TOKEN

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

    def get_headers(self):
        """
        Get request headers for Tpipay API
        """
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def generate_client_id(self):
        """Generate a unique client_id for each payout transaction"""
        timestamp = int(time.time())
        suffix = uuid.uuid4().hex[:8].upper()
        return f"TPI-{timestamp}-{suffix}"

    def call_payout_api(self, account_number, ifsc_code, bank_name,
                        merchant_order_id, amount, payee_name, email, mobile,
                        channel_id='2'):
        """
        Call Tpipay payout API

        Args:
            account_number (str): Beneficiary bank account number
            ifsc_code (str): IFSC code (exactly 11 chars)
            bank_name (str): Bank name (for reference only; not sent to API)
            merchant_order_id (str): Unique merchant order ID used as client_id
            amount (float): Transfer amount
            payee_name (str): Beneficiary full name (as per bank)
            email (str): User's email
            mobile (str): 10-digit mobile number (no +91)
            channel_id (str): '1' = NEFT, '2' = IMPS (default: IMPS)

        Returns:
            dict: Standardised response with success status
        """
        try:
            print(f"[TPIPAY Payout] Creating payout:")
            print(f"  Merchant Order ID: {merchant_order_id}")
            print(f"  Amount: {amount}")
            print(f"  Payee: {payee_name}")
            print(f"  Account: {account_number}")
            print(f"  IFSC: {ifsc_code}")
            print(f"  Mobile: {mobile}")
            print(f"  Email: {email}")
            print(f"  Channel: {channel_id} ({'IMPS' if channel_id == '2' else 'NEFT'})")

            # Prepare request payload per Tpipay docs
            payload = {
                "api_token": self.api_token,
                "mobile_number": str(mobile).strip()[:10],
                "email": str(email).strip(),
                "beneficiary_name": str(payee_name).strip(),
                "ifsc_code": str(ifsc_code).upper().strip(),
                "account_number": str(account_number).strip(),
                "amount": float(amount),
                "channel_id": str(channel_id),
                "client_id": str(merchant_order_id).strip()
            }

            url = f"{self.base_url}/api/payout/v2/transfer-now"

            print(f"[TPIPAY Payout] Calling API: {url}")
            # Log payload with token masked
            safe_payload = {**payload, 'api_token': '***'}
            print(f"[TPIPAY Payout] Payload: {json.dumps(safe_payload, indent=2)}")

            # Make API call
            response = self.session.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=(10, 60)
            )

            print(f"[TPIPAY Payout] Response Status: {response.status_code}")
            print(f"[TPIPAY Payout] Response: {response.text}")

            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'Tpipay API error (HTTP {response.status_code}): {response.text}'
                }

            tpipay_response = response.json()

            status_val = str(tpipay_response.get('status', '')).lower()
            payid = tpipay_response.get('payid', '')
            utr = tpipay_response.get('utr', '')
            message = tpipay_response.get('message', '')

            if status_val == 'failure':
                error_msg = message or 'Payout creation failed'
                print(f"[TPIPAY Payout] Failed: {error_msg}")
                return {
                    'success': False,
                    'message': error_msg
                }

            # Map Tpipay status -> internal status
            if status_val == 'success':
                mapped_status = 'SUCCESS'
            elif status_val == 'pending':
                # Final status will arrive via callback
                mapped_status = 'INITIATED'
            else:
                mapped_status = 'INITIATED'

            return {
                'success': True,
                'status': mapped_status,
                'merchant_order_id': merchant_order_id,
                'payid': payid,
                'amount': amount,
                'charge': '0',
                'gst': '0',
                'total_debit_amount': str(amount),
                'utr': utr,
                'message': message or 'Payout initiated successfully',
                'data': tpipay_response
            }

        except requests.exceptions.Timeout as e:
            print(f"[TPIPAY Payout] API call timeout error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Payout gateway timeout. Please try again or check transaction status after a few minutes.'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[TPIPAY Payout] API call connection error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Unable to connect to Tpipay payout gateway. Please try again later.'
            }
        except Exception as e:
            print(f"[TPIPAY Payout] API call error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'API call error: {str(e)}'
            }

    def check_payout_status(self, merchant_order_id):
        """
        Tpipay does not expose a separate status-check endpoint in the provided docs.
        Status updates are delivered via callback (webhook).
        This stub is kept for interface compatibility and returns INITIATED by default
        so the caller keeps the transaction in a pending state until the callback arrives.

        Args:
            merchant_order_id (str): The client_id used when initiating the payout

        Returns:
            dict: Stub status response
        """
        print(f"[TPIPAY Payout] check_payout_status called for: {merchant_order_id}")
        print("[TPIPAY Payout] No status-check endpoint in docs – relying on callback")
        return {
            'success': True,
            'status': 'INITIATED',
            'merchant_order_id': merchant_order_id,
            'amount': 0,
            'utr': '',
            'message': 'Status will be delivered via callback from Tpipay'
        }


# Singleton instance
tpipay_payout_service = TpipayPayoutService()


def get_payout_service():
    return tpipay_payout_service
