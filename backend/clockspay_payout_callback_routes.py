"""
ClocksPay Payout Callback Routes
Handles payout status callbacks from ClocksPay
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json

clockspay_payout_callback_bp = Blueprint('clockspay_payout_callback', __name__, url_prefix='/api/callback')

@clockspay_payout_callback_bp.route('/clockspay/payout', methods=['GET', 'POST'])
def clockspay_payout_callback():
    """
    Webhook endpoint for ClocksPay payout status updates
    
    Expected callback format (from docs - GET request with query parameters):
    {
      order_id: Merchant Payout Order ID
      status: success | failed | unknown
      amount: Payout Amount (excluding charges)
      mobile: Beneficiary Mobile Number (optional)
      utr: Bank UTR / RRN (only for success)
      redirect_url: Merchant Redirect URL (if available)
    }
    
    Sample Callback URL:
    https://merchant.com/payout-callback?order_id=PY100002&status=success&amount=500&mobile=9876543210&utr=UTR987654321&redirect_url=https://merchant.com/return
    """
    try:
        # Get callback data - ClocksPay sends via GET request with query parameters
        callback_data = None
        data_source = None
        
        # Try GET parameters first (as per docs)
        if request.args:
            callback_data = request.args.to_dict()
            data_source = "GET"
        # Also support POST for flexibility
        elif request.method == 'POST':
            try:
                callback_data = request.get_json(force=True, silent=True)
                if callback_data:
                    data_source = "JSON"
            except:
                pass
            
            if not callback_data and request.form:
                callback_data = request.form.to_dict()
                data_source = "FORM"
        
        if not callback_data:
            raw_data = request.get_data(as_text=True)
            print(f"[ClocksPay Payout Callback] ERROR: No data received")
            print(f"Method: {request.method}")
            print(f"Content-Type: {request.content_type}")
            print(f"Query String: {request.query_string}")
            print(f"Raw data: {raw_data[:500]}")
            return jsonify({
                'success': False,
                'message': 'No data received in request'
            }), 400
        
        print("=" * 80)
        print("ClocksPay Payout Callback Received")
        print("=" * 80)
        print(f"Method: {request.method}")
        print(f"Data Source: {data_source}")
        print(f"Content-Type: {request.content_type}")
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")
        
        # Extract data from callback
        merchant_order_id = callback_data.get('order_id')
        status = callback_data.get('status', '').lower()
        amount = callback_data.get('amount')
        mobile = callback_data.get('mobile', '')
        utr = callback_data.get('utr', '')
        redirect_url = callback_data.get('redirect_url', '')
        
        if not merchant_order_id:
            print(f"[ClocksPay Payout Callback] ERROR: No order_id in callback")
            return jsonify({
                'success': False,
                'message': 'Missing order_id',
                'received_keys': list(callback_data.keys())
            }), 400
        
        print(f"Merchant Order ID: {merchant_order_id}")
        print(f"Status: {status}")
        print(f"Amount: {amount}")
        print(f"Mobile: {mobile}")
        print(f"UTR: {utr}")
        
        # Map ClocksPay status to our status
        # Database ENUM: INITIATED, QUEUED, INPROCESS, SUCCESS, FAILED, REVERSED
        if status == 'success':
            mapped_status = 'SUCCESS'
        elif status == 'failed':
            mapped_status = 'FAILED'
        elif status == 'unknown':
            mapped_status = 'INITIATED'
        else:
            mapped_status = 'INITIATED'
        
        print(f"Mapped Status: {mapped_status}")
        
        # Update database
        conn = get_db_connection()
        if not conn:
            print("[ClocksPay Payout Callback] ERROR: Database connection failed")
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Find transaction by reference_id OR order_id
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, reference_id, amount as txn_amount, 
                           callback_url, net_amount, order_id, pg_partner
                    FROM payout_transactions
                    WHERE pg_partner = 'CLOCKSPAY'
                    AND reference_id = %s
                    LIMIT 1
                """, (merchant_order_id,))
                
                txn = cursor.fetchone()
                
                # If not found by reference_id, try order_id
                if not txn:
                    print(f"[ClocksPay Payout Callback] Transaction not found by reference_id, trying order_id...")
                    cursor.execute("""
                        SELECT txn_id, status, merchant_id, reference_id, amount as txn_amount, 
                               callback_url, net_amount, order_id, pg_partner
                        FROM payout_transactions
                        WHERE pg_partner = 'CLOCKSPAY'
                        AND order_id = %s
                        LIMIT 1
                    """, (merchant_order_id,))
                    
                    txn = cursor.fetchone()
                
                # If still not found, try pg_txn_id
                if not txn:
                    print(f"[ClocksPay Payout Callback] Transaction not found by order_id, trying pg_txn_id...")
                    cursor.execute("""
                        SELECT txn_id, status, merchant_id, reference_id, amount as txn_amount, 
                               callback_url, net_amount, order_id, pg_partner
                        FROM payout_transactions
                        WHERE pg_partner = 'CLOCKSPAY'
                        AND pg_txn_id = %s
                        LIMIT 1
                    """, (merchant_order_id,))
                    
                    txn = cursor.fetchone()
                
                if not txn:
                    print(f"[ClocksPay Payout Callback] ERROR: Transaction not found for order_id: {merchant_order_id}")
                    
                    # Try to find any ClocksPay transaction to help debug
                    cursor.execute("""
                        SELECT txn_id, reference_id, order_id, pg_txn_id, status
                        FROM payout_transactions
                        WHERE pg_partner = 'CLOCKSPAY'
                        ORDER BY created_at DESC
                        LIMIT 5
                    """)
                    recent_txns = cursor.fetchall()
                    
                    if recent_txns:
                        print(f"Recent ClocksPay payout transactions:")
                        for t in recent_txns:
                            print(f"  - TXN: {t['txn_id']}, REF: {t['reference_id']}, ORDER: {t['order_id']}, PG_TXN: {t['pg_txn_id']}, STATUS: {t['status']}")
                    
                    return jsonify({
                        'success': False,
                        'message': f'Transaction not found for order_id: {merchant_order_id}'
                    }), 404
                
                print(f"Found Transaction: {txn['txn_id']}, Current Status: {txn['status']}")
                
                # Check if this is a duplicate callback
                if txn['status'] == mapped_status and mapped_status == 'SUCCESS':
                    print(f"⚠ Duplicate SUCCESS callback - transaction already processed")
                    return jsonify({
                        'success': True,
                        'message': 'Callback already processed',
                        'txn_id': txn['txn_id'],
                        'status': mapped_status
                    }), 200
                
                # Update transaction with callback data
                if mapped_status in ['SUCCESS', 'FAILED']:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s,
                            utr = %s,
                            completed_at = NOW(),
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, txn['txn_id']))
                    print(f"✓ Updated with status={mapped_status}, utr={utr}, completed_at=NOW()")
                else:
                    # Status is still pending/initiated
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s,
                            utr = %s,
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, txn['txn_id']))
                    print(f"✓ Updated status to {mapped_status}")
                
                conn.commit()
                
                # Deduct wallet if status is SUCCESS and merchant_id exists
                if mapped_status == 'SUCCESS' and txn['merchant_id']:
                    print("=" * 80)
                    print("WALLET DEDUCTION - SUCCESS STATUS")
                    print("=" * 80)
                    
                    # Check if wallet was already deducted (use txn_id, not reference_id)
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'DEBIT'
                    """, (txn['txn_id'],))
                    
                    already_debited = cursor.fetchone()['count'] > 0
                    
                    if already_debited:
                        print(f"⚠ Wallet already debited for this transaction - skipping")
                    else:
                        # Import wallet service
                        from wallet_service import WalletService
                        wallet_svc = WalletService()
                        
                        # Deduct from merchant settled wallet (full amount including charges)
                        debit_result = wallet_svc.debit_merchant_wallet(
                            merchant_id=txn['merchant_id'],
                            amount=float(txn['txn_amount']) if txn['txn_amount'] else 0,
                            description=f"Payout completed (ClocksPay) - Ref: {merchant_order_id}",
                            reference_id=txn['txn_id']
                        )
                        
                        if debit_result['success']:
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                        else:
                            print(f"❌ WALLET DEDUCTION FAILED: {debit_result['message']}")
                
                # Verify the update
                cursor.execute("""
                    SELECT status, utr, completed_at
                    FROM payout_transactions
                    WHERE txn_id = %s
                """, (txn['txn_id'],))
                
                updated_txn = cursor.fetchone()
                print(f"Verification - Status: {updated_txn['status']}, UTR: {updated_txn['utr']}, Completed: {updated_txn['completed_at']}")
                
                print("=" * 80)
                print("ClocksPay Payout Callback processed successfully")
                print("=" * 80)
                
                # Forward callback to merchant if configured (in Maxpe payout format)
                print("=" * 80)
                print("MERCHANT CALLBACK FORWARDING - PAYOUT (MAXPE FORMAT)")
                print("=" * 80)
                print(f"Transaction merchant_id: {txn.get('merchant_id')}")
                print(f"Transaction callback_url field: {txn.get('callback_url')}")
                
                try:
                    # Get callback URL from transaction or merchant_callbacks table
                    callback_url = None
                    
                    if txn.get('callback_url'):
                        callback_url = txn['callback_url'].strip()
                        if not callback_url:
                            callback_url = None
                    
                    print(f"Step 1: Transaction callback_url from DB: {callback_url if callback_url else 'NOT SET'}")
                    
                    # If no callback URL in transaction, check merchant_callbacks table
                    if not callback_url and txn['merchant_id']:
                        print(f"Step 2: Checking merchant_callbacks table for merchant: {txn['merchant_id']}")
                        cursor.execute("""
                            SELECT payout_callback_url FROM merchant_callbacks
                            WHERE merchant_id = %s
                        """, (txn['merchant_id'],))
                        
                        merchant_callback = cursor.fetchone()
                        if merchant_callback and merchant_callback.get('payout_callback_url'):
                            callback_url = merchant_callback['payout_callback_url'].strip()
                            if not callback_url:
                                callback_url = None
                        
                        print(f"Step 2: Merchant payout_callback_url: {callback_url if callback_url else 'NOT SET'}")
                    
                    if callback_url:
                        # DUPLICATE PREVENTION: Check if we already sent a SUCCESS callback
                        if mapped_status == 'SUCCESS':
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
                                print(f"  This is a duplicate callback from ClocksPay")
                                print("=" * 80)
                                
                                return jsonify({
                                    'success': True,
                                    'message': 'Callback processed (duplicate prevented)',
                                    'txn_id': txn['txn_id'],
                                    'status': mapped_status
                                }), 200
                        
                        import requests
                        
                        # Prepare callback payload for merchant in Maxpe payout format
                        merchant_callback_data = {
                            'txn_id': txn['txn_id'],
                            'reference_id': merchant_order_id,
                            'status': mapped_status,
                            'utr': utr,
                            'pg_partner': 'CLOCKSPAY',
                            'pg_txn_id': merchant_order_id,
                            'amount': float(txn['net_amount']) if txn['net_amount'] else 0,
                            'message': f'Payout {mapped_status.lower()}'
                        }
                        
                        print(f"Forwarding payout callback to merchant: {callback_url}")
                        print(f"Callback data (Maxpe format): {json.dumps(merchant_callback_data, indent=2)}")
                        
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
                                callback_response.text[:1000]
                            ))
                            conn.commit()
                            
                            print(f"✓ Merchant payout callback sent successfully and logged")
                            
                        except requests.exceptions.RequestException as e:
                            print(f"ERROR: Failed to send merchant payout callback: {e}")
                            
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
                        print("No merchant payout callback URL configured")
                        
                except Exception as e:
                    print(f"ERROR in merchant callback forwarding: {e}")
                    import traceback
                    traceback.print_exc()
                
                return jsonify({
                    'success': True,
                    'message': 'Callback processed successfully',
                    'txn_id': txn['txn_id'],
                    'status': mapped_status
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[ClocksPay Payout Callback] ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        # Return detailed error for debugging
        error_details = {
            'success': False,
            'message': str(e),
            'error_type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        
        return jsonify(error_details), 500
