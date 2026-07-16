"""
ClocksPay Payout Service
Handles payout transactions through ClocksPay
Uses same token as ClocksPay payin service
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import time
from datetime import datetime
from config import Config
from database import get_db_connection


class ClocksPayPayoutService:

    def __init__(self):
        """
        Initialize ClocksPay Payout Service
        Uses same token as ClocksPay payin service
        """
        self.base_url = Config.CLOCKSPAY_BASE_URL
        self.token = Config.CLOCKSPAY_TOKEN
        
        # Create a session with retry logic and connection pooling
        self.session = self._create_session_with_retries()
    
    def _create_session_with_retries(self):
        """
        Create a requests session with retry logic and connection pooling
        
        Returns:
            requests.Session: Configured session with retries
        """
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["POST", "GET"],
            raise_on_status=False
        )
        
        # Mount adapter with retry strategy
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
        Get request headers for ClocksPay API
        """
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        return headers

    def call_payout_api(self, account_number, ifsc_code, bank_name, merchant_order_id,
                        amount, payee_name, mobile, mode='IMPS'):
        """
        Call ClocksPay payout API

        Args:
            account_number: Beneficiary account number
            ifsc_code: IFSC code
            bank_name: Bank name
            merchant_order_id: Unique merchant order ID (txnid)
            amount: Payout amount
            payee_name: Account holder name
            mobile: 10 digit mobile number
            mode: Transfer mode (IMPS, NEFT, RTGS) - default IMPS

        Returns:
            dict: API response with success status
        """
        try:
            print(f"[ClocksPay Payout] Creating payout:")
            print(f"  Merchant Order ID: {merchant_order_id}")
            print(f"  Amount: {amount}")
            print(f"  Payee: {payee_name}")
            print(f"  Account: {account_number}")
            print(f"  IFSC: {ifsc_code}")
            print(f"  Bank: {bank_name}")
            print(f"  Mobile: {mobile}")
            print(f"  Mode: {mode}")

            # Prepare request payload as per ClocksPay API docs
            payload = {
                'token': self.token,
                'amount': int(amount),  # ClocksPay expects integer amount
                'name': payee_name.strip(),
                'mobile': mobile.strip(),
                'bank': bank_name.strip(),
                'account': account_number.strip(),
                'ifsc': ifsc_code.upper().strip(),
                'holder': payee_name.strip(),  # Account holder name
                'mode': mode.upper(),  # IMPS, NEFT, or RTGS
                'txnid': merchant_order_id.strip()
            }

            # API endpoint
            url = f"{self.base_url}/API/payout-request.php"

            print(f"[ClocksPay Payout] Calling API: {url}")
            print(f"[ClocksPay Payout] Payload: {json.dumps({**payload, 'token': '***'}, indent=2)}")

            # Make API call with retry logic and increased timeout
            response = self.session.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=(10, 60)  # (connect timeout, read timeout) in seconds
            )

            print(f"[ClocksPay Payout] Response Status: {response.status_code}")
            print(f"[ClocksPay Payout] Response: {response.text}")

            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'ClocksPay API error: {response.text}'
                }

            clockspay_response = response.json()

            # Check if API returned success
            # Success Response: {"status": "success", "message": "Payout request submitted"}
            # Pending Response: {"error": "Payout 200", "message": "..."} - This means payout is initiated/pending
            # Failed Response: {"status": "error", "message": "Invalid token"}
            
            status = clockspay_response.get('status', '').lower()
            message = clockspay_response.get('message', '')
            error = clockspay_response.get('error', '')

            # Check for "Payout 200" - this is actually a pending/initiated status, not an error
            if error and 'Payout 200' in error:
                print(f"[ClocksPay Payout] Payout initiated (Payout 200) - Message: {message}")
                return {
                    'success': True,
                    'status': 'INITIATED',  # Payout is pending
                    'merchant_order_id': merchant_order_id,
                    'amount': str(amount),
                    'message': message or 'Payout initiated successfully',
                    'data': clockspay_response
                }

            # Check for actual errors
            if status == 'error':
                error_msg = message or 'Payout creation failed'
                print(f"[ClocksPay Payout] Failed: {error_msg}")
                return {
                    'success': False,
                    'message': error_msg
                }

            # Success response
            if status == 'success':
                print(f"[ClocksPay Payout] Success - Message: {message}")
                return {
                    'success': True,
                    'status': 'INITIATED',  # Initial status
                    'merchant_order_id': merchant_order_id,
                    'amount': str(amount),
                    'message': message,
                    'data': clockspay_response
                }

            # Unknown response format - treat as initiated to wait for callback
            print(f"[ClocksPay Payout] Unknown response format, treating as INITIATED: {clockspay_response}")
            return {
                'success': True,
                'status': 'INITIATED',
                'merchant_order_id': merchant_order_id,
                'amount': str(amount),
                'message': message or 'Payout initiated, awaiting confirmation',
                'data': clockspay_response
            }

        except requests.exceptions.Timeout as e:
            print(f"[ClocksPay Payout] API call timeout error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Payout gateway timeout. Please try again or check transaction status after a few minutes.'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[ClocksPay Payout] API call connection error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Unable to connect to payout gateway. Please try again later.'
            }
        except Exception as e:
            print(f"[ClocksPay Payout] API call error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'API call error: {str(e)}'
            }

    def check_payout_status(self, merchant_order_id):
        """
        Check payout status on ClocksPay

        Args:
            merchant_order_id: The merchant order ID (txnid)

        Returns:
            dict: Status information
        """
        try:
            print(f"[ClocksPay Payout] Checking status - merchant_order_id: {merchant_order_id}")

            # Status endpoint
            url = f"{self.base_url}/API/order_status.php"

            # Prepare payload as per ClocksPay API docs
            payload = {
                'txnid': merchant_order_id,
                'type': 'payout',
                'token': self.token
            }

            print(f"[ClocksPay Payout] Status check payload: {json.dumps({**payload, 'token': '***'}, indent=2)}")

            # Use session with retry logic and increased timeout
            response = self.session.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=(10, 60)
            )

            print(f"[ClocksPay Payout] Status Response: {response.status_code} - {response.text[:500]}")

            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'Status check failed: {response.text}'
                }

            clockspay_response = response.json()

            # Check for error
            # Failed Response: {"status": "error", "message": "Invalid token"}
            if clockspay_response.get('status') == 'error':
                return {
                    'success': False,
                    'message': clockspay_response.get('message', 'Status check failed')
                }

            # Extract data from response
            # Success Response: {"statuscode": "TXN", "txn_status": "success", "txnid": "PY100002", "bankutr": "UTR654321"}
            # Pending Response: {"statuscode": "TXN", "txn_status": "pending", "txnid": "PY100002", "amount": "500"}
            
            txn_status = clockspay_response.get('txn_status', 'pending').lower()
            statuscode = clockspay_response.get('statuscode', '')

            # Map ClocksPay status to our status
            if txn_status == 'success':
                mapped_status = 'SUCCESS'
            elif txn_status == 'failed':
                mapped_status = 'FAILED'
            else:
                mapped_status = 'INITIATED'

            # Extract other details
            txnid = clockspay_response.get('txnid', merchant_order_id)
            amount = clockspay_response.get('amount', '0')
            utr = clockspay_response.get('bankutr', '')

            result = {
                'success': True,
                'status': mapped_status,
                'merchant_order_id': txnid,
                'amount': float(amount) if amount else 0,
                'utr': utr,
                'statuscode': statuscode,
                'message': 'Status retrieved successfully'
            }

            print(f"[ClocksPay Payout] Parsed Status: {result}")

            return result

        except requests.exceptions.Timeout as e:
            print(f"[ClocksPay Payout] Check status timeout error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Status check timeout. Please try again in a few moments.'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[ClocksPay Payout] Check status connection error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Unable to connect to payout gateway for status check.'
            }
        except Exception as e:
            print(f"[ClocksPay Payout] Check status error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'Status check error: {str(e)}'
            }


# Create singleton instance
clockspay_payout_service = ClocksPayPayoutService()
