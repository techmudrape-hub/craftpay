"""
Maxpe Payment Gateway Integration Service
Handles payin transactions through Maxpe
"""

import requests
import json
import os
import threading
import time
import hmac
import hashlib
from datetime import datetime
from urllib.parse import urlencode
from config import Config
from database import get_db_connection
import uuid

class MaxpeService:
    def __init__(self):
        self.base_url = Config.MAXPE_BASE_URL
        self.api_key = Config.MAXPE_API_KEY
        self.api_secret = Config.MAXPE_API_SECRET
        
        # Create session with connection pooling and retry logic
        self.session = requests.Session()
        
        # Configure retry strategy
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        # IMPORTANT: Don't retry on read timeouts - MaxPe API is just slow
        # Only retry on connection errors and 5xx server errors
        retry_strategy = Retry(
            total=2,  # Reduced retries (was 3)
            backoff_factor=2,  # Wait 2, 4 seconds between retries
            status_forcelist=[500, 502, 503, 504],  # Retry on server errors only
            allowed_methods=["POST", "GET"],
            raise_on_status=False,  # Don't raise exception on retry
            # Don't retry on read timeout - let it fail fast
            respect_retry_after_header=True
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20,
            pool_block=False  # Don't block when pool is full
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def generate_signature(self, data_to_sign):
        """
        Generate HMAC SHA256 signature for Maxpe API
        
        Args:
            data_to_sign: Dictionary containing fields to sign
        
        Returns:
            str: HMAC SHA256 signature
        """
        # Sort keys alphabetically
        sorted_keys = sorted(data_to_sign.keys())
        
        # Build canonical string: key=value&key=value
        canonical_parts = []
        for key in sorted_keys:
            value = str(data_to_sign[key])
            canonical_parts.append(f"{key}={value}")
        
        canonical_string = "&".join(canonical_parts)
        
        # Generate HMAC SHA256 signature
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            canonical_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def get_headers(self, timestamp, nonce, signature):
        """
        Get request headers for Maxpe API
        All requests require API key, timestamp, nonce, and signature
        """
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-API-KEY': self.api_key,
            'X-TIMESTAMP': str(timestamp),
            'X-NONCE': nonce,
            'X-SIGNATURE': signature
        }
        return headers
    
    def generate_nonce(self):
        """Generate unique nonce for request"""
        return uuid.uuid4().hex[:16]
    
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
        Create payin order via Maxpe
        order_data should contain:
        - amount
        - orderid
        - payee_fname
        - payee_lname (optional)
        - payee_mobile
        - payee_email
        
        Returns immediately with payment link, processes status check in background
        """
        try:
            # Start timing for performance monitoring
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
                merchant_order_id = order_data.get('orderid') or f"MAXPE_{merchant_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Create internal transaction ID
                txn_id = f"MAXPE_{merchant_id}_{merchant_order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
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
                
                # Generate timestamp and nonce
                timestamp = int(time.time())
                nonce = self.generate_nonce()
                
                # Generate a random VPA
                import random
                import string
                random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
                payer_vpa = order_data.get('payer_vpa') or f"usr{random_string}@okaxis"
                
                # Amount must be a whole number in rupees (MaxPe requirement)
                amount_str = str(int(amount))
                
                # Prepare payload for signature
                data_to_sign = {
                    'amount': amount_str,
                    'email': customer_email.strip(),
                    'mobile': customer_mobile.strip(),
                    'name': customer_name.strip(),
                    'nonce': nonce,
                    'payer_vpa': payer_vpa,
                    'timestamp': str(timestamp),
                    'merchant_order_id': merchant_order_id.strip()
                }
                
                # Generate signature
                signature = self.generate_signature(data_to_sign)
                
                print(f"[MaxPe PayIn] Creating payment order:")
                print(f"  Merchant: {merchant_id}")
                print(f"  Merchant Order ID: {merchant_order_id}")
                print(f"  Amount: ₹{amount}")
                print(f"  Customer: {customer_name} ({customer_mobile})")
                print(f"  Timestamp: {timestamp}")
                print(f"  Nonce: {nonce}")
                print(f"  Signature: {signature[:20]}...")
                
                # Prepare request payload (without nonce and timestamp - they go in headers)
                # amount_str must exactly match what was used in the signature
                payload = {
                    'name': customer_name.strip(),
                    'mobile': customer_mobile.strip(),
                    'email': customer_email.strip(),
                    'amount': amount_str,
                    'payer_vpa': payer_vpa,
                    'merchant_order_id': merchant_order_id.strip()
                }
                
                # Create payment order
                url = f"{self.base_url}/api/prod/payin/v1/create-payment"
                
                print(f"[MaxPe PayIn] Sending request to: {url}")
                api_start = time.time()
                
                # Use session with connection pooling and VERY generous timeout
                # MaxPe API is extremely slow - needs up to 120 seconds
                # timeout=(connect_timeout, read_timeout)
                try:
                    response = self.session.post(
                        url,
                        headers=self.get_headers(timestamp, nonce, signature),
                        json=payload,
                        timeout=(15, 120)  # 15s to connect, 120s to read response (2 minutes)
                    )
                    
                    api_elapsed = time.time() - api_start
                    print(f"[MaxPe PayIn] API Response Time: {api_elapsed:.2f}s")
                    print(f"[MaxPe PayIn] Response Status: {response.status_code}")
                    print(f"[MaxPe PayIn] Response: {response.text[:500]}")
                    
                except requests.exceptions.ReadTimeout:
                    # If MaxPe times out, save transaction as INITIATED and rely on callback
                    api_elapsed = time.time() - api_start
                    print(f"[MaxPe PayIn] ⚠️ API Timeout after {api_elapsed:.2f}s - saving as INITIATED")
                    print(f"[MaxPe PayIn] Transaction will be updated via callback or status check")
                    
                    # Save transaction as INITIATED - callback will update it
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
                        'INITIATED', 'MAXPE', merchant_order_id,
                        callback_url
                    ))
                    
                    conn.commit()
                    
                    # Schedule aggressive status checks since we don't have payment link
                    self.auto_check_status_after_delay(merchant_order_id, delay_seconds=30)
                    self.auto_check_status_after_delay(merchant_order_id, delay_seconds=60)
                    self.auto_check_status_after_delay(merchant_order_id, delay_seconds=120)
                    
                    return {
                        'success': False,
                        'message': 'Payment gateway timeout. Transaction saved. Please check status in a few minutes.',
                        'error_type': 'TIMEOUT',
                        'txn_id': txn_id,
                        'order_id': merchant_order_id,
                        'status_check_scheduled': True
                    }
                
                if response.status_code not in [200, 201]:
                    error_msg = f'Maxpe API error: {response.text}'
                    print(error_msg)
                    return {'success': False, 'message': error_msg}
                
                maxpe_response = response.json()
                print(f"Maxpe Response JSON: {maxpe_response}")
                
                if not maxpe_response.get('status'):
                    error_msg = maxpe_response.get('message', 'Payment order creation failed')
                    print(f"Maxpe payment order creation failed: {error_msg}")
                    return {'success': False, 'message': error_msg}
                
                # Extract data from response
                upi_deeplink = maxpe_response.get('payment_url', maxpe_response.get('upi_deeplink', ''))
                
                # Validate that we got the payment link
                if not upi_deeplink:
                    print(f"No payment link in response: {maxpe_response}")
                    return {'success': False, 'message': 'No payment link received from Maxpe'}
                
                # Extract callback URL from order_data
                callback_url = order_data.get('callbackurl') or order_data.get('callback_url')
                
                if not callback_url:
                    # Use default internal callback URL
                    base_url = os.getenv('BACKEND_URL', 'https://api.craftpay.in')
                    callback_url = f"{base_url}/api/callback/maxpe/payin"
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
                    'INITIATED', 'MAXPE', merchant_order_id,
                    callback_url
                ))
                
                print(f"✓ Transaction created:")
                print(f"  - TXN ID: {txn_id}")
                print(f"  - Merchant Order ID: {merchant_order_id}")
                print(f"  - Callback URL: {callback_url}")
                
                conn.commit()
                
                total_elapsed = time.time() - start_time
                print(f"[MaxPe PayIn] ✓ Transaction created in {total_elapsed:.2f}s")
                print(f"  - TXN ID: {txn_id}")
                print(f"  - Merchant Order ID: {merchant_order_id}")
                print(f"  - Amount: ₹{amount} (Net: ₹{net_amount}, Charge: ₹{charge_amount})")
                print(f"  - Callback URL: {callback_url}")
                print(f"  - UPI Link: {upi_deeplink[:50]}...")
                
                # Schedule multiple automatic status checks for reliability
                # Check at 60s, 120s, and 180s to catch delayed callbacks
                self.auto_check_status_after_delay(merchant_order_id, delay_seconds=60)
                self.auto_check_status_after_delay(merchant_order_id, delay_seconds=120)
                self.auto_check_status_after_delay(merchant_order_id, delay_seconds=180)
                print(f"[MaxPe PayIn] ✓ Scheduled automatic status checks at 60s, 120s, 180s")
                
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
                    'qr_string': upi_deeplink,  # For backward compatibility
                    'payment_link': upi_deeplink,
                    'pg_partner': 'MAXPE'
                }
                
        except requests.exceptions.Timeout as e:
            print(f"[MaxPe PayIn] ❌ Timeout error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False, 
                'message': 'Payment gateway timeout. Please try again or check transaction status after a few minutes.',
                'error_type': 'TIMEOUT'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[MaxPe PayIn] ❌ Connection error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False, 
                'message': 'Unable to connect to payment gateway. Please try again later.',
                'error_type': 'CONNECTION_ERROR'
            }
        except Exception as e:
            print(f"[MaxPe PayIn] ❌ Error: {e}")
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
        Check payment status on Maxpe
        
        Args:
            merchant_order_id: The merchant order ID
        
        Returns:
            dict: Status information
        """
        try:
            print(f"Checking Maxpe payment status - merchant_order_id: {merchant_order_id}")
            
            url = f"{self.base_url}/api/prod/payin/v1/status"
            
            # Status check uses form data and only requires X-API-KEY header
            headers = {
                'X-API-KEY': self.api_key
            }
            
            payload = {
                'merchant_order_id': merchant_order_id
            }
            
            print(f"Status check payload: {payload}")
            
            # Use session with retry logic and increased timeout
            response = self.session.post(
                url,
                headers=headers,
                data=payload,  # Use form data, not JSON
                timeout=(10, 60)  # (connect timeout, read timeout) in seconds
            )
            
            print(f"Response: {response.status_code} - {response.text[:500]}")
            
            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'Status check failed: {response.text}'
                }
            
            maxpe_response = response.json()
            
            # Extract data from Maxpe response
            if not maxpe_response.get('status'):
                return {
                    'success': False,
                    'message': maxpe_response.get('message', 'Status check failed')
                }
            
            data = maxpe_response.get('data', {})
            
            # Extract status
            transaction_status = data.get('transaction_status', 'PENDING').upper()
            
            # Map Maxpe status to our status
            if transaction_status == 'SUCCESS':
                mapped_status = 'SUCCESS'
            elif transaction_status == 'FAILED':
                mapped_status = 'FAILED'
            else:
                mapped_status = 'INITIATED'
            
            # Extract other details
            amount = data.get('amount', '0')
            utr = data.get('utr', '')
            created_at = data.get('created_at', '')
            
            result = {
                'success': True,
                'status': mapped_status,
                'merchant_order_id': data.get('merchant_order_id', merchant_order_id),
                'amount': float(amount) if amount else 0,
                'utr': utr,
                'created_at': created_at,
                'message': maxpe_response.get('message', 'Status retrieved successfully')
            }
            
            print(f"Parsed Maxpe Status: {result}")
            
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
                print(f"[Maxpe Auto Status Check] Waiting {delay_seconds} seconds before checking {merchant_order_id}...")
                time.sleep(delay_seconds)
                
                print(f"[Maxpe Auto Status Check] Checking status for {merchant_order_id}...")
                
                # Get transaction from database
                conn = get_db_connection()
                if not conn:
                    print(f"[Maxpe Auto Status Check] Database connection failed")
                    return
                
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            SELECT txn_id, order_id, merchant_id, status, pg_txn_id, net_amount, charge_amount
                            FROM payin_transactions
                            WHERE order_id = %s AND pg_partner = 'MAXPE'
                        """, (merchant_order_id,))
                        
                        txn = cursor.fetchone()
                        
                        if not txn:
                            print(f"[Maxpe Auto Status Check] Transaction not found: {merchant_order_id}")
                            return
                        
                        # Only check if still pending
                        if txn['status'] not in ['INITIATED', 'PENDING']:
                            print(f"[Maxpe Auto Status Check] Transaction already {txn['status']}, skipping")
                            return
                        
                        print(f"[Maxpe Auto Status Check] Checking Maxpe with merchant_order_id: {merchant_order_id}")
                        
                        # Check status from Maxpe
                        status_result = self.check_payment_status(merchant_order_id)
                        
                        if not status_result.get('success'):
                            print(f"[Maxpe Auto Status Check] Status check failed: {status_result.get('message')}")
                            return
                        
                        maxpe_status = status_result.get('status', '').upper()
                        print(f"[Maxpe Auto Status Check] Maxpe status: {maxpe_status}")
                        
                        # Update if status changed to SUCCESS
                        if maxpe_status == 'SUCCESS' and txn['status'] != 'SUCCESS':
                            print(f"[Maxpe Auto Status Check] Updating {txn['txn_id']} to SUCCESS")
                            
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
                                    description=f"PayIn received (Maxpe Auto) - {merchant_order_id}",
                                    reference_id=txn['txn_id']
                                )
                                
                                if wallet_result['success']:
                                    print(f"[Maxpe Auto Status Check] ✓ Merchant wallet credited: ₹{txn['net_amount']}")
                                else:
                                    print(f"[Maxpe Auto Status Check] ✗ Failed to credit merchant wallet: {wallet_result.get('message')}")
                                
                                # Credit admin unsettled wallet with charge amount
                                admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                    admin_id='admin',
                                    amount=float(txn['charge_amount']),
                                    description=f"PayIn charge (Maxpe Auto) - {merchant_order_id}",
                                    reference_id=txn['txn_id']
                                )
                                
                                if admin_wallet_result['success']:
                                    print(f"[Maxpe Auto Status Check] ✓ Admin wallet credited: ₹{txn['charge_amount']}")
                                else:
                                    print(f"[Maxpe Auto Status Check] ✗ Failed to credit admin wallet: {admin_wallet_result.get('message')}")
                            else:
                                print(f"[Maxpe Auto Status Check] ⚠ Wallet already credited, skipping")
                            
                            conn.commit()
                            print(f"[Maxpe Auto Status Check] ✓ Successfully updated {txn['txn_id']} to SUCCESS")
                        
                        elif maxpe_status == 'FAILED' and txn['status'] != 'FAILED':
                            print(f"[Maxpe Auto Status Check] Updating {txn['txn_id']} to FAILED")
                            
                            cursor.execute("""
                                UPDATE payin_transactions
                                SET status = 'FAILED',
                                    completed_at = NOW(),
                                    updated_at = NOW()
                                WHERE txn_id = %s
                            """, (txn['txn_id'],))
                            
                            conn.commit()
                            print(f"[Maxpe Auto Status Check] ✓ Updated {txn['txn_id']} to FAILED")
                        else:
                            print(f"[Maxpe Auto Status Check] Status unchanged: {maxpe_status}")
                        
                finally:
                    conn.close()
                    
            except Exception as e:
                print(f"[Maxpe Auto Status Check] Error: {e}")
                import traceback
                traceback.print_exc()
        
        # Start background thread
        thread = threading.Thread(target=check_status_task, daemon=True)
        thread.start()
        print(f"[Maxpe Auto Status Check] Scheduled status check for {merchant_order_id} in {delay_seconds} seconds")


# Create singleton instance
maxpe_service = MaxpeService()
