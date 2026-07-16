"""
OQPay Payment Gateway Integration Service
Handles payin transactions through OQPay
"""

import requests
import json
import os
import threading
import time
from datetime import datetime
from config import Config
from database import get_db_connection

class OQPayService:
    def __init__(self):
        self.base_url = Config.OQPAY_PAYIN_BASE_URL
        self.registration_id = Config.OQPAY_REGISTRATION_ID

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
        """Get request headers for OQPay API"""
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def calculate_charges(self, amount, scheme_id, service_type='PAYIN'):
        """Calculate charges based on scheme"""
        conn = None
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
            print(f"[OQPay] Calculate charges error: {e}")
            return None, None, None
        finally:
            if conn:
                conn.close()

    def create_payin_order(self, merchant_id, order_data):
        """
        Create payin order via OQPay
        order_data should contain:
        - amount
        - orderid
        - payee_fname
        - payee_lname (optional)
        - payee_mobile
        - payee_email
        """
        conn = None
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

                # Validate amount (Minimum amount ₹50 as per API docs)
                amount = float(order_data.get('amount', 0))
                if amount < 50:
                    return {'success': False, 'message': 'Amount cannot be less than ₹50'}

                # Calculate charges
                charge_amount, net_amount, charge_type = self.calculate_charges(
                    amount, merchant['scheme_id']
                )

                if charge_amount is None:
                    return {'success': False, 'message': 'Failed to calculate charges'}

                # Generate unique merchant order ID
                merchant_order_id = order_data.get('orderid') or \
                    f"OQPAY_{merchant_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

                # Create internal transaction ID
                txn_id = f"OQPAY_{merchant_id}_{merchant_order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

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

                print(f"[OQPay PayIn] Creating dynamic QR:")
                print(f"  Merchant: {merchant_id}")
                print(f"  Merchant Order ID: {merchant_order_id}")
                print(f"  Amount: ₹{amount}")
                print(f"  Customer: {customer_name} ({customer_mobile})")

                # Prepare OQPay API payload
                payload = {
                    'customerName': customer_name,
                    'customerMobile': customer_mobile,
                    'customerEmail': customer_email,
                    'amount': str(int(amount)), # Amount as string integer
                    'registrationID': self.registration_id
                }

                url = f"{self.base_url}/api/V1/Payin/DynamicQRCode"

                print(f"[OQPay PayIn] Sending request to: {url}")
                api_start = time.time()

                try:
                    response = self.session.post(
                        url,
                        headers=self.get_headers(),
                        json=payload,
                        timeout=(15, 60)  # 15s connect, 60s read
                    )

                    api_elapsed = time.time() - api_start
                    print(f"[OQPay PayIn] API Response Time: {api_elapsed:.2f}s")
                    print(f"[OQPay PayIn] Response Status: {response.status_code}")
                    print(f"[OQPay PayIn] Response: {response.text[:500]}")

                except requests.exceptions.ReadTimeout:
                    api_elapsed = time.time() - api_start
                    print(f"[OQPay PayIn] ⚠️ API Timeout after {api_elapsed:.2f}s")
                    return {
                        'success': False,
                        'message': 'Payment gateway timeout. Please try again.',
                        'error_type': 'TIMEOUT'
                    }

                if response.status_code not in [200, 201]:
                    error_msg = f'OQPay API error: {response.text}'
                    print(error_msg)
                    return {'success': False, 'message': error_msg}

                oqpay_response = response.json()
                print(f"[OQPay PayIn] Response JSON: {oqpay_response}")

                # Check response status
                status_field = oqpay_response.get('status', 'False')
                if status_field != 'True':
                    error_msg = oqpay_response.get('message', 'QR Code generation failed')
                    print(f"[OQPay PayIn] Failed: {error_msg}")
                    return {'success': False, 'message': error_msg}

                # Extract data from response
                oqpay_txn_ref_id = str(oqpay_response.get('txnRefranceID', '')).strip()
                upi_intend = oqpay_response.get('upiIntend', '')
                qr_id = oqpay_response.get('id', '')

                # Validate response fields
                if not upi_intend:
                    print(f"[OQPay PayIn] No upiIntend in response: {oqpay_response}")
                    return {'success': False, 'message': 'No UPI link received from OQPay'}

                # Map callback URL
                callback_url = order_data.get('callbackurl') or order_data.get('callback_url')
                if not callback_url:
                    base_url = os.getenv('BACKEND_URL', 'https://api.craftpay.in')
                    callback_url = f"{base_url}/api/callback/oqpay/payin"
                    print(f"⚠ No callback URL provided, using default: {callback_url}")

                # Insert transaction record. Store oqpay_txn_ref_id in pg_txn_id
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
                    'INITIATED', 'OQPAY', oqpay_txn_ref_id,
                    callback_url
                ))

                conn.commit()

                total_elapsed = time.time() - start_time
                print(f"[OQPay PayIn] ✓ Transaction created in {total_elapsed:.2f}s")
                print(f"  - TXN ID: {txn_id}")
                print(f"  - Merchant Order ID: {merchant_order_id}")
                print(f"  - OQPay Reference ID: {oqpay_txn_ref_id}")
                print(f"  - Amount: ₹{amount} (Net: ₹{net_amount}, Charge: ₹{charge_amount})")
                print(f"  - Callback URL: {callback_url}")
                print(f"  - UPI Intent: {upi_intend}")

                # Schedule automatic status checks
                self.auto_check_status_after_delay(oqpay_txn_ref_id, delay_seconds=60)
                self.auto_check_status_after_delay(oqpay_txn_ref_id, delay_seconds=120)
                self.auto_check_status_after_delay(oqpay_txn_ref_id, delay_seconds=180)
                print(f"[OQPay PayIn] ✓ Scheduled automatic status checks at 60s, 120s, 180s")

                return {
                    'success': True,
                    'txn_id': txn_id,
                    'order_id': merchant_order_id,
                    'merchant_order_id': merchant_order_id,
                    'amount': amount,
                    'charge_amount': charge_amount,
                    'net_amount': net_amount,
                    'upi_link': upi_intend,
                    'intent_url': upi_intend,
                    'qr_string': upi_intend,
                    'payment_link': upi_intend,
                    'pg_partner': 'OQPAY'
                }

        except requests.exceptions.Timeout as e:
            print(f"[OQPay PayIn] ❌ Timeout error: {e}")
            return {
                'success': False,
                'message': 'Payment gateway timeout. Please try again.',
                'error_type': 'TIMEOUT'
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[OQPay PayIn] ❌ Connection error: {e}")
            return {
                'success': False,
                'message': 'Unable to connect to payment gateway. Please try again later.',
                'error_type': 'CONNECTION_ERROR'
            }
        except Exception as e:
            print(f"[OQPay PayIn] ❌ Error: {e}")
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

    def check_payment_status(self, oqpay_txn_ref_id):
        """
        Check payment status on OQPay.
        Since OQPay does not document a check status API in the provided documentation,
        we read the latest status from our database to be safe. If status is updated
        via webhooks, it will reflect here.
        """
        try:
            print(f"[OQPay] Checking status - oqpay_txn_ref_id: {oqpay_txn_ref_id}")

            conn = get_db_connection()
            if not conn:
                return {'success': False, 'message': 'Database connection failed'}

            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT status, bank_ref_no, amount
                        FROM payin_transactions
                        WHERE pg_txn_id = %s AND pg_partner = 'OQPAY'
                        LIMIT 1
                    """, (oqpay_txn_ref_id,))

                    txn = cursor.fetchone()
                    if txn:
                        return {
                            'success': True,
                            'status': txn['status'],
                            'amount': float(txn['amount']),
                            'utr': txn.get('bank_ref_no', ''),
                            'message': 'Status retrieved from local records'
                        }
                    else:
                        return {
                            'success': False,
                            'message': 'Transaction not found in local database'
                        }
            finally:
                conn.close()

        except Exception as e:
            print(f"[OQPay] Local status check error: {e}")
            return {'success': False, 'message': f'Status check error: {str(e)}'}

    def auto_check_status_after_delay(self, oqpay_txn_ref_id, delay_seconds=60):
        """
        Automatically check payment status after a delay.
        For OQPay, because we do not have an active check status API,
        we query our DB to check if the webhook already succeeded.
        If still pending after a long time (e.g. 180s), we could mark it failed,
        but standard behavior in this app is to keep it pending or skip.
        """
        def check_status_task():
            try:
                print(f"[OQPay Auto Check] Waiting {delay_seconds}s before checking {oqpay_txn_ref_id}...")
                time.sleep(delay_seconds)

                conn = get_db_connection()
                if not conn:
                    print(f"[OQPay Auto Check] Database connection failed")
                    return

                try:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            SELECT txn_id, status
                            FROM payin_transactions
                            WHERE pg_txn_id = %s AND pg_partner = 'OQPAY'
                        """, (oqpay_txn_ref_id,))

                        txn = cursor.fetchone()
                        if not txn:
                            print(f"[OQPay Auto Check] Transaction not found: {oqpay_txn_ref_id}")
                            return

                        print(f"[OQPay Auto Check] Transaction {txn['txn_id']} status is {txn['status']}")
                finally:
                    conn.close()

            except Exception as e:
                print(f"[OQPay Auto Check] Error: {e}")

        # Start background thread
        thread = threading.Thread(target=check_status_task, daemon=True)
        thread.start()

# Create singleton instance
oqpay_service = OQPayService()
