"""
SectorPe Payout Callback Routes
Handles payout status callbacks from SectorPe
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json
import requests
import traceback

sectorpe_payout_callback_bp = Blueprint('sectorpe_payout_callback', __name__, url_prefix='/api/callback')

@sectorpe_payout_callback_bp.route('/sectorpe/payout', methods=['GET', 'POST'])
def sectorpe_payout_callback():
    """
    Webhook endpoint for SectorPe payout status updates
    SectorPe sends callbacks via GET method with query parameters.
    We also accept POST to be flexible in case they change it.
    
    Expected GET callback format (from docs):
    ?order_id=PY300567&status=success&amount=500&mobile=9876543210&utr=UTR987654321&redirect_url=...
    """
    try:
        # Get callback data (SectorPe uses GET with query string)
        callback_data = request.args.to_dict()
        data_source = "QUERY_STRING"
        
        # Fallback for POST requests
        if not callback_data and request.method == 'POST':
            if request.is_json:
                callback_data = request.get_json(silent=True) or {}
                data_source = "JSON"
            elif request.form:
                callback_data = request.form.to_dict()
                data_source = "FORM"
            elif request.data:
                try:
                    callback_data = json.loads(request.data)
                    data_source = "RAW_JSON"
                except:
                    pass
        
        if not callback_data:
            print(f"[SectorPe Payout Callback] ERROR: No data received")
            return jsonify({
                'success': False,
                'message': 'No data received in request'
            }), 400
            
        print("=" * 80)
        print("SectorPe Payout Callback Received")
        print("=" * 80)
        print(f"Data Source: {data_source}, Method: {request.method}")
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")
        
        merchant_order_id = callback_data.get('order_id')
        status = callback_data.get('status', '').lower()
        amount = callback_data.get('amount')
        utr = callback_data.get('utr', '')
        
        if not merchant_order_id:
            print(f"[SectorPe Payout Callback] ERROR: Missing order_id")
            return jsonify({
                'success': False,
                'message': 'Missing order_id'
            }), 400
            
        # Map status
        if status == 'success':
            mapped_status = 'SUCCESS'
        elif status == 'failed':
            mapped_status = 'FAILED'
        elif status == 'pending':
            mapped_status = 'INPROCESS'
        else:
            mapped_status = 'INITIATED'
            
        print(f"Merchant Order ID: {merchant_order_id}")
        print(f"Status: {status} -> {mapped_status}")
        print(f"UTR: {utr}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
            
        try:
            with conn.cursor() as cursor:
                # Find transaction by reference_id, then order_id, then pg_txn_id
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, reference_id, amount as txn_amount, 
                           callback_url, net_amount, order_id, pg_partner
                    FROM payout_transactions
                    WHERE pg_partner IN ('PES', 'SECTORPE', 'SectorPe', 'Sectorpe', 'sectorpe')
                    AND (reference_id = %s OR order_id = %s OR pg_txn_id = %s)
                    LIMIT 1
                """, (merchant_order_id, merchant_order_id, merchant_order_id))
                
                txn = cursor.fetchone()
                
                if not txn:
                    print(f"[SectorPe Payout Callback] Transaction not found for: {merchant_order_id}")
                    return jsonify({
                        'success': False,
                        'message': 'Transaction not found'
                    }), 404
                    
                print(f"Found Transaction: {txn['txn_id']}, Current Status: {txn['status']}")
                
                if txn['status'] == mapped_status and mapped_status == 'SUCCESS':
                    print(f"⚠ Duplicate SUCCESS callback - skipping")
                    return jsonify({'success': True, 'message': 'Already processed'}), 200
                    
                # Update transaction
                if mapped_status in ['SUCCESS', 'FAILED']:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, txn['txn_id']))
                else:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, txn['txn_id']))
                conn.commit()
                
                # Deduct wallet if status changed to SUCCESS
                if mapped_status == 'SUCCESS' and txn['merchant_id']:
                    # Use WalletService
                    from wallet_service import WalletService
                    wallet_svc = WalletService()
                    
                    # Check if already debited to prevent double debit
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'DEBIT'
                    """, (txn['txn_id'],))
                    
                    if cursor.fetchone()['count'] == 0:
                        debit_result = wallet_svc.debit_merchant_wallet(
                            merchant_id=txn['merchant_id'],
                            amount=float(txn['txn_amount']) if txn['txn_amount'] else 0,
                            description=f"Payout completed (PES) - Ref: {merchant_order_id}",
                            reference_id=txn['txn_id']
                        )
                        if debit_result['success']:
                            print(f"✅ WALLET DEBITED")
                        else:
                            print(f"❌ WALLET DEDUCTION FAILED: {debit_result['message']}")
                
                # Forward to merchant webhook
                callback_url = txn.get('callback_url')
                if callback_url:
                    callback_url = callback_url.strip()
                
                if not callback_url and txn['merchant_id']:
                    cursor.execute("SELECT payout_callback_url FROM merchant_callbacks WHERE merchant_id = %s", (txn['merchant_id'],))
                    merchant_cb = cursor.fetchone()
                    if merchant_cb and merchant_cb.get('payout_callback_url'):
                        callback_url = merchant_cb['payout_callback_url'].strip()
                        
                if callback_url:
                    # Prevent duplicate webhook sends
                    if mapped_status == 'SUCCESS':
                        cursor.execute("""
                            SELECT COUNT(*) as count FROM callback_logs
                            WHERE merchant_id = %s AND txn_id = %s AND response_code BETWEEN 200 AND 299
                            AND request_data LIKE %s
                        """, (txn['merchant_id'], txn['txn_id'], '%"status": "SUCCESS"%'))
                        if cursor.fetchone()['count'] > 0:
                            print("Merchant callback already sent for SUCCESS")
                            return jsonify({'success': True, 'message': 'Processed successfully'}), 200

                    payload = {
                        'txn_id': txn['txn_id'],
                        'reference_id': merchant_order_id,
                        'status': mapped_status,
                        'utr': utr,
                        'pg_partner': 'PES',
                        'pg_txn_id': merchant_order_id,
                        'amount': float(txn['net_amount']) if txn['net_amount'] else 0,
                        'message': f'Payout {mapped_status.lower()}'
                    }
                    try:
                        resp = requests.post(callback_url, json=payload, headers={'Content-Type': 'application/json'}, timeout=10)
                        cursor.execute("""
                            INSERT INTO callback_logs (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        """, (txn['merchant_id'], txn['txn_id'], callback_url, json.dumps(payload), resp.status_code, resp.text[:1000]))
                        conn.commit()
                    except Exception as e:
                        cursor.execute("""
                            INSERT INTO callback_logs (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        """, (txn['merchant_id'], txn['txn_id'], callback_url, json.dumps(payload), 0, str(e)[:1000]))
                        conn.commit()
                        
                return jsonify({'success': True, 'message': 'Callback processed successfully'}), 200
        finally:
            conn.close()
    except Exception as e:
        print(f"[SectorPe Payout Callback] Error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal Server Error'}), 500
