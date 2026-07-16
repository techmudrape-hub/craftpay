"""
Titanexam Callback Routes
Handles payin callbacks from Titanexam payment gateway
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json
import requests
import os

titanexam_callback_bp = Blueprint('titanexam_callback', __name__, url_prefix='/api/callback')

@titanexam_callback_bp.route('/titanexam/payin', methods=['POST'])
def titanexam_payin_callback():
    """
    Webhook endpoint for Titanexam payin status updates
    """
    try:
        callback_data = request.get_json(force=True, silent=True)
        if not callback_data:
            if request.form:
                callback_data = request.form.to_dict()
            elif request.values:
                callback_data = request.values.to_dict()
            else:
                raw_data = request.get_data(as_text=True)
                try:
                    callback_data = json.loads(raw_data)
                except:
                    pass

        if not callback_data:
            return jsonify({'success': False, 'message': 'No data received'}), 400

        print("=" * 80)
        print("Titanexam Payin Callback Received")
        print("=" * 80)
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")

        status = callback_data.get('status', '').upper()
        order_id = callback_data.get('orderId')
        transaction_id = callback_data.get('transactionId')
        amount = callback_data.get('amount')
        utr = callback_data.get('bank_ref', '')

        if not order_id:
            return jsonify({'success': False, 'message': 'Missing orderId'}), 400

        if status == 'COMPLETED':
            mapped_status = 'SUCCESS'
        elif status in ['FAILED', 'CANCELLED']:
            mapped_status = 'FAILED'
        else:
            mapped_status = 'INITIATED'

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, order_id, amount as txn_amount, 
                           net_amount, charge_amount, callback_url
                    FROM payin_transactions
                    WHERE pg_partner = 'TITANEXAM'
                    AND order_id = %s
                    LIMIT 1
                """, (order_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    return jsonify({'success': False, 'message': f'Transaction not found for orderId: {order_id}'}), 404

                # Update transaction
                if mapped_status in ['SUCCESS', 'FAILED']:
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s, 
                            bank_ref_no = %s,
                            payment_mode = 'UPI',
                            completed_at = NOW(), 
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, txn['txn_id']))
                else:
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s, 
                            bank_ref_no = %s,
                            payment_mode = 'UPI',
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, txn['txn_id']))
                
                conn.commit()

                # Credit wallet if SUCCESS
                if mapped_status == 'SUCCESS' and txn['merchant_id']:
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                    """, (txn['txn_id'],))
                    
                    if cursor.fetchone()['count'] == 0:
                        try:
                            from wallet_service import wallet_service as wallet_svc
                            
                            wallet_svc.credit_unsettled_wallet(
                                merchant_id=txn['merchant_id'],
                                amount=float(txn['net_amount']) if txn['net_amount'] else 0,
                                description=f"PayIn received (Titanexam) - {order_id}",
                                reference_id=txn['txn_id']
                            )
                            
                            wallet_svc.credit_admin_unsettled_wallet(
                                admin_id='admin',
                                amount=float(txn['charge_amount']) if txn['charge_amount'] else 0,
                                description=f"PayIn charge (Titanexam) - {order_id}",
                                reference_id=txn['txn_id']
                            )
                        except Exception as e:
                            print(f"Wallet credit error: {e}")

                # Forward callback to merchant
                callback_url = txn.get('callback_url')
                if not callback_url and txn['merchant_id']:
                    cursor.execute("""
                        SELECT payin_callback_url FROM merchant_callbacks
                        WHERE merchant_id = %s
                    """, (txn['merchant_id'],))
                    res = cursor.fetchone()
                    if res and res.get('payin_callback_url'):
                        callback_url = res['payin_callback_url']

                if callback_url:
                    merchant_callback_data = {
                        'txn_id': txn['txn_id'],
                        'order_id': order_id,
                        'status': mapped_status,
                        'utr': utr,
                        'pg_partner': 'TITANEXAM',
                        'amount': float(txn['txn_amount']) if txn['txn_amount'] else 0,
                        'net_amount': float(txn['net_amount']) if txn['net_amount'] else 0,
                        'charge_amount': float(txn['charge_amount']) if txn['charge_amount'] else 0
                    }
                    
                    try:
                        requests.post(
                            callback_url,
                            json=merchant_callback_data,
                            headers={'Content-Type': 'application/json'},
                            timeout=10
                        )
                    except Exception as e:
                        print(f"Failed to forward callback to merchant: {e}")

                # Forward callback to checkout page
                try:
                    backend_url = os.getenv('BACKEND_URL', 'http://localhost:5000')
                    checkout_callback_url = f"{backend_url}/api/checkout/titanexam/callback"
                    
                    checkout_callback_data = {
                        'order_id': order_id,
                        'status': mapped_status,
                        'amount': float(txn['txn_amount']) if txn['txn_amount'] else 0,
                        'utr': utr or '',
                        'txn_id': txn['txn_id'],
                        'bank_ref_no': utr or '',
                        'completed_at': datetime.now().isoformat()
                    }
                    
                    requests.post(
                        checkout_callback_url,
                        json=checkout_callback_data,
                        headers={'Content-Type': 'application/json'},
                        timeout=5
                    )
                except Exception as e:
                    print(f"Failed to forward callback to checkout page: {e}")

                return jsonify({
                    'success': True,
                    'message': 'Callback processed successfully',
                    'txn_id': txn['txn_id'],
                    'status': mapped_status
                }), 200

        finally:
            conn.close()

    except Exception as e:
        print(f"ERROR in Titanexam callback: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
