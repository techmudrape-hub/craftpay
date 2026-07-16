"""
Alopna Payment Gateway Integration Service
Handles payin and payout transactions through Alopna API
"""

import requests
import json
import os
import time
from datetime import datetime
from config import Config
from database import get_db_connection

class AlopnaService:
    def __init__(self):
        self.payin_base_url = Config.ALOPNA_PAYIN_BASE_URL
        self.payout_base_url = Config.ALOPNA_PAYOUT_BASE_URL
        self.payin_token = Config.ALOPNA_PAYIN_TOKEN
        self.client_id = Config.ALOPNA_CLIENT_ID
        self.client_secret = Config.ALOPNA_CLIENT_SECRET
        
        # Create session with connection pooling
        self.session = requests.Session()
        
        # Configure retry strategy
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=2,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["POST", "GET"],
            raise_on_status=False,
            respect_retry_after_header=True
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20,
            pool_block=False
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Token caching for payout
        self.payout_token = None
        self.payout_token_expiry = 0
    
    def calculate_charges(self, amount, scheme_id, service_type='PAYIN'):
        """Calculate charges based on scheme"""
        try:
            conn = get_db_connection()
            if not conn:
                return None, None, None
            
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT charge_value, charge_type
                    FROM commercial_charges
                    WHERE scheme_id = %s 
                    AND service_type = %s
                    AND %s BETWEEN min_amount AND max_amount
                    ORDER BY min_amount DESC
                    LIMIT 1
                """, (scheme_id, service_type, amount))
                
                charge_config = cursor.fetchone()
                
                if not charge_config:
                    return 0.00, amount, 'FIXED'
                
                charge_type = charge_config['charge_type']
                charge_value = float(charge_config['charge_value'])
                
                if charge_type == 'PERCENTAGE':
                    charge_amount = (amount * charge_value) / 100
                else:
                    charge_amount = charge_value
                
                net_amount = amount - charge_amount
                
                return round(charge_amount, 2), round(net_amount, 2), charge_type
                
        except Exception as e:
            print(f"Calculate charges error: {e}")
            return None, None, None
        finally:
            if conn:
                conn.close()
    
    def create_payin_order(self, merchant_id, order_data):
        """
        Create payin order via Alopna
        """
        try:
            start_time = time.time()
            
            conn = get_db_connection()
            if not conn:
                return {'success': False, 'message': 'Database connection failed'}
            
            with conn.cursor() as cursor:
                # Get merchant details
                cursor.execute("""
                    SELECT merchant_id, full_name, email, scheme_id, is_active
                    FROM merchants
                    WHERE merchant_id = %s
                """, (merchant_id,))
                
                merchant = cursor.fetchone()
                
                if not merchant:
                    return {'success': False, 'message': 'Merchant not found'}
                
                if not merchant['is_active']:
                    return {'success': False, 'message': 'Merchant account is inactive'}
                
                amount = float(order_data.get('amount', 0))
                
                # Calculate charges
                charge_amount, net_amount, charge_type = self.calculate_charges(
                    amount, merchant['scheme_id'], service_type='PAYIN'
                )
                
                if charge_amount is None:
                    return {'success': False, 'message': 'Failed to calculate charges'}
                
                # Generate unique merchant order ID
                merchant_order_id = order_data.get('orderid') or f"ALOPNA_{merchant_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Create internal transaction ID
                txn_id = f"ALOPNA_{merchant_id}_{merchant_order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Prepare customer data
                first_name = order_data.get('payee_fname', 'Customer')
                last_name = order_data.get('payee_lname', '')
                customer_mobile = order_data.get('payee_mobile', '9999999999')
                customer_email = order_data.get('payee_email', merchant['email'])
                remark = order_data.get('productinfo', 'Payment')
                
                # Get redirect URL
                redirect_url = order_data.get('callbackurl') or order_data.get('callback_url')
                if not redirect_url:
                    base_url = os.getenv('BACKEND_URL', 'https://api.craftpay.in')
                    redirect_url = f"{base_url}/api/callback/alopna/payin"
                
                # Prepare payload
                payload = {
                    "request_id": merchant_order_id,
                    "amount": amount,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": customer_email,
                    "mobile": customer_mobile,
                    "remark": remark,
                    "return_url": redirect_url
                }
                
                headers = {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'token': self.payin_token
                }
                
                url = f"{self.payin_base_url}/payment/initiate"
                
                print(f"[Alopna PayIn] Sending request to: {url}")
                print(f"[Alopna PayIn] Payload: {payload}")
                
                api_start = time.time()
                
                try:
                    response = self.session.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=(15, 60)
                    )
                    
                    api_elapsed = time.time() - api_start
                    print(f"[Alopna PayIn] API Response Time: {api_elapsed:.2f}s")
                    print(f"[Alopna PayIn] Response Status: {response.status_code}")
                    print(f"[Alopna PayIn] Response: {response.text[:500]}")
                    
                except requests.exceptions.Timeout:
                    return {'success': False, 'message': 'Payment gateway timeout', 'error_type': 'TIMEOUT'}
                except requests.exceptions.ConnectionError:
                    return {'success': False, 'message': 'Unable to connect to gateway', 'error_type': 'CONNECTION_ERROR'}
                
                if response.status_code not in [200, 201]:
                    return {'success': False, 'message': f'Alopna API error: {response.text}'}
                
                response_json = response.json()
                
                if response_json.get('status') != 'success':
                    error_msg = response_json.get('message', 'Payment initiation failed')
                    return {'success': False, 'message': error_msg}
                
                data = response_json.get('data', {})
                pg_txn_id = data.get('transaction_id', '')
                alopna_order_id = data.get('order_id', '')
                
                # Mapping UPI link and payment link
                upi_link_val = data.get('upi_link', '')
                payment_link_val = data.get('payment_link', '')
                qr_code = data.get('qr_code', '')
                
                # Insert transaction record
                cursor.execute("""
                    INSERT INTO payin_transactions (
                        txn_id, merchant_id, order_id, amount, charge_amount, 
                        charge_type, net_amount, payee_name, payee_email, 
                        payee_mobile, product_info, status, pg_partner,
                        pg_txn_id, callback_url, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                    )
                """, (
                    txn_id, merchant_id, merchant_order_id, amount,
                    charge_amount, charge_type, net_amount,
                    f"{first_name} {last_name}".strip(), customer_email, customer_mobile,
                    remark, 'INITIATED', 'ALOPNA', pg_txn_id,
                    redirect_url
                ))
                
                conn.commit()
                
                return {
                    'success': True,
                    'txn_id': txn_id,
                    'order_id': merchant_order_id,
                    'merchant_order_id': merchant_order_id,
                    'amount': amount,
                    'charge_amount': charge_amount,
                    'net_amount': net_amount,
                    'upi_link': upi_link_val,
                    'intent_url': upi_link_val,
                    'qr_string': upi_link_val,
                    'qr_code_url': qr_code,
                    'payment_link': payment_link_val,
                    'pg_partner': 'ALOPNA'
                }
                
        except Exception as e:
            print(f"[Alopna PayIn] ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'Internal error: {str(e)}'}
        finally:
            if conn:
                conn.close()
                
    def _get_payout_auth_token(self):
        """Generate and cache auth token for payout"""
        # Return cached token if still valid (assuming 1 hour expiry)
        if self.payout_token and time.time() < self.payout_token_expiry:
            return self.payout_token
            
        try:
            url = f"{self.payout_base_url}/auth/token/create"
            headers = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'Content-Type': 'application/json'
            }
            payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
            
            response = self.session.post(url, headers=headers, json=payload, timeout=10)
            
            if response.status_code == 200:
                resp_json = response.json()
                if resp_json.get('status') is True and 'data' in resp_json:
                    token = resp_json['data'].get('token')
                    if token:
                        self.payout_token = token
                        self.payout_token_expiry = time.time() + 3000 # Cache for ~50 minutes
                        return token
                print(f"[Alopna Auth] Missing token in response: {response.text}")
            else:
                print(f"[Alopna Auth] Failed to generate token: {response.text}")
                
            return None
        except Exception as e:
            print(f"[Alopna Auth] Error: {e}")
            return None

    def call_payout_api(self, account_number, ifsc_code, bank_name, merchant_order_id, amount, payee_name, email, mobile, mode='IMPS'):
        """
        Call Alopna Payout API directly.
        Returns:
            dict: {
                'success': bool,
                'status': str ('SUCCESS', 'FAILED', 'INITIATED'),
                'alopna_txn_id': str,
                'utr': str,
                'message': str
            }
        """
        try:
            token = self._get_payout_auth_token()
            if not token:
                return {'success': False, 'message': 'Failed to generate authentication token'}
                
            url = f"{self.payout_base_url}/kgpe/transaction"
            
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}'
            }
            
            payload = {
                "request_id": merchant_order_id,
                "account_number": account_number,
                "ifsc": ifsc_code,
                "name": payee_name,
                "amount": float(amount),
                "remarks": "Payout",
                "mode": mode,
                "mobile": mobile
            }
            
            print(f"[Alopna Payout] Sending request to {url}")
            
            response = self.session.post(
                url,
                headers=headers,
                json=payload,
                timeout=(10, 60)
            )
            
            print(f"[Alopna Payout] Response code: {response.status_code}")
            print(f"[Alopna Payout] Response body: {response.text}")
            
            if response.status_code in [200, 201]:
                resp_data = response.json()
                
                api_status = resp_data.get('status', '').lower()
                
                # Map status
                status = 'INITIATED'
                if api_status == 'success':
                    status = 'SUCCESS'
                elif api_status == 'failed':
                    status = 'FAILED'
                elif api_status == 'pending':
                    status = 'INITIATED'
                    
                alopna_txn_id = resp_data.get('transaction_id') or resp_data.get('txn_id') or ''
                utr = resp_data.get('utr') or resp_data.get('bank_ref_no') or ''
                message = resp_data.get('message', 'Payout initiated')
                
                return {
                    'success': True,
                    'status': status,
                    'alopna_txn_id': alopna_txn_id,
                    'utr': utr,
                    'message': message,
                    'raw_response': resp_data
                }
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', f'API Error: {response.status_code}')
                except:
                    error_msg = f'API Error: {response.status_code} - {response.text}'
                    
                return {
                    'success': False,
                    'message': error_msg,
                    'status': 'FAILED'
                }
                
        except requests.exceptions.Timeout:
            return {'success': False, 'message': 'Payment gateway timeout', 'status': 'INITIATED'}
        except Exception as e:
            print(f"[Alopna Payout] Exception: {str(e)}")
            return {'success': False, 'message': f'Internal Error: {str(e)}', 'status': 'FAILED'}

alopna_service = AlopnaService()
