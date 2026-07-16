"""
Tpipay Payout Callback Routes
Handles payout status webhooks (callbacks) from Tpipay.

Tpipay sends a POST request to your configured callback URL when a
pending payout reaches a final status (success/failure).

Webhook payload example:
{
    "status": "success",
    "utr": "value_of_utr",
    "payid": "12345",
    "client_id": "PAYOUT-2025-0001",
    "amount": 2500.00
}

Expected response from us:
{
    "status": "success",
    "message": "Callback received and processed successfully."
}
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json
import requests
import traceback

tpipay_payout_callback_bp = Blueprint(
    'tpipay_payout_callback', __name__, url_prefix='/api/callback'
)


@tpipay_payout_callback_bp.route('/tpipay/payout', methods=['POST'])
def tpipay_payout_callback():
    """
    Webhook endpoint for Tpipay payout status updates.

    Tpipay sends POST JSON when a pending payout reaches its final state.
    We acknowledge with {"status": "success", "message": "..."} as per docs.
    """
    try:
        callback_data = None
        data_source = None

        # --- Parse incoming payload ---
        try:
            callback_data = request.get_json(force=True, silent=True)
            if callback_data:
                data_source = "JSON"
        except Exception:
            pass

        if not callback_data and request.form:
            callback_data = request.form.to_dict()
            data_source = "FORM"

        if not callback_data and request.data:
            try:
                callback_data = json.loads(request.data)
                data_source = "RAW_JSON"
            except Exception:
                pass

        if not callback_data:
            print("[TPIPAY Payout Callback] ERROR: No data received")
            return jsonify({
                'status': 'failure',
                'message': 'No data received in request'
            }), 400

        print("=" * 80)
        print("Tpipay Payout Callback Received")
        print("=" * 80)
        print(f"Data Source: {data_source}, Method: {request.method}")
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")

        # --- Extract fields from Tpipay payload ---
        status_raw = str(callback_data.get('status', '')).lower()
        utr = callback_data.get('utr', '')
        payid = str(callback_data.get('payid', ''))
        client_id = callback_data.get('client_id', '')   # this is our merchant_order_id
        amount = callback_data.get('amount')

        if not client_id:
            print("[TPIPAY Payout Callback] ERROR: Missing client_id")
            return jsonify({
                'status': 'failure',
                'message': 'Missing client_id'
            }), 400

        # --- Map Tpipay status to internal status ---
        if status_raw == 'success':
            mapped_status = 'SUCCESS'
        elif status_raw == 'failure':
            mapped_status = 'FAILED'
        elif status_raw == 'pending':
            mapped_status = 'INPROCESS'
        else:
            mapped_status = 'INITIATED'

        print(f"client_id (merchant_order_id): {client_id}")
        print(f"Status: {status_raw} -> {mapped_status}")
        print(f"UTR: {utr}, PayID: {payid}")

        conn = get_db_connection()
        if not conn:
            return jsonify({
                'status': 'failure',
                'message': 'Database connection failed'
            }), 500

        try:
            with conn.cursor() as cursor:
                # Find the payout transaction by client_id (stored as reference_id or order_id)
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, reference_id, amount AS txn_amount,
                           callback_url, net_amount, order_id, pg_partner
                    FROM payout_transactions
                    WHERE pg_partner = 'TPIPAY'
                    AND (reference_id = %s OR order_id = %s OR pg_txn_id = %s)
                    LIMIT 1
                """, (client_id, client_id, payid))

                txn = cursor.fetchone()

                if not txn:
                    print(f"[TPIPAY Payout Callback] Transaction not found for client_id: {client_id}")
                    return jsonify({
                        'status': 'failure',
                        'message': 'Transaction not found'
                    }), 404

                print(f"Found Transaction: {txn['txn_id']}, Current Status: {txn['status']}")

                # Prevent duplicate SUCCESS processing
                if txn['status'] == mapped_status and mapped_status == 'SUCCESS':
                    print("⚠ Duplicate SUCCESS callback – skipping")
                    return jsonify({
                        'status': 'success',
                        'message': 'Callback received and processed successfully.'
                    }), 200

                # --- Update transaction status ---
                if mapped_status in ['SUCCESS', 'FAILED']:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, pg_txn_id = %s,
                            completed_at = NOW(), updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, payid, txn['txn_id']))
                else:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, pg_txn_id = %s,
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, payid, txn['txn_id']))

                conn.commit()

                # --- Wallet deduction on SUCCESS (for merchant payouts) ---
                if mapped_status == 'SUCCESS' and txn['merchant_id']:
                    from wallet_service import WalletService
                    wallet_svc = WalletService()

                    # Guard against double-debit
                    cursor.execute("""
                        SELECT COUNT(*) AS count FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'DEBIT'
                    """, (txn['txn_id'],))

                    if cursor.fetchone()['count'] == 0:
                        debit_amount = float(txn['txn_amount']) if txn['txn_amount'] else 0
                        debit_result = wallet_svc.debit_merchant_wallet(
                            merchant_id=txn['merchant_id'],
                            amount=debit_amount,
                            description=f"Payout completed (TPIPAY) – Ref: {client_id}",
                            reference_id=txn['txn_id']
                        )
                        if debit_result.get('success'):
                            print(f"✅ WALLET DEBITED – amount: {debit_amount}")
                        else:
                            print(f"❌ WALLET DEDUCTION FAILED: {debit_result.get('message')}")

                # --- Refund wallet on FAILED (for merchant payouts) ---
                if mapped_status == 'FAILED' and txn['merchant_id'] and txn['status'] != 'FAILED':
                    cursor.execute("""
                        SELECT COUNT(*) AS count FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'PAYOUT_REFUND'
                    """, (txn['txn_id'],))

                    if not cursor.fetchone()['count'] > 0:
                        try:
                            from wallet_service import wallet_service as wallet_svc_instance
                            refund_amount = float(txn.get('net_amount') or txn.get('txn_amount') or 0)
                            if refund_amount > 0:
                                wallet_svc_instance.credit_settled_wallet(
                                    merchant_id=txn['merchant_id'],
                                    amount=refund_amount,
                                    description=f"Payout Failed Refund (TPIPAY) – {client_id}",
                                    reference_id=txn['txn_id']
                                )
                                print(f"✅ Refunded {refund_amount} to merchant {txn['merchant_id']}")
                        except Exception as refund_err:
                            print(f"❌ WALLET REFUND ERROR: {refund_err}")

                # --- Forward callback to merchant webhook ---
                callback_url = (txn.get('callback_url') or '').strip() or None

                if not callback_url and txn['merchant_id']:
                    cursor.execute(
                        "SELECT payout_callback_url FROM merchant_callbacks WHERE merchant_id = %s",
                        (txn['merchant_id'],)
                    )
                    merchant_cb = cursor.fetchone()
                    if merchant_cb and merchant_cb.get('payout_callback_url'):
                        callback_url = merchant_cb['payout_callback_url'].strip()

                if callback_url:
                    # Prevent sending a duplicate SUCCESS webhook
                    if mapped_status == 'SUCCESS':
                        cursor.execute("""
                            SELECT COUNT(*) AS count FROM callback_logs
                            WHERE merchant_id = %s AND txn_id = %s
                              AND response_code BETWEEN 200 AND 299
                              AND request_data LIKE %s
                        """, (txn['merchant_id'], txn['txn_id'], '%"status": "SUCCESS"%'))
                        if cursor.fetchone()['count'] > 0:
                            print("Merchant SUCCESS callback already sent – skipping")
                            return jsonify({
                                'status': 'success',
                                'message': 'Callback received and processed successfully.'
                            }), 200

                    merchant_payload = {
                        'txn_id': txn['txn_id'],
                        'reference_id': client_id,
                        'order_id': txn.get('order_id', ''),
                        'status': mapped_status,
                        'utr': utr,
                        'payid': payid,
                        'pg_partner': 'TPIPAY',
                        'amount': float(txn.get('net_amount') or txn.get('txn_amount') or 0),
                        'message': f'Payout {mapped_status.lower()}'
                    }
                    try:
                        resp = requests.post(
                            callback_url,
                            json=merchant_payload,
                            headers={'Content-Type': 'application/json'},
                            timeout=10
                        )
                        cursor.execute("""
                            INSERT INTO callback_logs
                                (merchant_id, txn_id, callback_url, request_data,
                                 response_code, response_data, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        """, (
                            txn['merchant_id'], txn['txn_id'], callback_url,
                            json.dumps(merchant_payload), resp.status_code,
                            resp.text[:1000]
                        ))
                        conn.commit()
                        print(f"Merchant callback sent – HTTP {resp.status_code}")
                    except Exception as cb_err:
                        print(f"Merchant callback failed: {cb_err}")
                        cursor.execute("""
                            INSERT INTO callback_logs
                                (merchant_id, txn_id, callback_url, request_data,
                                 response_code, response_data, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        """, (
                            txn['merchant_id'], txn['txn_id'], callback_url,
                            json.dumps(merchant_payload), 0, str(cb_err)[:1000]
                        ))
                        conn.commit()

                # Acknowledge to Tpipay as required by their docs
                return jsonify({
                    'status': 'success',
                    'message': 'Callback received and processed successfully.'
                }), 200

        finally:
            conn.close()

    except Exception as e:
        print(f"[TPIPAY Payout Callback] Error: {e}")
        traceback.print_exc()
        return jsonify({
            'status': 'failure',
            'message': 'Internal Server Error'
        }), 500
