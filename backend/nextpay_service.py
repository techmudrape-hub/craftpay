"""
Nextpay Payment Gateway Integration Service
Handles payin transactions through Nextpay
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

class NextpayService:
    def __init__(self):
        self.base_url = Config.NEXTPAY_BASE_URL
        self.client_id = Config.NEXTPAY_CLIENT_ID
        self.api_secret = Config.NEXTPAY_API_SECRET
        
        # Create session with connection pooling and retry logic
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
    
    def generate_signature(self, data_to_sign):
        """
        Generate HMAC SHA256 signature for Nextpay API
        """
        # Sort keys alphabetically
        sorted_keys = sorted(data_to_sign.keys())
        
        # Build canonical string: key=value&key=value
        canonical_parts = []
        for key in sorted_keys:
            value = str(data_to_sign[key])
            canonical_parts.append(f"{key}={value}")
        
        canonical_string = "&".join(canonical_parts)
        
        # Generate HMAC SHA256 signature
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            canonical_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def get_headers(self, timestamp, request_id, signature):
        """
        Get request headers for Nextpay API
        """
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Client-ID': self.client_id,
            'X-Timestamp': str(timestamp),
            'X-Request-ID': request_id,
            'X-Signature': signature
        }
        return headers
    
    def generate_request_id(self):
        """Generate unique request id"""
        return f"REQ_{uuid.uuid4().hex[:12].upper()}"
    
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
        Create payin order via Nextpay
        """
        try:
            start_time = time.time()
            
            conn = get_db_connection()
            if not conn:
                return {'success': False, 'message': 'Database connection failed'}
            
            with conn.cursor() as cursor:
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
                if amount <= 0:
                    return {'success': False, 'message': 'Invalid amount'}
                
                charge_amount, net_amount, charge_type = self.calculate_charges(
                    amount, merchant['scheme_id']
                )
                
                if charge_amount is None:
                    return {'success': False, 'message': 'Failed to calculate charges'}
                
                merchant_order_id = order_data.get('orderid') or f"NXTP_{merchant_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                txn_id = f"NXTP_{merchant_id}_{merchant_order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                customer_name = f"{order_data.get('payee_fname', '')} {order_data.get('payee_lname', '')}".strip()
                customer_mobile = order_data.get('payee_mobile', '')
                customer_email = order_data.get('payee_email', '')
                
                if not customer_name:
                    return {'success': False, 'message': 'Customer name is required'}
                if not customer_mobile or len(customer_mobile) != 10:
                    return {'success': False, 'message': 'Valid 10-digit mobile number is required'}
                if not customer_email:
                    # Provide default email if missing, although Nextpay says optional, good to have
                    customer_email = merchant['email']
                
                # Extract callback URL
                callback_url = order_data.get('callbackurl') or order_data.get('callback_url')
                if not callback_url:
                    base_url = os.getenv('BACKEND_URL', 'https://api.craftpay.in')
                    callback_url = f"{base_url}/api/callback/nextpay/payin"
                
                timestamp = int(time.time())
                request_id = self.generate_request_id()
                
                # Prepare payload
                payload = {
                    'amount': amount,
                    'customer_name': customer_name,
                    'customer_mobile': customer_mobile,
                    'customer_email': customer_email,
                    'remarks': order_data.get('productinfo', 'Payment'),
                    'client_order_id': merchant_order_id,
                    'return_url': callback_url
                }
                
                # Add headers details to signature payload if required (Assuming same logic as Payout doc)
                data_to_sign = payload.copy()
                data_to_sign['timestamp'] = str(timestamp)
                data_to_sign['request_id'] = request_id
                
                signature = self.generate_signature(data_to_sign)
                
                print(f"[Nextpay PayIn] Creating payment order for {merchant_order_id}")
                url = f"{self.base_url}/api/v1/payin/create"
                
                try:
                    response = self.session.post(
                        url,
                        headers=self.get_headers(timestamp, request_id, signature),
                        json=payload,
                        timeout=(15, 60)
                    )
                    
                    api_elapsed = time.time() - start_time
                    print(f"[Nextpay PayIn] API Response Time: {api_elapsed:.2f}s, Status: {response.status_code}")
                    
                except requests.exceptions.ReadTimeout:
                    # Handle timeout by saving as INITIATED
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
                        customer_name, customer_email, customer_mobile,
                        order_data.get('productinfo', 'Payment'),
                        'INITIATED', 'NEXTPAY', merchant_order_id,
                        callback_url
                    ))
                    
                    conn.commit()
                    return {
                        'success': False,
                        'message': 'Payment gateway timeout. Transaction saved as pending.',
                        'error_type': 'TIMEOUT',
                        'txn_id': txn_id,
                        'order_id': merchant_order_id
                    }
                
                if response.status_code not in [200, 201]:
                    error_msg = f'Nextpay API error: {response.text}'
                    print(error_msg)
                    return {'success': False, 'message': error_msg}
                
                nextpay_response = response.json()
                print(f"Nextpay Response: {nextpay_response}")
                
                if not nextpay_response.get('success'):
                    error_msg = nextpay_response.get('message', 'Payment order creation failed')
                    return {'success': False, 'message': error_msg}
                
                data = nextpay_response.get('data', {})
                pg_txn_id = data.get('transaction_id', merchant_order_id)
                intent_url = data.get('intent_url', '')
                payment_url = data.get('payment_url', '')
                
                if not payment_url and not intent_url:
                    return {'success': False, 'message': 'No payment link received from Nextpay'}
                
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
                    customer_name, customer_email, customer_mobile,
                    order_data.get('productinfo', 'Payment'),
                    'INITIATED', 'NEXTPAY', pg_txn_id,
                    callback_url
                ))
                
                conn.commit()
                
                # Use intent_url if available, else payment_url
                upi_link = intent_url if intent_url else payment_url
                
                return {
                    'success': True,
                    'txn_id': txn_id,
                    'order_id': merchant_order_id,
                    'merchant_order_id': merchant_order_id,
                    'amount': amount,
                    'charge_amount': charge_amount,
                    'net_amount': net_amount,
                    'upi_link': upi_link,
                    'intent_url': intent_url,
                    'payment_link': payment_url,
                    'qr_string': upi_link,
                    'pg_partner': 'NEXTPAY'
                }
                
        except Exception as e:
            print(f"[Nextpay PayIn] Error: {e}")
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
    
    def check_payment_status(self, pg_txn_id):
        """
        Check payment status on Nextpay using their transaction_id
        """
        try:
            url = f"{self.base_url}/api/v1/payin/status"
            
            timestamp = int(time.time())
            request_id = self.generate_request_id()
            
            payload = {
                'transaction_id': pg_txn_id
            }
            
            data_to_sign = payload.copy()
            data_to_sign['timestamp'] = str(timestamp)
            data_to_sign['request_id'] = request_id
            
            signature = self.generate_signature(data_to_sign)
            
            response = self.session.post(
                url,
                headers=self.get_headers(timestamp, request_id, signature),
                json=payload,
                timeout=(10, 30)
            )
            
            if response.status_code not in [200, 201]:
                return {'success': False, 'message': f'Status check failed: {response.text}'}
            
            nextpay_response = response.json()
            if not nextpay_response.get('success'):
                return {'success': False, 'message': nextpay_response.get('message', 'Status check failed')}
            
            data = nextpay_response.get('data', {})
            transaction_status = data.get('status', 'PENDING').lower()
            
            if transaction_status == 'success':
                mapped_status = 'SUCCESS'
            elif transaction_status in ['failed', 'failure']:
                mapped_status = 'FAILED'
            else:
                mapped_status = 'INITIATED'
                
            return {
                'success': True,
                'status': mapped_status,
                'merchant_order_id': data.get('client_order_id', ''),
                'pg_txn_id': data.get('transaction_id', pg_txn_id),
                'amount': float(data.get('amount', 0)),
                'utr': data.get('utr_number', ''),
                'created_at': data.get('created_at', ''),
                'message': nextpay_response.get('message', 'Success')
            }
            
        except Exception as e:
            print(f"Check payment status error: {e}")
            return {'success': False, 'message': f'Status check error: {str(e)}'}

# Create singleton instance
nextpay_service = NextpayService()
