"""
Acceptpay Payment Gateway Integration Service
Handles payin transactions through Acceptpay
"""

import requests
import json
import threading
import time
from datetime import datetime
from config import Config
from database import get_db_connection
from timezone_utils import get_ist_now, ist_to_mysql_format

class AcceptpayService:
    def __init__(self):
        self.base_url = Config.ACCEPTPAY_BASE_URL.strip().strip('"').strip("'") if Config.ACCEPTPAY_BASE_URL else ''
        self.token = Config.ACCEPTPAY_TOKEN.strip().strip('"').strip("'") if Config.ACCEPTPAY_TOKEN else ''
        self.merchant_id = Config.ACCEPTPAY_MERCHANT_ID.strip().strip('"').strip("'") if hasattr(Config, 'ACCEPTPAY_MERCHANT_ID') and Config.ACCEPTPAY_MERCHANT_ID else ''
        self.api_secret = Config.ACCEPTPAY_WEBHOOK_SECRET.strip().strip('"').strip("'") if Config.ACCEPTPAY_WEBHOOK_SECRET else ''
    
    def get_headers(self):
        """Get request headers for Acceptpay API"""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}',
            'X-API-Key': self.token
        }
        if self.api_secret:
            headers['X-API-Secret'] = self.api_secret
        if self.merchant_id:
            headers['X-Merchant-Id'] = self.merchant_id
            headers['merchantId'] = self.merchant_id
        return headers
    
    def calculate_charges(self, amount, scheme_id, service_type='PAYIN'):
        """Calculate charges based on scheme"""
        try:
            conn = get_db_connection()
            if not conn:
                return None, None, None
            
            with conn.cursor() as cursor:
                # Get applicable charge
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
                    # No charges configured
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
        """
        Create payin order via Acceptpay API
        order_data should contain:
        - amount
        - orderid
        - payee_fname
        - payee_lname
        - payee_mobile
        - payee_email
        - remark (optional)
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
                amount = int(float(order_data.get('amount', 0))) # API expects integer
                if amount <= 0:
                    return {'success': False, 'message': 'Invalid amount'}
                
                # Calculate charges
                charge_amount, net_amount, charge_type = self.calculate_charges(
                    amount, merchant['scheme_id']
                )
                
                if charge_amount is None:
                    return {'success': False, 'message': 'Failed to calculate charges'}
                
                # Get order details
                order_id = order_data.get('orderid')
                if not order_id:
                    order_id = f"ORD_{merchant_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Get customer details
                email = order_data.get('payee_email', merchant['email'])
                mobile = order_data.get('payee_mobile', '9999999999') # Default to something if not provided, API expects 10 digits
                # clean up mobile to be 10 digits
                mobile = ''.join(filter(str.isdigit, mobile))[-10:]
                if len(mobile) != 10:
                    mobile = "9999999999"

                remark = order_data.get('remark', f'Payment for Order {order_id}')
                if remark and len(remark) > 40:
                    remark = remark[:40]
                
                payee_fname = order_data.get('payee_fname', '')
                payee_lname = order_data.get('payee_lname', '')
                customer_name = f"{payee_fname} {payee_lname}".strip()
                if not customer_name:
                    customer_name = merchant['full_name'] or "Customer"
                
                # Prepare Acceptpay API request
                payload = {
                    'amount': amount,
                    'mobile': mobile,
                    'email': email,
                    'billId': order_id,
                    'description': remark,
                    'customerName': customer_name
                }
                
                if self.merchant_id:
                    payload['merchantId'] = self.merchant_id
                
                print(f"Acceptpay Payin Request:")
                print(f"  Amount: {amount}")
                print(f"  Email: {email}")
                print(f"  Mobile: {mobile}")
                print(f"  Bill ID: {order_id}")
                
                # Call Acceptpay API
                url = f"{self.base_url}/api/v1/transaction/initiate-transaction"
                headers = self.get_headers()
                
                response = requests.post(url, json=payload, headers=headers, timeout=30)
                response_data = response.json()
                
                print(f"Acceptpay Response Status: {response.status_code}")
                print(f"Acceptpay Response: {json.dumps(response_data, indent=2)}")
                
                if response.status_code not in [200, 201] or response_data.get('status') != 'success':
                    error_msg = response_data.get('message', 'Payment initiation failed')
                    print(f"ERROR: {error_msg}")
                    return {'success': False, 'message': error_msg}
                
                # Extract response data
                data = response_data.get('data', {})
                transaction_id = data.get('transactionId') or data.get('_id', '')
                payment_link = response_data.get('paymentLink') or data.get('paymentLink', '')
                
                # Store transaction in database
                txn_id = f"ACC_{merchant_id}_{order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                callback_url = order_data.get('callbackurl') or order_data.get('callback_url', '')
                
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
                    txn_id, merchant_id, order_id, amount, charge_amount, charge_type, net_amount,
                    customer_name, email, mobile, remark, 'INITIATED', 'ACCEPTPAY', transaction_id,
                    callback_url
                ))
                
                conn.commit()
                
                print(f"Transaction stored in database")
                print(f"  Order ID: {order_id}")
                print(f"  PG TXN ID: {transaction_id}")
                
                # Start auto-check status thread
                self.auto_check_status_after_delay(order_id, transaction_id)
                
                return {
                    'success': True,
                    'message': 'Payment initiated successfully',
                    'txn_id': txn_id,
                    'order_id': order_id,
                    'pg_order_id': transaction_id,
                    'pg_txn_id': transaction_id,
                    'payment_url': payment_link,
                    'payment_link': payment_link,
                    'upi_link': payment_link,
                    'intent_url': payment_link,
                    'qr_string': payment_link,
                    'qr_code_url': payment_link,
                    'amount': amount,
                    'charge_amount': charge_amount,
                    'net_amount': net_amount
                }
                
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return {'success': False, 'message': f'API request failed: {str(e)}'}
        except Exception as e:
            print(f"Error creating payin order: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'Error: {str(e)}'}
        finally:
            if conn:
                conn.close()
    
    def check_payment_status(self, transaction_id):
        """
        Check payment status from Acceptpay
        
        Args:
            transaction_id: The transactionId from Acceptpay response
        
        Returns:
            Status response from Acceptpay
        """
        try:
            url = f"{self.base_url}/api/v1/transaction/status-of-transaction/{transaction_id}"
            headers = self.get_headers()
            
            print(f"Checking Acceptpay status for transaction: {transaction_id}")
            
            response = requests.get(url, headers=headers, timeout=30)
            response_data = response.json()
            
            print(f"Acceptpay Status Response: {json.dumps(response_data, indent=2)}")
            
            if response.status_code != 200 or response_data.get('status') != 'success':
                print(f"Status check failed: {response_data.get('message')}")
                return None
            
            return response_data.get('data', {})
            
        except Exception as e:
            print(f"Error checking payment status: {e}")
            return None
    
    def auto_check_status_after_delay(self, order_id, transaction_id, delay_seconds=60):
        """
        Auto-check payment status after a delay
        Runs in background thread
        """
        def check_and_update():
            try:
                time.sleep(delay_seconds)
                
                print(f"Auto-checking status for order: {order_id}, txn: {transaction_id}")
                
                status_data = self.check_payment_status(transaction_id)
                
                if not status_data:
                    print(f"Could not retrieve status for {transaction_id}")
                    return
                
                transaction_status = status_data.get('status', '').lower()
                rrn = status_data.get('gatewayPaymentId', '')
                
                # Map status
                if transaction_status == 'success':
                    mapped_status = 'SUCCESS'
                elif transaction_status == 'failed':
                    mapped_status = 'FAILED'
                elif transaction_status == 'refunded':
                    mapped_status = 'REFUNDED'
                else:
                    mapped_status = 'INITIATED'
                
                # Update database
                conn = get_db_connection()
                if conn:
                    with conn.cursor() as cursor:
                        now = get_ist_now()
                        mysql_timestamp = ist_to_mysql_format(now)
                        
                        update_query = """
                            UPDATE payin_transactions
                            SET status = %s, updated_at = %s
                        """
                        params = [mapped_status, mysql_timestamp]
                        
                        if rrn:
                            update_query += ", bank_ref_no = %s"
                            params.append(rrn)
                            
                        if mapped_status in ['SUCCESS', 'FAILED', 'REFUNDED']:
                            update_query += ", completed_at = %s"
                            params.append(mysql_timestamp)
                            
                        update_query += " WHERE order_id = %s AND pg_name = 'ACCEPTPAY'"
                        params.append(order_id)
                        
                        cursor.execute(update_query, params)
                        
                        conn.commit()
                        print(f"Updated transaction status to {mapped_status}")
                    
                    conn.close()
                
            except Exception as e:
                print(f"Error in auto-check status: {e}")
        
        # Run in background thread
        thread = threading.Thread(target=check_and_update, daemon=True)
        thread.start()
    
    def update_payin_status(self, order_id, status, pg_txn_id=None, utr=None, error_message=None):
        """Update payin transaction status in database"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
            
            with conn.cursor() as cursor:
                now = get_ist_now()
                mysql_timestamp = ist_to_mysql_format(now)
                
                update_query = """
                    UPDATE payin_transactions
                    SET status = %s, updated_at = %s
                """
                params = [status, mysql_timestamp]
                
                if utr:
                    update_query += ", bank_ref_no = %s"
                    params.append(utr)
                
                if error_message:
                    update_query += ", error_message = %s"
                    params.append(error_message)
                    
                if status in ['SUCCESS', 'FAILED']:
                    update_query += ", completed_at = %s"
                    params.append(mysql_timestamp)
                
                update_query += " WHERE order_id = %s AND pg_name = 'ACCEPTPAY'"
                params.append(order_id)
                
                cursor.execute(update_query, params)
                conn.commit()
                
                print(f"Updated payin status for order {order_id} to {status}")
                return True
            
        except Exception as e:
            print(f"Error updating payin status: {e}")
            return False
        finally:
            if conn:
                conn.close()

acceptpay_service = AcceptpayService()
