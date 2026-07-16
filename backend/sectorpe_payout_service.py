"""
SectorPe Payout Service
Handles payout transactions through SectorPe
Uses same credentials as SectorPe payin
"""

import requests
import json
import time
from config import Config
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class SectorPePayoutService:

    def __init__(self):
        """
        Initialize SectorPe Payout Service
        """
        self.service_provider = 'PES'
        self.base_url = Config.SECTORPE_BASE_URL
        self.token = Config.SECTORPE_TOKEN
        
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
        Get request headers for SectorPe API
        """
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def call_payout_api(self, account_number, ifsc_code, bank_name, merchant_order_id,
                        amount, payee_name, email, mobile, mode='IMPS'):
        """
        Call SectorPe payout API

        Args:
            account_number: Beneficiary account number
            ifsc_code: IFSC code
            bank_name: Bank name
            merchant_order_id: Unique merchant order ID
            amount: Payout amount
            payee_name: Account holder name
            email: Beneficiary email
            mobile: 10 digit mobile number
            mode: Payment mode (IMPS/NEFT/UPI)

        Returns:
            dict: API response with success status
        """
        try:
            print(f"[SECTORPE Payout] Creating payout:")
            print(f"  Merchant Order ID: {merchant_order_id}")
            print(f"  Amount: {amount}")
            print(f"  Payee: {payee_name}")
            print(f"  Account: {account_number}")
            print(f"  IFSC: {ifsc_code}")
            print(f"  Bank: {bank_name}")

            # Prepare request payload (JSON)
            payload = {
                "token": self.token,
                "amount": float(amount),
                "name": payee_name.strip(),
                "mobile": mobile.strip(),
                "bank": bank_name.strip(),
                "account": account_number.strip(),
                "ifsc": ifsc_code.upper().strip(),
                "holder": payee_name.strip(),
                "mode": mode.upper(),
                "txnid": merchant_order_id.strip()
            }

            # API endpoint
            url = f"{self.base_url}/routes/create_payout.php"

            print(f"[SECTORPE Payout] Calling API: {url}")
            print(f"[SECTORPE Payout] Payload (hidden token): {json.dumps({**payload, 'token': '***'}, indent=2)}")

            # Make API call
            response = self.session.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=(10, 60)
            )

            print(f"[SECTORPE Payout] Response Status: {response.status_code}")
            print(f"[SECTORPE Payout] Response: {response.text}")

            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'SectorPe API error: {response.text}'
                }

            sectorpe_response = response.json()

            # Check if API returned success based on status or error flag
            # Note: Checking docs, "status": "success" is standard. Let's assume error handling.
            status_val = sectorpe_response.get('status', '').lower()
            if status_val == 'error' or sectorpe_response.get('error') is True:
                error_msg = sectorpe_response.get('message', 'Payout creation failed')
                print(f"[SECTORPE Payout] Failed: {error_msg}")
                return {
                    'success': False,
                    'message': error_msg
                }

            # If response gives success, status is considered INITIATED, SUCCESS, QUEUED, etc.
            # We map success -> SUCCESS, pending -> INITIATED, failed -> FAILED
            if status_val == 'success':
                mapped_status = 'SUCCESS'
            elif status_val == 'pending':
                mapped_status = 'INITIATED'
            elif status_val == 'failed':
                mapped_status = 'FAILED'
            else:
                mapped_status = 'INITIATED'

            # SectorPe might return reference or bankutr.
            utr = sectorpe_response.get('bankutr', sectorpe_response.get('reference', sectorpe_response.get('utr', '')))
            
            return {
                'success': True,
                'status': mapped_status,
                'merchant_order_id': merchant_order_id,
                'amount': amount,
                'charge': '0',
                'gst': '0',
                'total_debit_amount': str(amount),
                'utr': utr,
                'message': sectorpe_response.get('message', 'Payout initiated successfully'),
                'data': sectorpe_response
            }

        except requests.exceptions.Timeout as e:
            print(f"[SECTORPE Payout] API call timeout error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Payout gateway timeout. Please try again or check transaction status after a few minutes.'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[SECTORPE Payout] API call connection error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Unable to connect to payout gateway. Please try again later.'
            }
        except Exception as e:
            print(f"[SECTORPE Payout] API call error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'API call error: {str(e)}'
            }

    def check_payout_status(self, merchant_order_id):
        """
        Check payout status on SectorPe

        Args:
            merchant_order_id: The merchant order ID

        Returns:
            dict: Status information
        """
        try:
            print(f"[SECTORPE Payout] Checking status - merchant_order_id: {merchant_order_id}")

            url = f"{self.base_url}/routes/get_order_status.php"

            payload = {
                'txnid': merchant_order_id,
                'type': 'payout',
                'token': self.token
            }

            print(f"[SECTORPE Payout] Status check payload: {payload}")

            response = self.session.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=(10, 60)
            )

            print(f"[SECTORPE Payout] Status Response: {response.status_code} - {response.text[:500]}")

            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'Status check failed: {response.text}'
                }

            sectorpe_response = response.json()

            # Check for error response
            if sectorpe_response.get('status') == 'error':
                return {
                    'success': False,
                    'message': sectorpe_response.get('message', 'Status check failed')
                }

            txn_status = sectorpe_response.get('txn_status', sectorpe_response.get('status', 'pending')).lower()

            if txn_status == 'success':
                mapped_status = 'SUCCESS'
            elif txn_status == 'failed':
                mapped_status = 'FAILED'
            else:
                mapped_status = 'INITIATED'

            utr = sectorpe_response.get('bankutr', sectorpe_response.get('utr', ''))
            amount = sectorpe_response.get('amount', '0')

            result = {
                'success': True,
                'status': mapped_status,
                'merchant_order_id': sectorpe_response.get('txnid', merchant_order_id),
                'amount': float(amount) if amount else 0,
                'charge': 0,
                'gst': 0,
                'utr': utr,
                'created_at': '',
                'message': sectorpe_response.get('message', 'Status retrieved successfully')
            }

            print(f"[SECTORPE Payout] Parsed Status: {result}")

            return result

        except requests.exceptions.Timeout as e:
            print(f"[SECTORPE Payout] Check status timeout error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Status check timeout. Please try again in a few moments.'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[SECTORPE Payout] Check status connection error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Unable to connect to payout gateway for status check.'
            }
        except Exception as e:
            print(f"[SECTORPE Payout] Check status error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'Status check error: {str(e)}'
            }


# Create singleton instance
sectorpe_payout_service = SectorPePayoutService()

def get_payout_service():
    return sectorpe_payout_service
