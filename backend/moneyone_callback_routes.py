"""
MoneyOne Callback Routes
Handles callbacks from MoneyOne payment gateway
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json
import requests

moneyone_callback_bp = Blueprint('moneyone_callback', __name__, url_prefix='/api/callback')

@moneyone_callback_bp.route('/moneyone/payin', methods=['POST'])
def moneyone_payin_callback():
    """
    Webhook endpoint for MoneyOne payin status updates
    MoneyOne will call this when payment status changes
    """
    try:
        # Get callback data from MoneyOne
        callback_data = request.json
        
        print("=" * 80)
        print("MoneyOne Payin Callback Received")
        print("=" * 80)
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")
        
        # Extract data from callback
        order_id = callback_data.get('order_id') or callback_data.get('orderid')
        txn_id = callback_data.get('txn_id')
        status = callback_data.get('status', 'INITIATED').upper()
        utr = callback_data.get('utr') or callback_data.get('bank_ref_no')
        payment_mode = callback_data.get('payment_mode', 'UPI')
        amount = callback_data.get('amount')
        
        if not order_id:
            print("ERROR: No order_id in callback")
            return jsonify({'success': False, 'message': 'Missing order_id'}), 400
        
        print(f"Order ID: {order_id}")
        print(f"TXN ID: {txn_id}")
        print(f"Status: {status}")
        print(f"UTR: {utr}")
        print(f"Payment Mode: {payment_mode}")
        print(f"Amount: {amount}")
        
        # Map status
        if status == 'PENDING':
            status = 'INITIATED'
        
        # Update database
        conn = get_db_connection()
        if not conn:
            print("ERROR: Database connection failed")
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Find transaction by order_id
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, net_amount, charge_amount
                    FROM payin_transactions
                    WHERE order_id = %s AND pg_partner = 'MoneyOne'
                """, (order_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    print(f"ERROR: Transaction not found for order_id: {order_id}")
                    return jsonify({'success': False, 'message': 'Transaction not found'}), 404
                
                print(f"Found Transaction: {txn['txn_id']}, Current Status: {txn['status']}")
                
                # Update transaction status
                if status == 'SUCCESS':
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                            completed_at = NOW(), updated_at = NOW()
                        WHERE txn_id = %s
                    """, (status, utr, txn_id, payment_mode, txn['txn_id']))
                    
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
                            description=f"PayIn received (MoneyOne) - {order_id}",
                            reference_id=txn['txn_id']
                        )
                        
                        if wallet_result['success']:
                            print(f"✓ Merchant unsettled wallet credited: ₹{txn['net_amount']}")
                        else:
                            print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")
                        
                        # Credit admin unsettled wallet with charge amount
                        admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                            admin_id='admin',
                            amount=float(txn['charge_amount']),
                            description=f"PayIn charge (MoneyOne) - {order_id}",
                            reference_id=txn['txn_id']
                        )
                        
                        if admin_wallet_result['success']:
                            print(f"✓ Admin unsettled wallet credited: ₹{txn['charge_amount']}")
                        else:
                            print(f"✗ Failed to credit admin unsettled wallet: {admin_wallet_result.get('message')}")
                    else:
                        print(f"⚠ Wallet already credited for this transaction - skipping")
                    
                elif status == 'FAILED':
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                            completed_at = NOW(), updated_at = NOW()
                        WHERE txn_id = %s
                    """, (status, utr, txn_id, payment_mode, txn['txn_id']))
                else:
                    # Still pending/initiated
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s, updated_at = NOW()
                        WHERE txn_id = %s
                    """, (status, utr, txn_id, payment_mode, txn['txn_id']))
                
                conn.commit()
                
                print(f"✓ Updated transaction {txn['txn_id']} to {status}")
                print("=" * 80)
                
                # Forward callback to merchant if configured
                print("=" * 80)
                print(f"MERCHANT CALLBACK FORWARDING - MoneyOne")
                print("=" * 80)
                try:
                    # First, get the callback URL from the transaction itself (sent in payload)
                    cursor.execute("""
                        SELECT callback_url FROM payin_transactions
                        WHERE order_id = %s
                    """, (order_id,))
                    
                    txn_callback = cursor.fetchone()
                    callback_url = None
                    
                    if txn_callback and txn_callback.get('callback_url'):
                        callback_url = txn_callback['callback_url'].strip()
                        if not callback_url:  # Empty string after strip
                            callback_url = None
                    
                    print(f"Step 1: Transaction callback_url from DB: {callback_url if callback_url else 'NOT SET'}")
                    
                    # If no callback URL in transaction, check merchant_callbacks table
                    if not callback_url:
                        print(f"Step 2: Checking merchant_callbacks table for merchant: {txn['merchant_id']}")
                        cursor.execute("""
                            SELECT payin_callback_url FROM merchant_callbacks
                            WHERE merchant_id = %s
                        """, (txn['merchant_id'],))
                        
                        merchant_callback = cursor.fetchone()
                        if merchant_callback and merchant_callback.get('payin_callback_url'):
                            callback_url = merchant_callback['payin_callback_url'].strip()
                            if not callback_url:  # Empty string after strip
                                callback_url = None
                        
                        print(f"Step 2: Merchant payin_callback_url: {callback_url if callback_url else 'NOT SET'}")
                    
                    if callback_url:
                        # DUPLICATE PREVENTION: Check if we already sent a SUCCESS callback for this transaction
                        if status == 'SUCCESS':
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
                                print(f"  This is a duplicate callback from MoneyOne")
                                print("=" * 80)
                                
                                return jsonify({
                                    'success': True,
                                    'message': 'Callback processed (duplicate prevented)',
                                    'txn_id': txn['txn_id'],
                                    'status': status
                                }), 200
                        
                        import requests
                        
                        # Prepare callback payload for merchant (matching standard format)
                        merchant_callback_data = {
                            'utr': utr or '',
                            'amount': float(amount) if amount else float(txn.get('amount', 0)),
                            'ref_id': order_id,
                            'source': 'MoneyOne',
                            'status': status,
                            'txn_id': txn['txn_id'],  # Our internal txn_id
                            'pg_txn_id': txn_id or '',  # MoneyOne's txn_id
                            'pg_partner': 'MoneyOne',
                            'payeeVpa': '',
                            'timestamp': datetime.now().isoformat(),
                            'order_id': order_id  # Keep for backward compatibility
                        }
                        
                        print(f"Forwarding MoneyOne callback to merchant: {callback_url}")
                        print(f"Callback data: {json.dumps(merchant_callback_data, indent=2)}")
                        
                        try:
                            callback_response = requests.post(
                                callback_url,
                                json=merchant_callback_data,
                                headers={'Content-Type': 'application/json'},
                                timeout=10
                            )
                            
                            print(f"Merchant callback response: {callback_response.status_code}")
                            print(f"Merchant callback response body: {callback_response.text[:200]}")
                            
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
                                callback_response.text[:1000]  # Limit response data
                            ))
                            conn.commit()
                            
                            print(f"✓ MoneyOne merchant callback sent successfully and logged")
                            
                        except requests.exceptions.RequestException as e:
                            print(f"ERROR: Failed to send MoneyOne merchant callback: {e}")
                            
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
                    else:
                        print(f"⚠ No callback URL configured for merchant {txn['merchant_id']}")
                        print(f"  Skipping merchant callback forwarding")
                    
                except Exception as callback_error:
                    print(f"ERROR in merchant callback forwarding: {callback_error}")
                    import traceback
                    traceback.print_exc()
                    # Don't fail the main callback if merchant forwarding fails
                
                print("=" * 80)
                
                return jsonify({
                    'success': True,
                    'message': 'Callback processed successfully'
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"MoneyOne Payin Callback Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal server error'}), 500
