"""
HDFC JVI Payin Service
Generates dynamic UPI intent links for HDFC JVI QR code
"""

import os
import json
import uuid
import requests
import urllib.parse
from datetime import datetime
from database import get_db_connection

class HdfcJviService:
    def __init__(self):
        self.payee_vpa = "9810244341.2@hdfc"
        self.payee_name = "Indrajeet More"
    
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
        Create payin order by generating dynamic UPI intent
        """
        try:
            import time
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
                merchant_order_id = order_data.get('orderid') or f"HDFCJVI_{merchant_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Create internal transaction ID
                txn_id = f"HDFCJVI_{merchant_id}_{merchant_order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Prepare customer data
                customer_name = f"{order_data.get('payee_fname', '')} {order_data.get('payee_lname', '')}".strip()
                customer_mobile = order_data.get('payee_mobile', '')
                customer_email = order_data.get('payee_email', '')
                
                # Extract callback URL from order_data
                callback_url = order_data.get('callbackurl') or order_data.get('callback_url')
                
                if not callback_url:
                    base_url = os.getenv('BACKEND_URL', 'https://api.craftpay.in')
                    callback_url = f"{base_url}/api/callback/hdfc_jvi/payin"
                    print(f"⚠ No callback URL provided, using default: {callback_url}")

                # Generate dynamic UPI intent
                transaction_note = order_data.get('productinfo') or merchant_order_id
                
                upi_params = {
                    'pa': self.payee_vpa,
                    'pn': self.payee_name,
                    'am': f"{amount:.2f}",
                    'cu': 'INR',
                    'tn': transaction_note,
                    'tr': merchant_order_id
                }
                
                upi_deeplink = f"upi://pay?{urllib.parse.urlencode(upi_params)}"
                
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
                    'INITIATED', 'HDFC_JVI', merchant_order_id,
                    callback_url
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
                    'upi_link': upi_deeplink,
                    'intent_url': upi_deeplink,
                    'qr_string': upi_deeplink,
                    'payment_link': upi_deeplink,
                    'pg_partner': 'HDFC_JVI'
                }
                
        except Exception as e:
            print(f"[HDFC JVI PayIn] ❌ Error: {e}")
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

    def send_callback(self, txn_id):
        """
        Send Maxpe-formatted callback to merchant
        """
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'message': 'Database connection failed'}
            
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, order_id, amount as txn_amount, 
                           net_amount, charge_amount, callback_url, bank_ref_no
                    FROM payin_transactions
                    WHERE txn_id = %s
                """, (txn_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    return {'success': False, 'message': 'Transaction not found'}
                
                callback_url = txn.get('callback_url')
                if callback_url:
                    callback_url = callback_url.strip()
                    
                if not callback_url and txn['merchant_id']:
                    cursor.execute("""
                        SELECT payin_callback_url FROM merchant_callbacks
                        WHERE merchant_id = %s
                    """, (txn['merchant_id'],))
                    merchant_callback = cursor.fetchone()
                    if merchant_callback and merchant_callback.get('payin_callback_url'):
                        callback_url = merchant_callback['payin_callback_url'].strip()

                if not callback_url:
                    return {'success': False, 'message': 'No callback URL found'}

                mapped_status = txn['status']
                
                if mapped_status == 'SUCCESS':
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM callback_logs
                        WHERE merchant_id = %s 
                        AND txn_id = %s 
                        AND response_code BETWEEN 200 AND 299
                        AND request_data LIKE %s
                    """, (txn['merchant_id'], txn['txn_id'], '%"status": "SUCCESS"%'))
                    
                    if cursor.fetchone()['count'] > 0:
                        return {'success': True, 'message': 'Callback already sent'}

                merchant_callback_data = {
                    'txn_id': txn['txn_id'],
                    'order_id': txn['order_id'],
                    'status': mapped_status,
                    'utr': txn.get('bank_ref_no', ''),
                    'pg_partner': 'HDFC_JVI',
                    'amount': float(txn['txn_amount']) if txn['txn_amount'] else 0,
                    'net_amount': float(txn['net_amount']) if txn['net_amount'] else 0,
                    'charge_amount': float(txn['charge_amount']) if txn['charge_amount'] else 0
                }

                try:
                    callback_response = requests.post(
                        callback_url,
                        json=merchant_callback_data,
                        headers={'Content-Type': 'application/json'},
                        timeout=10
                    )
                    
                    cursor.execute("""
                        INSERT INTO callback_logs 
                        (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    """, (
                        txn['merchant_id'],
                        txn['txn_id'],
                        callback_url,
                        json.dumps(merchant_callback_data),
                        callback_response.status_code,
                        callback_response.text[:1000]
                    ))
                    conn.commit()
                    return {'success': True, 'message': 'Callback sent'}
                except requests.exceptions.RequestException as e:
                    cursor.execute("""
                        INSERT INTO callback_logs 
                        (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    """, (
                        txn['merchant_id'],
                        txn['txn_id'],
                        callback_url,
                        json.dumps(merchant_callback_data),
                        0,
                        str(e)[:1000]
                    ))
                    conn.commit()
                    return {'success': False, 'message': f'Callback failed: {e}'}

        finally:
            conn.close()

hdfc_jvi_service = HdfcJviService()
