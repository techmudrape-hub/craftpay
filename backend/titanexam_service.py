"""
Titanexam Payment Gateway Integration Service
Handles payin transactions through Titanexam
"""

import requests
import json
import os
import threading
import time
from datetime import datetime
from config import Config
from database import get_db_connection
import base64

class TitanexamService:
    def __init__(self):
        self.base_url = Config.TITANEXAM_BASE_URL
        self.merchant_id = Config.TITANEXAM_MERCHANT_ID
        self.secret_key = Config.TITANEXAM_SECRET_KEY
        
        # Create session with connection pooling and retry logic
        self.session = requests.Session()
        
        # Configure retry strategy
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=2,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["POST", "PUT", "GET"],
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

    def get_auth_header(self):
        credentials = f"{self.merchant_id}:{self.secret_key}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        return {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/json'
        }

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
        Create payin order via Titanexam
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
                
                # Generate unique merchant order ID
                merchant_order_id = order_data.get('orderid') or f"TITAN_{merchant_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Create internal transaction ID
                txn_id = f"TITAN_{merchant_id}_{merchant_order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Prepare customer data
                customer_name = f"{order_data.get('payee_fname', '')} {order_data.get('payee_lname', '')}".strip()
                customer_mobile = order_data.get('payee_mobile', '')
                customer_email = order_data.get('payee_email', '')
                
                if not customer_name:
                    return {'success': False, 'message': 'Customer name is required'}
                if not customer_mobile or len(customer_mobile) != 10:
                    return {'success': False, 'message': 'Valid 10-digit mobile number is required'}
                
                # Extract callback URL from order_data
                merchant_callback_url = order_data.get('callbackurl') or order_data.get('callback_url')
                
                # Default internal callback URL
                base_url = os.getenv('BACKEND_URL', 'https://api.craftpay.in')
                callback_url = f"{base_url}/api/callback/titanexam/payin"
                
                print(f"[Titanexam PayIn] Creating payment order:")
                print(f"  Merchant: {merchant_id}")
                print(f"  Merchant Order ID: {merchant_order_id}")
                print(f"  Amount: ₹{amount}")
                
                # Prepare request payload
                payload = {
                    'amountPaisa': int(amount * 100),
                    'orderId': merchant_order_id,
                    'callbackUrl': callback_url
                }
                
                url = f"{self.base_url}/transaction"
                
                print(f"[Titanexam PayIn] Sending request to: {url}")
                api_start = time.time()
                
                try:
                    response = self.session.put(
                        url,
                        headers=self.get_auth_header(),
                        json=payload,
                        timeout=(15, 60)
                    )
                    
                    api_elapsed = time.time() - api_start
                    print(f"[Titanexam PayIn] API Response Time: {api_elapsed:.2f}s")
                    print(f"[Titanexam PayIn] Response Status: {response.status_code}")
                    print(f"[Titanexam PayIn] Response: {response.text[:500]}")
                    
                except requests.exceptions.ReadTimeout:
                    # If timeout, save as INITIATED and rely on callback
                    api_elapsed = time.time() - api_start
                    print(f"[Titanexam PayIn] ⚠️ API Timeout after {api_elapsed:.2f}s - saving as INITIATED")
                    
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
                        'INITIATED', 'TITANEXAM', merchant_order_id,
                        merchant_callback_url
                    ))
                    
                    conn.commit()
                    
                    return {
                        'success': False,
                        'message': 'Payment gateway timeout. Transaction saved. Please check status in a few minutes.',
                        'error_type': 'TIMEOUT',
                        'txn_id': txn_id,
                        'order_id': merchant_order_id
                    }
                
                if response.status_code not in [200, 201]:
                    try:
                        error_res = response.json()
                        error_msg = error_res.get('message', 'Payment order creation failed')
                    except:
                        error_msg = f'Titanexam API error: {response.text}'
                    print(error_msg)
                    return {'success': False, 'message': error_msg}
                
                titan_response = response.json()
                
                # Extract data from response
                upi_string = titan_response.get('upiString', '')
                transaction_id = titan_response.get('transactionId', merchant_order_id)
                
                if not upi_string:
                    return {'success': False, 'message': 'No payment link received from Titanexam'}
                
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
                    'INITIATED', 'TITANEXAM', transaction_id,
                    merchant_callback_url
                ))
                
                print(f"✓ Transaction created:")
                print(f"  - TXN ID: {txn_id}")
                print(f"  - Merchant Order ID: {merchant_order_id}")
                print(f"  - Callback URL: {merchant_callback_url}")
                
                conn.commit()
                
                return {
                    'success': True,
                    'txn_id': txn_id,
                    'order_id': merchant_order_id,
                    'merchant_order_id': merchant_order_id,
                    'amount': amount,
                    'charge_amount': charge_amount,
                    'net_amount': net_amount,
                    'upi_link': upi_string,
                    'intent_url': upi_string,
                    'qr_string': upi_string,
                    'payment_link': upi_string,
                    'pg_partner': 'TITANEXAM'
                }
                
        except requests.exceptions.Timeout as e:
            print(f"[Titanexam PayIn] ❌ Timeout error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False, 
                'message': 'Payment gateway timeout. Please try again or check transaction status after a few minutes.',
                'error_type': 'TIMEOUT'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[Titanexam PayIn] ❌ Connection error: {e}")
            return {
                'success': False, 
                'message': 'Unable to connect to payment gateway. Please try again later.',
                'error_type': 'CONNECTION_ERROR'
            }
        except Exception as e:
            print(f"[Titanexam PayIn] ❌ Error: {e}")
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

# Create singleton instance
titanexam_service = TitanexamService()
