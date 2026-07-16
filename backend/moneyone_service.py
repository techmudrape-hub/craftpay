"""
MoneyOne Payment Gateway Integration Service
Handles payin transactions through MoneyOne
"""

import requests
import json
import os
import threading
import time
from datetime import datetime
from config import Config
from database import get_db_connection
from utils import encrypt_aes, decrypt_aes
import random

class MoneyOneService:
    def __init__(self):
        self.base_url = Config.MONEYONE_BASE_URL
        self.merchant_id = Config.MONEYONE_MERCHANT_ID
        self.password = Config.MONEYONE_PASSWORD
        self.auth_key = Config.MONEYONE_AUTH_KEY
        self.module_secret = Config.MONEYONE_MODULE_SECRET
        self.aes_key = Config.MONEYONE_AES_KEY
        self.aes_iv = Config.MONEYONE_AES_IV
        self.token = None
        self.token_expiry = None
    
    def get_headers(self, include_auth=False):
        """Get request headers"""
        headers = {
            'X-Authorization-Key': self.auth_key,
            'X-Module-Secret': self.module_secret,
            'Content-Type': 'application/json'
        }
        
        if include_auth and self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        return headers
    
    def merchant_login(self):
        """Login to get authentication token - must be done for every payin request"""
        try:
            url = f"{self.base_url}/api/merchant/login"
            
            payload = {
                'merchantId': self.merchant_id,
                'password': self.password
            }
            
            print(f"MoneyOne: Logging in merchant {self.merchant_id}")
            
            response = requests.post(
                url,
                json=payload,
                timeout=30
            )
            
            print(f"MoneyOne Login Response: {response.status_code}")
            
            if response.status_code not in [200, 201]:
                return {'success': False, 'message': f'Login failed: {response.text}'}
            
            data = response.json()
            
            if not data.get('success'):
                return {'success': False, 'message': data.get('message', 'Login failed')}
            
            self.token = data.get('token')
            print(f"✓ MoneyOne login successful, token obtained")
            
            return {'success': True, 'token': self.token}
            
        except Exception as e:
            print(f"MoneyOne login error: {e}")
            return {'success': False, 'message': f'Login error: {str(e)}'}
    
    def generate_txn_id(self, merchant_id, order_id):
        """Generate unique transaction ID"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_part = str(random.randint(100000, 999999))
        return f"{timestamp}{random_part}"
    
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
        Create payin order via MoneyOne
        order_data should contain:
        - amount
        - orderid
        - payee_fname
        - payee_lname
        - payee_mobile
        - payee_email
        """
        try:
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
                
                # Validate amount
                amount = float(order_data.get('amount', 0))
                if amount <= 0:
                    return {'success': False, 'message': 'Invalid amount'}
                
                # Calculate charges
                charge_amount, net_amount, charge_type = self.calculate_charges(
                    amount, merchant['scheme_id']
                )
                
                if charge_amount is None:
                    return {'success': False, 'message': 'Failed to calculate charges'}
                
                # Generate unique order ID
                order_id = f"ORD{self.generate_txn_id(merchant_id, order_data.get('orderid'))}"
                
                # Create internal transaction ID
                txn_id = f"MONEYONE_{merchant_id}_{order_data.get('orderid')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Login to get token (required for every request)
                login_result = self.merchant_login()
                if not login_result['success']:
                    return login_result
                
                # Prepare callback URL
                callback_url = order_data.get('callbackurl') or order_data.get('callback_url')
                if not callback_url:
                    base_url = os.getenv('BACKEND_URL', 'https://api.craftpay.in')
                    callback_url = f"{base_url}/api/callback/moneyone/payin"
                    print(f"⚠ No callback URL provided, using default: {callback_url}")
                
                # Prepare order payload
                firstname = order_data.get('payee_fname', '')
                lastname = order_data.get('payee_lname', '')
                email = order_data.get('payee_email', '')
                phone = order_data.get('payee_mobile', '')
                
                payload = {
                    'amount': float(amount),
                    'orderid': order_id,
                    'payee_fname': firstname,
                    'payee_lname': lastname,
                    'payee_mobile': phone,
                    'payee_email': email,
                    'callbackurl': callback_url
                }
                
                # Encrypt payload using system's encrypt_aes
                encrypted_payload = encrypt_aes(json.dumps(payload), self.aes_key, self.aes_iv)
                
                if not encrypted_payload:
                    return {'success': False, 'message': 'Failed to encrypt payload'}
                
                print(f"Creating MoneyOne order for merchant {merchant_id}")
                print(f"Order ID: {order_id}, Amount: {amount}")
                
                # Create order on MoneyOne
                url = f"{self.base_url}/api/payin/order/create"
                
                response = requests.post(
                    url,
                    headers=self.get_headers(include_auth=True),
                    json={'data': encrypted_payload},
                    timeout=30
                )
                
                print(f"MoneyOne API Response Status: {response.status_code}")
                
                if response.status_code not in [200, 201]:
                    error_msg = f'MoneyOne API error: {response.text}'
                    print(error_msg)
                    return {'success': False, 'message': error_msg}
                
                # Decrypt response
                response_json = response.json()
                
                if not response_json.get('success'):
                    return {'success': False, 'message': response_json.get('message', 'Order creation failed')}
                
                encrypted_response = response_json.get('data')
                if not encrypted_response:
                    return {'success': False, 'message': 'No data in response'}
                
                # Decrypt response using system's decrypt_aes
                decrypted_response = decrypt_aes(encrypted_response, self.aes_key, self.aes_iv)
                
                if not decrypted_response:
                    return {'success': False, 'message': 'Failed to decrypt response'}
                
                moneyone_response = json.loads(decrypted_response)
                
                print(f"MoneyOne Response: {moneyone_response}")
                
                # Extract payment data from response
                # Check all possible fields for QR/UPI data
                qr_string = (moneyone_response.get('qr_string') or 
                           moneyone_response.get('qr_code_url') or '')
                
                upi_link = (moneyone_response.get('upi_link') or 
                          moneyone_response.get('payment_link') or 
                          moneyone_response.get('intent_url') or 
                          moneyone_response.get('tiny_url') or '')
                
                moneyone_txn_id = moneyone_response.get('txn_id', '')
                pg_partner = moneyone_response.get('pg_partner', 'MONEYONE')
                
                # Validate that we got payment data
                if not upi_link and not qr_string:
                    print(f"No payment link or QR string in response: {moneyone_response}")
                    return {'success': False, 'message': 'No payment link received from MoneyOne'}
                
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
                    txn_id, merchant_id, order_id, amount,
                    charge_amount, charge_type, net_amount,
                    f"{firstname} {lastname}".strip(), email, phone,
                    order_data.get('productinfo', 'Payment'),
                    'INITIATED', 'MoneyOne', moneyone_txn_id,
                    callback_url
                ))
                
                print(f"✓ Transaction created:")
                print(f"  - TXN ID: {txn_id}")
                print(f"  - Order ID: {order_id}")
                print(f"  - MoneyOne TXN ID: {moneyone_txn_id}")
                print(f"  - Callback URL: {callback_url}")
                
                conn.commit()
                
                # Schedule automatic status check after 60 seconds
                self.auto_check_status_after_delay(order_id, delay_seconds=60)
                print(f"✓ Scheduled automatic status check for {order_id} in 60 seconds")
                
                return {
                    'success': True,
                    'txn_id': txn_id,
                    'order_id': order_id,
                    'merchant_order_id': order_data.get('orderid'),
                    'amount': amount,
                    'charge_amount': charge_amount,
                    'net_amount': net_amount,
                    'qr_string': qr_string,
                    'upi_link': upi_link,
                    'payment_link': upi_link,
                    'intent_url': upi_link,
                    'moneyone_txn_id': moneyone_txn_id,
                    'pg_partner': pg_partner
                }
                
        except Exception as e:
            print(f"Create payin order error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'Internal error: {str(e)}'}
        finally:
            if conn:
                conn.close()
    
    def check_payment_status(self, identifier):
        """
        Check payment status on MoneyOne
        
        Args:
            identifier: Can be order_id or txn_id
        
        Returns:
            dict: Status information
        """
        try:
            # Login to get token
            login_result = self.merchant_login()
            if not login_result['success']:
                return login_result
            
            print(f"Checking MoneyOne payment status for: {identifier}")
            
            # Prepare request payload
            payload = {}
            
            # Determine if it's order_id or txn_id
            if identifier.startswith('ORD'):
                payload['order_id'] = identifier
            else:
                payload['txn_id'] = identifier
            
            # Encrypt payload using system's encrypt_aes
            encrypted_payload = encrypt_aes(json.dumps(payload), self.aes_key, self.aes_iv)
            
            if not encrypted_payload:
                return {'success': False, 'message': 'Failed to encrypt payload'}
            
            # Check status
            url = f"{self.base_url}/api/payin/verify-payment"
            
            response = requests.post(
                url,
                headers=self.get_headers(include_auth=True),
                json={'data': encrypted_payload},
                timeout=30
            )
            
            print(f"MoneyOne Status Response: {response.status_code}")
            
            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'Status check failed: {response.text}'
                }
            
            response_json = response.json()
            
            if not response_json.get('success'):
                return {
                    'success': False,
                    'message': response_json.get('message', 'Status check failed')
                }
            
            # Decrypt response
            encrypted_response = response_json.get('data')
            if not encrypted_response:
                return {'success': False, 'message': 'No data in response'}
            
            # Decrypt response using system's decrypt_aes
            decrypted_response = decrypt_aes(encrypted_response, self.aes_key, self.aes_iv)
            
            if not decrypted_response:
                return {'success': False, 'message': 'Failed to decrypt response'}
            
            status_data = json.loads(decrypted_response)
            
            print(f"MoneyOne Status Data: {status_data}")
            
            # Extract status
            status = status_data.get('status', 'INITIATED').upper()
            if status == 'PENDING':
                status = 'INITIATED'
            
            result = {
                'success': True,
                'status': status,
                'txnId': status_data.get('txn_id'),
                'order_id': status_data.get('order_id'),
                'amount': status_data.get('amount'),
                'utr': status_data.get('utr') or status_data.get('bank_ref_no'),
                'payment_mode': status_data.get('payment_mode', 'UPI'),
                'created_at': status_data.get('created_at'),
                'completed_at': status_data.get('completed_at'),
                'message': 'Status retrieved successfully'
            }
            
            return result
            
        except Exception as e:
            print(f"Check payment status error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'Status check error: {str(e)}'}
    
    def auto_check_status_after_delay(self, order_id, delay_seconds=60):
        """
        Automatically check payment status after a delay
        This ensures status gets updated even if callback fails
        """
        def check_status_task():
            try:
                print(f"[MoneyOne Auto Status Check] Waiting {delay_seconds} seconds before checking {order_id}...")
                time.sleep(delay_seconds)
                
                print(f"[MoneyOne Auto Status Check] Checking status for {order_id}...")
                
                conn = get_db_connection()
                if not conn:
                    print(f"[MoneyOne Auto Status Check] Database connection failed")
                    return
                
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            SELECT txn_id, order_id, merchant_id, status, pg_txn_id, net_amount, charge_amount
                            FROM payin_transactions
                            WHERE order_id = %s AND pg_partner = 'MoneyOne'
                        """, (order_id,))
                        
                        txn = cursor.fetchone()
                        
                        if not txn:
                            print(f"[MoneyOne Auto Status Check] Transaction not found: {order_id}")
                            return
                        
                        if txn['status'] not in ['INITIATED', 'PENDING']:
                            print(f"[MoneyOne Auto Status Check] Transaction already {txn['status']}, skipping")
                            return
                        
                        identifier = txn.get('pg_txn_id') or order_id
                        
                        print(f"[MoneyOne Auto Status Check] Checking with identifier: {identifier}")
                        
                        status_result = self.check_payment_status(identifier)
                        
                        if not status_result.get('success'):
                            print(f"[MoneyOne Auto Status Check] Status check failed: {status_result.get('message')}")
                            return
                        
                        new_status = status_result.get('status', '').upper()
                        print(f"[MoneyOne Auto Status Check] Status: {new_status}")
                        
                        if new_status == 'SUCCESS' and txn['status'] != 'SUCCESS':
                            print(f"[MoneyOne Auto Status Check] Updating {txn['txn_id']} to SUCCESS")
                            
                            cursor.execute("""
                                UPDATE payin_transactions
                                SET status = 'SUCCESS',
                                    bank_ref_no = %s,
                                    pg_txn_id = %s,
                                    payment_mode = 'UPI',
                                    completed_at = NOW(),
                                    updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status_result.get('utr'), status_result.get('txnId'), txn['txn_id']))
                            
                            # Check if wallet already credited
                            cursor.execute("""
                                SELECT COUNT(*) as count FROM merchant_wallet_transactions
                                WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                            """, (txn['txn_id'],))
                            
                            wallet_already_credited = cursor.fetchone()['count'] > 0
                            
                            if not wallet_already_credited:
                                from wallet_service import wallet_service as wallet_svc
                                wallet_result = wallet_svc.credit_unsettled_wallet(
                                    merchant_id=txn['merchant_id'],
                                    amount=float(txn['net_amount']),
                                    description=f"PayIn received (MoneyOne Auto) - {order_id}",
                                    reference_id=txn['txn_id']
                                )
                                
                                if wallet_result['success']:
                                    print(f"[MoneyOne Auto Status Check] ✓ Merchant wallet credited: ₹{txn['net_amount']}")
                                
                                admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                    admin_id='admin',
                                    amount=float(txn['charge_amount']),
                                    description=f"PayIn charge (MoneyOne Auto) - {order_id}",
                                    reference_id=txn['txn_id']
                                )
                                
                                if admin_wallet_result['success']:
                                    print(f"[MoneyOne Auto Status Check] ✓ Admin wallet credited: ₹{txn['charge_amount']}")
                            
                            conn.commit()
                            print(f"[MoneyOne Auto Status Check] ✓ Successfully updated to SUCCESS")
                        
                        elif new_status == 'FAILED' and txn['status'] != 'FAILED':
                            cursor.execute("""
                                UPDATE payin_transactions
                                SET status = 'FAILED',
                                    pg_txn_id = %s,
                                    completed_at = NOW(),
                                    updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status_result.get('txnId'), txn['txn_id']))
                            
                            conn.commit()
                            print(f"[MoneyOne Auto Status Check] ✓ Updated to FAILED")
                        
                finally:
                    conn.close()
                    
            except Exception as e:
                print(f"[MoneyOne Auto Status Check] Error: {e}")
                import traceback
                traceback.print_exc()
        
        thread = threading.Thread(target=check_status_task, daemon=True)
        thread.start()


# Create singleton instance
moneyone_service = MoneyOneService()
