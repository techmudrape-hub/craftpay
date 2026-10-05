"""
Shadvalpay Callback Routes
Handles payin callbacks from Shadvalpay payment gateway
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from shadvalpay_service import shadvalpay_service
from datetime import datetime
import json
import requests

shadvalpay_callback_bp = Blueprint('shadvalpay_callback', __name__, url_prefix='/api/callback')

@shadvalpay_callback_bp.route('/shadvalpay/payin', methods=['POST'])
def shadvalpay_payin_callback():
    """
    Webhook endpoint for Shadvalpay payin status updates
    """
    try:
        callback_data = request.get_json(force=True, silent=True)
        if not callback_data:
            return jsonify({'success': False, 'message': 'No data received'}), 400

        print(f"Shadvalpay Callback Received: {json.dumps(callback_data)}")
        
        status = callback_data.get('status', '').upper()
        if status != 'SUCCESS':
            return jsonify({'success': True, 'message': 'Not a success status ignored'}), 200

        encrypted_response = callback_data.get('response')
        payment_id = callback_data.get('payment_id')
        
        if not encrypted_response:
            return jsonify({'success': False, 'message': 'Missing response data'}), 400
            
        decrypted_data = shadvalpay_service.decrypt_response(encrypted_response)
        
        if not decrypted_data:
            return jsonify({'success': False, 'message': 'Failed to decrypt webhook data'}), 400
            
        print(f"Decrypted Shadvalpay Webhook Data: {decrypted_data}")
        
        transaction_status = decrypted_data.get('txn_status', 'FAILED').upper()
        
        if transaction_status != 'SUCCESS':
            return jsonify({'success': True, 'message': 'Transaction not successful'}), 200
            
        utr = decrypted_data.get('bank_ref_num')
        merchant_order_id = decrypted_data.get('txn_unique_id')
        amount = decrypted_data.get('txn_amount')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
            
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, order_id, amount as txn_amount, 
                           net_amount, charge_amount, callback_url
                    FROM payin_transactions
                    WHERE pg_partner = 'SHADVALPAY'
                    AND order_id = %s
                    LIMIT 1
                """, (merchant_order_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    return jsonify({'success': False, 'message': 'Transaction not found'}), 404
                    
                if txn['status'] == 'SUCCESS':
                    return jsonify({'success': True, 'message': 'Already processed'}), 200
                    
                # Update transaction
                cursor.execute("""
                    UPDATE payin_transactions
                    SET status = 'SUCCESS', 
                        bank_ref_no = %s,
                        payment_mode = 'UPI',
                        completed_at = NOW(), 
                        updated_at = NOW()
                    WHERE txn_id = %s
                """, (utr, txn['txn_id']))
                
                conn.commit()
                
                # Credit wallet
                if txn['merchant_id']:
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                    """, (txn['txn_id'],))
                    
                    if cursor.fetchone()['count'] == 0:
                        try:
                            from wallet_service import wallet_service as wallet_svc
                            wallet_svc.credit_unsettled_wallet(
                                merchant_id=txn['merchant_id'],
                                amount=float(txn['net_amount']),
                                description=f"PayIn received (Shadvalpay) - {merchant_order_id}",
                                reference_id=txn['txn_id']
                            )
                            wallet_svc.credit_admin_unsettled_wallet(
                                admin_id='admin',
                                amount=float(txn['charge_amount']),
                                description=f"PayIn charge (Shadvalpay) - {merchant_order_id}",
                                reference_id=txn['txn_id']
                            )
                        except Exception as e:
                            print(f"Wallet credit error: {e}")
                
                # Forward to merchant
                callback_url = txn.get('callback_url')
                if not callback_url and txn['merchant_id']:
                    cursor.execute("SELECT payin_callback_url FROM merchant_callbacks WHERE merchant_id = %s", (txn['merchant_id'],))
                    res = cursor.fetchone()
                    if res and res.get('payin_callback_url'):
                        callback_url = res['payin_callback_url']
                        
                if callback_url:
                    merchant_callback_data = {
                        'txn_id': txn['txn_id'],
                        'order_id': merchant_order_id,
                        'status': 'SUCCESS',
                        'utr': utr,
                        'pg_partner': 'SHADVALPAY',
                        'amount': float(txn['txn_amount']),
                        'net_amount': float(txn['net_amount']),
                        'charge_amount': float(txn['charge_amount'])
                    }
                    try:
                        requests.post(callback_url, json=merchant_callback_data, timeout=5)
                    except Exception as e:
                        print(f"Merchant callback failed: {e}")
                
                return jsonify({'success': True, 'message': 'Callback processed successfully'}), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Shadvalpay callback error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
