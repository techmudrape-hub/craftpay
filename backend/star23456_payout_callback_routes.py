"""
Star23456 Payout Callback Routes
Handles payout callbacks from Star23456 payment gateway
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json
import threading

star23456_payout_callback_bp = Blueprint('star23456_payout_callback', __name__, url_prefix='/api/callback/payout')

@star23456_payout_callback_bp.route('/star23456', methods=['POST'])
def star23456_payout_callback():
    try:
        callback_data = request.get_json(force=True, silent=True)
        if not callback_data:
            return jsonify({'success': False, 'message': 'No data received'}), 400
            
        print("=" * 80)
        print("Star23456 Payout Callback Received")
        print(f"Data: {json.dumps(callback_data)}")
        print("=" * 80)
        
        merchant_order_id = callback_data.get('orderId')
        status_code = callback_data.get('statusCode', '').upper()
        utr = callback_data.get('bankId')
        
        if not merchant_order_id:
            return jsonify({'success': False, 'message': 'Missing orderId'}), 400
            
        mapped_status = 'PENDING'
        if status_code in ['COMPLETED']:
            mapped_status = 'SUCCESS'
        elif status_code in ['FAILED', 'REVERSED']:
            mapped_status = 'FAILED'
        elif status_code in ['ACCEPTED', 'PENDING', 'PROCESSING']:
            mapped_status = 'PENDING'
            
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
            
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, client_txn_id, amount, 
                           charge_amount, callback_url
                    FROM payout_transactions
                    WHERE pg_partner = 'STAR23456'
                    AND client_txn_id = %s
                    LIMIT 1
                """, (merchant_order_id,))
                
                txn = cursor.fetchone()
                if not txn:
                    return jsonify({'success': False, 'message': 'Transaction not found'}), 404
                    
                current_status = txn['status']
                
                # Only update if status is actually changing to a final state
                if current_status not in ['SUCCESS', 'FAILED'] and mapped_status in ['SUCCESS', 'FAILED']:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, 
                            bank_ref_no = %s,
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, txn['txn_id']))
                    
                    conn.commit()
                    
                    # Refund wallet if FAILED
                    if mapped_status == 'FAILED' and txn['merchant_id']:
                        cursor.execute("""
                            SELECT COUNT(*) as count FROM merchant_wallet_transactions
                            WHERE reference_id = %s AND txn_type = 'PAYOUT_REFUND'
                        """, (txn['txn_id'],))
                        
                        already_refunded = cursor.fetchone()['count'] > 0
                        
                        if not already_refunded:
                            refund_amount = txn['amount'] + txn['charge_amount']
                            
                            cursor.execute("""
                                UPDATE merchants 
                                SET wallet_balance = wallet_balance + %s,
                                    updated_at = NOW()
                                WHERE merchant_id = %s
                            """, (refund_amount, txn['merchant_id']))
                            
                            cursor.execute("""
                                SELECT wallet_balance FROM merchants WHERE merchant_id = %s
                            """, (txn['merchant_id'],))
                            
                            new_balance = cursor.fetchone()['wallet_balance']
                            
                            cursor.execute("""
                                INSERT INTO merchant_wallet_transactions (
                                    merchant_id, txn_type, amount, balance_after,
                                    reference_id, description, status, created_at
                                ) VALUES (
                                    %s, 'PAYOUT_REFUND', %s, %s, %s, %s, 'COMPLETED', NOW()
                                )
                            """, (
                                txn['merchant_id'], refund_amount, new_balance,
                                txn['txn_id'], f"Refund for failed payout {txn['client_txn_id']}"
                            ))
                            
                            conn.commit()
                            
                    # Forward callback to merchant
                    if txn.get('callback_url'):
                        from callback_forwarder import callback_forwarder
                        
                        forward_data = {
                            'status': mapped_status,
                            'order_id': txn['client_txn_id'],
                            'txn_id': txn['txn_id'],
                            'amount': float(txn['amount']),
                            'utr': utr,
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        def run_forwarder():
                            callback_forwarder.forward_payout_callback(
                                merchant_id=txn['merchant_id'],
                                order_id=txn['client_txn_id'],
                                callback_url=txn['callback_url'],
                                callback_data=forward_data
                            )
                        
                        threading.Thread(target=run_forwarder).start()
                
                return jsonify({'success': True, 'message': 'Callback processed successfully'}), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[Star23456 Payout Callback] Error: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500
