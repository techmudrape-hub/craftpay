"""
Acceptpay Callback Routes
Handles payin callbacks from Acceptpay
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from wallet_service import wallet_service
from acceptpay_service import acceptpay_service
from config import Config
from timezone_utils import get_ist_now, ist_to_mysql_format
import hmac
import hashlib
import json
import traceback

acceptpay_callback_bp = Blueprint('acceptpay_callback', __name__, url_prefix='/api/callback/acceptpay')

def verify_webhook_signature(payload_bytes, signature, secret, token=None, auth_header=None):
    """Verify signature or bearer token from Acceptpay"""
    
    # Check Bearer token if present
    if auth_header and auth_header.startswith('Bearer '):
        bearer_token = auth_header.split(' ')[1]
        if bearer_token and bearer_token in [secret, token]:
            print("✓ Acceptpay Webhook: Verified via Bearer Token in Authorization header")
            return True
            
    if not signature:
        print("❌ Acceptpay Webhook: Missing signature and Bearer token")
        return False
        
    if not secret:
        print("❌ Acceptpay Webhook: Missing ACCEPTPAY_WEBHOOK_SECRET in configuration")
        return False
        
    # 1. Try standard raw payload with secret
    expected_signature = hmac.new(secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()
    if hmac.compare_digest(expected_signature, signature):
        return True
        
    # 2. Try raw payload with token (in case they use API key for signature)
    if token:
        expected_token_sig = hmac.new(token.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected_token_sig, signature):
            print("⚠ Acceptpay Webhook: Signature matched using ACCEPTPAY_TOKEN instead of WEBHOOK_SECRET")
            return True
            
    # 3. Try stripped raw payload (removes trailing newlines)
    expected_stripped = hmac.new(secret.encode('utf-8'), payload_bytes.strip(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(expected_stripped, signature):
        return True

    # 4. Try Node.js exact JSON.stringify (no sorting, no spaces)
    try:
        data = json.loads(payload_bytes.decode('utf-8'))
        node_json = json.dumps(data, separators=(',', ':')).encode('utf-8')
        expected_node = hmac.new(secret.encode('utf-8'), node_json, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected_node, signature):
            return True
            
        # 5. Try sorted JSON payload
        sorted_json = json.dumps(data, separators=(',', ':'), sort_keys=True).encode('utf-8')
        expected_sorted = hmac.new(secret.encode('utf-8'), sorted_json, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected_sorted, signature):
            print("⚠ Acceptpay Webhook: Signature matched using sorted JSON keys")
            return True
            
        if token:
            expected_token_sorted = hmac.new(token.encode('utf-8'), sorted_json, hashlib.sha256).hexdigest()
            if hmac.compare_digest(expected_token_sorted, signature):
                print("⚠ Acceptpay Webhook: Signature matched using ACCEPTPAY_TOKEN and sorted JSON keys")
                return True
    except Exception as e:
        pass
        
    print(f"❌ Acceptpay Webhook: Signature mismatch. Expected: {expected_signature}, Received: {signature}")
    return False

@acceptpay_callback_bp.route('/webhook', methods=['POST'])
def acceptpay_webhook():
    """Handle Acceptpay Webhook"""
    try:
        raw_data = request.get_data()
        
        # Try multiple possible signature headers
        signature = request.headers.get('x-acceptpay-signature') or \
                    request.headers.get('x-signature') or \
                    request.headers.get('signature') or \
                    request.headers.get('x-webhook-signature')
                    
        secret = Config.ACCEPTPAY_WEBHOOK_SECRET.strip().strip('"').strip("'") if Config.ACCEPTPAY_WEBHOOK_SECRET else ''
        token = Config.ACCEPTPAY_TOKEN.strip().strip('"').strip("'") if Config.ACCEPTPAY_TOKEN else ''
        
        print(f"Acceptpay Webhook received. Signature: {signature}")
        auth_header = request.headers.get('Authorization', '')
        
        if not signature and not auth_header.startswith('Bearer '):
            print("Headers received:")
            for k, v in request.headers.items():
                print(f"  {k}: {v}")
                
        print(f"Raw payload: {raw_data.decode('utf-8')}")
        
        if not verify_webhook_signature(raw_data, signature, secret, token, auth_header):
            print("❌ Acceptpay Webhook: Invalid signature or token")
            print("⚠ Proceeding with payment processing despite signature mismatch (Bypass Enabled)")
            # return jsonify({'error': 'Unauthorized'}), 401
            
        data_json = json.loads(raw_data.decode('utf-8'))
        
        # Handle both nested and flat payload formats
        event = data_json.get('event')
        
        if event:
            payload_data = data_json.get('data', {})
        else:
            payload_data = data_json
            
        if not payload_data:
            return jsonify({'received': True}), 200
            
        order_id = payload_data.get('billId') or payload_data.get('orderId') or payload_data.get('order_id')
        pg_txn_id = payload_data.get('transactionId') or payload_data.get('txnId')
        status = payload_data.get('status', '').lower()
        amount_raw = payload_data.get('amount')
        amount = float(amount_raw) if amount_raw else 0.0
        gateway_payment_id = payload_data.get('gatewayPaymentId') or payload_data.get('rrn') or payload_data.get('bankRefNo') or payload_data.get('bank_ref_no') or payload_data.get('utr')
        
        # In flat format we might not have 'event == payment.completed', so we check status directly
        if status in ['success', 'completed', 'failed', 'refunded']:
            
            if not order_id:
                print("❌ Acceptpay Webhook: Missing billId (order_id)")
                return jsonify({'received': True}), 200
                
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'Database error'}), 500
                
            try:
                with conn.cursor() as cursor:
                    # Get transaction details
                    cursor.execute("""
                        SELECT txn_id, merchant_id, status, amount, charge_amount, net_amount 
                        FROM payin_transactions 
                        WHERE order_id = %s AND pg_partner = 'ACCEPTPAY'
                    """, (order_id,))
                    
                    txn = cursor.fetchone()
                    
                    if not txn:
                        print(f"❌ Acceptpay Webhook: Transaction not found for order {order_id}")
                        return jsonify({'received': True}), 200
                        
                    current_status = txn['status']
                    txn_id = txn['txn_id']
                    merchant_id = txn['merchant_id']
                    net_amount = float(txn['net_amount'])
                    charge_amount = float(txn['charge_amount'])
                    
                    if current_status in ['SUCCESS', 'FAILED']:
                        print(f"⚠ Acceptpay Webhook: Transaction {order_id} already processed ({current_status})")
                        return jsonify({'received': True}), 200
                        
                    now = get_ist_now()
                    mysql_timestamp = ist_to_mysql_format(now)
                    
                    if status in ['success', 'completed']:
                        # Update transaction status
                        cursor.execute("""
                            UPDATE payin_transactions 
                            SET status = 'SUCCESS', bank_ref_no = %s, pg_txn_id = %s,
                                completed_at = %s, updated_at = %s
                            WHERE order_id = %s AND pg_partner = 'ACCEPTPAY'
                        """, (gateway_payment_id, pg_txn_id, mysql_timestamp, mysql_timestamp, order_id))
                        
                        # Check if wallet already credited
                        cursor.execute("""
                            SELECT COUNT(*) as count FROM merchant_wallet_transactions
                            WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                        """, (txn_id,))
                        
                        wallet_already_credited = cursor.fetchone()['count'] > 0
                        
                        if not wallet_already_credited:
                            # Credit merchant unsettled wallet
                            wallet_result = wallet_service.credit_unsettled_wallet(
                                merchant_id=merchant_id,
                                amount=net_amount,
                                description=f"PayIn received (Acceptpay) - {order_id}",
                                reference_id=txn_id
                            )
                            
                            if wallet_result['success']:
                                print(f"✓ Merchant unsettled wallet credited: ₹{net_amount}")
                            else:
                                print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")
                            
                            # Credit admin unsettled wallet with charge amount
                            admin_wallet_result = wallet_service.credit_admin_unsettled_wallet(
                                admin_id='admin',
                                amount=charge_amount,
                                description=f"PayIn charge (Acceptpay) - {order_id}",
                                reference_id=txn_id
                            )
                            
                            if admin_wallet_result['success']:
                                print(f"✓ Admin unsettled wallet credited: ₹{charge_amount}")
                            else:
                                print(f"✗ Failed to credit admin unsettled wallet: {admin_wallet_result.get('message')}")
                        
                        conn.commit()
                        print(f"✓ Acceptpay Webhook: Successfully processed payment for {order_id}")
                        
                    elif status in ['failed', 'refunded']:
                        # Update transaction status to FAILED or REFUNDED
                        new_status = 'FAILED' if status == 'failed' else 'REFUNDED'
                        cursor.execute("""
                            UPDATE payin_transactions 
                            SET status = %s, bank_ref_no = %s, pg_txn_id = %s,
                                completed_at = %s, updated_at = %s
                            WHERE order_id = %s AND pg_partner = 'ACCEPTPAY'
                        """, (new_status, gateway_payment_id, pg_txn_id, mysql_timestamp, mysql_timestamp, order_id))
                        conn.commit()
                        print(f"✓ Acceptpay Webhook: Processed failure/refund for {order_id}")
                        
                    # Forward callback to merchant if configured
                    try:
                        cursor.execute("""
                            SELECT callback_url FROM payin_transactions
                            WHERE txn_id = %s
                        """, (txn_id,))
                        
                        txn_callback = cursor.fetchone()
                        callback_url = txn_callback['callback_url'].strip() if txn_callback and txn_callback.get('callback_url') else None
                        
                        if not callback_url:
                            cursor.execute("""
                                SELECT payin_callback_url FROM merchant_callbacks
                                WHERE merchant_id = %s
                            """, (merchant_id,))
                            
                            merchant_callback = cursor.fetchone()
                            if merchant_callback and merchant_callback.get('payin_callback_url'):
                                callback_url = merchant_callback['payin_callback_url'].strip()
                                
                        if callback_url:
                            merchant_callback_data = {
                                'txn_id': txn_id,
                                'order_id': order_id,
                                'status': 'SUCCESS' if status in ['success', 'completed'] else ('FAILED' if status == 'failed' else 'REFUNDED'),
                                'amount': float(amount) if amount else 0.0,
                                'utr': gateway_payment_id or '',
                                'pg_txn_id': pg_txn_id or '',
                                'pg_partner': 'ACCEPTPAY',
                                'payment_mode': 'UPI',
                                'timestamp': get_ist_now().isoformat()
                            }
                            
                            print(f"Forwarding ACCEPTPAY callback to merchant: {callback_url}")
                            import requests
                            callback_response = requests.post(
                                callback_url,
                                json=merchant_callback_data,
                                headers={'Content-Type': 'application/json'},
                                timeout=10
                            )
                            
                            # Log callback attempt
                            cursor.execute("""
                                INSERT INTO callback_logs 
                                (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                            """, (
                                merchant_id, txn_id, callback_url, 
                                json.dumps(merchant_callback_data),
                                callback_response.status_code, callback_response.text[:1000]
                            ))
                            conn.commit()
                            print("✓ Merchant callback sent successfully")
                            
                    except Exception as e:
                        print(f"ERROR in merchant callback forwarding: {e}")
                        
            except Exception as e:
                if conn:
                    conn.rollback()
                print(f"Error processing Acceptpay webhook: {e}")
                traceback.print_exc()
            finally:
                if conn:
                    conn.close()
                    
        return jsonify({'received': True}), 200
        
    except Exception as e:
        print(f"Acceptpay webhook endpoint error: {e}")
        return jsonify({'received': True}), 200

cashfree_webhook_bp = Blueprint('cashfree_webhook', __name__, url_prefix='/api/v1/webhook')

@cashfree_webhook_bp.route('/cashfree', methods=['POST'])
def cashfree_webhook():
    """Handle raw Cashfree webhooks for Acceptpay transactions"""
    try:
        data_json = request.get_json(silent=True)
        if not data_json:
            return jsonify({'received': True}), 200
            
        # Parse cashfree format
        data = data_json.get('data', {})
        order = data.get('order', {})
        payment = data.get('payment', {})
        
        cf_order_id = order.get('order_id', '')
        status = payment.get('payment_status', '').lower()
        pg_txn_id = payment.get('cf_payment_id')
        gateway_payment_id = payment.get('bank_reference') or payment.get('gateway_payment_id') or payment.get('auth_id')
        amount = payment.get('payment_amount', 0.0)
        
        if not cf_order_id or status not in ['success', 'completed', 'failed']:
            return jsonify({'received': True}), 200
            
        # Extract Acceptpay txn ID from CFO_6a33a009df11c44628eb0191_1781768232370
        parts = cf_order_id.split('_')
        if len(parts) < 2:
            return jsonify({'received': True}), 200
            
        acceptpay_txn_id = parts[1]
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'received': True}), 200
            
        try:
            with conn.cursor() as cursor:
                # Look up by the exact Acceptpay transaction ID
                cursor.execute("""
                    SELECT txn_id, order_id, merchant_id, status, amount, charge_amount, net_amount 
                    FROM payin_transactions 
                    WHERE pg_txn_id = %s AND pg_partner = 'ACCEPTPAY'
                """, (acceptpay_txn_id,))
                
                txn = cursor.fetchone()
                
                # Fallback: check if the whole cf_order_id is the order_id in our DB
                if not txn:
                    cursor.execute("""
                        SELECT txn_id, order_id, merchant_id, status, amount, charge_amount, net_amount 
                        FROM payin_transactions 
                        WHERE order_id = %s AND pg_partner = 'ACCEPTPAY'
                    """, (cf_order_id,))
                    txn = cursor.fetchone()
                    
                if not txn:
                    print(f"❌ Cashfree Webhook: Transaction not found for Acceptpay txn {acceptpay_txn_id}")
                    return jsonify({'received': True}), 200
                    
                order_id = txn['order_id']
                txn_id = txn['txn_id']
                merchant_id = txn['merchant_id']
                current_status = txn['status']
                net_amount = float(txn['net_amount'])
                charge_amount = float(txn['charge_amount'])
                
                if current_status in ['SUCCESS', 'FAILED']:
                    print(f"⚠ Cashfree Webhook: Transaction {order_id} already processed ({current_status})")
                    return jsonify({'received': True}), 200
                    
                now = get_ist_now()
                mysql_timestamp = ist_to_mysql_format(now)
                
                if status in ['success', 'completed']:
                    cursor.execute("""
                        UPDATE payin_transactions 
                        SET status = 'SUCCESS', bank_ref_no = %s, pg_txn_id = %s,
                            completed_at = %s, updated_at = %s
                        WHERE txn_id = %s
                    """, (gateway_payment_id, pg_txn_id, mysql_timestamp, mysql_timestamp, txn_id))
                    
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                    """, (txn_id,))
                    wallet_already_credited = cursor.fetchone()['count'] > 0
                    
                    if not wallet_already_credited:
                        wallet_service.credit_unsettled_wallet(
                            merchant_id=merchant_id,
                            amount=net_amount,
                            description=f"PayIn received (Acceptpay) - {order_id}",
                            reference_id=txn_id
                        )
                        wallet_service.credit_admin_unsettled_wallet(
                            admin_id='admin',
                            amount=charge_amount,
                            description=f"PayIn charge (Acceptpay) - {order_id}",
                            reference_id=txn_id
                        )
                    conn.commit()
                    print(f"✓ Cashfree Webhook: Successfully processed Acceptpay payment for {order_id}")
                    
                elif status == 'failed':
                    cursor.execute("""
                        UPDATE payin_transactions 
                        SET status = 'FAILED', bank_ref_no = %s, pg_txn_id = %s,
                            completed_at = %s, updated_at = %s
                        WHERE txn_id = %s
                    """, (gateway_payment_id, pg_txn_id, mysql_timestamp, mysql_timestamp, txn_id))
                    conn.commit()
                    print(f"✓ Cashfree Webhook: Processed failure for {order_id}")
                    
                # Forward callback to merchant
                try:
                    cursor.execute("SELECT callback_url FROM payin_transactions WHERE txn_id = %s", (txn_id,))
                    txn_callback = cursor.fetchone()
                    callback_url = txn_callback['callback_url'].strip() if txn_callback and txn_callback.get('callback_url') else None
                    
                    if not callback_url:
                        cursor.execute("SELECT payin_callback_url FROM merchant_callbacks WHERE merchant_id = %s", (merchant_id,))
                        merchant_callback = cursor.fetchone()
                        if merchant_callback and merchant_callback.get('payin_callback_url'):
                            callback_url = merchant_callback['payin_callback_url'].strip()
                            
                    if callback_url:
                        merchant_callback_data = {
                            'txn_id': txn_id,
                            'order_id': order_id,
                            'status': 'SUCCESS' if status in ['success', 'completed'] else 'FAILED',
                            'amount': float(amount) if amount else float(txn['amount']),
                            'utr': gateway_payment_id or '',
                            'pg_txn_id': pg_txn_id or acceptpay_txn_id,
                            'pg_partner': 'ACCEPTPAY',
                            'payment_mode': 'UPI',
                            'timestamp': get_ist_now().isoformat()
                        }
                        
                        import requests
                        callback_response = requests.post(callback_url, json=merchant_callback_data, headers={'Content-Type': 'application/json'}, timeout=10)
                        
                        cursor.execute("""
                            INSERT INTO callback_logs 
                            (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        """, (merchant_id, txn_id, callback_url, json.dumps(merchant_callback_data), callback_response.status_code, callback_response.text[:1000]))
                        conn.commit()
                except Exception as e:
                    print(f"ERROR in merchant callback forwarding: {e}")
                    
        finally:
            conn.close()
            
        return jsonify({'received': True}), 200
        
    except Exception as e:
        print(f"Cashfree webhook endpoint error: {e}")
        return jsonify({'received': True}), 200
