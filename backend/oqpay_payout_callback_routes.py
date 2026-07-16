"""
OQPay Payout Callback Routes
Handles payout callback webhooks from OQPay
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json
import requests
import traceback

oqpay_payout_callback_bp = Blueprint('oqpay_payout_callback', __name__, url_prefix='/api/callback')

@oqpay_payout_callback_bp.route('/oqpay/payout', methods=['POST', 'GET'])
def oqpay_payout_callback():
    """
    Webhook callback endpoint for OQPay payout status updates.
    """
    try:
        # Extract callback data
        callback_data = {}
        data_source = "UNKNOWN"

        if request.method == 'POST':
            if request.is_json:
                callback_data = request.get_json(silent=True) or {}
                data_source = "POST_JSON"
            elif request.form:
                callback_data = request.form.to_dict()
                data_source = "POST_FORM"
            elif request.data:
                try:
                    callback_data = json.loads(request.data.decode('utf-8'))
                    data_source = "POST_RAW_JSON"
                except:
                    pass
        else: # GET request
            callback_data = request.args.to_dict()
            data_source = "GET_ARGS"

        if not callback_data:
            print("[OQPay Payout Callback] ERROR: No callback data received")
            return jsonify({
                "status": "False",
                "message": "No data received"
            }), 400

        print("=" * 80)
        print(f"OQPay Payout Webhook Callback Received ({data_source})")
        print("=" * 80)
        print(f"Payload: {json.dumps(callback_data, indent=2)}")

        # Extract OQPay payout parameters
        # Adjust these parameter keys depending on OQPay webhook schema
        transaction_id = callback_data.get('transactionID') or callback_data.get('txn_id')
        transaction_ref_no = callback_data.get('transactionReferenceNo') or callback_data.get('reference_id')
        status = callback_data.get('status', '').upper() # SUCCESS, FAILED, ACPT
        utr = callback_data.get('utr', '')
        amount = callback_data.get('amount')

        # Try mapping keys if standard keys not found
        if not transaction_id:
            # Maybe the webhook sends key as pg_txn_id or client_txn_id
            transaction_id = callback_data.get('pg_txn_id') or callback_data.get('order_id')
        if not transaction_ref_no:
            transaction_ref_no = callback_data.get('merchant_order_id')

        # Fallback to keys if still not found
        if not transaction_id and not transaction_ref_no:
            print("[OQPay Payout Callback] ERROR: Missing transaction identifiers")
            return jsonify({
                "status": "False",
                "message": "Missing transaction ID or reference number"
            }), 400

        # Map status
        if status in ['SUCCESS', 'COMPLETED', 'CAPTURED', 'ACPT']:
            mapped_status = 'SUCCESS'
        elif status in ['FAILED', 'FAILURE', 'REJECTED', 'REJ']:
            mapped_status = 'FAILED'
        elif status in ['PENDING', 'PROCESSING', 'INPROCESS']:
            mapped_status = 'INPROCESS'
        else:
            mapped_status = 'INITIATED'

        print(f"OQPay Transaction ID: {transaction_id}")
        print(f"Reference No        : {transaction_ref_no}")
        print(f"Status              : {status} -> {mapped_status}")
        print(f"UTR                 : {utr}")

        conn = get_db_connection()
        if not conn:
            return jsonify({
                "status": "False",
                "message": "Database connection failed"
            }), 500

        try:
            with conn.cursor() as cursor:
                # Find payout transaction in db
                # We search by pg_txn_id, reference_id, order_id, or txn_id
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, reference_id, amount as txn_amount, 
                           callback_url, net_amount, order_id, pg_partner
                    FROM payout_transactions
                    WHERE pg_partner = 'OQPAY'
                    AND (pg_txn_id = %s OR reference_id = %s OR order_id = %s OR txn_id = %s)
                    LIMIT 1
                """, (transaction_id, transaction_ref_no, transaction_ref_no, transaction_id))

                txn = cursor.fetchone()

                if not txn:
                    print(f"[OQPay Payout Callback] ERROR: Transaction not found locally for ID: {transaction_id} or Ref: {transaction_ref_no}")
                    return jsonify({
                        "status": "False",
                        "message": "Transaction not found"
                    }), 404

                print(f"Found Payout Transaction: {txn['txn_id']}, Current Status: {txn['status']}")

                if txn['status'] == mapped_status and mapped_status == 'SUCCESS':
                    print("⚠ Duplicate SUCCESS callback - skipping processing")
                    return jsonify({
                        "status": "True",
                        "message": "Already processed successfully"
                    }), 200

                # Update transaction in DB
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

                # Deduct merchant wallet if SUCCESS
                if mapped_status == 'SUCCESS' and txn['merchant_id']:
                    from wallet_service import WalletService
                    wallet_svc = WalletService()

                    # Idempotency check for wallet deduction
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'DEBIT'
                    """, (txn['txn_id'],))

                    if cursor.fetchone()['count'] == 0:
                        debit_result = wallet_svc.debit_merchant_wallet(
                            merchant_id=txn['merchant_id'],
                            amount=float(txn['txn_amount']) if txn['txn_amount'] else 0,
                            description=f"Payout completed (OQPay) - Ref: {transaction_ref_no}",
                            reference_id=txn['txn_id']
                        )
                        if debit_result.get('success'):
                            print(f"✅ WALLET DEBITED - Net: ₹{txn['txn_amount']:.2f}")
                        else:
                            print(f"❌ WALLET DEDUCTION FAILED: {debit_result.get('message')}")
                    else:
                        print("⚠ Wallet already debited for this transaction")

                # Forward webhook notification to merchant
                callback_url = txn.get('callback_url')
                if callback_url:
                    callback_url = callback_url.strip()
                    if 'api/callback/oqpay' in callback_url:
                        callback_url = None

                if not callback_url and txn['merchant_id']:
                    cursor.execute("""
                        SELECT payout_callback_url FROM merchant_callbacks
                        WHERE merchant_id = %s
                    """, (txn['merchant_id'],))
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
                            print("⚠ Webhook already forwarded to merchant - skipping duplicate")
                            return jsonify({
                                "status": "True",
                                "message": "Callback processed successfully"
                            }), 200

                    # Prepare merchant payload
                    merchant_payload = {
                        'txn_id': txn['txn_id'],
                        'reference_id': txn['reference_id'] or txn['order_id'],
                        'status': mapped_status,
                        'utr': utr,
                        'pg_partner': 'OQPAY',
                        'pg_txn_id': transaction_id,
                        'amount': float(txn['net_amount']) if txn['net_amount'] else 0,
                        'message': f'Payout {mapped_status.lower()}'
                    }

                    print(f"📤 Forwarding payout callback to merchant: {callback_url}")
                    try:
                        resp = requests.post(
                            callback_url,
                            json=merchant_payload,
                            headers={'Content-Type': 'application/json'},
                            timeout=10
                        )
                        print(f"✅ Merchant response code: {resp.status_code}")

                        # Log callback log
                        cursor.execute("""
                            INSERT INTO callback_logs
                            (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        """, (
                            txn['merchant_id'],
                            txn['txn_id'],
                            callback_url,
                            json.dumps(merchant_payload),
                            resp.status_code,
                            resp.text[:1000]
                        ))
                        conn.commit()
                    except Exception as webhook_err:
                        print(f"❌ Webhook forwarding failed: {webhook_err}")
                        cursor.execute("""
                            INSERT INTO callback_logs
                            (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        """, (
                            txn['merchant_id'],
                            txn['txn_id'],
                            callback_url,
                            json.dumps(merchant_payload),
                            0,
                            str(webhook_err)[:1000]
                        ))
                        conn.commit()

            print("=" * 80)
            print("OQPay Payout Callback processed successfully")
            print("=" * 80)

            return jsonify({
                "status": "True",
                "message": "Callback processed successfully"
            }), 200

        finally:
            conn.close()

    except Exception as e:
        print(f"[OQPay Payout Callback] Error: {e}")
        traceback.print_exc()
        return jsonify({
            "status": "False",
            "message": f"Callback error: {str(e)}"
        }), 500
