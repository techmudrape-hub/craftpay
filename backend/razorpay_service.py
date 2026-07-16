"""
Razorpay Payment Gateway Integration Service
Handles payin transactions through Razorpay Payment Links
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

class RazorpayService:
    def __init__(self):
        self.base_url = Config.RAZORPAY_BASE_URL
        self.key_id = Config.RAZORPAY_KEY_ID
        self.key_secret = Config.RAZORPAY_KEY_SECRET
        
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
    
    def get_auth(self):
        """Get Basic Auth tuple for Razorpay API"""
        return (self.key_id, self.key_secret)
    
    def get_headers(self):
        """Get request headers for Razorpay API"""
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
        Create payin order via Razorpay Payment Link
        order_data should contain:
        - amount
        - orderid (optional - will be generated if not provided)
        - payee_fname
        - payee_mobile
        - payee_email
        - productinfo (optional)
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
                merchant_order_id = order_data.get('orderid') or f"RZP_{merchant_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Create internal transaction ID
                txn_id = f"RAZORPAY_{merchant_id}_{merchant_order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
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
                
                # Prepare callback URL
                callback_url = order_data.get('callbackurl') or order_data.get('callback_url')
                if not callback_url:
                    base_url = os.getenv('BACKEND_URL', 'https://api.craftpay.in')
                    callback_url = f"{base_url}/api/callback/razorpay/payin"
                    print(f"⚠ No callback URL provided, using default: {callback_url}")
                
                print(f"[Razorpay PayIn] Creating payment link:")
                print(f"  Merchant: {merchant_id}")
                print(f"  Merchant Order ID: {merchant_order_id}")
                print(f"  Amount: ₹{amount}")
                print(f"  Customer: {customer_name} ({customer_mobile})")
                
                # Prepare Razorpay Payment Link payload
                # Amount in paise (smallest currency unit)
                amount_in_paise = int(amount * 100)
                
                payload = {
                    'upi_link': True,  # Create UPI Payment Link
                    'amount': amount_in_paise,
                    'currency': 'INR',
                    'description': order_data.get('productinfo', 'Payment'),
                    'customer': {
                        'name': customer_name,
                        'contact': f'+91{customer_mobile}',
                        'email': customer_email
                    },
                    'notify': {
                        'sms': False,  # We handle notifications
                        'email': False
                    },
                    'reminder_enable': False,
                    'callback_url': callback_url,
                    'callback_method': 'get'
                }
                
                # Create payment link
                url = f"{self.base_url}/v1/payment_links"
                
                print(f"[Razorpay PayIn] Sending request to: {url}")
                api_start = time.time()
                
                try:
                    response = self.session.post(
                        url,
                        auth=self.get_auth(),
                        headers=self.get_headers(),
                        json=payload,
                        timeout=(15, 60)  # 15s to connect, 60s to read response
                    )
                    
                    api_elapsed = time.time() - api_start
                    print(f"[Razorpay PayIn] API Response Time: {api_elapsed:.2f}s")
                    print(f"[Razorpay PayIn] Response Status: {response.status_code}")
                    print(f"[Razorpay PayIn] Response: {response.text[:500]}")
                    
                except requests.exceptions.ReadTimeout:
                    api_elapsed = time.time() - api_start
                    print(f"[Razorpay PayIn] ⚠️ API Timeout after {api_elapsed:.2f}s")
                    return {
                        'success': False,
                        'message': 'Payment gateway timeout. Please try again.',
                        'error_type': 'TIMEOUT'
                    }
                
                if response.status_code not in [200, 201]:
                    error_msg = f'Razorpay API error: {response.text}'
                    print(error_msg)
                    return {'success': False, 'message': error_msg}
                
                razorpay_response = response.json()
                print(f"Razorpay Response JSON: {razorpay_response}")
                
                # Extract data from response
                payment_link_id = razorpay_response.get('id', '')
                short_url = razorpay_response.get('short_url', '')
                status = razorpay_response.get('status', 'created')
                
                # Validate that we got the payment link
                if not short_url:
                    print(f"No short_url in response: {razorpay_response}")
                    return {'success': False, 'message': 'No payment link received from Razorpay'}
                
                # Map status to our database ENUM
                db_status = 'INITIATED' if status == 'created' else status.upper()
                
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
                    db_status, 'RAZORPAY', payment_link_id,
                    callback_url
                ))
                
                conn.commit()
                
                total_elapsed = time.time() - start_time
                print(f"[Razorpay PayIn] ✓ Transaction created in {total_elapsed:.2f}s")
                print(f"  - TXN ID: {txn_id}")
                print(f"  - Merchant Order ID: {merchant_order_id}")
                print(f"  - Payment Link ID: {payment_link_id}")
                print(f"  - Amount: ₹{amount} (Net: ₹{net_amount}, Charge: ₹{charge_amount})")
                print(f"  - Callback URL: {callback_url}")
                print(f"  - Payment Link: {short_url}")
                
                # Schedule automatic status checks
                self.auto_check_status_after_delay(payment_link_id, delay_seconds=60)
                self.auto_check_status_after_delay(payment_link_id, delay_seconds=120)
                self.auto_check_status_after_delay(payment_link_id, delay_seconds=180)
                print(f"[Razorpay PayIn] ✓ Scheduled automatic status checks at 60s, 120s, 180s")
                
                return {
                    'success': True,
                    'txn_id': txn_id,
                    'order_id': merchant_order_id,
                    'merchant_order_id': merchant_order_id,
                    'amount': amount,
                    'charge_amount': charge_amount,
                    'net_amount': net_amount,
                    'upi_link': short_url,
                    'intent_url': short_url,
                    'qr_string': short_url,
                    'payment_link': short_url,
                    'payment_link_id': payment_link_id,
                    'pg_partner': 'RAZORPAY'
                }
                
        except requests.exceptions.Timeout as e:
            print(f"[Razorpay PayIn] ❌ Timeout error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False, 
                'message': 'Payment gateway timeout. Please try again.',
                'error_type': 'TIMEOUT'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[Razorpay PayIn] ❌ Connection error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False, 
                'message': 'Unable to connect to payment gateway. Please try again later.',
                'error_type': 'CONNECTION_ERROR'
            }
        except Exception as e:
            print(f"[Razorpay PayIn] ❌ Error: {e}")
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
    
    def check_payment_status(self, payment_link_id):
        """
        Check payment status on Razorpay
        
        Args:
            payment_link_id: The Razorpay payment link ID
        
        Returns:
            dict: Status information
        """
        try:
            print(f"Checking Razorpay payment status - payment_link_id: {payment_link_id}")
            
            url = f"{self.base_url}/v1/payment_links/{payment_link_id}"
            
            response = self.session.get(
                url,
                auth=self.get_auth(),
                headers=self.get_headers(),
                timeout=(10, 60)
            )
            
            print(f"Response: {response.status_code} - {response.text[:500]}")
            
            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'Status check failed: {response.text}'
                }
            
            razorpay_response = response.json()
            
            # Extract status
            status = razorpay_response.get('status', 'created').lower()
            
            # Map Razorpay status to our status
            if status == 'paid':
                mapped_status = 'SUCCESS'
            elif status in ['expired', 'cancelled']:
                mapped_status = 'FAILED'
            else:
                mapped_status = 'INITIATED'
            
            # Extract payment details if paid
            payments = razorpay_response.get('payments', [])
            payment_id = None
            utr = None
            
            if payments and len(payments) > 0:
                payment = payments[0]
                payment_id = payment.get('payment_id', '')
                
                # Fetch full payment details to get bank UTR
                if payment_id:
                    try:
                        print(f"Fetching payment details to get bank UTR for {payment_id}...")
                        payment_url = f"{self.base_url}/v1/payments/{payment_id}"
                        payment_response = self.session.get(
                            payment_url,
                            auth=self.get_auth(),
                            headers=self.get_headers(),
                            timeout=(10, 30)
                        )
                        
                        if payment_response.status_code == 200:
                            payment_data = payment_response.json()
                            # Extract UTR from acquirer_data
                            acquirer_data = payment_data.get('acquirer_data', {})
                            utr = acquirer_data.get('rrn') or acquirer_data.get('utr') or acquirer_data.get('bank_transaction_id')
                            
                            if utr:
                                print(f"✓ Bank UTR found: {utr}")
                            else:
                                print(f"⚠ No bank UTR in acquirer_data, using payment_id")
                                utr = payment_id
                        else:
                            print(f"⚠ Failed to fetch payment details, using payment_id as UTR")
                            utr = payment_id
                    except Exception as e:
                        print(f"⚠ Error fetching bank UTR: {e}")
                        utr = payment_id
                else:
                    utr = payment_id
            
            result = {
                'success': True,
                'status': mapped_status,
                'payment_link_id': razorpay_response.get('id', payment_link_id),
                'amount': razorpay_response.get('amount', 0) / 100,  # Convert paise to rupees
                'amount_paid': razorpay_response.get('amount_paid', 0) / 100,
                'payment_id': payment_id,
                'utr': utr,
                'created_at': razorpay_response.get('created_at', ''),
                'message': 'Status retrieved successfully'
            }
            
            print(f"Parsed Razorpay Status: {result}")
            
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
    
    def auto_check_status_after_delay(self, payment_link_id, delay_seconds=60):
        """
        Automatically check payment status after a delay
        This ensures status gets updated even if callback fails
        
        Args:
            payment_link_id: The Razorpay payment link ID to check
            delay_seconds: Delay before checking (default 60 seconds)
        """
        def check_status_task():
            try:
                print(f"[Razorpay Auto Status Check] Waiting {delay_seconds} seconds before checking {payment_link_id}...")
                time.sleep(delay_seconds)
                
                print(f"[Razorpay Auto Status Check] Checking status for {payment_link_id}...")
                
                # Get transaction from database
                conn = get_db_connection()
                if not conn:
                    print(f"[Razorpay Auto Status Check] Database connection failed")
                    return
                
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            SELECT txn_id, order_id, merchant_id, status, pg_txn_id, net_amount, charge_amount
                            FROM payin_transactions
                            WHERE pg_txn_id = %s AND pg_partner = 'RAZORPAY'
                        """, (payment_link_id,))
                        
                        txn = cursor.fetchone()
                        
                        if not txn:
                            print(f"[Razorpay Auto Status Check] Transaction not found: {payment_link_id}")
                            return
                        
                        # Only check if still pending
                        if txn['status'] not in ['INITIATED', 'PENDING']:
                            print(f"[Razorpay Auto Status Check] Transaction already {txn['status']}, skipping")
                            return
                        
                        print(f"[Razorpay Auto Status Check] Checking Razorpay with payment_link_id: {payment_link_id}")
                        
                        # Check status from Razorpay
                        status_result = self.check_payment_status(payment_link_id)
                        
                        if not status_result.get('success'):
                            print(f"[Razorpay Auto Status Check] Status check failed: {status_result.get('message')}")
                            return
                        
                        razorpay_status = status_result.get('status', '').upper()
                        print(f"[Razorpay Auto Status Check] Razorpay status: {razorpay_status}")
                        
                        # Update if status changed to SUCCESS
                        if razorpay_status == 'SUCCESS' and txn['status'] != 'SUCCESS':
                            print(f"[Razorpay Auto Status Check] Updating {txn['txn_id']} to SUCCESS")
                            
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
                                    description=f"PayIn received (Razorpay Auto) - {txn['order_id']}",
                                    reference_id=txn['txn_id']
                                )
                                
                                if wallet_result['success']:
                                    print(f"[Razorpay Auto Status Check] ✓ Merchant wallet credited: ₹{txn['net_amount']}")
                                else:
                                    print(f"[Razorpay Auto Status Check] ✗ Failed to credit merchant wallet: {wallet_result.get('message')}")
                                
                                # Credit admin unsettled wallet with charge amount
                                admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                    admin_id='admin',
                                    amount=float(txn['charge_amount']),
                                    description=f"PayIn charge (Razorpay Auto) - {txn['order_id']}",
                                    reference_id=txn['txn_id']
                                )
                                
                                if admin_wallet_result['success']:
                                    print(f"[Razorpay Auto Status Check] ✓ Admin wallet credited: ₹{txn['charge_amount']}")
                                else:
                                    print(f"[Razorpay Auto Status Check] ✗ Failed to credit admin wallet: {admin_wallet_result.get('message')}")
                            else:
                                print(f"[Razorpay Auto Status Check] ⚠ Wallet already credited, skipping")
                            
                            conn.commit()
                            print(f"[Razorpay Auto Status Check] ✓ Successfully updated {txn['txn_id']} to SUCCESS")
                            
                            # FORWARD CALLBACK TO MERCHANT
                            print(f"[Razorpay Auto Status Check] Forwarding callback to merchant...")
                            
                            # Get callback URL
                            cursor.execute("""
                                SELECT callback_url FROM payin_transactions WHERE txn_id = %s
                            """, (txn['txn_id'],))
                            
                            txn_updated = cursor.fetchone()
                            callback_url = txn_updated.get('callback_url') if txn_updated else None
                            
                            # If no callback URL in transaction, check merchant_callbacks table
                            if not callback_url and txn['merchant_id']:
                                cursor.execute("""
                                    SELECT payin_callback_url FROM merchant_callbacks
                                    WHERE merchant_id = %s
                                """, (txn['merchant_id'],))
                                
                                merchant_callback = cursor.fetchone()
                                if merchant_callback:
                                    callback_url = merchant_callback.get('payin_callback_url')
                            
                            if callback_url and callback_url.strip():
                                # Check if callback already sent
                                cursor.execute("""
                                    SELECT COUNT(*) as count FROM callback_logs
                                    WHERE merchant_id = %s 
                                    AND txn_id = %s 
                                    AND response_code BETWEEN 200 AND 299
                                    AND request_data LIKE %s
                                """, (txn['merchant_id'], txn['txn_id'], '%"status": "SUCCESS"%'))
                                
                                callback_already_sent = cursor.fetchone()['count'] > 0
                                
                                if not callback_already_sent:
                                    import requests
                                    import json
                                    
                                    # Get amount from database
                                    cursor.execute("""
                                        SELECT amount FROM payin_transactions WHERE txn_id = %s
                                    """, (txn['txn_id'],))
                                    
                                    amount_row = cursor.fetchone()
                                    amount = float(amount_row['amount']) if amount_row else 0
                                    
                                    # Prepare callback data in MAXPE format
                                    callback_data = {
                                        'txn_id': txn['txn_id'],
                                        'order_id': txn['order_id'],
                                        'status': 'SUCCESS',
                                        'utr': status_result.get('utr'),
                                        'pg_partner': 'RAZORPAY',
                                        'amount': amount,
                                        'net_amount': float(txn['net_amount']),
                                        'charge_amount': float(txn['charge_amount'])
                                    }
                                    
                                    try:
                                        print(f"[Razorpay Auto Status Check] Sending callback to: {callback_url}")
                                        print(f"[Razorpay Auto Status Check] Callback data: {json.dumps(callback_data)}")
                                        
                                        response = requests.post(
                                            callback_url,
                                            json=callback_data,
                                            headers={'Content-Type': 'application/json'},
                                            timeout=10
                                        )
                                        
                                        print(f"[Razorpay Auto Status Check] ✓ Merchant callback sent: {response.status_code}")
                                        
                                        # Log callback
                                        cursor.execute("""
                                            INSERT INTO callback_logs 
                                            (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                                            VALUES (%s, %s, %s, %s, %s, %s, NOW())
                                        """, (
                                            txn['merchant_id'],
                                            txn['txn_id'],
                                            callback_url,
                                            json.dumps(callback_data),
                                            response.status_code,
                                            response.text[:1000]
                                        ))
                                        conn.commit()
                                        
                                    except Exception as e:
                                        print(f"[Razorpay Auto Status Check] ✗ Failed to send callback: {e}")
                                        
                                        # Log failed callback
                                        cursor.execute("""
                                            INSERT INTO callback_logs 
                                            (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                                            VALUES (%s, %s, %s, %s, %s, %s, NOW())
                                        """, (
                                            txn['merchant_id'],
                                            txn['txn_id'],
                                            callback_url,
                                            json.dumps(callback_data),
                                            0,
                                            str(e)[:1000]
                                        ))
                                        conn.commit()
                                else:
                                    print(f"[Razorpay Auto Status Check] ⚠ Callback already sent, skipping")
                            else:
                                print(f"[Razorpay Auto Status Check] ⚠ No merchant callback URL configured")
                        
                        elif razorpay_status == 'FAILED' and txn['status'] != 'FAILED':
                            print(f"[Razorpay Auto Status Check] Updating {txn['txn_id']} to FAILED")
                            
                            cursor.execute("""
                                UPDATE payin_transactions
                                SET status = 'FAILED',
                                    completed_at = NOW(),
                                    updated_at = NOW()
                                WHERE txn_id = %s
                            """, (txn['txn_id'],))
                            
                            conn.commit()
                            print(f"[Razorpay Auto Status Check] ✓ Updated {txn['txn_id']} to FAILED")
                        else:
                            print(f"[Razorpay Auto Status Check] Status unchanged: {razorpay_status}")
                        
                finally:
                    conn.close()
                    
            except Exception as e:
                print(f"[Razorpay Auto Status Check] Error: {e}")
                import traceback
                traceback.print_exc()
        
        # Start background thread
        thread = threading.Thread(target=check_status_task, daemon=True)
        thread.start()
        print(f"[Razorpay Auto Status Check] Scheduled status check for {payment_link_id} in {delay_seconds} seconds")
    
    def verify_signature(self, razorpay_order_id, razorpay_payment_id, razorpay_signature):
        """
        Verify Razorpay signature for callback
        
        Args:
            razorpay_order_id: Order ID from Razorpay
            razorpay_payment_id: Payment ID from Razorpay
            razorpay_signature: Signature from Razorpay
        
        Returns:
            bool: True if signature is valid, False otherwise
        """
        try:
            message = f"{razorpay_order_id}|{razorpay_payment_id}"
            generated_signature = hmac.new(
                self.key_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(generated_signature, razorpay_signature)
        except Exception as e:
            print(f"Signature verification error: {e}")
            return False


# Create singleton instance
razorpay_service = RazorpayService()
