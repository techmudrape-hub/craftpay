"""
Kortyapay Payout Callback Routes
Handles webhook/callback notifications from Kortyapay for payout transactions
"""

from flask import Blueprint, request, jsonify
import json
from datetime import datetime
from database import get_db_connection
from wallet_service import WalletService

kortyapay_payout_callback_bp = Blueprint('kortyapay_payout_callback', __name__, url_prefix='/api/callback')


@kortyapay_payout_callback_bp.route('/kortyapay/payout', methods=['GET', 'POST'])
def kortyapay_payout_callback():
    """
    Handle payout status callback/webhook from Kortyapay
    URL: /api/callback/kortyapay/payout
    """
    try:
        callback_data = {}
        data_source = "UNKNOWN"

        if request.is_json:
            callback_data = request.get_json(silent=True) or {}
            data_source = "JSON"
        elif request.form:
            callback_data = request.form.to_dict()
            data_source = "FORM"
        elif request.args:
            callback_data = request.args.to_dict()
            data_source = "QUERY"

        if not callback_data:
            raw_data = request.get_data(as_text=True)
            if raw_data:
                try:
                    callback_data = json.loads(raw_data)
                    data_source = "RAW_JSON"
                except Exception:
                    pass

        print("=" * 80)
        print("Kortyapay Payout Callback Received")
        print("=" * 80)
        print(f"Method: {request.method}")
        print(f"Data Source: {data_source}")
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")

        # Extract fields
        # Could be under 'data' dict or top-level
        # Extract fields from Kortyapay callback:
        # e.g. {"status": "SUCCESS", "order_id": "DP...", "txn_id": "TGA...", "amount": "100.00", "rrn": "C118...", "message": "processed"}
        data_obj = callback_data.get('data', {}) if isinstance(callback_data.get('data'), dict) else callback_data
        
        order_id_param = str(data_obj.get('order_id') or callback_data.get('order_id') or '').strip()
        pg_txn_id_param = str(data_obj.get('txn_id') or callback_data.get('txn_id') or '').strip()
        status_raw = str(data_obj.get('status', '') or callback_data.get('status', '')).upper()
        rrn = str(data_obj.get('rrn') or data_obj.get('utr') or callback_data.get('rrn') or callback_data.get('utr') or '').strip()

        lookup_1 = order_id_param or pg_txn_id_param
        lookup_2 = pg_txn_id_param or order_id_param

        if not lookup_1:
            print("[Kortyapay Payout Callback] ERROR: Missing order_id and txn_id in callback")
            return jsonify({
                'success': False,
                'message': 'Missing order_id and txn_id'
            }), 400

        mapped_status = 'INITIATED'
        if status_raw in ['SUCCESS', 'SUCCESSFUL', 'COMPLETED', 'TRUE', 'PROCESSED', 'PAID']:
            mapped_status = 'SUCCESS'
        elif status_raw in ['FAILED', 'FAILURE', 'REJECTED', 'FALSE']:
            mapped_status = 'FAILED'

        print(f"Merchant Order ID: {order_id_param}, PG Txn ID: {pg_txn_id_param}, Raw Status: {status_raw}, Mapped: {mapped_status}, RRN: {rrn}")

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, reference_id, amount as txn_amount, 
                           callback_url, net_amount, order_id, pg_partner
                    FROM payout_transactions
                    WHERE (reference_id = %s OR order_id = %s OR pg_txn_id = %s OR
                           reference_id = %s OR order_id = %s OR pg_txn_id = %s)
                    AND pg_partner = 'KORTYAPAY'
                    LIMIT 1
                """, (lookup_1, lookup_1, lookup_1, lookup_2, lookup_2, lookup_2))

                txn = cursor.fetchone()
                if not txn:
                    print(f"[Kortyapay Payout Callback] ERROR: Transaction not found for id: {lookup_1}")
                    return jsonify({
                        'success': False,
                        'message': 'Transaction not found'
                    }), 404

                print(f"Found DB Transaction: {txn['txn_id']}, Current DB Status: {txn['status']}")

                if txn['status'] == mapped_status and mapped_status in ['SUCCESS', 'FAILED']:
                    print("Duplicate callback for already finalized transaction")
                    return jsonify({
                        'success': True,
                        'message': 'Callback already processed',
                        'txn_id': txn['txn_id'],
                        'status': mapped_status
                    }), 200

                if mapped_status in ['SUCCESS', 'FAILED']:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s,
                            utr = COALESCE(NULLIF(%s, ''), utr),
                            pg_txn_id = COALESCE(NULLIF(%s, ''), pg_txn_id),
                            completed_at = NOW(),
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, rrn, pg_txn_id_param, txn['txn_id']))
                else:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s,
                            utr = COALESCE(NULLIF(%s, ''), utr),
                            pg_txn_id = COALESCE(NULLIF(%s, ''), pg_txn_id),
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, rrn, pg_txn_id_param, txn['txn_id']))

                conn.commit()

                # Deduct wallet if status changed to SUCCESS and merchant_id exists
                if mapped_status == 'SUCCESS' and txn['merchant_id']:
                    print("WALLET DEDUCTION - SUCCESS STATUS (KORTYAPAY)")
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'DEBIT'
                    """, (txn['txn_id'],))

                    already_debited = cursor.fetchone()['count'] > 0
                    if not already_debited:
                        wallet_svc = WalletService()
                        debit_result = wallet_svc.debit_merchant_wallet(
                            merchant_id=txn['merchant_id'],
                            amount=float(txn['txn_amount']) if txn['txn_amount'] else 0,
                            description=f"Payout completed (Kortyapay) - Ref: {txn['reference_id'] or txn['order_id'] or order_id_param}",
                            reference_id=txn['txn_id']
                        )
                        if debit_result['success']:
                            print(f"✅ WALLET DEBITED: {debit_result['balance_before']} -> {debit_result['balance_after']}")
                        else:
                            print(f"❌ WALLET DEBIT FAILED: {debit_result['message']}")

                # Forward callback to merchant if configured
                print("=" * 80)
                print("MERCHANT CALLBACK FORWARDING - PAYOUT (KORTYAPAY)")
                print("=" * 80)
                print(f"Transaction merchant_id: {txn.get('merchant_id')}")
                print(f"Transaction callback_url field: {txn.get('callback_url')}")

                try:
                    callback_url = None
                    if txn.get('callback_url'):
                        callback_url = txn['callback_url'].strip()
                        if not callback_url:
                            callback_url = None

                    print(f"Step 1: Transaction callback_url from DB: {callback_url if callback_url else 'NOT SET'}")

                    if not callback_url and txn['merchant_id']:
                        print(f"Step 2: Checking merchant_callbacks table for merchant: {txn['merchant_id']}")
                        cursor.execute("""
                            SELECT payout_callback_url FROM merchant_callbacks
                            WHERE merchant_id = %s
                        """, (txn['merchant_id'],))
                        merchant_callback = cursor.fetchone()
                        if merchant_callback and merchant_callback.get('payout_callback_url'):
                            callback_url = merchant_callback['payout_callback_url'].strip()
                            if not callback_url:
                                callback_url = None
                        print(f"Step 2: Merchant payout_callback_url: {callback_url if callback_url else 'NOT SET'}")

                    if callback_url:
                        # DUPLICATE PREVENTION: Check if we already sent a SUCCESS callback for this transaction
                        if mapped_status == 'SUCCESS':
                            cursor.execute("""
                                SELECT COUNT(*) as count FROM callback_logs
                                WHERE merchant_id = %s
                                AND txn_id = %s
                                AND response_code BETWEEN 200 AND 299
                                AND request_data LIKE %s
                            """, (txn['merchant_id'], txn['txn_id'], '%"status": "SUCCESS"%'))
                            
                            success_callback_sent = cursor.fetchone()['count'] > 0
                            if success_callback_sent:
                                print(f"⚠ SUCCESS callback already sent to merchant - skipping duplicate")
                                return jsonify({
                                    'success': True,
                                    'message': 'Callback processed (duplicate prevented)',
                                    'txn_id': txn['txn_id'],
                                    'status': mapped_status
                                }), 200

                        import requests

                        merchant_callback_data = {
                            'txn_id': txn['txn_id'],
                            'reference_id': txn['reference_id'] or txn['order_id'] or order_id_param,
                            'status': mapped_status,
                            'utr': rrn,
                            'pg_partner': txn['pg_partner'],  # 'KORTYAPAY'
                            'pg_txn_id': pg_txn_id_param or txn['reference_id'] or txn['order_id'] or order_id_param,
                            'amount': float(txn['net_amount']) if txn.get('net_amount') else (float(txn['txn_amount']) if txn.get('txn_amount') else 0),
                            'message': f'Payout {mapped_status.lower()}'
                        }

                        print(f"Forwarding payout callback to merchant: {callback_url}")
                        print(f"Callback data: {json.dumps(merchant_callback_data, indent=2)}")

                        try:
                            callback_response = requests.post(
                                callback_url,
                                json=merchant_callback_data,
                                headers={'Content-Type': 'application/json'},
                                timeout=10
                            )
                            print(f"Merchant callback response: {callback_response.status_code}")
                            print(f"Merchant callback response body: {callback_response.text[:200]}")

                            cursor.execute("""
                                INSERT INTO callback_logs
                                (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                            """, (
                                txn['merchant_id'],
                                txn['txn_id'],
                                callback_url,
                                json.dumps(merchant_callback_data),
                                callback_response.status_code,
                                callback_response.text[:1000]
                            ))
                            conn.commit()
                            print(f"✓ Merchant payout callback sent successfully and logged")
                        except requests.exceptions.RequestException as e:
                            print(f"ERROR: Failed to send merchant payout callback: {e}")
                            cursor.execute("""
                                INSERT INTO callback_logs
                                (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                            """, (
                                txn['merchant_id'],
                                txn['txn_id'],
                                callback_url,
                                json.dumps(merchant_callback_data),
                                0,
                                str(e)[:1000]
                            ))
                            conn.commit()
                    else:
                        print("No merchant payout callback URL configured")
                except Exception as e:
                    print(f"ERROR in merchant callback forwarding: {e}")
                    import traceback
                    traceback.print_exc()

                return jsonify({
                    'success': True,
                    'message': 'Callback processed successfully',
                    'txn_id': txn['txn_id'],
                    'status': mapped_status
                }), 200

        finally:
            conn.close()

    except Exception as e:
        print(f"[Kortyapay Payout Callback] Exception: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'Internal server error processing callback'
        }), 500
