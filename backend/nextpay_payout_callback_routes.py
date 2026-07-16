"""
Nextpay Payout Callback Routes
Handles payout callbacks from Nextpay payment gateway
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json
import requests

nextpay_payout_callback_bp = Blueprint('nextpay_payout_callback', __name__, url_prefix='/api/callback')

@nextpay_payout_callback_bp.route('/nextpay/payout', methods=['POST'])
def nextpay_payout_callback():
    """
    Webhook endpoint for Nextpay payout status updates
    """
    try:
        callback_data = None
        data_source = None
        
        try:
            callback_data = request.get_json(force=True, silent=True)
            if callback_data:
                data_source = "JSON"
        except:
            pass
            
        if not callback_data:
            if request.form:
                callback_data = request.form.to_dict()
                data_source = "FORM"
            elif request.values:
                callback_data = request.values.to_dict()
                data_source = "VALUES"
                
        if not callback_data:
            raw_data = request.get_data(as_text=True)
            if raw_data:
                try:
                    callback_data = json.loads(raw_data)
                    data_source = "RAW"
                except:
                    from urllib.parse import parse_qs
                    try:
                        parsed = parse_qs(raw_data)
                        callback_data = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
                        data_source = "RAW_FORM"
                    except:
                        pass
                        
        if not callback_data:
            return jsonify({'success': False, 'message': 'No data received in request'}), 400

        print("=" * 80)
        print("Nextpay Payout Callback Received")
        print(f"Data Source: {data_source}")
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")
        
        event = callback_data.get('event', '')
        status = callback_data.get('status', '').upper()
        transaction_id = callback_data.get('transaction_id')
        utr = callback_data.get('utr_number')
        
        if not transaction_id:
            return jsonify({'success': False, 'message': 'Missing transaction_id'}), 400
            
        if status == 'SUCCESS' or event == 'payout.success':
            mapped_status = 'SUCCESS'
        elif status in ['FAILED', 'FAILURE'] or event == 'payout.failed':
            mapped_status = 'FAILED'
        else:
            mapped_status = 'INITIATED'

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
            
        try:
            with conn.cursor() as cursor:
                # Find transaction by order_id
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, order_id, amount, 
                           charge_amount, gst_amount, total_debit_amount, callback_url
                    FROM payout_transactions
                    WHERE pg_partner = 'NEXTPAY'
                    AND order_id = %s
                    LIMIT 1
                """, (transaction_id,))
                
                txn = cursor.fetchone()

                if not txn:
                    return jsonify({
                        'success': False, 
                        'message': f'Transaction not found for id: {transaction_id}'
                    }), 404

                print(f"Found Payout Transaction: {txn['txn_id']}, Current Status: {txn['status']}")
                
                # Update transaction
                if mapped_status in ['SUCCESS', 'FAILED']:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, 
                            bank_ref_no = %s,
                            completed_at = NOW(), 
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, txn['txn_id']))
                else:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, 
                            bank_ref_no = %s,
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, txn['txn_id']))
                    
                # Handle refunds if payout failed
                if mapped_status == 'FAILED' and txn['status'] != 'FAILED' and txn['merchant_id']:
                    # Ensure we haven't already refunded
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'PAYOUT_REFUND'
                    """, (txn['txn_id'],))
                    
                    if not cursor.fetchone()['count'] > 0:
                        try:
                            from wallet_service import wallet_service as wallet_svc
                            
                            refund_amount = float(txn['total_debit_amount']) if txn['total_debit_amount'] else 0
                            
                            if refund_amount > 0:
                                wallet_svc.credit_settled_wallet(
                                    merchant_id=txn['merchant_id'],
                                    amount=refund_amount,
                                    description=f"Payout Failed Refund (Nextpay) - {transaction_id}",
                                    reference_id=txn['txn_id']
                                )
                                print(f"Refunded {refund_amount} to merchant {txn['merchant_id']}")
                        except Exception as e:
                            print(f"WALLET REFUND ERROR: {e}")

                conn.commit()

                # Forward callback to merchant
                callback_url = txn.get('callback_url', '').strip() if txn.get('callback_url') else None
                
                if not callback_url and txn['merchant_id']:
                    cursor.execute("""
                        SELECT payout_callback_url FROM merchant_callbacks
                        WHERE merchant_id = %s
                    """, (txn['merchant_id'],))
                    merchant_callback = cursor.fetchone()
                    if merchant_callback and merchant_callback.get('payout_callback_url'):
                        callback_url = merchant_callback['payout_callback_url'].strip()

                if callback_url:
                    merchant_callback_data = {
                        'txn_id': txn['txn_id'],
                        'order_id': txn['order_id'],
                        'status': mapped_status,
                        'utr': utr,
                        'pg_partner': 'NEXTPAY',
                        'amount': float(txn['amount']) if txn['amount'] else 0,
                        'charge_amount': float(txn['charge_amount']) if txn['charge_amount'] else 0
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
                            txn['merchant_id'], txn['txn_id'], callback_url,
                            json.dumps(merchant_callback_data), callback_response.status_code,
                            callback_response.text[:1000]
                        ))
                        conn.commit()
                    except Exception as e:
                        print(f"Merchant payout callback failed: {e}")

                return jsonify({
                    'success': True,
                    'message': 'Payout Callback processed successfully',
                    'txn_id': txn['txn_id']
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"ERROR in Nextpay payout callback: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
