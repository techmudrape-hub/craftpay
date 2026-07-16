"""
PayU Legal Halt Callback Routes
Handles callbacks/webhooks from PayU Legal Halt gateway
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json
from payu_legalhalt_service import payu_legalhalt_service

payu_legalhalt_callback_bp = Blueprint('payu_legalhalt_callback', __name__, url_prefix='/api/payin/callback/legalhalt')

@payu_legalhalt_callback_bp.route('/success', methods=['POST', 'GET'])
def payin_callback_payhalt_success():
    """PayU Legal Halt Return URL (Success)"""
    return jsonify({'success': True, 'message': 'Payment marked as success by client. Awaiting webhook confirmation.'}), 200

@payu_legalhalt_callback_bp.route('/failure', methods=['POST', 'GET'])
def payin_callback_payhalt_failure():
    """PayU Legal Halt Return URL (Failure)"""
    return jsonify({'success': False, 'message': 'Payment marked as failed by client.'}), 200

@payu_legalhalt_callback_bp.route('/webhook', methods=['POST'])
def payin_callback_payhalt_webhook():
    """PayU Legal Halt Webhook endpoint (S2S Callback)"""
    try:
        response_data = request.form.to_dict()
        if not response_data:
            if request.is_json:
                response_data = request.get_json()
        
        print(f"PayU Legal Halt Webhook Data: {response_data}")

        if not response_data:
            return jsonify({'success': False, 'message': 'No data received'}), 400

        # Verify hash
        if not payu_legalhalt_service.verify_webhook_hash(response_data):
            print("PayU Legal Halt Webhook Hash Verification Failed")
            return jsonify({'success': False, 'message': 'Invalid hash'}), 400
        
        txn_id = response_data.get('txnid')
        status = response_data.get('status')
        pg_txn_id = response_data.get('mihpayid')
        bank_ref_no = response_data.get('bank_ref_num')
        payment_mode = response_data.get('mode', 'UPI')
        
        status_mapping = {
            'success': 'SUCCESS',
            'failure': 'FAILED',
            'pending': 'PENDING'
        }
        mapped_status = status_mapping.get(status, 'PENDING')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
            
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT merchant_id, net_amount, charge_amount, status, order_id 
                    FROM payin_transactions 
                    WHERE txn_id = %s
                """, (txn_id,))
                
                txn_record = cursor.fetchone()
                
                if not txn_record:
                    return jsonify({'success': False, 'message': 'Transaction not found'}), 404
                    
                current_status = txn_record['status']
                
                if current_status != mapped_status:
                    if mapped_status == 'SUCCESS':
                        cursor.execute("""
                            UPDATE payin_transactions
                            SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                                completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (mapped_status, bank_ref_no, pg_txn_id, payment_mode, txn_id))
                        
                        cursor.execute("""
                            SELECT COUNT(*) as count FROM merchant_wallet_transactions
                            WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                        """, (txn_id,))
                        
                        if cursor.fetchone()['count'] == 0:
                            from wallet_service import wallet_service as wallet_svc
                            wallet_svc.credit_unsettled_wallet(
                                merchant_id=txn_record['merchant_id'],
                                amount=float(txn_record['net_amount']),
                                description=f"PayIn received (PayU Legal Halt) - {txn_record['order_id']}",
                                reference_id=txn_id
                            )
                            wallet_svc.credit_admin_unsettled_wallet(
                                admin_id='admin',
                                amount=float(txn_record['charge_amount']),
                                description=f"PayIn charge (PayU Legal Halt) - {txn_record['order_id']}",
                                reference_id=txn_id
                            )
                            
                    elif mapped_status == 'FAILED':
                        cursor.execute("""
                            UPDATE payin_transactions
                            SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                                completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (mapped_status, bank_ref_no, pg_txn_id, payment_mode, txn_id))
                        
                    conn.commit()
                    
                # Forward callback to merchant if configured
                print("=" * 80)
                print("MERCHANT CALLBACK FORWARDING - PAYU LEGAL HALT")
                print("=" * 80)
                
                try:
                    callback_url = None
                    cursor.execute("SELECT callback_url FROM payin_transactions WHERE txn_id = %s", (txn_id,))
                    txn_cb_row = cursor.fetchone()
                    if txn_cb_row and txn_cb_row.get('callback_url'):
                        callback_url = txn_cb_row['callback_url'].strip()
                        if not callback_url:
                            callback_url = None

                    if not callback_url and txn_record['merchant_id']:
                        cursor.execute("""
                            SELECT payin_callback_url FROM merchant_callbacks
                            WHERE merchant_id = %s
                        """, (txn_record['merchant_id'],))
                        merchant_callback = cursor.fetchone()
                        if merchant_callback and merchant_callback.get('payin_callback_url'):
                            callback_url = merchant_callback['payin_callback_url'].strip()
                            if not callback_url:
                                callback_url = None

                    if callback_url:
                        if mapped_status == 'SUCCESS':
                            cursor.execute("""
                                SELECT COUNT(*) as count FROM callback_logs
                                WHERE merchant_id = %s 
                                AND txn_id = %s 
                                AND response_code BETWEEN 200 AND 299
                                AND request_data LIKE %s
                            """, (txn_record['merchant_id'], txn_id, '%"status": "SUCCESS"%'))
                            
                            if cursor.fetchone()['count'] > 0:
                                print(f"⚠ SUCCESS callback already sent to merchant - skipping duplicate")
                                return jsonify({'success': True, 'message': 'Callback processed (duplicate prevented)'}), 200

                        import requests
                        total_amount = float(txn_record['net_amount'] or 0) + float(txn_record['charge_amount'] or 0)
                        
                        merchant_callback_data = {
                            'txn_id': txn_id,
                            'order_id': txn_record['order_id'],
                            'status': mapped_status,
                            'utr': bank_ref_no or '',
                            'pg_partner': 'PAYU_LEGALHALT',
                            'amount': total_amount,
                            'net_amount': float(txn_record['net_amount'] or 0),
                            'charge_amount': float(txn_record['charge_amount'] or 0)
                        }
                        
                        try:
                            callback_response = requests.post(
                                callback_url,
                                json=merchant_callback_data,
                                headers={'Content-Type': 'application/json'},
                                timeout=10
                            )
                            
                            cursor.execute("""
                                INSERT INTO callback_logs 
                                (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                            """, (
                                txn_record['merchant_id'], txn_id, callback_url,
                                json.dumps(merchant_callback_data), callback_response.status_code,
                                callback_response.text[:1000]
                            ))
                            conn.commit()
                        except requests.exceptions.RequestException as e:
                            cursor.execute("""
                                INSERT INTO callback_logs 
                                (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                            """, (
                                txn_record['merchant_id'], txn_id, callback_url,
                                json.dumps(merchant_callback_data), 0, str(e)[:1000]
                            ))
                            conn.commit()
                except Exception as e:
                    print(f"ERROR in merchant callback forwarding: {e}")
                    
        finally:
            conn.close()
            
        return "OK", 200

    except Exception as e:
        print(f"PayU Legal Halt webhook error: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500
