"""
RockyPayz Payout Callback Routes
Handles payout status callbacks from RockyPayz
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json

rockypayz_payout_callback_bp = Blueprint('rockypayz_payout_callback', __name__, url_prefix='/api/callback')

@rockypayz_payout_callback_bp.route('/rockypayz/payout', methods=['GET', 'POST'])
def rockypayz_payout_callback():
    """
    Webhook endpoint for RockyPayz payout status updates
    
    Expected callback format (from RockyPayz team):
    The callback will be sent in the same format as the payout response:
    {
      "statuscode": "TXN",
      "msg": "Payout completed",
      "data": {
        "TXN_Time": "2025-11-07 18:20:57",
        "TXN_ID": "abcxyz1615255",
        "Amount": 100,
        "Fees": 10.62,
        "UTR": "61201018xxx",
        "status": "success"
      }
    }
    
    This endpoint will forward the callback to merchant in MaxPe payout format
    """
    try:
        # Get callback data - support both GET and POST
        callback_data = None
        data_source = None
        
        # Try GET parameters first
        if request.args:
            callback_data = request.args.to_dict()
            data_source = "GET"
        # Try POST JSON
        elif request.method == 'POST':
            try:
                callback_data = request.get_json(force=True, silent=True)
                if callback_data:
                    data_source = "JSON"
            except:
                pass
            
            # Try POST form data
            if not callback_data and request.form:
                callback_data = request.form.to_dict()
                data_source = "FORM"
                # Try to parse nested JSON strings in form data
                for key, value in callback_data.items():
                    try:
                        callback_data[key] = json.loads(value)
                    except:
                        pass
        
        if not callback_data:
            raw_data = request.get_data(as_text=True)
            print(f"[RockyPayz Payout Callback] ERROR: No data received")
            print(f"Method: {request.method}")
            print(f"Content-Type: {request.content_type}")
            print(f"Query String: {request.query_string}")
            print(f"Raw data: {raw_data[:500]}")
            return jsonify({
                'success': False,
                'message': 'No data received in request'
            }), 400
        
        print("=" * 80)
        print("RockyPayz Payout Callback Received")
        print("=" * 80)
        print(f"Method: {request.method}")
        print(f"Data Source: {data_source}")
        print(f"Content-Type: {request.content_type}")
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")
        
        # Extract data from callback
        statuscode = callback_data.get('statuscode', '').upper()
        message = callback_data.get('msg', '')
        data = callback_data.get('data', {})
        
        if not data:
            print(f"[RockyPayz Payout Callback] ERROR: No data object in callback")
            return jsonify({
                'success': False,
                'message': 'Missing data object',
                'received_keys': list(callback_data.keys())
            }), 400
        
        # Extract transaction details
        merchant_order_id = data.get('TXN_ID')  # This is the ref_no we sent
        amount = data.get('Amount')
        fees = data.get('Fees', 0)
        utr = data.get('UTR', '')
        status = data.get('status', '').lower()
        txn_time = data.get('TXN_Time', '')
        
        if not merchant_order_id:
            print(f"[RockyPayz Payout Callback] ERROR: No TXN_ID in callback")
            return jsonify({
                'success': False,
                'message': 'Missing TXN_ID',
                'received_keys': list(data.keys())
            }), 400
        
        print(f"Merchant Order ID (TXN_ID): {merchant_order_id}")
        print(f"Status: {status}")
        print(f"Amount: {amount}")
        print(f"Fees: {fees}")
        print(f"UTR: {utr}")
        print(f"TXN Time: {txn_time}")
        
        # Map RockyPayz status to our status
        # Database ENUM: INITIATED, QUEUED, INPROCESS, SUCCESS, FAILED, REVERSED
        if status == 'success':
            mapped_status = 'SUCCESS'
        elif status == 'failed':
            mapped_status = 'FAILED'
        elif status == 'pending':
            mapped_status = 'INPROCESS'
        else:
            mapped_status = 'INITIATED'
        
        print(f"Mapped Status: {mapped_status}")
        
        # Update database
        conn = get_db_connection()
        if not conn:
            print("[RockyPayz Payout Callback] ERROR: Database connection failed")
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Find transaction by reference_id (starts with RCK_TXN)
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, reference_id, amount as txn_amount, 
                           callback_url, net_amount, order_id, pg_partner
                    FROM payout_transactions
                    WHERE pg_partner = 'ROCKYPAYZ'
                    AND reference_id = %s
                    LIMIT 1
                """, (merchant_order_id,))
                
                txn = cursor.fetchone()
                
                # If not found by reference_id, try order_id
                if not txn:
                    print(f"[RockyPayz Payout Callback] Transaction not found by reference_id, trying order_id...")
                    cursor.execute("""
                        SELECT txn_id, status, merchant_id, reference_id, amount as txn_amount, 
                               callback_url, net_amount, order_id, pg_partner
                        FROM payout_transactions
                        WHERE pg_partner = 'ROCKYPAYZ'
                        AND order_id = %s
                        LIMIT 1
                    """, (merchant_order_id,))
                    
                    txn = cursor.fetchone()
                
                # If still not found, try pg_txn_id
                if not txn:
                    print(f"[RockyPayz Payout Callback] Transaction not found by order_id, trying pg_txn_id...")
                    cursor.execute("""
                        SELECT txn_id, status, merchant_id, reference_id, amount as txn_amount, 
                               callback_url, net_amount, order_id, pg_partner
                        FROM payout_transactions
                        WHERE pg_partner = 'ROCKYPAYZ'
                        AND pg_txn_id = %s
                        LIMIT 1
                    """, (merchant_order_id,))
                    
                    txn = cursor.fetchone()
                
                if not txn:
                    print(f"[RockyPayz Payout Callback] ERROR: Transaction not found for TXN_ID: {merchant_order_id}")
                    
                    # Try to find any RockyPayz transaction to help debug
                    cursor.execute("""
                        SELECT txn_id, reference_id, order_id, pg_txn_id, status
                        FROM payout_transactions
                        WHERE pg_partner = 'ROCKYPAYZ'
                        ORDER BY created_at DESC
                        LIMIT 5
                    """)
                    recent_txns = cursor.fetchall()
                    
                    if recent_txns:
                        print(f"Recent RockyPayz payout transactions:")
                        for t in recent_txns:
                            print(f"  - TXN: {t['txn_id']}, REF: {t['reference_id']}, ORDER: {t['order_id']}, PG_TXN: {t['pg_txn_id']}, STATUS: {t['status']}")
                    
                    return jsonify({
                        'success': False,
                        'message': f'Transaction not found for TXN_ID: {merchant_order_id}'
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
                            description=f"Payout completed (RockyPayz) - Ref: {merchant_order_id}",
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
                print("RockyPayz Payout Callback processed successfully")
                print("=" * 80)
                
                # Forward callback to merchant if configured (in MaxPe payout format)
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
                                print(f"  This is a duplicate callback from RockyPayz")
                                print("=" * 80)
                                
                                return jsonify({
                                    'success': True,
                                    'message': 'Callback processed (duplicate prevented)',
                                    'txn_id': txn['txn_id'],
                                    'status': mapped_status
                                }), 200
                        
                        import requests
                        
                        # Prepare callback payload for merchant in MaxPe payout format
                        merchant_callback_data = {
                            'txn_id': txn['txn_id'],
                            'reference_id': merchant_order_id,
                            'status': mapped_status,
                            'utr': utr,
                            'pg_partner': 'ROCKYPAYZ',
                            'pg_txn_id': merchant_order_id,
                            'amount': float(txn['net_amount']) if txn['net_amount'] else 0,
                            'message': f'Payout {mapped_status.lower()}'
                        }
                        
                        print(f"Forwarding payout callback to merchant: {callback_url}")
                        print(f"Callback data (MaxPe format): {json.dumps(merchant_callback_data, indent=2)}")
                        
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
        print(f"[RockyPayz Payout Callback] ERROR: {e}")
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
