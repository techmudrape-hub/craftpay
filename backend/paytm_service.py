"""
Paytm Payment Gateway Integration Service
Handles payin transactions through Paytm Payment Links
"""

import requests
import json
import os
import threading
import time
import hmac
import hashlib
import base64
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from config import Config
from database import get_db_connection

class PaytmService:
    def __init__(self):
        self.base_url = Config.PAYTM_BASE_URL  # https://securestage.paytmpayments.com or https://secure.paytm.in for production
        self.merchant_id = Config.PAYTM_MERCHANT_ID
        self.merchant_key = Config.PAYTM_MERCHANT_KEY  # For checksum generation
        
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
    
    def generate_checksum(self, body_dict):
        """
        Generate Paytm checksum for request body
        Uses SHA256 hashing and AES128 encryption as per Paytm specification
        
        Paytm Checksum Algorithm:
        1. Convert body to JSON string
        2. Generate SHA256 hash of the JSON string
        3. Encrypt the hash using AES-128-CBC with merchant key
        4. Base64 encode the encrypted data
        
        Args:
            body_dict: Dictionary containing request body
        
        Returns:
            str: Base64 encoded checksum
        """
        try:
            # Step 1: Convert body to JSON string (compact format, no spaces)
            body_json = json.dumps(body_dict, separators=(',', ':'), sort_keys=True)
            
            print(f"[Checksum] Body JSON: {body_json[:200]}...")
            
            # Step 2: Generate SHA256 hash
            sha256_hash = hashlib.sha256(body_json.encode('utf-8')).hexdigest()
            print(f"[Checksum] SHA256 Hash: {sha256_hash[:40]}...")
            
            # Step 3: Prepare AES encryption
            # Paytm uses AES-128-CBC encryption
            # Key must be 16 bytes (128 bits) for AES-128
            key = self.merchant_key.encode('utf-8')[:16]  # Use first 16 bytes
            iv = key  # Use same key as IV (as per Paytm specification)
            
            print(f"[Checksum] Key length: {len(key)} bytes")
            
            # Create cipher
            cipher = AES.new(key, AES.MODE_CBC, iv)
            
            # Step 4: Pad and encrypt the hash
            padded_hash = pad(sha256_hash.encode('utf-8'), AES.block_size)
            encrypted = cipher.encrypt(padded_hash)
            
            # Step 5: Base64 encode
            checksum = base64.b64encode(encrypted).decode('utf-8')
            
            print(f"[Checksum] Generated checksum: {checksum[:40]}...")
            
            return checksum
            
        except Exception as e:
            print(f"Generate checksum error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def verify_checksum(self, body_dict, checksum):
        """
        Verify Paytm checksum from callback
        Uses SHA256 hashing and AES128 decryption
        
        Args:
            body_dict: Dictionary containing callback body (without CHECKSUMHASH)
            checksum: Checksum to verify
        
        Returns:
            bool: True if checksum is valid
        """
        try:
            # Remove CHECKSUMHASH from body if present
            body_copy = {k: v for k, v in body_dict.items() if k != 'CHECKSUMHASH'}
            
            # Generate checksum for comparison
            generated_checksum = self.generate_checksum(body_copy)
            
            if not generated_checksum:
                print("[Checksum Verify] Failed to generate checksum for comparison")
                return False
            
            # Compare checksums
            is_valid = generated_checksum == checksum
            
            if is_valid:
                print("[Checksum Verify] ✓ Checksum is valid")
            else:
                print("[Checksum Verify] ✗ Checksum mismatch")
                print(f"  Expected: {checksum[:40]}...")
                print(f"  Generated: {generated_checksum[:40]}...")
            
            return is_valid
            
        except Exception as e:
            print(f"Verify checksum error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_headers(self):
        """Get request headers for Paytm API"""
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
        Create payin order via Paytm Payment Link
        order_data should contain:
        - amount
        - orderid (optional - will be generated if not provided)
        - payee_fname
        - payee_mobile
        - payee_email
        - productinfo (optional)
        - callbackurl (optional)
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
                merchant_order_id = order_data.get('orderid') or f"PAYTM_{merchant_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Create internal transaction ID
                txn_id = f"PAYTM_{merchant_id}_{merchant_order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
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
                
                # Prepare callback URL - ALWAYS include in API request
                # This works even without dashboard configuration
                callback_url = order_data.get('callbackurl') or order_data.get('callback_url')
                if not callback_url:
                    base_url = os.getenv('BACKEND_URL', 'https://api.craftpay.in')
                    callback_url = f"{base_url}/api/callback/paytm/payin"
                    print(f"⚠ No callback URL provided, using default: {callback_url}")
                
                print(f"[Paytm PayIn] Creating payment link:")
                print(f"  Merchant: {merchant_id}")
                print(f"  Merchant Order ID: {merchant_order_id}")
                print(f"  Amount: ₹{amount}")
                print(f"  Customer: {customer_name} ({customer_mobile})")
                print(f"  Callback URL: {callback_url}")
                
                # Prepare Paytm Payment Link payload
                # Paytm expects timestamp in EPOCH format (15 digits)
                timestamp = str(int(time.time() * 1000))  # Milliseconds
                
                # Prepare body - ALWAYS include statusCallbackUrl in request
                body = {
                    'mid': self.merchant_id,
                    'linkType': 'GENERIC',
                    'linkDescription': order_data.get('productinfo', 'Payment'),
                    'linkName': f"Payment_{merchant_order_id}",
                    'amount': str(amount),
                    'customerContact': {
                        'customerId': merchant_order_id,
                        'customerName': customer_name,
                        'customerEmail': customer_email,
                        'customerMobile': customer_mobile
                    },
                    'statusCallbackUrl': callback_url,  # ALWAYS passed in API request body
                    'partialPayment': 'false',
                    'bindLinkIdMobile': True
                }
                
                # Generate checksum
                checksum = self.generate_checksum(body)
                
                if not checksum:
                    return {'success': False, 'message': 'Failed to generate checksum'}
                
                # Prepare request payload
                payload = {
                    'head': {
                        'tokenType': 'AES',
                        'signature': checksum,
                        'timestamp': timestamp
                    },
                    'body': body
                }
                
                # Create payment link
                url = f"{self.base_url}/link/create"
                
                print(f"[Paytm PayIn] Sending request to: {url}")
                print(f"[Paytm PayIn] Payload: {json.dumps(payload, indent=2)}")
                api_start = time.time()
                
                try:
                    response = self.session.post(
                        url,
                        headers=self.get_headers(),
                        json=payload,
                        timeout=(15, 60)  # 15s to connect, 60s to read response
                    )
                    
                    api_elapsed = time.time() - api_start
                    print(f"[Paytm PayIn] API Response Time: {api_elapsed:.2f}s")
                    print(f"[Paytm PayIn] Response Status: {response.status_code}")
                    print(f"[Paytm PayIn] Response: {response.text[:500]}")
                    
                except requests.exceptions.ReadTimeout:
                    api_elapsed = time.time() - api_start
                    print(f"[Paytm PayIn] ⚠️ API Timeout after {api_elapsed:.2f}s")
                    return {
                        'success': False,
                        'message': 'Payment gateway timeout. Please try again.',
                        'error_type': 'TIMEOUT'
                    }
                
                if response.status_code not in [200, 201]:
                    error_msg = f'Paytm API error: {response.text}'
                    print(error_msg)
                    return {'success': False, 'message': error_msg}
                
                paytm_response = response.json()
                print(f"Paytm Response JSON: {json.dumps(paytm_response, indent=2)}")
                
                # Extract data from response
                response_body = paytm_response.get('body', {})
                result_info = response_body.get('resultInfo', {})
                
                # Check if link creation was successful
                if result_info.get('resultStatus') != 'SUCCESS':
                    error_msg = result_info.get('resultMessage', 'Payment link creation failed')
                    print(f"Paytm payment link creation failed: {error_msg}")
                    return {'success': False, 'message': error_msg}
                
                # Extract link details
                link_id = response_body.get('linkId', '')
                short_url = response_body.get('shortUrl', '')
                long_url = response_body.get('longUrl', '')
                is_active = response_body.get('isActive', False)
                
                # Use short URL as payment link
                payment_link = short_url or long_url
                
                # Validate that we got the payment link
                if not payment_link:
                    print(f"No payment link in response: {paytm_response}")
                    return {'success': False, 'message': 'No payment link received from Paytm'}
                
                # Map status to our database ENUM
                db_status = 'INITIATED' if is_active else 'FAILED'
                
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
                    db_status, 'PAYTM', str(link_id),
                    callback_url
                ))
                
                conn.commit()
                
                total_elapsed = time.time() - start_time
                print(f"[Paytm PayIn] ✓ Transaction created in {total_elapsed:.2f}s")
                print(f"  - TXN ID: {txn_id}")
                print(f"  - Merchant Order ID: {merchant_order_id}")
                print(f"  - Link ID: {link_id}")
                print(f"  - Amount: ₹{amount} (Net: ₹{net_amount}, Charge: ₹{charge_amount})")
                print(f"  - Callback URL: {callback_url}")
                print(f"  - Payment Link: {payment_link}")
                
                # Schedule automatic status checks
                self.auto_check_status_after_delay(str(link_id), delay_seconds=60)
                self.auto_check_status_after_delay(str(link_id), delay_seconds=120)
                self.auto_check_status_after_delay(str(link_id), delay_seconds=180)
                print(f"[Paytm PayIn] ✓ Scheduled automatic status checks at 60s, 120s, 180s")
                
                return {
                    'success': True,
                    'txn_id': txn_id,
                    'order_id': merchant_order_id,
                    'merchant_order_id': merchant_order_id,
                    'amount': amount,
                    'charge_amount': charge_amount,
                    'net_amount': net_amount,
                    'upi_link': payment_link,
                    'intent_url': payment_link,
                    'qr_string': payment_link,
                    'payment_link': payment_link,
                    'link_id': str(link_id),
                    'pg_partner': 'PAYTM'
                }
                
        except requests.exceptions.Timeout as e:
            print(f"[Paytm PayIn] ❌ Timeout error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False, 
                'message': 'Payment gateway timeout. Please try again.',
                'error_type': 'TIMEOUT'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[Paytm PayIn] ❌ Connection error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False, 
                'message': 'Unable to connect to payment gateway. Please try again later.',
                'error_type': 'CONNECTION_ERROR'
            }
        except Exception as e:
            print(f"[Paytm PayIn] ❌ Error: {e}")
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
    
    def check_payment_status(self, link_id):
        """
        Check payment status on Paytm
        
        Args:
            link_id: The Paytm link ID
        
        Returns:
            dict: Status information
        """
        try:
            print(f"Checking Paytm payment status - link_id: {link_id}")
            
            # Paytm doesn't have a direct status check API for payment links
            # Status updates come via callback
            # This is a placeholder for future implementation
            
            return {
                'success': False,
                'message': 'Status check not available. Please wait for callback.'
            }
            
        except Exception as e:
            print(f"Check payment status error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'Status check error: {str(e)}'}
    
    def auto_check_status_after_delay(self, link_id, delay_seconds=60):
        """
        Automatically check payment status after a delay
        This ensures status gets updated even if callback fails
        
        Args:
            link_id: The Paytm link ID to check
            delay_seconds: Delay before checking (default 60 seconds)
        """
        def check_status_task():
            try:
                print(f"[Paytm Auto Status Check] Waiting {delay_seconds} seconds before checking {link_id}...")
                time.sleep(delay_seconds)
                
                print(f"[Paytm Auto Status Check] Status check for Paytm relies on callback")
                # Paytm doesn't have a status check API
                # Status updates come via callback only
                
            except Exception as e:
                print(f"[Paytm Auto Status Check] Error: {e}")
        
        # Start background thread
        thread = threading.Thread(target=check_status_task, daemon=True)
        thread.start()

# Create singleton instance
paytm_service = PaytmService()
