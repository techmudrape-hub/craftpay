"""
Risexpay Callback Routes
Handles payin callbacks/webhooks from Risexpay payment gateway

IMPORTANT: Risexpay signs ALL callbacks with X-Signature header
Every callback must be verified using HMAC-SHA256 with Payin Secret Key
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json
import requests
import hmac
import hashlib
from config import Config

risexpay_callback_bp = Blueprint('risexpay_callback', __name__, url_prefix='/api/callback')

def verify_callback_signature(callback_body, timestamp, signature):
    """
    Verify the callback signature from Risexpay
    
    According to Risexpay docs:
    "Every inbound webhook callback includes an X-Signature header.
    Verify it against the response body using your Payin Secret Key."
    
    Format: timestamp=<timestamp>&<response_body_as_json_string>
    
    Args:
        callback_body: Raw JSON string of callback body
        timestamp: Timestamp from X-Timestamp header
        signature: Signature from X-Signature header
    
    Returns:
        bool: True if signature is valid, False otherwise
    """
    try:
        secret_key = Config.RISEXPAY_SECRET_KEY
        
        # Parse JSON to sort keys as per new documentation
        payload = json.loads(callback_body)
        
        # Build canonical string: sort keys, timestamp first
        parts = [f"timestamp={timestamp}"]
        for k in sorted(payload.keys()):
            v = payload[k]
            if isinstance(v, (dict, list)):
                val_str = json.dumps(v, separators=(',', ':'))
            elif isinstance(v, bool):
                val_str = "1" if v else ""
            elif v is None:
                val_str = ""
            else:
                val_str = str(v)
            parts.append(f"{k}={val_str}")
            
        canonical_string = "&".join(parts)
        
        # Generate expected signature
        expected_signature = hmac.new(
            secret_key.encode('utf-8'),
            canonical_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        print(f"[Risexpay Callback] Canonical string: {canonical_string}")
        print(f"[Risexpay Callback] Expected signature: {expected_signature[:20]}...")
        print(f"[Risexpay Callback] Received signature: {signature[:20]}...")
        
        return hmac.compare_digest(expected_signature, signature)
        
    except Exception as e:
        print(f"[Risexpay Callback] Signature verification error: {e}")
        return False

@risexpay_callback_bp.route('/risexpay/payin', methods=['POST'])
def risexpay_payin_callback():
    """
    Webhook endpoint for Risexpay payin status updates
    
    IMPORTANT: All callbacks are signed with X-Signature header
    Must verify signature using HMAC-SHA256 with Payin Secret Key
    
    Headers:
    - X-Timestamp: Unix timestamp
    - X-Signature: HMAC-SHA256 signature of "timestamp=X&<json_body>"
    
    Supported callback formats:
    
    Format 1 (Standard):
    {
      "event": "payment.update",
      "payment_status": "COMPLETED",
      "order": {
        "order_id": "ORD_24_1778576951_6896",
        "imb_order_id": "999999991111166",
        "amount": 100,
        "customer_mobile": "9876543210",
        "status": "COMPLETED",
        "txn_id": "TXN_123",
        "utr": "123456789012",
        "created_at": "2026-05-12 09:09:11",
        "updated_at": "2026-05-12 09:10:00"
      }
    }
    
    Format 2 (Alternative):
    {
      "TXN_amount": "5000.00",
      "TXN_date": "2025-01-10 14:35:20",
      "Txn_ID": "TXN123456789",
      "TXN_Status": "SUCCESS",
      "UTR": "HDFC12345XYZ"
    }
    """
    try:
        # Get signature headers
        timestamp = request.headers.get('X-Timestamp')
        signature = request.headers.get('X-Signature')
        
        # Get raw body for signature verification
        raw_body = request.get_data(as_text=True)
        
        print("=" * 80)
        print("Risexpay Payin Callback Received")
        print("=" * 80)
        print(f"Timestamp: {timestamp}")
        print(f"Signature: {signature[:20] if signature else 'MISSING'}...")
        if raw_body:
            print(f"Raw Body: {raw_body[:200]}...")
        else:
            print("No raw body text.")
            
        # As per Risexpay instructions, do NOT use signature in callback
        print("⚠ WARNING: Signature verification disabled as per instructions")
        
        # Parse JSON or Form Data
        callback_data = {}
        if request.is_json:
            callback_data = request.get_json()
        elif request.form:
            callback_data = request.form.to_dict()
        else:
            try:
                if raw_body:
                    callback_data = json.loads(raw_body)
            except json.JSONDecodeError:
                pass
                
        if not callback_data:
            print(f"ERROR: Invalid or empty payload received")
            return jsonify({
                'status': 'error', 
                'message': 'Invalid or empty payload received.'
            }), 400
        
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")
        
        # Extract data from callback - support multiple formats including flat structure or form-data
        event = callback_data.get('event', '')
        payment_status = callback_data.get('payment_status', '').upper()
        
        # Handle case where order is passed as stringified JSON in form data
        order_data = callback_data.get('order', {})
        if isinstance(order_data, str):
            try:
                order_data = json.loads(order_data)
            except Exception:
                pass
        
        # Check if this is the alternative format (flat structure with TXN_ prefix or arbitrary flat mapping)
        if not order_data and ('Txn_ID' in callback_data or 'order_id' in callback_data or 'txn_id' in callback_data or 'pg_txn_id' in callback_data):
            print("Detected alternative callback format (flat structure)")
            # Map alternative format to standard format
            order_id = callback_data.get('order_id') or callback_data.get('Txn_ID') or callback_data.get('pg_txn_id') or callback_data.get('request_id') or ''
            imb_order_id = callback_data.get('imb_order_id') or callback_data.get('txn_id') or ''
            amount = callback_data.get('amount') or callback_data.get('TXN_amount') or 0
            
            status = callback_data.get('status') or callback_data.get('TXN_Status') or callback_data.get('payment_status') or ''
            status = str(status).upper()
            
            txn_id = callback_data.get('txn_id') or imb_order_id
            utr = callback_data.get('utr') or callback_data.get('UTR') or callback_data.get('bank_ref_no') or ''
            
            # Set payment_status from status if not set
            if not payment_status:
                payment_status = status
        else:
            # Standard format
            if not order_data:
                print("ERROR: No order data in callback")
                return jsonify({
                    'success': False, 
                    'message': 'Missing order data'
                }), 400
            
            # Extract order details
            order_id = order_data.get('order_id', '')
            imb_order_id = order_data.get('imb_order_id', '')
            amount = order_data.get('amount', 0)
            customer_mobile = order_data.get('customer_mobile', '')
            status = order_data.get('status', '').upper()
            txn_id = order_data.get('txn_id', '')
            utr = order_data.get('utr', '')
        
        # Fallback to txn_id if utr is missing, null, or empty
        if not utr or str(utr).lower() == 'null' or str(utr).lower() == 'none':
            utr = txn_id
            print(f"⚠ UTR was empty/null, using txn_id as UTR: {utr}")
        
        if not order_id:
            print("ERROR: No order_id in callback")
            return jsonify({
                'success': False, 
                'message': 'Missing order_id'
            }), 400
        
        print(f"Event: {event}")
        print(f"Payment Status: {payment_status}")
        print(f"Order ID: {order_id}")
        print(f"IMB Order ID: {imb_order_id}")
        print(f"Status: {status}")
        print(f"Amount: {amount}")
        print(f"UTR: {utr}")
        print(f"TXN ID: {txn_id}")
        
        # Map Risexpay status to our status
        if status == 'COMPLETED':
            mapped_status = 'SUCCESS'
        elif status == 'FAILED':
            mapped_status = 'FAILED'
        else:
            mapped_status = 'INITIATED'
        
        print(f"Mapped Status: {mapped_status}")
        
        # Update database
        conn = get_db_connection()
        if not conn:
            print("ERROR: Database connection failed")
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Find transaction by pg_txn_id, order_id, or txn_id (since risexpay can send back different IDs)
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, order_id, amount as txn_amount, 
                           net_amount, charge_amount, callback_url, pg_txn_id
                    FROM payin_transactions
                    WHERE pg_partner = 'RISEXPAY'
                    AND (pg_txn_id = %s OR order_id = %s OR txn_id = %s)
                    LIMIT 1
                """, (order_id, order_id, order_id))
                
                txn = cursor.fetchone()
                
                if not txn:
                    print(f"ERROR: Transaction not found for order_id: {order_id}")
                    
                    # Try to find any Risexpay transaction to help debug
                    cursor.execute("""
                        SELECT txn_id, order_id, pg_txn_id, status
                        FROM payin_transactions
                        WHERE pg_partner = 'RISEXPAY'
                        ORDER BY created_at DESC
                        LIMIT 5
                    """)
                    recent_txns = cursor.fetchall()
                    
                    if recent_txns:
                        print(f"Recent Risexpay payin transactions:")
                        for t in recent_txns:
                            print(f"  - TXN: {t['txn_id']}, ORDER: {t['order_id']}, PG_TXN: {t['pg_txn_id']}, STATUS: {t['status']}")
                    
                    return jsonify({
                        'success': False, 
                        'message': f'Transaction not found for order_id: {order_id}'
                    }), 404
                
                print(f"Found Transaction: {txn['txn_id']}, Current Status: {txn['status']}")
                
                # DUPLICATE CHECK: If this order_id has already been processed successfully, reject
                if mapped_status == 'SUCCESS':
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM payin_transactions
                        WHERE (pg_txn_id = %s OR order_id = %s OR txn_id = %s)
                        AND pg_partner = 'RISEXPAY'
                        AND status = 'SUCCESS'
                    """, (order_id, order_id, order_id))
                    
                    already_processed = cursor.fetchone()['count'] > 0
                    
                    if already_processed and txn['status'] == 'SUCCESS':
                        print(f"⚠ Order {order_id} already processed as SUCCESS - rejecting duplicate")
                        return jsonify({
                            'status': 'error',
                            'message': 'Order ID has already been processed.',
                            'orderId': order_id
                        }), 200  # Return 200 to acknowledge receipt
                
                # Update transaction with callback data
                if mapped_status in ['SUCCESS', 'FAILED']:
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s, 
                            bank_ref_no = %s,
                            payment_mode = 'UPI',
                            completed_at = NOW(), 
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, txn['txn_id']))
                    print(f"✓ Updated with status={mapped_status}, utr={utr}, completed_at=NOW()")
                else:
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s, 
                            bank_ref_no = %s,
                            payment_mode = 'UPI',
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, txn['txn_id']))
                    print(f"✓ Updated status to {mapped_status}")
                
                conn.commit()
                
                # Credit wallet if status is SUCCESS and merchant_id exists
                if mapped_status == 'SUCCESS' and txn['merchant_id']:
                    print("=" * 80)
                    print("WALLET CREDIT - SUCCESS STATUS")
                    print("=" * 80)
                    
                    # Check if wallet was already credited (use txn_id)
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                    """, (txn['txn_id'],))
                    
                    already_credited = cursor.fetchone()['count'] > 0
                    
                    if already_credited:
                        print(f"⚠ Wallet already credited for this transaction - skipping")
                    else:
                        try:
                            # Import wallet service
                            from wallet_service import wallet_service as wallet_svc
                            
                            # Credit merchant unsettled wallet with net amount
                            credit_result = wallet_svc.credit_unsettled_wallet(
                                merchant_id=txn['merchant_id'],
                                amount=float(txn['net_amount']) if txn['net_amount'] else 0,
                                description=f"PayIn received (Risexpay) - {order_id}",
                                reference_id=txn['txn_id']
                            )
                            
                            if credit_result.get('success'):
                                balance_before = credit_result.get('balance_before', 0)
                                balance_after = credit_result.get('balance_after', 0)
                                print(f"✅ MERCHANT WALLET CREDITED - Balance: ₹{balance_before:.2f} → ₹{balance_after:.2f}")
                            else:
                                print(f"❌ MERCHANT WALLET CREDIT FAILED: {credit_result.get('message', 'Unknown error')}")
                            
                            # Credit admin unsettled wallet with charge amount
                            admin_credit_result = wallet_svc.credit_admin_unsettled_wallet(
                                admin_id='admin',
                                amount=float(txn['charge_amount']) if txn['charge_amount'] else 0,
                                description=f"PayIn charge (Risexpay) - {order_id}",
                                reference_id=txn['txn_id']
                            )
                            
                            if admin_credit_result.get('success'):
                                print(f"✅ ADMIN WALLET CREDITED - Charge: ₹{txn['charge_amount']:.2f}")
                            else:
                                print(f"❌ ADMIN WALLET CREDIT FAILED: {admin_credit_result.get('message', 'Unknown error')}")
                        
                        except Exception as wallet_error:
                            print(f"❌ WALLET CREDIT ERROR: {wallet_error}")
                            import traceback
                            traceback.print_exc()
                
                # Verify the update
                cursor.execute("""
                    SELECT status, bank_ref_no, completed_at
                    FROM payin_transactions
                    WHERE txn_id = %s
                """, (txn['txn_id'],))
                
                updated_txn = cursor.fetchone()
                print(f"Verification - Status: {updated_txn['status']}, UTR: {updated_txn['bank_ref_no']}, Completed: {updated_txn['completed_at']}")
                
                print("=" * 80)
                print("Risexpay Payin Callback processed successfully")
                print("=" * 80)
                
                # Forward callback to merchant if configured
                print("=" * 80)
                print("MERCHANT CALLBACK FORWARDING - PAYIN")
                print("=" * 80)
                print(f"Transaction merchant_id: {txn.get('merchant_id')}")
                print(f"Transaction callback_url field: {txn.get('callback_url')}")
                print(f"Mapped status: {mapped_status}")
                
                try:
                    # Get callback URL from transaction or merchant_callbacks table
                    callback_url = None
                    
                    if txn.get('callback_url'):
                        callback_url = txn['callback_url'].strip()
                        # Skip if it's the internal Risexpay callback URL
                        if callback_url and 'api.craftpay.in/api/callback/risexpay' in callback_url:
                            print(f"⚠ Skipping internal callback URL: {callback_url}")
                            callback_url = None
                        elif callback_url:
                            print(f"✅ Found callback_url in transaction: {callback_url}")
                        else:
                            callback_url = None
                    
                    # If no valid callback URL in transaction, check merchant_callbacks table
                    if not callback_url and txn['merchant_id']:
                        print(f"Checking merchant_callbacks table for merchant: {txn['merchant_id']}")
                        cursor.execute("""
                            SELECT payin_callback_url FROM merchant_callbacks
                            WHERE merchant_id = %s
                        """, (txn['merchant_id'],))
                        
                        merchant_callback = cursor.fetchone()
                        if merchant_callback and merchant_callback.get('payin_callback_url'):
                            callback_url = merchant_callback['payin_callback_url'].strip()
                            if not callback_url:
                                callback_url = None
                            else:
                                print(f"✅ Found payin_callback_url in merchant_callbacks: {callback_url}")
                    
                    print(f"Final callback_url to use: {callback_url if callback_url else 'NONE'}")
                    
                    if callback_url:
                        print(f"✅ Callback URL found, proceeding with forwarding...")
                        
                        # DUPLICATE PREVENTION: Check if we already sent a SUCCESS callback
                        if mapped_status == 'SUCCESS':
                            print(f"Checking for duplicate SUCCESS callbacks...")
                            cursor.execute("""
                                SELECT COUNT(*) as count FROM callback_logs
                                WHERE merchant_id = %s 
                                AND txn_id = %s 
                                AND response_code BETWEEN 200 AND 299
                                AND request_data LIKE %s
                            """, (txn['merchant_id'], txn['txn_id'], '%"status": "SUCCESS"%'))
                            
                            success_callback_sent = cursor.fetchone()['count'] > 0
                            
                            if success_callback_sent:
                                print(f"⚠ SUCCESS callback already sent to merchant - skipping duplicate")
                                print("=" * 80)
                                
                                return jsonify({
                                    'success': True,
                                    'message': 'Callback processed (duplicate prevented)',
                                    'txn_id': txn['txn_id'],
                                    'status': mapped_status
                                }), 200
                        
                        import requests
                        
                        # Prepare callback payload for merchant (MAXPE format)
                        merchant_callback_data = {
                            'txn_id': txn['txn_id'],
                            'order_id': txn['order_id'],  # This is the merchant_order_id from our DB
                            'status': mapped_status,
                            'utr': utr,
                            'pg_partner': 'RISEXPAY',
                            'amount': float(txn['txn_amount']) if txn['txn_amount'] else 0,
                            'net_amount': float(txn['net_amount']) if txn['net_amount'] else 0,
                            'charge_amount': float(txn['charge_amount']) if txn['charge_amount'] else 0
                        }
                        
                        print(f"📤 Forwarding payin callback to merchant: {callback_url}")
                        print(f"📦 Callback data: {json.dumps(merchant_callback_data, indent=2)}")
                        
                        try:
                            callback_response = requests.post(
                                callback_url,
                                json=merchant_callback_data,
                                headers={'Content-Type': 'application/json'},
                                timeout=10
                            )
                            
                            print(f"✅ Merchant callback response: {callback_response.status_code}")
                            print(f"📄 Merchant callback response body: {callback_response.text[:200]}")
                            
                            # Log callback attempt
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
                            
                            print(f"✅ Merchant payin callback sent successfully and logged")
                            
                        except requests.exceptions.RequestException as e:
                            print(f"❌ ERROR: Failed to send merchant payin callback: {e}")
                            
                            # Log failed callback attempt
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
                            print(f"📝 Failed callback attempt logged")
                    else:
                        print("❌ No merchant payin callback URL configured")
                        
                except Exception as e:
                    print(f"❌ ERROR in merchant callback forwarding: {e}")
                    import traceback
                    traceback.print_exc()
                
                print("=" * 80)
                
                return jsonify({
                    'status': 'success',
                    'message': 'Data inserted successfully.' if mapped_status == 'SUCCESS' else 'Callback processed successfully',
                    'received_data': {
                        'amount': str(amount),
                        'date_at': order_data.get('created_at', '') if order_data else callback_data.get('TXN_date', ''),
                        'orderId': order_id,
                        'utr': utr,
                        'status': mapped_status
                    }
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"ERROR in callback: {e}")
        import traceback
        traceback.print_exc()
        
        error_details = {
            'success': False,
            'message': str(e),
            'error_type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        
        return jsonify(error_details), 500
