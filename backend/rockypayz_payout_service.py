"""
RockyPayz Payout Service
Handles payout transactions through RockyPayz
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import time
from datetime import datetime
from config import Config
from database import get_db_connection


class RockyPayzPayoutService:

    def __init__(self):
        """
        Initialize RockyPayz Payout Service
        """
        self.base_url = Config.ROCKYPAYZ_BASE_URL
        self.mid = Config.ROCKYPAYZ_MID
        self.api_key = Config.ROCKYPAYZ_API_KEY
        self.route = Config.ROCKYPAYZ_ROUTE  # Route for payout (typically 1)
        
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
        Get request headers for RockyPayz API
        """
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        return headers

    def call_payout_api(self, account_number, ifsc_code, bank_name, merchant_order_id,
                        amount, payee_name, mobile, remarks='Payout'):
        """
        Call RockyPayz payout API

        Args:
            account_number: Beneficiary account number
            ifsc_code: IFSC code
            bank_name: Bank name (not used in API but kept for consistency)
            merchant_order_id: Unique merchant order ID (ref_no)
            amount: Payout amount
            payee_name: Account holder name (customer_name)
            mobile: 10 digit mobile number (optional)
            remarks: Payout remarks (optional)

        Returns:
            dict: API response with success status
        """
        try:
            print(f"[RockyPayz Payout] Creating payout:")
            print(f"  Merchant Order ID: {merchant_order_id}")
            print(f"  Amount: {amount}")
            print(f"  Payee: {payee_name}")
            print(f"  Account: {account_number}")
            print(f"  IFSC: {ifsc_code}")
            print(f"  Mobile: {mobile}")
            print(f"  Remarks: {remarks}")

            # Prepare request payload as per RockyPayz API docs
            payload = {
                'mid': self.mid,
                'apikey': self.api_key,
                'route': self.route,
                'ref_no': merchant_order_id.strip(),  # Alphanumeric reference
                'amount': str(amount),
                'customer_name': payee_name.strip(),
                'account_number': account_number.strip(),
                'ifsc': ifsc_code.upper().strip(),
                'customer_mobile': mobile.strip() if mobile else '',
                'remarks': remarks.strip() if remarks else 'Payout'
            }

            # API endpoint
            url = f"{self.base_url}/api/v-secure-core/transfer"

            print(f"[RockyPayz Payout] Calling API: {url}")
            print(f"[RockyPayz Payout] Payload: {json.dumps({**payload, 'apikey': '***'}, indent=2)}")

            # Make API call with retry logic and increased timeout
            response = self.session.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=(10, 60)  # (connect timeout, read timeout) in seconds
            )

            print(f"[RockyPayz Payout] Response Status: {response.status_code}")
            print(f"[RockyPayz Payout] Response: {response.text}")

            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'RockyPayz API error: {response.text}'
                }

            rockypayz_response = response.json()

            # Check if API returned success
            # Success Response: {"statuscode": "TXN", "msg": "Payout initiated", "data": {...}}
            # Failed Response: {"statuscode": "ERR", "msg": "Error message"}
            
            statuscode = rockypayz_response.get('statuscode', '').upper()
            message = rockypayz_response.get('msg', '')
            data = rockypayz_response.get('data', {})

            # Check for errors
            if statuscode != 'TXN':
                error_msg = message or 'Payout creation failed'
                print(f"[RockyPayz Payout] Failed: {error_msg}")
                return {
                    'success': False,
                    'message': error_msg
                }

            # Extract data from response
            # Response format:
            # {
            #   "statuscode": "TXN",
            #   "msg": "Payout initiated",
            #   "data": {
            #     "TXN_Time": "2025-11-07 18:20:57",
            #     "TXN_ID": "abcxyz1615255",
            #     "Amount": 100,
            #     "Fees": 10.62,
            #     "UTR": "61201018xxx",
            #     "status": "success"
            #   }
            # }

            txn_time = data.get('TXN_Time', '')
            txn_id = data.get('TXN_ID', merchant_order_id)
            amount_resp = data.get('Amount', amount)
            fees = data.get('Fees', 0)
            utr = data.get('UTR', '')
            status = data.get('status', 'pending').lower()

            # Map status to our status
            # Database ENUM: INITIATED, QUEUED, INPROCESS, SUCCESS, FAILED, REVERSED
            if status == 'success':
                mapped_status = 'SUCCESS'
            elif status == 'failed':
                mapped_status = 'FAILED'
            elif status == 'pending':
                mapped_status = 'INITIATED'
            else:
                mapped_status = 'INITIATED'

            print(f"[RockyPayz Payout] Success - Status: {mapped_status}")
            print(f"  TXN Time: {txn_time}")
            print(f"  TXN ID: {txn_id}")
            print(f"  Amount: {amount_resp}")
            print(f"  Fees: {fees}")
            print(f"  UTR: {utr}")

            return {
                'success': True,
                'status': mapped_status,
                'merchant_order_id': merchant_order_id,
                'txn_id': txn_id,
                'amount': str(amount_resp),
                'fees': str(fees),
                'utr': utr,
                'txn_time': txn_time,
                'message': message,
                'data': rockypayz_response
            }

        except requests.exceptions.Timeout as e:
            print(f"[RockyPayz Payout] API call timeout error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Payout gateway timeout. Please try again or check transaction status after a few minutes.'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[RockyPayz Payout] API call connection error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Unable to connect to payout gateway. Please try again later.'
            }
        except Exception as e:
            print(f"[RockyPayz Payout] API call error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'API call error: {str(e)}'
            }

    def check_payout_status(self, merchant_order_id):
        """
        Check payout status on RockyPayz

        Args:
            merchant_order_id: The merchant order ID (client_txn_id)

        Returns:
            dict: Status information
        """
        try:
            print(f"[RockyPayz Payout] Checking status - merchant_order_id: {merchant_order_id}")

            # Status endpoint
            url = f"{self.base_url}/api/v1/check_order_status"

            # Prepare payload as per RockyPayz API docs
            payload = {
                'mid': self.mid,
                'apikey': self.api_key,
                'route': 0,  # Use 0 for payout status check
                'client_txn_id': merchant_order_id
            }

            print(f"[RockyPayz Payout] Status check payload: {json.dumps({**payload, 'apikey': '***'}, indent=2)}")

            # Use session with retry logic and increased timeout
            response = self.session.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=(10, 60)
            )

            print(f"[RockyPayz Payout] Status Response: {response.status_code} - {response.text[:500]}")

            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'Status check failed: {response.text}'
                }

            rockypayz_response = response.json()

            # Check for error
            # Failed Response: {"status": false, "msg": "Transaction not found"}
            if not rockypayz_response.get('status'):
                return {
                    'success': False,
                    'message': rockypayz_response.get('msg', 'Status check failed')
                }

            # Extract data from response
            # Success Response: 
            # {
            #   "status": true,
            #   "msg": "Transaction found",
            #   "data": {
            #     "TXN_Time": "2026-01-13 21:58:23",
            #     "TXN_ID": "Rckpy143",
            #     "Amount": 100,
            #     "UTR": "601321087819",
            #     "status": "success"
            #   }
            # }
            
            data = rockypayz_response.get('data', {})
            txn_status = data.get('status', 'pending').lower()

            # Map RockyPayz status to our status
            if txn_status == 'success':
                mapped_status = 'SUCCESS'
            elif txn_status == 'failed':
                mapped_status = 'FAILED'
            else:
                mapped_status = 'INITIATED'

            # Extract other details
            txn_time = data.get('TXN_Time', '')
            txn_id = data.get('TXN_ID', merchant_order_id)
            amount = data.get('Amount', 0)
            utr = data.get('UTR', '')

            result = {
                'success': True,
                'status': mapped_status,
                'merchant_order_id': merchant_order_id,
                'txn_id': txn_id,
                'amount': float(amount) if amount else 0,
                'utr': utr,
                'txn_time': txn_time,
                'message': 'Status retrieved successfully'
            }

            print(f"[RockyPayz Payout] Parsed Status: {result}")

            return result

        except requests.exceptions.Timeout as e:
            print(f"[RockyPayz Payout] Check status timeout error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Status check timeout. Please try again in a few moments.'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[RockyPayz Payout] Check status connection error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Unable to connect to payout gateway for status check.'
            }
        except Exception as e:
            print(f"[RockyPayz Payout] Check status error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'Status check error: {str(e)}'
            }


# Create singleton instance
rockypayz_payout_service = RockyPayzPayoutService()
