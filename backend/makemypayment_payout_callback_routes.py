"""
MakeMyPayment Payout Callback Routes
Handles webhooks from MakeMyPayment
"""

from flask import Blueprint, request, jsonify
from database_pooled import get_db_connection
from utils import decrypt_aes
from config import Config
import json

makemypayment_payout_callback_bp = Blueprint('makemypayment_payout_callback', __name__, url_prefix='/api/callback/makemypayment')

@makemypayment_payout_callback_bp.route('/payout', methods=['POST'])
def makemypayment_payout_webhook():
    """
    Handle MakeMyPayment Payout Webhook
    """
    try:
        # Get signature from header
        signature = request.headers.get('x-signature')
        
        # In a strict implementation, we would verify the signature if it's a HMAC hash. 
        # The docs say: "x-signature: <your_webhook_secret>". We check if it matches.
        expected_signature = Config.MAKEMYPAYMENT_WEBHOOK_SECRET
        if expected_signature and signature != expected_signature:
            print(f"[MakeMyPayment Webhook] Invalid signature. Received: {signature}, Expected: {expected_signature}")
            return jsonify({'success': False, 'message': 'Invalid signature'}), 401

        # The payload is AES-256-CBC encrypted and base64 encoded
        encrypted_payload = request.data.decode('utf-8')
        if not encrypted_payload:
            return jsonify({'success': False, 'message': 'Empty payload'}), 400

        # Decrypt payload
        api_secret = Config.MAKEMYPAYMENT_API_SECRET
        iv = "0g7H#8X2mTqjvLwR"
        
        decrypted_str = decrypt_aes(encrypted_payload, api_secret, iv)
        if not decrypted_str:
            print("[MakeMyPayment Webhook] Failed to decrypt payload")
            return jsonify({'success': False, 'message': 'Decryption failed'}), 400
            
        payload = json.loads(decrypted_str)
        # Handle double-encoded JSON string
        if isinstance(payload, str):
            payload = json.loads(payload)
            
        print(f"[MakeMyPayment Webhook] Decrypted Payload: {json.dumps(payload)}")
        
        transaction_id = payload.get('transaction_id')
        merchant_reference_id = payload.get('merchant_reference_id')
        # Extract status safely (could be boolean, integer, or missing)
        raw_status = payload.get('status')
        if raw_status is None:
            # Maybe it's in a different field
            raw_status = payload.get('transaction_status', '')
            
        status = str(raw_status).lower()
        
        if not merchant_reference_id and not transaction_id:
            print("[MakeMyPayment Webhook] Missing both merchant_reference_id and transaction_id in payload")
            return jsonify({'success': False, 'message': 'Missing identifiers'}), 400
            
        # Map status
        if status in ['success', 'successful', 'processed', 'settled', 'true', '1']:
            mapped_status = 'SUCCESS'
        elif status in ['failed', 'failure', 'rejected', 'reversed', 'false', '0']:
            mapped_status = 'FAILED'
        else:
            # Fallback to checking remarks/message if status is weird
            remarks = str(payload.get('remarks', '')).lower()
            if 'settled' in remarks or 'success' in remarks:
                mapped_status = 'SUCCESS'
            elif 'failed' in remarks or 'rejected' in remarks:
                mapped_status = 'FAILED'
            else:
                mapped_status = 'INITIATED'
                
        # Also properly handle utr
        utr = str(payload.get('utr', ''))
        if utr.lower() in ['none', 'null', '']:
            utr = ''
            
        remarks = payload.get('remarks', '')
            
        # Update database
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
            
        try:
            with conn.cursor() as cursor:
                # Check current status
                if merchant_reference_id:
                    cursor.execute("""
                        SELECT txn_id, status, reference_id, merchant_id, callback_url, net_amount, utr 
                        FROM payout_transactions 
                        WHERE reference_id = %s
                    """, (merchant_reference_id,))
                else:
                    cursor.execute("""
                        SELECT txn_id, status, reference_id, merchant_id, callback_url, net_amount, utr 
                        FROM payout_transactions 
                        WHERE pg_txn_id = %s
                    """, (transaction_id,))
                
                txn = cursor.fetchone()
                if not txn:
                    identifier = merchant_reference_id if merchant_reference_id else transaction_id
                    print(f"[MakeMyPayment Webhook] Transaction not found for identifier: {identifier}")
                    return jsonify({'success': False, 'message': 'Transaction not found'}), 404
                    
                current_status = txn['status']
                current_utr = txn.get('utr')
                # Ensure merchant_reference_id is set for subsequent queries and logs
                merchant_reference_id = txn['reference_id']
                
                utr_updated = False
                
                # Only update if current status is not final
                if current_status not in ['SUCCESS', 'FAILED', 'REVERSED']:
                    if mapped_status in ['SUCCESS', 'FAILED']:
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = %s, pg_txn_id = %s, utr = %s, error_message = %s, 
                                completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (mapped_status, transaction_id, utr, remarks if mapped_status == 'FAILED' else None, merchant_reference_id))
                    else:
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                            WHERE reference_id = %s
                        """, (mapped_status, transaction_id, utr, merchant_reference_id))
                    
                    conn.commit()
                    print(f"[MakeMyPayment Webhook] Updated {merchant_reference_id} from {current_status} to {mapped_status}")
                    if utr and utr != current_utr:
                        utr_updated = True
                        
                    # Deduct wallet if status is SUCCESS
                    if mapped_status == 'SUCCESS' and txn['merchant_id']:
                        print("=" * 80)
                        print("WALLET DEDUCTION - SUCCESS STATUS (MAKEMYPAYMENT)")
                        print("=" * 80)
                        
                        cursor.execute("""
                            SELECT COUNT(*) as count FROM merchant_wallet_transactions
                            WHERE reference_id = %s AND txn_type = 'DEBIT'
                        """, (txn['txn_id'],))
                        
                        already_debited = cursor.fetchone()['count'] > 0
                        
                        if already_debited:
                            print(f"⚠ Wallet already debited for this transaction - skipping")
                        else:
                            cursor.execute("SELECT amount FROM payout_transactions WHERE txn_id = %s", (txn['txn_id'],))
                            txn_amount = cursor.fetchone()['amount']
                            
                            import wallet_service
                            wallet_svc = wallet_service.wallet_service
                            
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=txn['merchant_id'],
                                amount=float(txn_amount) if txn_amount else 0,
                                description=f"Payout completed (MAKEMYPAYMENT) - Ref: {merchant_reference_id}",
                                reference_id=txn['txn_id']
                            )
                            
                            if debit_result['success']:
                                print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            else:
                                print(f"❌ WALLET DEDUCTION FAILED: {debit_result['message']}")
                else:
                    print(f"[MakeMyPayment Webhook] Transaction {merchant_reference_id} already in final state: {current_status}")
                    # If it's SUCCESS and we received a new UTR, update the UTR
                    if current_status == 'SUCCESS' and mapped_status == 'SUCCESS' and utr and utr != current_utr:
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET utr = %s, updated_at = NOW()
                            WHERE reference_id = %s
                        """, (utr, merchant_reference_id))
                        conn.commit()
                        utr_updated = True
                        print(f"[MakeMyPayment Webhook] Updated UTR for {merchant_reference_id} to {utr}")
                        
                # MERCHANT CALLBACK LOGIC
                import requests
                
                # Forward callback to merchant if configured
                print("=" * 80)
                print("MERCHANT CALLBACK FORWARDING - MAKEMYPAYMENT PAYOUT")
                print("=" * 80)
                
                try:
                    callback_url = txn.get('callback_url')
                    
                    if callback_url:
                        callback_url = callback_url.strip()
                    
                    # If no callback URL in transaction, check merchant_callbacks table
                    if not callback_url and txn.get('merchant_id'):
                        cursor.execute("""
                            SELECT payout_callback_url FROM merchant_callbacks
                            WHERE merchant_id = %s
                        """, (txn['merchant_id'],))
                        
                        merchant_callback = cursor.fetchone()
                        if merchant_callback and merchant_callback.get('payout_callback_url'):
                            callback_url = merchant_callback['payout_callback_url'].strip()
                            
                    if callback_url:
                        # Prevent duplicate SUCCESS callback unless UTR was updated
                        if mapped_status == 'SUCCESS' and not utr_updated:
                            cursor.execute("""
                                SELECT COUNT(*) as count FROM callback_logs
                                WHERE merchant_id = %s AND txn_id = %s AND response_code BETWEEN 200 AND 299
                                AND request_data LIKE %s
                            """, (txn['merchant_id'], txn['txn_id'], '%"status": "SUCCESS"%'))
                            
                            if cursor.fetchone()['count'] > 0:
                                print("⚠ SUCCESS callback already sent to merchant - skipping duplicate")
                                conn.close()
                                return "OK", 200

                        merchant_callback_data = {
                            'txn_id': txn['txn_id'],
                            'reference_id': merchant_reference_id,
                            'status': mapped_status,
                            'utr': utr,
                            'pg_partner': 'MAKEMYPAYMENT',
                            'pg_txn_id': transaction_id,
                            'amount': float(txn['net_amount']) if txn.get('net_amount') else 0,
                            'message': f'Payout {mapped_status.lower()}'
                        }
                        
                        print(f"Forwarding payout callback to merchant: {callback_url}")
                        
                        try:
                            callback_response = requests.post(
                                callback_url,
                                json=merchant_callback_data,
                                headers={'Content-Type': 'application/json'},
                                timeout=10
                            )
                            
                            print(f"Merchant callback response: {callback_response.status_code}")
                            
                            cursor.execute("""
                                INSERT INTO callback_logs
                                (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                            """, (
                                txn['merchant_id'], txn['txn_id'], callback_url,
                                json.dumps(merchant_callback_data),
                                callback_response.status_code, callback_response.text[:1000]
                            ))
                            conn.commit()
                        except requests.exceptions.RequestException as e:
                            print(f"ERROR: Failed to send merchant payout callback: {e}")
                            cursor.execute("""
                                INSERT INTO callback_logs
                                (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                            """, (
                                txn['merchant_id'], txn['txn_id'], callback_url,
                                json.dumps(merchant_callback_data), 0, str(e)[:1000]
                            ))
                            conn.commit()
                    else:
                        print("No merchant payout callback URL configured")
                except Exception as e:
                    print(f"ERROR in merchant callback forwarding: {e}")
                    
        finally:
            conn.close()
            
        # Return 200 OK as expected by the gateway
        return "OK", 200

    except json.JSONDecodeError:
        print("[MakeMyPayment Webhook] Invalid JSON payload after decryption")
        return jsonify({'success': False, 'message': 'Invalid JSON format'}), 400
    except Exception as e:
        print(f"[MakeMyPayment Webhook] Error processing webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal Server Error'}), 500
