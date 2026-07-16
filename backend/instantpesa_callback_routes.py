"""
InstantPesa Callback Routes
Handles webhook notifications from InstantPesa
"""

from flask import Blueprint, request, jsonify
import json
from database import get_db_connection
from timezone_utils import get_ist_now, ist_to_mysql_format

instantpesa_callback_bp = Blueprint('instantpesa_callback', __name__)

@instantpesa_callback_bp.route('/api/callback/instantpesa/payin', methods=['POST'])
def instantpesa_payin_callback():
    """
    Webhook endpoint for InstantPesa payin status updates
    
    InstantPesa will POST to this endpoint with:
    {
        "status": true,
        "message": "Transaction successful. Your payment has been processed and confirmed.",
        "data": {
            "transaction_status": "success",
            "request_id": "REQ123456789",
            "transaction_id": "TXN20250528150100",
            "amount": 1000.00,
            "charge": 20.00,
            "received_amount": 980.00,
            "payment_mode": "UPI",
            "rrn": "123456789012",
            "transaction_at": "2025-05-28 15:01:00"
        }
    }
    """
    try:
        print("=" * 80)
        print("InstantPesa Payin Callback Received")
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
        received_amount = data.get('received_amount', 0)
        payment_mode = data.get('payment_mode', 'UPI')
        rrn = data.get('rrn', '')
        transaction_at = data.get('transaction_at', '')
        
        print(f"Callback Details:")
        print(f"  Callback Status: {callback_status}")
        print(f"  Transaction Status: {transaction_status}")
        print(f"  Request ID: {request_id}")
        print(f"  Transaction ID: {transaction_id}")
        print(f"  Amount: {amount}")
        print(f"  Charge: {charge}")
        print(f"  Received Amount: {received_amount}")
        print(f"  Payment Mode: {payment_mode}")
        print(f"  RRN: {rrn}")
        print(f"  Transaction At: {transaction_at}")
        
        if not transaction_id:
            print("ERROR: No transaction_id in callback")
            return jsonify({'success': False, 'message': 'Missing transaction_id'}), 400
        
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
                # Find transaction by pg_txn_id (transaction_id from InstantPesa)
                cursor.execute("""
                    SELECT txn_id, order_id, merchant_id, amount, status
                    FROM payin_transactions
                    WHERE pg_txn_id = %s AND pg_name = 'INSTANTPESA'
                """, (transaction_id,))
                
                transaction = cursor.fetchone()
                
                if not transaction:
                    print(f"WARNING: Transaction not found for pg_txn_id: {transaction_id}")
                    # Still return success to acknowledge receipt
                    return jsonify({'success': True, 'message': 'Callback received'}), 200
                
                txn_id = transaction['txn_id']
                order_id = transaction['order_id']
                merchant_id = transaction['merchant_id']
                db_amount = transaction['amount']
                current_status = transaction['status']
                
                print(f"Found Transaction:")
                print(f"  TXN ID: {txn_id}")
                print(f"  Order ID: {order_id}")
                print(f"  Merchant ID: {merchant_id}")
                print(f"  Current Status: {current_status}")
                
                # Only update if status is changing
                if current_status != mapped_status:
                    now = get_ist_now()
                    mysql_timestamp = ist_to_mysql_format(now)
                    
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s, utr = %s, updated_at = %s
                        WHERE txn_id = %s
                    """, (mapped_status, rrn, mysql_timestamp, txn_id))
                    
                    conn.commit()
                    print(f"Updated transaction status to {mapped_status}")
                    
                    # If successful, update wallet
                    if mapped_status == 'SUCCESS':
                        print(f"Processing successful payment for merchant {merchant_id}")
                        
                        # Get merchant wallet
                        cursor.execute("""
                            SELECT wallet_id, balance
                            FROM merchant_wallets
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        
                        wallet = cursor.fetchone()
                        
                        if wallet:
                            wallet_id = wallet['wallet_id']
                            current_balance = float(wallet['balance'])
                            new_balance = current_balance + float(received_amount)
                            
                            # Update wallet balance
                            cursor.execute("""
                                UPDATE merchant_wallets
                                SET balance = %s, updated_at = %s
                                WHERE wallet_id = %s
                            """, (new_balance, mysql_timestamp, wallet_id))
                            
                            # Log wallet transaction
                            cursor.execute("""
                                INSERT INTO wallet_transactions (
                                    wallet_id, txn_id, transaction_type, amount,
                                    balance_before, balance_after, description, created_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                wallet_id, txn_id, 'CREDIT', received_amount,
                                current_balance, new_balance,
                                f'InstantPesa Payin - {rrn}', mysql_timestamp
                            ))
                            
                            conn.commit()
                            print(f"Wallet updated: {current_balance} -> {new_balance}")
                        else:
                            print(f"WARNING: Wallet not found for merchant {merchant_id}")
                else:
                    print(f"Status unchanged, skipping update")
                
                return jsonify({'success': True, 'message': 'Callback processed successfully'}), 200
        
        except Exception as e:
            print(f"ERROR: {e}")
            conn.rollback()
            return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
        finally:
            conn.close()
    
    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
