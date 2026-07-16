"""
Paytm Callback Routes
Handles payin callbacks from Paytm payment gateway
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json

paytm_callback_bp = Blueprint('paytm_callback', __name__, url_prefix='/api/callback')

@paytm_callback_bp.route('/paytm/payin', methods=['POST'])
def paytm_payin_callback():
    """
    Webhook endpoint for Paytm payin status updates
    Paytm will call this when payment status changes
    
    Expected callback format (POST form data):
    - ORDERID: Merchant order ID
    - MID: Merchant ID
    - TXNID: Paytm transaction ID
    - TXNAMOUNT: Transaction amount
    - PAYMENTMODE: Payment mode (UPI, CARD, etc.)
    - CURRENCY: INR
    - TXNDATE: Transaction date
    - STATUS: TXN_SUCCESS or TXN_FAILURE
    - RESPCODE: Response code (01 for success)
    - RESPMSG: Response message
    - GATEWAYNAME: Gateway name
    - BANKTXNID: Bank transaction ID (UTR)
    - CHECKSUMHASH: Checksum for verification
    """
    try:
        # Get callback data from Paytm - accept both JSON and form data
        callback_data = None
        data_source = None
        
        # Try form data first (Paytm sends form data)
        if request.form:
            callback_data = request.form.to_dict()
            data_source = "FORM"
        elif request.values:
            callback_data = request.values.to_dict()
            data_source = "VALUES"
        
        # Try JSON if no form data
        if not callback_data:
            try:
                callback_data = request.get_json(force=True, silent=True)
                if callback_data:
                    data_source = "JSON"
            except:
                pass
        
        # If still no data, try raw data
        if not callback_data:
            raw_data = request.get_data(as_text=True)
            if raw_data:
                try:
                    callback_data = json.loads(raw_data)
                    data_source = "RAW"
                except:
                    # Try to parse as form-encoded
                    from urllib.parse import parse_qs
                    try:
                        parsed = parse_qs(raw_data)
                        callback_data = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
                        data_source = "RAW_FORM"
                    except:
                        pass
        
        if not callback_data:
            raw_data = request.get_data(as_text=True)
            print(f"ERROR: No data received")
            print(f"Content-Type: {request.content_type}")
            print(f"Raw data: {raw_data[:500]}")
            return jsonify({
                'success': False, 
                'message': 'No data received in request'
            }), 400
        
        print("=" * 80)
        print("Paytm Payin Callback Received")
        print("=" * 80)
        print(f"Data Source: {data_source}")
        print(f"Content-Type: {request.content_type}")
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")
        
        # Extract data from callback
        order_id = callback_data.get('ORDERID', '')
        paytm_mid = callback_data.get('MID', '')
        paytm_txn_id = callback_data.get('TXNID', '')
        amount = callback_data.get('TXNAMOUNT', '0')
        payment_mode = callback_data.get('PAYMENTMODE', 'UPI')
        currency = callback_data.get('CURRENCY', 'INR')
        txn_date = callback_data.get('TXNDATE', '')
        status = callback_data.get('STATUS', '').upper()
        resp_code = callback_data.get('RESPCODE', '')
        resp_msg = callback_data.get('RESPMSG', '')
        gateway_name = callback_data.get('GATEWAYNAME', '')
        bank_txn_id = callback_data.get('BANKTXNID', '')  # This is the UTR
        checksum_hash = callback_data.get('CHECKSUMHASH', '')
        
        if not order_id:
            print("ERROR: No ORDERID in callback")
            return jsonify({
                'success': False, 
                'message': 'Missing ORDERID'
            }), 400
        
        print(f"Order ID: {order_id}")
        print(f"Paytm MID: {paytm_mid}")
        print(f"Paytm TXN ID: {paytm_txn_id}")
        print(f"Amount: {amount}")
        print(f"Payment Mode: {payment_mode}")
        print(f"Status: {status}")
        print(f"Response Code: {resp_code}")
        print(f"Response Message: {resp_msg}")
        print(f"Bank TXN ID (UTR): {bank_txn_id}")
        print(f"Gateway: {gateway_name}")
        print(f"Checksum: {checksum_hash[:40] if checksum_hash else 'NOT PROVIDED'}...")
        
        # OPTIONAL: Verify checksum (recommended for production)
        # Note: Checksum verification requires merchant key
        # Uncomment below code when merchant key is available
        """
        if checksum_hash:
            from paytm_service import paytm_service
            
            # Create body dict without checksum for verification
            body_for_verification = {k: v for k, v in callback_data.items() if k != 'CHECKSUMHASH'}
            
            is_valid = paytm_service.verify_checksum(body_for_verification, checksum_hash)
            
            if not is_valid:
                print("ERROR: Invalid checksum - callback may be tampered")
                return jsonify({
                    'success': False,
                    'message': 'Invalid checksum'
                }), 400
            
            print("✓ Checksum verified successfully")
        """
        print(f"Gateway: {gateway_name}")
        
        # Map Paytm status to our status
        # Paytm statuses: TXN_SUCCESS, TXN_FAILURE, PENDING
        if status == 'TXN_SUCCESS':
            mapped_status = 'SUCCESS'
        elif status == 'TXN_FAILURE':
            mapped_status = 'FAILED'
        else:
            mapped_status = 'INITIATED'
        
        print(f"Mapped Status: {mapped_status}")
        
        # Update database
        conn = get_db_connection()
        if not conn:
            print("ERROR: Database connection failed")
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Find transaction by order_id
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, order_id, amount as txn_amount, 
                           net_amount, charge_amount, callback_url
                    FROM payin_transactions
                    WHERE pg_partner = 'PAYTM'
                    AND order_id = %s
                    LIMIT 1
                """, (order_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    print(f"ERROR: Transaction not found for order_id: {order_id}")
                    
                    # Try to find any Paytm transaction to help debug
                    cursor.execute("""
                        SELECT txn_id, order_id, pg_txn_id, status
                        FROM payin_transactions
                        WHERE pg_partner = 'PAYTM'
                        ORDER BY created_at DESC
                        LIMIT 5
                    """)
                    recent_txns = cursor.fetchall()
                    
                    if recent_txns:
                        print(f"Recent Paytm payin transactions:")
                        for t in recent_txns:
                            print(f"  - TXN: {t['txn_id']}, ORDER: {t['order_id']}, PG_TXN: {t['pg_txn_id']}, STATUS: {t['status']}")
                    
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
                            pg_txn_id = %s,
                            payment_mode = %s,
                            completed_at = NOW(), 
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, bank_txn_id, paytm_txn_id, payment_mode, txn['txn_id']))
                    print(f"✓ Updated with status={mapped_status}, utr={bank_txn_id}, pg_txn_id={paytm_txn_id}, completed_at=NOW()")
                else:
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s, 
                            bank_ref_no = %s,
                            pg_txn_id = %s,
                            payment_mode = %s,
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, bank_txn_id, paytm_txn_id, payment_mode, txn['txn_id']))
                    print(f"✓ Updated status to {mapped_status}")
                
                conn.commit()
                
                # Credit wallet if status is SUCCESS and merchant_id exists
                if mapped_status == 'SUCCESS' and txn['merchant_id']:
                    print("=" * 80)
                    print("WALLET CREDIT - SUCCESS STATUS")
                    print("=" * 80)
                    
                    # Check if wallet was already credited (use txn_id)
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
                                description=f"PayIn received (Paytm) - {order_id}",
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
                                description=f"PayIn charge (Paytm) - {order_id}",
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
                print("Paytm Payin Callback processed successfully")
                print("=" * 80)
                
                # Forward callback to merchant if configured (MAXPE FORMAT)
                print("=" * 80)
                print("MERCHANT CALLBACK FORWARDING - PAYIN (MAXPE FORMAT)")
                print("=" * 80)
                print(f"Transaction merchant_id: {txn.get('merchant_id')}")
                print(f"Transaction callback_url field: {txn.get('callback_url')}")
                print(f"Mapped status: {mapped_status}")
                
                try:
                    # Get callback URL from transaction or merchant_callbacks table
                    callback_url = None
                    
                    if txn.get('callback_url'):
                        callback_url = txn['callback_url'].strip()
                        if not callback_url:
                            callback_url = None
                        else:
                            print(f"✅ Found callback_url in transaction: {callback_url}")
                    
                    if not callback_url and txn['merchant_id']:
                        print(f"Checking merchant_callbacks table for merchant: {txn['merchant_id']}")
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
                                print(f"✅ Found payin_callback_url in merchant_callbacks: {callback_url}")
                    
                    print(f"Final callback_url to use: {callback_url if callback_url else 'NONE'}")
                    
                    if callback_url:
                        print(f"✅ Callback URL found, proceeding with forwarding...")
                        
                        # DUPLICATE PREVENTION: Check if we already sent a SUCCESS callback
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
                                print(f"⚠ SUCCESS callback already sent to merchant - skipping duplicate")
                                print("=" * 80)
                                
                                return jsonify({
                                    'success': True,
                                    'message': 'Callback processed (duplicate prevented)',
                                    'txn_id': txn['txn_id'],
                                    'status': mapped_status
                                }), 200
                        
                        import requests
                        
                        # Prepare callback payload for merchant in MAXPE format
                        merchant_callback_data = {
                            'txn_id': txn['txn_id'],
                            'order_id': order_id,
                            'status': mapped_status,
                            'utr': bank_txn_id,
                            'pg_partner': 'PAYTM',
                            'amount': float(txn['txn_amount']) if txn['txn_amount'] else 0,
                            'net_amount': float(txn['net_amount']) if txn['net_amount'] else 0,
                            'charge_amount': float(txn['charge_amount']) if txn['charge_amount'] else 0
                        }
                        
                        print(f"📤 Forwarding payin callback to merchant: {callback_url}")
                        print(f"📦 Callback data (MAXPE format): {json.dumps(merchant_callback_data, indent=2)}")
                        
                        try:
                            print(f"🔄 Sending POST request...")
                            callback_response = requests.post(
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
                            
                        except requests.exceptions.RequestException as e:
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
                        
                except Exception as e:
                    print(f"❌ ERROR in merchant callback forwarding: {e}")
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
        print(f"ERROR in callback: {e}")
        import traceback
        traceback.print_exc()
        
        error_details = {
            'success': False,
            'message': str(e),
            'error_type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        
        return jsonify(error_details), 500
