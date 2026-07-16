"""
OQPay Payout Service
Handles payout transactions through OQPay
"""

import requests
import json
import time
from config import Config
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from database import get_db_connection

class OQPayPayoutService:
    def __init__(self):
        """
        Initialize OQPay Payout Service
        """
        self.service_provider = 'OQPAY'
        self.base_url = Config.OQPAY_PAYOUT_BASE_URL
        self.registration_id = Config.OQPAY_REGISTRATION_ID
        
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
        Get request headers for OQPay API
        """
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def call_payout_api(self, account_number, ifsc_code, bank_name, merchant_order_id,
                        amount, payee_name, email, mobile, mode='IMPS'):
        """
        Call OQPay payout API

        Args:
            account_number: Beneficiary bank account number
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
            print(f"[OQPAY Payout] Creating payout:")
            print(f"  Merchant Order ID: {merchant_order_id}")
            print(f"  Amount: {amount}")
            print(f"  Payee: {payee_name}")
            print(f"  Account: {account_number}")
            print(f"  IFSC: {ifsc_code}")
            print(f"  Mode: {mode}")

            # Prepare request payload (JSON)
            payload = {
                "accountNumber": str(account_number).strip(),
                "amount": f"{float(amount):.2f}",
                "transactionType": "IMPS" if str(mode).upper() == "IMPS" else "NEFT",
                "beneficiaryIFSC": str(ifsc_code).upper().strip(),
                "beneficiaryName": str(payee_name).strip(),
                "emailID": str(email).strip() if email else "abc@gmail.com",
                "mobileNo": str(mobile).strip() if mobile else "995964XXXX",
                "registrationID": self.registration_id
            }

            url = f"{self.base_url}/api/V6/Payout/OQPayout"

            print(f"[OQPAY Payout] Calling API: {url}")
            print(f"[OQPAY Payout] Payload (hidden registration ID): {json.dumps({**payload, 'registrationID': '***'}, indent=2)}")

            # Make API call
            response = self.session.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=(10, 60)
            )

            print(f"[OQPAY Payout] Response Status: {response.status_code}")
            print(f"[OQPAY Payout] Response: {response.text}")

            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'OQPay Payout API error: {response.text}'
                }

            oqpay_response = response.json()

            # Handle parsing OQPay Response JSON.
            # OQPay response has "statuss": "SUCCESS" at the root level.
            # And nested: initiateAuthGenericFundTransferAPIResp -> metaData -> status: "SUCCESS"
            root_status = oqpay_response.get('statuss', '').upper()
            
            nested_resp = oqpay_response.get('initiateAuthGenericFundTransferAPIResp', {})
            metadata = nested_resp.get('metaData', {})
            metadata_status = metadata.get('status', '').upper()
            
            resource_data = nested_resp.get('resourceData', {})
            resource_status = resource_data.get('status', '').upper() # ACPT, etc.
            
            is_successful = (root_status == 'SUCCESS') or (metadata_status == 'SUCCESS')

            if not is_successful:
                error_msg = oqpay_response.get('message') or metadata.get('message') or 'Payout execution failed'
                print(f"[OQPAY Payout] Failed: {error_msg}")
                return {
                    'success': False,
                    'message': error_msg
                }

            # Map the transaction status.
            # Resource status: ACPT usually means Accepted / Initiated.
            if resource_status == 'ACPT':
                mapped_status = 'INITIATED'
            elif resource_status == 'SUCCESS' or root_status == 'SUCCESS':
                # If transaction is successful immediately
                mapped_status = 'SUCCESS'
            elif resource_status == 'FAILED' or resource_status == 'REJ':
                mapped_status = 'FAILED'
            else:
                mapped_status = 'INITIATED'

            # OQPay payout identifiers
            # transactionReferenceNo: bank reference/UTR or query ID
            # transactionID: OQPay's internal transaction ID
            utr = resource_data.get('transactionReferenceNo', '')
            pg_txn_id = resource_data.get('transactionID', '')

            return {
                'success': True,
                'status': mapped_status,
                'merchant_order_id': merchant_order_id,
                'pg_txn_id': pg_txn_id,
                'amount': amount,
                'charge': '0',
                'gst': '0',
                'total_debit_amount': str(amount),
                'utr': utr,
                'message': oqpay_response.get('message') or metadata.get('message') or 'Payout initiated successfully',
                'data': oqpay_response
            }

        except requests.exceptions.Timeout as e:
            print(f"[OQPAY Payout] API call timeout error: {e}")
            return {
                'success': False,
                'message': 'Payout gateway timeout. Please try again or check transaction status after a few minutes.'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[OQPAY Payout] API call connection error: {e}")
            return {
                'success': False,
                'message': 'Unable to connect to payout gateway. Please try again later.'
            }
        except Exception as e:
            print(f"[OQPAY Payout] API call error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'API call error: {str(e)}'
            }

    def check_payout_status(self, merchant_order_id):
        """
        Check payout status on OQPay.
        Since OQPay does not document a status query API for payout in the provided docs,
        we fetch the status from local database records.
        """
        try:
            print(f"[OQPAY Payout] Checking status locally - merchant_order_id: {merchant_order_id}")

            conn = get_db_connection()
            if not conn:
                return {'success': False, 'message': 'Database connection failed'}

            try:
                with conn.cursor() as cursor:
                    # Query by merchant_order_id (matching reference_id or order_id)
                    cursor.execute("""
                        SELECT status, utr, amount
                        FROM payout_transactions
                        WHERE (reference_id = %s OR order_id = %s OR pg_txn_id = %s) AND pg_partner = 'OQPAY'
                        LIMIT 1
                    """, (merchant_order_id, merchant_order_id, merchant_order_id))

                    txn = cursor.fetchone()
                    if txn:
                        return {
                            'success': True,
                            'status': txn['status'],
                            'amount': float(txn['amount']),
                            'utr': txn.get('utr', ''),
                            'message': 'Status retrieved from local database'
                        }
                    else:
                        return {
                            'success': False,
                            'message': 'Payout transaction not found locally'
                        }
            finally:
                conn.close()

        except Exception as e:
            print(f"[OQPAY Payout] Check status error: {e}")
            return {
                'success': False,
                'message': f'Status check error: {str(e)}'
            }

# Create singleton instance
oqpay_payout_service = OQPayPayoutService()

def get_payout_service():
    return oqpay_payout_service
