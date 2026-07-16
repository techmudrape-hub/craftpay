"""
Maxpe Callback Routes
Handles payin callbacks from Maxpe payment gateway
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime
import json

maxpe_callback_bp = Blueprint('maxpe_callback', __name__, url_prefix='/api/callback')

@maxpe_callback_bp.route('/maxpe/payin', methods=['POST'])
def maxpe_payin_callback():
    """
    Webhook endpoint for Maxpe payin status updates
    Maxpe will call this when payment status changes
    
    Expected callback format:
    {
      "status": "SUCCESS",
      "transaction_details": {
        "amount": "1000.00",
        "merchant_order_id": "txn_00001",
        "utr": "608919646598"
      }
    }
    """
    try:
        # Get callback data from Maxpe - accept both JSON and form data
        callback_data = None
        data_source = None
        
        # Try JSON first
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
                # Try to parse nested JSON strings in form data
                for key, value in callback_data.items():
                    try:
                        callback_data[key] = json.loads(value)
                    except:
                        pass
            elif request.values:
                callback_data = request.values.to_dict()
                data_source = "VALUES"
                # Try to parse nested JSON strings
                for key, value in callback_data.items():
                    try:
                        callback_data[key] = json.loads(value)
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
        print("Maxpe Payin Callback Received")
        print("=" * 80)
        print(f"Data Source: {data_source}")
        print(f"Content-Type: {request.content_type}")
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")
        
        # Extract data from callback
        status = callback_data.get('status', '').upper()
        transaction_details = callback_data.get('transaction_details', {})
        
        if not transaction_details:
            print("ERROR: No transaction_details in callback")
            return jsonify({
                'success': False, 
                'message': 'Missing transaction_details'
            }), 400
        
        # MaxPe sends order ID as either 'merchant_order_id' or 'transaction_id'
        merchant_order_id = transaction_details.get('merchant_order_id') or transaction_details.get('transaction_id')
        amount = transaction_details.get('amount')
        utr = transaction_details.get('utr')
        charge = transaction_details.get('charge')
        gst = transaction_details.get('gst')
        paid_amount = transaction_details.get('paid_amount')
        
        if not merchant_order_id:
            print("ERROR: No merchant_order_id or transaction_id in callback")
            print(f"Available keys: {list(transaction_details.keys())}")
            return jsonify({
                'success': False, 
                'message': 'Missing merchant_order_id or transaction_id',
                'received_keys': list(transaction_details.keys())
            }), 400
        
        print(f"Merchant Order ID: {merchant_order_id}")
        print(f"Status: {status}")
        print(f"Amount: {amount}")
        print(f"UTR: {utr}")
        print(f"Charge: {charge}")
        print(f"GST: {gst}")
        print(f"Paid Amount: {paid_amount}")
        
        # Map Maxpe status to our status
        # Database ENUM: INITIATED, QUEUED, INPROCESS, SUCCESS, FAILED, REVERSED
        if status == 'SUCCESS':
            mapped_status = 'SUCCESS'
        elif status == 'FAILED':
            mapped_status = 'FAILED'
        elif status == 'PENDING':
            mapped_status = 'INITIATED'
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
                # Find transaction by order_id, or pg_txn_id
                # Try order_id first (most common)
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, order_id, amount as txn_amount, 
                           net_amount, charge_amount, callback_url
                    FROM payin_transactions
                    WHERE pg_partner = 'MAXPE'
                    AND order_id = %s
                    LIMIT 1
                """, (merchant_order_id,))
                
                txn = cursor.fetchone()
                
                # If still not found, try pg_txn_id
                if not txn:
                    print(f"[MaxPe Payin Callback] Transaction not found by order_id, trying pg_txn_id...")
                    cursor.execute("""
                        SELECT txn_id, status, merchant_id, order_id, amount as txn_amount, 
                               net_amount, charge_amount, callback_url
                        FROM payin_transactions
                        WHERE pg_partner = 'MAXPE'
                        AND pg_txn_id = %s
                        LIMIT 1
                    """, (merchant_order_id,))
                    
                    txn = cursor.fetchone()
                
                if not txn:
                    print(f"ERROR: Transaction not found for merchant_order_id: {merchant_order_id}")
                    print(f"Searched in: order_id, pg_txn_id")
                    
                    # Try to find any Maxpe transaction to help debug
                    cursor.execute("""
                        SELECT txn_id, order_id, pg_txn_id, status
                        FROM payin_transactions
                        WHERE pg_partner = 'MAXPE'
                        ORDER BY created_at DESC
                        LIMIT 5
                    """)
                    recent_txns = cursor.fetchall()
                    
                    if recent_txns:
                        print(f"Recent Maxpe payin transactions:")
                        for t in recent_txns:
                            print(f"  - TXN: {t['txn_id']}, ORDER: {t['order_id']}, PG_TXN: {t['pg_txn_id']}, STATUS: {t['status']}")
                    
                    return jsonify({
                        'success': False, 
                        'message': f'Transaction not found for merchant_order_id: {merchant_order_id}. This callback may be for a transaction created outside this system.'
                    }), 404
                
                print(f"Found Transaction: {txn['txn_id']}, Current Status: {txn['status']}")
                
                # Don't skip if status is already SUCCESS - we still need to forward the callback
                # The duplicate prevention will be handled later by checking callback_logs
                
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
                    # Status is still pending/initiated
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
                                description=f"PayIn received (Maxpe) - {merchant_order_id}",
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
                                description=f"PayIn charge (Maxpe) - {merchant_order_id}",
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
                
                # Verify the update
                cursor.execute("""
                    SELECT status, bank_ref_no, completed_at
                    FROM payin_transactions
                    WHERE txn_id = %s
                """, (txn['txn_id'],))
                
                updated_txn = cursor.fetchone()
                print(f"Verification - Status: {updated_txn['status']}, UTR: {updated_txn['bank_ref_no']}, Completed: {updated_txn['completed_at']}")
                
                print("=" * 80)
                print("Maxpe Payin Callback processed successfully")
                print("=" * 80)
                
                # Forward callback to merchant if configured
                print("=" * 80)
                print("MERCHANT CALLBACK FORWARDING - PAYIN")
                print("=" * 80)
                print(f"Transaction merchant_id: {txn.get('merchant_id')}")
                print(f"Transaction callback_url field: {txn.get('callback_url')}")
                print(f"Mapped status: {mapped_status}")
                print(f"Is SUCCESS: {mapped_status == 'SUCCESS'}")
                
                try:
                    # Get callback URL from transaction or merchant_callbacks table
                    callback_url = None
                    
                    if txn.get('callback_url'):
                        callback_url = txn['callback_url'].strip()
                        if not callback_url:  # Empty string after strip
                            callback_url = None
                        else:
                            print(f"✅ Found callback_url in transaction: {callback_url}")
                    
                    print(f"Step 1: Transaction callback_url from DB: {callback_url if callback_url else 'NOT SET'}")
                    
                    # If no callback URL in transaction, check merchant_callbacks table
                    if not callback_url and txn['merchant_id']:
                        print(f"Step 2: Checking merchant_callbacks table for merchant: {txn['merchant_id']}")
                        cursor.execute("""
                            SELECT payin_callback_url FROM merchant_callbacks
                            WHERE merchant_id = %s
                        """, (txn['merchant_id'],))
                        
                        merchant_callback = cursor.fetchone()
                        if merchant_callback and merchant_callback.get('payin_callback_url'):
                            callback_url = merchant_callback['payin_callback_url'].strip()
                            if not callback_url:  # Empty string after strip
                                callback_url = None
                            else:
                                print(f"✅ Found payin_callback_url in merchant_callbacks: {callback_url}")
                        
                        print(f"Step 2: Merchant payin_callback_url: {callback_url if callback_url else 'NOT SET'}")
                    
                    print(f"Final callback_url to use: {callback_url if callback_url else 'NONE'}")
                    
                    if callback_url:
                        print(f"✅ Callback URL found, proceeding with forwarding...")
                        
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
                            
                            print(f"Duplicate check result: {success_callback_sent}")
                            
                            if success_callback_sent:
                                print(f"⚠ SUCCESS callback already sent to merchant - skipping duplicate")
                                print(f"  This is a duplicate callback from Maxpe")
                                print("=" * 80)
                                
                                return jsonify({
                                    'success': True,
                                    'message': 'Callback processed (duplicate prevented)',
                                    'txn_id': txn['txn_id'],
                                    'status': mapped_status
                                }), 200
                        
                        import requests
                        
                        # Prepare callback payload for merchant
                        merchant_callback_data = {
                            'txn_id': txn['txn_id'],
                            'order_id': merchant_order_id,
                            'status': mapped_status,
                            'utr': utr,
                            'pg_partner': 'MAXPE',
                            'amount': float(txn['txn_amount']) if txn['txn_amount'] else 0,
                            'net_amount': float(txn['net_amount']) if txn['net_amount'] else 0,
                            'charge_amount': float(txn['charge_amount']) if txn['charge_amount'] else 0
                        }
                        
                        print(f"📤 Forwarding payin callback to merchant: {callback_url}")
                        print(f"📦 Callback data: {json.dumps(merchant_callback_data, indent=2)}")
                        
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
                                callback_response.text[:1000]  # Limit response data
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
                        print("   - Transaction callback_url: NOT SET or EMPTY")
                        print("   - Merchant payin_callback_url: NOT SET or EMPTY")
                        
                except Exception as e:
                    print(f"❌ ERROR in merchant callback forwarding: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Forward callback to checkout page
                print("=" * 80)
                print("CHECKOUT PAGE CALLBACK FORWARDING")
                print("=" * 80)
                
                try:
                    import os
                    backend_url = os.getenv('BACKEND_URL', 'http://localhost:5000')
                    checkout_callback_url = f"{backend_url}/api/checkout/maxpe/callback"
                    
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
        
        # Return detailed error for debugging
        error_details = {
            'success': False,
            'message': str(e),
            'error_type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        
        return jsonify(error_details), 500
