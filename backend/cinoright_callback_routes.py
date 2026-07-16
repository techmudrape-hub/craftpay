from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json

cinoright_callback_bp = Blueprint('cinoright_callback', __name__, url_prefix='/api/callback')

@cinoright_callback_bp.route('/cinoright/payout', methods=['POST'])
def cinoright_payout_callback():
    """
    Webhook endpoint for Cinoright payout status updates
    Cinoright will call this when payout status changes
    
    Expected callback format:
    {
      "success": true,
      "data": {
        "status": "SUCCESS",
        "statusCode": "200",
        "message": "Transaction Successfully",
        "data": {
          "transactionId": "ARNPY334239241PT194",  // pg_txn_id
          "utr": null,
          "client_referenceId": "Br2140002556",     // reference_id
          "acknowledged": 0
        }
      }
    }
    """
    try:
        # Get callback data from Cinoright - accept both JSON and form data
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
            print(f"ERROR: No data received")
            print(f"Content-Type: {request.content_type}")
            print(f"Raw data: {raw_data[:500]}")
            return jsonify({
                'success': False, 
                'message': 'No data received in request'
            }), 400
        
        print("=" * 80)
        print("Cinoright Payout Callback Received")
        print("=" * 80)
        print(f"Data Source: {data_source}")
        print(f"Content-Type: {request.content_type}")
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")
        
        # Extract data - handle both nested and flat formats
        # Flat format (actual): {"status": "SUCCESS", "transactionId": "...", "client_referenceId": "..."}
        # Nested format (documented): {"success": true, "data": {"status": "SUCCESS", "data": {...}}}
        
        # Check if it's the flat format (has client_referenceId at top level)
        if 'client_referenceId' in callback_data:
            # Flat format - direct access
            status = callback_data.get('status', '').upper()
            message = callback_data.get('description', callback_data.get('message', ''))
            pg_txn_id = callback_data.get('transactionId')
            utr = callback_data.get('utr')
            reference_id = callback_data.get('client_referenceId')
            amount = callback_data.get('txn_amount')
            
            print("Using FLAT format (actual Cinoright format)")
            
        # Check if it's the nested format
        elif 'data' in callback_data:
            outer_data = callback_data.get('data', {})
            
            # Check if double-nested
            if 'data' in outer_data:
                inner_data = outer_data.get('data', {})
                status = outer_data.get('status', '').upper()
                message = outer_data.get('message', '')
                pg_txn_id = inner_data.get('transactionId')
                utr = inner_data.get('utr')
                reference_id = inner_data.get('client_referenceId')
                amount = inner_data.get('txn_amount')
                
                print("Using NESTED format (documented format)")
            else:
                # Single nested
                status = outer_data.get('status', '').upper()
                message = outer_data.get('description', outer_data.get('message', ''))
                pg_txn_id = outer_data.get('transactionId')
                utr = outer_data.get('utr')
                reference_id = outer_data.get('client_referenceId')
                amount = outer_data.get('txn_amount')
                
                print("Using SINGLE-NESTED format")
        else:
            print("ERROR: Unknown callback format")
            print(f"Available keys: {list(callback_data.keys())}")
            return jsonify({
                'success': False, 
                'message': 'Unknown callback format',
                'received_keys': list(callback_data.keys())
            }), 400
        
        if not reference_id:
            print("ERROR: No client_referenceId in callback")
            print(f"Callback data keys: {list(callback_data.keys())}")
            return jsonify({
                'success': False, 
                'message': 'Missing client_referenceId',
                'received_keys': list(callback_data.keys())
            }), 400
        
        print(f"Reference ID (client_referenceId): {reference_id}")
        print(f"PG Transaction ID (transactionId): {pg_txn_id}")
        print(f"Status: {status}")
        print(f"Message: {message}")
        print(f"UTR: {utr}")
        
        # Map Cinoright status to our status
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
            print("ERROR: Database connection failed")
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Find transaction by reference_id (client_referenceId from Cinoright)
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, reference_id, amount as txn_amount, callback_url
                    FROM payout_transactions
                    WHERE pg_partner = 'CINORIGHT'
                    AND reference_id = %s
                    LIMIT 1
                """, (reference_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    print(f"ERROR: Transaction not found for reference_id: {reference_id}")
                    
                    # Try to find any Cinoright transaction to help debug
                    cursor.execute("""
                        SELECT txn_id, reference_id, order_id, pg_txn_id, status
                        FROM payout_transactions
                        WHERE pg_partner = 'CINORIGHT'
                        ORDER BY created_at DESC
                        LIMIT 5
                    """)
                    recent_txns = cursor.fetchall()
                    
                    if recent_txns:
                        print(f"Recent Cinoright transactions:")
                        for t in recent_txns:
                            print(f"  - TXN: {t['txn_id']}, REF: {t['reference_id']}, ORDER: {t['order_id']}, PG_TXN: {t['pg_txn_id']}, STATUS: {t['status']}")
                    
                    return jsonify({
                        'success': False, 
                        'message': f'Transaction not found for reference_id: {reference_id}'
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
                # Update pg_txn_id (transactionId from Cinoright) and UTR
                if mapped_status in ['SUCCESS', 'FAILED']:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, 
                            utr = %s, 
                            pg_txn_id = %s,
                            completed_at = NOW(), 
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, pg_txn_id, txn['txn_id']))
                    print(f"✓ Updated with status={mapped_status}, utr={utr}, pg_txn_id={pg_txn_id}, completed_at=NOW()")
                else:
                    # Status is still pending/initiated
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, 
                            utr = %s, 
                            pg_txn_id = %s,
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, pg_txn_id, txn['txn_id']))
                    print(f"✓ Updated status to {mapped_status}, pg_txn_id={pg_txn_id}")
                
                conn.commit()
                
                # Deduct wallet if status is SUCCESS and merchant_id exists
                if mapped_status == 'SUCCESS' and txn['merchant_id']:
                    print("=" * 80)
                    print("WALLET DEDUCTION - SUCCESS STATUS")
                    print("=" * 80)
                    
                    # Check if wallet was already deducted (use txn_id, not reference_id)
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM wallet_transactions
                        WHERE txn_id = %s AND txn_type = 'DEBIT'
                    """, (txn['txn_id'],))
                    
                    already_debited = cursor.fetchone()['count'] > 0
                    
                    if already_debited:
                        print(f"⚠ Wallet already debited for this transaction - skipping")
                    else:
                        # Import wallet service
                        from wallet_service import WalletService
                        wallet_svc = WalletService()
                        
                        # Deduct from merchant settled wallet
                        debit_result = wallet_svc.debit_merchant_wallet(
                            merchant_id=txn['merchant_id'],
                            amount=float(txn['txn_amount']) if txn['txn_amount'] else 0,
                            description=f"Payout completed - Ref: {reference_id}",
                            reference_id=txn['txn_id']
                        )
                        
                        if debit_result['success']:
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                        else:
                            print(f"❌ WALLET DEDUCTION FAILED: {debit_result['message']}")
                            # Note: We don't fail the callback even if wallet deduction fails
                            # The transaction is already SUCCESS at Cinoright's end
                
                # Verify the update
                cursor.execute("""
                    SELECT status, utr, pg_txn_id, completed_at
                    FROM payout_transactions
                    WHERE txn_id = %s
                """, (txn['txn_id'],))
                
                updated_txn = cursor.fetchone()
                print(f"Verification - Status: {updated_txn['status']}, UTR: {updated_txn['utr']}, PG_TXN_ID: {updated_txn['pg_txn_id']}, Completed: {updated_txn['completed_at']}")
                
                print("=" * 80)
                print("Cinoright Payout Callback processed successfully")
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
                                print(f"  This is a duplicate callback from Cinoright")
                                print("=" * 80)
                                
                                return jsonify({
                                    'success': True,
                                    'message': 'Callback processed (duplicate prevented)',
                                    'txn_id': txn['txn_id'],
                                    'status': mapped_status
                                }), 200
                        
                        import requests
                        
                        # Prepare callback payload for merchant
                        # Convert Decimal to float for JSON serialization
                        merchant_callback_data = {
                            'txn_id': txn['txn_id'],
                            'reference_id': reference_id,
                            'status': mapped_status,
                            'utr': utr,
                            'pg_partner': 'CINORIGHT',
                            'pg_txn_id': pg_txn_id,
                            'amount': float(txn['txn_amount']) if txn['txn_amount'] else 0,
                            'message': message
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
        print(f"ERROR in callback: {e}")
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
