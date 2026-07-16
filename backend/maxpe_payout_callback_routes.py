"""
MaxPe Payout Callback Routes
Handles payout status callbacks from MaxPe
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json

maxpe_payout_callback_bp = Blueprint('maxpe_payout_callback', __name__, url_prefix='/api/callback')

@maxpe_payout_callback_bp.route('/maxpe/payout', methods=['POST'])
def maxpe_payout_callback():
    """
    Webhook endpoint for MaxPe/NodePay payout status updates
    Both MaxPe and NodePay will call this endpoint when payout status changes
    
    Expected callback format (from docs):
    {
      "status": "SUCCESS",
      "transaction_details": {
        "amount": "1000.00",
        "merchant_order_id": "txn_00001",
        "utr": "608919646598"
      }
    }
    """
    try:
        # Get callback data from MaxPe - accept both JSON and form data
        callback_data = None
        data_source = None
        
        # Try JSON first
        try:
            callback_data = request.get_json(force=True, silent=True)
            if callback_data:
                data_source = "JSON"
        except:
            pass
        
        # If no JSON, try form data
        if not callback_data:
            if request.form:
                callback_data = request.form.to_dict()
                data_source = "FORM"
                # Try to parse nested JSON strings in form data
                for key, value in callback_data.items():
                    try:
                        callback_data[key] = json.loads(value)
                    except:
                        pass
            elif request.values:
                callback_data = request.values.to_dict()
                data_source = "VALUES"
                # Try to parse nested JSON strings
                for key, value in callback_data.items():
                    try:
                        callback_data[key] = json.loads(value)
                    except:
                        pass
        
        # If still no data, try raw data
        if not callback_data:
            raw_data = request.get_data(as_text=True)
            if raw_data:
                try:
                    callback_data = json.loads(raw_data)
                    data_source = "RAW"
                except:
                    # Try to parse as form-encoded
                    from urllib.parse import parse_qs
                    try:
                        parsed = parse_qs(raw_data)
                        callback_data = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
                        data_source = "RAW_FORM"
                    except:
                        pass
        
        if not callback_data:
            raw_data = request.get_data(as_text=True)
            print(f"[MaxPe Payout Callback] ERROR: No data received")
            print(f"Content-Type: {request.content_type}")
            print(f"Raw data: {raw_data[:500]}")
            return jsonify({
                'success': False,
                'message': 'No data received in request'
            }), 400
        
        print("=" * 80)
        print("MaxPe/NodePay Payout Callback Received")
        print("=" * 80)
        print(f"Data Source: {data_source}")
        print(f"Content-Type: {request.content_type}")
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")
        
        # Extract data from callback
        # Expected format: {"status": "SUCCESS", "transaction_details": {...}}
        status = callback_data.get('status', '').upper()
        transaction_details = callback_data.get('transaction_details', {})
        
        if not transaction_details:
            print(f"[MaxPe/NodePay Payout Callback] ERROR: No transaction_details in callback")
            return jsonify({
                'success': False,
                'message': 'Missing transaction_details',
                'received_keys': list(callback_data.keys())
            }), 400
        
        merchant_order_id = transaction_details.get('merchant_order_id')
        amount = transaction_details.get('amount')
        utr = transaction_details.get('utr')
        
        if not merchant_order_id:
            print(f"[MaxPe/NodePay Payout Callback] ERROR: No merchant_order_id in callback")
            return jsonify({
                'success': False,
                'message': 'Missing merchant_order_id',
                'received_keys': list(transaction_details.keys())
            }), 400
        
        print(f"Merchant Order ID: {merchant_order_id}")
        print(f"Status: {status}")
        print(f"Amount: {amount}")
        print(f"UTR: {utr}")
        
        # Map MaxPe/NodePay status to our status
        # Database ENUM: INITIATED, QUEUED, INPROCESS, SUCCESS, FAILED, REVERSED
        if status == 'SUCCESS':
            mapped_status = 'SUCCESS'
        elif status == 'FAILED':
            mapped_status = 'FAILED'
        elif status == 'PENDING':
            mapped_status = 'INPROCESS'
        else:
            mapped_status = 'INITIATED'
        
        print(f"Mapped Status: {mapped_status}")
        
        # Update database
        conn = get_db_connection()
        if not conn:
            print("[MaxPe/NodePay Payout Callback] ERROR: Database connection failed")
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Find transaction by reference_id OR order_id (MaxPe/NodePay can send either)
                # Try reference_id first (our internal reference)
                # Look for both MAXPE and NODEPAY transactions
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, reference_id, amount as txn_amount, 
                           callback_url, net_amount, order_id, pg_partner
                    FROM payout_transactions
                    WHERE pg_partner IN ('MAXPE', 'NODEPAY')
                    AND reference_id = %s
                    LIMIT 1
                """, (merchant_order_id,))
                
                txn = cursor.fetchone()
                
                # If not found by reference_id, try order_id (merchant's order ID)
                if not txn:
                    print(f"[MaxPe/NodePay Payout Callback] Transaction not found by reference_id, trying order_id...")
                    cursor.execute("""
                        SELECT txn_id, status, merchant_id, reference_id, amount as txn_amount, 
                               callback_url, net_amount, order_id, pg_partner
                        FROM payout_transactions
                        WHERE pg_partner IN ('MAXPE', 'NODEPAY')
                        AND order_id = %s
                        LIMIT 1
                    """, (merchant_order_id,))
                    
                    txn = cursor.fetchone()
                
                # If still not found, try pg_txn_id (in case MaxPe/NodePay stored their own ID there)
                if not txn:
                    print(f"[MaxPe/NodePay Payout Callback] Transaction not found by order_id, trying pg_txn_id...")
                    cursor.execute("""
                        SELECT txn_id, status, merchant_id, reference_id, amount as txn_amount, 
                               callback_url, net_amount, order_id, pg_partner
                        FROM payout_transactions
                        WHERE pg_partner IN ('MAXPE', 'NODEPAY')
                        AND pg_txn_id = %s
                        LIMIT 1
                    """, (merchant_order_id,))
                    
                    txn = cursor.fetchone()
                
                if not txn:
                    print(f"[MaxPe/NodePay Payout Callback] ERROR: Transaction not found for merchant_order_id: {merchant_order_id}")
                    print(f"[MaxPe/NodePay Payout Callback] Searched in: reference_id, order_id, pg_txn_id")
                    
                    # Try to find any MaxPe/NodePay transaction to help debug
                    cursor.execute("""
                        SELECT txn_id, reference_id, order_id, pg_txn_id, status, pg_partner
                        FROM payout_transactions
                        WHERE pg_partner IN ('MAXPE', 'NODEPAY')
                        ORDER BY created_at DESC
                        LIMIT 5
                    """)
                    recent_txns = cursor.fetchall()
                    
                    if recent_txns:
                        print(f"Recent MaxPe/NodePay payout transactions:")
                        for t in recent_txns:
                            print(f"  - TXN: {t['txn_id']}, REF: {t['reference_id']}, ORDER: {t['order_id']}, PG_TXN: {t['pg_txn_id']}, STATUS: {t['status']}, PG: {t['pg_partner']}")
                    
                    return jsonify({
                        'success': False,
                        'message': f'Transaction not found for merchant_order_id: {merchant_order_id}. This callback may be for a transaction created outside this system.'
                    }), 404
                
                print(f"Found Transaction: {txn['txn_id']}, Current Status: {txn['status']}, PG Partner: {txn['pg_partner']}")
                
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
                            description=f"Payout completed ({txn['pg_partner']}) - Ref: {merchant_order_id}",
                            reference_id=txn['txn_id']
                        )
                        
                        if debit_result['success']:
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                        else:
                            print(f"❌ WALLET DEDUCTION FAILED: {debit_result['message']}")
                            # Note: We don't fail the callback even if wallet deduction fails
                            # The transaction is already SUCCESS at MaxPe's end
                
                # Verify the update
                cursor.execute("""
                    SELECT status, utr, completed_at
                    FROM payout_transactions
                    WHERE txn_id = %s
                """, (txn['txn_id'],))
                
                updated_txn = cursor.fetchone()
                print(f"Verification - Status: {updated_txn['status']}, UTR: {updated_txn['utr']}, Completed: {updated_txn['completed_at']}")
                
                print("=" * 80)
                print("MaxPe/NodePay Payout Callback processed successfully")
                print("=" * 80)
                
                # Forward callback to merchant if configured
                print("=" * 80)
                print("MERCHANT CALLBACK FORWARDING - PAYOUT")
                print("=" * 80)
                print(f"Transaction merchant_id: {txn.get('merchant_id')}")
                print(f"Transaction callback_url field: {txn.get('callback_url')}")
                
                try:
                    # Get callback URL from transaction or merchant_callbacks table
                    callback_url = None
                    
                    if txn.get('callback_url'):
                        callback_url = txn['callback_url'].strip()
                        if not callback_url:  # Empty string after strip
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
                            if not callback_url:  # Empty string after strip
                                callback_url = None
                        
                        print(f"Step 2: Merchant payout_callback_url: {callback_url if callback_url else 'NOT SET'}")
                    
                    if callback_url:
                        # DUPLICATE PREVENTION: Check if we already sent a SUCCESS callback for this transaction
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
                                print(f"  This is a duplicate callback from {txn['pg_partner']}")
                                print("=" * 80)
                                
                                return jsonify({
                                    'success': True,
                                    'message': 'Callback processed (duplicate prevented)',
                                    'txn_id': txn['txn_id'],
                                    'status': mapped_status
                                }), 200
                        
                        import requests
                        
                        # Prepare callback payload for merchant in Cinoright format
                        # Convert Decimal to float for JSON serialization
                        merchant_callback_data = {
                            'txn_id': txn['txn_id'],
                            'reference_id': merchant_order_id,
                            'status': mapped_status,
                            'utr': utr,
                            'pg_partner': txn['pg_partner'],  # Will be either 'MAXPE' or 'NODEPAY'
                            'pg_txn_id': merchant_order_id,
                            'amount': float(txn['net_amount']) if txn['net_amount'] else 0,
                            'message': f'Payout {mapped_status.lower()}'
                        }
                        
                        print(f"Forwarding payout callback to merchant: {callback_url}")
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
        print(f"[MaxPe/NodePay Payout Callback] ERROR: {e}")
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


@maxpe_payout_callback_bp.route('/nodepay/payout', methods=['POST'])
def nodepay_payout_callback():
    """
    Webhook endpoint for NodePay payout status updates
    This is an alias to the MaxPe callback handler since they use the same format
    """
    print("🔄 NodePay callback received - forwarding to MaxPe/NodePay handler")
    return maxpe_payout_callback()
