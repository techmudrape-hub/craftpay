"""
Razorpay Callback Routes
Handles payin callbacks from Razorpay payment gateway
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json

razorpay_callback_bp = Blueprint('razorpay_callback', __name__, url_prefix='/api/callback')

@razorpay_callback_bp.route('/razorpay/payin', methods=['GET', 'POST'])
def razorpay_payin_callback():
    """
    Callback endpoint for Razorpay payin status updates
    Razorpay redirects customer here after payment completion
    
    Flow:
    1. Receive callback from Razorpay
    2. Call Razorpay Payment Link Status API to get complete details
    3. Extract bank UTR from payment details
    4. Update database
    5. Credit wallets
    6. Forward to merchant with complete details
    
    Expected callback format (GET parameters):
    - razorpay_payment_id
    - razorpay_payment_link_id
    - razorpay_payment_link_reference_id
    - razorpay_payment_link_status
    - razorpay_signature
    """
    try:
        # Get callback data - Razorpay sends as GET parameters
        callback_data = {}
        
        if request.method == 'GET':
            callback_data = request.args.to_dict()
            data_source = "GET"
        else:
            # Try JSON for POST
            try:
                callback_data = request.get_json(force=True, silent=True)
                if callback_data:
                    data_source = "JSON"
            except:
                pass
            
            # If no JSON, try form data
            if not callback_data:
                if request.form:
                    callback_data = request.form.to_dict()
                    data_source = "FORM"
        
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
        print("Razorpay Payin Callback Received")
        print("=" * 80)
        print(f"Data Source: {data_source}")
        print(f"Content-Type: {request.content_type}")
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")
        
        # Extract data from callback
        razorpay_payment_id = callback_data.get('razorpay_payment_id', '')
        razorpay_payment_link_id = callback_data.get('razorpay_payment_link_id', '')
        razorpay_payment_link_reference_id = callback_data.get('razorpay_payment_link_reference_id', '')
        razorpay_payment_link_status = callback_data.get('razorpay_payment_link_status', '')
        razorpay_signature = callback_data.get('razorpay_signature', '')
        
        print(f"Payment ID: {razorpay_payment_id}")
        print(f"Payment Link ID: {razorpay_payment_link_id}")
        print(f"Payment Link Reference ID: {razorpay_payment_link_reference_id}")
        print(f"Payment Link Status: {razorpay_payment_link_status}")
        print(f"Signature: {razorpay_signature[:20] if razorpay_signature else 'NOT PROVIDED'}...")
        
        if not razorpay_payment_link_id:
            print("ERROR: No razorpay_payment_link_id in callback")
            return jsonify({
                'success': False, 
                'message': 'Missing razorpay_payment_link_id'
            }), 400
        
        # STEP 1: Call Razorpay Payment Link Status API to get complete details
        print("=" * 80)
        print("STEP 1: Fetching complete payment details from Razorpay")
        print("=" * 80)
        
        from razorpay_service import razorpay_service
        
        status_result = razorpay_service.check_payment_status(razorpay_payment_link_id)
        
        if not status_result.get('success'):
            print(f"ERROR: Failed to fetch payment details: {status_result.get('message')}")
            return jsonify({
                'success': False,
                'message': f"Failed to fetch payment details: {status_result.get('message')}"
            }), 500
        
        print(f"✓ Payment details fetched successfully")
        print(f"Status from Razorpay: {status_result.get('status')}")
        print(f"Amount: {status_result.get('amount')}")
        print(f"Amount Paid: {status_result.get('amount_paid')}")
        print(f"Payment ID: {status_result.get('payment_id')}")
        print(f"Bank UTR: {status_result.get('utr')}")
        
        # Extract details from status result
        mapped_status = status_result.get('status', 'INITIATED')
        bank_utr = status_result.get('utr') or razorpay_payment_id
        payment_id = status_result.get('payment_id') or razorpay_payment_id
        
        print(f"Mapped Status: {mapped_status}")
        print(f"Bank UTR: {bank_utr}")
        
        # STEP 2: Update database
        print("=" * 80)
        print("STEP 2: Updating database")
        print("=" * 80)
        
        conn = get_db_connection()
        if not conn:
            print("ERROR: Database connection failed")
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Find transaction by pg_txn_id (payment_link_id)
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, order_id, amount as txn_amount, 
                           net_amount, charge_amount, callback_url
                    FROM payin_transactions
                    WHERE pg_partner = 'RAZORPAY'
                    AND pg_txn_id = %s
                    LIMIT 1
                """, (razorpay_payment_link_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    print(f"ERROR: Transaction not found for payment_link_id: {razorpay_payment_link_id}")
                    
                    # Try to find any Razorpay transaction to help debug
                    cursor.execute("""
                        SELECT txn_id, order_id, pg_txn_id, status
                        FROM payin_transactions
                        WHERE pg_partner = 'RAZORPAY'
                        ORDER BY created_at DESC
                        LIMIT 5
                    """)
                    recent_txns = cursor.fetchall()
                    
                    if recent_txns:
                        print(f"Recent Razorpay payin transactions:")
                        for t in recent_txns:
                            print(f"  - TXN: {t['txn_id']}, ORDER: {t['order_id']}, PG_TXN: {t['pg_txn_id']}, STATUS: {t['status']}")
                    
                    return jsonify({
                        'success': False, 
                        'message': f'Transaction not found for payment_link_id: {razorpay_payment_link_id}'
                    }), 404
                
                print(f"Found Transaction: {txn['txn_id']}, Current Status: {txn['status']}")
                
                # Update transaction with complete details from status API
                if mapped_status in ['SUCCESS', 'FAILED']:
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s, 
                            bank_ref_no = %s,
                            payment_mode = 'UPI',
                            completed_at = NOW(), 
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, bank_utr, txn['txn_id']))
                    print(f"✓ Updated with status={mapped_status}, bank_utr={bank_utr}, completed_at=NOW()")
                else:
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s, 
                            bank_ref_no = %s,
                            payment_mode = 'UPI',
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, bank_utr, txn['txn_id']))
                    print(f"✓ Updated status to {mapped_status}")
                
                conn.commit()
                
                # STEP 3: Credit wallet if status is SUCCESS
                if mapped_status == 'SUCCESS' and txn['merchant_id']:
                    print("=" * 80)
                    print("STEP 3: WALLET CREDIT - SUCCESS STATUS")
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
                                description=f"PayIn received (Razorpay) - {txn['order_id']}",
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
                                description=f"PayIn charge (Razorpay) - {txn['order_id']}",
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
                print("Razorpay Payin Callback processed successfully")
                print("=" * 80)
                
                # STEP 4: Forward callback to merchant with complete details
                print("=" * 80)
                print("STEP 4: MERCHANT CALLBACK FORWARDING (MAXPE FORMAT)")
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
                        
                        # Prepare callback payload for merchant in MAXPE format (flat structure)
                        merchant_callback_data = {
                            'txn_id': txn['txn_id'],
                            'order_id': txn['order_id'],
                            'status': mapped_status,
                            'utr': bank_utr,  # Real bank UTR from Razorpay status API
                            'pg_partner': 'RAZORPAY',
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
    """
    Callback endpoint for Razorpay payin status updates
    Razorpay redirects customer here after payment completion
    
    Expected callback format (GET parameters):
    - razorpay_payment_id
    - razorpay_payment_link_id
    - razorpay_payment_link_reference_id
    - razorpay_payment_link_status
    - razorpay_signature
    """
    try:
        # Get callback data - Razorpay sends as GET parameters
        callback_data = {}
        
        if request.method == 'GET':
            callback_data = request.args.to_dict()
            data_source = "GET"
        else:
            # Try JSON for POST
            try:
                callback_data = request.get_json(force=True, silent=True)
                if callback_data:
                    data_source = "JSON"
            except:
                pass
            
            # If no JSON, try form data
            if not callback_data:
                if request.form:
                    callback_data = request.form.to_dict()
                    data_source = "FORM"
        
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
        print("Razorpay Payin Callback Received")
        print("=" * 80)
        print(f"Data Source: {data_source}")
        print(f"Content-Type: {request.content_type}")
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")
        
        # Extract data from callback
        razorpay_payment_id = callback_data.get('razorpay_payment_id', '')
        razorpay_payment_link_id = callback_data.get('razorpay_payment_link_id', '')
        razorpay_payment_link_reference_id = callback_data.get('razorpay_payment_link_reference_id', '')
        razorpay_payment_link_status = callback_data.get('razorpay_payment_link_status', '')
        razorpay_signature = callback_data.get('razorpay_signature', '')
        
        print(f"Payment ID: {razorpay_payment_id}")
        print(f"Payment Link ID: {razorpay_payment_link_id}")
        print(f"Payment Link Reference ID: {razorpay_payment_link_reference_id}")
        print(f"Payment Link Status: {razorpay_payment_link_status}")
        print(f"Signature: {razorpay_signature[:20] if razorpay_signature else 'NOT PROVIDED'}...")
        
        if not razorpay_payment_link_id:
            print("ERROR: No razorpay_payment_link_id in callback")
            return jsonify({
                'success': False, 
                'message': 'Missing razorpay_payment_link_id'
            }), 400
        
        # Fetch actual bank UTR from Razorpay if payment is successful
        bank_utr = None
        if razorpay_payment_id and razorpay_payment_link_status == 'paid':
            try:
                print(f"Fetching payment details from Razorpay to get bank UTR...")
                from razorpay_service import razorpay_service
                
                # Fetch payment details from Razorpay
                payment_url = f"{razorpay_service.base_url}/v1/payments/{razorpay_payment_id}"
                payment_response = razorpay_service.session.get(
                    payment_url,
                    auth=razorpay_service.get_auth(),
                    headers=razorpay_service.get_headers(),
                    timeout=(10, 30)
                )
                
                if payment_response.status_code == 200:
                    payment_data = payment_response.json()
                    print(f"Payment data received: {json.dumps(payment_data, indent=2)}")
                    
                    # Extract UTR from acquirer_data
                    acquirer_data = payment_data.get('acquirer_data', {})
                    bank_utr = acquirer_data.get('rrn') or acquirer_data.get('utr') or acquirer_data.get('bank_transaction_id')
                    
                    if bank_utr:
                        print(f"✓ Bank UTR found: {bank_utr}")
                    else:
                        print(f"⚠ No bank UTR in acquirer_data. Available fields: {list(acquirer_data.keys())}")
                        # Fallback to payment_id if no UTR
                        bank_utr = razorpay_payment_id
                else:
                    print(f"⚠ Failed to fetch payment details: {payment_response.status_code}")
                    bank_utr = razorpay_payment_id
                    
            except Exception as e:
                print(f"⚠ Error fetching bank UTR: {e}")
                # Fallback to payment_id
                bank_utr = razorpay_payment_id
        else:
            # For non-paid status, use payment_id
            bank_utr = razorpay_payment_id
        
        # Map Razorpay status to our status
        # Razorpay statuses: paid, expired, cancelled, created
        if razorpay_payment_link_status == 'paid':
            mapped_status = 'SUCCESS'
        elif razorpay_payment_link_status in ['expired', 'cancelled']:
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
                # Find transaction by pg_txn_id (payment_link_id)
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, order_id, amount as txn_amount, 
                           net_amount, charge_amount, callback_url
                    FROM payin_transactions
                    WHERE pg_partner = 'RAZORPAY'
                    AND pg_txn_id = %s
                    LIMIT 1
                """, (razorpay_payment_link_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    print(f"ERROR: Transaction not found for payment_link_id: {razorpay_payment_link_id}")
                    
                    # Try to find any Razorpay transaction to help debug
                    cursor.execute("""
                        SELECT txn_id, order_id, pg_txn_id, status
                        FROM payin_transactions
                        WHERE pg_partner = 'RAZORPAY'
                        ORDER BY created_at DESC
                        LIMIT 5
                    """)
                    recent_txns = cursor.fetchall()
                    
                    if recent_txns:
                        print(f"Recent Razorpay payin transactions:")
                        for t in recent_txns:
                            print(f"  - TXN: {t['txn_id']}, ORDER: {t['order_id']}, PG_TXN: {t['pg_txn_id']}, STATUS: {t['status']}")
                    
                    return jsonify({
                        'success': False, 
                        'message': f'Transaction not found for payment_link_id: {razorpay_payment_link_id}'
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
                    """, (mapped_status, bank_utr, txn['txn_id']))
                    print(f"✓ Updated with status={mapped_status}, bank_utr={bank_utr}, completed_at=NOW()")
                else:
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s, 
                            bank_ref_no = %s,
                            payment_mode = 'UPI',
                            updated_at = NOW()
                        WHERE txn_id = %s
                    """, (mapped_status, bank_utr, txn['txn_id']))
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
                                description=f"PayIn received (Razorpay) - {txn['order_id']}",
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
                                description=f"PayIn charge (Razorpay) - {txn['order_id']}",
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
                print(f"Verification - Status: {updated_txn['status']}, Payment ID: {updated_txn['bank_ref_no']}, Completed: {updated_txn['completed_at']}")
                
                print("=" * 80)
                print("Razorpay Payin Callback processed successfully")
                print("=" * 80)
                
                # Forward callback to merchant if configured - MAXPE FORMAT
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
                        
                        # Prepare callback payload for merchant in MAXPE format (flat structure)
                        merchant_callback_data = {
                            'txn_id': txn['txn_id'],
                            'order_id': txn['order_id'],
                            'status': mapped_status,
                            'utr': bank_utr or razorpay_payment_id,  # Use bank UTR if available, else payment_id
                            'pg_partner': 'RAZORPAY',
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
