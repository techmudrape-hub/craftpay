"""
MaxPe Payout Service
Handles payout transactions through MaxPe
Uses same credentials as MaxPe payin
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import hmac
import hashlib
import time
import uuid
from datetime import datetime
from config import Config
from database import get_db_connection


class MaxPePayoutService:

    def __init__(self, service_provider='MAXPE'):
        """
        Initialize MaxPe/NodePay Payout Service
        
        Args:
            service_provider: 'MAXPE' or 'NODEPAY' - determines which credentials to use
        """
        self.service_provider = service_provider.upper()
        
        if self.service_provider == 'NODEPAY':
            # NodePay Configuration
            self.base_url = Config.NODEPAY_BASE_URL
            self.api_key = Config.NODEPAY_API_KEY
            self.api_secret = Config.NODEPAY_API_SECRET
            # NodePay doesn't use latitude/longitude
            self.latitude = None
            self.longitude = None
        else:
            # MaxPe Configuration (default)
            self.base_url = Config.MAXPE_BASE_URL
            self.api_key = Config.MAXPE_API_KEY
            self.api_secret = Config.MAXPE_API_SECRET
            # Fixed latitude and longitude as per MaxPe documentation
            self.latitude = "28.6139"
            self.longitude = "77.2090"
        
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
        # Retry on connection errors, timeouts, and 5xx server errors
        retry_strategy = Retry(
            total=3,  # Total number of retries
            backoff_factor=2,  # Wait 2s, 4s, 8s between retries
            status_forcelist=[500, 502, 503, 504],  # Retry on these HTTP status codes
            allowed_methods=["POST", "GET"],  # Retry POST and GET requests
            raise_on_status=False  # Don't raise exception on retry exhaustion
        )
        
        # Mount adapter with retry strategy
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,  # Number of connection pools
            pool_maxsize=20  # Max connections per pool
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session

    def generate_nonce(self):
        """Generate unique nonce for request (16 character hex)"""
        return uuid.uuid4().hex[:16]

    def generate_signature(self, data_to_sign):
        """
        Generate HMAC SHA256 signature for MaxPe/NodePay API
        Uses the SAME method as working payin service

        Args:
            data_to_sign: Dictionary containing fields to sign

        Returns:
            str: HMAC SHA256 signature
        """
        # Sort keys alphabetically (same as payin)
        sorted_keys = sorted(data_to_sign.keys())

        print(f"[{self.service_provider} Payout Signature] Sorted keys: {sorted_keys}")

        # Build canonical string: key=value&key=value (same as payin)
        canonical_parts = []
        for key in sorted_keys:
            value = str(data_to_sign[key])
            canonical_parts.append(f"{key}={value}")
            print(f"[{self.service_provider} Payout Signature]   {key}={value}")

        canonical_string = "&".join(canonical_parts)

        print(f"[{self.service_provider} Payout Signature] Canonical String: {canonical_string}")
        print(f"[{self.service_provider} Payout Signature] API Secret (first 10 chars): {self.api_secret[:10]}...")

        # Generate HMAC SHA256 signature (same as payin)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            canonical_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        print(f"[{self.service_provider} Payout Signature] Generated Signature: {signature}")

        return signature

    def get_headers(self, timestamp, nonce, signature):
        """
        Get request headers for MaxPe/NodePay API
        All requests require API key, timestamp, nonce, and signature
        NOTE: Do NOT set Content-Type here - let requests library set it for form data
        """
        headers = {
            'Accept': 'application/json',
            'X-API-KEY': self.api_key,
            'X-TIMESTAMP': str(timestamp),
            'X-NONCE': nonce,
            'X-SIGNATURE': signature
        }
        return headers

    def call_payout_api(self, account_number, ifsc_code, bank_name, merchant_order_id,
                        amount, payee_name, email, mobile):
        """
        Call MaxPe/NodePay payout API

        Args:
            account_number: Beneficiary account number
            ifsc_code: IFSC code
            bank_name: Bank name
            merchant_order_id: Unique merchant order ID
            amount: Payout amount
            payee_name: Account holder name
            email: Beneficiary email
            mobile: 10 digit mobile number

        Returns:
            dict: API response with success status
        """
        try:
            # Generate timestamp and nonce
            timestamp = int(time.time())
            nonce = self.generate_nonce()

            # Prepare data for signature
            # CRITICAL: Only these fields are included in signature (NOT latitude/longitude for MaxPe)
            # For NodePay, latitude/longitude are not used at all
            data_to_sign = {
                'merchant_order_id': merchant_order_id.strip(),
                'payee_name': payee_name.strip(),
                'payee_account_number': account_number.strip(),
                'ifsc': ifsc_code.upper().strip(),
                'bank': bank_name.upper().strip(),
                'amount': str(amount),
                'email': email.strip(),
                'mobile': mobile.strip(),
                'timestamp': str(timestamp),
                'nonce': nonce
            }

            print(f"[{self.service_provider} Payout] Data to sign (before sorting):")
            for key, value in data_to_sign.items():
                print(f"  {key}: {value}")

            # Generate signature
            signature = self.generate_signature(data_to_sign)

            print(f"[{self.service_provider} Payout] Creating payout:")
            print(f"  Service Provider: {self.service_provider}")
            print(f"  Merchant Order ID: {merchant_order_id}")
            print(f"  Amount: {amount}")
            print(f"  Payee: {payee_name}")
            print(f"  Account: {account_number}")
            print(f"  IFSC: {ifsc_code}")
            print(f"  Bank: {bank_name}")
            print(f"  Timestamp: {timestamp}")
            print(f"  Nonce: {nonce}")
            print(f"  Signature: {signature}")

            # Prepare request payload (form data as per cURL example)
            payload = {
                'merchant_order_id': merchant_order_id.strip(),
                'payee_name': payee_name.strip(),
                'payee_account_number': account_number.strip(),
                'ifsc': ifsc_code.upper().strip(),
                'bank': bank_name.upper().strip(),
                'amount': str(amount),
                'email': email.strip(),
                'mobile': mobile.strip()
            }

            # Add latitude/longitude only for MaxPe (not for NodePay)
            if self.service_provider == 'MAXPE' and self.latitude and self.longitude:
                payload['latitude'] = self.latitude
                payload['longitude'] = self.longitude

            # API endpoint
            url = f"{self.base_url}/api/prod/payout/create"

            print(f"[{self.service_provider} Payout] Calling API: {url}")
            print(f"[{self.service_provider} Payout] Payload: {json.dumps(payload, indent=2)}")

            # Make API call with form data, retry logic, and increased timeout
            response = self.session.post(
                url,
                headers=self.get_headers(timestamp, nonce, signature),
                data=payload,  # Use form data, not JSON
                timeout=(10, 60)  # (connect timeout, read timeout) in seconds
            )

            print(f"[{self.service_provider} Payout] Response Status: {response.status_code}")
            print(f"[{self.service_provider} Payout] Response: {response.text}")

            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'{self.service_provider} API error: {response.text}'
                }

            maxpe_response = response.json()

            # Check if API returned success
            if not maxpe_response.get('status'):
                error_msg = maxpe_response.get('message', 'Payout creation failed')
                print(f"[{self.service_provider} Payout] Failed: {error_msg}")
                return {
                    'success': False,
                    'message': error_msg
                }

            # Extract data from response
            data = maxpe_response.get('data', {})

            # Response format (same for both MaxPe and NodePay):
            # {
            #   "status": true,
            #   "message": "success",
            #   "data": {
            #     "merchant_order_id": "txn_00001",
            #     "amount": "510.00",
            #     "charge": "10.20",
            #     "gst": "1.84",
            #     "total_debit_amount": "522.04",
            #     "status": "INITIATED"
            #   }
            # }

            payout_status = data.get('status', 'INITIATED').upper()
            merchant_order_id_resp = data.get('merchant_order_id', merchant_order_id)
            amount_resp = data.get('amount', str(amount))
            charge = data.get('charge', '0')
            gst = data.get('gst', '0')
            total_debit = data.get('total_debit_amount', str(amount))

            print(f"[{self.service_provider} Payout] Success - Status: {payout_status}")
            print(f"  Amount: {amount_resp}")
            print(f"  Charge: {charge}")
            print(f"  GST: {gst}")
            print(f"  Total Debit: {total_debit}")

            # Map status to our status
            # Database ENUM: INITIATED, QUEUED, INPROCESS, SUCCESS, FAILED, REVERSED
            if payout_status == 'SUCCESS':
                mapped_status = 'SUCCESS'
            elif payout_status == 'FAILED':
                mapped_status = 'FAILED'
            elif payout_status == 'INITIATED':
                mapped_status = 'INITIATED'
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
                'message': maxpe_response.get('message', 'Payout initiated successfully'),
                'data': maxpe_response
            }

        except requests.exceptions.Timeout as e:
            print(f"[{self.service_provider} Payout] API call timeout error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Payout gateway timeout. Please try again or check transaction status after a few minutes.'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[{self.service_provider} Payout] API call connection error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Unable to connect to payout gateway. Please try again later.'
            }
        except Exception as e:
            print(f"[{self.service_provider} Payout] API call error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'API call error: {str(e)}'
            }

    def check_payout_status(self, merchant_order_id):
        """
        Check payout status on MaxPe/NodePay

        Args:
            merchant_order_id: The merchant order ID

        Returns:
            dict: Status information
        """
        try:
            print(f"[{self.service_provider} Payout] Checking status - merchant_order_id: {merchant_order_id}")

            # Status endpoint is the same for both MaxPe and NodePay
            if self.service_provider == 'NODEPAY':
                url = f"{self.base_url}/api/prod/payout/status"
            else:
                url = f"{self.base_url}/api/prod/payout1/status"

            # Status check uses form data and only requires X-API-KEY header
            headers = {
                'X-API-KEY': self.api_key
            }

            payload = {
                'merchant_order_id': merchant_order_id
            }

            print(f"[{self.service_provider} Payout] Status check payload: {payload}")

            # Use session with retry logic and increased timeout
            response = self.session.post(
                url,
                headers=headers,
                data=payload,  # Use form data
                timeout=(10, 60)  # (connect timeout, read timeout) in seconds
            )

            print(f"[{self.service_provider} Payout] Status Response: {response.status_code} - {response.text[:500]}")

            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'Status check failed: {response.text}'
                }

            maxpe_response = response.json()

            # Extract data from response
            if not maxpe_response.get('status'):
                return {
                    'success': False,
                    'message': maxpe_response.get('message', 'Status check failed')
                }

            data = maxpe_response.get('data', {})

            # Response format (same for both MaxPe and NodePay):
            # {
            #   "status": true,
            #   "message": "Payout details fetched successfully",
            #   "data": {
            #     "merchant_order_id": "txn_00001",
            #     "amount": "510.00",
            #     "charge": "10.20",
            #     "gst": "1.84",
            #     "utr": "609014729614",
            #     "transaction_status": "SUCCESS",
            #     "created_at": "2026-03-31 14:31:31"
            #   }
            # }

            transaction_status = data.get('transaction_status', 'PENDING').upper()

            # Map status to our status
            if transaction_status == 'SUCCESS':
                mapped_status = 'SUCCESS'
            elif transaction_status == 'FAILED':
                mapped_status = 'FAILED'
            else:
                mapped_status = 'INITIATED'

            # Extract other details
            merchant_order_id_resp = data.get('merchant_order_id', merchant_order_id)
            amount = data.get('amount', '0')
            charge = data.get('charge', '0')
            gst = data.get('gst', '0')
            utr = data.get('utr', '')
            created_at = data.get('created_at', '')

            result = {
                'success': True,
                'status': mapped_status,
                'merchant_order_id': merchant_order_id_resp,
                'amount': float(amount) if amount else 0,
                'charge': float(charge) if charge else 0,
                'gst': float(gst) if gst else 0,
                'utr': utr,
                'created_at': created_at,
                'message': maxpe_response.get('message', 'Status retrieved successfully')
            }

            print(f"[{self.service_provider} Payout] Parsed Status: {result}")

            return result

        except requests.exceptions.Timeout as e:
            print(f"[{self.service_provider} Payout] Check status timeout error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Status check timeout. Please try again in a few moments.'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[{self.service_provider} Payout] Check status connection error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'Unable to connect to payout gateway for status check.'
            }
        except Exception as e:
            print(f"[{self.service_provider} Payout] Check status error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'Status check error: {str(e)}'
            }


# Create singleton instances for both services
maxpe_payout_service = MaxPePayoutService('MAXPE')
nodepay_payout_service = MaxPePayoutService('NODEPAY')

def get_payout_service(service_provider='MAXPE'):
    """
    Get the appropriate payout service instance
    
    Args:
        service_provider: 'MAXPE' or 'NODEPAY'
    
    Returns:
        MaxPePayoutService: Configured service instance
    """
    if service_provider.upper() == 'NODEPAY':
        return nodepay_payout_service
    else:
        return maxpe_payout_service