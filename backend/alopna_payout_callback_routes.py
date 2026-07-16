from flask import Blueprint, request, jsonify
import json
from datetime import datetime
from database import get_db_connection

alopna_payout_callback_bp = Blueprint('alopna_payout_callback', __name__, url_prefix='/api/callback/alopna')

@alopna_payout_callback_bp.route('/payout', methods=['POST', 'GET'])
def payout_callback():
    """Alopna PayOut Webhook Handler"""
    try:
        # Get data from JSON or form depending on content type
        if request.is_json:
            data = request.json
        else:
            data = request.form.to_dict()
            
        print(f"[{datetime.now()}] [Alopna PayOut Webhook] Received: {data}")
        
        # Alopna specific field mapping
        status = data.get('status', '').lower()
        order_id = data.get('request_id') or data.get('order_id')
        pg_txn_id = data.get('transaction_id') or data.get('txn_id')
        utr = data.get('utr') or data.get('bank_ref_no') or ''
        message = data.get('message') or data.get('remarks') or ''
        
        if not order_id:
            return jsonify({'success': False, 'message': 'Missing request_id identifier'}), 400
            
        mapped_status = 'INITIATED'
        if status == 'success':
            mapped_status = 'SUCCESS'
        elif status == 'failed':
            mapped_status = 'FAILED'
            
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
            
        try:
            with conn.cursor() as cursor:
                # Find transaction by order_id (request_id)
                # Alopna Payouts use reference_id = order_id
                cursor.execute("""
                    SELECT txn_id, reference_id, merchant_id, admin_id, status, amount, charge_amount 
                    FROM payout_transactions 
                    WHERE reference_id = %s
                """, (order_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    print(f"[Alopna PayOut Webhook] Transaction not found: {order_id}")
                    return jsonify({'success': False, 'message': 'Transaction not found'}), 404
                    
                reference_id = txn['reference_id']
                current_status = txn['status']
                
                # If transaction is already in final state, don't update
                if current_status in ['SUCCESS', 'FAILED']:
                    print(f"[Alopna PayOut Webhook] Transaction {reference_id} already in final state: {current_status}")
                    return jsonify({'success': True, 'message': 'Webhook processed (already in final state)'}), 200
                    
                # Update transaction
                if mapped_status == 'SUCCESS':
                    cursor.execute("""
                        UPDATE payout_transactions 
                        SET status = 'SUCCESS', utr = %s, pg_txn_id = %s,
                            completed_at = NOW(), updated_at = NOW()
                        WHERE reference_id = %s
                    """, (utr, pg_txn_id, reference_id))
                    
                elif mapped_status == 'FAILED':
                    cursor.execute("""
                        UPDATE payout_transactions 
                        SET status = 'FAILED', pg_txn_id = %s, error_message = %s,
                            completed_at = NOW(), updated_at = NOW()
                        WHERE reference_id = %s
                    """, (pg_txn_id, message, reference_id))
                    
                    # Process refund if failed
                    if txn['merchant_id']:
                        print(f"[Alopna PayOut Webhook] Processing refund for failed payout: {reference_id}")
                        total_deducted = float(txn['amount']) + float(txn['charge_amount'])
                        
                        from wallet_service import wallet_service as wallet_svc
                        refund_result = wallet_svc.credit_merchant_wallet(
                            merchant_id=txn['merchant_id'],
                            amount=total_deducted,
                            description=f"Refund for failed payout: {reference_id}",
                            reference_id=reference_id
                        )
                        
                        if refund_result['success']:
                            print(f"[Alopna PayOut Webhook] Refund successful: {total_deducted}")
                        else:
                            print(f"[Alopna PayOut Webhook] Refund failed: {refund_result.get('message')}")
                            
                conn.commit()
                print(f"[Alopna PayOut Webhook] Successfully processed for {order_id} -> {mapped_status}")
                return jsonify({'success': True, 'message': 'Webhook processed successfully'}), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[Alopna PayOut Webhook] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal server error'}), 500
