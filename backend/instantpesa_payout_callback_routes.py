"""
InstantPesa Payout Callback Routes
Handles webhook notifications from InstantPesa for payout transactions
"""

from flask import Blueprint, request, jsonify
import json
from database import get_db_connection
from timezone_utils import get_ist_now, ist_to_mysql_format
from datetime import datetime
import requests

instantpesa_payout_callback_bp = Blueprint('instantpesa_payout_callback', __name__, url_prefix='/api/callback')

@instantpesa_payout_callback_bp.route('/instantpesa/payout', methods=['POST'])
def instantpesa_payout_callback():
    """
    Webhook endpoint for InstantPesa payout status updates
    
    InstantPesa will POST to this endpoint with:
    {
        "status": true,
        "message": "Payout successful. The amount has been transferred.",
        "data": {
            "transaction_status": "success",
            "request_id": "REQ99887766",
            "transaction_id": "TXN20250528155500",
            "amount": 2000.00,
            "charge": 30.00,
            "total_amount": 2030.00,
            "transfer_mode": "NEFT",
            "utr": "NEFT9988776655"
        }
    }
    """
    try:
        print("=" * 80)
        print("InstantPesa Payout Callback Received")
        print("=" * 80)
        
        # Log request details
        print(f"Content-Type: {request.content_type}")
        print(f"Headers: {dict(request.headers)}")
        
        # Get callback data
        callback_data = None
        
        if request.is_json:
            callback_data = request.json
            print("Received as JSON")
        elif request.form:
            callback_data = request.form.to_dict()
            print("Received as Form Data")
        elif request.data:
            try:
                callback_data = json.loads(request.data.decode('utf-8'))
                print("Received as Raw Data (parsed as JSON)")
            except:
                print(f"Raw Data (could not parse): {request.data}")
                return jsonify({'success': False, 'message': 'Invalid data format'}), 400
        else:
            print("ERROR: No data received")
            return jsonify({'success': False, 'message': 'No data received'}), 400
        
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")
        
        # Extract outer status
        callback_status = callback_data.get('status', False)
        callback_message = callback_data.get('message', '')
        
        # Extract data from callback
        data = callback_data.get('data', {})
        transaction_status = data.get('transaction_status', '').upper()
        request_id = data.get('request_id', '')
        transaction_id = data.get('transaction_id', '')
        amount = data.get('amount', 0)
        charge = data.get('charge', 0)
        total_amount = data.get('total_amount', 0)
        transfer_mode = data.get('transfer_mode', 'IMPS')
        utr = data.get('utr', '')
        
        print(f"Callback Details:")
        print(f"  Callback Status: {callback_status}")
        print(f"  Transaction Status: {transaction_status}")
        print(f"  Request ID: {request_id}")
        print(f"  Transaction ID: {transaction_id}")
        print(f"  Amount: {amount}")
        print(f"  Charge: {charge}")
        print(f"  Total Amount: {total_amount}")
        print(f"  Transfer Mode: {transfer_mode}")
        print(f"  UTR: {utr}")
        
        if not request_id:
            print("ERROR: No request_id in callback")
            return jsonify({'success': False, 'message': 'Missing request_id'}), 400
        
        # Map transaction status
        if transaction_status == 'SUCCESS' or callback_status is True:
            mapped_status = 'SUCCESS'
        elif transaction_status == 'FAILED':
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
                # Find transaction by reference_id (request_id from InstantPesa)
                cursor.execute("""
                    SELECT txn_id, merchant_id, status, amount as txn_amount
                    FROM payout_transactions
                    WHERE reference_id = %s AND pg_name = 'INSTANTPESA'
                """, (request_id,))
                
                transaction = cursor.fetchone()
                
                if not transaction:
                    print(f"WARNING: Transaction not found for reference_id: {request_id}")
                    # Still return success to acknowledge receipt
                    return jsonify({'success': True, 'message': 'Callback received'}), 200
                
                txn_id = transaction['txn_id']
                merchant_id = transaction['merchant_id']
                current_status = transaction['status']
                
                print(f"Found Transaction:")
                print(f"  TXN ID: {txn_id}")
                print(f"  Merchant ID: {merchant_id}")
                print(f"  Current Status: {current_status}")
                
                # CRITICAL: Debit wallet when status is SUCCESS
                if mapped_status == 'SUCCESS' and merchant_id:
                    # Check if wallet was already deducted to prevent duplicate deductions
                    cursor.execute("""
                        SELECT txn_id FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'DEBIT'
                    """, (txn_id,))
                    
                    wallet_already_deducted = cursor.fetchone()
                    
                    if wallet_already_deducted:
                        print(f"⚠️  Wallet already deducted for this transaction - skipping")
                    else:
                        print(f"Status is SUCCESS - Debiting merchant settled wallet")
                        
                        # Get transaction details for wallet deduction
                        cursor.execute("""
                            SELECT amount, net_amount, charge_amount FROM payout_transactions
                            WHERE txn_id = %s
                        """, (txn_id,))
                        payout_details = cursor.fetchone()
                        
                        # Use 'amount' field which already contains total deduction
                        total_deduction = float(payout_details['amount'])
                        
                        print(f"Deducting from settled wallet - Amount: ₹{total_deduction:.2f} (Net: ₹{payout_details['net_amount']:.2f} + Charges: ₹{payout_details['charge_amount']:.2f})")
                        
                        # Debit merchant settled wallet
                        from wallet_service import WalletService
                        wallet_svc = WalletService()
                        debit_result = wallet_svc.debit_merchant_wallet(
                            merchant_id=merchant_id,
                            amount=total_deduction,
                            description=f"Payout: ₹{payout_details['net_amount']:.2f} + Charges: ₹{payout_details['charge_amount']:.2f}",
                            reference_id=txn_id
                        )
                        
                        if debit_result['success']:
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                        else:
                            print(f"✗ WALLET DEBIT FAILED: {debit_result['message']}")
                            # Update transaction to FAILED if wallet debit fails
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = 'FAILED', error_message = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (f"Wallet debit failed: {debit_result['message']}", txn_id))
                            conn.commit()
                            
                            return jsonify({
                                'success': False,
                                'message': f"Payout succeeded but wallet debit failed: {debit_result['message']}"
                            }), 500
                
                # Update transaction with callback data
                now = get_ist_now()
                mysql_timestamp = ist_to_mysql_format(now)
                
                if mapped_status in ['SUCCESS', 'FAILED']:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, pg_txn_id = %s, completed_at = %s, updated_at = NOW()
                        WHERE reference_id = %s
                    """, (mapped_status, utr, transaction_id, mysql_timestamp, request_id))
                    print(f"✓ Updated with completed_at: {mysql_timestamp}")
                else:
                    # Status is still pending/initiated
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, pg_txn_id = %s, updated_at = NOW()
                        WHERE reference_id = %s
                    """, (mapped_status, utr, transaction_id, request_id))
                    print(f"✓ Updated status to {mapped_status}")
                
                conn.commit()
                
                # Verify the update
                cursor.execute("""
                    SELECT status, utr, pg_txn_id, completed_at
                    FROM payout_transactions
                    WHERE reference_id = %s
                """, (request_id,))
                
                updated_txn = cursor.fetchone()
                print(f"Verification - Status: {updated_txn['status']}, UTR: {updated_txn['utr']}, PG_TXN_ID: {updated_txn['pg_txn_id']}, Completed: {updated_txn['completed_at']}")
                
                print("=" * 80)
                print("InstantPesa Payout Callback processed successfully")
                print("=" * 80)
                
                # Forward callback to merchant if configured
                print("=" * 80)
                print("MERCHANT CALLBACK FORWARDING - PAYOUT")
                print("=" * 80)
                try:
                    # First, get the callback URL from the transaction itself
                    cursor.execute("""
                        SELECT callback_url FROM payout_transactions
                        WHERE reference_id = %s
                    """, (request_id,))
                    
                    txn_callback = cursor.fetchone()
                    callback_url = None
                    
                    if txn_callback and txn_callback.get('callback_url'):
                        callback_url = txn_callback['callback_url'].strip()
                        if not callback_url:  # Empty string after strip
                            callback_url = None
                    
                    print(f"Step 1: Transaction callback_url from DB: {callback_url if callback_url else 'NOT SET'}")
                    
                    # If no callback URL in transaction, check merchant_callbacks table
                    if not callback_url:
                        print(f"Step 2: Checking merchant_callbacks table for merchant: {merchant_id}")
                        cursor.execute("""
                            SELECT payout_callback_url FROM merchant_callbacks
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        
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
                            """, (merchant_id, txn_id, '%"status": "SUCCESS"%'))
                            
                            success_callback_sent = cursor.fetchone()['count'] > 0
                            
                            if success_callback_sent:
                                print(f"⚠ SUCCESS callback already sent to merchant - skipping duplicate")
                                print(f"  This is a duplicate callback from InstantPesa")
                                print("=" * 80)
                                
                                return jsonify({
                                    'success': True,
                                    'message': 'Callback processed (duplicate prevented)',
                                    'txn_id': txn_id,
                                    'status': mapped_status
                                }), 200
                        
                        # Prepare callback payload for merchant
                        merchant_callback_data = {
                            'txn_id': txn_id,
                            'reference_id': request_id,
                            'status': mapped_status,
                            'utr': utr,
                            'pg_txn_id': transaction_id,
                            'pg_partner': 'InstantPesa',
                            'transfer_mode': transfer_mode,
                            'amount': amount,
                            'charge': charge,
                            'total_amount': total_amount,
                            'timestamp': datetime.now().isoformat()
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
                                merchant_id,
                                txn_id,
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
                                merchant_id,
                                txn_id,
                                callback_url,
                                json.dumps(merchant_callback_data),
                                0,
                                str(e)[:1000]
                            ))
                            conn.commit()
                    else:
                        print("No merchant payout callback URL configured (neither in transaction nor merchant_callbacks table)")
                        
                except Exception as e:
                    print(f"ERROR in merchant callback forwarding: {e}")
                    import traceback
                    traceback.print_exc()
                
                return jsonify({
                    'success': True,
                    'message': 'Callback processed successfully',
                    'txn_id': txn_id,
                    'status': mapped_status
                }), 200
        
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()
            return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
        finally:
            conn.close()
    
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
