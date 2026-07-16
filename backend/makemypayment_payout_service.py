"""
MakeMyPayment Payout Service
Handles payout transactions through MakeMyPayment
"""

import requests
import json
import base64
import uuid
from config import Config
from utils import encrypt_aes, decrypt_aes
from datetime import datetime

class MakeMyPaymentService:

    def __init__(self):
        # Configuration
        self.base_url = Config.MAKEMYPAYMENT_BASE_URL
        self.api_key = Config.MAKEMYPAYMENT_API_KEY
        self.api_secret = Config.MAKEMYPAYMENT_API_SECRET
        self.iv = "0g7H#8X2mTqjvLwR"

    def encrypt_payload(self, data):
        """
        Encrypt payload using AES-256-CBC with the API Secret as key and predefined IV
        """
        try:
            json_data = json.dumps(data)
            # encrypt_aes returns a base64 encoded string
            encrypted_b64 = encrypt_aes(json_data, self.api_secret, self.iv)
            return encrypted_b64
        except Exception as e:
            print(f"[MakeMyPayment] Encryption error: {e}")
            return None

    def decrypt_response(self, encrypted_data):
        """
        Decrypt response using AES-256-CBC
        """
        try:
            decrypted = decrypt_aes(encrypted_data, self.api_secret, self.iv)
            return json.loads(decrypted)
        except Exception as e:
            print(f"[MakeMyPayment] Decryption error: {e}")
            return None

    def get_headers(self, api_id):
        """
        Get required headers
        """
        return {
            'X-API-KEY': self.api_key,
            'X-API-SECRET': self.api_secret,
            'X-API-ID': api_id,
            'Content-Type': 'text/plain' # Payload is a base64 string
        }

    def get_balance(self):
        """
        Retrieve current balance
        Endpoint: P7X4K2
        """
        try:
            api_id = "P7X4K2"
            url = f"{self.base_url}/api/v2/payouts"
            
            payload = {}
            encrypted_payload = self.encrypt_payload(payload)
            
            if not encrypted_payload:
                return {'success': False, 'message': 'Failed to encrypt payload'}
                
            response = requests.post(
                url,
                headers=self.get_headers(api_id),
                data=encrypted_payload,
                timeout=(10, 30)
            )
            
            if response.status_code not in [200, 201]:
                return {'success': False, 'message': f'API error: HTTP {response.status_code}'}
                
            decrypted_resp = self.decrypt_response(response.text)
            if not decrypted_resp:
                return {'success': False, 'message': 'Failed to decrypt response'}
                
            if decrypted_resp.get('status'):
                return {
                    'success': True,
                    'data': decrypted_resp.get('data'),
                    'message': decrypted_resp.get('message')
                }
            else:
                return {
                    'success': False,
                    'message': decrypted_resp.get('message', 'Failed to get balance')
                }
                
        except requests.exceptions.Timeout:
            return {'success': False, 'message': 'Timeout connecting to MakeMyPayment'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def initiate_single_payout(self, merchant_reference_id, account_holder, account_number, 
                             ifsc_code, bank_name, mobile, amount, mode='imps', 
                             purpose='Payment', branch_name='', branch_code='', 
                             city='', beneficiary_address='', email='', state='', 
                             pincode='', narration=''):
        """
        Initiate Single Payout
        Endpoint: M9Q8R5
        """
        try:
            api_id = "M9Q8R5"
            url = f"{self.base_url}/api/v2/payouts"
            
            # Ensure beneficiary address is at least 5 characters for MakeMyPayment
            if not beneficiary_address or len(beneficiary_address) < 5:
                beneficiary_address = f"ADDR{uuid.uuid4().hex[:6]}"
            
            # Use default string values if empty for required fields to prevent validation errors
            payload = {
                'merchant_reference_id': merchant_reference_id,
                'account_holder': account_holder,
                'account_number': account_number,
                'ifsc_code': ifsc_code,
                'bank_name': bank_name,
                'branch_name': branch_name or 'NA',
                'branch_code': branch_code or 'NA',
                'mobile': mobile or '9999999999',
                'city': city or 'NA',
                'beneficiary_address': beneficiary_address,
                'amount': amount,
                'mode': mode.lower(),
                'purpose': purpose
            }
            
            # Optional fields
            if email:
                payload['email'] = email
            if state:
                payload['state'] = state
            if pincode:
                payload['pincode'] = pincode
            if narration:
                payload['narration'] = narration

            print(f"[MakeMyPayment] Payload before encryption: {json.dumps(payload)}")
            
            encrypted_payload = self.encrypt_payload(payload)
            if not encrypted_payload:
                return {'success': False, 'message': 'Failed to encrypt payload'}
                
            response = requests.post(
                url,
                headers=self.get_headers(api_id),
                data=encrypted_payload,
                timeout=(10, 60)
            )
            
            if response.status_code not in [200, 201]:
                return {'success': False, 'message': f'API error: HTTP {response.status_code}'}
                
            decrypted_resp = self.decrypt_response(response.text)
            if not decrypted_resp:
                return {'success': False, 'message': 'Failed to decrypt response'}
                
            print(f"[MakeMyPayment] Response: {json.dumps(decrypted_resp)}")
                
            if not decrypted_resp.get('status'):
                return {
                    'success': False,
                    'message': decrypted_resp.get('message', 'Payout failed')
                }
                
            data = decrypted_resp.get('data', {})
            raw_status = data.get('status')
            if raw_status is None:
                raw_status = data.get('transaction_status', 'processing')
                
            payout_status = str(raw_status).lower()
            
            if payout_status in ['success', 'successful', 'processed', 'settled', 'true', '1']:
                mapped_status = 'SUCCESS'
            elif payout_status in ['failed', 'failure', 'rejected', 'reversed', 'false', '0']:
                mapped_status = 'FAILED'
            else:
                remarks = str(data.get('remarks', '')).lower()
                if 'settled' in remarks or 'success' in remarks:
                    mapped_status = 'SUCCESS'
                elif 'failed' in remarks or 'rejected' in remarks:
                    mapped_status = 'FAILED'
                else:
                    mapped_status = 'INITIATED'
                
            return {
                'success': True,
                'status': mapped_status,
                'transaction_id': data.get('transaction_id', ''),
                'merchant_reference_id': data.get('merchant_reference_id', merchant_reference_id),
                'amount': data.get('amount', amount),
                'utr': str(data.get('utr', '')) if str(data.get('utr', '')).lower() not in ['none', 'null'] else '',
                'message': decrypted_resp.get('message', 'Payout initiated successfully'),
                'data': decrypted_resp
            }
            
        except requests.exceptions.Timeout:
            return {'success': False, 'message': 'Timeout connecting to MakeMyPayment'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def check_payout_status(self, merchant_reference_id=None, transaction_id=None):
        """
        Get Payout Status
        Uses H5C9V4 (by reference ID) or Z1D7P8 (by transaction ID)
        """
        try:
            url = f"{self.base_url}/api/v2/payouts"
            
            if transaction_id:
                api_id = "Z1D7P8"
                payload = {'transaction_id': transaction_id}
            elif merchant_reference_id:
                api_id = "H5C9V4"
                payload = {'merchant_reference_id': merchant_reference_id}
            else:
                return {'success': False, 'message': 'Must provide either merchant_reference_id or transaction_id'}
                
            encrypted_payload = self.encrypt_payload(payload)
            if not encrypted_payload:
                return {'success': False, 'message': 'Failed to encrypt payload'}
                
            response = requests.post(
                url,
                headers=self.get_headers(api_id),
                data=encrypted_payload,
                timeout=(10, 30)
            )
            
            if response.status_code not in [200, 201]:
                return {'success': False, 'message': f'API error: HTTP {response.status_code}'}
                
            decrypted_resp = self.decrypt_response(response.text)
            if not decrypted_resp:
                return {'success': False, 'message': 'Failed to decrypt response'}
                
            if not decrypted_resp.get('status'):
                return {
                    'success': False,
                    'message': decrypted_resp.get('message', 'Status check failed')
                }
                
            data = decrypted_resp.get('data', {})
            raw_status = data.get('status')
            if raw_status is None:
                raw_status = data.get('transaction_status', 'processing')
                
            payout_status = str(raw_status).lower()
            
            if payout_status in ['success', 'successful', 'processed', 'settled', 'true', '1']:
                mapped_status = 'SUCCESS'
            elif payout_status in ['failed', 'failure', 'rejected', 'reversed', 'false', '0']:
                mapped_status = 'FAILED'
            else:
                remarks = str(data.get('remarks', '')).lower()
                if 'settled' in remarks or 'success' in remarks:
                    mapped_status = 'SUCCESS'
                elif 'failed' in remarks or 'rejected' in remarks:
                    mapped_status = 'FAILED'
                else:
                    mapped_status = 'INITIATED'
                
            return {
                'success': True,
                'status': mapped_status,
                'transaction_id': data.get('transaction_id', ''),
                'merchant_reference_id': data.get('merchant_reference_id', ''),
                'amount': data.get('amount', '0'),
                'utr': str(data.get('utr', '')) if str(data.get('utr', '')).lower() not in ['none', 'null'] else '',
                'remarks': data.get('remarks', ''),
                'message': decrypted_resp.get('message', 'Status retrieved successfully'),
                'data': decrypted_resp
            }
            
        except requests.exceptions.Timeout:
            return {'success': False, 'message': 'Timeout connecting to MakeMyPayment'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

# Singleton instance
makemypayment_payout_service = MakeMyPaymentService()
