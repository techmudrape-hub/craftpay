"""
ORO Payin Callback Routes
Handles callbacks from ORO payment gateway
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from wallet_service import wallet_service
from callback_forwarder import forward_callback_to_merchant
import json
import traceback

oro_callback_bp = Blueprint('oro_callback', __name__, url_prefix='/api/callback/oro')

@oro_callback_bp.route('/payin', methods=['POST', 'GET'])
def oro_payin_callback():
    """Handle callback from ORO for payin transactions"""
    print("="*50)
    print("RECEIVED ORO PAYIN CALLBACK")
    print(f"Method: {request.method}")
    print(f"Headers: {dict(request.headers)}")
    
    try:
        # Support both JSON and form data
        data = None
        if request.is_json:
            data = request.get_json()
        elif request.form:
            data = request.form.to_dict()
        else:
            # Try to parse raw data
            raw_data = request.get_data()
            if raw_data:
                try:
                    data = json.loads(raw_data)
                except json.JSONDecodeError:
                    # Not JSON
                    pass
                    
        print(f"Parsed Callback Data: {json.dumps(data) if data else 'None'}")
        
        if not data:
            return jsonify({'status': 'Failed', 'message': 'No data received'}), 400
            
        # ORO callback format:
        # {
        #     "user_id": 2,
        #     "systemgenerateid": "OROTEST54856",
        #     "order_id": "order_SQCuf4pXRy5sd9",
        #     "utr": "965156832691",
        #     "amount": "10",
        #     "status": "success"
        # }
        
        order_id = data.get('order_id')
        utr = data.get('utr', '')
        callback_status = str(data.get('status', '')).upper()
        amount = data.get('amount')
        
        if not order_id:
            return jsonify({'status': 'Failed', 'message': 'Missing order_id'}), 400
            
        conn = get_db_connection()
        if not conn:
            return jsonify({'status': 'Failed', 'message': 'Database error'}), 500
            
        try:
            with conn.cursor() as cursor:
                # 1. Fetch transaction
                cursor.execute("""
                    SELECT txn_id, merchant_id, amount, charge_amount, net_amount, 
                           status, pg_partner, pg_txn_id, callback_url, order_id
                    FROM payin_transactions
                    WHERE order_id = %s OR txn_id = %s OR pg_txn_id = %s
                """, (order_id, order_id, order_id))
                
                txn = cursor.fetchone()
                
                if not txn:
                    print(f"Transaction not found for order_id: {order_id}")
                    return jsonify({'status': 'Failed', 'message': 'Transaction not found'}), 404
                    
                txn_id = txn['txn_id']
                merchant_id = txn['merchant_id']
                merchant_order_id = txn['order_id']
                callback_url = txn['callback_url']
                current_status = txn['status']
                
                print(f"Found Transaction: TXN ID={txn_id}, Merchant={merchant_id}, Current Status={current_status}")
                
                # Check if transaction is already in a final state
                if current_status in ['SUCCESS', 'FAILED']:
                    print(f"Transaction {txn_id} is already {current_status}. Skipping update.")
                    
                    # Still forward callback if needed
                    if callback_url and callback_status == 'SUCCESS' and current_status == 'SUCCESS':
                        # Forward to merchant
                        print(f"Forwarding callback to merchant URL: {callback_url}")
                        forward_payload = {
                            "status": "SUCCESS",
                            "message": "Payment Successful",
                            "txn_id": txn_id,
                            "order_id": merchant_order_id,
                            "amount": str(txn['amount']),
                            "utr": utr,
                            "timestamp": data.get('timestamp')
                        }
                        
                        forward_callback_to_merchant(
                            merchant_id=merchant_id,
                            callback_url=callback_url,
                            payload=forward_payload,
                            txn_id=txn_id,
                            provider='ORO'
                        )
                        
                    return jsonify({'status': 'Success', 'message': f'Transaction already {current_status}'}), 200
                
                # Map ORO status to system status
                if callback_status in ['SUCCESS', '1', 'TRUE']:
                    mapped_status = 'SUCCESS'
                elif callback_status in ['FAILED', 'FAILURE', '0', 'FALSE']:
                    mapped_status = 'FAILED'
                else:
                    mapped_status = 'PENDING'
                    
                print(f"Mapped Status: {mapped_status}")
                
                # 2. Process based on status
                if mapped_status == 'SUCCESS':
                    # Update transaction
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = 'SUCCESS',
                            bank_ref_no = %s,
                            pg_txn_id = COALESCE(pg_txn_id, %s),
                            payment_mode = 'UPI',
                            completed_at = NOW(),
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (utr, data.get('systemgenerateid', ''), txn_id))
                    
                    print(f"Updated transaction {txn_id} status to SUCCESS")
                    
                    # 3. Credit unsettled wallet (Idempotent check inside wallet_service)
                    print(f"Crediting merchant {merchant_id} unsettled wallet with {txn['net_amount']}")
                    wallet_result = wallet_service.credit_unsettled_wallet(
                        merchant_id=merchant_id,
                        amount=float(txn['net_amount']),
                        description=f"PayIn received (ORO) - {merchant_order_id}",
                        reference_id=txn_id
                    )
                    
                    if wallet_result['success']:
                        print("Merchant unsettled wallet credited successfully")
                    else:
                        print(f"Failed to credit merchant wallet: {wallet_result.get('message')}")
                        
                    # 4. Credit admin unsettled wallet
                    print(f"Crediting admin unsettled wallet with {txn['charge_amount']}")
                    admin_result = wallet_service.credit_admin_unsettled_wallet(
                        admin_id='admin',
                        amount=float(txn['charge_amount']),
                        description=f"PayIn charge (ORO) - {merchant_order_id}",
                        reference_id=txn_id
                    )
                    
                    if admin_result['success']:
                        print("Admin unsettled wallet credited successfully")
                    else:
                        print(f"Failed to credit admin wallet: {admin_result.get('message')}")
                        
                    conn.commit()
                    print("Transaction committed to database")
                    
                    # 5. Forward callback to merchant
                    if callback_url:
                        print(f"Forwarding SUCCESS callback to merchant URL: {callback_url}")
                        forward_payload = {
                            "status": "SUCCESS",
                            "message": "Payment Successful",
                            "txn_id": txn_id,
                            "order_id": merchant_order_id,
                            "amount": str(txn['amount']),
                            "utr": utr,
                            "pg_order_id": data.get('systemgenerateid', '')
                        }
                        
                        forward_callback_to_merchant(
                            merchant_id=merchant_id,
                            callback_url=callback_url,
                            payload=forward_payload,
                            txn_id=txn_id,
                            provider='ORO'
                        )
                    else:
                        print(f"No callback URL provided for transaction {txn_id}")
                        
                    return jsonify({'status': 'Success', 'message': 'Callback processed successfully'}), 200
                    
                elif mapped_status == 'FAILED':
                    # Update transaction to FAILED
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = 'FAILED',
                            completed_at = NOW(),
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (txn_id,))
                    
                    conn.commit()
                    print(f"Updated transaction {txn_id} status to FAILED")
                    
                    # Forward callback to merchant
                    if callback_url:
                        print(f"Forwarding FAILED callback to merchant URL: {callback_url}")
                        forward_payload = {
                            "status": "FAILED",
                            "message": "Payment Failed",
                            "txn_id": txn_id,
                            "order_id": merchant_order_id,
                            "amount": str(txn['amount'])
                        }
                        
                        forward_callback_to_merchant(
                            merchant_id=merchant_id,
                            callback_url=callback_url,
                            payload=forward_payload,
                            txn_id=txn_id,
                            provider='ORO'
                        )
                        
                    return jsonify({'status': 'Success', 'message': 'Failed callback processed'}), 200
                    
                else:
                    return jsonify({'status': 'Success', 'message': f'Status {mapped_status} ignored'}), 200
                    
        finally:
            conn.close()
            
    except Exception as e:
        print(f"ORO callback error: {e}")
        traceback.print_exc()
        return jsonify({'status': 'Failed', 'message': 'Internal Server Error'}), 500
