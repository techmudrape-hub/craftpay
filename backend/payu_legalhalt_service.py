"""
PayU Legal Halt (UPI Intent S2S) Payment Gateway Integration Service
Handles payin transactions through PayU using Server-to-Server Intent flow
"""

import hashlib
import requests
import json
from datetime import datetime
from config import Config
from database import get_db_connection
from wallet_service import wallet_service

class PayULegalHaltService:
    def __init__(self):
        self.merchant_key = Config.PAYU_LEGALHALT_MERCHANT_KEY
        self.merchant_salt = Config.PAYU_LEGALHALT_MERCHANT_SALT
        self.base_url = Config.PAYU_LEGALHALT_BASE_URL
        self.test_mode = Config.PAYU_LEGALHALT_TEST_MODE
    
    def generate_hash(self, params, salt):
        """Generate SHA512 hash for PayU Payment Initiation"""
        key = params.get('key', '')
        txnid = params.get('txnid', '')
        amount = params.get('amount', '')
        productinfo = params.get('productinfo', '')
        firstname = params.get('firstname', '')
        email = params.get('email', '')
        udf1 = params.get('udf1', '')
        udf2 = params.get('udf2', '')
        udf3 = params.get('udf3', '')
        udf4 = params.get('udf4', '')
        udf5 = params.get('udf5', '')
        
        # Format: key|txnid|amount|productinfo|firstname|email|udf1|udf2|udf3|udf4|udf5||||||salt
        hash_string = f"{key}|{txnid}|{amount}|{productinfo}|{firstname}|{email}|{udf1}|{udf2}|{udf3}|{udf4}|{udf5}||||||{salt}"
        return hashlib.sha512(hash_string.encode('utf-8')).hexdigest()
    
    def generate_txn_id(self, merchant_id):
        """Generate unique transaction ID prefixed with PULH_ (Max 25 chars)"""
        import uuid
        # Use short year timestamp (12 chars) + random (6 chars) to ensure uniqueness
        # Example: PULH_260611143022a1b2c3 (23 chars total)
        timestamp = datetime.now().strftime('%y%m%d%H%M%S')
        random_str = uuid.uuid4().hex[:6]
        return f"PULH_{timestamp}{random_str}"
    
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
    
    def create_payin_order(self, merchant_id, order_data, client_ip=None, device_info=None):
        """
        Create payin order via Server-to-Server
        """
        try:
            # Handle if the API passes the full merchant dictionary instead of just the ID
            merchant_id = merchant_id.get('merchant_id') if isinstance(merchant_id, dict) else merchant_id
            
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
                
                # Generate transaction ID (must be max 25 chars)
                txn_id = self.generate_txn_id(merchant_id)
                
                # Prepare PayU S2S payment data
                productinfo = order_data.get('productinfo', 'Payment')
                firstname = order_data.get('payee_fname', 'User')
                lastname = order_data.get('payee_lname', '')
                email = order_data.get('payee_email', merchant['email'])
                phone = order_data.get('payee_mobile', '9999999999')
                surl = f"https://api.craftpay.in/api/payin/callback/legalhalt/success"  # Placeholder domain, overridden by proxy usually
                furl = f"https://api.craftpay.in/api/payin/callback/legalhalt/failure"
                
                # Base parameters for hashing
                params = {
                    'key': self.merchant_key,
                    'txnid': txn_id,
                    'amount': f"{amount:.2f}",
                    'productinfo': productinfo,
                    'firstname': firstname,
                    'email': email,
                    'phone': phone,
                    'surl': surl,
                    'furl': furl,
                    'pg': 'UPI',
                    'bankcode': 'INTENT',
                    'txn_s2s_flow': '4'
                }
                
                if client_ip:
                    params['s2s_client_ip'] = client_ip
                if device_info:
                    params['s2s_device_info'] = device_info
                
                # Generate hash
                params['hash'] = self.generate_hash(params, self.merchant_salt)
                
                # Make the S2S POST request
                payment_url = f"{self.base_url}/_payment"
                headers = {
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
                
                response = requests.post(payment_url, data=params, headers=headers, timeout=15)
                
                if response.status_code != 200:
                    print(f"PayU Legal Halt Error: Status {response.status_code}, Body: {response.text}")
                    return {'success': False, 'message': f'Upstream gateway error: {response.status_code}'}
                
                try:
                    resp_data = response.json()
                except ValueError:
                    print(f"PayU Legal Halt Non-JSON Response: {response.text}")
                    return {'success': False, 'message': 'Invalid response from gateway'}
                
                # Check if it was successful in pending state (normal for S2S intent)
                metadata = resp_data.get('metaData', {})
                result = resp_data.get('result', {})
                
                if metadata.get('unmappedStatus') == 'pending' and 'intentURIData' in result:
                    intent_uri_data = result.get('intentURIData')
                    full_deeplink = f"upi://pay?{intent_uri_data}"
                    pg_payment_id = result.get('paymentId', '')
                    
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
                        txn_id, merchant_id, order_data.get('orderid'), amount,
                        charge_amount, charge_type, net_amount,
                        f"{firstname} {lastname}".strip(), email, phone, productinfo,
                        'INITIATED', 'PAYU_LEGALHALT', pg_payment_id, order_data.get('callbackurl')
                    ))
                    
                    conn.commit()
                    
                    return {
                        'success': True,
                        'txn_id': txn_id,
                        'order_id': order_data.get('orderid'),
                        'amount': amount,
                        'charge_amount': charge_amount,
                        'net_amount': net_amount,
                        'payment_url': full_deeplink,
                        'upi_link': full_deeplink,
                        'intent_url': full_deeplink,
                        'qr_string': full_deeplink,
                        'qr_code_url': full_deeplink
                    }
                else:
                    error_msg = metadata.get('message') or 'Failed to get intent URI from PayU'
                    print(f"PayU Legal Halt API Error: {resp_data}")
                    return {'success': False, 'message': error_msg}
                
        except Exception as e:
            print(f"Create payin order error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'Internal error: {str(e)}'}
        finally:
            if conn:
                conn.close()

    def check_payment_status(self, txn_id):
        """Verify Payment status from PayU"""
        try:
            # Hash formula: sha512(key|command|var1|salt)
            hash_string = f"{self.merchant_key}|verify_payment|{txn_id}|{self.merchant_salt}"
            verify_hash = hashlib.sha512(hash_string.encode('utf-8')).hexdigest()
            
            payload = {
                'key': self.merchant_key,
                'command': 'verify_payment',
                'var1': txn_id,
                'hash': verify_hash
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            url = f"{self.base_url}/merchant/postservice.php?form=2"
            
            response = requests.post(url, data=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                resp_data = response.json()
                if resp_data.get('status') == 1:
                    txn_details = resp_data.get('transaction_details', {}).get(txn_id, {})
                    
                    status_mapping = {
                        'success': 'SUCCESS',
                        'failure': 'FAILED',
                        'pending': 'PENDING'
                    }
                    
                    mapped_status = status_mapping.get(txn_details.get('status'), 'PENDING')
                    
                    return {
                        'success': True,
                        'status': mapped_status,
                        'utr': txn_details.get('bank_ref_num'),
                        'txnId': txn_details.get('mihpayid'),
                        'payment_mode': txn_details.get('mode', 'UPI'),
                        'raw_status': txn_details.get('status'),
                        'error_message': txn_details.get('error_Message')
                    }
                else:
                    return {'success': False, 'message': resp_data.get('msg')}
            else:
                return {'success': False, 'message': f'HTTP Error {response.status_code}'}
                
        except Exception as e:
            print(f"PayU Legal Halt verify error: {e}")
            return {'success': False, 'message': str(e)}

    def verify_webhook_hash(self, payload):
        """Verify incoming webhook hash"""
        try:
            # sha512(SALT|status||||||udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key)
            status = payload.get('status', '')
            udf5 = payload.get('udf5', '')
            udf4 = payload.get('udf4', '')
            udf3 = payload.get('udf3', '')
            udf2 = payload.get('udf2', '')
            udf1 = payload.get('udf1', '')
            email = payload.get('email', '')
            firstname = payload.get('firstname', '')
            productinfo = payload.get('productinfo', '')
            amount = payload.get('amount', '')
            txnid = payload.get('txnid', '')
            key = payload.get('key', '')
            received_hash = payload.get('hash', '')
            
            hash_string = f"{self.merchant_salt}|{status}||||||{udf5}|{udf4}|{udf3}|{udf2}|{udf1}|{email}|{firstname}|{productinfo}|{amount}|{txnid}|{key}"
            computed_hash = hashlib.sha512(hash_string.encode('utf-8')).hexdigest()
            
            return computed_hash == received_hash
        except Exception as e:
            print(f"Webhook hash verification error: {e}")
            return False

    def send_callback_notification(self, merchant_id, txn_data):
        """Send callback notification to merchant"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
            
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT payin_callback_url
                    FROM merchant_callbacks
                    WHERE merchant_id = %s
                """, (merchant_id,))
                
                callback_config = cursor.fetchone()
                
                if not callback_config or not callback_config.get('payin_callback_url'):
                    return False
                
                callback_url = callback_config['payin_callback_url']
                
                callback_data = {
                    'txn_id': txn_data['txn_id'],
                    'order_id': txn_data['order_id'],
                    'amount': str(txn_data['amount']),
                    'status': txn_data['status'],
                    'pg_txn_id': txn_data.get('pg_txn_id'),
                    'bank_ref_no': txn_data.get('bank_ref_no'),
                    'payment_mode': txn_data.get('payment_mode', 'UPI'),
                    'timestamp': datetime.now().isoformat()
                }
                
                response = requests.post(
                    callback_url,
                    json=callback_data,
                    timeout=10
                )
                
                cursor.execute("""
                    INSERT INTO callback_logs (
                        merchant_id, txn_id, callback_url, request_data,
                        response_code, response_data, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (
                    merchant_id, txn_data['txn_id'], callback_url,
                    json.dumps(callback_data), response.status_code,
                    response.text[:1000]
                ))
                
                conn.commit()
                return response.status_code == 200
                
        except Exception as e:
            print(f"Send callback error: {e}")
            return False
        finally:
            if conn:
                conn.close()

payu_legalhalt_service = PayULegalHaltService()
