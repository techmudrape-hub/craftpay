from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from functools import wraps
import jwt
import bcrypt
from datetime import datetime
from database_pooled import get_db_connection
from config import Config
import payout_service
import payu_payout_service
import wallet_service
import uuid
import json
from mudrape_service import mudrape_service
from instantpesa_service import InstantPesaService
from paytouch_service import paytouch_service
from paytouch2_service import paytouch2_service
from cinoright_service import cinoright_service
from maxpe_payout_service import maxpe_payout_service, get_payout_service
from clockspay_payout_service import clockspay_payout_service
from sectorpe_payout_service import sectorpe_payout_service
from rockypayz_payout_service import rockypayz_payout_service
from oqpay_payout_service import oqpay_payout_service
from alopna_service import alopna_service
from risexpay_payout_service import risexpay_payout_service
from tpipay_payout_service import tpipay_payout_service
from makemypayment_payout_service import makemypayment_payout_service
from oro_payout_service import oro_payout_service

payout_bp = Blueprint('payout', __name__, url_prefix='/api/payout')

# Get service instances
payout_svc = payout_service.payout_service
payu_payout_svc = payu_payout_service.payu_payout_service
wallet_svc = wallet_service.wallet_service
instantpesa_svc = InstantPesaService()


# Admin Personal Payout
@payout_bp.route('/admin/risexpay-auto-success', methods=['POST'])
@jwt_required()
def toggle_risexpay_auto_success():
    try:
        data = request.json
        is_enabled = data.get('enabled', True)
        merchant_id = data.get('merchant_id')
        
        import risexpay_payout_service as rps
        rps.set_auto_success_enabled(is_enabled, merchant_id)
        
        # We don't need to update rps.AUTO_SUCCESS_ENABLED anymore as it's fetched dynamically
        
        msg = f"Risexpay auto-success turned {'ON' if is_enabled else 'OFF'} successfully"
        if merchant_id:
            msg += f" for merchant {merchant_id}"
            
        return jsonify({
            'success': True,
            'message': msg,
            'enabled': is_enabled,
            'merchant_id': merchant_id
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@payout_bp.route('/admin/risexpay-auto-success', methods=['GET'])
@jwt_required()
def get_risexpay_auto_success():
    try:
        merchant_id = request.args.get('merchant_id')
        import risexpay_payout_service as rps
        return jsonify({
            'success': True,
            'enabled': rps.get_auto_success_enabled(merchant_id),
            'merchant_id': merchant_id
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@payout_bp.route('/admin/personal-payout', methods=['POST'])
@jwt_required()
def admin_personal_payout():
    """
    Admin Personal Payout - Direct Mudrape API call
    NO wallet balance check or deduction
    """
    try:
        data = request.json
        admin_id = get_jwt_identity()
        
        # Validate required fields
        required_fields = ['bank_id', 'amount', 'tpin', 'pg_partner', 'mobile_number', 'email_address']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        # Validate mobile number
        mobile_number = str(data['mobile_number']).strip()
        if not mobile_number or len(mobile_number) != 10 or not mobile_number.isdigit():
            return jsonify({'success': False, 'message': 'Invalid mobile number. Must be 10 digits'}), 400
        
        # Validate email address
        email_address = str(data['email_address']).strip()
        if not email_address or '@' not in email_address:
            return jsonify({'success': False, 'message': 'Invalid email address'}), 400
        
        # Validate amount
        try:
            amount = float(data['amount'])
            if amount <= 0:
                return jsonify({'success': False, 'message': 'Amount must be greater than 0'}), 400
            
            # Check payout limit - maximum 500,000 per transaction
            if amount > 500000:
                return jsonify({'success': False, 'message': 'Transaction out of limit. Maximum payout amount is ₹5,00,000 per transaction'}), 400
                
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid amount format'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Verify TPIN
                cursor.execute("SELECT pin_hash FROM admin_users WHERE admin_id = %s", (admin_id,))
                admin = cursor.fetchone()
                
                if not admin or not admin['pin_hash']:
                    return jsonify({'success': False, 'message': 'TPIN not set'}), 400
                
                if not bcrypt.checkpw(data['tpin'].encode('utf-8'), admin['pin_hash'].encode('utf-8')):
                    return jsonify({'success': False, 'message': 'Invalid TPIN'}), 400
                
                # Get bank details
                cursor.execute("""
                    SELECT * FROM admin_banks 
                    WHERE id = %s AND admin_id = %s AND is_active = TRUE
                """, (data['bank_id'], admin_id))
                bank = cursor.fetchone()
                
                if not bank:
                    return jsonify({'success': False, 'message': 'Bank not found'}), 404
                
                # NO WALLET BALANCE CHECK - Admin personal payouts go directly through gateway
                
                # Create payout transaction record with NULL merchant_id (admin payouts don't belong to any merchant)
                # Generate gateway-specific txn_id prefix for easy identification
                pg_partner_upper = data['pg_partner'].upper()
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                random_suffix = uuid.uuid4().hex[:6].upper()
                
                # Reference ID remains ADMIN for admin payouts
                reference_id = f"ADMIN{timestamp}{random_suffix}"
                
                # Gateway-specific TXN_ID for easy identification
                if pg_partner_upper == 'ROCKYPAYZ':
                    txn_id = f"RCK_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper in ['PES', 'SECTORPE']:
                    txn_id = f"PES_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper in ['MAXPE', 'NODEPAY']:
                    txn_id = f"MAXPE_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'NEXTPAY':
                    txn_id = f"NEXTPAY_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'NEXTPAY':
                    txn_id = f"MAXPE_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'NEXTPAY':
                    txn_id = f"NEXTPAY_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'CLOCKSPAY':
                    txn_id = f"CLK_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'CINORIGHT':
                    txn_id = f"CINO_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'ALOPNA':
                    txn_id = f"ALOPNA_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'OQPAY':
                    txn_id = f"OQP_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'RISEXPAY':
                    txn_id = f"TXN{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'TPIPAY':
                    txn_id = f"TPI_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'MAKEMYPAYMENT':
                    txn_id = f"MMP_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'ORO':
                    txn_id = f"ORO_{uuid.uuid4().hex[:12].upper()}"
                else:
                    txn_id = f"TXN{uuid.uuid4().hex[:12].upper()}"
                
                # Auto-generate order_id for admin payouts
                order_id = f"ORD{timestamp}{uuid.uuid4().hex[:8].upper()}"
                
                cursor.execute("""
                    INSERT INTO payout_transactions 
                    (txn_id, reference_id, order_id, merchant_id, admin_id, amount, charge_amount, charge_type, net_amount,
                     bene_name, bene_bank, account_no, ifsc_code, payment_type, pg_partner, status, created_at)
                    VALUES (%s, %s, %s, NULL, %s, %s, 0.00, 'FIXED', %s, %s, %s, %s, %s, 'IMPS', %s, 'INITIATED', NOW())
                """, (txn_id, reference_id, order_id, admin_id, data['amount'], data['amount'],
                      bank['account_holder_name'], bank['bank_name'],
                      bank['account_number'], bank['ifsc_code'], data['pg_partner']))
                
                conn.commit()
                
                # Process payout based on pg_partner (already set above)
                
                if pg_partner_upper == 'PAYU':
                    # Use PayU for payout - Direct API call, NO wallet deduction
                    transfer_data = [{
                        'bene_name': bank['account_holder_name'],
                        'bene_email': email_address,
                        'bene_mobile': mobile_number,
                        'purpose': 'Admin Personal Payout',
                        'amount': float(data['amount']),
                        'batch_id': '',
                        'reference_id': reference_id,
                        'payment_type': 'IMPS',
                        'account_no': bank['account_number'],
                        'ifsc_code': bank['ifsc_code'],
                        'retry': False
                    }]
                    
                    result = payu_payout_svc.initiate_transfer(transfer_data)
                    
                    if result['success']:
                        # NO WALLET DEDUCTION - Admin personal payouts go directly through PayU
                        # Update status to QUEUED
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'QUEUED', updated_at = NOW()
                            WHERE reference_id = %s
                        """, (reference_id,))
                        conn.commit()
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id
                        }), 200
                    else:
                        # Update status to FAILED
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, updated_at = NOW()
                            WHERE reference_id = %s
                        """, (result.get('error', 'Payout failed'), reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': result.get('error', 'Payout failed')
                        }), 400
                
                elif pg_partner_upper == 'MUDRAPE':
                    # Use Mudrape for payout (IMPS) - Direct API call, NO wallet deduction
                    result = mudrape_service.call_imps_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        client_txn_id=reference_id,
                        amount=float(data['amount']),
                        beneficiary_name=bank['account_holder_name'],
                        mobile=mobile_number,
                        email=email_address
                    )
                    
                    if result['success']:
                        # NO WALLET DEDUCTION - Admin personal payouts go directly through Mudrape
                        # Update transaction with Mudrape response
                        status = result.get('status', 'INITIATED')
                        mudrape_txn_id = result.get('mudrape_txn_id', '')
                        
                        print(f"DEBUG: result dict = {result}")
                        print(f"DEBUG: status variable = '{status}' (type: {type(status)})")
                        print(f"DEBUG: mudrape_txn_id = '{mudrape_txn_id}'")
                        print(f"Mudrape payout initiated - Status: {status}, TxnID: {mudrape_txn_id}")
                        
                        # Set completed_at if status is final
                        if status in ['SUCCESS', 'FAILED']:
                            update_query = """
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE reference_id = %s
                            """
                            update_params = (status, mudrape_txn_id, reference_id)
                            print(f"DEBUG: Executing UPDATE with status='{status}', pg_txn_id='{mudrape_txn_id}', ref='{reference_id}'")
                            cursor.execute(update_query, update_params)
                        else:
                            update_query = """
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, updated_at = NOW()
                                WHERE reference_id = %s
                            """
                            update_params = (status, mudrape_txn_id, reference_id)
                            print(f"DEBUG: Executing UPDATE with status='{status}', pg_txn_id='{mudrape_txn_id}', ref='{reference_id}'")
                            cursor.execute(update_query, update_params)
                        
                        conn.commit()
                        print(f"DEBUG: UPDATE committed, rows affected: {cursor.rowcount}")
                        
                        # If status is still INITIATED (pending), check status from Mudrape API
                        if status == 'INITIATED':
                            print(f"Checking status from Mudrape for reference_id: {reference_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = mudrape_service.check_payout_status(reference_id)
                            print(f"DEBUG: status_result = {status_result}")
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                utr = status_result.get('utr')
                                completed_at_from_api = status_result.get('completed_at')
                                
                                print(f"Mudrape status check result - Status: {updated_status}, UTR: {utr}, Completed: {completed_at_from_api}")
                                print(f"DEBUG: About to UPDATE with status='{updated_status}'")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    if completed_at_from_api:
                                        # Use the timestamp from Mudrape
                                        update_query2 = """
                                            UPDATE payout_transactions 
                                            SET status = %s, utr = %s, completed_at = %s, updated_at = NOW()
                                            WHERE reference_id = %s
                                        """
                                        update_params2 = (updated_status, utr, completed_at_from_api, reference_id)
                                    else:
                                        # Fallback to NOW() if no timestamp from Mudrape
                                        update_query2 = """
                                            UPDATE payout_transactions 
                                            SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                            WHERE reference_id = %s
                                        """
                                        update_params2 = (updated_status, utr, reference_id)
                                    print(f"DEBUG: Executing final UPDATE: status='{updated_status}', utr='{utr}', completed_at='{completed_at_from_api}', ref='{reference_id}'")
                                    cursor.execute(update_query2, update_params2)
                                else:
                                    update_query2 = """
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE reference_id = %s
                                    """
                                    update_params2 = (updated_status, utr, reference_id)
                                    print(f"DEBUG: Executing final UPDATE: status='{updated_status}', utr='{utr}', ref='{reference_id}'")
                                    cursor.execute(update_query2, update_params2)
                                
                                conn.commit()
                                print(f"DEBUG: Final UPDATE committed, rows affected: {cursor.rowcount}")
                                status = updated_status
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': status
                        }), 200
                    else:
                        # Update status to FAILED
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (result.get('message', 'Payout failed'), reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': result.get('message', 'Payout failed')
                        }), 400
                
                elif pg_partner_upper == 'INSTANTPESA':
                    # Use InstantPesa for payout (IMPS/NEFT/RTGS) - Direct API call, NO wallet deduction
                    payout_data = {
                        'amount': float(data['amount']),
                        'account_number': bank['account_number'],
                        'ifsc_code': bank['ifsc_code'],
                        'bank_name': bank['bank_name'],
                        'beneficiary_name': bank['account_holder_name'],
                        'email': email_address,
                        'mobile': mobile_number,
                        'transaction_mode': data.get('transaction_mode', 'IMPS')
                    }
                    
                    result = instantpesa_svc.create_imps_payout(
                        merchant_id=None,  # No merchant for admin payouts
                        payout_data=payout_data
                    )
                    
                    if result['success']:
                        # NO WALLET DEDUCTION - Admin personal payouts go directly through InstantPesa
                        # Update transaction with InstantPesa response
                        status = result.get('data', {}).get('status', 'INITIATED')
                        instantpesa_txn_id = result.get('data', {}).get('transaction_id', '')
                        
                        print(f"InstantPesa payout initiated - Status: {status}, TxnID: {instantpesa_txn_id}")
                        
                        # Update transaction
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = %s, pg_txn_id = %s, updated_at = NOW()
                            WHERE reference_id = %s
                        """, (status, instantpesa_txn_id, reference_id))
                        
                        conn.commit()
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': status
                        }), 200
                    else:
                        # Update status to FAILED
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (result.get('message', 'Payout failed'), reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': result.get('message', 'Payout failed')
                        }), 400
                
                elif pg_partner_upper in ['PAYTOUCH', 'PAYTOUCH_TRUAXIS']:
                    # Use PayTouch for payout - Direct API call, NO wallet deduction
                    # PayTouch requirements: request_id=order_id, currency=INR, narration=Truaxis, payment_mode=IMPS, bank_branch=oooo
                    payout_data = {
                        'reference_id': reference_id,
                        'amount': float(data['amount']),
                        'bene_name': bank['account_holder_name'],
                        'bene_account': bank['account_number'],
                        'bene_ifsc': bank['ifsc_code'],
                        'bank_name': bank['bank_name']
                        # payment_mode, narration, bank_branch are hardcoded in service
                    }
                    
                    result = paytouch_service.initiate_payout(
                        merchant_id=None,  # No merchant for admin payouts
                        payout_data=payout_data,
                        admin_id=admin_id
                    )
                    
                    if result['success']:
                        # NO WALLET DEDUCTION - Admin personal payouts go directly through PayTouch
                        print(f"PayTouch payout initiated - Status: {result.get('status')}, TxnID: {result.get('paytouch_txn_id')}")
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': result.get('status', 'QUEUED')
                        }), 200
                    else:
                        # Update status to FAILED
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (result.get('message', 'Payout failed'), reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': result.get('message', 'Payout failed')
                        }), 400
                
                elif pg_partner_upper in ['PAYTOUCH2', 'PAYTOUCH_GROSMART']:
                    # Use PayTouch2 for payout - Direct API call, NO wallet deduction
                    # PayTouch2 requirements: request_id=order_id, currency=INR, narration=Truaxis, payment_mode=IMPS, bank_branch=oooo
                    payout_data = {
                        'reference_id': reference_id,
                        'amount': float(data['amount']),
                        'bene_name': bank['account_holder_name'],
                        'bene_account': bank['account_number'],
                        'bene_ifsc': bank['ifsc_code'],
                        'bank_name': bank['bank_name']
                        # payment_mode, narration, bank_branch are hardcoded in service
                    }
                    
                    result = paytouch2_service.initiate_payout(
                        merchant_id=None,  # No merchant for admin payouts
                        payout_data=payout_data,
                        admin_id=admin_id
                    )
                    
                    if result['success']:
                        # NO WALLET DEDUCTION - Admin personal payouts go directly through PayTouch2
                        print(f"PayTouch2 payout initiated - Status: {result.get('status')}, TxnID: {result.get('paytouch2_txn_id')}")
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': result.get('status', 'QUEUED')
                        }), 200
                    else:
                        # Update status to FAILED
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (result.get('message', 'Payout failed'), reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': result.get('message', 'Payout failed')
                        }), 400
                
                elif pg_partner_upper == 'CINORIGHT':
                    # Use Cinoright for payout (IMPS) - Direct API call, NO wallet deduction
                    result = cinoright_service.call_imps_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        reference_id=reference_id,
                        amount=float(data['amount']),
                        beneficiary_name=bank['account_holder_name'],
                        email=email_address,
                        phone=mobile_number
                    )
                    
                    if result['success']:
                        # NO WALLET DEDUCTION - Admin personal payouts go directly through Cinoright
                        # Update transaction with Cinoright response
                        status = result.get('status', 'INITIATED')
                        cinoright_txn_id = result.get('cinoright_txn_id', '')
                        utr = result.get('utr')
                        
                        print(f"Cinoright payout initiated - Status: {status}, TxnID: {cinoright_txn_id}")
                        
                        # Set completed_at if status is final
                        if status in ['SUCCESS', 'FAILED']:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, cinoright_txn_id, utr, reference_id))
                        else:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, cinoright_txn_id, utr, reference_id))
                        
                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from Cinoright API
                        if status == 'INITIATED' and cinoright_txn_id:
                            print(f"Checking status from Cinoright for txn_id: {cinoright_txn_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = cinoright_service.check_payout_status(cinoright_txn_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"Cinoright status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE reference_id = %s
                                    """, (updated_status, updated_utr, reference_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE reference_id = %s
                                    """, (updated_status, updated_utr, reference_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': status
                        }), 200
                    else:
                        # Update status to FAILED
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (result.get('message', 'Payout failed'), reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': result.get('message', 'Payout failed')
                        }), 400
                
                elif pg_partner_upper in ['PES', 'SECTORPE']:
                    # Use SectorPe for payout (IMPS) - Direct API call, NO wallet deduction
                    result = sectorpe_payout_service.call_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        merchant_order_id=reference_id,
                        amount=float(data['amount']),
                        payee_name=bank['account_holder_name'],
                        email=email_address,
                        mobile=mobile_number,
                        mode='IMPS'
                    )
                    
                    if result['success']:
                        # NO WALLET DEDUCTION
                        status = result.get('status', 'INITIATED')
                        
                        print(f"SectorPe payout initiated - Status: {status}, Merchant Order ID: {reference_id}")
                        
                        if status in ['SUCCESS', 'FAILED']:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, reference_id))
                        else:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, reference_id))
                        
                        conn.commit()
                        
                        # Check status if INITIATED
                        if status == 'INITIATED':
                            print(f"Checking status from SectorPe for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)
                            
                            status_result = sectorpe_payout_service.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"SectorPe status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE reference_id = %s
                                    """, (updated_status, updated_utr, reference_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE reference_id = %s
                                    """, (updated_status, updated_utr, reference_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': status
                        }), 200
                    else:
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (result.get('message', 'Payout failed'), reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': result.get('message', 'Payout failed')
                        }), 400
                
                elif pg_partner_upper in ['MAXPE', 'NODEPAY']:
                    # Use MaxPe or NodePay for payout (IMPS) - Direct API call, NO wallet deduction
                    # Get the appropriate service based on pg_partner
                    payout_service_instance = get_payout_service(pg_partner_upper)
                    
                    result = payout_service_instance.call_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        merchant_order_id=reference_id,
                        amount=float(data['amount']),
                        payee_name=bank['account_holder_name'],
                        email=email_address,
                        mobile=mobile_number
                    )
                    
                    if result['success']:
                        # NO WALLET DEDUCTION - Admin personal payouts go directly through MaxPe/NodePay
                        # Update transaction with response
                        status = result.get('status', 'INITIATED')
                        
                        print(f"{pg_partner_upper} payout initiated - Status: {status}, Merchant Order ID: {reference_id}")
                        
                        # Set completed_at if status is final
                        if status in ['SUCCESS', 'FAILED']:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, reference_id))
                        else:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, reference_id))
                        
                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from API
                        if status == 'INITIATED':
                            print(f"Checking status from {pg_partner_upper} for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = payout_service_instance.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"{pg_partner_upper} status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE reference_id = %s
                                    """, (updated_status, updated_utr, reference_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE reference_id = %s
                                    """, (updated_status, updated_utr, reference_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': status
                        }), 200
                    else:
                        # Update status to FAILED
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (result.get('message', 'Payout failed'), reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': result.get('message', 'Payout failed')
                        }), 400
                
                elif pg_partner_upper == 'NEXTPAY':
                    # Use Nextpay for payout (IMPS) - Direct API call, NO wallet deduction
                    # Get the appropriate service based on pg_partner
                    payout_service_instance = nextpay_payout_service
                    
                    result = payout_service_instance.call_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        merchant_order_id=reference_id,
                        amount=float(data['amount']),
                        payee_name=bank['account_holder_name'],
                        email=email_address,
                        mobile=mobile_number
                    )
                    
                    if result['success']:
                        # NO WALLET DEDUCTION - Admin personal payouts go directly through MaxPe/NodePay
                        # Update transaction with response
                        status = result.get('status', 'INITIATED')
                        
                        print(f"{pg_partner_upper} payout initiated - Status: {status}, Merchant Order ID: {reference_id}")
                        
                        # Set completed_at if status is final
                        if status in ['SUCCESS', 'FAILED']:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, reference_id))
                        else:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, reference_id))
                        
                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from API
                        if status == 'INITIATED':
                            print(f"Checking status from {pg_partner_upper} for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = payout_service_instance.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"{pg_partner_upper} status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE reference_id = %s
                                    """, (updated_status, updated_utr, reference_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE reference_id = %s
                                    """, (updated_status, updated_utr, reference_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': status
                        }), 200
                    else:
                        # Update status to FAILED
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (result.get('message', 'Payout failed'), reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': result.get('message', 'Payout failed')
                        }), 400
                
                elif pg_partner_upper == 'TPIPAY':
                    # Use Tpipay for payout (IMPS/NEFT) - Direct API call, NO wallet deduction
                    result = tpipay_payout_service.call_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        merchant_order_id=reference_id,
                        amount=float(data['amount']),
                        payee_name=bank['account_holder_name'],
                        email=email_address,
                        mobile=mobile_number,
                        channel_id='2'  # 2 = IMPS
                    )
                    
                    if result['success']:
                        # NO WALLET DEDUCTION - Admin personal payouts go directly through Tpipay
                        status = result.get('status', 'INITIATED')
                        payid = result.get('payid', '')
                        utr = result.get('utr', '')
                        
                        print(f"Tpipay payout initiated - Status: {status}, Merchant Order ID: {reference_id}, PayID: {payid}")
                        
                        if status in ['SUCCESS', 'FAILED']:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, payid, utr, reference_id))
                        else:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, payid, utr, reference_id))
                        
                        conn.commit()
                        # Note: Tpipay does not have a status-check endpoint.
                        # Final status will be delivered via callback (webhook).
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': status
                        }), 200
                    else:
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (result.get('message', 'Payout failed'), reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': result.get('message', 'Payout failed')
                        }), 400
                
                elif pg_partner_upper == 'MAKEMYPAYMENT':
                    result = makemypayment_payout_service.initiate_single_payout(
                        merchant_reference_id=reference_id,
                        account_holder=bank['account_holder_name'],
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        mobile=mobile_number,
                        amount=str(float(data['amount'])),
                        mode='imps',
                        purpose='Payment',
                        email=email_address
                    )
                    
                    if result['success']:
                        status = result.get('status', 'INITIATED')
                        mmp_txn_id = result.get('transaction_id', '')
                        
                        print(f"MakeMyPayment payout initiated - Status: {status}, TxnID: {mmp_txn_id}")
                        
                        if status in ['SUCCESS', 'FAILED']:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, mmp_txn_id, reference_id))
                        else:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, mmp_txn_id, reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': status
                        }), 200
                    else:
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (result.get('message', 'Payout failed'), reference_id))
                        conn.commit()
                        return jsonify({'success': False, 'message': result.get('message', 'Payout failed')}), 400
                
                elif pg_partner_upper == 'CLOCKSPAY':
                    # Use ClocksPay for payout (IMPS) - Direct API call, NO wallet deduction
                    result = clockspay_payout_service.call_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        merchant_order_id=reference_id,
                        amount=float(data['amount']),
                        payee_name=bank['account_holder_name'],
                        mobile=mobile_number,
                        mode='IMPS'
                    )
                    
                    if result['success']:
                        # NO WALLET DEDUCTION - Admin personal payouts go directly through ClocksPay
                        # Update transaction with response
                        status = result.get('status', 'INITIATED')
                        
                        print(f"ClocksPay payout initiated - Status: {status}, Merchant Order ID: {reference_id}")
                        
                        # Set completed_at if status is final
                        if status in ['SUCCESS', 'FAILED']:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, reference_id))
                        else:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, reference_id))
                        
                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from API
                        if status == 'INITIATED':
                            print(f"Checking status from ClocksPay for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = clockspay_payout_service.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"ClocksPay status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE reference_id = %s
                                    """, (updated_status, updated_utr, reference_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE reference_id = %s
                                    """, (updated_status, updated_utr, reference_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': status
                        }), 200
                    else:
                        # Update status to FAILED
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (result.get('message', 'Payout failed'), reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': result.get('message', 'Payout failed')
                        }), 400
                
                elif pg_partner_upper == 'ROCKYPAYZ':
                    # Use RockyPayz for payout (IMPS) - Direct API call, NO wallet deduction
                    result = rockypayz_payout_service.call_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        merchant_order_id=reference_id,
                        amount=float(data['amount']),
                        payee_name=bank['account_holder_name'],
                        mobile=mobile_number,
                        remarks='Admin Personal Payout'
                    )
                    
                    if result['success']:
                        # NO WALLET DEDUCTION - Admin personal payouts go directly through RockyPayz
                        # Update transaction with response
                        status = result.get('status', 'INITIATED')
                        txn_id_resp = result.get('txn_id', '')
                        utr = result.get('utr', '')
                        
                        print(f"RockyPayz payout initiated - Status: {status}, TXN ID: {txn_id_resp}, Merchant Order ID: {reference_id}")
                        
                        # Set completed_at if status is final
                        if status in ['SUCCESS', 'FAILED']:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, txn_id_resp, utr, reference_id))
                        else:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, txn_id_resp, utr, reference_id))
                        
                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from API
                        if status == 'INITIATED' and txn_id_resp:
                            print(f"Checking status from RockyPayz for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = rockypayz_payout_service.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"RockyPayz status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE reference_id = %s
                                    """, (updated_status, updated_utr, reference_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE reference_id = %s
                                    """, (updated_status, updated_utr, reference_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': status
                        }), 200
                    else:
                        # Update status to FAILED
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (result.get('message', 'Payout failed'), reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': result.get('message', 'Payout failed')
                        }), 400
                
                elif pg_partner_upper == 'ALOPNA':
                    # Use Alopna for payout (IMPS) - Direct API call, NO wallet deduction
                    result = alopna_service.call_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        merchant_order_id=reference_id,
                        amount=float(data['amount']),
                        payee_name=bank['account_holder_name'],
                        email=email_address,
                        mobile=mobile_number,
                        mode='IMPS'
                    )
                    
                    if result['success']:
                        status = result.get('status', 'INITIATED')
                        pg_txn_id_resp = result.get('alopna_txn_id', '')
                        utr = result.get('utr', '')
                        
                        if status in ['SUCCESS', 'FAILED']:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, pg_txn_id_resp, utr, reference_id))
                        else:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, pg_txn_id_resp, utr, reference_id))
                        
                        conn.commit()
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': status
                        }), 200
                    else:
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (result.get('message', 'Payout failed'), reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': result.get('message', 'Payout failed')
                        }), 400
                
                elif pg_partner_upper == 'RISEXPAY':
                    # Use Risexpay for payout (IMPS)
                    result = risexpay_payout_service.call_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        merchant_order_id=reference_id,
                        amount=float(data['amount']),
                        payee_name=bank['account_holder_name'],
                        email=email_address,
                        mobile=mobile_number,
                        mode='IMPS'
                    )

                    if result['success']:
                        status = result.get('status', 'QUEUED')
                        pg_txn_id_resp = result.get('pg_txn_id', '')
                        utr = result.get('utr', '')
                        print(f"Risexpay payout initiated - Status: {status}, PG Txn ID: {pg_txn_id_resp}, Merchant Order ID: {reference_id}")
                    else:
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'error': result.get('message')
                        }), 400

                elif pg_partner_upper == 'ORO':
                    # Use ORO for payout
                    oro_result = oro_payout_service.call_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        merchant_order_id=reference_id,
                        amount=data['amount'],
                        payee_name=bank['account_holder_name'],
                        email=email_address,
                        mobile=mobile_number
                    )
                    
                    if oro_result['success']:
                        status = oro_result.get('status', 'INITIATED')
                        pg_txn_id_resp = oro_result.get('pg_txn_id', '')
                        utr = oro_result.get('utr', '')
                        
                        print(f"ORO payout initiated - Status: {status}, TxnID: {pg_txn_id_resp}")
                        
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                            WHERE reference_id = %s
                        """, (status, pg_txn_id_resp, utr, reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': status
                        }), 200
                    else:
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (oro_result.get('message', 'ORO payout failed'), reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': oro_result.get('message', 'Payout failed')
                        }), 400

                elif pg_partner_upper == 'OQPAY':
                    # Use OQPay for payout (IMPS) - Direct API call, NO wallet deduction
                    result = oqpay_payout_service.call_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        merchant_order_id=reference_id,
                        amount=float(data['amount']),
                        payee_name=bank['account_holder_name'],
                        email=email_address,
                        mobile=mobile_number,
                        mode='IMPS'
                    )
                    
                    if result['success']:
                        # NO WALLET DEDUCTION - Admin personal payouts go directly through OQPay
                        # Update transaction with response
                        status = result.get('status', 'INITIATED')
                        pg_txn_id_resp = result.get('pg_txn_id', '')
                        utr = result.get('utr', '')
                        
                        print(f"OQPay payout initiated - Status: {status}, PG Txn ID: {pg_txn_id_resp}, Merchant Order ID: {reference_id}")
                        
                        # Set completed_at if status is final
                        if status in ['SUCCESS', 'FAILED']:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, pg_txn_id_resp, utr, reference_id))
                        else:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, pg_txn_id_resp, utr, reference_id))
                        
                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from API
                        if status == 'INITIATED':
                            print(f"Checking status from OQPay for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = oqpay_payout_service.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"OQPay status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE reference_id = %s
                                    """, (updated_status, updated_utr, reference_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE reference_id = %s
                                    """, (updated_status, updated_utr, reference_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': status
                        }), 200
                    else:
                        # Update status to FAILED
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (result.get('message', 'Payout failed'), reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': result.get('message', 'Payout failed')
                        }), 400
                
                elif pg_partner_upper == 'RISEXPAY':
                    # Use Risexpay for payout (IMPS) - Direct API call, NO wallet deduction
                    result = risexpay_payout_service.call_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        merchant_order_id=reference_id,
                        amount=float(data['amount']),
                        payee_name=bank['account_holder_name'],
                        email=email_address,
                        mobile=mobile_number,
                        mode='IMPS'
                    )

                    if result['success']:
                        # NO WALLET DEDUCTION - Admin personal payouts go directly through Risexpay
                        status = result.get('status', 'INITIATED')
                        pg_txn_id_resp = result.get('pg_txn_id', '')
                        utr = result.get('utr', '')

                        print(f"Risexpay payout initiated - Status: {status}, PG TXN: {pg_txn_id_resp}, Ref: {reference_id}")

                        # Set completed_at if status is final
                        if status in ['SUCCESS', 'FAILED']:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, pg_txn_id_resp, utr, reference_id))
                        else:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE reference_id = %s
                            """, (status, pg_txn_id_resp, utr, reference_id))

                        conn.commit()

                        # If still INITIATED, do a quick status check
                        if status == 'INITIATED' and pg_txn_id_resp:
                            print(f"Checking status from Risexpay for reference_id: {reference_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking

                            status_result = risexpay_payout_service.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr', '')

                                print(f"Risexpay status check result - Status: {updated_status}, UTR: {updated_utr}")

                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE reference_id = %s
                                    """, (updated_status, updated_utr, reference_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE reference_id = %s
                                    """, (updated_status, updated_utr, reference_id))

                                conn.commit()
                                status = updated_status

                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': status
                        }), 200
                    else:
                        # Update status to FAILED
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (result.get('message', 'Payout failed'), reference_id))
                        conn.commit()

                        return jsonify({
                            'success': False,
                            'message': result.get('message', 'Payout failed')
                        }), 400

                else:
                    return jsonify({
                        'success': False,
                        'message': f'Payment gateway {data["pg_partner"]} not supported'
                    }), 400
                    
        finally:
            conn.close()
                
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# Fund Request - Client creates request
@payout_bp.route('/client/fund-request', methods=['POST'])
@jwt_required()
def create_fund_request():
    try:
        data = request.json
        merchant_id = get_jwt_identity()
        
        if 'amount' not in data or float(data['amount']) <= 0:
            return jsonify({'success': False, 'message': 'Valid amount is required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        with conn.cursor() as cursor:
            request_id = f"FR{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6]}"
            
            cursor.execute("""
                INSERT INTO fund_requests (request_id, merchant_id, amount, request_type, remarks)
                VALUES (%s, %s, %s, %s, %s)
            """, (request_id, merchant_id, data['amount'], 'SETTLEMENT', data.get('remarks', '')))
            
            conn.commit()
        
        conn.close()
        return jsonify({'success': True, 'message': 'Fund request submitted', 'request_id': request_id}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Get Fund Requests - Admin view
@payout_bp.route('/admin/fund-requests', methods=['GET'])
@jwt_required()
def get_fund_requests():
    try:
        status = request.args.get('status', 'PENDING')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT fr.*, m.full_name, m.mobile, m.email
                FROM fund_requests fr
                JOIN merchants m ON fr.merchant_id = m.merchant_id
                WHERE fr.status = %s
                ORDER BY fr.requested_at DESC
            """, (status,))
            
            requests_list = cursor.fetchall()
        
        conn.close()
        return jsonify({'success': True, 'data': requests_list}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Approve/Reject Fund Request
@payout_bp.route('/admin/fund-request/<request_id>', methods=['PUT'])
@jwt_required()
def process_fund_request(request_id):
    conn = None
    try:
        data = request.json
        admin_id = get_jwt_identity()
        action = data.get('action')  # 'APPROVE' or 'REJECT'
        
        if action not in ['APPROVE', 'REJECT']:
            return jsonify({'success': False, 'message': 'Invalid action'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        with conn.cursor() as cursor:
            # Get fund request
            cursor.execute("""
                SELECT * FROM fund_requests WHERE request_id = %s AND status = 'PENDING'
            """, (request_id,))
            fund_request = cursor.fetchone()
            
            if not fund_request:
                conn.close()
                return jsonify({'success': False, 'message': 'Request not found'}), 404
            
            if action == 'APPROVE':
                # CRITICAL FIX: Pass the connection to ensure atomic transaction
                # This prevents admin wallet debit if merchant credit fails
                admin_debit = wallet_svc.debit_admin_wallet(
                    admin_id,
                    float(fund_request['amount']),
                    f"Fund request approved for {fund_request['merchant_id']} - {request_id}",
                    reference_id=request_id,
                    conn=conn  # Pass existing connection for atomic transaction
                )
                
                if not admin_debit['success']:
                    conn.close()
                    return jsonify(admin_debit), 400
                
                # CRITICAL FIX: Credit SETTLED wallet, not unsettled wallet
                # Fund requests/topups should go to settled balance (ready for payout)
                # NOT to unsettled balance (which is for PayIN that needs settlement)
                
                # Get current settled balance
                cursor.execute("""
                    SELECT settled_balance FROM merchant_wallet WHERE merchant_id = %s
                """, (fund_request['merchant_id'],))
                wallet = cursor.fetchone()
                
                if not wallet:
                    # Create wallet if doesn't exist
                    cursor.execute("""
                        INSERT INTO merchant_wallet (merchant_id, balance, settled_balance, unsettled_balance)
                        VALUES (%s, %s, %s, 0.00)
                    """, (fund_request['merchant_id'], fund_request['amount'], fund_request['amount']))
                    settled_before = 0.00
                else:
                    settled_before = float(wallet['settled_balance'])
                
                settled_after = settled_before + float(fund_request['amount'])
                
                # Update settled balance
                cursor.execute("""
                    UPDATE merchant_wallet 
                    SET settled_balance = %s, balance = %s, last_updated = NOW()
                    WHERE merchant_id = %s
                """, (settled_after, settled_after, fund_request['merchant_id']))
                
                # Record transaction in merchant_wallet_transactions
                txn_id = f"MWT{datetime.now().strftime('%Y%m%d%H%M%S')}"
                cursor.execute("""
                    INSERT INTO merchant_wallet_transactions 
                    (merchant_id, txn_id, txn_type, amount, balance_before, balance_after, description, reference_id)
                    VALUES (%s, %s, 'CREDIT', %s, %s, %s, %s, %s)
                """, (
                    fund_request['merchant_id'], txn_id, fund_request['amount'],
                    settled_before, settled_after,
                    f"Fund topup approved - {request_id}",
                    request_id
                ))
            
            # Update request status
            cursor.execute("""
                UPDATE fund_requests 
                SET status = %s, processed_at = NOW(), processed_by = %s, remarks = %s
                WHERE request_id = %s
            """, ('APPROVED' if action == 'APPROVE' else 'REJECTED', admin_id, data.get('remarks', ''), request_id))
            
            conn.commit()
        
        conn.close()
        return jsonify({'success': True, 'message': f'Request {action.lower()}d successfully'}), 200
        
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return jsonify({'success': False, 'message': str(e)}), 500


# Admin Topup Fund
@payout_bp.route('/admin/topup-fund', methods=['POST'])
@jwt_required()
def admin_topup_fund():
    try:
        data = request.json
        admin_id = get_jwt_identity()
        
        required_fields = ['merchant_id', 'amount', 'tpin']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Verify admin TPIN
                cursor.execute("SELECT pin_hash FROM admin_users WHERE admin_id = %s", (admin_id,))
                admin = cursor.fetchone()
                
                if not admin or not admin['pin_hash']:
                    conn.close()
                    return jsonify({'success': False, 'message': 'TPIN not set'}), 400
                
                if not bcrypt.checkpw(data['tpin'].encode('utf-8'), admin['pin_hash'].encode('utf-8')):
                    conn.close()
                    return jsonify({'success': False, 'message': 'Invalid TPIN'}), 400
                
                # Lock admin wallet row to prevent concurrent topups (race condition fix)
                cursor.execute("""
                    SELECT admin_id FROM admin_wallet 
                    WHERE admin_id = %s 
                    FOR UPDATE
                """, (admin_id,))
                
                # Check for duplicate topup in last minute (idempotency check)
                cursor.execute("""
                    SELECT COUNT(*) as count, MAX(processed_at) as last_topup
                    FROM fund_requests
                    WHERE merchant_id = %s 
                    AND amount = %s
                    AND processed_at >= DATE_SUB(NOW(), INTERVAL 1 MINUTE)
                    AND status = 'APPROVED'
                """, (data['merchant_id'], data['amount']))
                
                duplicate_check = cursor.fetchone()
                if duplicate_check and duplicate_check['count'] > 0:
                    conn.close()
                    return jsonify({
                        'success': False,
                        'message': f'Duplicate topup detected. Last topup of ₹{data["amount"]} was processed at {duplicate_check["last_topup"]}. Please wait before retrying.'
                    }), 400
                
                # Check available balance in admin wallet
                # Admin Wallet = PayIN + Fetch - Topups + Manual Adjustments
                # (Payouts are deducted from merchant wallets, not admin wallet)
                cursor.execute("""
                    SELECT COALESCE(SUM(amount), 0) as total_payin
                    FROM payin_transactions
                    WHERE status = 'SUCCESS'
                """)
                total_payin = float(cursor.fetchone()['total_payin'])
                
                # Get total approved fund requests (topups already given to merchants)
                cursor.execute("""
                    SELECT COALESCE(SUM(amount), 0) as total_topup
                    FROM fund_requests
                    WHERE status = 'APPROVED'
                """)
                total_topup = float(cursor.fetchone()['total_topup'])
                
                # Get total fetch from merchants (money returned to admin)
                cursor.execute("""
                    SELECT COALESCE(SUM(amount), 0) as total_fetch
                    FROM merchant_wallet_transactions
                    WHERE txn_type = 'DEBIT' 
                    AND description LIKE '%fetched by admin%'
                """)
                total_fetch = float(cursor.fetchone()['total_fetch'])
                
                # Get manual adjustments from admin_wallet_transactions
                cursor.execute("""
                    SELECT COALESCE(SUM(
                        CASE 
                            WHEN txn_type = 'CREDIT' THEN amount
                            WHEN txn_type = 'DEBIT' THEN -amount
                            ELSE 0
                        END
                    ), 0) as total_adjustments
                    FROM admin_wallet_transactions
                    WHERE description LIKE '%Manual balance%'
                    OR description LIKE '%Balance adjustment%'
                    OR description LIKE '%Initial capital%'
                """)
                total_adjustments = float(cursor.fetchone()['total_adjustments'])
                
                # Admin available balance = PayIN + Fetch - Topups + Manual Adjustments
                # Topups transfer money FROM admin TO merchants
                # Payouts are paid from merchant wallets, not admin wallet
                available_balance = total_payin + total_fetch - total_topup + total_adjustments
                
                # Log for debugging
                print(f"=== TOPUP VALIDATION ===")
                print(f"Merchant: {data['merchant_id']}")
                print(f"Amount: {data['amount']}")
                print(f"Available Balance: {available_balance}")
                print(f"PayIN: {total_payin}, Fetch: {total_fetch}, Topups: {total_topup}, Adjustments: {total_adjustments}")
                
                if float(data['amount']) > available_balance:
                    print(f"❌ VALIDATION FAILED: {data['amount']} > {available_balance}")
                    conn.close()
                    return jsonify({
                        'success': False, 
                        'message': f'Insufficient balance in wallet, remaining balance in wallet: ₹{available_balance:.2f}'
                    }), 400
                
                print(f"✓ VALIDATION PASSED: {data['amount']} <= {available_balance}")
                
                # Create fund request entry (auto-approved by admin)
                request_id = f"FR{uuid.uuid4().hex[:12].upper()}"
                remarks = data.get('remarks', 'Manual topup by admin')
                
                cursor.execute("""
                    INSERT INTO fund_requests 
                    (request_id, merchant_id, amount, status, remarks, processed_by, processed_at)
                    VALUES (%s, %s, %s, 'APPROVED', %s, %s, NOW())
                """, (request_id, data['merchant_id'], data['amount'], remarks, admin_id))
                
                # CRITICAL FIX: Record admin wallet debit in same transaction
                # Calculate balance for admin wallet transaction
                balance_before = available_balance
                balance_after = available_balance - float(data['amount'])
                
                awt_id = f"AWT{datetime.now().strftime('%Y%m%d%H%M%S')}"
                cursor.execute("""
                    INSERT INTO admin_wallet_transactions 
                    (admin_id, txn_id, txn_type, amount, balance_before, balance_after, description, reference_id)
                    VALUES (%s, %s, 'DEBIT', %s, %s, %s, %s, %s)
                """, (admin_id, awt_id, data['amount'], balance_before, balance_after,
                      f"Manual topup for {data['merchant_id']} - {request_id}", request_id))
                
                # CRITICAL FIX: Credit merchant's SETTLED wallet in same transaction
                # Get current settled balance
                cursor.execute("""
                    SELECT settled_balance FROM merchant_wallet WHERE merchant_id = %s
                """, (data['merchant_id'],))
                wallet = cursor.fetchone()
                
                if not wallet:
                    # Create wallet if doesn't exist
                    cursor.execute("""
                        INSERT INTO merchant_wallet (merchant_id, balance, settled_balance, unsettled_balance)
                        VALUES (%s, %s, %s, 0.00)
                    """, (data['merchant_id'], data['amount'], data['amount']))
                    settled_before = 0.00
                else:
                    settled_before = float(wallet['settled_balance'])
                
                settled_after = settled_before + float(data['amount'])
                
                # Update settled balance
                cursor.execute("""
                    UPDATE merchant_wallet 
                    SET settled_balance = %s, balance = %s, last_updated = NOW()
                    WHERE merchant_id = %s
                """, (settled_after, settled_after, data['merchant_id']))
                
                # Record transaction in merchant_wallet_transactions
                txn_id = f"MWT{datetime.now().strftime('%Y%m%d%H%M%S')}"
                cursor.execute("""
                    INSERT INTO merchant_wallet_transactions 
                    (merchant_id, txn_id, txn_type, amount, balance_before, balance_after, description, reference_id)
                    VALUES (%s, %s, 'CREDIT', %s, %s, %s, %s, %s)
                """, (
                    data['merchant_id'], txn_id, data['amount'],
                    settled_before, settled_after,
                    f"Topup approved - {request_id}",
                    request_id
                ))
                
                print(f"✓ Credited merchant settled wallet: ₹{data['amount']}")
                
                conn.commit()
            
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Topup successful',
                'request_id': request_id
            }), 200
            
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            raise e
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Client Settle Fund (Disburse to bank)
@payout_bp.route('/client/settle-fund', methods=['POST'])
@jwt_required()
def client_settle_fund():
    try:
        data = request.json
        merchant_id = get_jwt_identity()
        
        # IP SECURITY CHECK - Validate merchant IP for settle fund operations
        from ip_security_routes import validate_merchant_ip
        is_valid, message = validate_merchant_ip(merchant_id, '/api/payout/client/settle-fund')
        if not is_valid:
            return jsonify({'success': False, 'message': message}), 403
        
        required_fields = ['bank_id', 'amount', 'tpin']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Verify merchant TPIN
                cursor.execute("SELECT pin_hash, scheme_id FROM merchants WHERE merchant_id = %s", (merchant_id,))
                merchant = cursor.fetchone()
                
                if not merchant or not merchant['pin_hash']:
                    conn.close()
                    return jsonify({'success': False, 'message': 'TPIN not set'}), 400
                
                if not bcrypt.checkpw(data['tpin'].encode('utf-8'), merchant['pin_hash'].encode('utf-8')):
                    conn.close()
                    return jsonify({'success': False, 'message': 'Invalid TPIN'}), 400
                
                # Get bank details
                cursor.execute("""
                    SELECT * FROM merchant_banks 
                    WHERE id = %s AND merchant_id = %s AND is_active = TRUE
                """, (data['bank_id'], merchant_id))
                bank = cursor.fetchone()
                
                if not bank:
                    conn.close()
                    return jsonify({'success': False, 'message': 'Bank not found'}), 404
                
                # Calculate payout charges based on merchant scheme
                charges = payout_svc.calculate_charges(
                    float(data['amount']),
                    merchant['scheme_id'],
                    'PAYOUT'
                )
                
                if not charges:
                    conn.close()
                    return jsonify({'success': False, 'message': 'Unable to calculate payout charges'}), 400
                
                # NEW LOGIC: User receives full amount, charges deducted from wallet
                # Amount to send to bank = requested amount (full amount)
                amount_to_bank = float(data['amount'])
                # Total deduction from wallet = amount + charges
                total_wallet_deduction = amount_to_bank + charges['charge_amount']
                
                if amount_to_bank <= 0:
                    conn.close()
                    return jsonify({'success': False, 'message': 'Invalid settlement amount'}), 400
                
                # Get settled balance from merchant_wallet (this is the withdrawable amount)
                cursor.execute("""
                    SELECT COALESCE(settled_balance, 0) as available_balance
                    FROM merchant_wallet
                    WHERE merchant_id = %s
                """, (merchant_id,))
                wallet_result = cursor.fetchone()
                available_balance = float(wallet_result['available_balance']) if wallet_result else 0.00
                
                # Check if settled balance is sufficient (amount + charges)
                if total_wallet_deduction > available_balance:
                    conn.close()
                    return jsonify({
                        'success': False, 
                        'message': f'Insufficient balance in wallet, remaining balance in wallet: ₹{available_balance:.2f}'
                    }), 400
                
                # Get PG partner from service routing for PAYOUT
                # First try to get merchant-specific routing
                cursor.execute("""
                    SELECT pg_partner FROM service_routing
                    WHERE service_type = 'PAYOUT' 
                    AND routing_type = 'SINGLE_USER'
                    AND merchant_id = %s
                    AND is_active = TRUE
                    ORDER BY priority ASC
                    LIMIT 1
                """, (merchant_id,))
                routing = cursor.fetchone()
                
                # If no merchant-specific routing, get ALL_USERS routing
                if not routing:
                    cursor.execute("""
                        SELECT pg_partner FROM service_routing
                        WHERE service_type = 'PAYOUT' 
                        AND routing_type = 'ALL_USERS'
                        AND is_active = TRUE
                        ORDER BY priority ASC
                        LIMIT 1
                    """)
                    routing = cursor.fetchone()
                
                if not routing:
                    conn.close()
                    return jsonify({'success': False, 'message': 'No payout gateway configured'}), 400
                
                pg_partner = routing['pg_partner']
                
                print(f"DEBUG: Merchant {merchant_id} payout - pg_partner from DB: '{pg_partner}'")
                
                # Create payout transaction record with charges
                # Store total_wallet_deduction as amount (what's deducted from wallet)
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                reference_id = f"SF{timestamp}{uuid.uuid4().hex[:6].upper()}"
                
                # Gateway-specific TXN_ID for easy identification
                pg_partner_upper = pg_partner.upper()
                if pg_partner_upper == 'ROCKYPAYZ':
                    txn_id = f"RCK_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper in ['PES', 'SECTORPE']:
                    txn_id = f"PES_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper in ['MAXPE', 'NODEPAY']:
                    txn_id = f"MAXPE_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'NEXTPAY':
                    txn_id = f"NEXTPAY_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'NEXTPAY':
                    txn_id = f"MAXPE_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'NEXTPAY':
                    txn_id = f"NEXTPAY_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'TPIPAY':
                    txn_id = f"TPI_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'MAKEMYPAYMENT':
                    txn_id = f"MMP_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'CLOCKSPAY':
                    txn_id = f"CLK_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'CINORIGHT':
                    txn_id = f"CINO_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'OQPAY':
                    txn_id = f"OQP_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'RISEXPAY':
                    txn_id = f"TXN{uuid.uuid4().hex[:12].upper()}"
                else:
                    txn_id = f"TXN{uuid.uuid4().hex[:12].upper()}"
                
                order_id = f"SF{timestamp}{uuid.uuid4().hex[:8].upper()}"
                
                # DO NOT debit wallet yet - only debit when payout is SUCCESS
                cursor.execute("""
                    INSERT INTO payout_transactions 
                    (txn_id, reference_id, order_id, merchant_id, amount, charge_amount, charge_type, 
                     net_amount, bene_name, bene_bank, account_no, ifsc_code, 
                     pg_partner, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING', NOW())
                """, (txn_id, reference_id, order_id, merchant_id, total_wallet_deduction, 
                      charges['charge_amount'], charges['charge_type'], amount_to_bank,
                      bank['account_holder_name'], bank['bank_name'], 
                      bank['account_number'], bank['ifsc_code'], pg_partner))
                
                conn.commit()
                
                # Process through PayU if configured
                pg_partner_upper = pg_partner.upper()
                
                print(f"DEBUG: pg_partner_upper: '{pg_partner_upper}'")
                
                if pg_partner_upper == 'PAYU':
                    transfer_data = [{
                        'reference_id': reference_id,
                        'amount': amount_to_bank,  # Send full requested amount to user
                        'bene_name': bank['account_holder_name'],
                        'bene_email': '',
                        'bene_mobile': '',
                        'account_no': bank['account_number'],
                        'ifsc_code': bank['ifsc_code'],
                        'payment_type': 'IMPS',
                        'purpose': 'Fund Settlement'
                    }]
                    
                    payu_result = payu_payout_svc.initiate_transfer(transfer_data)
                    
                    if payu_result['success']:
                        # Update status to QUEUED (wallet will be deducted when status becomes SUCCESS)
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'QUEUED', pg_response = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        """, (json.dumps(payu_result['data']), txn_id))
                        conn.commit()
                        
                        conn.close()
                        return jsonify({
                            'success': True,
                            'message': 'Settlement initiated successfully. Wallet will be deducted when payout is successful.',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'requested_amount': amount_to_bank,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_wallet_deduction,
                            'amount_to_bank': amount_to_bank,
                            'status': 'QUEUED'
                        }), 200
                    else:
                        # Update status to FAILED (no wallet deduction happened, so no refund needed)
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (payu_result.get('error', 'PayU transfer failed'), txn_id))
                        conn.commit()
                        
                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Settlement failed',
                            'txn_id': txn_id,
                            'error': payu_result.get('error')
                        }), 400
                
                elif pg_partner_upper == 'MUDRAPE':
                    # Use Mudrape for payout (IMPS)
                    mudrape_result = mudrape_service.call_imps_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        client_txn_id=reference_id,
                        amount=amount_to_bank,  # Send full requested amount to user
                        beneficiary_name=bank['account_holder_name']
                    )
                    
                    if mudrape_result['success']:
                        # Update transaction with Mudrape response
                        status = mudrape_result.get('status', 'INITIATED')
                        mudrape_txn_id = mudrape_result.get('mudrape_txn_id', '')
                        
                        print(f"Mudrape settlement initiated - Status: {status}, TxnID: {mudrape_txn_id}")
                        
                        # Deduct wallet ONLY if status is SUCCESS
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_wallet_deduction,
                                description=f"Settlement: ₹{amount_to_bank:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                # This shouldn't happen as we already checked balance, but handle it
                                cursor.execute("""
                                    UPDATE payout_transactions 
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, mudrape_txn_id, txn_id))
                        elif status == 'FAILED':
                            # No wallet deduction for failed transactions
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, mudrape_txn_id, txn_id))
                        else:
                            # PENDING/INITIATED - wallet will be deducted later when status becomes SUCCESS
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, mudrape_txn_id, txn_id))
                        
                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from Mudrape API
                        if status == 'INITIATED':
                            print(f"Checking status from Mudrape for reference_id: {reference_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = mudrape_service.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                utr = status_result.get('utr')
                                completed_at_from_api = status_result.get('completed_at')
                                
                                print(f"Mudrape status check result - Status: {updated_status}, UTR: {utr}, Completed: {completed_at_from_api}")
                                
                                # Deduct wallet if status changed to SUCCESS
                                if updated_status == 'SUCCESS' and status != 'SUCCESS':
                                    debit_result = wallet_svc.debit_merchant_wallet(
                                        merchant_id=merchant_id,
                                        amount=total_wallet_deduction,
                                        description=f"Settlement: ₹{amount_to_bank:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                        reference_id=txn_id
                                    )
                                    
                                    if debit_result['success']:
                                        print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    if completed_at_from_api:
                                        cursor.execute("""
                                            UPDATE payout_transactions 
                                            SET status = %s, utr = %s, completed_at = %s, updated_at = NOW()
                                            WHERE txn_id = %s
                                        """, (updated_status, utr, completed_at_from_api, txn_id))
                                    else:
                                        cursor.execute("""
                                            UPDATE payout_transactions 
                                            SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                            WHERE txn_id = %s
                                        """, (updated_status, utr, txn_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, utr, txn_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        conn.close()
                        return jsonify({
                            'success': True,
                            'message': 'Settlement initiated successfully' if status != 'SUCCESS' else 'Settlement completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'requested_amount': amount_to_bank,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_wallet_deduction,
                            'amount_to_bank': amount_to_bank,
                            'status': status,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None
                        }), 200
                    else:
                        # No wallet deduction for failed transactions
                        # Update status to FAILED
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (mudrape_result.get('message', 'Mudrape transfer failed'), txn_id))
                        conn.commit()
                        
                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Settlement failed',
                            'txn_id': txn_id,
                            'error': mudrape_result.get('message')
                        }), 400
                
                elif pg_partner_upper == 'PAYTOUCH':
                    # Use PayTouch for payout
                    # PayTouch requirements: request_id=order_id, currency=INR, narration=Truaxis, payment_mode=IMPS, bank_branch=oooo
                    payout_data = {
                        'reference_id': reference_id,  # This will be used as request_id
                        'amount': amount_to_bank,  # Send full requested amount to user
                        'bene_name': bank['account_holder_name'],
                        'bene_account': bank['account_number'],
                        'bene_ifsc': bank['ifsc_code'],
                        'bank_name': bank['bank_name']
                        # payment_mode, narration, bank_branch are hardcoded in service
                    }
                    
                    paytouch_result = paytouch_service.initiate_payout(
                        merchant_id=merchant_id,
                        payout_data=payout_data,
                        admin_id=None
                    )
                    
                    if paytouch_result['success']:
                        status = paytouch_result.get('status', 'QUEUED')
                        paytouch_txn_id = paytouch_result.get('paytouch_txn_id', '')
                        
                        print(f"PayTouch settlement initiated - Status: {status}, TxnID: {paytouch_txn_id}")
                        
                        # Wallet will be deducted via callback when status becomes SUCCESS
                        # Update transaction with PayTouch response
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = %s, pg_txn_id = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        """, (status, paytouch_txn_id, txn_id))
                        
                        conn.commit()
                        conn.close()
                        
                        return jsonify({
                            'success': True,
                            'message': 'Settlement initiated successfully. Wallet will be deducted when payout is successful.',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'requested_amount': amount_to_bank,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_wallet_deduction,
                            'amount_to_bank': amount_to_bank,
                            'status': status,
                            'note': 'Wallet will be deducted when payout is successful'
                        }), 200
                    else:
                        # No wallet deduction for failed transactions
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (paytouch_result.get('message', 'PayTouch transfer failed'), txn_id))
                        conn.commit()
                        
                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Settlement failed',
                            'txn_id': txn_id,
                            'error': paytouch_result.get('message')
                        }), 400
                
                elif pg_partner_upper == 'PAYTOUCH2':
                    # Use PayTouch2 for payout
                    # PayTouch2 requirements: request_id=order_id, currency=INR, narration=Truaxis, payment_mode=IMPS, bank_branch=oooo
                    payout_data = {
                        'reference_id': reference_id,  # This will be used as request_id
                        'amount': amount_to_bank,  # Send full requested amount to user
                        'bene_name': bank['account_holder_name'],
                        'bene_account': bank['account_number'],
                        'bene_ifsc': bank['ifsc_code'],
                        'bank_name': bank['bank_name']
                        # payment_mode, narration, bank_branch are hardcoded in service
                    }
                    
                    paytouch2_result = paytouch2_service.initiate_payout(
                        merchant_id=merchant_id,
                        payout_data=payout_data,
                        admin_id=None
                    )
                    
                    if paytouch2_result['success']:
                        status = paytouch2_result.get('status', 'QUEUED')
                        paytouch2_txn_id = paytouch2_result.get('paytouch2_txn_id', '')
                        
                        print(f"PayTouch2 settlement initiated - Status: {status}, TxnID: {paytouch2_txn_id}")
                        
                        # Wallet will be deducted via callback when status becomes SUCCESS
                        # Update transaction with PayTouch2 response
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = %s, pg_txn_id = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        """, (status, paytouch2_txn_id, txn_id))
                        
                        conn.commit()
                        conn.close()
                        
                        return jsonify({
                            'success': True,
                            'message': 'Settlement initiated successfully. Wallet will be deducted when payout is successful.',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'requested_amount': amount_to_bank,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_wallet_deduction,
                            'amount_to_bank': amount_to_bank,
                            'status': status,
                            'note': 'Wallet will be deducted when payout is successful'
                        }), 200
                    else:
                        # No wallet deduction for failed transactions
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (paytouch2_result.get('message', 'PayTouch2 transfer failed'), txn_id))
                        conn.commit()
                        
                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Settlement failed',
                            'txn_id': txn_id,
                            'error': paytouch2_result.get('message')
                        }), 400
                
                elif pg_partner_upper == 'INSTANTPESA':
                    # Use InstantPesa for settlement (IMPS/NEFT/RTGS)
                    payout_data = {
                        'amount': amount_to_bank,
                        'account_number': bank['account_number'],
                        'ifsc_code': bank['ifsc_code'],
                        'bank_name': bank['bank_name'],
                        'beneficiary_name': bank['account_holder_name'],
                        'email': data.get('email', 'merchant@orchpay.in'),
                        'mobile': data.get('mobile', '9999999999'),
                        'transaction_mode': data.get('transaction_mode', 'IMPS')
                    }
                    
                    instantpesa_result = instantpesa_svc.create_imps_payout(
                        merchant_id=merchant_id,
                        payout_data=payout_data
                    )
                    
                    if instantpesa_result['success']:
                        status = instantpesa_result.get('data', {}).get('status', 'INITIATED')
                        instantpesa_txn_id = instantpesa_result.get('data', {}).get('transaction_id', '')
                        
                        print(f"InstantPesa settlement initiated - Status: {status}, TxnID: {instantpesa_txn_id}")
                        
                        # Deduct wallet ONLY if status is SUCCESS
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_wallet_deduction,
                                description=f"Settlement: ₹{amount_to_bank:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions 
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, instantpesa_txn_id, txn_id))
                        elif status == 'FAILED':
                            # No wallet deduction for failed transactions
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, instantpesa_txn_id, txn_id))
                        else:
                            # PENDING/INITIATED - wallet will be deducted later when status becomes SUCCESS
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, instantpesa_txn_id, txn_id))
                        
                        conn.commit()
                        conn.close()
                        
                        return jsonify({
                            'success': True,
                            'message': 'Settlement initiated successfully' if status != 'SUCCESS' else 'Settlement completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'requested_amount': amount_to_bank,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_wallet_deduction,
                            'amount_to_bank': amount_to_bank,
                            'status': status,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None
                        }), 200
                    else:
                        # No wallet deduction for failed transactions
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (instantpesa_result.get('message', 'InstantPesa transfer failed'), txn_id))
                        conn.commit()
                        
                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Settlement failed',
                            'txn_id': txn_id,
                            'error': instantpesa_result.get('message')
                        }), 400
                
                elif pg_partner_upper == 'CINORIGHT':
                    # Use Cinoright for settlement (IMPS)
                    cinoright_result = cinoright_service.call_imps_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        reference_id=reference_id,
                        amount=amount_to_bank,
                        beneficiary_name=bank['account_holder_name'],
                        email=data.get('email', 'merchant@orchpay.in'),
                        phone=data.get('phone', '9999999999')
                    )
                    
                    if cinoright_result['success']:
                        status = cinoright_result.get('status', 'INITIATED')
                        cinoright_txn_id = cinoright_result.get('cinoright_txn_id', '')
                        utr = cinoright_result.get('utr')
                        
                        print(f"Cinoright settlement initiated - Status: {status}, TxnID: {cinoright_txn_id}")
                        
                        # Deduct wallet ONLY if status is SUCCESS
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_wallet_deduction,
                                description=f"Settlement: ₹{amount_to_bank:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions 
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, cinoright_txn_id, utr, txn_id))
                        elif status == 'FAILED':
                            # No wallet deduction for failed transactions
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, cinoright_txn_id, utr, txn_id))
                        else:
                            # PENDING/INITIATED - wallet will be deducted later when status becomes SUCCESS
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, cinoright_txn_id, utr, txn_id))
                        
                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from Cinoright API
                        if status == 'INITIATED' and cinoright_txn_id:
                            print(f"Checking status from Cinoright for txn_id: {cinoright_txn_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = cinoright_service.check_payout_status(cinoright_txn_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"Cinoright status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                # Deduct wallet if status changed to SUCCESS
                                if updated_status == 'SUCCESS' and status != 'SUCCESS':
                                    debit_result = wallet_svc.debit_merchant_wallet(
                                        merchant_id=merchant_id,
                                        amount=total_wallet_deduction,
                                        description=f"Settlement: ₹{amount_to_bank:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                        reference_id=txn_id
                                    )
                                    
                                    if debit_result['success']:
                                        print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        conn.close()
                        return jsonify({
                            'success': True,
                            'message': 'Settlement initiated successfully' if status != 'SUCCESS' else 'Settlement completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'requested_amount': amount_to_bank,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_wallet_deduction,
                            'amount_to_bank': amount_to_bank,
                            'status': status,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None
                        }), 200
                    else:
                        # No wallet deduction for failed transactions
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (cinoright_result.get('message', 'Cinoright transfer failed'), txn_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': 'Settlement failed',
                            'txn_id': txn_id,
                            'error': cinoright_result.get('message')
                        }), 400
                
                elif pg_partner_upper == 'ALOPNA':
                    # Use Alopna for settlement (IMPS)
                    alopna_result = alopna_service.call_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        merchant_order_id=reference_id,
                        amount=amount_to_bank,
                        payee_name=bank['account_holder_name'],
                        email=data.get('email', 'merchant@orchpay.in'),
                        mobile=data.get('mobile', '9999999999'),
                        mode='IMPS'
                    )
                    
                    if alopna_result['success']:
                        status = alopna_result.get('status', 'INITIATED')
                        pg_txn_id_resp = alopna_result.get('alopna_txn_id', '')
                        utr = alopna_result.get('utr', '')
                        
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_wallet_deduction,
                                description=f"Settlement: ₹{amount_to_bank:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions 
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        elif status == 'FAILED':
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        else:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        
                        conn.commit()
                        
                        return jsonify({
                            'success': True,
                            'message': 'Settlement initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'requested_amount': amount_to_bank,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_wallet_deduction,
                            'amount_to_bank': amount_to_bank,
                            'status': status
                        }), 200
                    else:
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (alopna_result.get('message', 'Payout failed'), txn_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': 'Settlement failed',
                            'txn_id': txn_id,
                            'error': alopna_result.get('message')
                        }), 400
                
                elif pg_partner_upper == 'RISEXPAY':

                    # Use Risexpay for settlement (IMPS)
                    result = risexpay_payout_service.call_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        merchant_order_id=reference_id,
                        amount=amount_to_bank,  # Send full requested amount to user bank
                        payee_name=bank['account_holder_name'],
                        email=data.get('email', 'merchant@orchpay.in'),
                        mobile=data.get('mobile', '9999999999'),
                        mode='IMPS'
                    )
                    
                    if result['success']:
                        status = result.get('status', 'INITIATED')
                        pg_txn_id_resp = result.get('pg_txn_id', '')
                        utr = result.get('utr', '')
                        
                        print(f"Risexpay settlement initiated - Status: {status}, TxnID: {pg_txn_id_resp}")
                        
                        # Deduct wallet ONLY if status is SUCCESS
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_wallet_deduction,
                                description=f"Settlement: ₹{amount_to_bank:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions 
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        elif status == 'FAILED':
                            # No wallet deduction for failed transactions
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        else:
                            # PENDING/INITIATED - wallet will be deducted later when status becomes SUCCESS
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        
                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from Risexpay API
                        if status == 'INITIATED':
                            print(f"Checking status from Risexpay for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = risexpay_payout_service.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"Risexpay status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                # Deduct wallet if status changed to SUCCESS
                                if updated_status == 'SUCCESS' and status != 'SUCCESS':
                                    debit_result = wallet_svc.debit_merchant_wallet(
                                        merchant_id=merchant_id,
                                        amount=total_wallet_deduction,
                                        description=f"Settlement: ₹{amount_to_bank:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                        reference_id=txn_id
                                    )
                                    
                                    if debit_result['success']:
                                        print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        conn.close()
                        return jsonify({
                            'success': True,
                            'message': 'Settlement initiated successfully' if status != 'SUCCESS' else 'Settlement completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'requested_amount': amount_to_bank,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_wallet_deduction,
                            'amount_to_bank': amount_to_bank,
                            'status': status,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None
                        }), 200
                    else:
                        # No wallet deduction for failed transactions
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (result.get('message', 'Risexpay transfer failed'), txn_id))
                        conn.commit()
                        
                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Settlement failed',
                            'txn_id': txn_id,
                            'error': result.get('message')
                        }), 400
                
                elif pg_partner_upper == 'ORO':
                    # Use ORO for settlement
                    oro_result = oro_payout_service.call_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        merchant_order_id=reference_id,
                        amount=amount_to_bank,
                        payee_name=bank['account_holder_name'],
                        email=merchant['email'],
                        mobile=merchant['mobile']
                    )
                    
                    if oro_result['success']:
                        status = oro_result.get('status', 'INITIATED')
                        pg_txn_id_resp = oro_result.get('pg_txn_id', '')
                        utr = oro_result.get('utr', '')
                        
                        print(f"ORO settlement initiated - Status: {status}, TxnID: {pg_txn_id_resp}")
                        
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                            WHERE reference_id = %s
                        """, (status, pg_txn_id_resp, utr, reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': True,
                            'message': 'Settlement initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': status
                        }), 200
                    else:
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        """, (oro_result.get('message', 'ORO transfer failed'), reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': oro_result.get('message', 'Transfer failed')
                        }), 400

                elif pg_partner_upper == 'OQPAY':
                    # Use OQPay for settlement (IMPS)
                    oqpay_result = oqpay_payout_service.call_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        merchant_order_id=reference_id,
                        amount=amount_to_bank,  # Send full requested amount to user bank
                        payee_name=bank['account_holder_name'],
                        email=data.get('email', 'merchant@orchpay.in'),
                        mobile=data.get('mobile', '9999999999'),
                        mode='IMPS'
                    )
                    
                    if oqpay_result['success']:
                        status = oqpay_result.get('status', 'INITIATED')
                        pg_txn_id_resp = oqpay_result.get('pg_txn_id', '')
                        utr = oqpay_result.get('utr', '')
                        
                        print(f"OQPay settlement initiated - Status: {status}, TxnID: {pg_txn_id_resp}")
                        
                        # Deduct wallet ONLY if status is SUCCESS
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_wallet_deduction,
                                description=f"Settlement: ₹{amount_to_bank:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions 
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        elif status == 'FAILED':
                            # No wallet deduction for failed transactions
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        else:
                            # PENDING/INITIATED - wallet will be deducted later when status becomes SUCCESS
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        
                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from OQPay API
                        if status == 'INITIATED':
                            print(f"Checking status from OQPay for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = oqpay_payout_service.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"OQPay status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                # Deduct wallet if status changed to SUCCESS
                                if updated_status == 'SUCCESS' and status != 'SUCCESS':
                                    debit_result = wallet_svc.debit_merchant_wallet(
                                        merchant_id=merchant_id,
                                        amount=total_wallet_deduction,
                                        description=f"Settlement: ₹{amount_to_bank:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                        reference_id=txn_id
                                    )
                                    
                                    if debit_result['success']:
                                        print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        conn.close()
                        return jsonify({
                            'success': True,
                            'message': 'Settlement initiated successfully' if status != 'SUCCESS' else 'Settlement completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'requested_amount': amount_to_bank,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_wallet_deduction,
                            'amount_to_bank': amount_to_bank,
                            'status': status,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None
                        }), 200
                    else:
                        # No wallet deduction for failed transactions
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (oqpay_result.get('message', 'OQPay transfer failed'), txn_id))
                        conn.commit()
                        
                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Settlement failed',
                            'txn_id': txn_id,
                            'error': oqpay_result.get('message')
                        }), 400
                
                elif pg_partner_upper == 'MAKEMYPAYMENT':
                    # Use MakeMyPayment for settlement (IMPS/NEFT)
                    mmp_result = makemypayment_payout_service.initiate_single_payout(
                        merchant_reference_id=reference_id,
                        account_holder=bank['account_holder_name'],
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        mobile=data.get('mobile', '9999999999'),
                        amount=str(amount_to_bank),
                        mode='IMPS',
                        purpose='Fund Settlement',
                        email=data.get('email', 'merchant@orchpay.in')
                    )

                    if mmp_result['success']:
                        status = mmp_result.get('status', 'INITIATED')
                        mmp_txn_id = mmp_result.get('transaction_id', '')

                        print(f"MakeMyPayment settlement initiated - Status: {status}, TxnID: {mmp_txn_id}")

                        # Deduct wallet ONLY if status is SUCCESS
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_wallet_deduction,
                                description=f"Settlement: ₹{amount_to_bank:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )

                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions 
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500

                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")

                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, mmp_txn_id, txn_id))
                        elif status == 'FAILED':
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, mmp_txn_id, txn_id))
                        else:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, mmp_txn_id, txn_id))

                        conn.commit()

                        conn.close()
                        return jsonify({
                            'success': True,
                            'message': 'Settlement initiated successfully' if status != 'SUCCESS' else 'Settlement completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'requested_amount': amount_to_bank,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_wallet_deduction,
                            'amount_to_bank': amount_to_bank,
                            'status': status,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None
                        }), 200
                    else:
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (mmp_result.get('message', 'Payout failed'), txn_id))
                        conn.commit()

                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Settlement failed',
                            'txn_id': txn_id,
                            'error': mmp_result.get('message')
                        }), 400

                else:
                    # For other gateways, keep as PENDING
                    conn.close()
                    return jsonify({
                        'success': True,
                        'message': 'Settlement request created',
                        'txn_id': txn_id,
                        'reference_id': reference_id,
                        'requested_amount': amount_to_bank,
                        'charges': charges['charge_amount'],
                        'total_deducted': total_wallet_deduction,
                        'amount_to_bank': amount_to_bank,
                        'status': 'PENDING'
                    }), 200
                    
        except Exception as e:
            conn.rollback()
            conn.close()
            raise e
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# Admin Fetch Fund
@payout_bp.route('/admin/fetch-fund', methods=['POST'])
@jwt_required()
def admin_fetch_fund():
    """
    Admin fetches funds from merchant wallet.
    This reduces merchant's settled balance and increases admin's balance.
    """
    try:
        data = request.json
        admin_id = get_jwt_identity()
        
        required_fields = ['merchant_id', 'amount', 'tpin', 'reason']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'message': '{} is required'.format(field)}), 400
        
        # Validate amount
        try:
            fetch_amount = float(data['amount'])
            if fetch_amount <= 0:
                return jsonify({'success': False, 'message': 'Amount must be greater than 0'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid amount format'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Verify admin TPIN
                cursor.execute("SELECT pin_hash FROM admin_users WHERE admin_id = %s", (admin_id,))
                admin = cursor.fetchone()
                
                if not admin or not admin['pin_hash']:
                    conn.close()
                    return jsonify({'success': False, 'message': 'TPIN not set'}), 400
                
                if not bcrypt.checkpw(data['tpin'].encode('utf-8'), admin['pin_hash'].encode('utf-8')):
                    conn.close()
                    return jsonify({'success': False, 'message': 'Invalid TPIN'}), 400
                
                merchant_id = data['merchant_id']
                reason = data['reason']
                
                # Get settled balance from merchant_wallet
                cursor.execute("""
                    SELECT COALESCE(settled_balance, 0) as available_balance
                    FROM merchant_wallet
                    WHERE merchant_id = %s
                """, (merchant_id,))
                wallet_result = cursor.fetchone()
                available_balance = float(wallet_result['available_balance']) if wallet_result else 0.00
                
                print("=== FETCH FUND DEBUG ===")
                print("Merchant ID: {}".format(merchant_id))
                print("Settled Balance (Available): ₹{:.2f}".format(available_balance))
                print("Fetch Amount: ₹{:.2f}".format(fetch_amount))
                
                # Check if sufficient balance
                if fetch_amount > available_balance:
                    conn.close()
                    return jsonify({
                        'success': False,
                        'message': 'Insufficient balance in wallet, remaining balance in wallet: ₹{:.2f}'.format(available_balance)
                    }), 400
            
            conn.close()
            
            # Debit merchant wallet using wallet service
            debit_result = wallet_svc.debit_merchant_wallet(
                merchant_id=merchant_id,
                amount=fetch_amount,
                description="Fund fetched by admin - {}".format(reason),
                reference_id=reason
            )
            
            if not debit_result['success']:
                return jsonify({
                    'success': False,
                    'message': debit_result['message']
                }), 400
            
            print("✅ WALLET DEBITED - Balance Before: ₹{:.2f}, Balance After: ₹{:.2f}".format(
                debit_result['balance_before'], debit_result['balance_after']))
            
            # Credit admin wallet
            admin_credit = wallet_svc.credit_admin_wallet(
                admin_id=admin_id,
                amount=fetch_amount,
                description="Fund fetched from {} - {}".format(merchant_id, reason),
                reference_id=debit_result['txn_id']
            )
            
            if admin_credit['success']:
                print("✅ ADMIN WALLET CREDITED - ₹{:.2f}".format(fetch_amount))
            
            return jsonify({
                'success': True,
                'message': 'Fund fetched successfully',
                'txn_id': debit_result['txn_id'],
                'amount': fetch_amount,
                'balance_before': debit_result['balance_before'],
                'balance_after': debit_result['balance_after']
            }), 200
            
        except Exception as e:
            print("Error in admin_fetch_fund: {}".format(str(e)))
            if conn:
                conn.rollback()
                conn.close()
            raise e
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
# Client Direct Payout (with bank details in request)
@payout_bp.route('/client/direct-payout', methods=['POST'])
@jwt_required()
def client_direct_payout():
    """
    Process payout with bank details provided directly in the request.
    No need to pre-register bank account.
    """
    try:
        data = request.json
        merchant_id = get_jwt_identity()

        # IP SECURITY CHECK - Validate merchant IP for payout operations
        from ip_security_routes import validate_merchant_ip
        is_valid, message = validate_merchant_ip(merchant_id, '/api/payout/client/direct-payout')
        if not is_valid:
            return jsonify({'success': False, 'message': message}), 403

        # Required fields for direct payout
        required_fields = ['amount', 'tpin', 'account_holder_name', 'account_number', 'ifsc_code', 'bank_name', 'order_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'message': f'{field} is required'}), 400

        # Optional fields
        payment_type = data.get('payment_type', 'IMPS')  # IMPS, NEFT, RTGS
        purpose = data.get('purpose', 'Payout')
        bene_email = data.get('bene_email', '')
        bene_mobile = data.get('bene_mobile', '')
        callback_url = data.get('callback_url', None)  # Optional callback URL for this transaction

        # Validate payment type
        if payment_type not in ['IMPS', 'NEFT', 'RTGS']:
            return jsonify({'success': False, 'message': 'Invalid payment_type. Must be IMPS, NEFT, or RTGS'}), 400

        # Validate amount
        try:
            amount = float(data['amount'])
            if amount <= 0:
                return jsonify({'success': False, 'message': 'Amount must be greater than 0'}), 400
            
            # Check payout limit - maximum 500,000 per transaction
            if amount > 500000:
                return jsonify({'success': False, 'message': 'Transaction out of limit. Maximum payout amount is ₹5,00,000 per transaction'}), 400
                
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid amount format'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        try:
            with conn.cursor() as cursor:
                # Check for duplicate order_id for this merchant
                cursor.execute("""
                    SELECT txn_id, status FROM payout_transactions
                    WHERE merchant_id = %s AND order_id = %s
                """, (merchant_id, data['order_id']))
                existing_payout = cursor.fetchone()
                
                if existing_payout:
                    conn.close()
                    return jsonify({
                        'success': False,
                        'message': f'Payout failed: Duplicate order_id. A payout with order_id {data["order_id"]} already exists',
                        'existing_txn_id': existing_payout['txn_id'],
                        'existing_status': existing_payout['status']
                    }), 400
                
                # Verify merchant TPIN
                cursor.execute("SELECT pin_hash, scheme_id FROM merchants WHERE merchant_id = %s", (merchant_id,))
                merchant = cursor.fetchone()

                if not merchant or not merchant['pin_hash']:
                    conn.close()
                    return jsonify({'success': False, 'message': 'TPIN not set'}), 400

                if not bcrypt.checkpw(data['tpin'].encode('utf-8'), merchant['pin_hash'].encode('utf-8')):
                    conn.close()
                    return jsonify({'success': False, 'message': 'Invalid TPIN'}), 400

                # Calculate payout charges based on merchant scheme
                charges = payout_svc.calculate_charges(
                    amount,
                    merchant['scheme_id'],
                    'PAYOUT'
                )

                if not charges:
                    conn.close()
                    return jsonify({'success': False, 'message': 'Unable to calculate payout charges'}), 400

                # Send full requested amount to bank, deduct charges from wallet separately
                net_amount_to_bank = amount  # Full requested amount goes to beneficiary
                total_deduction = amount + charges['charge_amount']  # Total to deduct from wallet

                # Get settled balance from merchant_wallet (this is the withdrawable amount)
                cursor.execute("""
                    SELECT COALESCE(settled_balance, 0) as available_balance
                    FROM merchant_wallet
                    WHERE merchant_id = %s
                """, (merchant_id,))
                wallet_result = cursor.fetchone()
                available_balance = float(wallet_result['available_balance']) if wallet_result else 0.00

                # DEBUG LOGGING
                print(f"=== PAYOUT VALIDATION DEBUG ===")
                print(f"Merchant ID: {merchant_id}")
                print(f"Requested Amount: ₹{amount:.2f}")
                print(f"Charges: ₹{charges['charge_amount']:.2f}")
                print(f"Total Deduction: ₹{total_deduction:.2f}")
                print(f"Settled Balance (Available): ₹{available_balance:.2f}")
                print(f"Validation Check: {total_deduction} > {available_balance} = {total_deduction > available_balance}")
                print(f"===============================")

                # Check if settled balance is sufficient (amount + charges)
                if total_deduction > available_balance:
                    print(f"❌ VALIDATION FAILED - Rejecting payout")
                    conn.close()
                    return jsonify({
                        'success': False,
                        'message': f'Insufficient balance in wallet, remaining balance in wallet: ₹{available_balance:.2f}'
                    }), 400
                
                print(f"✅ VALIDATION PASSED - Processing payout")
                
                # DO NOT debit wallet yet - only debit when payout is SUCCESS
                # This prevents wallet deduction for pending/failed transactions
                
                # Get PG partner from service routing for PAYOUT
                cursor.execute("""
                    SELECT pg_partner FROM service_routing
                    WHERE service_type = 'PAYOUT'
                    AND routing_type = 'SINGLE_USER'
                    AND merchant_id = %s
                    AND is_active = TRUE
                    ORDER BY priority ASC
                    LIMIT 1
                """, (merchant_id,))
                routing = cursor.fetchone()

                # If no merchant-specific routing, get ALL_USERS routing
                if not routing:
                    cursor.execute("""
                        SELECT pg_partner FROM service_routing
                        WHERE service_type = 'PAYOUT'
                        AND routing_type = 'ALL_USERS'
                        AND is_active = TRUE
                        ORDER BY priority ASC
                        LIMIT 1
                    """)
                    routing = cursor.fetchone()

                if not routing:
                    conn.close()
                    return jsonify({'success': False, 'message': 'No payout gateway configured'}), 400

                pg_partner = routing['pg_partner']

                # Create payout transaction record
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                reference_id = f"DP{timestamp}{uuid.uuid4().hex[:6].upper()}"
                
                # Gateway-specific TXN_ID for easy identification
                pg_partner_upper = pg_partner.upper()
                if pg_partner_upper == 'ROCKYPAYZ':
                    txn_id = f"RCK_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper in ['PES', 'SECTORPE']:
                    txn_id = f"PES_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper in ['MAXPE', 'NODEPAY']:
                    txn_id = f"MAXPE_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'NEXTPAY':
                    txn_id = f"NEXTPAY_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'NEXTPAY':
                    txn_id = f"MAXPE_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'NEXTPAY':
                    txn_id = f"NEXTPAY_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'TPIPAY':
                    txn_id = f"TPI_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'MAKEMYPAYMENT':
                    txn_id = f"MMP_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'CLOCKSPAY':
                    txn_id = f"CLK_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'CINORIGHT':
                    txn_id = f"CINO_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'OQPAY':
                    txn_id = f"OQP_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'RISEXPAY':
                    txn_id = f"TXN{uuid.uuid4().hex[:12].upper()}"
                else:
                    txn_id = f"TXN{uuid.uuid4().hex[:12].upper()}"

                cursor.execute("""
                    INSERT INTO payout_transactions
                    (txn_id, reference_id, order_id, merchant_id, amount, charge_amount, charge_type,
                     net_amount, bene_name, bene_email, bene_mobile, bene_bank, account_no,
                     ifsc_code, payment_type, purpose, callback_url, pg_partner, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'INITIATED', NOW())
                """, (txn_id, reference_id, data['order_id'], merchant_id, total_deduction,
                      charges['charge_amount'], charges['charge_type'], net_amount_to_bank,
                      data['account_holder_name'], bene_email, bene_mobile, data['bank_name'],
                      data['account_number'], data['ifsc_code'], payment_type, purpose, callback_url, pg_partner))

                conn.commit()

                # Process through payment gateway
                pg_partner_upper = pg_partner.upper()

                if pg_partner_upper == 'PAYU':
                    transfer_data = [{
                        'reference_id': reference_id,
                        'amount': net_amount_to_bank,
                        'bene_name': data['account_holder_name'],
                        'bene_email': bene_email,
                        'bene_mobile': bene_mobile,
                        'account_no': data['account_number'],
                        'ifsc_code': data['ifsc_code'],
                        'payment_type': payment_type,
                        'purpose': purpose
                    }]

                    payu_result = payu_payout_svc.initiate_transfer(transfer_data)

                    if payu_result['success']:
                        # Update status to QUEUED (wallet will be deducted when status becomes SUCCESS)
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = 'QUEUED', updated_at = NOW()
                            WHERE txn_id = %s
                        """, (txn_id,))
                        conn.commit()
                        
                        # Get current wallet balance (not yet deducted)
                        cursor.execute("""
                            SELECT settled_balance, unsettled_balance
                            FROM merchant_wallet
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        current_wallet = cursor.fetchone()
                        current_balance = float(current_wallet['settled_balance']) if current_wallet else 0.00

                        conn.close()
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully. Wallet will be deducted when payout is successful.',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'order_id': data['order_id'],
                            'requested_amount': amount,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_deduction,
                            'amount_to_beneficiary': net_amount_to_bank,
                            'status': 'QUEUED',
                            'wallet_balance': current_balance,  # Current balance (not yet deducted)
                            'beneficiary': {
                                'name': data['account_holder_name'],
                                'account_number': data['account_number'],
                                'ifsc_code': data['ifsc_code'],
                                'bank_name': data['bank_name']
                            }
                        }), 200
                    else:
                        # No wallet deduction happened, so no refund needed
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = 'FAILED', error_message = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        """, (payu_result.get('error', 'PayU transfer failed'), txn_id))
                        conn.commit()

                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': payu_result.get('error')
                        }), 400

                elif pg_partner_upper == 'MUDRAPE':
                    mudrape_result = mudrape_service.call_imps_payout_api(
                        account_number=data['account_number'],
                        ifsc_code=data['ifsc_code'],
                        client_txn_id=reference_id,
                        amount=net_amount_to_bank,
                        beneficiary_name=data['account_holder_name']
                    )

                    if mudrape_result['success']:
                        status = mudrape_result.get('status', 'INITIATED')
                        mudrape_txn_id = mudrape_result.get('mudrape_txn_id', '')

                        print(f"Mudrape payout initiated - Status: {status}, TxnID: {mudrape_txn_id}")

                        # Deduct wallet ONLY if status is SUCCESS
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_deduction,
                                description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                # This shouldn't happen as we already checked balance, but handle it
                                cursor.execute("""
                                    UPDATE payout_transactions
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, mudrape_txn_id, txn_id))
                        elif status == 'FAILED':
                            # No wallet deduction for failed transactions
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, mudrape_txn_id, txn_id))
                        else:
                            # PENDING/INITIATED - wallet will be deducted later when status becomes SUCCESS
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, mudrape_txn_id, txn_id))

                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from Mudrape API
                        if status == 'INITIATED':
                            print(f"Checking status from Mudrape for reference_id: {reference_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = mudrape_service.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                utr = status_result.get('utr')
                                completed_at_from_api = status_result.get('completed_at')
                                
                                print(f"Mudrape status check result - Status: {updated_status}, UTR: {utr}, Completed: {completed_at_from_api}")
                                
                                # Deduct wallet if status changed to SUCCESS
                                if updated_status == 'SUCCESS' and status != 'SUCCESS':
                                    debit_result = wallet_svc.debit_merchant_wallet(
                                        merchant_id=merchant_id,
                                        amount=total_deduction,
                                        description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                        reference_id=txn_id
                                    )
                                    
                                    if debit_result['success']:
                                        print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    if completed_at_from_api:
                                        cursor.execute("""
                                            UPDATE payout_transactions 
                                            SET status = %s, utr = %s, completed_at = %s, updated_at = NOW()
                                            WHERE txn_id = %s
                                        """, (updated_status, utr, completed_at_from_api, txn_id))
                                    else:
                                        cursor.execute("""
                                            UPDATE payout_transactions 
                                            SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                            WHERE txn_id = %s
                                        """, (updated_status, utr, txn_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, utr, txn_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        # Get current wallet balance
                        cursor.execute("""
                            SELECT settled_balance, unsettled_balance
                            FROM merchant_wallet
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        current_wallet = cursor.fetchone()
                        current_balance = float(current_wallet['settled_balance']) if current_wallet else 0.00
                        
                        conn.close()

                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully' if status != 'SUCCESS' else 'Payout completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'order_id': data['order_id'],
                            'requested_amount': amount,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_deduction,
                            'amount_to_beneficiary': net_amount_to_bank,
                            'status': status,
                            'wallet_balance': current_balance,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None,
                            'beneficiary': {
                                'name': data['account_holder_name'],
                                'account_number': data['account_number'],
                                'ifsc_code': data['ifsc_code'],
                                'bank_name': data['bank_name']
                            }
                        }), 200
                    else:
                        # No wallet deduction for failed transactions
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (mudrape_result.get('message', 'Mudrape transfer failed'), txn_id))
                        conn.commit()

                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': mudrape_result.get('message')
                        }), 400

                elif pg_partner_upper == 'INSTANTPESA':
                    payout_data = {
                        'amount': net_amount_to_bank,
                        'account_number': data['account_number'],
                        'ifsc_code': data['ifsc_code'],
                        'bank_name': data['bank_name'],
                        'beneficiary_name': data['account_holder_name'],
                        'email': bene_email or 'merchant@orchpay.in',
                        'mobile': bene_mobile or '9999999999',
                        'transaction_mode': payment_type
                    }
                    
                    instantpesa_result = instantpesa_svc.create_imps_payout(
                        merchant_id=merchant_id,
                        payout_data=payout_data
                    )

                    if instantpesa_result['success']:
                        status = instantpesa_result.get('data', {}).get('status', 'INITIATED')
                        instantpesa_txn_id = instantpesa_result.get('data', {}).get('transaction_id', '')

                        print(f"InstantPesa payout initiated - Status: {status}, TxnID: {instantpesa_txn_id}")

                        # Deduct wallet ONLY if status is SUCCESS
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_deduction,
                                description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, instantpesa_txn_id, txn_id))
                        elif status == 'FAILED':
                            # No wallet deduction for failed transactions
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, instantpesa_txn_id, txn_id))
                        else:
                            # PENDING/INITIATED - wallet will be deducted later when status becomes SUCCESS
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, instantpesa_txn_id, txn_id))

                        conn.commit()
                        
                        # Get current wallet balance
                        cursor.execute("""
                            SELECT settled_balance, unsettled_balance
                            FROM merchant_wallet
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        current_wallet = cursor.fetchone()
                        current_balance = float(current_wallet['settled_balance']) if current_wallet else 0.00
                        
                        conn.close()

                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully' if status != 'SUCCESS' else 'Payout completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'order_id': data['order_id'],
                            'requested_amount': amount,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_deduction,
                            'amount_to_beneficiary': net_amount_to_bank,
                            'status': status,
                            'wallet_balance': current_balance,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None,
                            'beneficiary': {
                                'name': data['account_holder_name'],
                                'account_number': data['account_number'],
                                'ifsc_code': data['ifsc_code'],
                                'bank_name': data['bank_name']
                            }
                        }), 200
                    else:
                        # No wallet deduction happened, so no refund needed
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = 'FAILED', error_message = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        """, (instantpesa_result.get('message', 'InstantPesa payout failed'), txn_id))
                        conn.commit()

                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': instantpesa_result.get('message')
                        }), 400

                elif pg_partner_upper == 'PAYTOUCH':
                    # Use PayTouch for payout
                    # PayTouch requirements: request_id=order_id, currency=INR, narration=Truaxis, payment_mode=IMPS, bank_branch=oooo
                    payout_data = {
                        'reference_id': reference_id,  # This will be used as request_id
                        'amount': net_amount_to_bank,
                        'bene_name': data['account_holder_name'],
                        'bene_account': data['account_number'],
                        'bene_ifsc': data['ifsc_code'],
                        'bank_name': data['bank_name']
                        # payment_mode, narration, bank_branch are hardcoded in service
                    }
                    
                    paytouch_result = paytouch_service.initiate_payout(
                        merchant_id=merchant_id,
                        payout_data=payout_data,
                        admin_id=None
                    )
                    
                    if paytouch_result['success']:
                        status = paytouch_result.get('status', 'QUEUED')
                        paytouch_txn_id = paytouch_result.get('paytouch_txn_id', '')
                        
                        # Wallet will be deducted via callback when status becomes SUCCESS
                        # Update transaction with PayTouch response
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = %s, pg_txn_id = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        """, (status, paytouch_txn_id, txn_id))
                        
                        conn.commit()
                        
                        # Get current wallet balance (not yet deducted)
                        cursor.execute("""
                            SELECT settled_balance, unsettled_balance
                            FROM merchant_wallet
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        current_wallet = cursor.fetchone()
                        current_balance = float(current_wallet['settled_balance']) if current_wallet else 0.00
                        
                        conn.close()
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully. Wallet will be deducted when payout is successful.',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'order_id': data['order_id'],
                            'requested_amount': amount,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_deduction,
                            'amount_to_beneficiary': net_amount_to_bank,
                            'status': status,
                            'wallet_balance': current_balance,
                            'note': 'Wallet will be deducted when payout is successful',
                            'beneficiary': {
                                'name': data['account_holder_name'],
                                'account_number': data['account_number'],
                                'ifsc_code': data['ifsc_code'],
                                'bank_name': data['bank_name']
                            }
                        }), 200
                    else:
                        # No wallet deduction for failed transactions
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (paytouch_result.get('message', 'PayTouch transfer failed'), txn_id))
                        conn.commit()
                        
                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': paytouch_result.get('message')
                        }), 400

                elif pg_partner_upper == 'PAYTOUCH2':
                    # Use PayTouch2 for payout
                    # PayTouch2 requirements: request_id=order_id, currency=INR, narration=Truaxis, payment_mode=IMPS, bank_branch=oooo
                    payout_data = {
                        'reference_id': reference_id,  # This will be used as request_id
                        'amount': net_amount_to_bank,
                        'bene_name': data['account_holder_name'],
                        'bene_account': data['account_number'],
                        'bene_ifsc': data['ifsc_code'],
                        'bank_name': data['bank_name']
                        # payment_mode, narration, bank_branch are hardcoded in service
                    }
                    
                    paytouch2_result = paytouch2_service.initiate_payout(
                        merchant_id=merchant_id,
                        payout_data=payout_data,
                        admin_id=None
                    )
                    
                    if paytouch2_result['success']:
                        status = paytouch2_result.get('status', 'QUEUED')
                        paytouch2_txn_id = paytouch2_result.get('paytouch2_txn_id', '')
                        
                        # Wallet will be deducted via callback when status becomes SUCCESS
                        # Update transaction with PayTouch2 response
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = %s, pg_txn_id = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        """, (status, paytouch2_txn_id, txn_id))
                        
                        conn.commit()
                        
                        # Get current wallet balance (not yet deducted)
                        cursor.execute("""
                            SELECT settled_balance, unsettled_balance
                            FROM merchant_wallet
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        current_wallet = cursor.fetchone()
                        current_balance = float(current_wallet['settled_balance']) if current_wallet else 0.00
                        
                        conn.close()
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully. Wallet will be deducted when payout is successful.',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'order_id': data['order_id'],
                            'requested_amount': amount,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_deduction,
                            'amount_to_beneficiary': net_amount_to_bank,
                            'status': status,
                            'wallet_balance': current_balance,
                            'note': 'Wallet will be deducted when payout is successful',
                            'beneficiary': {
                                'name': data['account_holder_name'],
                                'account_number': data['account_number'],
                                'ifsc_code': data['ifsc_code'],
                                'bank_name': data['bank_name']
                            }
                        }), 200
                    else:
                        # No wallet deduction for failed transactions
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (paytouch2_result.get('message', 'PayTouch2 transfer failed'), txn_id))
                        conn.commit()
                        
                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': paytouch2_result.get('message')
                        }), 400

                elif pg_partner_upper == 'CINORIGHT':
                    # Use Cinoright for payout (IMPS)
                    cinoright_result = cinoright_service.call_imps_payout_api(
                        account_number=data['account_number'],
                        ifsc_code=data['ifsc_code'],
                        reference_id=reference_id,
                        amount=net_amount_to_bank,
                        beneficiary_name=data['account_holder_name'],
                        email=bene_email or 'merchant@orchpay.in',
                        phone=bene_mobile or '9999999999'
                    )

                    if cinoright_result['success']:
                        status = cinoright_result.get('status', 'INITIATED')
                        cinoright_txn_id = cinoright_result.get('cinoright_txn_id', '')
                        utr = cinoright_result.get('utr')

                        print(f"Cinoright payout initiated - Status: {status}, TxnID: {cinoright_txn_id}")

                        # Deduct wallet ONLY if status is SUCCESS
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_deduction,
                                description=f"Payout: ₹{net_amount_to_bank:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )

                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500

                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")

                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, cinoright_txn_id, utr, txn_id))
                        elif status == 'FAILED':
                            # No wallet deduction for failed transactions
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, cinoright_txn_id, utr, txn_id))
                        else:
                            # PENDING/INITIATED - wallet will be deducted later when status becomes SUCCESS
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, cinoright_txn_id, utr, txn_id))

                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from Cinoright API
                        if status == 'INITIATED' and cinoright_txn_id:
                            print(f"Checking status from Cinoright for txn_id: {cinoright_txn_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = cinoright_service.check_payout_status(cinoright_txn_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"Cinoright status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                # Deduct wallet if status changed to SUCCESS
                                if updated_status == 'SUCCESS' and status != 'SUCCESS':
                                    debit_result = wallet_svc.debit_merchant_wallet(
                                        merchant_id=merchant_id,
                                        amount=total_deduction,
                                        description=f"Payout: ₹{net_amount_to_bank:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                        reference_id=txn_id
                                    )
                                    
                                    if debit_result['success']:
                                        print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        # Get current wallet balance
                        cursor.execute("""
                            SELECT settled_balance, unsettled_balance
                            FROM merchant_wallet
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        current_wallet = cursor.fetchone()
                        current_balance = float(current_wallet['settled_balance']) if current_wallet else 0.00
                        
                        conn.close()

                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully' if status != 'SUCCESS' else 'Payout completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'order_id': data['order_id'],
                            'requested_amount': amount,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_deduction,
                            'amount_to_beneficiary': net_amount_to_bank,
                            'status': status,
                            'wallet_balance': current_balance,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None,
                            'beneficiary': {
                                'name': data['account_holder_name'],
                                'account_number': data['account_number'],
                                'ifsc_code': data['ifsc_code'],
                                'bank_name': data['bank_name']
                            }
                        }), 200
                    else:
                        # No wallet deduction happened, so no refund needed
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = 'FAILED', error_message = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        """, (cinoright_result.get('message', 'Cinoright payout failed'), txn_id))
                        conn.commit()

                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': cinoright_result.get('message')
                        }), 400

                elif pg_partner_upper in ['PES', 'SECTORPE']:
                    # Use SectorPe for payout (IMPS)
                    sectorpe_result = sectorpe_payout_service.call_payout_api(
                        account_number=data['account_number'],
                        ifsc_code=data['ifsc_code'],
                        bank_name=data['bank_name'],
                        merchant_order_id=reference_id,
                        amount=net_amount_to_bank,
                        payee_name=data['account_holder_name'],
                        email=bene_email or 'merchant@orchpay.in',
                        mobile=bene_mobile or '9999999999',
                        mode='IMPS'
                    )

                    if sectorpe_result['success']:
                        status = sectorpe_result.get('status', 'INITIATED')

                        print(f"SectorPe payout initiated - Status: {status}, Merchant Order ID: {reference_id}")

                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_deduction,
                                description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, txn_id))
                        elif status == 'FAILED':
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, txn_id))
                        else:
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, txn_id))

                        conn.commit()
                        
                        if status == 'INITIATED':
                            print(f"Checking status from SectorPe for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)
                            
                            status_result = sectorpe_payout_service.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"SectorPe status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                if updated_status == 'SUCCESS' and status != 'SUCCESS':
                                    debit_result = wallet_svc.debit_merchant_wallet(
                                        merchant_id=merchant_id,
                                        amount=total_deduction,
                                        description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                        reference_id=txn_id
                                    )
                                    
                                    if debit_result['success']:
                                        print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                                
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        cursor.execute("""
                            SELECT settled_balance, unsettled_balance
                            FROM merchant_wallet
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        current_wallet = cursor.fetchone()
                        current_balance = float(current_wallet['settled_balance']) if current_wallet else 0.00
                        
                        conn.close()

                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully' if status != 'SUCCESS' else 'Payout completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'order_id': data['order_id'],
                            'requested_amount': amount,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_deduction,
                            'amount_to_beneficiary': net_amount_to_bank,
                            'status': status,
                            'wallet_balance': current_balance,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None,
                            'beneficiary': {
                                'name': data['account_holder_name'],
                                'account_number': data['account_number'],
                                'ifsc_code': data['ifsc_code'],
                                'bank_name': data['bank_name']
                            }
                        }), 200
                    else:
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = 'FAILED', error_message = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        """, (sectorpe_result.get('message', 'SectorPe payout failed'), txn_id))
                        conn.commit()

                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': sectorpe_result.get('message')
                        }), 400
                
                elif pg_partner_upper in ['MAXPE', 'NODEPAY']:
                    # Use MaxPe or NodePay for payout (IMPS)
                    # Get the appropriate service based on pg_partner
                    payout_service_instance = get_payout_service(pg_partner_upper)
                    
                    maxpe_result = payout_service_instance.call_payout_api(
                        account_number=data['account_number'],
                        ifsc_code=data['ifsc_code'],
                        bank_name=data['bank_name'],
                        merchant_order_id=reference_id,
                        amount=net_amount_to_bank,
                        payee_name=data['account_holder_name'],
                        email=bene_email or 'merchant@orchpay.in',
                        mobile=bene_mobile or '9999999999'
                    )

                    if maxpe_result['success']:
                        status = maxpe_result.get('status', 'INITIATED')

                        print(f"{pg_partner_upper} payout initiated - Status: {status}, Merchant Order ID: {reference_id}")

                        # Deduct wallet ONLY if status is SUCCESS
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_deduction,
                                description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, txn_id))
                        elif status == 'FAILED':
                            # No wallet deduction for failed transactions
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, txn_id))
                        else:
                            # PENDING/INITIATED - wallet will be deducted later when status becomes SUCCESS
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, txn_id))

                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from API
                        if status == 'INITIATED':
                            print(f"Checking status from {pg_partner_upper} for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = payout_service_instance.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"{pg_partner_upper} status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                # Deduct wallet if status changed to SUCCESS
                                if updated_status == 'SUCCESS' and status != 'SUCCESS':
                                    debit_result = wallet_svc.debit_merchant_wallet(
                                        merchant_id=merchant_id,
                                        amount=total_deduction,
                                        description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                        reference_id=txn_id
                                    )
                                    
                                    if debit_result['success']:
                                        print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        # Get current wallet balance
                        cursor.execute("""
                            SELECT settled_balance, unsettled_balance
                            FROM merchant_wallet
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        current_wallet = cursor.fetchone()
                        current_balance = float(current_wallet['settled_balance']) if current_wallet else 0.00
                        
                        conn.close()

                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully' if status != 'SUCCESS' else 'Payout completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'order_id': data['order_id'],
                            'requested_amount': amount,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_deduction,
                            'amount_to_beneficiary': net_amount_to_bank,
                            'status': status,
                            'wallet_balance': current_balance,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None,
                            'beneficiary': {
                                'name': data['account_holder_name'],
                                'account_number': data['account_number'],
                                'ifsc_code': data['ifsc_code'],
                                'bank_name': data['bank_name']
                            }
                        }), 200
                    else:
                        # No wallet deduction happened, so no refund needed
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = 'FAILED', error_message = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        """, (maxpe_result.get('message', 'MaxPe payout failed'), txn_id))
                        conn.commit()

                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': maxpe_result.get('message')
                        }), 400

                elif pg_partner_upper == 'NEXTPAY':
                    # Use Nextpay for payout (IMPS)
                    # Get the appropriate service based on pg_partner
                    payout_service_instance = nextpay_payout_service
                    
                    maxpe_result = payout_service_instance.call_payout_api(
                        account_number=data['account_number'],
                        ifsc_code=data['ifsc_code'],
                        bank_name=data['bank_name'],
                        merchant_order_id=reference_id,
                        amount=net_amount_to_bank,
                        payee_name=data['account_holder_name'],
                        email=bene_email or 'merchant@orchpay.in',
                        mobile=bene_mobile or '9999999999'
                    )

                    if maxpe_result['success']:
                        status = maxpe_result.get('status', 'INITIATED')

                        print(f"{pg_partner_upper} payout initiated - Status: {status}, Merchant Order ID: {reference_id}")

                        # Deduct wallet ONLY if status is SUCCESS
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_deduction,
                                description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, txn_id))
                        elif status == 'FAILED':
                            # No wallet deduction for failed transactions
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, txn_id))
                        else:
                            # PENDING/INITIATED - wallet will be deducted later when status becomes SUCCESS
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, txn_id))

                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from API
                        if status == 'INITIATED':
                            print(f"Checking status from {pg_partner_upper} for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = payout_service_instance.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"{pg_partner_upper} status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                # Deduct wallet if status changed to SUCCESS
                                if updated_status == 'SUCCESS' and status != 'SUCCESS':
                                    debit_result = wallet_svc.debit_merchant_wallet(
                                        merchant_id=merchant_id,
                                        amount=total_deduction,
                                        description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                        reference_id=txn_id
                                    )
                                    
                                    if debit_result['success']:
                                        print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        # Get current wallet balance
                        cursor.execute("""
                            SELECT settled_balance, unsettled_balance
                            FROM merchant_wallet
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        current_wallet = cursor.fetchone()
                        current_balance = float(current_wallet['settled_balance']) if current_wallet else 0.00
                        
                        conn.close()

                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully' if status != 'SUCCESS' else 'Payout completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'order_id': data['order_id'],
                            'requested_amount': amount,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_deduction,
                            'amount_to_beneficiary': net_amount_to_bank,
                            'status': status,
                            'wallet_balance': current_balance,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None,
                            'beneficiary': {
                                'name': data['account_holder_name'],
                                'account_number': data['account_number'],
                                'ifsc_code': data['ifsc_code'],
                                'bank_name': data['bank_name']
                            }
                        }), 200
                    else:
                        # No wallet deduction happened, so no refund needed
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = 'FAILED', error_message = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        """, (maxpe_result.get('message', 'MaxPe payout failed'), txn_id))
                        conn.commit()

                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': maxpe_result.get('message')
                        }), 400

                elif pg_partner_upper == 'TPIPAY':
                    # Use Tpipay for payout (IMPS/NEFT)
                    tpipay_result = tpipay_payout_service.call_payout_api(
                        account_number=data['account_number'],
                        ifsc_code=data['ifsc_code'],
                        bank_name=data['bank_name'],
                        merchant_order_id=reference_id,
                        amount=net_amount_to_bank,
                        payee_name=data['account_holder_name'],
                        email=bene_email or 'merchant@orchpay.in',
                        mobile=bene_mobile or '9999999999',
                        channel_id='2'  # 2 = IMPS
                    )

                    if tpipay_result['success']:
                        status = tpipay_result.get('status', 'INITIATED')
                        payid = tpipay_result.get('payid', '')
                        utr = tpipay_result.get('utr', '')

                        print(f"Tpipay payout initiated - Status: {status}, Merchant Order ID: {reference_id}, PayID: {payid}")

                        # Deduct wallet ONLY if status is SUCCESS (pending goes via callback)
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_deduction,
                                description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )

                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500

                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, payid, utr, txn_id))
                        elif status == 'FAILED':
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, payid, utr, txn_id))
                        else:
                            # PENDING/INITIATED – wallet will be deducted via callback when SUCCESS
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, payid, utr, txn_id))

                        conn.commit()
                        # Note: Tpipay delivers final status via callback – no status-check endpoint.

                        # Get current wallet balance
                        cursor.execute("""
                            SELECT settled_balance, unsettled_balance
                            FROM merchant_wallet
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        current_wallet = cursor.fetchone()
                        current_balance = float(current_wallet['settled_balance']) if current_wallet else 0.00

                        conn.close()

                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully' if status != 'SUCCESS' else 'Payout completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'order_id': data['order_id'],
                            'requested_amount': amount,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_deduction,
                            'amount_to_beneficiary': net_amount_to_bank,
                            'status': status,
                            'wallet_balance': current_balance,
                            'note': 'Wallet will be deducted when payout is confirmed via callback' if status not in ['SUCCESS', 'FAILED'] else None,
                            'beneficiary': {
                                'name': data['account_holder_name'],
                                'account_number': data['account_number'],
                                'ifsc_code': data['ifsc_code'],
                                'bank_name': data['bank_name']
                            }
                        }), 200
                    else:
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = 'FAILED', error_message = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        """, (tpipay_result.get('message', 'Tpipay payout failed'), txn_id))
                        conn.commit()

                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': tpipay_result.get('message')
                        }), 400

                elif pg_partner_upper == 'MAKEMYPAYMENT':
                    mmp_result = makemypayment_payout_service.initiate_single_payout(
                        merchant_reference_id=reference_id,
                        account_holder=data['account_holder_name'],
                        account_number=data['account_number'],
                        ifsc_code=data['ifsc_code'],
                        bank_name=data['bank_name'],
                        mobile=bene_mobile or '9999999999',
                        amount=str(net_amount_to_bank),
                        mode=payment_type,
                        purpose=purpose,
                        email=bene_email or 'merchant@orchpay.in'
                    )

                    if mmp_result['success']:
                        status = mmp_result.get('status', 'INITIATED')
                        mmp_txn_id = mmp_result.get('transaction_id', '')

                        print(f"MakeMyPayment payout initiated - Status: {status}, Merchant Order ID: {reference_id}, TxnID: {mmp_txn_id}")

                        # Deduct wallet ONLY if status is SUCCESS (pending goes via callback)
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_deduction,
                                description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )

                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500

                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, mmp_txn_id, txn_id))
                        elif status == 'FAILED':
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, mmp_txn_id, txn_id))
                        else:
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, mmp_txn_id, txn_id))

                        conn.commit()
                        
                        # Get current wallet balance
                        cursor.execute("""
                            SELECT settled_balance, unsettled_balance
                            FROM merchant_wallet
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        current_wallet = cursor.fetchone()
                        current_balance = float(current_wallet['settled_balance']) if current_wallet else 0.00
                        
                        conn.close()

                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully' if status != 'SUCCESS' else 'Payout completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'order_id': data['order_id'],
                            'requested_amount': amount,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_deduction,
                            'amount_to_beneficiary': net_amount_to_bank,
                            'status': status,
                            'wallet_balance': current_balance,
                            'note': 'Wallet will be deducted when payout is confirmed via callback' if status not in ['SUCCESS', 'FAILED'] else None,
                            'beneficiary': {
                                'name': data['account_holder_name'],
                                'account_number': data['account_number'],
                                'ifsc_code': data['ifsc_code'],
                                'bank_name': data['bank_name']
                            }
                        }), 200
                    else:
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (mmp_result.get('message', 'Payout failed'), txn_id))
                        conn.commit()
                        
                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': mmp_result.get('message')
                        }), 400

                elif pg_partner_upper == 'CLOCKSPAY':
                    # Use ClocksPay for payout (IMPS)
                    clockspay_result = clockspay_payout_service.call_payout_api(
                        account_number=data['account_number'],
                        ifsc_code=data['ifsc_code'],
                        bank_name=data['bank_name'],
                        merchant_order_id=reference_id,
                        amount=net_amount_to_bank,
                        payee_name=data['account_holder_name'],
                        mobile=bene_mobile or '9999999999',
                        mode='IMPS'
                    )

                    if clockspay_result['success']:
                        status = clockspay_result.get('status', 'INITIATED')

                        print(f"ClocksPay payout initiated - Status: {status}, Merchant Order ID: {reference_id}")

                        # Deduct wallet ONLY if status is SUCCESS
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_deduction,
                                description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, txn_id))
                        elif status == 'FAILED':
                            # No wallet deduction for failed transactions
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, txn_id))
                        else:
                            # PENDING/INITIATED - wallet will be deducted later when status becomes SUCCESS
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, txn_id))

                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from API
                        if status == 'INITIATED':
                            print(f"Checking status from ClocksPay for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = clockspay_payout_service.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"ClocksPay status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                # Deduct wallet if status changed to SUCCESS
                                if updated_status == 'SUCCESS' and status != 'SUCCESS':
                                    debit_result = wallet_svc.debit_merchant_wallet(
                                        merchant_id=merchant_id,
                                        amount=total_deduction,
                                        description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                        reference_id=txn_id
                                    )
                                    
                                    if debit_result['success']:
                                        print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        # Get current wallet balance
                        cursor.execute("""
                            SELECT settled_balance, unsettled_balance
                            FROM merchant_wallet
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        current_wallet = cursor.fetchone()
                        current_balance = float(current_wallet['settled_balance']) if current_wallet else 0.00
                        
                        conn.close()

                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully' if status != 'SUCCESS' else 'Payout completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'order_id': data['order_id'],
                            'requested_amount': amount,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_deduction,
                            'amount_to_beneficiary': net_amount_to_bank,
                            'status': status,
                            'wallet_balance': current_balance,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None,
                            'beneficiary': {
                                'name': data['account_holder_name'],
                                'account_number': data['account_number'],
                                'ifsc_code': data['ifsc_code'],
                                'bank_name': data['bank_name']
                            }
                        }), 200
                    else:
                        # No wallet deduction happened, so no refund needed
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = 'FAILED', error_message = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        """, (clockspay_result.get('message', 'ClocksPay payout failed'), txn_id))
                        conn.commit()

                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': clockspay_result.get('message')
                        }), 400

                elif pg_partner_upper == 'ALOPNA':
                    # Use Alopna for payout (IMPS)
                    alopna_result = alopna_service.call_payout_api(
                        account_number=data['account_number'],
                        ifsc_code=data['ifsc_code'],
                        bank_name=data['bank_name'],
                        merchant_order_id=reference_id,
                        amount=net_amount_to_bank,
                        payee_name=data['account_holder_name'],
                        email=bene_email or 'merchant@orchpay.in',
                        mobile=bene_mobile or '9999999999',
                        mode='IMPS'
                    )
                    
                    if alopna_result['success']:
                        status = alopna_result.get('status', 'INITIATED')
                        pg_txn_id_resp = alopna_result.get('alopna_txn_id', '')
                        utr = alopna_result.get('utr', '')
                        
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_wallet_deduction,
                                description=f"Payout: ₹{net_amount_to_bank:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions 
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        elif status == 'FAILED':
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        else:
                            cursor.execute("""
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        
                        conn.commit()
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'requested_amount': net_amount_to_bank,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_wallet_deduction,
                            'status': status
                        }), 200
                    else:
                        cursor.execute("""
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE txn_id = %s
                        """, (alopna_result.get('message', 'Payout failed'), txn_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': alopna_result.get('message')
                        }), 400
                
                elif pg_partner_upper == 'RISEXPAY':

                    # Use Risexpay for payout (IMPS)
                    result = risexpay_payout_service.call_payout_api(
                        account_number=data['account_number'],
                        ifsc_code=data['ifsc_code'],
                        bank_name=data['bank_name'],
                        merchant_order_id=reference_id,
                        amount=net_amount_to_bank,  # Send full net amount to user bank
                        payee_name=data['account_holder_name'],
                        email=bene_email or 'merchant@orchpay.in',
                        mobile=bene_mobile or '9999999999',
                        mode='IMPS'
                    )

                    if result['success']:
                        status = result.get('status', 'INITIATED')
                        pg_txn_id_resp = result.get('pg_txn_id', '')
                        utr = result.get('utr', '')

                        print(f"Risexpay payout initiated - Status: {status}, PG Txn ID: {pg_txn_id_resp}, Merchant Order ID: {reference_id}")

                        # Deduct wallet ONLY if status is SUCCESS
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_deduction,
                                description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        elif status == 'FAILED':
                            # No wallet deduction for failed transactions
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        else:
                            # PENDING/INITIATED - wallet will be deducted later when status becomes SUCCESS
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))

                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from API
                        if status == 'INITIATED':
                            print(f"Checking status from Risexpay for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = risexpay_payout_service.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"Risexpay status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                # Deduct wallet if status changed to SUCCESS
                                if updated_status == 'SUCCESS' and status != 'SUCCESS':
                                    debit_result = wallet_svc.debit_merchant_wallet(
                                        merchant_id=merchant_id,
                                        amount=total_deduction,
                                        description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                        reference_id=txn_id
                                    )
                                    
                                    if debit_result['success']:
                                        print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        # Get current wallet balance
                        cursor.execute("""
                            SELECT settled_balance, unsettled_balance
                            FROM merchant_wallet
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        current_wallet = cursor.fetchone()
                        current_balance = float(current_wallet['settled_balance']) if current_wallet else 0.00
                        
                        conn.close()

                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully' if status != 'SUCCESS' else 'Payout completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'order_id': data['order_id'],
                            'requested_amount': amount,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_deduction,
                            'amount_to_beneficiary': net_amount_to_bank,
                            'status': status,
                            'wallet_balance': current_balance,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None,
                            'beneficiary': {
                                    'name': data['account_holder_name'],
                                    'account_number': data['account_number'],
                                    'ifsc_code': data['ifsc_code'],
                                    'bank_name': data['bank_name']
                            }
                        }), 200
                    else:
                        # No wallet deduction happened, so no refund needed
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = 'FAILED', error_message = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        """, (result.get('message', 'Risexpay payout failed'), txn_id))
                        conn.commit()

                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': result.get('message')
                        }), 400
                
                elif pg_partner_upper == 'ORO':
                    # Use ORO for payout
                    oro_result = oro_payout_service.call_payout_api(
                        account_number=data['account_number'],
                        ifsc_code=data['ifsc_code'],
                        bank_name=data.get('bank_name', ''),
                        merchant_order_id=reference_id,
                        amount=net_amount_to_bank,
                        payee_name=data.get('account_holder_name', ''),
                        email=bene_email or merchant.get('email', ''),
                        mobile=bene_mobile or merchant.get('mobile', '')
                    )
                    
                    if oro_result['success']:
                        status = oro_result.get('status', 'INITIATED')
                        pg_txn_id_resp = oro_result.get('pg_txn_id', '')
                        utr = oro_result.get('utr', '')
                        
                        print(f"ORO payout initiated - Status: {status}, PG Txn ID: {pg_txn_id_resp}, Merchant Order ID: {reference_id}")
                        
                        # Deduct wallet ONLY if status is SUCCESS
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_deduction,
                                description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        elif status == 'FAILED':
                            # No wallet deduction for failed transactions
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        else:
                            # PENDING/INITIATED - wallet will be deducted later when status becomes SUCCESS
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        
                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from API
                        if status == 'INITIATED':
                            print(f"Checking status from ORO for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = oro_payout_service.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"ORO status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                # Deduct wallet if status changed to SUCCESS
                                if updated_status == 'SUCCESS' and status != 'SUCCESS':
                                    debit_result = wallet_svc.debit_merchant_wallet(
                                        merchant_id=merchant_id,
                                        amount=total_deduction,
                                        description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                        reference_id=txn_id
                                    )
                                    
                                    if debit_result['success']:
                                        print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        # Get current wallet balance
                        cursor.execute("""
                            SELECT settled_balance, unsettled_balance
                            FROM merchant_wallet
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        current_wallet = cursor.fetchone()
                        current_balance = float(current_wallet['settled_balance']) if current_wallet else 0.00
                        
                        conn.close()

                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully' if status != 'SUCCESS' else 'Payout completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'order_id': data['order_id'],
                            'requested_amount': amount,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_deduction,
                            'amount_to_beneficiary': net_amount_to_bank,
                            'status': status,
                            'wallet_balance': current_balance,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None,
                            'beneficiary': {
                                    'name': data['account_holder_name'],
                                    'account_number': data['account_number'],
                                    'ifsc_code': data['ifsc_code'],
                                    'bank_name': data['bank_name']
                            }
                        }), 200
                    else:
                        # No wallet deduction happened, so no refund needed
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = 'FAILED', error_message = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        """, (oro_result.get('message', 'ORO payout failed'), txn_id))
                        conn.commit()

                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': oro_result.get('message')
                        }), 400

                elif pg_partner_upper == 'OQPAY':
                    # Use OQPay for payout (IMPS)
                    oqpay_result = oqpay_payout_service.call_payout_api(
                        account_number=data['account_number'],
                        ifsc_code=data['ifsc_code'],
                        bank_name=data['bank_name'],
                        merchant_order_id=reference_id,
                        amount=net_amount_to_bank,  # Send full net amount to user bank
                        payee_name=data['account_holder_name'],
                        email=bene_email or 'merchant@orchpay.in',
                        mobile=bene_mobile or '9999999999',
                        mode='IMPS'
                    )

                    if oqpay_result['success']:
                        status = oqpay_result.get('status', 'INITIATED')
                        pg_txn_id_resp = oqpay_result.get('pg_txn_id', '')
                        utr = oqpay_result.get('utr', '')

                        print(f"OQPay payout initiated - Status: {status}, PG Txn ID: {pg_txn_id_resp}, Merchant Order ID: {reference_id}")

                        # Deduct wallet ONLY if status is SUCCESS
                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_deduction,
                                description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                cursor.execute("""
                                    UPDATE payout_transactions
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        elif status == 'FAILED':
                            # No wallet deduction for failed transactions
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))
                        else:
                            # PENDING/INITIATED - wallet will be deducted later when status becomes SUCCESS
                            cursor.execute("""
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            """, (status, pg_txn_id_resp, utr, txn_id))

                        conn.commit()
                        
                        # If status is still INITIATED (pending), check status from API
                        if status == 'INITIATED':
                            print(f"Checking status from OQPay for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)  # Wait 2 seconds before checking
                            
                            status_result = oqpay_payout_service.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"OQPay status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                # Deduct wallet if status changed to SUCCESS
                                if updated_status == 'SUCCESS' and status != 'SUCCESS':
                                    debit_result = wallet_svc.debit_merchant_wallet(
                                        merchant_id=merchant_id,
                                        amount=total_deduction,
                                        description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                        reference_id=txn_id
                                    )
                                    
                                    if debit_result['success']:
                                        print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                                
                                # Update with latest status
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute("""
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                else:
                                    cursor.execute("""
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (updated_status, updated_utr, txn_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        # Get current wallet balance
                        cursor.execute("""
                            SELECT settled_balance, unsettled_balance
                            FROM merchant_wallet
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        current_wallet = cursor.fetchone()
                        current_balance = float(current_wallet['settled_balance']) if current_wallet else 0.00
                        
                        conn.close()

                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully' if status != 'SUCCESS' else 'Payout completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'order_id': data['order_id'],
                            'requested_amount': amount,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_deduction,
                            'amount_to_beneficiary': net_amount_to_bank,
                            'status': status,
                            'wallet_balance': current_balance,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None,
                            'beneficiary': {
                                    'name': data['account_holder_name'],
                                    'account_number': data['account_number'],
                                    'ifsc_code': data['ifsc_code'],
                                    'bank_name': data['bank_name']
                            }
                        }), 200
                    else:
                        # No wallet deduction happened, so no refund needed
                        cursor.execute("""
                            UPDATE payout_transactions
                            SET status = 'FAILED', error_message = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        """, (oqpay_result.get('message', 'OQPay payout failed'), txn_id))
                        conn.commit()

                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': oqpay_result.get('message')
                        }), 400
                
                else:
                    conn.close()
                    return jsonify({
                        'success': True,
                        'message': 'Payout request created',
                        'txn_id': txn_id,
                        'reference_id': reference_id,
                        'order_id': data['order_id'],
                        'requested_amount': amount,
                        'charges': charges['charge_amount'],
                        'total_deducted': total_deduction,
                        'amount_to_beneficiary': net_amount_to_bank,
                        'status': 'INITIATED',
                        'beneficiary': {
                            'name': data['account_holder_name'],
                            'account_number': data['account_number'],
                            'ifsc_code': data['ifsc_code'],
                            'bank_name': data['bank_name']
                        }
                    }), 200

        except Exception as e:
            # DO NOT ROLLBACK - the INSERT was already committed at line 1247
            # Rolling back here would delete the payout record but wallet was already debited
            print(f"❌ Error in client_direct_payout after INSERT: {e}")
            import traceback
            traceback.print_exc()
            if conn:
                conn.close()
            # Return error but don't rollback the transaction
            return jsonify({'success': False, 'message': f'Payout processing error: {str(e)}'}), 500

    except Exception as e:
        print(f"❌ Error in client_direct_payout: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500



# Get Payout Report - Admin
@payout_bp.route('/admin/payout-report', methods=['GET'])
@jwt_required()
def get_admin_payout_report():
    """Get payout report with pagination (admin only)"""
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        offset = (page - 1) * limit
        
        # Get filter parameters
        merchant_id = request.args.get('merchant_id')
        status = request.args.get('status')
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        search = request.args.get('search')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Build main query with pagination
                query = """
                    SELECT 
                        pt.id,
                        pt.txn_id,
                        pt.merchant_id,
                        pt.reference_id,
                        pt.order_id,
                        pt.batch_id,
                        pt.amount,
                        pt.charge_amount,
                        pt.charge_type,
                        pt.net_amount,
                        pt.bene_name,
                        pt.bene_email,
                        pt.bene_mobile,
                        pt.bene_bank,
                        pt.ifsc_code,
                        pt.account_no,
                        pt.vpa,
                        pt.payment_type,
                        pt.purpose,
                        pt.status,
                        pt.pg_partner,
                        pt.pg_txn_id,
                        pt.bank_ref_no,
                        pt.utr,
                        pt.name_with_bank,
                        pt.name_match_score,
                        pt.error_message,
                        pt.remarks,
                        pt.callback_url,
                        pt.created_at,
                        pt.updated_at,
                        pt.completed_at,
                        m.full_name,
                        m.mobile,
                        m.full_name as payer_name
                    FROM payout_transactions pt
                    LEFT JOIN merchants m ON pt.merchant_id = m.merchant_id
                    WHERE 1=1
                """
                params = []
                
                if merchant_id:
                    query += " AND pt.merchant_id = %s"
                    params.append(merchant_id)
                
                if status:
                    query += " AND pt.status = %s"
                    params.append(status)
                
                # Add search filter
                if search:
                    query += """ AND (
                        pt.txn_id LIKE %s OR 
                        pt.reference_id LIKE %s OR 
                        pt.order_id LIKE %s OR
                        pt.merchant_id LIKE %s OR 
                        m.full_name LIKE %s OR
                        pt.bene_name LIKE %s OR
                        pt.account_no LIKE %s OR
                        pt.ifsc_code LIKE %s OR
                        pt.utr LIKE %s OR
                        pt.bank_ref_no LIKE %s
                    )"""
                    search_pattern = f"%{search}%"
                    params.extend([search_pattern] * 10)
                
                if from_date:
                    query += " AND DATE(pt.created_at) >= %s"
                    params.append(from_date)
                
                if to_date:
                    query += " AND DATE(pt.created_at) <= %s"
                    params.append(to_date)
                
                query += " ORDER BY pt.created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                payouts = cursor.fetchall()
                
                # Get total count with same filters
                count_query = """
                    SELECT COUNT(*) as total 
                    FROM payout_transactions pt
                    LEFT JOIN merchants m ON pt.merchant_id = m.merchant_id
                    WHERE 1=1
                """
                count_params = []
                
                if merchant_id:
                    count_query += " AND pt.merchant_id = %s"
                    count_params.append(merchant_id)
                
                if status:
                    count_query += " AND pt.status = %s"
                    count_params.append(status)
                
                if search:
                    count_query += """ AND (
                        pt.txn_id LIKE %s OR 
                        pt.reference_id LIKE %s OR 
                        pt.order_id LIKE %s OR
                        pt.merchant_id LIKE %s OR 
                        m.full_name LIKE %s OR
                        pt.bene_name LIKE %s OR
                        pt.account_no LIKE %s OR
                        pt.ifsc_code LIKE %s OR
                        pt.utr LIKE %s OR
                        pt.bank_ref_no LIKE %s
                    )"""
                    search_pattern = f"%{search}%"
                    count_params.extend([search_pattern] * 10)
                
                if from_date:
                    count_query += " AND DATE(pt.created_at) >= %s"
                    count_params.append(from_date)
                
                if to_date:
                    count_query += " AND DATE(pt.created_at) <= %s"
                    count_params.append(to_date)
                
                cursor.execute(count_query, count_params)
                total = cursor.fetchone()['total']
                
                # Format the data properly
                formatted_payouts = []
                for payout in payouts:
                    formatted_payout = {
                        'id': payout['id'],
                        'txn_id': payout['txn_id'],
                        'merchant_id': payout['merchant_id'],
                        'reference_id': payout['reference_id'],
                        'order_id': payout.get('order_id'),
                        'batch_id': payout['batch_id'],
                        'amount': float(payout['amount']) if payout['amount'] else 0.0,
                        'charge_amount': float(payout['charge_amount']) if payout['charge_amount'] else 0.0,
                        'charge_type': payout['charge_type'],
                        'net_amount': float(payout['net_amount']) if payout['net_amount'] else 0.0,
                        'bene_name': payout['bene_name'],
                        'bene_email': payout['bene_email'],
                        'bene_mobile': payout['bene_mobile'],
                        'bene_bank': payout['bene_bank'],
                        'ifsc_code': payout['ifsc_code'],
                        'account_no': payout['account_no'],
                        'vpa': payout['vpa'],
                        'payment_type': payout['payment_type'],
                        'purpose': payout['purpose'],
                        'status': payout['status'],
                        'pg_partner': payout['pg_partner'],
                        'pg_txn_id': payout['pg_txn_id'],
                        'bank_ref_no': payout['bank_ref_no'],
                        'utr': payout['utr'],
                        'name_with_bank': payout['name_with_bank'],
                        'name_match_score': payout['name_match_score'],
                        'error_message': payout['error_message'],
                        'remarks': payout['remarks'],
                        'callback_url': payout['callback_url'],
                        'created_at': payout['created_at'].strftime('%Y-%m-%d %H:%M:%S') if payout['created_at'] else None,
                        'updated_at': payout['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if payout['updated_at'] else None,
                        'completed_at': payout['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if payout['completed_at'] else None,
                        'full_name': payout['full_name'],
                        'mobile': payout['mobile'],
                        'payer_name': payout['payer_name']
                    }
                    formatted_payouts.append(formatted_payout)
            
                return jsonify({
                    'success': True, 
                    'data': formatted_payouts,
                    'pagination': {
                        'page': page,
                        'limit': limit,
                        'total': total,
                        'pages': (total + limit - 1) // limit
                    }
                }), 200
                
        finally:
            conn.close()
        
    except Exception as e:
        print(f"Error in get_admin_payout_report: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@payout_bp.route('/admin/payout-report/all', methods=['GET'])
@jwt_required()
def get_admin_payout_report_all():
    """Get ALL payout transactions (admin only) with filters - for download"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        with conn.cursor() as cursor:
            # Get filter parameters
            status = request.args.get('status')
            search = request.args.get('search')
            from_date = request.args.get('from_date')
            to_date = request.args.get('to_date')
            
            query = """
                SELECT 
                    pt.id,
                    pt.txn_id,
                    pt.merchant_id,
                    pt.admin_id,
                    pt.reference_id,
                    pt.order_id,
                    pt.batch_id,
                    pt.amount,
                    pt.charge_amount,
                    pt.charge_type,
                    pt.net_amount,
                    pt.bene_name,
                    pt.bene_email,
                    pt.bene_mobile,
                    pt.bene_bank,
                    pt.ifsc_code,
                    pt.account_no,
                    pt.vpa,
                    pt.payment_type,
                    pt.purpose,
                    pt.status,
                    pt.pg_partner,
                    pt.pg_txn_id,
                    pt.bank_ref_no,
                    pt.utr,
                    pt.name_with_bank,
                    pt.name_match_score,
                    pt.error_message,
                    pt.remarks,
                    pt.callback_url,
                    pt.created_at,
                    pt.updated_at,
                    pt.completed_at,
                    m.full_name,
                    m.mobile
                FROM payout_transactions pt
                LEFT JOIN merchants m ON pt.merchant_id = m.merchant_id
                WHERE 1=1
            """
            params = []
            
            if status:
                query += " AND pt.status = %s"
                params.append(status)
            
            if search:
                query += """ AND (
                    pt.txn_id LIKE %s OR
                    pt.reference_id LIKE %s OR
                    pt.order_id LIKE %s OR
                    pt.bene_name LIKE %s OR
                    pt.account_no LIKE %s OR
                    pt.ifsc_code LIKE %s OR
                    m.full_name LIKE %s
                )"""
                search_pattern = f"%{search}%"
                params.extend([search_pattern] * 7)
            
            if from_date:
                query += " AND DATE(pt.created_at) >= %s"
                params.append(from_date)
            
            if to_date:
                query += " AND DATE(pt.created_at) <= %s"
                params.append(to_date)
            
            query += " ORDER BY pt.created_at DESC"
            
            cursor.execute(query, params)
            payouts = cursor.fetchall()
            
            # Format the data
            formatted_payouts = []
            for payout in payouts:
                formatted_payout = {
                    'id': payout.get('id'),
                    'txn_id': payout.get('txn_id'),
                    'merchant_id': payout.get('merchant_id'),
                    'admin_id': payout.get('admin_id'),
                    'reference_id': payout.get('reference_id'),
                    'order_id': payout.get('order_id'),
                    'batch_id': payout.get('batch_id'),
                    'amount': float(payout['amount']) if payout.get('amount') else 0.0,
                    'charge_amount': float(payout['charge_amount']) if payout.get('charge_amount') else 0.0,
                    'charge_type': payout.get('charge_type'),
                    'net_amount': float(payout['net_amount']) if payout.get('net_amount') else 0.0,
                    'bene_name': payout.get('bene_name'),
                    'bene_email': payout.get('bene_email'),
                    'bene_mobile': payout.get('bene_mobile'),
                    'bene_bank': payout.get('bene_bank'),
                    'ifsc_code': payout.get('ifsc_code'),
                    'account_no': payout.get('account_no'),
                    'vpa': payout.get('vpa'),
                    'payment_type': payout.get('payment_type'),
                    'purpose': payout.get('purpose'),
                    'status': payout.get('status'),
                    'pg_partner': payout.get('pg_partner'),
                    'pg_txn_id': payout.get('pg_txn_id'),
                    'bank_ref_no': payout.get('bank_ref_no'),
                    'utr': payout.get('utr') or payout.get('bank_ref_no'),
                    'name_with_bank': payout.get('name_with_bank'),
                    'name_match_score': payout.get('name_match_score'),
                    'error_message': payout.get('error_message'),
                    'remarks': payout.get('remarks'),
                    'callback_url': payout.get('callback_url'),
                    'created_at': payout['created_at'].strftime('%Y-%m-%d %H:%M:%S') if payout.get('created_at') else None,
                    'updated_at': payout['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if payout.get('updated_at') else None,
                    'completed_at': payout['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if payout.get('completed_at') else None,
                    'full_name': payout.get('full_name'),
                    'mobile': payout.get('mobile'),
                    'payer_name': payout.get('full_name') or 'Admin Payout'
                }
                formatted_payouts.append(formatted_payout)
        
        conn.close()
        return jsonify({'success': True, 'data': formatted_payouts, 'count': len(formatted_payouts)}), 200
    
    except Exception as e:
        print(f"Error in get_admin_payout_report_all: {e}")
        import traceback
        error_details = traceback.format_exc()
        print(f"Full traceback: {error_details}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@payout_bp.route('/admin/payout-report/today', methods=['GET'])
@jwt_required()
def get_admin_payout_report_today():
    """Get ALL payout transactions for today (admin only) - for report download"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        with conn.cursor() as cursor:
            query = """
                SELECT 
                    pt.*,
                    m.full_name,
                    m.mobile,
                    m.full_name as payer_name
                FROM payout_transactions pt
                LEFT JOIN merchants m ON pt.merchant_id = m.merchant_id
                WHERE DATE(pt.created_at) = CURDATE()
                ORDER BY pt.created_at DESC
            """
            
            cursor.execute(query)
            payouts = cursor.fetchall()
            
            # Format the data properly
            formatted_payouts = []
            for payout in payouts:
                formatted_payout = {
                    'id': payout['id'],
                    'txn_id': payout['txn_id'],
                    'merchant_id': payout['merchant_id'],
                    'reference_id': payout['reference_id'],
                    'order_id': payout.get('order_id'),
                    'batch_id': payout['batch_id'],
                    'amount': float(payout['amount']) if payout['amount'] else 0.0,
                    'charge_amount': float(payout['charge_amount']) if payout['charge_amount'] else 0.0,
                    'charge_type': payout['charge_type'],
                    'net_amount': float(payout['net_amount']) if payout['net_amount'] else 0.0,
                    'bene_name': payout['bene_name'],
                    'bene_email': payout['bene_email'],
                    'bene_mobile': payout['bene_mobile'],
                    'bene_bank': payout['bene_bank'],
                    'ifsc_code': payout['ifsc_code'],
                    'account_no': payout['account_no'],
                    'vpa': payout['vpa'],
                    'payment_type': payout['payment_type'],
                    'purpose': payout['purpose'],
                    'status': payout['status'],
                    'pg_partner': payout['pg_partner'],
                    'pg_txn_id': payout['pg_txn_id'],
                    'bank_ref_no': payout['bank_ref_no'],
                    'utr': payout['utr'],
                    'name_with_bank': payout['name_with_bank'],
                    'name_match_score': payout['name_match_score'],
                    'error_message': payout['error_message'],
                    'remarks': payout['remarks'],
                    'callback_url': payout['callback_url'],
                    'created_at': payout['created_at'].strftime('%Y-%m-%d %H:%M:%S') if payout['created_at'] else None,
                    'updated_at': payout['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if payout['updated_at'] else None,
                    'completed_at': payout['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if payout['completed_at'] else None,
                    'full_name': payout['full_name'],
                    'mobile': payout['mobile'],
                    'payer_name': payout['payer_name']
                }
                formatted_payouts.append(formatted_payout)
        
        conn.close()
        return jsonify({'success': True, 'data': formatted_payouts, 'count': len(formatted_payouts)}), 200
        
    except Exception as e:
        print(f"Error in get_admin_payout_report_today: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


# Get Pending Payouts - Admin
@payout_bp.route('/admin/pending-payouts', methods=['GET'])
@jwt_required()
def get_pending_payouts():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT pt.*, m.full_name, m.mobile
                FROM payout_transactions pt
                LEFT JOIN merchants m ON pt.merchant_id = m.merchant_id
                WHERE pt.status IN ('FAILED', 'INITIATED', 'INPROCESS')
                ORDER BY pt.created_at DESC
            """)
            payouts = cursor.fetchall()
        
        conn.close()
        return jsonify({'success': True, 'data': payouts}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Get Admin Wallet Overview
@payout_bp.route('/admin/wallet-overview', methods=['GET'])
@jwt_required()
def get_admin_wallet_overview():
    try:
        admin_id = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM admin_wallet WHERE admin_id = %s
            """, (admin_id,))
            wallet = cursor.fetchone()
            
            if not wallet:
                wallet = {'main_balance': 0, 'unsettled_balance': 0}
        
        conn.close()
        return jsonify({'success': True, 'data': wallet}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Get Admin Wallet Statement
@payout_bp.route('/admin/wallet-statement', methods=['GET'])
@jwt_required()
def get_admin_wallet_statement():
    try:
        admin_id = get_jwt_identity()
        wallet_type = request.args.get('wallet_type', 'MAIN')
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        with conn.cursor() as cursor:
            query = """
                SELECT * FROM admin_wallet_transactions
                WHERE admin_id = %s AND wallet_type = %s
            """
            params = [admin_id, wallet_type]
            
            if from_date:
                query += " AND DATE(created_at) >= %s"
                params.append(from_date)
            
            if to_date:
                query += " AND DATE(created_at) <= %s"
                params.append(to_date)
            
            query += " ORDER BY created_at DESC"
            
            cursor.execute(query, params)
            transactions = cursor.fetchall()
        
        conn.close()
        return jsonify({'success': True, 'data': transactions}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Get Client Wallet Statement (Unsettled)
@payout_bp.route('/client/wallet-statement', methods=['GET'])
@jwt_required()
def get_client_wallet_statement():
    try:
        merchant_id = get_jwt_identity()
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        with conn.cursor() as cursor:
            query = """
                SELECT * FROM wallet_transactions
                WHERE merchant_id = %s
            """
            params = [merchant_id]
            
            if from_date:
                query += " AND DATE(created_at) >= %s"
                params.append(from_date)
            
            if to_date:
                query += " AND DATE(created_at) <= %s"
                params.append(to_date)
            
            query += " ORDER BY created_at DESC"
            
            cursor.execute(query, params)
            transactions = cursor.fetchall()
        
        conn.close()
        return jsonify({'success': True, 'data': transactions}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# Get Fund Requests - Client view
@payout_bp.route('/client/fund-requests', methods=['GET'])
@jwt_required()
def get_client_fund_requests():
    try:
        merchant_id = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM fund_requests
                WHERE merchant_id = %s
                ORDER BY requested_at DESC
            """, (merchant_id,))
            
            requests_list = cursor.fetchall()
        
        conn.close()
        return jsonify({'success': True, 'data': requests_list}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Get Unsettled Wallet Balance - Client
@payout_bp.route('/client/unsettled-wallet', methods=['GET'])
@jwt_required()
def get_unsettled_wallet():
    try:
        merchant_id = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT balance FROM merchant_unsettled_wallet WHERE merchant_id = %s
            """, (merchant_id,))
            wallet = cursor.fetchone()
            
            if not wallet:
                wallet = {'balance': 0}
        
        conn.close()
        return jsonify({'success': True, 'data': wallet}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# Get Payout Report - Client
@payout_bp.route('/client/report', methods=['GET'])
@jwt_required()
def get_client_payout_report():
    """Get payout report for merchant with search and date filters"""
    try:
        merchant_id = get_jwt_identity()
        status = request.args.get('status')
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        search = request.args.get('search')  # New: search parameter

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        with conn.cursor() as cursor:
            query = """
                SELECT
                    pt.id,
                    pt.txn_id,
                    pt.merchant_id,
                    pt.reference_id,
                    pt.order_id,
                    pt.batch_id,
                    pt.amount,
                    pt.charge_amount,
                    pt.charge_type,
                    pt.net_amount,
                    pt.bene_name,
                    pt.bene_email,
                    pt.bene_mobile,
                    pt.bene_bank,
                    pt.ifsc_code,
                    pt.account_no,
                    pt.vpa,
                    pt.payment_type,
                    pt.purpose,
                    pt.status,
                    pt.pg_partner,
                    pt.pg_txn_id,
                    pt.bank_ref_no,
                    pt.utr,
                    pt.name_with_bank,
                    pt.name_match_score,
                    pt.error_message,
                    pt.remarks,
                    pt.callback_url,
                    pt.created_at,
                    pt.updated_at,
                    pt.completed_at,
                    m.full_name,
                    m.mobile
                FROM payout_transactions pt
                LEFT JOIN merchants m ON pt.merchant_id = m.merchant_id
                WHERE pt.merchant_id = %s
            """
            params = [merchant_id]

            if status:
                query += " AND pt.status = %s"
                params.append(status)

            # Add search filter (searches across multiple fields)
            if search:
                query += """ AND (
                    pt.txn_id LIKE %s OR
                    pt.reference_id LIKE %s OR
                    pt.order_id LIKE %s OR
                    pt.bene_name LIKE %s OR
                    pt.account_no LIKE %s OR
                    pt.ifsc_code LIKE %s OR
                    pt.utr LIKE %s OR
                    pt.bank_ref_no LIKE %s
                )"""
                search_pattern = f"%{search}%"
                params.extend([search_pattern] * 8)

            if from_date:
                query += " AND DATE(pt.created_at) >= %s"
                params.append(from_date)

            if to_date:
                query += " AND DATE(pt.created_at) <= %s"
                params.append(to_date)

            query += " ORDER BY pt.created_at DESC LIMIT 100"

            cursor.execute(query, params)
            payouts = cursor.fetchall()

            # Format the data properly
            formatted_payouts = []
            for payout in payouts:
                formatted_payout = {
                    'id': payout['id'],
                    'txn_id': payout['txn_id'],
                    'merchant_id': payout['merchant_id'],
                    'reference_id': payout['reference_id'],
                    'order_id': payout.get('order_id'),
                    'batch_id': payout['batch_id'],
                    'amount': float(payout['amount']) if payout['amount'] else 0.0,
                    'charge_amount': float(payout['charge_amount']) if payout['charge_amount'] else 0.0,
                    'charge_type': payout['charge_type'],
                    'net_amount': float(payout['net_amount']) if payout['net_amount'] else 0.0,
                    'bene_name': payout['bene_name'],
                    'bene_email': payout['bene_email'],
                    'bene_mobile': payout['bene_mobile'],
                    'bene_bank': payout['bene_bank'],
                    'ifsc_code': payout['ifsc_code'],
                    'account_no': payout['account_no'],
                    'vpa': payout['vpa'],
                    'payment_type': payout['payment_type'],
                    'purpose': payout['purpose'],
                    'status': payout['status'],
                    'pg_partner': 'XES' if payout['pg_partner'] == 'RISEXPAY' else payout['pg_partner'],
                    'pg_txn_id': payout['pg_txn_id'],
                    'bank_ref_no': payout['bank_ref_no'],
                    'utr': payout['utr'],
                    'name_with_bank': payout['name_with_bank'],
                    'name_match_score': payout['name_match_score'],
                    'error_message': payout['error_message'],
                    'remarks': payout['remarks'],
                    'callback_url': payout['callback_url'],
                    'created_at': payout['created_at'].strftime('%Y-%m-%d %H:%M:%S') if payout['created_at'] else None,
                    'updated_at': payout['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if payout['updated_at'] else None,
                    'completed_at': payout['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if payout['completed_at'] else None,
                    'full_name': payout['full_name'],
                    'mobile': payout['mobile']
                }
                formatted_payouts.append(formatted_payout)

        conn.close()
        return jsonify({'success': True, 'data': formatted_payouts}), 200

    except Exception as e:
        print(f"Error in get_client_payout_report: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@payout_bp.route('/client/report/all', methods=['GET'])
@jwt_required()
def get_client_payout_report_all():
    """Get ALL payout report for merchant (for download) with filters"""
    try:
        merchant_id = get_jwt_identity()
        status = request.args.get('status')
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        search = request.args.get('search')

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        with conn.cursor() as cursor:
            query = """
                SELECT
                    pt.id,
                    pt.txn_id,
                    pt.merchant_id,
                    pt.reference_id,
                    pt.order_id,
                    pt.batch_id,
                    pt.amount,
                    pt.charge_amount,
                    pt.charge_type,
                    pt.net_amount,
                    pt.bene_name,
                    pt.bene_email,
                    pt.bene_mobile,
                    pt.bene_bank,
                    pt.ifsc_code,
                    pt.account_no,
                    pt.vpa,
                    pt.payment_type,
                    pt.purpose,
                    pt.status,
                    pt.pg_partner,
                    pt.pg_txn_id,
                    pt.bank_ref_no,
                    pt.utr,
                    pt.name_with_bank,
                    pt.name_match_score,
                    pt.error_message,
                    pt.remarks,
                    pt.callback_url,
                    pt.created_at,
                    pt.updated_at,
                    pt.completed_at,
                    m.full_name,
                    m.mobile
                FROM payout_transactions pt
                LEFT JOIN merchants m ON pt.merchant_id = m.merchant_id
                WHERE pt.merchant_id = %s
            """
            params = [merchant_id]

            if status:
                query += " AND pt.status = %s"
                params.append(status)

            if search:
                query += """ AND (
                    pt.txn_id LIKE %s OR
                    pt.reference_id LIKE %s OR
                    pt.order_id LIKE %s OR
                    pt.bene_name LIKE %s OR
                    pt.account_no LIKE %s OR
                    pt.ifsc_code LIKE %s OR
                    pt.utr LIKE %s OR
                    pt.bank_ref_no LIKE %s
                )"""
                search_pattern = f"%{search}%"
                params.extend([search_pattern] * 8)
                search_pattern = f"%{search}%"
                params.extend([search_pattern] * 7)

            if from_date:
                query += " AND DATE(pt.created_at) >= %s"
                params.append(from_date)

            if to_date:
                query += " AND DATE(pt.created_at) <= %s"
                params.append(to_date)

            query += " ORDER BY pt.created_at DESC"

            cursor.execute(query, params)
            payouts = cursor.fetchall()

            formatted_payouts = []
            for payout in payouts:
                formatted_payout = {
                    'id': payout['id'],
                    'txn_id': payout['txn_id'],
                    'merchant_id': payout['merchant_id'],
                    'reference_id': payout['reference_id'],
                    'order_id': payout.get('order_id'),
                    'reference_id': payout['reference_id'],
                    'batch_id': payout['batch_id'],
                    'amount': float(payout['amount']) if payout['amount'] else 0.0,
                    'charge_amount': float(payout['charge_amount']) if payout['charge_amount'] else 0.0,
                    'charge_type': payout['charge_type'],
                    'net_amount': float(payout['net_amount']) if payout['net_amount'] else 0.0,
                    'bene_name': payout['bene_name'],
                    'bene_email': payout['bene_email'],
                    'bene_mobile': payout['bene_mobile'],
                    'bene_bank': payout['bene_bank'],
                    'ifsc_code': payout['ifsc_code'],
                    'account_no': payout['account_no'],
                    'vpa': payout['vpa'],
                    'payment_type': payout['payment_type'],
                    'purpose': payout['purpose'],
                    'status': payout['status'],
                    'pg_partner': 'XES' if payout['pg_partner'] == 'RISEXPAY' else payout['pg_partner'],
                    'pg_txn_id': payout['pg_txn_id'],
                    'bank_ref_no': payout['bank_ref_no'],
                    'utr': payout['utr'],
                    'name_with_bank': payout['name_with_bank'],
                    'name_match_score': payout['name_match_score'],
                    'error_message': payout['error_message'],
                    'remarks': payout['remarks'],
                    'callback_url': payout['callback_url'],
                    'created_at': payout['created_at'].strftime('%Y-%m-%d %H:%M:%S') if payout['created_at'] else None,
                    'updated_at': payout['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if payout['updated_at'] else None,
                    'completed_at': payout['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if payout['completed_at'] else None,
                    'full_name': payout['full_name'],
                    'mobile': payout['mobile']
                }
                formatted_payouts.append(formatted_payout)

        conn.close()
        return jsonify({'success': True, 'data': formatted_payouts, 'count': len(formatted_payouts)}), 200

    except Exception as e:
        print(f"Error in get_client_payout_report_all: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@payout_bp.route('/client/report/today', methods=['GET'])
@jwt_required()
def get_client_payout_report_today():
    """Get today's payout report for merchant (for download)"""
    try:
        merchant_id = get_jwt_identity()

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        with conn.cursor() as cursor:
            query = """
                SELECT
                    pt.id,
                    pt.txn_id,
                    pt.merchant_id,
                    pt.reference_id,
                    pt.order_id,
                    pt.batch_id,
                    pt.amount,
                    pt.charge_amount,
                    pt.charge_type,
                    pt.net_amount,
                    pt.bene_name,
                    pt.bene_email,
                    pt.bene_mobile,
                    pt.bene_bank,
                    pt.ifsc_code,
                    pt.account_no,
                    pt.vpa,
                    pt.payment_type,
                    pt.purpose,
                    pt.status,
                    pt.pg_partner,
                    pt.pg_txn_id,
                    pt.bank_ref_no,
                    pt.utr,
                    pt.name_with_bank,
                    pt.name_match_score,
                    pt.error_message,
                    pt.remarks,
                    pt.callback_url,
                    pt.created_at,
                    pt.updated_at,
                    pt.completed_at,
                    m.full_name,
                    m.mobile
                FROM payout_transactions pt
                LEFT JOIN merchants m ON pt.merchant_id = m.merchant_id
                WHERE pt.merchant_id = %s AND DATE(pt.created_at) = CURDATE()
                ORDER BY pt.created_at DESC
            """

            cursor.execute(query, [merchant_id])
            payouts = cursor.fetchall()

            formatted_payouts = []
            for payout in payouts:
                formatted_payout = {
                    'id': payout['id'],
                    'txn_id': payout['txn_id'],
                    'merchant_id': payout['merchant_id'],
                    'reference_id': payout['reference_id'],
                    'order_id': payout.get('order_id'),
                    'batch_id': payout['batch_id'],
                    'amount': float(payout['amount']) if payout['amount'] else 0.0,
                    'charge_amount': float(payout['charge_amount']) if payout['charge_amount'] else 0.0,
                    'charge_type': payout['charge_type'],
                    'net_amount': float(payout['net_amount']) if payout['net_amount'] else 0.0,
                    'bene_name': payout['bene_name'],
                    'bene_email': payout['bene_email'],
                    'bene_mobile': payout['bene_mobile'],
                    'bene_bank': payout['bene_bank'],
                    'ifsc_code': payout['ifsc_code'],
                    'account_no': payout['account_no'],
                    'vpa': payout['vpa'],
                    'payment_type': payout['payment_type'],
                    'purpose': payout['purpose'],
                    'status': payout['status'],
                    'pg_partner': 'XES' if payout['pg_partner'] == 'RISEXPAY' else payout['pg_partner'],
                    'pg_txn_id': payout['pg_txn_id'],
                    'bank_ref_no': payout['bank_ref_no'],
                    'utr': payout['utr'],
                    'name_with_bank': payout['name_with_bank'],
                    'name_match_score': payout['name_match_score'],
                    'error_message': payout['error_message'],
                    'remarks': payout['remarks'],
                    'callback_url': payout['callback_url'],
                    'created_at': payout['created_at'].strftime('%Y-%m-%d %H:%M:%S') if payout['created_at'] else None,
                    'updated_at': payout['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if payout['updated_at'] else None,
                    'completed_at': payout['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if payout['completed_at'] else None,
                    'full_name': payout['full_name'],
                    'mobile': payout['mobile']
                }
                formatted_payouts.append(formatted_payout)

        conn.close()
        return jsonify({'success': True, 'data': formatted_payouts, 'count': len(formatted_payouts)}), 200

    except Exception as e:
        print(f"Error in get_client_payout_report_today: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500



# Client/Merchant Status Check - Check payout status from Mudrape
@payout_bp.route('/client/check-status/<txn_id>', methods=['POST'])
@jwt_required()
def client_check_payout_status(txn_id):
    """
    Check payout status from any PG partner and update database automatically.
    This endpoint is for merchants to check their own payout transactions.
    Supports: Mudrape, PayTouch, TourQuest (with database updates)
    PayTouch2: Read-only status check (no database updates - handled by cron job)
    """
    try:
        merchant_id = get_jwt_identity()

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        with conn.cursor() as cursor:
            # Get transaction details - ensure it belongs to the merchant
            cursor.execute("""
                SELECT txn_id, reference_id, pg_partner, status, merchant_id, pg_txn_id, 
                       amount, utr, created_at, completed_at
                FROM payout_transactions
                WHERE txn_id = %s AND merchant_id = %s
            """, (txn_id, merchant_id))

            txn = cursor.fetchone()

            if not txn:
                conn.close()
                return jsonify({'success': False, 'message': 'Transaction not found or unauthorized'}), 404

            print(f"Merchant {merchant_id} checking status for {txn['txn_id']} - {txn['reference_id']} via {txn['pg_partner']}")

            # Check status based on PG partner
            if txn['pg_partner'] == 'Mudrape':
                status_result = mudrape_service.check_payout_status(txn['reference_id'])
            elif txn['pg_partner'] == 'PayTouch':
                status_result = paytouch_service.check_payout_status(
                    transaction_id=txn['pg_txn_id'],
                    external_ref=txn['reference_id']
                )
            elif txn['pg_partner'] == 'Paytouch2':
                # PayTouch2 status check - READ ONLY (don't update database)
                status_result = paytouch2_service.check_payout_status(
                    transaction_id=txn['pg_txn_id'],
                    external_ref=txn['reference_id']
                )
                
                if not status_result.get('success'):
                    conn.close()
                    return jsonify({
                        'success': False,
                        'message': status_result.get('message', 'Failed to check status from PayTouch2')
                    }), 400

                # For PayTouch2, return status without updating database
                paytouch2_status = status_result.get('status', 'PENDING')
                paytouch2_utr = status_result.get('utr')
                paytouch2_txn_id = status_result.get('transaction_id') or txn['pg_txn_id']

                print(f"PayTouch2 Status Check (READ ONLY): Status={paytouch2_status}, UTR={paytouch2_utr}, PG_TXN_ID={paytouch2_txn_id}")

                conn.close()
                return jsonify({
                    'success': True,
                    'message': 'PayTouch2 status retrieved successfully (read-only)',
                    'data': {
                        'txn_id': txn['txn_id'],
                        'reference_id': txn['reference_id'],
                        'amount': float(txn['amount']) if txn['amount'] else 0.0,
                        'status': txn['status'],  # Current database status
                        'paytouch2_status': paytouch2_status,  # Live PayTouch2 status
                        'utr': txn['utr'],  # Current database UTR
                        'paytouch2_utr': paytouch2_utr,  # Live PayTouch2 UTR
                        'pg_txn_id': txn['pg_txn_id'],
                        'paytouch2_txn_id': paytouch2_txn_id,  # Live PayTouch2 transaction ID
                        'pg_partner': 'XES' if txn['pg_partner'] == 'RISEXPAY' else txn['pg_partner'],
                        'created_at': txn['created_at'].strftime('%Y-%m-%d %H:%M:%S') if txn['created_at'] else None,
                        'completed_at': txn['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if txn['completed_at'] else None,
                        'note': 'PayTouch2 status is read-only. Database updates happen via callback or cron job.'
                    }
                }), 200
                
            elif txn['pg_partner'] == 'TourQuest':
                status_result = tourquest_service.check_payout_status(txn['reference_id'])
            elif txn['pg_partner'] == 'MAKEMYPAYMENT':
                status_result = makemypayment_payout_service.check_payout_status(merchant_reference_id=txn['reference_id'])
            elif txn['pg_partner'] in ['MAXPE', 'NODEPAY']:
                # Import get_payout_service inline if not already imported, but it usually is
                try:
                    from payout_routes import get_payout_service
                except ImportError:
                    pass
                payout_service_instance = get_payout_service(txn['pg_partner'])
                status_result = payout_service_instance.check_payout_status(merchant_order_id=txn['reference_id'])
            else:
                conn.close()
                return jsonify({
                    'success': False,
                    'message': f'Status check not supported for {txn["pg_partner"]}'
                }), 400

            if not status_result.get('success'):
                conn.close()
                return jsonify({
                    'success': False,
                    'message': status_result.get('message', f'Failed to check status from {txn["pg_partner"]}')
                }), 400

            new_status = status_result.get('status', 'INITIATED')
            utr = status_result.get('utr')
            completed_at_from_api = status_result.get('completed_at')
            created_at_from_api = status_result.get('created_at')
            pg_txn_id = status_result.get('transaction_id') or status_result.get('pg_txn_id') or txn['pg_txn_id']

            print(f"{txn['pg_partner']} returned: Status={new_status}, UTR={utr}, PG_TXN_ID={pg_txn_id}, Created={created_at_from_api}, Completed={completed_at_from_api}")

            # Update transaction with timestamps from PG partner
            if new_status in ['SUCCESS', 'FAILED']:
                if completed_at_from_api and created_at_from_api:
                    # Update both created_at and completed_at from API
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, pg_txn_id = %s, created_at = %s, completed_at = %s, updated_at = NOW()
                        WHERE txn_id = %s
                    """, (new_status, utr, pg_txn_id, created_at_from_api, completed_at_from_api, txn_id))
                elif completed_at_from_api:
                    # Update only completed_at
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, pg_txn_id = %s, completed_at = %s, updated_at = NOW()
                        WHERE txn_id = %s
                    """, (new_status, utr, pg_txn_id, completed_at_from_api, txn_id))
                else:
                    # Fallback to NOW()
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                        WHERE txn_id = %s
                    """, (new_status, utr, pg_txn_id, txn_id))
            else:
                # Status is still pending/initiated
                if created_at_from_api:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, pg_txn_id = %s, created_at = %s, updated_at = NOW()
                        WHERE txn_id = %s
                    """, (new_status, utr, pg_txn_id, created_at_from_api, txn_id))
                else:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, pg_txn_id = %s, updated_at = NOW()
                        WHERE txn_id = %s
                    """, (new_status, utr, pg_txn_id, txn_id))

            conn.commit()

            # Get updated transaction
            cursor.execute("""
                SELECT * FROM payout_transactions WHERE txn_id = %s
            """, (txn_id,))

            updated_txn = cursor.fetchone()

            conn.close()

            print(f"✓ Transaction {txn_id} checked successfully - Status: {new_status}, UTR: {utr}")

            return jsonify({
                'success': True,
                'message': 'Status checked and updated successfully',
                'data': {
                    'txn_id': updated_txn['txn_id'],
                    'reference_id': updated_txn['reference_id'],
                    'amount': float(updated_txn['amount']),
                    'status': updated_txn['status'],
                    'utr': updated_txn['utr'],
                    'pg_txn_id': updated_txn['pg_txn_id'],
                    'pg_partner': updated_txn['pg_partner'],
                    'created_at': updated_txn['created_at'].strftime('%Y-%m-%d %H:%M:%S') if updated_txn['created_at'] else None,
                    'completed_at': updated_txn['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if updated_txn['completed_at'] else None
                }
            }), 200

    except Exception as e:
        print(f"Error in client_check_payout_status: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500




# Manual Status Sync - Check single transaction status from Mudrape (Admin)
@payout_bp.route('/sync-status/<txn_id>', methods=['POST'])
@jwt_required()
def sync_transaction_status(txn_id):
    """Manually sync transaction status from Mudrape"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        with conn.cursor() as cursor:
            # Get transaction details
            cursor.execute("""
                SELECT txn_id, reference_id, pg_partner, status
                FROM payout_transactions
                WHERE txn_id = %s
            """, (txn_id,))
            
            txn = cursor.fetchone()
            
            if not txn:
                conn.close()
                return jsonify({'success': False, 'message': 'Transaction not found'}), 404
            
            if txn['pg_partner'] != 'Mudrape':
                conn.close()
                return jsonify({'success': False, 'message': 'Only Mudrape transactions can be synced'}), 400
            
            print(f"Manual sync requested for {txn['txn_id']} - {txn['reference_id']}")
            
            # Check status from Mudrape
            status_result = mudrape_service.check_payout_status(txn['reference_id'])
            
            if not status_result.get('success'):
                conn.close()
                return jsonify({
                    'success': False, 
                    'message': status_result.get('message', 'Failed to check status from Mudrape')
                }), 400
            
            new_status = status_result.get('status', 'INITIATED')
            utr = status_result.get('utr')
            completed_at_from_api = status_result.get('completed_at')
            created_at_from_api = status_result.get('created_at')
            
            print(f"Mudrape returned: Status={new_status}, UTR={utr}, Created={created_at_from_api}, Completed={completed_at_from_api}")
            
            # Update transaction with timestamps from Mudrape
            if new_status in ['SUCCESS', 'FAILED']:
                if completed_at_from_api and created_at_from_api:
                    # Update both created_at and completed_at from Mudrape
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, created_at = %s, completed_at = %s, updated_at = NOW()
                        WHERE txn_id = %s
                    """, (new_status, utr, created_at_from_api, completed_at_from_api, txn_id))
                elif completed_at_from_api:
                    # Update only completed_at
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, completed_at = %s, updated_at = NOW()
                        WHERE txn_id = %s
                    """, (new_status, utr, completed_at_from_api, txn_id))
                else:
                    # Fallback to NOW()
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                        WHERE txn_id = %s
                    """, (new_status, utr, txn_id))
            else:
                # Status is still pending/initiated
                if created_at_from_api:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, created_at = %s, updated_at = NOW()
                        WHERE txn_id = %s
                    """, (new_status, utr, created_at_from_api, txn_id))
                else:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = %s, utr = %s, updated_at = NOW()
                        WHERE txn_id = %s
                    """, (new_status, utr, txn_id))
            
            conn.commit()
            
            # Get updated transaction
            cursor.execute("""
                SELECT * FROM payout_transactions WHERE txn_id = %s
            """, (txn_id,))
            
            updated_txn = cursor.fetchone()
            
            conn.close()
            
            print(f"✓ Transaction {txn_id} synced successfully - Status: {new_status}, Created: {created_at_from_api}, Completed: {completed_at_from_api}")
            
            return jsonify({
                'success': True,
                'message': 'Status synced successfully',
                'data': updated_txn
            }), 200
            
    except Exception as e:
        print(f"Error in sync_transaction_status: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


# Get Payout Stats - Client
@payout_bp.route('/client/stats', methods=['GET'])
@jwt_required()
def get_client_payout_stats():
    """Get payout statistics for merchant with date ranges"""
    try:
        merchant_id = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        with conn.cursor() as cursor:
            # Get stats by status
            cursor.execute("""
                SELECT 
                    status,
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) as total_amount
                FROM payout_transactions
                WHERE merchant_id = %s
                GROUP BY status
            """, (merchant_id,))
            
            stats_by_status = cursor.fetchall()
            
            # Initialize stats
            stats = {
                'success': {'count': 0, 'amount': 0},
                'pending': {'count': 0, 'amount': 0},
                'failed': {'count': 0, 'amount': 0},
                'queued': {'count': 0, 'amount': 0}
            }
            
            # Map database results to stats
            for stat in stats_by_status:
                status = stat['status'].upper()  # Convert to uppercase for consistency
                if status == 'SUCCESS':
                    stats['success'] = {'count': stat['count'], 'amount': float(stat['total_amount'])}
                elif status in ['INITIATED', 'INPROCESS']:
                    stats['pending']['count'] += stat['count']
                    stats['pending']['amount'] += float(stat['total_amount'])
                elif status in ['FAILED', 'REVERSED']:
                    stats['failed']['count'] += stat['count']
                    stats['failed']['amount'] += float(stat['total_amount'])
                elif status == 'QUEUED':
                    stats['queued'] = {'count': stat['count'], 'amount': float(stat['total_amount'])}
            
            # Get today's stats
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as payout,
                    COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payout
                FROM payout_transactions
                WHERE merchant_id = %s AND DATE(created_at) = CURDATE()
            """, (merchant_id,))
            today = cursor.fetchone()
            
            # Get yesterday's stats
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as payout,
                    COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payout
                FROM payout_transactions
                WHERE merchant_id = %s AND DATE(created_at) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)
            """, (merchant_id,))
            yesterday = cursor.fetchone()
            
            # Get last 7 days stats
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as payout,
                    COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payout
                FROM payout_transactions
                WHERE merchant_id = %s AND DATE(created_at) >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            """, (merchant_id,))
            last7days = cursor.fetchone()
            
            # Get last 30 days stats
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as payout,
                    COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payout
                FROM payout_transactions
                WHERE merchant_id = %s AND DATE(created_at) >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            """, (merchant_id,))
            last30days = cursor.fetchone()
        
        conn.close()
        return jsonify({
            'success': True, 
            'stats': stats,
            'timeRanges': {
                'today': {
                    'payout': float(today['payout']),
                    'net_payout': float(today['net_payout'])
                },
                'yesterday': {
                    'payout': float(yesterday['payout']),
                    'net_payout': float(yesterday['net_payout'])
                },
                'last7days': {
                    'payout': float(last7days['payout']),
                    'net_payout': float(last7days['net_payout'])
                },
                'last30days': {
                    'payout': float(last30days['payout']),
                    'net_payout': float(last30days['net_payout'])
                }
            }
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


# Get Payout Stats - Admin
@payout_bp.route('/admin/stats', methods=['GET'])
@jwt_required()
def get_admin_payout_stats():
    """Get payout statistics for admin with date ranges"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        with conn.cursor() as cursor:
            # Get stats by status
            cursor.execute("""
                SELECT 
                    status,
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) as total_amount,
                    COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN charge_amount ELSE 0 END), 0) as total_payout_charges
                FROM payout_transactions
                GROUP BY status
            """)
            
            stats_by_status = cursor.fetchall()
            
            # Get total payout charges
            total_payout_charges = sum(float(stat.get('total_payout_charges', 0)) for stat in stats_by_status)
            
            # Initialize stats
            stats = {
                'success': {'count': 0, 'amount': 0},
                'pending': {'count': 0, 'amount': 0},
                'failed': {'count': 0, 'amount': 0},
                'queued': {'count': 0, 'amount': 0}
            }
            
            # Map database results to stats
            for stat in stats_by_status:
                status = stat['status'].upper()  # Convert to uppercase for consistency
                if status == 'SUCCESS':
                    stats['success'] = {'count': stat['count'], 'amount': float(stat['total_amount'])}
                elif status in ['INITIATED', 'INPROCESS']:
                    stats['pending']['count'] += stat['count']
                    stats['pending']['amount'] += float(stat['total_amount'])
                elif status in ['FAILED', 'REVERSED']:
                    stats['failed']['count'] += stat['count']
                    stats['failed']['amount'] += float(stat['total_amount'])
                elif status == 'QUEUED':
                    stats['queued'] = {'count': stat['count'], 'amount': float(stat['total_amount'])}
            
            # Get today's stats
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as payout,
                    COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payout
                FROM payout_transactions
                WHERE DATE(created_at) = CURDATE()
            """)
            today = cursor.fetchone()
            
            # Get yesterday's stats
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as payout,
                    COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payout
                FROM payout_transactions
                WHERE DATE(created_at) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)
            """)
            yesterday = cursor.fetchone()
            
            # Get last 7 days stats
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as payout,
                    COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payout
                FROM payout_transactions
                WHERE DATE(created_at) >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            """)
            last7days = cursor.fetchone()
            
            # Get last 30 days stats
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as payout,
                    COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payout
                FROM payout_transactions
                WHERE DATE(created_at) >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            """)
            last30days = cursor.fetchone()
        
        conn.close()
        return jsonify({
            'success': True, 
            'stats': stats,
            'totals': {
                'total_payout_charges': float(total_payout_charges)
            },
            'timeRanges': {
                'today': {
                    'payout': float(today['payout']),
                    'net_payout': float(today['net_payout'])
                },
                'yesterday': {
                    'payout': float(yesterday['payout']),
                    'net_payout': float(yesterday['net_payout'])
                },
                'last7days': {
                    'payout': float(last7days['payout']),
                    'net_payout': float(last7days['net_payout'])
                },
                'last30days': {
                    'payout': float(last30days['payout']),
                    'net_payout': float(last30days['net_payout'])
                }
            }
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
        return jsonify({'success': False, 'message': str(e)}), 500


# PayU Payout Token and Account Management APIs

@payout_bp.route('/admin/payu/token/generate', methods=['POST'])
@jwt_required()
def generate_payu_token():
    """Generate PayU payout access token"""
    try:
        result = payu_payout_svc.generate_access_token()
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Token generated successfully',
                'data': {
                    'access_token': result['access_token'][:20] + '...',  # Masked for security
                    'token_type': result.get('token_type'),
                    'expires_in': result.get('expires_in'),
                    'user_uuid': result.get('user_uuid')
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': result.get('error', 'Token generation failed')
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@payout_bp.route('/admin/payu/token/refresh', methods=['POST'])
@jwt_required()
def refresh_payu_token():
    """Refresh PayU payout access token"""
    try:
        result = payu_payout_svc.refresh_access_token()
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Token refreshed successfully',
                'data': {
                    'access_token': result['access_token'][:20] + '...'  # Masked for security
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': result.get('error', 'Token refresh failed')
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@payout_bp.route('/admin/payu/account/details', methods=['GET'])
@jwt_required()
def get_payu_account_details():
    """Get PayU payout account details"""
    try:
        result = payu_payout_svc.get_account_details()
        
        if result['success']:
            return jsonify({
                'success': True,
                'data': result['data']
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': result.get('error', 'Failed to get account details')
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@payout_bp.route('/admin/payu/transfer/status/<reference_id>', methods=['GET'])
@jwt_required()
def check_payu_transfer_status(reference_id):
    """Check PayU transfer status"""
    try:
        result = payout_svc.get_transaction_status(reference_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'data': result
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': result.get('error', 'Failed to check status')
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@payout_bp.route('/admin/payu/transfer/list', methods=['POST'])
@jwt_required()
def list_payu_transfers():
    """List PayU transfers with filters"""
    try:
        data = request.get_json()
        
        result = payu_payout_svc.check_transfer_status(
            merchant_ref_id=data.get('merchant_ref_id'),
            batch_id=data.get('batch_id'),
            transfer_status=data.get('transfer_status'),
            from_date=data.get('from_date'),
            to_date=data.get('to_date'),
            page=data.get('page', 1),
            page_size=data.get('page_size', 100)
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'data': result['data']
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': result.get('error', 'Failed to list transfers')
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# Client Direct Payout (with bank details in request)


# ============================================================================
# MERCHANT PAYOUT STATUS CHECK API WITH CLIENT ORDER ID
# ============================================================================

@payout_bp.route('/client/check-status-by-order-id/<order_id>', methods=['GET'])
@jwt_required()
def check_payout_status_by_order_id(order_id):
    """
    Check payout status by client order ID
    
    Merchant must be logged in and can only check their own transactions
    
    Example:
    GET /api/payout/client/check-status-by-order-id/ORDER12345
    Header: Authorization: Bearer <token>
    
    Response:
    {
        "success": true,
        "message": "Payout status retrieved successfully",
        "data": {
            "order_id": "ORDER12345",
            "reference_id": "DP2026040221520368FF8E",
            "txn_id": "TXN5074C9A5A1B5",
            "amount": 2015.0,
            "status": "SUCCESS",
            "pg_partner": "Pg",
            "utr": "609221495505",
            "created_at": "2026-04-02 21:52:03",
            "completed_at": "2026-04-02 21:57:23"
        }
    }
    """
    try:
        # Get merchant ID from JWT token
        merchant_id = get_jwt_identity()
        print(f"DEBUG: Checking payout status for merchant_id={merchant_id}, order_id={order_id}")
        
        if not order_id:
            return jsonify({
                'success': False,
                'message': 'Order ID is required'
            }), 400
        
        conn = get_db_connection()
        if not conn:
            print("ERROR: Database connection failed")
            return jsonify({
                'success': False,
                'message': 'Database connection failed'
            }), 500
        
        try:
            with conn.cursor() as cursor:
                # Query payout transaction by order_id and merchant_id
                query = """
                    SELECT 
                        order_id,
                        reference_id,
                        txn_id,
                        amount,
                        status,
                        pg_partner,
                        utr,
                        DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at,
                        DATE_FORMAT(completed_at, '%%Y-%%m-%%d %%H:%%i:%%s') as completed_at
                    FROM payout_transactions
                    WHERE order_id = %s AND merchant_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                print(f"DEBUG: Executing query with order_id={order_id}, merchant_id={merchant_id}")
                cursor.execute(query, (order_id, merchant_id))
                
                transaction = cursor.fetchone()
                print(f"DEBUG: Query result: {transaction}")
                
                if not transaction:
                    print(f"WARNING: Transaction not found for order_id={order_id}, merchant_id={merchant_id}")
                    return jsonify({
                        'success': False,
                        'message': 'Transaction not found'
                    }), 404
                
                # Live Status Check for MAKEMYPAYMENT and MAXPE
                status_result = {}
                if transaction['pg_partner'].upper() == 'MAKEMYPAYMENT':
                    print(f"DEBUG: Performing live status check for MAKEMYPAYMENT order {order_id}")
                    status_result = makemypayment_payout_service.check_payout_status(merchant_reference_id=transaction['reference_id'])
                elif transaction['pg_partner'].upper() in ['MAXPE', 'NODEPAY']:
                    print(f"DEBUG: Performing live status check for {transaction['pg_partner']} order {order_id}")
                    try:
                        from payout_routes import get_payout_service
                    except ImportError:
                        pass
                    payout_service_instance = get_payout_service(transaction['pg_partner'].upper())
                    status_result = payout_service_instance.check_payout_status(merchant_order_id=transaction['reference_id'])
                    
                if status_result.get('success'):
                        new_status = status_result.get('status', 'INITIATED')
                        utr = status_result.get('utr')
                        
                        # Only update if status changed or new UTR arrived
                        if new_status != transaction['status'] or (utr and utr != transaction['utr']):
                            import datetime
                            if new_status in ['SUCCESS', 'FAILED'] and transaction['status'] not in ['SUCCESS', 'FAILED']:
                                cursor.execute("""
                                    UPDATE payout_transactions 
                                    SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (new_status, utr, transaction['txn_id']))
                                transaction['completed_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                
                                # Deduct wallet if status transitioned to SUCCESS
                                if new_status == 'SUCCESS' and merchant_id:
                                    print("=" * 80)
                                    print("WALLET DEDUCTION - SUCCESS STATUS (MAKEMYPAYMENT Live Check)")
                                    print("=" * 80)
                                    
                                    cursor.execute("""
                                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                                        WHERE reference_id = %s AND txn_type = 'DEBIT'
                                    """, (transaction['txn_id'],))
                                    
                                    already_debited = cursor.fetchone()['count'] > 0
                                    
                                    if already_debited:
                                        print(f"⚠ Wallet already debited for this transaction - skipping")
                                    else:
                                        import wallet_service
                                        wallet_svc = wallet_service.wallet_service
                                        
                                        debit_result = wallet_svc.debit_merchant_wallet(
                                            merchant_id=merchant_id,
                                            amount=float(transaction['amount']) if transaction.get('amount') else 0,
                                            description=f"Payout completed (MAKEMYPAYMENT) - Ref: {transaction['reference_id']}",
                                            reference_id=transaction['txn_id']
                                        )
                                        
                                        if debit_result['success']:
                                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                                        else:
                                            print(f"❌ WALLET DEDUCTION FAILED: {debit_result['message']}")
                            else:
                                cursor.execute("""
                                    UPDATE payout_transactions 
                                    SET status = %s, utr = %s, updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (new_status, utr, transaction['txn_id']))
                            conn.commit()
                            
                            # Update local dict so the response uses new data
                            transaction['status'] = new_status
                            if utr:
                                transaction['utr'] = utr
                
                # Format response data
                response_data = {
                    'order_id': transaction['order_id'],
                    'reference_id': transaction['reference_id'],
                    'txn_id': transaction['txn_id'],
                    'amount': float(transaction['amount']),
                    'status': transaction['status'],
                    'pg_partner': transaction['pg_partner'],
                    'utr': transaction['utr'] if transaction['utr'] else None,
                    'created_at': transaction['created_at'],
                    'completed_at': transaction['completed_at'] if transaction['completed_at'] else None
                }
                
                print(f"SUCCESS: Returning payout status for order_id={order_id}")
                return jsonify({
                    'success': True,
                    'message': 'Payout status retrieved successfully',
                    'data': response_data
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"ERROR: Check payout status error: {e}")
        print(f"ERROR: Traceback: {error_trace}")
        return jsonify({
            'success': False,
            'message': 'Internal server error',
            'error': str(e)
        }), 500
