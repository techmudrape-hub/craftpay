"""
Shadvalpay Payment Gateway Integration Service
Handles payin transactions through Shadvalpay
"""

import requests
import json
import os
import threading
import time
import hmac
import hashlib
from datetime import datetime
from config import Config
from database import get_db_connection
import uuid
import jwt

class ShadvalpayService:
    def __init__(self):
        self.base_url = Config.SHADVALPAY_BASE_URL
        self.merchant_id = Config.SHADVALPAY_MERCHANT_ID
        self.shadval_key = Config.SHADVALPAY_KEY
        
        self.session = requests.Session()
        
    def generate_signature(self, plain_text):
        """
        Generate HMAC SHA256 signature for Shadvalpay API
        """
        signature = hmac.new(
            self.shadval_key.encode('utf-8'),
            plain_text.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def decrypt_response(self, encrypted_data):
        """
        Decrypt webhook/status response data using JWT HS256
        """
        try:
            decoded = jwt.decode(
                encrypted_data, 
                self.merchant_id, 
                algorithms=["HS256"]
            )
            return decoded
        except Exception as e:
            print(f"Error decrypting Shadvalpay data: {e}")
            return None

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
    
    def create_payin_order(self, internal_merchant_id, order_data):
        """
        Create payin order via Shadvalpay QR Intent
        """
        try:
            conn = get_db_connection()
            if not conn:
                return {'success': False, 'message': 'Database connection failed'}
            
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT merchant_id, full_name, email, scheme_id, is_active
                    FROM merchants
                    WHERE merchant_id = %s
                """, (internal_merchant_id,))
                
                merchant = cursor.fetchone()
                
                if not merchant:
                    return {'success': False, 'message': 'Merchant not found'}
                
                if not merchant['is_active']:
                    return {'success': False, 'message': 'Merchant account is inactive'}
                
                amount = float(order_data.get('amount', 0))
                if amount <= 0:
                    return {'success': False, 'message': 'Invalid amount'}
                
                charge_amount, net_amount, charge_type = self.calculate_charges(
                    amount, merchant['scheme_id']
                )
                
                if charge_amount is None:
                    return {'success': False, 'message': 'Failed to calculate charges'}
                
                merchant_order_id = order_data.get('orderid') or f"SHD_{internal_merchant_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                txn_id = f"SHD_{internal_merchant_id}_{merchant_order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                customer_name = f"{order_data.get('payee_fname', '')} {order_data.get('payee_lname', '')}".strip() or merchant['full_name']
                customer_mobile = order_data.get('payee_mobile', '9999999999')
                customer_email = order_data.get('payee_email', merchant['email'])
                remarks = order_data.get('productinfo', 'payment')
                
                amount_str = str(int(amount)) if amount.is_integer() else str(amount)
                
                # Plain Text Format : ShadvalKey + merchant_id + txn_amount + txn_unique_id + customer_name + email_address + mobile_number
                plain_text = f"{self.shadval_key}{self.merchant_id}{amount_str}{merchant_order_id}{customer_name}{customer_email}{customer_mobile}"
                signature = self.generate_signature(plain_text)
                
                payload = {
                    "merchant_id": self.merchant_id,
                    "txn_amount": amount_str,
                    "currency": "INR",
                    "txn_unique_id": merchant_order_id,
                    "customer_name": customer_name,
                    "email_address": customer_email,
                    "mobile_number": customer_mobile,
                    "remarks": remarks,
                    "device_os": "ANDROID"
                }
                
                headers = {
                    'Content-Type': 'application/json',
                    'authorization': self.shadval_key,
                    'payload': signature
                }
                
                url = f"{self.base_url}/payment_gateway/upi_intent"
                
                response = self.session.post(url, headers=headers, json=payload, timeout=30)
                
                if response.status_code not in [200, 201]:
                    return {'success': False, 'message': f'Shadvalpay API error: {response.text}'}
                
                shadval_response = response.json()
                
                if shadval_response.get('status') != 'SUCCESS':
                    error_msg = shadval_response.get('message', 'Payment order creation failed')
                    return {'success': False, 'message': error_msg}
                
                data = shadval_response.get('data', {})
                payment_id = data.get('payment_id')
                qr_intent = data.get('qr_intent', '')
                
                if not qr_intent:
                    return {'success': False, 'message': 'No intent URL received'}
                
                callback_url = order_data.get('callbackurl') or order_data.get('callback_url')
                if not callback_url:
                    base_url = os.getenv('BACKEND_URL', 'https://api.craftpay.in')
                    callback_url = f"{base_url}/api/callback/shadvalpay/payin"
                
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
                    txn_id, internal_merchant_id, merchant_order_id, amount,
                    charge_amount, charge_type, net_amount,
                    customer_name, customer_email, customer_mobile,
                    remarks, 'INITIATED', 'SHADVALPAY', payment_id,
                    callback_url
                ))
                
                conn.commit()
                
                # Auto status check
                self.auto_check_status_after_delay(merchant_order_id, payment_id, delay_seconds=60)
                self.auto_check_status_after_delay(merchant_order_id, payment_id, delay_seconds=120)
                self.auto_check_status_after_delay(merchant_order_id, payment_id, delay_seconds=300)
                
                return {
                    'success': True,
                    'txn_id': txn_id,
                    'order_id': merchant_order_id,
                    'merchant_order_id': merchant_order_id,
                    'amount': amount,
                    'charge_amount': charge_amount,
                    'net_amount': net_amount,
                    'upi_link': qr_intent,
                    'intent_url': qr_intent,
                    'qr_string': qr_intent,
                    'payment_link': qr_intent,
                    'pg_partner': 'SHADVALPAY'
                }
                
        except Exception as e:
            print(f"[Shadvalpay PayIn] ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False, 
                'message': f'Internal error: {str(e)}',
                'error_type': 'INTERNAL_ERROR'
            }
        finally:
            if conn:
                conn.close()

    def check_payment_status(self, merchant_order_id, payment_id):
        """
        Check payment status on Shadvalpay
        """
        try:
            unique_request_id = f"CHK_{uuid.uuid4().hex[:10]}"
            
            # Plain Text Format : ShadvalKey + merchant_id + unique_request_id + txn_unique_id + payment_id
            plain_text = f"{self.shadval_key}{self.merchant_id}{unique_request_id}{merchant_order_id}{payment_id}"
            signature = self.generate_signature(plain_text)
            
            payload = {
                "merchant_id": self.merchant_id,
                "unique_request_id": unique_request_id,
                "txn_unique_id": merchant_order_id,
                "payment_id": payment_id
            }
            
            headers = {
                'Content-Type': 'application/json',
                'authorization': self.shadval_key,
                'payload': signature
            }
            
            url = f"{self.base_url}/payment_gateway/get_invoice_status"
            
            response = self.session.post(url, headers=headers, json=payload, timeout=15)
            
            if response.status_code not in [200, 201]:
                return {'success': False, 'message': f'Status check failed: {response.text}'}
            
            shadval_response = response.json()
            
            if shadval_response.get('status') != 'SUCCESS':
                return {'success': False, 'message': shadval_response.get('message', 'Status check failed')}
            
            encrypted_data = shadval_response.get('data')
            if not encrypted_data:
                return {'success': False, 'message': 'No data in status response'}
                
            decrypted_data = self.decrypt_response(encrypted_data)
            
            if not decrypted_data:
                return {'success': False, 'message': 'Failed to decrypt status response'}
            
            transaction_status = decrypted_data.get('txn_status', 'FAILED').upper()
            
            mapped_status = 'INITIATED'
            if transaction_status == 'SUCCESS':
                mapped_status = 'SUCCESS'
            elif transaction_status == 'FAILED':
                mapped_status = 'FAILED'
                
            amount = decrypted_data.get('txn_amount', 0)
            utr = decrypted_data.get('bank_ref_num', '')
            
            return {
                'success': True,
                'status': mapped_status,
                'merchant_order_id': merchant_order_id,
                'amount': float(amount),
                'utr': utr,
                'message': shadval_response.get('message', 'Status retrieved successfully')
            }
            
        except Exception as e:
            print(f"Check payment status error: {e}")
            return {'success': False, 'message': f'Status check error: {str(e)}'}

    def auto_check_status_after_delay(self, merchant_order_id, payment_id, delay_seconds=60):
        def check_status_task():
            try:
                time.sleep(delay_seconds)
                conn = get_db_connection()
                if not conn: return
                
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            SELECT txn_id, order_id, merchant_id, status, pg_txn_id, net_amount, charge_amount
                            FROM payin_transactions
                            WHERE order_id = %s AND pg_partner = 'SHADVALPAY'
                        """, (merchant_order_id,))
                        
                        txn = cursor.fetchone()
                        if not txn or txn['status'] not in ['INITIATED', 'PENDING']:
                            return
                        
                        status_result = self.check_payment_status(merchant_order_id, payment_id)
                        
                        if not status_result.get('success'):
                            return
                        
                        pg_status = status_result.get('status', '').upper()
                        
                        if pg_status == 'SUCCESS' and txn['status'] != 'SUCCESS':
                            cursor.execute("""
                                UPDATE payin_transactions
                                SET status = 'SUCCESS',
                                    bank_ref_no = %s,
                                    payment_mode = 'UPI',
                                    completed_at = NOW(),
                                    updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status_result.get('utr'), txn['txn_id']))
                            
                            cursor.execute("""
                                SELECT COUNT(*) as count FROM merchant_wallet_transactions
                                WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                            """, (txn['txn_id'],))
                            
                            wallet_already_credited = cursor.fetchone()['count'] > 0
                            
                            if not wallet_already_credited:
                                from wallet_service import wallet_service as wallet_svc
                                wallet_svc.credit_unsettled_wallet(
                                    merchant_id=txn['merchant_id'],
                                    amount=float(txn['net_amount']),
                                    description=f"PayIn received (Shadval Auto) - {merchant_order_id}",
                                    reference_id=txn['txn_id']
                                )
                                
                                wallet_svc.credit_admin_unsettled_wallet(
                                    admin_id='admin',
                                    amount=float(txn['charge_amount']),
                                    description=f"PayIn charge (Shadval Auto) - {merchant_order_id}",
                                    reference_id=txn['txn_id']
                                )
                            conn.commit()
                        
                        elif pg_status == 'FAILED' and txn['status'] != 'FAILED':
                            cursor.execute("""
                                UPDATE payin_transactions
                                SET status = 'FAILED',
                                    completed_at = NOW(),
                                    updated_at = NOW()
                                WHERE txn_id = %s
                            """, (txn['txn_id'],))
                            conn.commit()
                            
                finally:
                    conn.close()
            except Exception as e:
                print(f"[Shadval Auto Status Check] Error: {e}")
                
        threading.Thread(target=check_status_task, daemon=True).start()

shadvalpay_service = ShadvalpayService()
