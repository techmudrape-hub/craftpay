"""
Star23456 Callback Routes
Handles payin callbacks from Star23456 payment gateway
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json
import threading
import requests

star23456_callback_bp = Blueprint('star23456_callback', __name__, url_prefix='/api/callback')

@star23456_callback_bp.route('/star23456/payin', methods=['POST'])
def star23456_payin_callback():
    try:
        callback_data = request.get_json(force=True, silent=True)
        if not callback_data:
            return jsonify({'success': False, 'message': 'No data received'}), 400
            
        print("=" * 80)
        print("Star23456 Payin Callback Received")
        print(f"Data: {json.dumps(callback_data)}")
        print("=" * 80)
        
        merchant_order_id = callback_data.get('collect_ref')
        status = callback_data.get('status', '').upper()
        utr = callback_data.get('bankref') or callback_data.get('upi_transaction_id')
        
        if not merchant_order_id:
            return jsonify({'success': False, 'message': 'Missing collect_ref'}), 400
            
        mapped_status = 'INITIATED'
        if status in ['SUCCESS', 'COMPLETED']:
            mapped_status = 'SUCCESS'
        elif status in ['FAILED']:
            mapped_status = 'FAILED'
            
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
            
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, order_id, amount as txn_amount, 
                           net_amount, charge_amount, callback_url, bank_ref_no
                    FROM payin_transactions
                    WHERE pg_partner = 'STAR23456'
                    AND order_id = %s
                    LIMIT 1
                """, (merchant_order_id,))
                
                txn = cursor.fetchone()
                if not txn:
                    return jsonify({'success': False, 'message': 'Transaction not found'}), 404
                    
                db_status = txn['status']
                
                # Prevent downgrading if already SUCCESS
                if db_status == 'SUCCESS':
                    mapped_status = 'SUCCESS'
                    if not utr and txn.get('bank_ref_no'):
                        utr = txn['bank_ref_no']
                elif db_status == 'FAILED' and mapped_status != 'SUCCESS':
                    mapped_status = 'FAILED'
                    
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
                else:
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s, 
                            bank_ref_no = %s,
                            payment_mode = 'UPI',
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, utr, txn['txn_id']))
                
                conn.commit()
                
                # Credit wallet if SUCCESS
                if mapped_status == 'SUCCESS' and txn['merchant_id']:
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                    """, (txn['txn_id'],))
                    
                    already_credited = cursor.fetchone()['count'] > 0
                    
                    if already_credited:
                        print(f"⚠ Wallet already credited for this transaction - skipping")
                    else:
                        try:
                            # Import wallet service
                            from wallet_service import wallet_service as wallet_svc
                            
                            # Credit merchant unsettled wallet with net amount
                            credit_result = wallet_svc.credit_unsettled_wallet(
                                merchant_id=txn['merchant_id'],
                                amount=float(txn['net_amount']) if txn['net_amount'] else 0,
                                description=f"PayIn received (Star23456) - {merchant_order_id}",
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
                                description=f"PayIn charge (Star23456) - {merchant_order_id}",
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
                            # Continue processing - don't let wallet errors stop callback forwarding
                        
                # Forward callback to merchant if configured
                print("=" * 80)
                print("MERCHANT CALLBACK FORWARDING - PAYIN")
                print("=" * 80)
                
                try:
                    # Get callback URL from transaction or merchant_callbacks table
                    callback_url = None
                    
                    if txn.get('callback_url'):
                        callback_url = txn['callback_url'].strip()
                        if not callback_url:
                            callback_url = None
                    
                    if not callback_url and txn.get('merchant_id'):
                        cursor.execute("""
                            SELECT payin_callback_url FROM merchant_callbacks
                            WHERE merchant_id = %s
                        """, (txn['merchant_id'],))
                        
                        merchant_callback = cursor.fetchone()
                        if merchant_callback and merchant_callback.get('payin_callback_url'):
                            callback_url = merchant_callback['payin_callback_url'].strip()
                            if not callback_url:
                                callback_url = None
                    
                    if callback_url:
                        # Extract UTR from multiple possible gateway keys if it was None
                        if not utr:
                            utr = callback_data.get('ref_num') or callback_data.get('transaction_id') or txn.get('bank_ref_no')
                            
                        # DUPLICATE PREVENTION: Check if we already sent a SUCCESS callback for this transaction
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
                            
                            if success_callback_sent:
                                print(f"⚠ SUCCESS callback already sent to merchant - skipping duplicate return, forcing forward for test")
                                # Removed early return to allow forced forwards during testing
                        
                        from callback_forwarder import forward_callback_to_merchant
                        
                        # Forward callback to merchant
                        print(f"Forwarding {mapped_status} callback to merchant URL: {callback_url}")
                        
                        forward_payload = {
                            "status": mapped_status,
                            "message": "Payment Successful" if mapped_status == "SUCCESS" else "Payment Failed",
                            "txn_id": txn['txn_id'],
                            "order_id": merchant_order_id,
                            "amount": str(txn['txn_amount']) if txn['txn_amount'] else "0",
                            "utr": utr,
                            "pg_order_id": callback_data.get('transaction_id', '')
                        }
                        
                        forward_callback_to_merchant(
                            merchant_id=txn['merchant_id'],
                            callback_url=callback_url,
                            payload=forward_payload,
                            txn_id=txn['txn_id'],
                            provider='STAR23456'
                        )
                    else:
                        print("❌ No merchant payin callback URL configured")
                        
                except Exception as e:
                    print(f"❌ ERROR preparing merchant callback: {e}")
                    import traceback
                    traceback.print_exc()

                # Forward callback to checkout page
                print("=" * 80)
                print("CHECKOUT PAGE CALLBACK FORWARDING")
                print("=" * 80)
                
                try:
                    checkout_callback_url = "https://api.craftpay.in/api/checkout/star23456/callback"
                    
                    # Prepare callback data for checkout page
                    checkout_callback_data = {
                        'order_id': merchant_order_id,
                        'status': mapped_status,
                        'amount': float(txn['txn_amount']) if txn['txn_amount'] else 0,
                        'utr': utr or '',
                        'txn_id': txn['txn_id'],
                        'bank_ref_no': utr or '',
                        'completed_at': datetime.now().isoformat()
                    }
                    
                    print(f"📤 Forwarding callback to checkout page: {checkout_callback_url}")
                    print(f"📦 Callback data: {json.dumps(checkout_callback_data, indent=2)}")
                    
                    try:
                        import requests
                        checkout_response = requests.post(
                            checkout_callback_url,
                            json=checkout_callback_data,
                            headers={'Content-Type': 'application/json'},
                            timeout=5
                        )
                        
                        print(f"✅ Checkout callback response: {checkout_response.status_code}")
                        print(f"📄 Checkout callback response: {checkout_response.text[:200]}")
                        
                    except requests.exceptions.RequestException as e:
                        print(f"❌ ERROR: Failed to send checkout callback: {e}")
                        # Don't fail the main callback if checkout notification fails
                        
                except Exception as e:
                    print(f"❌ ERROR in checkout callback forwarding: {e}")
                    import traceback
                    traceback.print_exc()
                
                return jsonify({'success': True, 'message': 'Callback processed successfully'}), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[Star23456 Callback] Error: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500
