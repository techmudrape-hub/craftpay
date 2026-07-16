"""
InstantPesa Payment Gateway Integration Service
Handles payin transactions through InstantPesa
"""

import requests
import json
import os
import threading
import time
from datetime import datetime
from config import Config
from database import get_db_connection
from timezone_utils import get_ist_now, ist_to_mysql_format
import uuid

class InstantPesaService:
    def __init__(self):
        self.base_url = Config.INSTANTPESA_BASE_URL
        self.token = Config.INSTANTPESA_TOKEN
    
    def get_headers(self):
        """Get request headers for InstantPesa API"""
        headers = {
            'Accept': 'application/json',
            'token': self.token,
            'Content-Type': 'application/json'
        }
        return headers
    
    def generate_txn_id(self, merchant_id, order_id):
        """Generate unique transaction ID for InstantPesa request_id"""
        # Format: INST_{merchant_id}_{timestamp}_{random}
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_part = str(uuid.uuid4().hex[:8]).upper()
        return f"INST_{merchant_id}_{timestamp}_{random_part}"
    
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
        Create payin order via InstantPesa API
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
                amount = float(order_data.get('amount', 0))
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
                
                # Generate unique request_id for InstantPesa
                request_id = self.generate_txn_id(merchant_id, order_id)
                
                # Get customer details
                first_name = order_data.get('payee_fname', 'Customer')
                last_name = order_data.get('payee_lname', '')
                email = order_data.get('payee_email', '')
                mobile = order_data.get('payee_mobile', '')
                remark = order_data.get('remark', f'Payment for Order {order_id}')
                
                # Validate required fields
                if not email or not mobile:
                    return {'success': False, 'message': 'Email and mobile are required'}
                
                # Prepare InstantPesa API request
                payload = {
                    'request_id': request_id,
                    'amount': float(amount),
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'mobile': mobile,
                    'remark': remark
                }
                
                print(f"InstantPesa Payin Request:")
                print(f"  Request ID: {request_id}")
                print(f"  Amount: {amount}")
                print(f"  Customer: {first_name} {last_name}")
                print(f"  Email: {email}")
                print(f"  Mobile: {mobile}")
                
                # Call InstantPesa API
                url = f"{self.base_url}/api/payment/initiate"
                headers = self.get_headers()
                
                response = requests.post(url, json=payload, headers=headers, timeout=30)
                response_data = response.json()
                
                print(f"InstantPesa Response Status: {response.status_code}")
                print(f"InstantPesa Response: {json.dumps(response_data, indent=2)}")
                
                if response.status_code != 200 or response_data.get('status') != 'success':
                    error_msg = response_data.get('message', 'Payment initiation failed')
                    print(f"ERROR: {error_msg}")
                    return {'success': False, 'message': error_msg}
                
                # Extract response data - ONLY upi_link is used
                data = response_data.get('data', {})
                order_id_from_api = data.get('order_id', '')
                transaction_id = data.get('transaction_id', '')
                upi_link = data.get('upi_link', '')
                
                # Store transaction in database
                now = get_ist_now()
                mysql_timestamp = ist_to_mysql_format(now)
                
                cursor.execute("""
                    INSERT INTO payin_transactions (
                        merchant_id, order_id, amount, charge_amount, net_amount,
                        pg_name, pg_order_id, pg_txn_id, status, upi_link,
                        request_id, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    merchant_id, order_id, amount, charge_amount, net_amount,
                    'INSTANTPESA', order_id_from_api, transaction_id, 'INITIATED',
                    upi_link, request_id,
                    mysql_timestamp, mysql_timestamp
                ))
                
                conn.commit()
                
                print(f"Transaction stored in database")
                print(f"  Order ID: {order_id}")
                print(f"  PG Order ID: {order_id_from_api}")
                print(f"  PG TXN ID: {transaction_id}")
                
                # Start auto-check status thread
                self.auto_check_status_after_delay(order_id, transaction_id)
                
                return {
                    'success': True,
                    'message': 'Payment initiated successfully',
                    'data': {
                        'order_id': order_id,
                        'pg_order_id': order_id_from_api,
                        'pg_txn_id': transaction_id,
                        'upi_link': upi_link,
                        'amount': amount,
                        'charge_amount': charge_amount,
                        'net_amount': net_amount
                    }
                }
                
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return {'success': False, 'message': f'API request failed: {str(e)}'}
        except Exception as e:
            print(f"Error creating payin order: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}
        finally:
            if conn:
                conn.close()
    
    def check_payment_status(self, transaction_id):
        """
        Check payment status from InstantPesa
        
        Args:
            transaction_id: The transaction_id from InstantPesa response
        
        Returns:
            Status response from InstantPesa
        """
        try:
            url = f"{self.base_url}/api/payment/status/{transaction_id}"
            headers = self.get_headers()
            
            print(f"Checking InstantPesa status for transaction: {transaction_id}")
            
            response = requests.get(url, headers=headers, timeout=30)
            response_data = response.json()
            
            print(f"InstantPesa Status Response: {json.dumps(response_data, indent=2)}")
            
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
                
                transaction_status = status_data.get('transaction_status', '').upper()
                amount = status_data.get('amount', 0)
                charge = status_data.get('charge', 0)
                received_amount = status_data.get('received_amount', 0)
                rrn = status_data.get('rrn', '')
                
                # Map status
                if transaction_status == 'SUCCESS':
                    mapped_status = 'SUCCESS'
                elif transaction_status == 'FAILED':
                    mapped_status = 'FAILED'
                else:
                    mapped_status = 'INITIATED'
                
                # Update database
                conn = get_db_connection()
                if conn:
                    with conn.cursor() as cursor:
                        now = get_ist_now()
                        mysql_timestamp = ist_to_mysql_format(now)
                        
                        cursor.execute("""
                            UPDATE payin_transactions
                            SET status = %s, utr = %s, updated_at = %s
                            WHERE order_id = %s AND pg_name = 'INSTANTPESA'
                        """, (mapped_status, rrn, mysql_timestamp, order_id))
                        
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
                    update_query += ", utr = %s"
                    params.insert(2, utr)
                
                if error_message:
                    update_query += ", error_message = %s"
                    params.append(error_message)
                
                update_query += " WHERE order_id = %s AND pg_name = 'INSTANTPESA'"
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
    
    # ==================== PAYOUT METHODS ====================
    
    def create_imps_payout(self, merchant_id, payout_data):
        """
        Create IMPS payout via InstantPesa API
        payout_data should contain:
        - amount
        - account_number
        - ifsc_code
        - bank_name
        - beneficiary_name
        - email
        - mobile
        - transaction_mode (IMPS, NEFT, RTGS)
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
                amount = float(payout_data.get('amount', 0))
                if amount <= 0:
                    return {'success': False, 'message': 'Invalid amount'}
                
                # Calculate charges
                charge_amount, net_amount, charge_type = self.calculate_charges(
                    amount, merchant['scheme_id'], service_type='PAYOUT'
                )
                
                if charge_amount is None:
                    return {'success': False, 'message': 'Failed to calculate charges'}
                
                # Get payout details
                account_number = payout_data.get('account_number', '').strip()
                ifsc_code = payout_data.get('ifsc_code', '').strip().upper()
                bank_name = payout_data.get('bank_name', '').strip()
                beneficiary_name = payout_data.get('beneficiary_name', '').strip()
                email = payout_data.get('email', '').strip()
                mobile = payout_data.get('mobile', '').strip()
                transaction_mode = payout_data.get('transaction_mode', 'IMPS').upper()
                
                # Validate required fields
                if not all([account_number, ifsc_code, bank_name, beneficiary_name, email, mobile]):
                    return {'success': False, 'message': 'Missing required payout details'}
                
                # Generate unique request_id for InstantPesa
                request_id = self.generate_txn_id(merchant_id, f"PAYOUT_{datetime.now().strftime('%Y%m%d%H%M%S')}")
                
                # Prepare InstantPesa API request
                payload = {
                    'request_id': request_id,
                    'amount': float(amount),
                    'transaction_mode': transaction_mode,
                    'account_number': account_number,
                    'ifsc_code': ifsc_code,
                    'bank_name': bank_name,
                    'name': beneficiary_name,
                    'email': email,
                    'mobile': mobile
                }
                
                print(f"InstantPesa Payout Request:")
                print(f"  Request ID: {request_id}")
                print(f"  Amount: {amount}")
                print(f"  Mode: {transaction_mode}")
                print(f"  Beneficiary: {beneficiary_name}")
                print(f"  Account: {account_number}")
                print(f"  IFSC: {ifsc_code}")
                print(f"  Email: {email}")
                print(f"  Mobile: {mobile}")
                
                # Call InstantPesa API
                url = f"{self.base_url}/api/payout/initiate"
                headers = self.get_headers()
                
                response = requests.post(url, json=payload, headers=headers, timeout=30)
                response_data = response.json()
                
                print(f"InstantPesa Payout Response Status: {response.status_code}")
                print(f"InstantPesa Payout Response: {json.dumps(response_data, indent=2)}")
                
                if response.status_code != 200 or response_data.get('status') != 'pending':
                    error_msg = response_data.get('message', 'Payout initiation failed')
                    print(f"ERROR: {error_msg}")
                    return {'success': False, 'message': error_msg}
                
                # Extract response data
                data = response_data.get('data', {})
                order_id = data.get('order_id', request_id)
                transaction_id = data.get('transaction_id', '')
                
                # Store transaction in database
                now = get_ist_now()
                mysql_timestamp = ist_to_mysql_format(now)
                
                cursor.execute("""
                    INSERT INTO payout_transactions (
                        merchant_id, reference_id, amount, charge_amount, net_amount,
                        pg_name, pg_txn_id, status, account_number, ifsc_code,
                        bank_name, beneficiary_name, email, mobile, transaction_mode,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    merchant_id, request_id, amount, charge_amount, net_amount,
                    'INSTANTPESA', transaction_id, 'INITIATED', account_number, ifsc_code,
                    bank_name, beneficiary_name, email, mobile, transaction_mode,
                    mysql_timestamp, mysql_timestamp
                ))
                
                conn.commit()
                
                print(f"Payout transaction stored in database")
                print(f"  Request ID: {request_id}")
                print(f"  Order ID: {order_id}")
                print(f"  Transaction ID: {transaction_id}")
                
                return {
                    'success': True,
                    'message': 'Payout initiated successfully',
                    'data': {
                        'reference_id': request_id,
                        'transaction_id': transaction_id,
                        'order_id': order_id,
                        'amount': amount,
                        'charge_amount': charge_amount,
                        'net_amount': net_amount,
                        'status': 'INITIATED'
                    }
                }
                
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return {'success': False, 'message': f'API request failed: {str(e)}'}
        except Exception as e:
            print(f"Error creating payout: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}
        finally:
            if conn:
                conn.close()
    
    def check_payout_status(self, transaction_id):
        """
        Check payout status from InstantPesa
        
        Args:
            transaction_id: The transaction_id from InstantPesa response
        
        Returns:
            Status response from InstantPesa
        """
        try:
            url = f"{self.base_url}/api/payout/status/{transaction_id}"
            headers = self.get_headers()
            
            print(f"Checking InstantPesa payout status for transaction: {transaction_id}")
            
            response = requests.post(url, headers=headers, timeout=30)
            response_data = response.json()
            
            print(f"InstantPesa Payout Status Response: {json.dumps(response_data, indent=2)}")
            
            if response.status_code != 200 or response_data.get('status') != 'success':
                print(f"Status check failed: {response_data.get('message')}")
                return None
            
            return response_data.get('data', {})
            
        except Exception as e:
            print(f"Error checking payout status: {e}")
            return None
    
    def update_payout_status(self, reference_id, status, pg_txn_id=None, utr=None, error_message=None):
        """Update payout transaction status in database"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
            
            with conn.cursor() as cursor:
                now = get_ist_now()
                mysql_timestamp = ist_to_mysql_format(now)
                
                update_query = """
                    UPDATE payout_transactions
                    SET status = %s, updated_at = %s
                """
                params = [status, mysql_timestamp]
                
                if utr:
                    update_query += ", utr = %s"
                    params.insert(2, utr)
                
                if error_message:
                    update_query += ", error_message = %s"
                    params.append(error_message)
                
                if status in ['SUCCESS', 'FAILED']:
                    update_query += ", completed_at = %s"
                    params.append(mysql_timestamp)
                
                update_query += " WHERE reference_id = %s AND pg_name = 'INSTANTPESA'"
                params.append(reference_id)
                
                cursor.execute(update_query, params)
                conn.commit()
                
                print(f"Updated payout status for reference {reference_id} to {status}")
                return True
            
        except Exception as e:
            print(f"Error updating payout status: {e}")
            return False
        finally:
            if conn:
                conn.close()
