"""
ClocksPay Payment Gateway Integration Service
Handles payin transactions through ClocksPay
"""

import requests
import json
import os
import threading
import time
from datetime import datetime
from config import Config
from database import get_db_connection

class ClocksPayService:
    def __init__(self):
        self.base_url = Config.CLOCKSPAY_BASE_URL
        self.token = Config.CLOCKSPAY_TOKEN
        
        # Create session with connection pooling
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
    
    def get_headers(self):
        """Get request headers for ClocksPay API"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
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
        Create payin order via ClocksPay
        order_data should contain:
        - amount
        - orderid
        - payee_fname
        - payee_lname (optional)
        - payee_mobile
        - payee_email
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
                merchant_order_id = order_data.get('orderid') or f"CLOCKSPAY_{merchant_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Create internal transaction ID
                txn_id = f"CLOCKSPAY_{merchant_id}_{merchant_order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Prepare customer data
                customer_name = f"{order_data.get('payee_fname', '')} {order_data.get('payee_lname', '')}".strip()
                customer_mobile = order_data.get('payee_mobile', '')
                customer_email = order_data.get('payee_email', '')
                
                # Validate required fields
                if not customer_name:
                    return {'success': False, 'message': 'Customer name is required'}
                if not customer_mobile or len(customer_mobile) != 10:
                    return {'success': False, 'message': 'Valid 10-digit mobile number is required'}
                if not customer_email:
                    return {'success': False, 'message': 'Customer email is required'}
                
                print(f"[ClocksPay PayIn] Creating payment link:")
                print(f"  Merchant: {merchant_id}")
                print(f"  Merchant Order ID: {merchant_order_id}")
                print(f"  Amount: ₹{amount}")
                print(f"  Customer: {customer_name} ({customer_mobile})")
                
                # Prepare ClocksPay API payload
                payload = {
                    'txnid': merchant_order_id,
                    'name': customer_name,
                    'email': customer_email,
                    'mobile': customer_mobile,
                    'amount': str(amount),
                    'token': self.token
                }
                
                # Create payment link
                url = f"{self.base_url}/API/create_link.php"
                
                print(f"[ClocksPay PayIn] Sending request to: {url}")
                api_start = time.time()
                
                try:
                    response = self.session.post(
                        url,
                        headers=self.get_headers(),
                        json=payload,
                        timeout=(15, 60)  # 15s to connect, 60s to read response
                    )
                    
                    api_elapsed = time.time() - api_start
                    print(f"[ClocksPay PayIn] API Response Time: {api_elapsed:.2f}s")
                    print(f"[ClocksPay PayIn] Response Status: {response.status_code}")
                    print(f"[ClocksPay PayIn] Response: {response.text[:500]}")
                    
                except requests.exceptions.ReadTimeout:
                    api_elapsed = time.time() - api_start
                    print(f"[ClocksPay PayIn] ⚠️ API Timeout after {api_elapsed:.2f}s")
                    return {
                        'success': False,
                        'message': 'Payment gateway timeout. Please try again.',
                        'error_type': 'TIMEOUT'
                    }
                
                if response.status_code not in [200, 201]:
                    error_msg = f'ClocksPay API error: {response.text}'
                    print(error_msg)
                    return {'success': False, 'message': error_msg}
                
                clockspay_response = response.json()
                print(f"ClocksPay Response JSON: {clockspay_response}")
                
                # Check for error in response
                if clockspay_response.get('error'):
                    error_msg = clockspay_response.get('message', 'Payment link not generated')
                    print(f"ClocksPay payment link creation failed: {error_msg}")
                    return {'success': False, 'message': error_msg}
                
                # Extract data from response
                payment_link = clockspay_response.get('paymentLink', '')
                upi_link = clockspay_response.get('upiLink', '')
                
                # Validate that we got the payment link
                if not payment_link:
                    print(f"No payment link in response: {clockspay_response}")
                    return {'success': False, 'message': 'No payment link received from ClocksPay'}
                
                # According to docs: use the upi link and copy it to all parameters of the payin link
                # Use payment link for payment_link parameter
                if upi_link:
                    # Copy UPI link to all UPI-related parameters
                    final_upi_link = upi_link
                    final_intent_url = upi_link
                    final_qr_string = upi_link
                else:
                    # Fallback to payment link if no UPI link
                    final_upi_link = payment_link
                    final_intent_url = payment_link
                    final_qr_string = payment_link
                
                # Extract callback URL from order_data
                callback_url = order_data.get('callbackurl') or order_data.get('callback_url')
                
                if not callback_url:
                    # Use default internal callback URL
                    base_url = os.getenv('BACKEND_URL', 'https://api.craftpay.in')
                    callback_url = f"{base_url}/api/callback/clockspay/payin"
                    print(f"⚠ No callback URL provided, using default: {callback_url}")
                
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
                    'INITIATED', 'CLOCKSPAY', merchant_order_id,
                    callback_url
                ))
                
                conn.commit()
                
                total_elapsed = time.time() - start_time
                print(f"[ClocksPay PayIn] ✓ Transaction created in {total_elapsed:.2f}s")
                print(f"  - TXN ID: {txn_id}")
                print(f"  - Merchant Order ID: {merchant_order_id}")
                print(f"  - Amount: ₹{amount} (Net: ₹{net_amount}, Charge: ₹{charge_amount})")
                print(f"  - Callback URL: {callback_url}")
                print(f"  - Payment Link: {payment_link}")
                print(f"  - UPI Link: {final_upi_link}")
                
                # Schedule automatic status checks
                self.auto_check_status_after_delay(merchant_order_id, delay_seconds=60)
                self.auto_check_status_after_delay(merchant_order_id, delay_seconds=120)
                self.auto_check_status_after_delay(merchant_order_id, delay_seconds=180)
                print(f"[ClocksPay PayIn] ✓ Scheduled automatic status checks at 60s, 120s, 180s")
                
                return {
                    'success': True,
                    'txn_id': txn_id,
                    'order_id': merchant_order_id,
                    'merchant_order_id': merchant_order_id,
                    'amount': amount,
                    'charge_amount': charge_amount,
                    'net_amount': net_amount,
                    'upi_link': final_upi_link,
                    'intent_url': final_intent_url,
                    'qr_string': final_qr_string,
                    'payment_link': payment_link,
                    'pg_partner': 'CLOCKSPAY'
                }
                
        except requests.exceptions.Timeout as e:
            print(f"[ClocksPay PayIn] ❌ Timeout error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False, 
                'message': 'Payment gateway timeout. Please try again.',
                'error_type': 'TIMEOUT'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[ClocksPay PayIn] ❌ Connection error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False, 
                'message': 'Unable to connect to payment gateway. Please try again later.',
                'error_type': 'CONNECTION_ERROR'
            }
        except Exception as e:
            print(f"[ClocksPay PayIn] ❌ Error: {e}")
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
    
    def check_payment_status(self, merchant_order_id):
        """
        Check payment status on ClocksPay
        
        Args:
            merchant_order_id: The merchant order ID (txnid)
        
        Returns:
            dict: Status information
        """
        try:
            print(f"Checking ClocksPay payment status - merchant_order_id: {merchant_order_id}")
            
            url = f"{self.base_url}/API/order_status.php"
            
            payload = {
                'txnid': merchant_order_id,
                'type': 'payin',
                'token': self.token
            }
            
            print(f"Status check payload: {payload}")
            
            response = self.session.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=(10, 60)
            )
            
            print(f"Response: {response.status_code} - {response.text[:500]}")
            
            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'Status check failed: {response.text}'
                }
            
            clockspay_response = response.json()
            
            # Check for error
            if clockspay_response.get('status') == 'error':
                return {
                    'success': False,
                    'message': clockspay_response.get('message', 'Status check failed')
                }
            
            # Extract status
            txn_status = clockspay_response.get('txn_status', 'pending').lower()
            
            # Map ClocksPay status to our status
            if txn_status == 'success':
                mapped_status = 'SUCCESS'
            elif txn_status == 'failed':
                mapped_status = 'FAILED'
            else:
                mapped_status = 'INITIATED'
            
            # Extract other details
            utr = clockspay_response.get('utr', '')
            amount = clockspay_response.get('amount', '0')
            
            result = {
                'success': True,
                'status': mapped_status,
                'txnid': clockspay_response.get('txnid', merchant_order_id),
                'amount': float(amount) if amount else 0,
                'utr': utr,
                'message': 'Status retrieved successfully'
            }
            
            print(f"Parsed ClocksPay Status: {result}")
            
            return result
            
        except requests.exceptions.Timeout as e:
            print(f"Check payment status timeout error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False, 
                'message': 'Status check timeout. Please try again in a few moments.'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"Check payment status connection error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False, 
                'message': 'Unable to connect to payment gateway for status check.'
            }
        except Exception as e:
            print(f"Check payment status error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'Status check error: {str(e)}'}
    
    def auto_check_status_after_delay(self, merchant_order_id, delay_seconds=60):
        """
        Automatically check payment status after a delay
        This ensures status gets updated even if callback fails
        
        Args:
            merchant_order_id: The merchant order ID to check
            delay_seconds: Delay before checking (default 60 seconds)
        """
        def check_status_task():
            try:
                print(f"[ClocksPay Auto Status Check] Waiting {delay_seconds} seconds before checking {merchant_order_id}...")
                time.sleep(delay_seconds)
                
                print(f"[ClocksPay Auto Status Check] Checking status for {merchant_order_id}...")
                
                # Get transaction from database
                conn = get_db_connection()
                if not conn:
                    print(f"[ClocksPay Auto Status Check] Database connection failed")
                    return
                
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            SELECT txn_id, order_id, merchant_id, status, pg_txn_id, net_amount, charge_amount
                            FROM payin_transactions
                            WHERE order_id = %s AND pg_partner = 'CLOCKSPAY'
                        """, (merchant_order_id,))
                        
                        txn = cursor.fetchone()
                        
                        if not txn:
                            print(f"[ClocksPay Auto Status Check] Transaction not found: {merchant_order_id}")
                            return
                        
                        # Only check if still pending
                        if txn['status'] not in ['INITIATED', 'PENDING']:
                            print(f"[ClocksPay Auto Status Check] Transaction already {txn['status']}, skipping")
                            return
                        
                        print(f"[ClocksPay Auto Status Check] Checking ClocksPay with merchant_order_id: {merchant_order_id}")
                        
                        # Check status from ClocksPay
                        status_result = self.check_payment_status(merchant_order_id)
                        
                        if not status_result.get('success'):
                            print(f"[ClocksPay Auto Status Check] Status check failed: {status_result.get('message')}")
                            return
                        
                        clockspay_status = status_result.get('status', '').upper()
                        print(f"[ClocksPay Auto Status Check] ClocksPay status: {clockspay_status}")
                        
                        # Update if status changed to SUCCESS
                        if clockspay_status == 'SUCCESS' and txn['status'] != 'SUCCESS':
                            print(f"[ClocksPay Auto Status Check] Updating {txn['txn_id']} to SUCCESS")
                            
                            # Update transaction
                            cursor.execute("""
                                UPDATE payin_transactions
                                SET status = 'SUCCESS',
                                    bank_ref_no = %s,
                                    payment_mode = 'UPI',
                                    completed_at = NOW(),
                                    updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status_result.get('utr'), txn['txn_id']))
                            
                            # Check if wallet already credited (idempotency)
                            cursor.execute("""
                                SELECT COUNT(*) as count FROM merchant_wallet_transactions
                                WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                            """, (txn['txn_id'],))
                            
                            wallet_already_credited = cursor.fetchone()['count'] > 0
                            
                            if not wallet_already_credited:
                                # Credit merchant unsettled wallet with net amount
                                from wallet_service import wallet_service as wallet_svc
                                wallet_result = wallet_svc.credit_unsettled_wallet(
                                    merchant_id=txn['merchant_id'],
                                    amount=float(txn['net_amount']),
                                    description=f"PayIn received (ClocksPay Auto) - {merchant_order_id}",
                                    reference_id=txn['txn_id']
                                )
                                
                                if wallet_result['success']:
                                    print(f"[ClocksPay Auto Status Check] ✓ Merchant wallet credited: ₹{txn['net_amount']}")
                                else:
                                    print(f"[ClocksPay Auto Status Check] ✗ Failed to credit merchant wallet: {wallet_result.get('message')}")
                                
                                # Credit admin unsettled wallet with charge amount
                                admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                    admin_id='admin',
                                    amount=float(txn['charge_amount']),
                                    description=f"PayIn charge (ClocksPay Auto) - {merchant_order_id}",
                                    reference_id=txn['txn_id']
                                )
                                
                                if admin_wallet_result['success']:
                                    print(f"[ClocksPay Auto Status Check] ✓ Admin wallet credited: ₹{txn['charge_amount']}")
                                else:
                                    print(f"[ClocksPay Auto Status Check] ✗ Failed to credit admin wallet: {admin_wallet_result.get('message')}")
                            else:
                                print(f"[ClocksPay Auto Status Check] ⚠ Wallet already credited, skipping")
                            
                            conn.commit()
                            print(f"[ClocksPay Auto Status Check] ✓ Successfully updated {txn['txn_id']} to SUCCESS")
                        
                        elif clockspay_status == 'FAILED' and txn['status'] != 'FAILED':
                            print(f"[ClocksPay Auto Status Check] Updating {txn['txn_id']} to FAILED")
                            
                            cursor.execute("""
                                UPDATE payin_transactions
                                SET status = 'FAILED',
                                    completed_at = NOW(),
                                    updated_at = NOW()
                                WHERE txn_id = %s
                            """, (txn['txn_id'],))
                            
                            conn.commit()
                            print(f"[ClocksPay Auto Status Check] ✓ Successfully updated {txn['txn_id']} to FAILED")
                        
                finally:
                    conn.close()
                    
            except Exception as e:
                print(f"[ClocksPay Auto Status Check] Error: {e}")
                import traceback
                traceback.print_exc()
        
        # Start background thread
        thread = threading.Thread(target=check_status_task, daemon=True)
        thread.start()

# Create singleton instance
clockspay_service = ClocksPayService()
