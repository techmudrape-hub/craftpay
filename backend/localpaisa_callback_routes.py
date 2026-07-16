"""
Localpaisa Callback Routes
Handles callbacks from Localpaisa payment gateway
"""

from flask import Blueprint, request, jsonify
import json
import requests
from database import get_db_connection
from datetime import datetime

localpaisa_callback_bp = Blueprint('localpaisa_callback', __name__, url_prefix='/api/callback')

@localpaisa_callback_bp.route('/localpaisa/payin', methods=['POST'])
def localpaisa_payin_callback():
    try:
        print("=" * 80)
        print("Localpaisa Payin Callback Received")
        print("=" * 80)
        
        callback_data = None
        if request.is_json:
            callback_data = request.json
        else:
            try:
                callback_data = json.loads(request.data.decode('utf-8'))
            except:
                pass
                
        if not callback_data:
            return jsonify({'success': False, 'message': 'Invalid data format'}), 400
            
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")
        
        event = callback_data.get('event')
        pg_txn_id = callback_data.get('transaction_id')
        status = callback_data.get('status')
        utr = callback_data.get('utr_number')
        
        if not pg_txn_id:
            return jsonify({'success': False, 'message': 'Missing transaction_id'}), 400
            
        mapped_status = 'INITIATED'
        if status and status.upper() == 'SUCCESS':
            mapped_status = 'SUCCESS'
        elif status and status.upper() in ['FAILED', 'FAILURE']:
            mapped_status = 'FAILED'
            
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
            
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT txn_id, order_id, status, merchant_id, amount as txn_amount, net_amount, charge_amount, callback_url
                    FROM payin_transactions
                    WHERE pg_txn_id = %s AND pg_partner = 'LOCALPAISA'
                """, (pg_txn_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    # Try fallback to matching by utr if pg_txn_id match fails (rare but possible)
                    if utr:
                        cursor.execute("""
                            SELECT txn_id, order_id, status, merchant_id, amount as txn_amount, net_amount, charge_amount, callback_url
                            FROM payin_transactions
                            WHERE bank_ref_no = %s AND pg_partner = 'LOCALPAISA'
                        """, (utr,))
                        txn = cursor.fetchone()
                        
                if not txn:
                    return jsonify({'success': False, 'message': 'Transaction not found'}), 404
                    
                track_id = txn['order_id']
                
                if mapped_status == 'SUCCESS':
                    # First, update the transaction status
                    if txn['status'] != 'SUCCESS':
                        cursor.execute("""
                            UPDATE payin_transactions
                            SET status = %s, bank_ref_no = %s, payment_mode = 'UPI', completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (mapped_status, utr, txn['txn_id']))
                    elif utr and utr != txn.get('bank_ref_no'):
                        cursor.execute("""
                            UPDATE payin_transactions
                            SET bank_ref_no = %s, payment_mode = 'UPI', updated_at = NOW()
                            WHERE txn_id = %s
                        """, (utr, txn['txn_id']))
                        
                    conn.commit()
                    
                    # Credit wallet if status is SUCCESS and merchant_id exists
                    if txn['merchant_id']:
                        cursor.execute("""
                            SELECT COUNT(*) as count FROM merchant_wallet_transactions
                            WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                        """, (txn['txn_id'],))
                        
                        wallet_credit_exists = cursor.fetchone()['count'] > 0
                        
                        if wallet_credit_exists:
                            print(f"⚠ Wallet already credited for this transaction - skipping")
                        else:
                            try:
                                net_amount = float(txn['net_amount']) if txn['net_amount'] else float(txn['txn_amount'])
                                charge_amount = float(txn['charge_amount']) if txn['charge_amount'] else 0.00
                                
                                from wallet_service import wallet_service as wallet_svc
                                
                                # Credit merchant unsettled wallet
                                wallet_result = wallet_svc.credit_unsettled_wallet(
                                    merchant_id=txn['merchant_id'],
                                    amount=net_amount,
                                    description=f"Localpaisa Payin credited - {track_id}",
                                    reference_id=txn['txn_id']
                                )
                                
                                if wallet_result.get('success'):
                                    print(f"✓ Credited merchant unsettled wallet: ₹{net_amount}")
                                else:
                                    print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")
                                    
                                # Credit admin unsettled wallet
                                admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                    admin_id='admin',
                                    amount=charge_amount,
                                    description=f"Localpaisa Payin charge - {track_id}",
                                    reference_id=txn['txn_id']
                                )
                                
                                if admin_wallet_result.get('success'):
                                    print(f"✓ Credited admin unsettled wallet: ₹{charge_amount}")
                                else:
                                    print(f"✗ Failed to credit admin unsettled wallet: {admin_wallet_result.get('message')}")
                            
                            except Exception as wallet_error:
                                print(f"❌ WALLET CREDIT ERROR: {wallet_error}")
                                import traceback
                                traceback.print_exc()
                                # Continue processing - don't let wallet errors stop callback forwarding
                else:
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s, bank_ref_no = %s, updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, txn['txn_id']))
                    conn.commit()
                    
                forward_callback_to_merchant(cursor, txn, callback_data, mapped_status, track_id, utr, pg_txn_id)
                return jsonify({'success': True, 'message': 'Callback processed successfully'})
                
        except Exception as e:
            print(f"ERROR processing callback: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            if conn:
                conn.close()
                
    except Exception as e:
        print(f"ERROR in callback: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

def forward_callback_to_merchant(cursor, txn, original_callback_data, status, track_id, utr, pg_txn_id):
    try:
        callback_url = None
        if txn.get('callback_url'):
            callback_url = txn['callback_url'].strip()
            if not callback_url:
                callback_url = None
                
        if not callback_url:
            cursor.execute("SELECT payin_callback_url FROM merchant_callbacks WHERE merchant_id = %s", (txn['merchant_id'],))
            merchant_callback = cursor.fetchone()
            if merchant_callback and merchant_callback.get('payin_callback_url'):
                callback_url = merchant_callback['payin_callback_url'].strip()
                if not callback_url:
                    callback_url = None
                    
        if not callback_url:
            return
            
        merchant_callback_data = {
            'status': status,
            'txnid': track_id,
            'amount': str(txn['txn_amount']),
            'productinfo': 'Payment',
            'firstname': '',
            'email': '',
            'phone': '',
            'utr': utr or '',
            'pg_txn_id': pg_txn_id or '',
            'pg_partner': 'LOCALPAISA',
            'timestamp': datetime.now().isoformat()
        }
        
        response = requests.post(callback_url, json=merchant_callback_data, timeout=30, headers={'Content-Type': 'application/json'})
        
        cursor.execute("""
            INSERT INTO callback_logs (txn_id, merchant_id, callback_url, request_data, response_code, response_data, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (txn['txn_id'], txn['merchant_id'], callback_url, json.dumps(merchant_callback_data), response.status_code, response.text[:1000]))
    except requests.exceptions.Timeout:
        cursor.execute("""
            INSERT INTO callback_logs (txn_id, merchant_id, callback_url, request_data, response_code, response_data, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (txn['txn_id'], txn['merchant_id'], callback_url, json.dumps(merchant_callback_data), 0, 'TIMEOUT'))
    except Exception as e:
        cursor.execute("""
            INSERT INTO callback_logs (txn_id, merchant_id, callback_url, request_data, response_code, response_data, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (txn['txn_id'], txn['merchant_id'], callback_url, json.dumps(merchant_callback_data), -1, str(e)[:1000]))
