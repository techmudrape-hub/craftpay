"""
Risexpay Payment Gateway Integration Service
Handles payin transactions through Risexpay with HMAC-SHA256 request signing
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

class RisexpayService:
    def __init__(self):
        self.base_url = Config.RISEXPAY_BASE_URL
        self.mid = Config.RISEXPAY_MID
        self.api_key = Config.RISEXPAY_API_KEY
        self.secret_key = Config.RISEXPAY_SECRET_KEY
        
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
    
    def generate_signature(self, payload, timestamp):
        """
        Generate HMAC-SHA256 signature for Risexpay API
        
        CORRECT FORMAT (verified working):
        timestamp=<timestamp>&key1=value1&key2=value2&...
        
        The timestamp comes FIRST, then sorted payload fields
        
        Args:
            payload: Dictionary containing request fields
            timestamp: Unix timestamp in seconds
        
        Returns:
            str: HMAC-SHA256 hex digest signature
        """
        # Sort payload keys alphabetically
        sorted_keys = sorted(payload.keys())
        
        # Build canonical string: timestamp FIRST, then sorted fields
        canonical_parts = [f"timestamp={timestamp}"]
        
        for key in sorted_keys:
            value = str(payload[key])
            canonical_parts.append(f"{key}={value}")
        
        canonical_string = "&".join(canonical_parts)
        
        print(f"[Risexpay] Canonical string: {canonical_string}")
        
        # Generate HMAC SHA256 signature
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            canonical_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def get_headers(self, timestamp, signature):
        """
        Get request headers for Risexpay API
        All requests require X-Timestamp and X-Signature headers
        """
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Timestamp': str(timestamp),
            'X-Signature': signature
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
        Create payin order via Risexpay
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
                
                # Validate amount (₹100 - ₹100000 as per Risexpay docs)
                amount = float(order_data.get('amount', 0))
                if amount < 100 or amount > 100000:
                    return {'success': False, 'message': 'Invalid amount. Allowed range: ₹100 to ₹100000'}
                
                # Calculate charges
                charge_amount, net_amount, charge_type = self.calculate_charges(
                    amount, merchant['scheme_id']
                )
                
                if charge_amount is None:
                    return {'success': False, 'message': 'Failed to calculate charges'}
                
                # Generate unique merchant order ID
                merchant_order_id = order_data.get('orderid') or f"RISEXPAY_{merchant_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Create internal transaction ID
                txn_id = f"RISEXPAY_{merchant_id}_{merchant_order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Prepare customer data
                customer_name = f"{order_data.get('payee_fname', '')} {order_data.get('payee_lname', '')}".strip()
                customer_mobile = order_data.get('payee_mobile', '')
                customer_email = order_data.get('payee_email', '')
                
                # Validate required fields
                if not customer_mobile or len(customer_mobile) != 10:
                    return {'success': False, 'message': 'Valid 10-digit mobile number is required'}
                
                # Get redirect URL (callback URL from merchant)
                redirect_url = order_data.get('callbackurl') or order_data.get('callback_url')
                
                if not redirect_url:
                    # Use default internal callback URL
                    base_url = os.getenv('BACKEND_URL', 'https://api.craftpay.in')
                    redirect_url = f"{base_url}/api/callback/risexpay/payin"
                    print(f"⚠ No callback URL provided, using default: {redirect_url}")
                
                print(f"[Risexpay PayIn] Creating payment order:")
                print(f"  Merchant: {merchant_id}")
                print(f"  Merchant Order ID: {merchant_order_id}")
                print(f"  Amount: ₹{amount}")
                print(f"  Customer: {customer_mobile}")
                print(f"  Redirect URL: {redirect_url}")
                
                # Generate timestamp (Unix timestamp in seconds)
                timestamp = int(time.time())
                
                # Prepare Risexpay API payload
                payload = {
                    'mid': self.mid,
                    'apikey': self.api_key,
                    'amount': int(amount),  # Risexpay expects integer amount
                    'customer_mobile': customer_mobile,
                    'redirect_url': redirect_url
                }
                
                # Add optional fields if provided
                if order_data.get('remark1'):
                    payload['remark1'] = order_data['remark1']
                if order_data.get('remark2'):
                    payload['remark2'] = order_data['remark2']
                
                # Generate signature
                signature = self.generate_signature(payload, timestamp)
                
                print(f"  Timestamp: {timestamp}")
                print(f"  Signature: {signature[:20]}...")
                
                # Create payment order
                url = f"{self.base_url}/api/v1/imb/create_order.php"
                
                print(f"[Risexpay PayIn] Sending request to: {url}")
                api_start = time.time()
                
                try:
                    response = self.session.post(
                        url,
                        headers=self.get_headers(timestamp, signature),
                        json=payload,
                        timeout=(15, 60)  # 15s to connect, 60s to read response
                    )
                    
                    api_elapsed = time.time() - api_start
                    print(f"[Risexpay PayIn] API Response Time: {api_elapsed:.2f}s")
                    print(f"[Risexpay PayIn] Response Status: {response.status_code}")
                    print(f"[Risexpay PayIn] Response: {response.text[:500]}")
                    
                except requests.exceptions.ReadTimeout:
                    api_elapsed = time.time() - api_start
                    print(f"[Risexpay PayIn] ⚠️ API Timeout after {api_elapsed:.2f}s")
                    return {
                        'success': False,
                        'message': 'Payment gateway timeout. Please try again.',
                        'error_type': 'TIMEOUT'
                    }
                
                # Check for HTTP errors
                if response.status_code == 401:
                    error_data = response.json() if response.text else {}
                    error_msg = error_data.get('message', 'Authentication failed')
                    print(f"[Risexpay PayIn] Authentication error: {error_msg}")
                    return {'success': False, 'message': f'Risexpay authentication error: {error_msg}'}
                
                if response.status_code not in [200, 201]:
                    error_msg = f'Risexpay API error: {response.text}'
                    print(error_msg)
                    return {'success': False, 'message': error_msg}
                
                risexpay_response = response.json()
                print(f"Risexpay Response JSON: {risexpay_response}")
                
                # Check for error in response
                if not risexpay_response.get('status'):
                    error_msg = risexpay_response.get('message', 'Payment order creation failed')
                    print(f"Risexpay payment order creation failed: {error_msg}")
                    return {'success': False, 'message': error_msg}
                
                # Extract data from response
                data = risexpay_response.get('data', {})
                order_id = data.get('order_id', '')
                imb_order_id = data.get('imb_order_id', '')
                payment_url = data.get('payment_url', '')
                bhim_link = data.get('bhim_link', '')  # UPI deeplink
                paytm_link = data.get('paytm_link', '')
                check_link = data.get('check_link', '')
                
                # Validate that we got the payment link
                if not payment_url:
                    print(f"No payment_url in response: {risexpay_response}")
                    return {'success': False, 'message': 'No payment link received from Risexpay'}
                
                # Use bhim_link (UPI deeplink) for all UPI parameters as per requirement
                # Use payment_url for the payment_link parameter
                final_upi_link = bhim_link if bhim_link else payment_url
                final_intent_url = bhim_link if bhim_link else payment_url
                final_qr_string = bhim_link if bhim_link else payment_url
                
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
                    'INITIATED', 'RISEXPAY', order_id,
                    redirect_url
                ))
                
                conn.commit()
                
                total_elapsed = time.time() - start_time
                print(f"[Risexpay PayIn] ✓ Transaction created in {total_elapsed:.2f}s")
                print(f"  - TXN ID: {txn_id}")
                print(f"  - Merchant Order ID: {merchant_order_id}")
                print(f"  - Risexpay Order ID: {order_id}")
                print(f"  - IMB Order ID: {imb_order_id}")
                print(f"  - Amount: ₹{amount} (Net: ₹{net_amount}, Charge: ₹{charge_amount})")
                print(f"  - Callback URL: {redirect_url}")
                print(f"  - Payment Link: {payment_url}")
                print(f"  - BHIM Link: {final_upi_link}")
                
                # Schedule automatic status checks
                self.auto_check_status_after_delay(order_id, delay_seconds=60)
                self.auto_check_status_after_delay(order_id, delay_seconds=120)
                self.auto_check_status_after_delay(order_id, delay_seconds=180)
                print(f"[Risexpay PayIn] ✓ Scheduled automatic status checks at 60s, 120s, 180s")
                
                return {
                    'success': True,
                    'txn_id': txn_id,
                    'order_id': order_id,
                    'merchant_order_id': order_id,
                    'imb_order_id': imb_order_id,
                    'amount': amount,
                    'charge_amount': charge_amount,
                    'net_amount': net_amount,
                    'upi_link': final_upi_link,
                    'intent_url': final_intent_url,
                    'qr_string': final_qr_string,
                    'payment_link': payment_url,
                    'paytm_link': paytm_link,
                    'check_link': check_link,
                    'pg_partner': 'RISEXPAY'
                }
                
        except requests.exceptions.Timeout as e:
            print(f"[Risexpay PayIn] ❌ Timeout error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False, 
                'message': 'Payment gateway timeout. Please try again.',
                'error_type': 'TIMEOUT'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[Risexpay PayIn] ❌ Connection error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False, 
                'message': 'Unable to connect to payment gateway. Please try again later.',
                'error_type': 'CONNECTION_ERROR'
            }
        except Exception as e:
            print(f"[Risexpay PayIn] ❌ Error: {e}")
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
    
    def check_payment_status(self, order_id):
        """
        Check payment status on Risexpay
        
        Args:
            order_id: The order ID from Risexpay
        
        Returns:
            dict: Status information
        """
        try:
            print(f"Checking Risexpay payment status - order_id: {order_id}")
            
            url = f"{self.base_url}/api/v1/imb/check_status.php"
            
            # Generate timestamp
            timestamp = int(time.time())
            
            # Prepare payload
            payload = {
                'mid': self.mid,
                'apikey': self.api_key,
                'order_id': order_id
            }
            
            # Generate signature
            signature = self.generate_signature(payload, timestamp)
            
            print(f"Status check payload: {payload}")
            
            response = self.session.post(
                url,
                headers=self.get_headers(timestamp, signature),
                json=payload,
                timeout=(10, 60)
            )
            
            print(f"Response: {response.status_code} - {response.text[:500]}")
            
            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'Status check failed: {response.text}'
                }
            
            risexpay_response = response.json()
            
            # Check for error
            if not risexpay_response.get('status'):
                return {
                    'success': False,
                    'message': risexpay_response.get('message', 'Status check failed')
                }
            
            # Extract data
            data = risexpay_response.get('data', {})
            current_status = data.get('current_status', 'PENDING').upper()
            
            # Map Risexpay status to our status
            if current_status == 'COMPLETED':
                mapped_status = 'SUCCESS'
            elif current_status == 'FAILED':
                mapped_status = 'FAILED'
            else:
                mapped_status = 'INITIATED'
            
            # Extract other details
            utr = data.get('utr', '')
            amount = data.get('amount', 0)
            
            result = {
                'success': True,
                'status': mapped_status,
                'order_id': data.get('order_id', order_id),
                'amount': float(amount) if amount else 0,
                'utr': utr,
                'transaction_time': data.get('transaction_time', ''),
                'message': 'Status retrieved successfully'
            }
            
            print(f"Parsed Risexpay Status: {result}")
            
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
    
    def auto_check_status_after_delay(self, order_id, delay_seconds=60):
        """
        Automatically check payment status after a delay
        This ensures status gets updated even if callback fails
        
        Args:
            order_id: The order ID to check
            delay_seconds: Delay before checking (default 60 seconds)
        """
        def check_status_task():
            try:
                print(f"[Risexpay Auto Status Check] Waiting {delay_seconds} seconds before checking {order_id}...")
                time.sleep(delay_seconds)
                
                print(f"[Risexpay Auto Status Check] Checking status for {order_id}...")
                
                # Get transaction from database
                conn = get_db_connection()
                if not conn:
                    print(f"[Risexpay Auto Status Check] Database connection failed")
                    return
                
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            SELECT txn_id, order_id, merchant_id, status, pg_txn_id, net_amount, charge_amount
                            FROM payin_transactions
                            WHERE pg_txn_id = %s AND pg_partner = 'RISEXPAY'
                        """, (order_id,))
                        
                        txn = cursor.fetchone()
                        
                        if not txn:
                            print(f"[Risexpay Auto Status Check] Transaction not found: {order_id}")
                            return
                        
                        # Only check if still pending
                        if txn['status'] not in ['INITIATED', 'PENDING']:
                            print(f"[Risexpay Auto Status Check] Transaction already {txn['status']}, skipping")
                            return
                        
                        print(f"[Risexpay Auto Status Check] Checking Risexpay with order_id: {order_id}")
                        
                        # Check status from Risexpay
                        status_result = self.check_payment_status(order_id)
                        
                        if not status_result.get('success'):
                            print(f"[Risexpay Auto Status Check] Status check failed: {status_result.get('message')}")
                            return
                        
                        risexpay_status = status_result.get('status', '').upper()
                        print(f"[Risexpay Auto Status Check] Risexpay status: {risexpay_status}")
                        
                        # Update if status changed to SUCCESS
                        if risexpay_status == 'SUCCESS' and txn['status'] != 'SUCCESS':
                            print(f"[Risexpay Auto Status Check] Updating {txn['txn_id']} to SUCCESS")
                            
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
                                    description=f"PayIn received (Risexpay Auto) - {order_id}",
                                    reference_id=txn['txn_id']
                                )
                                
                                if wallet_result['success']:
                                    print(f"[Risexpay Auto Status Check] ✓ Merchant wallet credited: ₹{txn['net_amount']}")
                                else:
                                    print(f"[Risexpay Auto Status Check] ✗ Failed to credit merchant wallet: {wallet_result.get('message')}")
                                
                                # Credit admin unsettled wallet with charge amount
                                admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                    admin_id='admin',
                                    amount=float(txn['charge_amount']),
                                    description=f"PayIn charge (Risexpay Auto) - {order_id}",
                                    reference_id=txn['txn_id']
                                )
                                
                                if admin_wallet_result['success']:
                                    print(f"[Risexpay Auto Status Check] ✓ Admin wallet credited: ₹{txn['charge_amount']}")
                                else:
                                    print(f"[Risexpay Auto Status Check] ✗ Failed to credit admin wallet: {admin_wallet_result.get('message')}")
                            else:
                                print(f"[Risexpay Auto Status Check] ⚠ Wallet already credited, skipping")
                            
                            conn.commit()
                            print(f"[Risexpay Auto Status Check] ✓ Successfully updated {txn['txn_id']} to SUCCESS")
                        
                        elif risexpay_status == 'FAILED' and txn['status'] != 'FAILED':
                            print(f"[Risexpay Auto Status Check] Updating {txn['txn_id']} to FAILED")
                            
                            cursor.execute("""
                                UPDATE payin_transactions
                                SET status = 'FAILED',
                                    completed_at = NOW(),
                                    updated_at = NOW()
                                WHERE txn_id = %s
                            """, (txn['txn_id'],))
                            
                            conn.commit()
                            print(f"[Risexpay Auto Status Check] ✓ Successfully updated {txn['txn_id']} to FAILED")
                        
                finally:
                    conn.close()
                    
            except Exception as e:
                print(f"[Risexpay Auto Status Check] Error: {e}")
                import traceback
                traceback.print_exc()
        
        # Start background thread
        thread = threading.Thread(target=check_status_task, daemon=True)
        thread.start()

# Create singleton instance
risexpay_service = RisexpayService()
