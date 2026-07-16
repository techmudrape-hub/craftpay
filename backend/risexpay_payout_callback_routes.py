"""
Risexpay Payout Callback Routes
Handles payout status webhook callbacks from Risexpay.

Risexpay sends a plain JSON POST (no signature on callbacks):
{
    "TXN_amount": "5000.00",
    "TXN_date":   "2025-01-10 14:35:20",
    "Txn_ID":     "TXN123456789",
    "TXN_Status": "SUCCESS",
    "UTR":        "HDFC12345XYZ"
}

We:
  1. Accept the raw JSON callback.
  2. Resolve the transaction in payout_transactions by reference_id / order_id / pg_txn_id.
  3. Update status + UTR.
  4. Deduct merchant wallet on SUCCESS (idempotent).
  5. Forward to merchant in the same format used by MaxPe payout callbacks.
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json
import requests as req_lib

risexpay_payout_callback_bp = Blueprint(
    'risexpay_payout_callback', __name__, url_prefix='/api/callback'
)


@risexpay_payout_callback_bp.route('/risexpay/payout', methods=['POST'])
def risexpay_payout_callback():
    """
    Webhook endpoint for Risexpay payout status updates.

    Callback URL to give Risexpay:
        https://api.craftpay.in/api/callback/risexpay/payout

    Expected payload (plain JSON, no signature):
    {
        "TXN_amount": "5000.00",
        "TXN_date":   "2025-01-10 14:35:20",
        "Txn_ID":     "TXN123456789",
        "TXN_Status": "SUCCESS",
        "UTR":        "HDFC12345XYZ"
    }
    """
    try:
        # ---------------------------------------------------------- #
        # 1. Parse callback payload
        # ---------------------------------------------------------- #
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
            raw_data = request.get_data(as_text=True)
            print(f"[Risexpay Payout CB] ERROR: No data received")
            print(f"Content-Type: {request.content_type}")
            print(f"Raw data: {raw_data[:500] if raw_data else 'EMPTY'}")
            return jsonify({'status': 'error', 'message': 'No data received'}), 400

        print("=" * 80)
        print("Risexpay Payout Callback Received")
        print("=" * 80)
        print(f"Data Source   : {data_source}")
        print(f"Content-Type  : {request.content_type}")
        print(f"Callback Data : {json.dumps(callback_data, indent=2)}")

        # ---------------------------------------------------------- #
        # 2. Extract fields from Risexpay callback format
        #    { "TXN_amount", "TXN_date", "Txn_ID", "TXN_Status", "UTR" }
        # ---------------------------------------------------------- #
        # Txn_ID is the gateway's transaction ID (may match our ref_no / pg_txn_id)
        pg_txn_id = (
            callback_data.get('Txn_ID') or
            callback_data.get('txn_id') or
            callback_data.get('TXN_ID') or
            ''
        ).strip()

        raw_status = (
            callback_data.get('TXN_Status') or
            callback_data.get('status') or
            callback_data.get('txn_status') or
            ''
        ).upper().strip()

        utr = (
            callback_data.get('UTR') or
            callback_data.get('utr') or
            ''
        ).strip()

        amount_str = (
            callback_data.get('TXN_amount') or
            callback_data.get('amount') or
            '0'
        )

        try:
            callback_amount = float(str(amount_str).replace(',', ''))
        except Exception:
            callback_amount = 0.0

        if not pg_txn_id:
            print(f"[Risexpay Payout CB] ERROR: Missing Txn_ID in callback")
            return jsonify({'status': 'error', 'message': 'Missing Txn_ID'}), 400

        # Map status
        if raw_status in ('SUCCESS', 'TXN', 'COMPLETED'):
            mapped_status = 'SUCCESS'
        elif raw_status in ('FAILED', 'ERR', 'FAILURE'):
            mapped_status = 'FAILED'
        elif raw_status in ('PENDING', 'INPROCESS', 'PROCESSING'):
            mapped_status = 'INPROCESS'
        else:
            mapped_status = 'INITIATED'

        print(f"Txn_ID         : {pg_txn_id}")
        print(f"TXN_Status     : {raw_status} → {mapped_status}")
        print(f"UTR            : {utr}")
        print(f"Amount         : ₹{callback_amount}")

        # ---------------------------------------------------------- #
        # 3. Look up transaction in DB
        # ---------------------------------------------------------- #
        conn = get_db_connection()
        if not conn:
            print("[Risexpay Payout CB] ERROR: DB connection failed")
            return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500

        try:
            with conn.cursor() as cursor:
                # Try reference_id first (our ref sent as ref_no)
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, reference_id,
                           amount AS txn_amount, callback_url, net_amount,
                           order_id, pg_partner, pg_txn_id AS pg_txn_id_db
                    FROM payout_transactions
                    WHERE pg_partner = 'RISEXPAY'
                    AND (reference_id = %s OR pg_txn_id = %s OR order_id = %s)
                    LIMIT 1
                """, (pg_txn_id, pg_txn_id, pg_txn_id))

                txn = cursor.fetchone()

                # If not found, try a broader search stripping prefix
                if not txn:
                    print(f"[Risexpay Payout CB] Not found by reference_id/pg_txn_id/order_id: {pg_txn_id}")
                    # Show recent RISEXPAY payout txns for debugging
                    cursor.execute("""
                        SELECT txn_id, reference_id, order_id, pg_txn_id, status
                        FROM payout_transactions
                        WHERE pg_partner = 'RISEXPAY'
                        ORDER BY created_at DESC
                        LIMIT 5
                    """)
                    recent = cursor.fetchall()
                    if recent:
                        print("Recent RISEXPAY payout transactions:")
                        for t in recent:
                            print(f"  TXN: {t['txn_id']} | REF: {t['reference_id']} | "
                                  f"ORDER: {t['order_id']} | PG_TXN: {t['pg_txn_id']} | "
                                  f"STATUS: {t['status']}")

                    return jsonify({
                        'status': 'error',
                        'message': f'Transaction not found for Txn_ID: {pg_txn_id}'
                    }), 404

                print(f"Found TX: {txn['txn_id']} | Current: {txn['status']}")

                # -------------------------------------------------- #
                # 4. Duplicate SUCCESS guard
                # -------------------------------------------------- #
                if txn['status'] == 'SUCCESS' and mapped_status == 'SUCCESS':
                    print("⚠ Duplicate SUCCESS callback — already processed")
                    return jsonify({
                        'status': 'success',
                        'message': 'Callback already processed',
                        'txn_id': txn['txn_id']
                    }), 200

                # -------------------------------------------------- #
                # 5. Handle UTR / pg_txn_id properly
                #    - If Risexpay sends a real UTR use it
                #    - If UTR is empty/NA, fall back to Txn_ID from callback
                # -------------------------------------------------- #
                final_utr = utr if (utr and utr.upper() not in ('NA', 'NULL', 'NONE', '')) else pg_txn_id

                # -------------------------------------------------- #
                # 6. Update payout_transactions
                # -------------------------------------------------- #
                if mapped_status in ('SUCCESS', 'FAILED'):
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status      = %s,
                            utr         = %s,
                            pg_txn_id   = %s,
                            completed_at = NOW(),
                            updated_at  = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, final_utr, pg_txn_id, txn['txn_id']))
                    print(f"✓ Updated status={mapped_status}, utr={final_utr}, pg_txn_id={pg_txn_id}")
                else:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status     = %s,
                            utr        = %s,
                            pg_txn_id  = %s,
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, final_utr, pg_txn_id, txn['txn_id']))
                    print(f"✓ Updated status={mapped_status}")

                conn.commit()

                # -------------------------------------------------- #
                # 7. Wallet deduction on SUCCESS (idempotent)
                # -------------------------------------------------- #
                if mapped_status == 'SUCCESS' and txn['merchant_id']:
                    print("=" * 60)
                    print("WALLET DEDUCTION — SUCCESS")
                    print("=" * 60)

                    cursor.execute("""
                        SELECT COUNT(*) AS cnt FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'DEBIT'
                    """, (txn['txn_id'],))

                    already_debited = cursor.fetchone()['cnt'] > 0

                    if already_debited:
                        print("⚠ Wallet already debited — skipping")
                    else:
                        from wallet_service import WalletService
                        wallet_svc = WalletService()

                        debit_result = wallet_svc.debit_merchant_wallet(
                            merchant_id=txn['merchant_id'],
                            amount=float(txn['txn_amount']) if txn['txn_amount'] else 0,
                            description=f"Payout completed (RISEXPAY) - Ref: {pg_txn_id}",
                            reference_id=txn['txn_id']
                        )

                        if debit_result['success']:
                            print(f"✅ Wallet debited — "
                                  f"₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                        else:
                            print(f"❌ Wallet deduction failed: {debit_result['message']}")

                # -------------------------------------------------- #
                # 8. Verify update
                # -------------------------------------------------- #
                cursor.execute("""
                    SELECT status, utr, completed_at
                    FROM payout_transactions
                    WHERE txn_id = %s
                """, (txn['txn_id'],))
                updated = cursor.fetchone()
                print(f"Verification — Status: {updated['status']}, UTR: {updated['utr']}, "
                      f"Completed: {updated['completed_at']}")

                print("=" * 80)
                print("Risexpay Payout Callback processed successfully")
                print("=" * 80)

                # -------------------------------------------------- #
                # 9. Forward callback to merchant (MaxPe format)
                # -------------------------------------------------- #
                print("=" * 60)
                print("MERCHANT CALLBACK FORWARDING — PAYOUT")
                print("=" * 60)

                try:
                    callback_url = None

                    # Check transaction-level callback_url first
                    if txn.get('callback_url'):
                        url_val = txn['callback_url'].strip()
                        if url_val:
                            callback_url = url_val

                    print(f"Step 1: TX callback_url: {callback_url or 'NOT SET'}")

                    # Fallback: merchant_callbacks table
                    if not callback_url and txn['merchant_id']:
                        cursor.execute("""
                            SELECT payout_callback_url FROM merchant_callbacks
                            WHERE merchant_id = %s
                        """, (txn['merchant_id'],))
                        mc = cursor.fetchone()
                        if mc and mc.get('payout_callback_url'):
                            url_val = mc['payout_callback_url'].strip()
                            if url_val:
                                callback_url = url_val

                        print(f"Step 2: Merchant payout_callback_url: {callback_url or 'NOT SET'}")

                    if callback_url:
                        # Duplicate SUCCESS guard
                        if mapped_status == 'SUCCESS':
                            cursor.execute("""
                                SELECT COUNT(*) AS cnt FROM callback_logs
                                WHERE merchant_id = %s
                                  AND txn_id = %s
                                  AND response_code BETWEEN 200 AND 299
                                  AND request_data LIKE %s
                            """, (txn['merchant_id'], txn['txn_id'], '%"status": "SUCCESS"%'))

                            already_sent = cursor.fetchone()['cnt'] > 0

                            if already_sent:
                                print("⚠ SUCCESS callback already sent — skipping duplicate")
                                return jsonify({
                                    'status': 'success',
                                    'message': 'Callback processed (duplicate prevented)',
                                    'txn_id': txn['txn_id']
                                }), 200

                        # Build merchant payload in MaxPe payout format
                        merchant_payload = {
                            'txn_id': txn['txn_id'],
                            'reference_id': txn.get('reference_id', pg_txn_id),
                            'status': mapped_status,
                            'utr': final_utr,
                            'pg_partner': 'RISEXPAY',
                            'pg_txn_id': pg_txn_id,
                            'amount': float(txn['net_amount']) if txn['net_amount'] else callback_amount,
                            'message': f'Payout {mapped_status.lower()}'
                        }

                        print(f"📤 Forwarding to merchant: {callback_url}")
                        print(f"📦 Payload: {json.dumps(merchant_payload, indent=2)}")

                        try:
                            cb_resp = req_lib.post(
                                callback_url,
                                json=merchant_payload,
                                headers={'Content-Type': 'application/json'},
                                timeout=10
                            )
                            print(f"✅ Merchant response: HTTP {cb_resp.status_code}")
                            print(f"   Body: {cb_resp.text[:200]}")

                            cursor.execute("""
                                INSERT INTO callback_logs
                                (merchant_id, txn_id, callback_url, request_data,
                                 response_code, response_data, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                            """, (
                                txn['merchant_id'],
                                txn['txn_id'],
                                callback_url,
                                json.dumps(merchant_payload),
                                cb_resp.status_code,
                                cb_resp.text[:1000]
                            ))
                            conn.commit()
                            print("✓ Merchant payout callback sent and logged")

                        except req_lib.exceptions.RequestException as cb_err:
                            print(f"❌ Failed to send merchant callback: {cb_err}")
                            cursor.execute("""
                                INSERT INTO callback_logs
                                (merchant_id, txn_id, callback_url, request_data,
                                 response_code, response_data, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                            """, (
                                txn['merchant_id'],
                                txn['txn_id'],
                                callback_url,
                                json.dumps(merchant_payload),
                                0,
                                str(cb_err)[:1000]
                            ))
                            conn.commit()
                    else:
                        print("ℹ No merchant payout callback URL configured")

                except Exception as fwd_err:
                    print(f"❌ Merchant callback forwarding error: {fwd_err}")
                    import traceback; traceback.print_exc()

                return jsonify({
                    'status': 'success',
                    'message': 'Callback processed successfully',
                    'txn_id': txn['txn_id'],
                    'mapped_status': mapped_status
                }), 200

        finally:
            conn.close()

    except Exception as e:
        print(f"[Risexpay Payout CB] EXCEPTION: {e}")
        import traceback; traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e),
            'error_type': type(e).__name__
        }), 500
