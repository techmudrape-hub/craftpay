"""
ORO Payout Callback Routes
Handles payout status webhook callbacks from ORO.
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json
import requests as req_lib

oro_payout_callback_bp = Blueprint(
    'oro_payout_callback', __name__, url_prefix='/api/callback'
)

@oro_payout_callback_bp.route('/oro/payout', methods=['POST'])
def oro_payout_callback():
    """
    Webhook endpoint for ORO payout status updates.
    Callback URL to give ORO:
        https://api.craftpay.in/api/callback/oro/payout
    """
    try:
        callback_data = None
        data_source = None

        # Try JSON first
        try:
            callback_data = request.get_json(force=True, silent=True)
            if callback_data:
                data_source = "JSON"
        except Exception:
            pass

        # Fallback: form data
        if not callback_data:
            if request.form:
                callback_data = request.form.to_dict()
                data_source = "FORM"
            elif request.values:
                callback_data = request.values.to_dict()
                data_source = "VALUES"

        # Fallback: raw body
        if not callback_data:
            raw_data = request.get_data(as_text=True)
            if raw_data:
                try:
                    callback_data = json.loads(raw_data)
                    data_source = "RAW"
                except Exception:
                    pass

        if not callback_data:
            print(f"[ORO Payout CB] ERROR: No data received")
            return jsonify({'status': 'error', 'message': 'No data received'}), 400

        print("=" * 80)
        print("ORO Payout Callback Received")
        print("=" * 80)
        print(f"Data Source   : {data_source}")
        print(f"Callback Data : {json.dumps(callback_data, indent=2)}")

        # Parse callback data
        pg_txn_id = (
            callback_data.get('trx_id') or
            callback_data.get('systemid') or
            ''
        ).strip()
        
        reference_id = (
            callback_data.get('cus_trx_id') or
            callback_data.get('order_id') or
            ''
        ).strip()

        raw_status = (
            callback_data.get('status') or
            ''
        ).upper().strip()

        utr = (
            callback_data.get('utr') or
            ''
        ).strip()

        if not pg_txn_id and not reference_id:
            print(f"[ORO Payout CB] ERROR: Missing trx_id and cus_trx_id")
            return jsonify({'status': 'error', 'message': 'Missing identifier'}), 400

        # Map status
        if raw_status in ('SUCCESS', 'SUCCESSFUL', 'COMPLETED'):
            mapped_status = 'SUCCESS'
        elif raw_status in ('FAILED', 'FAILURE', 'ERROR'):
            mapped_status = 'FAILED'
        elif raw_status in ('PENDING', 'PROCESSING', 'INITIATED'):
            mapped_status = 'INPROCESS'
        else:
            mapped_status = 'INITIATED'

        print(f"Txn_ID/PG_Txn_ID : {pg_txn_id}")
        print(f"Ref_ID/Order_ID  : {reference_id}")
        print(f"TXN_Status       : {raw_status} -> {mapped_status}")
        print(f"UTR              : {utr}")

        conn = get_db_connection()
        if not conn:
            return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500

        try:
            with conn.cursor() as cursor:
                # Look up transaction in DB
                query_params = []
                where_clauses = ["pg_partner = 'ORO'"]
                
                if reference_id:
                    where_clauses.append("(reference_id = %s OR order_id = %s)")
                    query_params.extend([reference_id, reference_id])
                elif pg_txn_id:
                    where_clauses.append("pg_txn_id = %s")
                    query_params.append(pg_txn_id)
                else:
                    return jsonify({'status': 'error', 'message': 'No valid identifier to find txn'}), 400

                query = f"""
                    SELECT txn_id, status, merchant_id, reference_id,
                           amount AS txn_amount, callback_url, net_amount,
                           order_id, pg_partner, pg_txn_id AS pg_txn_id_db
                    FROM payout_transactions
                    WHERE {" AND ".join(where_clauses)}
                    LIMIT 1
                """
                cursor.execute(query, tuple(query_params))
                txn = cursor.fetchone()

                if not txn:
                    # Retry with pg_txn_id fallback if reference_id failed
                    if reference_id and pg_txn_id:
                        cursor.execute("""
                            SELECT txn_id, status, merchant_id, reference_id,
                                   amount AS txn_amount, callback_url, net_amount,
                                   order_id, pg_partner, pg_txn_id AS pg_txn_id_db
                            FROM payout_transactions
                            WHERE pg_partner = 'ORO' AND pg_txn_id = %s
                            LIMIT 1
                        """, (pg_txn_id,))
                        txn = cursor.fetchone()

                if not txn:
                    print(f"[ORO Payout CB] Transaction not found")
                    return jsonify({'status': 'error', 'message': 'Transaction not found'}), 404

                print(f"Found TX: {txn['txn_id']} | Current Status: {txn['status']}")

                if txn['status'] == 'SUCCESS' and mapped_status == 'SUCCESS':
                    return jsonify({'status': 'success', 'message': 'Callback already processed', 'txn_id': txn['txn_id']}), 200

                final_utr = utr if (utr and utr.upper() not in ('NA', 'NULL', 'NONE', '')) else txn.get('utr', '')
                final_pg_txn_id = pg_txn_id if pg_txn_id else txn.get('pg_txn_id_db', '')

                if mapped_status in ('SUCCESS', 'FAILED'):
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, final_utr, final_pg_txn_id, txn['txn_id']))
                else:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, pg_txn_id = %s, updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, final_utr, final_pg_txn_id, txn['txn_id']))

                conn.commit()

                # Wallet deduction on SUCCESS
                if mapped_status == 'SUCCESS' and txn['merchant_id']:
                    cursor.execute("""
                        SELECT COUNT(*) AS cnt FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'DEBIT'
                    """, (txn['txn_id'],))

                    already_debited = cursor.fetchone()['cnt'] > 0

                    if not already_debited:
                        from wallet_service import WalletService
                        wallet_svc = WalletService()
                        debit_result = wallet_svc.debit_merchant_wallet(
                            merchant_id=txn['merchant_id'],
                            amount=float(txn['txn_amount']) if txn['txn_amount'] else 0,
                            description=f"Payout completed (ORO) - Ref: {final_pg_txn_id}",
                            reference_id=txn['txn_id']
                        )
                        if debit_result['success']:
                            print(f"✅ Wallet debited")
                        else:
                            print(f"❌ Wallet deduction failed: {debit_result['message']}")

                # Forward callback to merchant
                callback_url = txn.get('callback_url')
                if not callback_url and txn['merchant_id']:
                    cursor.execute("""
                        SELECT payout_callback_url FROM merchant_callbacks
                        WHERE merchant_id = %s
                    """, (txn['merchant_id'],))
                    mc = cursor.fetchone()
                    if mc and mc.get('payout_callback_url'):
                        callback_url = mc['payout_callback_url'].strip()

                if callback_url:
                    if mapped_status == 'SUCCESS':
                        cursor.execute("""
                            SELECT COUNT(*) AS cnt FROM callback_logs
                            WHERE merchant_id = %s AND txn_id = %s AND response_code BETWEEN 200 AND 299
                              AND request_data LIKE %s
                        """, (txn['merchant_id'], txn['txn_id'], '%"status": "SUCCESS"%'))
                        if cursor.fetchone()['cnt'] > 0:
                            return jsonify({'status': 'success', 'message': 'Callback processed', 'txn_id': txn['txn_id']}), 200

                    merchant_payload = {
                        'txn_id': txn['txn_id'],
                        'reference_id': txn.get('reference_id', reference_id),
                        'status': mapped_status,
                        'utr': final_utr,
                        'pg_partner': 'ORO',
                        'pg_txn_id': final_pg_txn_id,
                        'amount': float(txn['net_amount']) if txn['net_amount'] else float(callback_data.get('amount', 0)),
                        'message': f'Payout {mapped_status.lower()}'
                    }

                    try:
                        cb_resp = req_lib.post(callback_url, json=merchant_payload, headers={'Content-Type': 'application/json'}, timeout=10)
                        cursor.execute("""
                            INSERT INTO callback_logs
                            (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        """, (txn['merchant_id'], txn['txn_id'], callback_url, json.dumps(merchant_payload), cb_resp.status_code, cb_resp.text[:1000]))
                        conn.commit()
                    except Exception as cb_err:
                        cursor.execute("""
                            INSERT INTO callback_logs
                            (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        """, (txn['merchant_id'], txn['txn_id'], callback_url, json.dumps(merchant_payload), 0, str(cb_err)[:1000]))
                        conn.commit()

                return jsonify({'status': 'success', 'message': 'Callback processed', 'txn_id': txn['txn_id']})

        finally:
            conn.close()

    except Exception as e:
        print(f"[ORO Payout CB] EXCEPTION: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
