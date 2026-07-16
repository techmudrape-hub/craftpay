"""
OQPay Payin Callback Routes
Handles server-to-server webhook callbacks from OQPay
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json
import requests

oqpay_callback_bp = Blueprint('oqpay_callback', __name__, url_prefix='/api/callback')

@oqpay_callback_bp.route('/oqpay/payin', methods=['POST', 'GET'])
def oqpay_payin_callback():
    """
    Webhook callback endpoint for OQPay payin status updates.
    OQPay supports webhooks in JSON or form-encoded/GET formats.
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
            print("[OQPay Callback] ERROR: No callback data received")
            return jsonify({
                "status": "False",
                "message": "No data received"
            }), 400

        print("=" * 80)
        print(f"OQPay Payin Webhook Callback Received ({data_source})")
        print("=" * 80)
        print(f"Payload: {json.dumps(callback_data, indent=2)}")

        # ----------------------------------------------------------------
        # Detect callback format:
        #
        # NEW format (from OQPAY team response):
        #   { "txn_id": "pay_...", "ref_id": "OQP...", "amount": 50.0,
        #     "status": "SUCCESS", "message": "...", "utr": "...",
        #     "callback_time": "..." }
        #
        # OLD format (original):
        #   { "registrationID": "...", "txnRefranceID": "...",
        #     "paymentStatus": "captured", "rrn": "...", "method": "...",
        #     "status": "True"/"False" }
        # ----------------------------------------------------------------
        is_new_format = 'ref_id' in callback_data and 'utr' in callback_data

        if is_new_format:
            # ---- NEW FORMAT ----
            oqpay_txn_ref_id = str(callback_data.get('ref_id', '')).strip()   # maps to pg_txn_id
            oqpay_internal_txn_id = str(callback_data.get('txn_id', '')).strip()
            amount = callback_data.get('amount', '0')
            rrn = str(callback_data.get('utr', ''))                            # bank UTR
            method = 'UPI'                                                     # assume UPI for new format
            raw_status = str(callback_data.get('status', '')).upper()

            print(f"[OQPay Callback] Detected NEW callback format")
            print(f"OQPay Internal TXN ID : {oqpay_internal_txn_id}")
            print(f"OQPay Ref ID (pg_txn) : {oqpay_txn_ref_id}")
            print(f"UTR                   : {rrn}")
            print(f"Raw Status            : {raw_status}")

            if raw_status == 'SUCCESS':
                mapped_status = 'SUCCESS'
            elif raw_status in ['FAILED', 'FAILURE', 'REJECTED', 'REFUNDED']:
                mapped_status = 'FAILED'
            else:
                mapped_status = 'INITIATED'

        else:
            # ---- OLD FORMAT ----
            registration_id = callback_data.get('registrationID', '')
            oqpay_txn_ref_id = str(callback_data.get('txnRefranceID', '')).strip()  # Note: spelling txnRefranceID
            amount = callback_data.get('amount', '0')
            payment_status = callback_data.get('paymentStatus', '').lower()    # e.g. "captured"
            rrn = callback_data.get('rrn', '')                                 # Bank reference number
            method = callback_data.get('method', 'upi')                       # Payment method
            api_status = callback_data.get('status', 'False')                 # Request status ("True"/"False")

            print(f"[OQPay Callback] Detected OLD callback format")
            print(f"OQPay Ref ID   : {oqpay_txn_ref_id}")
            print(f"Payment Status : {payment_status}")
            print(f"Bank RRN       : {rrn}")

            if payment_status == 'captured' or api_status == 'True':
                mapped_status = 'SUCCESS'
            elif payment_status in ['failed', 'rejected', 'refunded']:
                mapped_status = 'FAILED'
            else:
                mapped_status = 'INITIATED'

        if not oqpay_txn_ref_id:
            print("[OQPay Callback] ERROR: Missing transaction reference ID (txnRefranceID / ref_id)")
            return jsonify({
                "status": "False",
                "message": "Missing transaction reference ID"
            }), 400

        print(f"Mapped Status  : {mapped_status}")

        # Update database and perform wallet credit
        conn = get_db_connection()
        if not conn:
            print("[OQPay Callback] ERROR: Database connection failed")
            return jsonify({
                "status": "False",
                "message": "Database connection failed"
            }), 500

        try:
            with conn.cursor() as cursor:
                # Find transaction by pg_txn_id (which stores oqpay_txn_ref_id)
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, order_id, amount as txn_amount,
                           net_amount, charge_amount, callback_url
                    FROM payin_transactions
                    WHERE pg_partner = 'OQPAY'
                    AND pg_txn_id = %s
                    LIMIT 1
                """, (oqpay_txn_ref_id,))

                txn = cursor.fetchone()

                if not txn:
                    print(f"[OQPay Callback] ERROR: Transaction not found for ref ID: {oqpay_txn_ref_id}")
                    return jsonify({
                        "status": "False",
                        "message": f"Transaction not found for reference ID {oqpay_txn_ref_id}"
                    }), 404

                print(f"Found Transaction: {txn['txn_id']}, Current Status: {txn['status']}")

                # Only update if status is not already final
                if txn['status'] != mapped_status:
                    if mapped_status in ['SUCCESS', 'FAILED']:
                        cursor.execute("""
                            UPDATE payin_transactions
                            SET status = %s,
                                bank_ref_no = %s,
                                payment_mode = %s,
                                completed_at = NOW(),
                                updated_at = NOW()
                            WHERE txn_id = %s
                        """, (mapped_status, rrn, method.upper(), txn['txn_id']))
                        print(f"✓ Local transaction status updated to {mapped_status}")
                    else:
                        cursor.execute("""
                            UPDATE payin_transactions
                            SET status = %s,
                                bank_ref_no = %s,
                                payment_mode = %s,
                                updated_at = NOW()
                            WHERE txn_id = %s
                        """, (mapped_status, rrn, method.upper(), txn['txn_id']))
                    conn.commit()

                # Credit wallet if SUCCESS
                if mapped_status == 'SUCCESS' and txn['merchant_id']:
                    # Check wallet credit idempotency
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                    """, (txn['txn_id'],))

                    already_credited = cursor.fetchone()['count'] > 0

                    if already_credited:
                        print(f"⚠ Wallet already credited for this transaction - skipping duplicate credit")
                    else:
                        try:
                            from wallet_service import wallet_service as wallet_svc

                            # Credit merchant unsettled wallet
                            credit_result = wallet_svc.credit_unsettled_wallet(
                                merchant_id=txn['merchant_id'],
                                amount=float(txn['net_amount']) if txn['net_amount'] else 0,
                                description=f"PayIn received (OQPay) - {oqpay_txn_ref_id}",
                                reference_id=txn['txn_id']
                            )

                            if credit_result.get('success'):
                                print(f"✅ MERCHANT WALLET CREDITED - Net: ₹{txn['net_amount']:.2f}")
                            else:
                                print(f"❌ MERCHANT WALLET CREDIT FAILED: {credit_result.get('message', 'Unknown error')}")

                            # Credit admin unsettled wallet
                            admin_credit_result = wallet_svc.credit_admin_unsettled_wallet(
                                admin_id='admin',
                                amount=float(txn['charge_amount']) if txn['charge_amount'] else 0,
                                description=f"PayIn charge (OQPay) - {oqpay_txn_ref_id}",
                                reference_id=txn['txn_id']
                            )

                            if admin_credit_result.get('success'):
                                print(f"✅ ADMIN WALLET CREDITED - Charge: ₹{txn['charge_amount']:.2f}")
                            else:
                                print(f"❌ ADMIN WALLET CREDIT FAILED: {admin_credit_result.get('message', 'Unknown error')}")

                        except Exception as wallet_error:
                            print(f"❌ WALLET CREDIT ERROR: {wallet_error}")

                # Send webhook notification to merchant
                callback_url = None
                if txn.get('callback_url'):
                    callback_url = txn['callback_url'].strip()
                    # Skip internal OQPay callback URLs
                    if callback_url and 'api/callback/oqpay' in callback_url:
                        callback_url = None

                # Fallback to merchant config callback if not in transaction
                if not callback_url and txn['merchant_id']:
                    cursor.execute("""
                        SELECT payin_callback_url FROM merchant_callbacks
                        WHERE merchant_id = %s
                    """, (txn['merchant_id'],))
                    merchant_cb = cursor.fetchone()
                    if merchant_cb and merchant_cb.get('payin_callback_url'):
                        callback_url = merchant_cb['payin_callback_url'].strip()

                if callback_url:
                    # Prevent duplicate webhook sends
                    if mapped_status == 'SUCCESS':
                        cursor.execute("""
                            SELECT COUNT(*) as count FROM callback_logs
                            WHERE merchant_id = %s AND txn_id = %s AND response_code BETWEEN 200 AND 299
                            AND request_data LIKE %s
                        """, (txn['merchant_id'], txn['txn_id'], '%"status": "SUCCESS"%'))
                        
                        if cursor.fetchone()['count'] > 0:
                            print("⚠ Merchant callback already sent for SUCCESS - skipping duplicate webhook")
                            return jsonify({
                                "status": "True",
                                "message": "Transaction completed successfully"
                            }), 200

                    # Prepare merchant payload
                    merchant_payload = {
                        'txn_id': txn['txn_id'],
                        'order_id': txn['order_id'],
                        'status': mapped_status,
                        'utr': rrn,
                        'pg_partner': 'OQPAY',
                        'amount': float(txn['txn_amount']) if txn['txn_amount'] else 0,
                        'net_amount': float(txn['net_amount']) if txn['net_amount'] else 0,
                        'charge_amount': float(txn['charge_amount']) if txn['charge_amount'] else 0
                    }

                    print(f"📤 Forwarding payin callback to merchant: {callback_url}")
                    try:
                        resp = requests.post(
                            callback_url,
                            json=merchant_payload,
                            headers={'Content-Type': 'application/json'},
                            timeout=10
                        )
                        print(f"✅ Merchant response: {resp.status_code}")
                        
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
            print("OQPay Payin Callback processed successfully")
            print("=" * 80)

            return jsonify({
                "status": "True",
                "message": "Transaction completed successfully"
            }), 200

        finally:
            conn.close()

    except Exception as e:
        print(f"[OQPay Callback] Internal Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "False",
            "message": f"Callback error: {str(e)}"
        }), 500
