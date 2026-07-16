from flask import Blueprint, request, jsonify
from database import get_db_connection
from timezone_utils import parse_mudrape_timestamp
from datetime import datetime
import json
import requests

mudrape_callback_bp = Blueprint('mudrape_callback', __name__, url_prefix='/api/callback')

@mudrape_callback_bp.route('/mudrape/payout', methods=['POST'])
def mudrape_payout_callback():
    """
    Webhook endpoint for Mudrape payout status updates
    Mudrape will call this when payout status changes
    
    NEW FORMAT (April 2026):
    {
      "payoutId": "cmnu09uuj000555555gvrxyf",
      "referenceId": "TXN4830995555001",
      "externalTxnId": "610112455543",
      "amount": 100,
      "status": "SUCCESS",
      "utr": "610112455543",
      "channel": "IMPS",
      "payeeName": "Test",
      "timestamp": "2026-04-11T12:52:28.471435",
      "provider": "PAYMENT GATEWAY"
    }
    """
    try:
        # Get callback data from Mudrape
        callback_data = request.json
        
        print("=" * 80)
        print("Mudrape Payout Callback Received")
        print("=" * 80)
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")
        
        # NEW FORMAT (April 2026) - Primary fields
        # referenceId = our client_txn_id that we sent to Mudrape
        client_txn_id = (callback_data.get('referenceId') or  # NEW FORMAT
                        callback_data.get('clientTxnId') or   # OLD FORMAT
                        callback_data.get('apiTxnId') or
                        callback_data.get('data', {}).get('clientTxnId') or
                        callback_data.get('data', {}).get('clientTransactionId'))
        
        # Status - NEW FORMAT uses direct "status" field
        payout_status = callback_data.get('status')  # NEW FORMAT: "SUCCESS", "FAILED", "PENDING"
        status_code = callback_data.get('statusCode') or callback_data.get('statuscode')  # OLD FORMAT
        
        # UTR - NEW FORMAT
        utr = (callback_data.get('utr') or  # NEW FORMAT
               callback_data.get('externalTxnId') or  # NEW FORMAT alternative
               callback_data.get('uniqueId') or
               callback_data.get('data', {}).get('txnId') or
               callback_data.get('data', {}).get('bankRefNo'))
        
        # Mudrape transaction ID - NEW FORMAT uses "payoutId"
        mudrape_txn_id = (callback_data.get('payoutId') or  # NEW FORMAT
                         callback_data.get('externalTxnId') or  # NEW FORMAT
                         callback_data.get('data', {}).get('txnId') or
                         callback_data.get('transactionId') or
                         callback_data.get('apiTxnId'))
        
        # Extract completion timestamp - NEW FORMAT
        processed_at = (callback_data.get('timestamp') or  # NEW FORMAT
                       callback_data.get('data', {}).get('processedAt') if callback_data.get('data') else None or
                       callback_data.get('data', {}).get('transactionDate') if callback_data.get('data') else None)
        
        # Extract additional NEW FORMAT fields
        channel = callback_data.get('channel', '')  # "IMPS", "UPI", etc.
        payee_name = callback_data.get('payeeName', '')
        provider = callback_data.get('provider', '')
        amount = callback_data.get('amount')
        
        if not client_txn_id:
            print("ERROR: No referenceId/clientTxnId in callback")
            return jsonify({'success': False, 'message': 'Missing referenceId/clientTxnId'}), 400
        
        print(f"Client TXN ID (referenceId): {client_txn_id}")
        print(f"Payout Status: {payout_status}")
        print(f"Status Code (old): {status_code}")
        print(f"UTR: {utr}")
        print(f"Mudrape Payout ID: {mudrape_txn_id}")
        print(f"Channel: {channel}")
        print(f"Payee Name: {payee_name}")
        print(f"Amount: {amount}")
        print(f"Timestamp: {processed_at}")
        print(f"Provider: {provider}")
        
        # Map Mudrape status to our status
        # Database ENUM: INITIATED, QUEUED, INPROCESS, SUCCESS, FAILED, REVERSED
        if payout_status and payout_status.upper() == 'SUCCESS':
            status = 'SUCCESS'
        elif payout_status and payout_status.upper() == 'FAILED':
            status = 'FAILED'
        elif payout_status and payout_status.upper() == 'PENDING':
            status = 'INITIATED'
        elif status_code == 10000:  # OLD FORMAT fallback
            status = 'SUCCESS'
        elif status_code == 10003:  # OLD FORMAT fallback
            status = 'FAILED'
        else:
            status = 'INITIATED'
        
        print(f"Mapped Status: {status}")
        
        # Convert processed_at to IST if available
        completed_at = None
        if processed_at and status in ['SUCCESS', 'FAILED']:
            completed_at = parse_mudrape_timestamp(processed_at)
            if completed_at:
                print(f"Completed At (IST): {completed_at}")
        
        # Update database
        conn = get_db_connection()
        if not conn:
            print("ERROR: Database connection failed")
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Find transaction by reference_id (which is the client_txn_id)
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, reference_id
                    FROM payout_transactions
                    WHERE reference_id = %s
                """, (client_txn_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    print(f"ERROR: Transaction not found for reference_id: {client_txn_id}")
                    return jsonify({'success': False, 'message': 'Transaction not found'}), 404
                
                print(f"Found Transaction: {txn['txn_id']}, Current Status: {txn['status']}")
                
                # CRITICAL: Debit wallet when status is SUCCESS
                # Check if wallet was already deducted to prevent duplicate deductions
                if status == 'SUCCESS' and txn['merchant_id']:
                    # Check if wallet was already deducted
                    cursor.execute("""
                        SELECT txn_id FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'DEBIT'
                    """, (txn['txn_id'],))
                    
                    wallet_already_deducted = cursor.fetchone()
                    
                    if wallet_already_deducted:
                        print(f"⚠️  Wallet already deducted for this transaction - skipping")
                    else:
                        print(f"Status is SUCCESS - Debiting merchant settled wallet")
                        
                        # Get transaction details for wallet deduction
                        # NOTE: 'amount' field already contains total deduction (payout amount + charges)
                        cursor.execute("""
                            SELECT amount, net_amount, charge_amount FROM payout_transactions
                            WHERE txn_id = %s
                        """, (txn['txn_id'],))
                        payout_details = cursor.fetchone()
                        
                        # Use 'amount' field which already contains total deduction
                        total_deduction = float(payout_details['amount'])
                        
                        print(f"Deducting from settled wallet - Amount: ₹{total_deduction:.2f} (Net: ₹{payout_details['net_amount']:.2f} + Charges: ₹{payout_details['charge_amount']:.2f})")
                        
                        # Debit merchant settled wallet
                        from wallet_service import WalletService
                        wallet_svc = WalletService()
                        debit_result = wallet_svc.debit_merchant_wallet(
                            merchant_id=txn['merchant_id'],
                            amount=total_deduction,
                            description=f"Payout: ₹{payout_details['net_amount']:.2f} + Charges: ₹{payout_details['charge_amount']:.2f}",
                            reference_id=txn['txn_id']
                        )
                        
                        if debit_result['success']:
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                        else:
                            print(f"✗ WALLET DEBIT FAILED: {debit_result['message']}")
                            # Update transaction to FAILED if wallet debit fails
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = 'FAILED', error_message = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (f"Wallet debit failed: {debit_result['message']}", txn['txn_id']))
                            conn.commit()
                            
                            return jsonify({
                                'success': False,
                                'message': f"Payout succeeded but wallet debit failed: {debit_result['message']}"
                            }), 500
                
                # Update transaction with callback data
                if status in ['SUCCESS', 'FAILED']:
                    if completed_at:
                        # Use timestamp from Mudrape
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = %s, utr = %s, pg_txn_id = %s, completed_at = %s, updated_at = NOW()
                            WHERE reference_id = %s
                        """, (status, utr, mudrape_txn_id, completed_at, client_txn_id))
                        print(f"✓ Updated with completed_at from Mudrape: {completed_at}")
                    else:
                        # Fallback to NOW() if no timestamp
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = %s, utr = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (status, utr, mudrape_txn_id, client_txn_id))
                        print(f"✓ Updated with completed_at = NOW()")
                else:
                    # Status is still pending/initiated
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, pg_txn_id = %s, updated_at = NOW()
                        WHERE reference_id = %s
                    """, (status, utr, mudrape_txn_id, client_txn_id))
                    print(f"✓ Updated status to {status}")
                
                conn.commit()
                
                # Verify the update
                cursor.execute("""
                    SELECT status, utr, pg_txn_id, completed_at
                    FROM payout_transactions
                    WHERE reference_id = %s
                """, (client_txn_id,))
                
                updated_txn = cursor.fetchone()
                print(f"Verification - Status: {updated_txn['status']}, UTR: {updated_txn['utr']}, PG_TXN_ID: {updated_txn['pg_txn_id']}, Completed: {updated_txn['completed_at']}")
                
                print("=" * 80)
                print("Mudrape Payout Callback processed successfully")
                print("=" * 80)
                
                # Forward callback to merchant if configured
                print("=" * 80)
                print("MERCHANT CALLBACK FORWARDING - PAYOUT")
                print("=" * 80)
                try:
                    # First, get the callback URL from the transaction itself (sent in payout payload)
                    cursor.execute("""
                        SELECT callback_url FROM payout_transactions
                        WHERE reference_id = %s
                    """, (client_txn_id,))
                    
                    txn_callback = cursor.fetchone()
                    callback_url = None
                    
                    if txn_callback and txn_callback.get('callback_url'):
                        callback_url = txn_callback['callback_url'].strip()
                        if not callback_url:  # Empty string after strip
                            callback_url = None
                    
                    print(f"Step 1: Transaction callback_url from DB: {callback_url if callback_url else 'NOT SET'}")
                    
                    # If no callback URL in transaction, check merchant_callbacks table
                    if not callback_url:
                        print(f"Step 2: Checking merchant_callbacks table for merchant: {txn['merchant_id']}")
                        cursor.execute("""
                            SELECT payout_callback_url FROM merchant_callbacks
                            WHERE merchant_id = %s
                        """, (txn['merchant_id'],))
                        
                        merchant_callback = cursor.fetchone()
                        if merchant_callback and merchant_callback.get('payout_callback_url'):
                            callback_url = merchant_callback['payout_callback_url'].strip()
                            if not callback_url:  # Empty string after strip
                                callback_url = None
                        
                        print(f"Step 2: Merchant payout_callback_url: {callback_url if callback_url else 'NOT SET'}")
                    
                    if callback_url:
                        # DUPLICATE PREVENTION: Check if we already sent a SUCCESS callback for this transaction
                        if status == 'SUCCESS':
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
                                print(f"  This is a duplicate callback from Mudrape")
                                print("=" * 80)
                                
                                return jsonify({
                                    'success': True,
                                    'message': 'Callback processed (duplicate prevented)',
                                    'txn_id': txn['txn_id'],
                                    'status': status
                                }), 200
                        
                        import requests
                        
                        # Prepare callback payload for merchant (NEW FORMAT compatible)
                        merchant_callback_data = {
                            'txn_id': txn['txn_id'],
                            'reference_id': client_txn_id,
                            'referenceId': client_txn_id,  # NEW FORMAT
                            'status': status,
                            'utr': utr,
                            'externalTxnId': utr,  # NEW FORMAT
                            'pg_txn_id': mudrape_txn_id,
                            'payoutId': mudrape_txn_id,  # NEW FORMAT
                            'pg_partner': 'Mudrape',
                            'provider': 'Mudrape',  # NEW FORMAT
                            'channel': channel,  # NEW FORMAT
                            'payeeName': payee_name,  # NEW FORMAT
                            'amount': amount,  # NEW FORMAT
                            'timestamp': processed_at or datetime.now().isoformat()
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
                            
                            print(f"✓ Merchant payout callback sent successfully and logged")
                            
                        except requests.exceptions.RequestException as e:
                            print(f"ERROR: Failed to send merchant payout callback: {e}")
                            
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
                    else:
                        print("No merchant payout callback URL configured (neither in transaction nor merchant_callbacks table)")
                        
                except Exception as e:
                    print(f"ERROR in merchant callback forwarding: {e}")
                    import traceback
                    traceback.print_exc()
                
                return jsonify({
                    'success': True,
                    'message': 'Callback processed successfully',
                    'txn_id': txn['txn_id'],
                    'status': status
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"ERROR in callback: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@mudrape_callback_bp.route('/mudrape/payin', methods=['POST'])
def mudrape_payin_callback():
    """
    Webhook endpoint for Mudrape payin status updates (NEW API FORMAT)
    Mudrape will call this when payin status changes
    
    NEW FORMAT (April 2026):
    {
      "payinId": "clx1234567890abcdef",
      "orderId": "ORDER123456",
      "externalTxnId": "TXN_IND_1712345678",
      "amount": 100.50,
      "status": "SUCCESS",
      "bankTransactionId": "312345678901",
      "bankReferenceNumber": "BNK123456789",
      "channel": "INDICONNECT",
      "customerName": "John Doe",
      "timestamp": "2026-04-11T10:35:00.000Z",
      "provider": "INDICONNECT"
    }
    """
    try:
        print("=" * 80)
        print("Mudrape Payin Callback Received (NEW API)")
        print("=" * 80)
        
        # Log request details
        print(f"Content-Type: {request.content_type}")
        print(f"Headers: {dict(request.headers)}")
        
        # Get callback data - support both JSON and form-data
        callback_data = None
        
        if request.is_json:
            callback_data = request.json
            print("Received as JSON")
        elif request.form:
            callback_data = request.form.to_dict()
            print("Received as Form Data")
        elif request.data:
            try:
                callback_data = json.loads(request.data.decode('utf-8'))
                print("Received as Raw Data (parsed as JSON)")
            except:
                print(f"Raw Data (could not parse): {request.data}")
                return jsonify({'success': False, 'message': 'Invalid data format'}), 400
        else:
            print("ERROR: No data received")
            return jsonify({'success': False, 'message': 'No data received'}), 400
        
        print(f"Callback Data: {json.dumps(callback_data, indent=2)}")
        
        # Extract data from NEW API callback format
        payin_id = callback_data.get('payinId')
        order_id = callback_data.get('orderId')
        external_txn_id = callback_data.get('externalTxnId')
        amount = callback_data.get('amount')
        status = callback_data.get('status')
        bank_transaction_id = callback_data.get('bankTransactionId')
        bank_reference_number = callback_data.get('bankReferenceNumber')
        channel = callback_data.get('channel', 'UPI')
        customer_name = callback_data.get('customerName', '')
        timestamp = callback_data.get('timestamp', '')
        provider = callback_data.get('provider', '')
        
        if not order_id:
            print("ERROR: No orderId in callback")
            return jsonify({'success': False, 'message': 'Missing orderId in callback'}), 400
        
        print(f"NEW API Callback Format:")
        print(f"  Payin ID: {payin_id}")
        print(f"  Order ID: {order_id}")
        print(f"  External TXN ID: {external_txn_id}")
        print(f"  Status: {status}")
        print(f"  Amount: {amount}")
        print(f"  Bank Transaction ID: {bank_transaction_id}")
        print(f"  Bank Reference Number: {bank_reference_number}")
        print(f"  Channel: {channel}")
        print(f"  Customer Name: {customer_name}")
        print(f"  Timestamp: {timestamp}")
        print(f"  Provider: {provider}")
        
        # Map status
        if status and status.upper() == 'SUCCESS':
            mapped_status = 'SUCCESS'
        elif status and status.upper() == 'FAILED':
            mapped_status = 'FAILED'
        else:
            mapped_status = 'INITIATED'
        
        print(f"Mapped Status: {mapped_status}")
        
        # UTR extraction - handle multiple field name variations
        # Priority: bankReferenceNumber > utr > bankTransactionId > bank_ref_no > bankRefNo
        utr = (callback_data.get('bankReferenceNumber') or 
               callback_data.get('utr') or 
               callback_data.get('bankTransactionId') or
               callback_data.get('bank_ref_no') or
               callback_data.get('bankRefNo') or
               callback_data.get('bank_reference_number'))
        
        print(f"  Extracted UTR: {utr}")
        
        # Update database
        conn = get_db_connection()
        if not conn:
            print("ERROR: Database connection failed")
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Find transaction by order_id
                cursor.execute("""
                    SELECT txn_id, status, merchant_id, amount as txn_amount, pg_partner
                    FROM payin_transactions
                    WHERE order_id = %s
                """, (order_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    print(f"ERROR: Transaction not found for order_id: {order_id}")
                    return jsonify({'success': False, 'message': 'Transaction not found'}), 404
                
                print(f"Found Transaction: {txn['txn_id']}, Current Status: {txn['status']}, PG Partner: {txn.get('pg_partner', 'Mudrape')}")
                
                # Update transaction
                if mapped_status == 'SUCCESS':
                    # Check if wallet has already been credited (idempotency check)
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                        WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                    """, (txn['txn_id'],))
                    
                    wallet_credit_exists = cursor.fetchone()['count'] > 0
                    
                    if wallet_credit_exists:
                        print(f"⚠ Wallet already credited for this transaction - skipping wallet credit")
                        print(f"  This is a duplicate callback from Mudrape")
                        
                        # Just update transaction status and UTR if needed
                        if txn['status'] != 'SUCCESS':
                            cursor.execute("""
                                UPDATE payin_transactions
                                SET status = %s, bank_ref_no = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE order_id = %s
                            """, (mapped_status, utr, payin_id, order_id))
                            conn.commit()
                            print(f"✓ Updated transaction status to SUCCESS")
                        elif utr and utr != txn.get('bank_ref_no'):
                            cursor.execute("""
                                UPDATE payin_transactions
                                SET bank_ref_no = %s, pg_txn_id = %s, updated_at = NOW()
                                WHERE order_id = %s
                            """, (utr, payin_id, order_id))
                            conn.commit()
                            print(f"✓ Updated UTR to {utr}")
                        
                        return jsonify({
                            'success': True,
                            'message': 'Callback processed (duplicate prevented)',
                            'txn_id': txn['txn_id'],
                            'status': mapped_status
                        }), 200
                    
                    # First time SUCCESS callback - update transaction and credit wallet
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s, completed_at = NOW(), updated_at = NOW()
                        WHERE order_id = %s
                    """, (mapped_status, utr, payin_id, channel, order_id))
                    
                    # Get charge details for wallet credit
                    cursor.execute("""
                        SELECT net_amount, charge_amount FROM payin_transactions
                        WHERE txn_id = %s
                    """, (txn['txn_id'],))
                    
                    charge_details = cursor.fetchone()
                    net_amount = float(charge_details['net_amount'])
                    charge_amount = float(charge_details['charge_amount'])
                    
                    # Credit merchant unsettled wallet
                    from wallet_service import wallet_service as wallet_svc
                    wallet_result = wallet_svc.credit_unsettled_wallet(
                        merchant_id=txn['merchant_id'],
                        amount=net_amount,
                        description=f"PayIn received - {order_id}",
                        reference_id=txn['txn_id']
                    )
                    
                    if wallet_result['success']:
                        print(f"✓ Merchant wallet credited: ₹{net_amount}")
                    else:
                        print(f"✗ Failed to credit merchant wallet: {wallet_result.get('message')}")
                    
                    # Credit admin unsettled wallet
                    admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                        admin_id='admin',
                        amount=charge_amount,
                        description=f"PayIn charge - {order_id}",
                        reference_id=txn['txn_id']
                    )
                    
                    if admin_wallet_result['success']:
                        print(f"✓ Admin wallet credited: ₹{charge_amount}")
                    else:
                        print(f"✗ Failed to credit admin wallet: {admin_wallet_result.get('message')}")
                    
                    conn.commit()
                    print(f"✓ Transaction updated to SUCCESS and wallets credited")
                    
                elif mapped_status == 'FAILED':
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                        WHERE order_id = %s
                    """, (mapped_status, utr, payin_id, order_id))
                    conn.commit()
                    print(f"✓ Transaction updated to FAILED")
                else:
                    # Status is still pending/initiated
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = %s, pg_txn_id = %s, updated_at = NOW()
                        WHERE order_id = %s
                    """, (mapped_status, payin_id, order_id))
                    conn.commit()
                    print(f"✓ Transaction updated to {mapped_status}")
                
                # Forward callback to merchant if configured
                print("=" * 80)
                print("MERCHANT CALLBACK FORWARDING - PAYIN")
                print("=" * 80)
                try:
                    # Get callback URL from transaction
                    cursor.execute("""
                        SELECT callback_url FROM payin_transactions
                        WHERE order_id = %s
                    """, (order_id,))
                    
                    txn_callback = cursor.fetchone()
                    callback_url = None
                    
                    if txn_callback and txn_callback.get('callback_url'):
                        callback_url = txn_callback['callback_url'].strip()
                        if not callback_url:
                            callback_url = None
                    
                    print(f"Transaction callback_url from DB: {callback_url if callback_url else 'NOT SET'}")
                    
                    if callback_url:
                        # DUPLICATE PREVENTION: Check if we already sent a SUCCESS callback
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
                        
                        # Prepare callback payload for merchant (NEW FORMAT)
                        merchant_callback_data = {
                            'txn_id': txn['txn_id'],
                            'order_id': order_id,
                            'orderId': order_id,
                            'payin_id': payin_id,
                            'payinId': payin_id,
                            'status': mapped_status,
                            'amount': amount,
                            'utr': utr,
                            'bankTransactionId': bank_transaction_id,
                            'bankReferenceNumber': bank_reference_number,
                            'external_txn_id': external_txn_id,
                            'externalTxnId': external_txn_id,
                            'pg_partner': 'Mudrape',
                            'provider': provider or 'Mudrape',
                            'channel': channel,
                            'customerName': customer_name,
                            'timestamp': timestamp or datetime.now().isoformat()
                        }
                        
                        print(f"Forwarding payin callback to merchant: {callback_url}")
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
                            
                            print(f"✓ Merchant payin callback sent successfully and logged")
                            
                        except requests.exceptions.RequestException as e:
                            print(f"ERROR: Failed to send merchant payin callback: {e}")
                            
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
                    else:
                        print("No merchant payin callback URL configured")
                        
                except Exception as e:
                    print(f"ERROR in merchant callback forwarding: {e}")
                    import traceback
                    traceback.print_exc()
                
                print("=" * 80)
                print("Mudrape Payin Callback processed successfully")
                print("=" * 80)
                
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
        return jsonify({'success': False, 'message': str(e)}), 500
