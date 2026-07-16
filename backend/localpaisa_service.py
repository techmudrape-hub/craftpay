import requests
import json
import hmac
import hashlib
import time
from datetime import datetime
from database import get_db_connection
from config import Config
import os

class LocalpaisaService:
    def __init__(self):
        self.base_url = "https://localpaisa.com/api"
        self.client_id = os.environ.get('LOCALPAISA_CLIENT_ID', 'YOUR_CLIENT_ID')
        self.client_secret = os.environ.get('LOCALPAISA_CLIENT_SECRET', 'YOUR_CLIENT_SECRET')

    def generate_signature(self, timestamp_str, body_str):
        # HMAC-SHA256( clientId + "." + timestamp + "." + requestBody, clientSecret )
        data = f"{self.client_id}.{timestamp_str}.{body_str}"
        signature = hmac.new(
            self.client_secret.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    def get_headers(self, body_str):
        timestamp = str(int(time.time()))
        signature = self.generate_signature(timestamp, body_str)
        return {
            'Content-Type': 'application/json',
            'X-Client-ID': self.client_id,
            'X-Timestamp': timestamp,
            'X-Signature': signature
        }

    def calculate_charges(self, amount, scheme_id, service_type='PAYIN'):
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
                else:  # FIXED
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
        try:
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
                
                order_id = order_data.get('orderid')
                txn_id = f"LOCP_{merchant_id}_{order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                firstname = order_data.get('payee_fname', '')
                lastname = order_data.get('payee_lname', '')
                fullname = f"{firstname} {lastname}".strip()
                if not fullname:
                    fullname = "Customer"
                email = order_data.get('payee_email', '')
                phone = order_data.get('payee_mobile', '9999999999')
                
                base_url = os.getenv('BACKEND_URL', 'https://api.craftpay.in')
                callback_url = f"{base_url}/api/callback/localpaisa/payin"
                
                payload = {
                    "amount": amount,
                    "customer_name": fullname,
                    "customer_mobile": phone,
                    "customer_email": email,
                    "remarks": order_data.get('productinfo', 'Payment'),
                    "client_order_id": order_id
                }
                
                body_str = json.dumps(payload)
                headers = self.get_headers(body_str)
                
                url = f"{self.base_url}/payin/create"
                
                print(f"Creating Localpaisa payment link: {url}")
                print(f"Payload: {payload}")
                
                response = requests.post(url, headers=headers, data=body_str, timeout=30)
                
                print(f"Localpaisa Response Status: {response.status_code}")
                print(f"Localpaisa Response: {response.text}")
                
                if response.status_code != 200:
                    return {'success': False, 'message': f'Localpaisa API error: {response.text}'}
                
                localpaisa_resp = response.json()
                
                if not localpaisa_resp.get('success'):
                    return {'success': False, 'message': localpaisa_resp.get('message', 'Payment link generation failed')}
                
                data = localpaisa_resp.get('data', {})
                payment_url = data.get('payment_url', '')
                upi_link = data.get('intent_url', '')
                provider_txn_id = data.get('transaction_id', '')
                
                if not payment_url and not upi_link:
                    return {'success': False, 'message': 'No payment link received'}
                
                # Check if merchant has custom callback
                merchant_callback_url = order_data.get('callbackurl') or order_data.get('callback_url')
                if merchant_callback_url:
                    # Save it in db logic
                    callback_url_to_save = merchant_callback_url
                else:
                    callback_url_to_save = callback_url
                
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
                    fullname, email, phone,
                    order_data.get('productinfo', 'Payment'),
                    'INITIATED', 'LOCALPAISA', provider_txn_id,
                    callback_url_to_save
                ))
                
                conn.commit()
                
                return {
                    'success': True,
                    'txn_id': txn_id,
                    'order_id': order_id,
                    'amount': amount,
                    'charge_amount': charge_amount,
                    'net_amount': net_amount,
                    'payment_url': payment_url,
                    'payment_link': payment_url,
                    'upi_link': upi_link,
                    'intent_url': upi_link,
                    'qr_string': upi_link,
                    'qr_code_url': upi_link,
                    'vpa': upi_link,
                    'tiny_url': '',
                    'pg_txn_id': provider_txn_id
                }
                
        except Exception as e:
            print(f"Create payin order error: {e}")
            return {'success': False, 'message': f'Internal error: {str(e)}'}
        finally:
            if conn:
                conn.close()

    def check_payment_status(self, transaction_id):
        """
        Check real-time status of a payin transaction from Localpaisa
        transaction_id is the Localpaisa transaction_id (pg_txn_id in our DB)
        """
        try:
            url = f"{self.base_url}/payin/status"
            
            payload = {
                "transaction_id": transaction_id
            }
            body_str = json.dumps(payload)
            headers = self.get_headers(body_str)
            
            response = requests.post(url, headers=headers, data=body_str, timeout=30)
            
            if response.status_code != 200:
                return {'success': False, 'message': f'API Error: {response.text}'}
                
            resp_json = response.json()
            
            if not resp_json.get('success'):
                return {'success': False, 'message': resp_json.get('message', 'Failed to get status')}
                
            data = resp_json.get('data', {})
            status_str = data.get('status', '').upper()
            
            mapped_status = 'INITIATED'
            if status_str == 'SUCCESS':
                mapped_status = 'SUCCESS'
            elif status_str in ['FAILED', 'FAILURE']:
                mapped_status = 'FAILED'
                
            return {
                'success': True,
                'status': mapped_status,
                'utr': data.get('utr_number'),
                'txnId': data.get('transaction_id'),
                'payment_mode': 'UPI',
                'created_at': data.get('created_at'),
                'completed_at': data.get('processed_at')
            }
            
        except Exception as e:
            print(f"Check payment status error: {e}")
            return {'success': False, 'message': str(e)}

localpaisa_service = LocalpaisaService()
