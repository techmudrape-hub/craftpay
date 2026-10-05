"""
Household Payin Service
Handles payin transactions through Household
"""

import requests
import json
import os
import time
from datetime import datetime
from config import Config
from database import get_db_connection

class HouseholdService:
    def __init__(self):
        self.base_url = Config.HOUSEHOLD_BASE_URL
        self.client_id = Config.HOUSEHOLD_CLIENT_ID
        self.secret_id = Config.HOUSEHOLD_SECRET_ID
        
        # Create session with connection pooling and retry logic
        self.session = requests.Session()
        
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=2,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["POST", "GET"],
            raise_on_status=False
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20,
            pool_block=False
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def get_headers(self):
        """
        Get request headers for Household API
        """
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Client-Id': self.client_id,
            'X-Secret-Id': self.secret_id
        }
        return headers
    
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
        Create payin order via Household
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
                merchant_order_id = order_data.get('orderid') or f"HOUSEHOLD_{merchant_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Create internal transaction ID
                txn_id = f"HOUSEHOLD_{merchant_id}_{merchant_order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Prepare customer data
                customer_name = f"{order_data.get('payee_fname', '')} {order_data.get('payee_lname', '')}".strip()
                customer_mobile = order_data.get('payee_mobile', '')
                
                if not customer_name:
                    customer_name = "Customer"
                if not customer_mobile or len(customer_mobile) < 10:
                    customer_mobile = "9999999999"  # Fallback mobile
                
                # Extract callback URL from order_data
                callback_url = order_data.get('callbackurl') or order_data.get('callback_url')
                
                if not callback_url:
                    base_url = os.getenv('BACKEND_URL', 'https://api.craftpay.in')
                    callback_url = f"{base_url}/api/callback/household/payin"
                    print(f"⚠ No callback URL provided, using default: {callback_url}")
                
                redirect_url = order_data.get('surl', 'https://orchpay.in')
                
                print(f"[HOUSEHOLD PayIn] Creating payment order:")
                print(f"  Merchant: {merchant_id}")
                print(f"  Merchant Order ID: {merchant_order_id}")
                print(f"  Amount: ₹{amount}")
                print(f"  Customer: {customer_name} ({customer_mobile})")
                
                # Prepare request payload
                payload = {
                    'name': customer_name,
                    'amount': amount,
                    'mobile_number': customer_mobile,
                    'order_id': merchant_order_id,
                    'redirect_url': redirect_url
                }
                
                url = f"{self.base_url}/payin/data"
                
                print(f"[HOUSEHOLD PayIn] Sending request to: {url}")
                print(f"[HOUSEHOLD PayIn] Payload: {json.dumps(payload)}")
                
                api_start = time.time()
                
                try:
                    response = self.session.post(
                        url,
                        headers=self.get_headers(),
                        json=payload,
                        timeout=(10, 60)
                    )
                    
                    api_elapsed = time.time() - api_start
                    print(f"[HOUSEHOLD PayIn] API Response Time: {api_elapsed:.2f}s")
                    print(f"[HOUSEHOLD PayIn] Response Status: {response.status_code}")
                    print(f"[HOUSEHOLD PayIn] Response: {response.text[:500]}")
                    
                except requests.exceptions.ReadTimeout:
                    api_elapsed = time.time() - api_start
                    print(f"[HOUSEHOLD PayIn] ⚠️ API Timeout after {api_elapsed:.2f}s")
                    return {
                        'success': False,
                        'message': 'Payment gateway timeout. Please try again.',
                        'error_type': 'TIMEOUT'
                    }
                
                if response.status_code not in [200, 201]:
                    error_msg = f'Household API error: {response.text}'
                    print(error_msg)
                    return {'success': False, 'message': error_msg}
                
                household_response = response.json()
                print(f"HOUSEHOLD Response JSON: {household_response}")
                
                # Check status
                # Household docs give `status: true` for success but let's be flexible
                is_success = household_response.get('status') is True or str(household_response.get('status')).lower() in ['true', 'success', '1']
                # Sometimes APIs return resultInfo -> resultStatus in body
                if not is_success and 'body' in household_response and 'resultInfo' in household_response['body']:
                    if household_response['body']['resultInfo'].get('resultStatus') == 'SUCCESS':
                        is_success = True
                        
                if not is_success:
                    error_msg = household_response.get('message', 'Payment order creation failed')
                    print(f"HOUSEHOLD payment order creation failed: {error_msg}")
                    return {'success': False, 'message': error_msg}
                
                # Extract payment URL or QR Data
                upi_link = ""
                
                # Case 1: qrData inside body
                if 'body' in household_response and 'qrData' in household_response['body']:
                    upi_link = household_response['body']['qrData']
                # Case 2: payment_url at root level
                elif 'payment_url' in household_response:
                    upi_link = household_response['payment_url']
                
                if not upi_link:
                    print(f"No payment link/QR data in response: {household_response}")
                    return {'success': False, 'message': 'No payment link received from Household'}
                
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
                    customer_name, order_data.get('payee_email', ''), customer_mobile,
                    order_data.get('productinfo', 'Payment'),
                    'INITIATED', 'HOUSEHOLD', household_response.get('trx_id', merchant_order_id),
                    callback_url
                ))
                
                conn.commit()
                
                total_elapsed = time.time() - start_time
                print(f"[HOUSEHOLD PayIn] ✓ Transaction created in {total_elapsed:.2f}s")
                print(f"  - TXN ID: {txn_id}")
                
                return {
                    'success': True,
                    'txn_id': txn_id,
                    'order_id': merchant_order_id,
                    'merchant_order_id': merchant_order_id,
                    'amount': amount,
                    'charge_amount': charge_amount,
                    'net_amount': net_amount,
                    'upi_link': upi_link,
                    'intent_url': upi_link,
                    'qr_string': upi_link,
                    'payment_link': upi_link,
                    'pg_partner': 'HOUSEHOLD'
                }
                
        except Exception as e:
            print(f"[HOUSEHOLD PayIn] ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False, 
                'message': f'Internal error: {str(e)}',
                'error_type': 'INTERNAL_ERROR'
            }
        finally:
            if 'conn' in locals() and conn:
                conn.close()

# Create singleton instance
household_service = HouseholdService()
