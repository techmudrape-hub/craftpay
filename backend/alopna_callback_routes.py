from flask import Blueprint, request, jsonify
import json
from datetime import datetime
from database import get_db_connection
from wallet_service import wallet_service

alopna_callback_bp = Blueprint('alopna_callback', __name__, url_prefix='/api/callback/alopna')

@alopna_callback_bp.route('/payin', methods=['POST', 'GET'])
def payin_callback():
    """Alopna PayIn Callback Handler"""
    try:
        # Get data from JSON or form depending on content type
        if request.is_json:
            data = request.json
        else:
            data = request.form.to_dict()
            
        print(f"[{datetime.now()}] [Alopna PayIn Callback] Received: {data}")
        
        # Alopna specific field mapping (adjust based on actual webhook format)
        status = data.get('status', '').lower()
        order_id = data.get('request_id') or data.get('order_id')
        pg_txn_id = data.get('transaction_id') or data.get('txn_id')
        utr = data.get('utr') or data.get('bank_ref_no') or ''
        
        if not order_id:
            return jsonify({'success': False, 'message': 'Missing order identifier'}), 400
            
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
                cursor.execute("""
                    SELECT txn_id, merchant_id, status, net_amount, charge_amount 
                    FROM payin_transactions 
                    WHERE order_id = %s AND pg_partner = 'ALOPNA'
                """, (order_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    print(f"[Alopna PayIn Callback] Transaction not found: {order_id}")
                    return jsonify({'success': False, 'message': 'Transaction not found'}), 404
                    
                txn_id = txn['txn_id']
                current_status = txn['status']
                
                # If transaction is already in final state, don't update
                if current_status in ['SUCCESS', 'FAILED']:
                    print(f"[Alopna PayIn Callback] Transaction {txn_id} already in final state: {current_status}")
                    return jsonify({'success': True, 'message': 'Callback processed (already in final state)'}), 200
                    
                # Update transaction
                if mapped_status == 'SUCCESS':
                    cursor.execute("""
                        UPDATE payin_transactions 
                        SET status = 'SUCCESS', bank_ref_no = %s, pg_txn_id = %s,
                            payment_mode = 'UPI', completed_at = NOW(), updated_at = NOW()
                        WHERE txn_id = %s
                    """, (utr, pg_txn_id, txn_id))
                    
                    # Credit merchant unsettled wallet
                    wallet_result = wallet_service.credit_unsettled_wallet(
                        merchant_id=txn['merchant_id'],
                        amount=float(txn['net_amount']),
                        description=f"PayIn received (Alopna) - {order_id}",
                        reference_id=txn_id
                    )
                    
                    if wallet_result['success']:
                        print(f"✓ Credited merchant unsettled wallet: ₹{txn['net_amount']}")
                    else:
                        print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")
                        
                    # Credit admin unsettled wallet
                    admin_wallet_result = wallet_service.credit_admin_unsettled_wallet(
                        admin_id='admin',
                        amount=float(txn['charge_amount']),
                        description=f"PayIn charge (Alopna) - {order_id}",
                        reference_id=txn_id
                    )
                    
                    if admin_wallet_result['success']:
                        print(f"✓ Credited admin unsettled wallet: ₹{txn['charge_amount']}")
                    else:
                        print(f"✗ Failed to credit admin unsettled wallet: {admin_wallet_result.get('message')}")
                        
                elif mapped_status == 'FAILED':
                    cursor.execute("""
                        UPDATE payin_transactions 
                        SET status = 'FAILED', pg_txn_id = %s,
                            completed_at = NOW(), updated_at = NOW()
                        WHERE txn_id = %s
                    """, (pg_txn_id, txn_id))
                    
                conn.commit()
                print(f"[Alopna PayIn Callback] Successfully processed for {order_id} -> {mapped_status}")
                return jsonify({'success': True, 'message': 'Callback processed successfully'}), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[Alopna PayIn Callback] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal server error'}), 500
