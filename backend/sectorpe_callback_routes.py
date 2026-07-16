"""
SectorPe Callback Routes
Handles payin callbacks from SectorPe payment gateway

Callback Format: GET request with URL query parameters
Parameters:
  - order_id   : Merchant Order ID
  - status     : success | failed | pending
  - amount     : Transaction Amount
  - mobile     : Customer Mobile Number
  - utr        : Bank UTR / RRN (optional)
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json

sectorpe_callback_bp = Blueprint('sectorpe_callback', __name__, url_prefix='/api/callback')


@sectorpe_callback_bp.route('/sectorpe/payin', methods=['GET'])
def sectorpe_payin_callback():
    """
    Callback endpoint for SectorPe payin status updates.
    SectorPe sends callback via GET method with URL query parameters.

    Expected GET parameters:
    - order_id : Merchant Order ID
    - status   : success | failed | pending
    - amount   : Transaction Amount
    - mobile   : Customer Mobile Number
    - utr      : Bank UTR / RRN (optional)
    """
    try:
        # Get callback data from SectorPe - sent as GET query parameters
        callback_data = request.args.to_dict()

        if not callback_data:
            print(f"[SectorPe Callback] ERROR: No data received")
            return jsonify({
                'success': False,
                'message': 'No data received in request'
            }), 400

        print("=" * 80)
        print("SectorPe Payin Callback Received")
        print("=" * 80)
        print(f"Data Source: GET")
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")

        # Extract data from callback
        order_id = callback_data.get('order_id', '')
        status = callback_data.get('status', '').lower()
        amount = callback_data.get('amount', '0')
        mobile = callback_data.get('mobile', '')
        utr = callback_data.get('utr', '')

        if not order_id:
            print("[SectorPe Callback] ERROR: No order_id in callback")
            return jsonify({
                'success': False,
                'message': 'Missing order_id'
            }), 400

        print(f"Order ID : {order_id}")
        print(f"Status   : {status}")
        print(f"Amount   : {amount}")
        print(f"Mobile   : {mobile}")
        print(f"UTR      : {utr}")

        # Map SectorPe status to our internal status
        if status == 'success':
            mapped_status = 'SUCCESS'
        elif status == 'failed':
            mapped_status = 'FAILED'
        else:
            mapped_status = 'INITIATED'  # pending or unknown

        print(f"Mapped Status: {mapped_status}")

        # Update database
        conn = get_db_connection()
        if not conn:
            print("[SectorPe Callback] ERROR: Database connection failed")
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        try:
            with conn.cursor() as cursor:
                # Find transaction by order_id
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, order_id, amount as txn_amount,
                           net_amount, charge_amount, callback_url
                    FROM payin_transactions
                    WHERE pg_partner IN ('PES', 'SECTORPE', 'SectorPe', 'Sectorpe', 'sectorpe')
                    AND order_id = %s
                    LIMIT 1
                """, (order_id,))

                txn = cursor.fetchone()

                if not txn:
                    print(f"[SectorPe Callback] ERROR: Transaction not found for order_id: {order_id}")

                    # Debug: show recent SectorPe transactions
                    cursor.execute("""
                        SELECT txn_id, order_id, pg_txn_id, status
                        FROM payin_transactions
                        WHERE pg_partner IN ('PES', 'SECTORPE', 'SectorPe', 'Sectorpe', 'sectorpe')
                        ORDER BY created_at DESC
                        LIMIT 5
                    """)
                    recent_txns = cursor.fetchall()

                    if recent_txns:
                        print(f"Recent SectorPe payin transactions:")
                        for t in recent_txns:
                            print(f"  - TXN: {t['txn_id']}, ORDER: {t['order_id']}, STATUS: {t['status']}")

                    return jsonify({
                        'success': False,
                        'message': f'Transaction not found for order_id: {order_id}'
                    }), 404

                print(f"Found Transaction: {txn['txn_id']}, Current Status: {txn['status']}")

                # Update transaction with callback data
                if mapped_status in ['SUCCESS', 'FAILED']:
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s,
                            bank_ref_no = %s,
                            payment_mode = 'UPI',
                            completed_at = NOW(),
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, txn['txn_id']))
                    print(f"✓ Updated with status={mapped_status}, utr={utr}, completed_at=NOW()")
                else:
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s,
                            bank_ref_no = %s,
                            payment_mode = 'UPI',
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, txn['txn_id']))
                    print(f"✓ Updated status to {mapped_status}")

                conn.commit()

                # Credit wallet if status is SUCCESS
                if mapped_status == 'SUCCESS' and txn['merchant_id']:
                    print("=" * 80)
                    print("WALLET CREDIT - SUCCESS STATUS")
                    print("=" * 80)

                    # Idempotency check
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                    """, (txn['txn_id'],))

                    already_credited = cursor.fetchone()['count'] > 0

                    if already_credited:
                        print(f"⚠ Wallet already credited for this transaction - skipping")
                    else:
                        try:
                            from wallet_service import wallet_service as wallet_svc

                            # Credit merchant unsettled wallet with net amount
                            credit_result = wallet_svc.credit_unsettled_wallet(
                                merchant_id=txn['merchant_id'],
                                amount=float(txn['net_amount']) if txn['net_amount'] else 0,
                                description=f"PayIn received (SectorPe) - {order_id}",
                                reference_id=txn['txn_id']
                            )

                            if credit_result.get('success'):
                                balance_before = credit_result.get('balance_before', 0)
                                balance_after = credit_result.get('balance_after', 0)
                                print(f"✅ MERCHANT WALLET CREDITED - Balance: ₹{balance_before:.2f} → ₹{balance_after:.2f}")
                            else:
                                print(f"❌ MERCHANT WALLET CREDIT FAILED: {credit_result.get('message', 'Unknown error')}")

                            # Credit admin unsettled wallet with charge amount
                            admin_credit_result = wallet_svc.credit_admin_unsettled_wallet(
                                admin_id='admin',
                                amount=float(txn['charge_amount']) if txn['charge_amount'] else 0,
                                description=f"PayIn charge (SectorPe) - {order_id}",
                                reference_id=txn['txn_id']
                            )

                            if admin_credit_result.get('success'):
                                print(f"✅ ADMIN WALLET CREDITED - Charge: ₹{txn['charge_amount']:.2f}")
                            else:
                                print(f"❌ ADMIN WALLET CREDIT FAILED: {admin_credit_result.get('message', 'Unknown error')}")

                        except Exception as wallet_error:
                            print(f"❌ WALLET CREDIT ERROR: {wallet_error}")
                            import traceback
                            traceback.print_exc()

                # Verify the update
                cursor.execute("""
                    SELECT status, bank_ref_no, completed_at
                    FROM payin_transactions
                    WHERE txn_id = %s
                """, (txn['txn_id'],))

                updated_txn = cursor.fetchone()
                print(f"Verification - Status: {updated_txn['status']}, UTR: {updated_txn['bank_ref_no']}, Completed: {updated_txn['completed_at']}")

                print("=" * 80)
                print("SectorPe Payin Callback processed successfully")
                print("=" * 80)

                # Forward callback to merchant if configured
                print("=" * 80)
                print("MERCHANT CALLBACK FORWARDING - PAYIN")
                print("=" * 80)
                print(f"Transaction merchant_id: {txn.get('merchant_id')}")
                print(f"Transaction callback_url field: {txn.get('callback_url')}")
                print(f"Mapped status: {mapped_status}")

                try:
                    callback_url = None

                    # Step 1: Check transaction callback_url (PRIMARY)
                    if txn.get('callback_url'):
                        callback_url = txn['callback_url'].strip()
                        # Skip internal SectorPe callback URL
                        if callback_url and 'api.craftpay.in/api/callback/sectorpe' in callback_url:
                            print(f"⚠ Step 1: Skipping internal callback URL: {callback_url}")
                            callback_url = None
                        elif callback_url:
                            print(f"✅ Step 1: Found callback_url in transaction: {callback_url}")
                        else:
                            print(f"❌ Step 1: Empty callback_url in transaction")
                            callback_url = None
                    else:
                        print(f"❌ Step 1: No callback_url in transaction")

                    # Step 2: If no valid URL, check merchant_callbacks table
                    if not callback_url and txn['merchant_id']:
                        print(f"Step 2: Checking merchant_callbacks table for merchant: {txn['merchant_id']}")
                        cursor.execute("""
                            SELECT payin_callback_url FROM merchant_callbacks
                            WHERE merchant_id = %s
                        """, (txn['merchant_id'],))

                        merchant_callback = cursor.fetchone()
                        if merchant_callback and merchant_callback.get('payin_callback_url'):
                            callback_url = merchant_callback['payin_callback_url'].strip()
                            if not callback_url:
                                callback_url = None
                            else:
                                print(f"✅ Step 2: Found payin_callback_url in merchant_callbacks: {callback_url}")
                        else:
                            print(f"❌ Step 2: No payin_callback_url in merchant_callbacks")

                    print(f"\n🎯 Final callback_url to use: {callback_url if callback_url else 'NONE'}")

                    if callback_url:
                        print(f"✅ Callback URL found, proceeding with forwarding...")

                        # DUPLICATE PREVENTION: Check if SUCCESS callback already sent
                        if mapped_status == 'SUCCESS':
                            print(f"Checking for duplicate SUCCESS callbacks...")
                            cursor.execute("""
                                SELECT COUNT(*) as count FROM callback_logs
                                WHERE merchant_id = %s
                                AND txn_id = %s
                                AND response_code BETWEEN 200 AND 299
                                AND request_data LIKE %s
                            """, (txn['merchant_id'], txn['txn_id'], '%"status": "SUCCESS"%'))

                            success_callback_sent = cursor.fetchone()['count'] > 0
                            print(f"Duplicate check result: {success_callback_sent}")

                            if success_callback_sent:
                                print(f"⚠ SUCCESS callback already sent to merchant - skipping duplicate")
                                print("=" * 80)
                                return "Callback processed successfully", 200

                        import requests as req

                        # Prepare callback payload for merchant
                        merchant_callback_data = {
                            'txn_id': txn['txn_id'],
                            'order_id': order_id,
                            'status': mapped_status,
                            'utr': utr,
                            'pg_partner': 'PES',
                            'amount': float(txn['txn_amount']) if txn['txn_amount'] else 0,
                            'net_amount': float(txn['net_amount']) if txn['net_amount'] else 0,
                            'charge_amount': float(txn['charge_amount']) if txn['charge_amount'] else 0
                        }

                        print(f"📤 Forwarding payin callback to merchant: {callback_url}")
                        print(f"📦 Callback data: {json.dumps(merchant_callback_data, indent=2)}")

                        try:
                            print(f"🔄 Sending POST request...")
                            callback_response = req.post(
                                callback_url,
                                json=merchant_callback_data,
                                headers={'Content-Type': 'application/json'},
                                timeout=10
                            )

                            print(f"✅ Merchant callback response: {callback_response.status_code}")
                            print(f"📄 Merchant callback response body: {callback_response.text[:200]}")

                            # Log callback attempt
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
                            print(f"✅ Merchant payin callback sent successfully and logged")

                        except req.exceptions.RequestException as e:
                            print(f"❌ ERROR: Failed to send merchant payin callback: {e}")

                            # Log failed callback attempt
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
                            print(f"📝 Failed callback attempt logged")
                    else:
                        print("❌ No merchant payin callback URL configured")
                        print("   - Transaction callback_url: NOT SET or EMPTY")
                        print("   - Merchant payin_callback_url: NOT SET or EMPTY")

                except Exception as e:
                    print(f"❌ ERROR in merchant callback forwarding: {e}")
                    import traceback
                    traceback.print_exc()

                return "Callback processed successfully", 200

        finally:
            conn.close()

    except Exception as e:
        print(f"[SectorPe Callback] ERROR: {e}")
        import traceback
        traceback.print_exc()

        error_details = {
            'success': False,
            'message': str(e),
            'error_type': type(e).__name__,
            'traceback': traceback.format_exc()
        }

        return jsonify(error_details), 500
