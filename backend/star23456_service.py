"""
Star23456 Payment Gateway Integration Service
Handles payin transactions through Star23456
"""

import requests
import json
import time
from datetime import datetime, timedelta
from config import Config
from database import get_db_connection

class Star23456Service:
    def __init__(self):
        self.base_url = Config.STAR23456_BASE_URL
        self.merchant_id = Config.STAR23456_MERCHANT_ID
        self.api_key = Config.STAR23456_API_KEY
        
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
        
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Token caching
        self._token = None
        self._token_expiry = None

    def get_token(self):
        """Get or refresh the authentication token"""
        if self._token and self._token_expiry and datetime.now() < self._token_expiry:
            return self._token
            
        url = f"{self.base_url}/Auth/login"
        payload = {
            "username": self.merchant_id,
            "password": self.api_key
        }
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            response = self.session.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if "token" in data:
                self._token = data["token"]
                # Token is valid for 2 hours according to docs, we expire it after 1 hour 45 mins to be safe
                self._token_expiry = datetime.now() + timedelta(minutes=105)
                return self._token
            return None
        except Exception as e:
            print(f"[Star23456] Error getting token: {e}")
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
            print(f"[Star23456] Calculate charges error: {e}")
            return None, None, None
        finally:
            if conn:
                conn.close()

    def create_payin_order(self, merchant_id, order_data):
        """
        Create payin order via Star23456
        order_data should contain amount, orderid, payee_mobile
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
                if not merchant or not merchant['is_active']:
                    return {'success': False, 'message': 'Merchant not found or inactive'}
                
                amount = float(order_data.get('amount', 0))
                if amount <= 0:
                    return {'success': False, 'message': 'Invalid amount'}
                
                charge_amount, net_amount, charge_type = self.calculate_charges(amount, merchant['scheme_id'])
                if charge_amount is None:
                    return {'success': False, 'message': 'Failed to calculate charges'}
                
                merchant_order_id = order_data.get('orderid') or f"STAR_{merchant_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                txn_id = f"STAR_{merchant_id}_{merchant_order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                customer_name = f"{order_data.get('payee_fname', '')} {order_data.get('payee_lname', '')}".strip() or "Customer"
                customer_mobile = order_data.get('payee_mobile', '9999999999')
                customer_email = order_data.get('payee_email', f"customer{merchant_id}@example.com")
                
                token = self.get_token()
                if not token:
                    return {'success': False, 'message': 'Failed to authenticate with Star23456 gateway'}
                
                url = f"{self.base_url}/v2/PaymentGateway/Initiate"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                }
                payload = {
                    "payAmount": amount,
                    "mobile": customer_mobile,
                    "merchantOrderId": merchant_order_id
                }
                
                try:
                    response = self.session.post(url, headers=headers, json=payload, timeout=30)
                    response_data = response.json()
                    
                    if response.status_code == 200 and response_data.get('status') in [True, "TXN"]:
                        payment_mode = response_data.get('payment_mode')
                        pg_txn_id = response_data.get('ref_num') or response_data.get('transaction_id')
                        
                        payment_url = ""
                        if payment_mode == 'UPI_QR':
                            payment_url = response_data.get('redirectUrl') or response_data.get('upi_link')
                        elif payment_mode == 'REDIRECT':
                            payment_url = response_data.get('redirectUrl')
                        else:
                            # Fallback if unknown
                            payment_url = response_data.get('redirectUrl')
                        
                        # Save transaction
                        cursor.execute("""
                            INSERT INTO payin_transactions (
                                txn_id, merchant_id, order_id, amount, charge_amount, 
                                charge_type, net_amount, payee_name, payee_email, 
                                payee_mobile, product_info, status, pg_partner,
                                pg_txn_id, payment_url, callback_url, created_at
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                            )
                        """, (
                            txn_id, merchant_id, merchant_order_id, amount, charge_amount,
                            charge_type, net_amount, customer_name, customer_email,
                            customer_mobile, f'PayIn {merchant_order_id}', 'INITIATED', 'STAR23456',
                            pg_txn_id, payment_url, order_data.get('callbackurl') or order_data.get('callback_url')
                        ))
                        conn.commit()
                        
                        return {
                            'success': True,
                            'message': 'Payment order created successfully',
                            'payment_link': payment_url,
                            'upi_link': payment_url,
                            'intent_url': payment_url,
                            'order_id': merchant_order_id,
                            'txn_id': txn_id,
                            'amount': amount,
                            'charge_amount': charge_amount,
                            'net_amount': net_amount,
                            'payment_mode': payment_mode,
                            'qr_image_data': response_data.get('qr_image_data') if payment_mode == 'UPI_QR' else None
                        }
                    else:
                        print(f"[Star23456] API Error: {response_data}")
                        error_msg = response_data.get('error') or response_data.get('message', 'Failed to create payment order at gateway')
                        return {'success': False, 'message': error_msg}
                        
                except Exception as api_e:
                    import traceback
                    print(f"[Star23456] Request Error: {api_e}\n{traceback.format_exc()}")
                    return {'success': False, 'message': f'Gateway request failed: {str(api_e)}'}
                    
        except Exception as e:
            import traceback
            print(f"[Star23456] Internal Error: {e}\n{traceback.format_exc()}")
            return {'success': False, 'message': f'Internal server error: {str(e)}'}
        finally:
            if conn:
                conn.close()

    def check_payment_status(self, merchant_order_id):
        """Check status of a payin order"""
        token = self.get_token()
        if not token:
            return {'success': False, 'message': 'Failed to authenticate'}
            
        url = f"{self.base_url}/v2/PaymentGateway/Status"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        payload = {
            "merchantOrderId": merchant_order_id
        }
        
        try:
            response = self.session.post(url, headers=headers, json=payload, timeout=15)
            data = response.json()
            
            if response.status_code == 200:
                txn_status = data.get('txn_status', '')
                status = 'FAILED'
                
                if txn_status.lower() == 'success':
                    status = 'SUCCESS'
                elif txn_status.lower() == 'pending':
                    status = 'PENDING'
                
                return {
                    'success': True,
                    'status': status,
                    'pg_txn_id': data.get('ref_num') or data.get('transaction_id'),
                    'raw_status': txn_status
                }
            return {'success': False, 'message': data.get('message', 'Failed to check status')}
            
        except Exception as e:
            print(f"[Star23456] Status check error: {e}")
            return {'success': False, 'message': str(e)}

star23456_service = Star23456Service()
