"""
Payin API Routes
Handles merchant payin operations through PayU, Mudrape, and Tourquest
"""

from flask import Blueprint, request, jsonify, redirect
from flask_jwt_extended import jwt_required, get_jwt_identity
from payu_service import payu_service
from mudrape_service import mudrape_service
from tourquest_service import tourquest_service
from vega_service import VegaService
from airpay_service import airpay_service
from payu_legalhalt_service import payu_legalhalt_service
from paytouchpayin_service import PaytouchpayinService
from skrillpe_service import skrillpe_service
from rang_service import RangService
from viyonapay_service import viyonapay_service, viyonapay_barringer_service
from moneyone_service import moneyone_service
from instantpesa_service import InstantPesaService
from maxpe_service import maxpe_service
from razorpay_service import razorpay_service
from paytm_service import paytm_service
from clockspay_service import clockspay_service
from risexpay_service import risexpay_service
from sectorpe_service import sectorpe_service
from oqpay_service import oqpay_service
from alopna_service import alopna_service
from nextpay_service import nextpay_service
from localpaisa_service import localpaisa_service
from titanexam_service import titanexam_service
from acceptpay_service import acceptpay_service
from hdfc_jvi_service import hdfc_jvi_service
from au_bank_service import au_bank_service
from oro_service import oro_service
from database import get_db_connection
from utils import decrypt_aes, encrypt_aes, validate_api_credentials
import json
import base64
import requests
from functools import wraps
from datetime import datetime

payin_bp = Blueprint('payin', __name__, url_prefix='/api/payin')

# Initialize services
vega_service = VegaService()
rang_service = RangService()
paytouchpayin_service = PaytouchpayinService()
instantpesa_service = InstantPesaService()

def require_api_credentials(f):
    """
    Decorator to validate API credentials (Authorization Key and Module Secret)
    Must be used after @jwt_required()
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get headers
        auth_key = request.headers.get('X-Authorization-Key')
        module_secret = request.headers.get('X-Module-Secret')
        
        # Get merchant ID from JWT
        merchant_id = get_jwt_identity()
        
        # Validate credentials
        is_valid, error_message, merchant_data = validate_api_credentials(
            auth_key, module_secret, merchant_id
        )
        
        if not is_valid:
            return jsonify({
                'success': False,
                'message': error_message or 'Invalid API credentials'
            }), 401
        
        # Store merchant data in request context for use in route
        request.merchant_data = merchant_data
        
        return f(*args, **kwargs)
    
    return decorated_function

@payin_bp.route('/order/create', methods=['POST'])
@jwt_required()
def create_payin_order():
    """
    Create payin order (for merchant dashboard)
    Requires: JWT token only (dashboard use)
    For external API use, use /api/v1/payin/order/create instead
    
    Expects encrypted payload with:
    - amount
    - orderid
    - payee_fname
    - payee_lname
    - payee_mobile
    - payee_email
    - callbackurl (optional)
    """
    try:
        current_merchant = get_jwt_identity()
        data = request.get_json()
        
        encrypted_data = data.get('data')
        if not encrypted_data:
            return jsonify({'success': False, 'message': 'Encrypted data required'}), 400
        
        # Get merchant AES credentials from database
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT aes_key, aes_iv FROM merchants WHERE merchant_id = %s
                """, (current_merchant,))
                
                merchant = cursor.fetchone()
                if not merchant:
                    return jsonify({'success': False, 'message': 'Merchant not found'}), 404
                
                # Decrypt payload
                decrypted_data = decrypt_aes(encrypted_data, merchant['aes_key'], merchant['aes_iv'])
                if not decrypted_data:
                    return jsonify({'success': False, 'message': 'Failed to decrypt data'}), 400
                
                order_data = json.loads(decrypted_data)
                
                # Validate required fields
                required_fields = ['amount', 'orderid', 'payee_fname', 'payee_mobile', 'payee_email']
                for field in required_fields:
                    if not order_data.get(field):
                        return jsonify({'success': False, 'message': f'{field} is required'}), 400
                
                # Check service routing to determine which gateway to use
                # First check for merchant-specific routing (SINGLE_USER)
                cursor.execute("""
                    SELECT pg_partner FROM service_routing
                    WHERE merchant_id = %s AND service_type = 'PAYIN' 
                    AND routing_type = 'SINGLE_USER' AND is_active = TRUE
                    ORDER BY priority ASC
                    LIMIT 1
                """, (current_merchant,))
                
                routing = cursor.fetchone()
                
                # If no merchant-specific routing, check for ALL_USERS routing
                if not routing:
                    cursor.execute("""
                        SELECT pg_partner FROM service_routing
                        WHERE merchant_id IS NULL AND service_type = 'PAYIN' 
                        AND routing_type = 'ALL_USERS' AND is_active = TRUE
                        ORDER BY priority ASC
                        LIMIT 1
                    """)
                    routing = cursor.fetchone()
                
                pg_partner = routing['pg_partner'].upper() if routing else 'PAYU'
                
                print(f"Creating payin order for merchant {current_merchant} using {pg_partner}")
                
                # Create payin order based on gateway
                if pg_partner == 'MUDRAPE':
                    # Use Mudrape for payin
                    result = mudrape_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'MONEYONE':
                    # Use MoneyOne for payin
                    result = moneyone_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'VEGA':
                    # Use Vega for payin
                    result = vega_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'AIRPAY':
                    # Use Airpay for payin
                    result = airpay_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'PAYTOUCHPAYIN':
                    # Use Paytouchpayin for payin
                    result = paytouchpayin_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'TOURQUEST':
                    # Use Tourquest for payin
                    result = tourquest_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'SKRILLPE':
                    # Use SkrillPe for payin
                    result = skrillpe_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'RANG':
                    # Use Rang for payin
                    result = rang_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'VIYONAPAY':
                    # Use VIYONAPAY for payin (Truaxis)
                    result = viyonapay_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'VIYONAPAY_BARRINGER':
                    # Use VIYONAPAY for payin (Barringer)
                    result = viyonapay_barringer_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'INSTANTPESA':
                    # Use InstantPesa for payin
                    result = instantpesa_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'ACCEPTPAY':
                    # Use Acceptpay for payin
                    result = acceptpay_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'MAXPE':
                    # Use Maxpe for payin
                    result = maxpe_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'RAZORPAY':
                    # Use Razorpay for payin
                    result = razorpay_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'PAYTM':
                    # Use Paytm for payin
                    result = paytm_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'CLOCKSPAY':
                    # Use ClocksPay for payin
                    result = clockspay_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'RISEXPAY':
                    # Use Risexpay for payin
                    result = risexpay_service.create_payin_order(current_merchant, order_data)
                elif pg_partner in ['PES', 'SECTORPE']:
                    # Use SectorPe for payin
                    result = sectorpe_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'OQPAY':
                    # Use OQPay for payin
                    result = oqpay_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'ALOPNA':
                    # Use Alopna for payin
                    result = alopna_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'NEXTPAY':
                    # Use Nextpay for payin
                    result = nextpay_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'LOCALPAISA':
                    # Use Localpaisa for payin
                    result = localpaisa_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'TITANEXAM':
                    # Use Titanexam for payin
                    result = titanexam_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'PAYU_LEGALHALT':
                    # Use PayU legalhalt S2S Intent for payin
                    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
                    device_info = request.headers.get('User-Agent', '')
                    result = payu_legalhalt_service.create_payin_order(current_merchant, order_data, client_ip, device_info)
                elif pg_partner == 'HDFC_JVI':
                    # Use HDFC JVI for payin
                    result = hdfc_jvi_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'AU_BANK':
                    # Use AU Bank for payin
                    result = au_bank_service.create_payin_order(current_merchant, order_data)
                elif pg_partner == 'ORO':
                    # Use ORO for payin
                    result = oro_service.create_payin_order(current_merchant, order_data)
                else:
                    # Use PayU for payin (default)
                    result = payu_service.create_payin_order(current_merchant, order_data)
                
                if not result.get('success'):
                    # Encrypt error response before returning (same as success response)
                    error_data = {
                        'error': result.get('message', 'Payment order creation failed'),
                        'pg_partner': pg_partner
                    }
                    encrypted_error = encrypt_aes(
                        json.dumps(error_data),
                        merchant['aes_key'],
                        merchant['aes_iv']
                    )
                    return jsonify({
                        'success': False,
                        'message': result.get('message', 'Payment order creation failed'),
                        'data': encrypted_error
                    }), 400
                
                # Encrypt response
                # Map payment_url to upi_link and intent_url for ViyonaPay
                # ViyonaPay returns payment_url which should be mapped to upi_link and intent_url
                payment_url_value = result.get('payment_url', '')
                payment_link_value = result.get('payment_link', '')
                
                # For ViyonaPay: map payment_url to upi_link and intent_url
                if pg_partner in ['VIYONAPAY', 'VIYONAPAY_BARRINGER'] and payment_url_value:
                    upi_link = payment_url_value
                    intent_url = payment_url_value
                    payment_link = payment_url_value
                elif pg_partner == 'PAYTOUCHPAYIN':
                    # Paytouchpayin returns redirect_url which is the QR payment page
                    upi_link = ''
                    intent_url = ''
                    payment_link = result.get('redirect_url', payment_link_value)
                elif pg_partner == 'INSTANTPESA':
                    # InstantPesa returns only upi_link
                    upi_link = result.get('upi_link', '')
                    intent_url = ''
                    payment_link = ''
                elif pg_partner == 'ACCEPTPAY':
                    # Acceptpay returns paymentLink
                    upi_link = result.get('payment_link', '')
                    intent_url = result.get('payment_link', '')
                    payment_link = result.get('payment_link', '')
                    result['vpa'] = upi_link
                elif pg_partner == 'LOCALPAISA':
                    upi_link = result.get('upi_link', '')
                    intent_url = upi_link
                    payment_link = payment_url_value
                    # Copy upi_link to all other link/QR parameters
                    result['qr_string'] = upi_link
                    result['qr_code_url'] = upi_link
                    result['vpa'] = upi_link
                else:
                    upi_link = result.get('upi_link', '')
                    intent_url = result.get('intent_url', '')
                    payment_link = payment_link_value
                
                response_data = {
                    'txn_id': result['txn_id'],
                    'order_id': result['order_id'],
                    'amount': result['amount'],
                    'charge_amount': result.get('charge_amount', 0),
                    'net_amount': result.get('net_amount', result['amount']),
                    'payment_params': result.get('payment_params', {}),
                    'qr_string': result.get('qr_string', ''),  # For Mudrape, Tourquest, and SkrillPe
                    'qr_code_url': result.get('qr_code_url', ''),  # For SkrillPe
                    'upi_link': upi_link,    # For Mudrape, Tourquest, and ViyonaPay
                    'payment_link': payment_link,  # For Tourquest, Vega, and ViyonaPay
                    'intent_url': intent_url,  # For SkrillPe and ViyonaPay
                    'tiny_url': result.get('tiny_url', ''),    # For SkrillPe new API
                    'expires_in': result.get('expires_in', 0),  # For Vega
                    'vpa': result.get('vpa', ''),  # For SkrillPe
                    'pg_partner': pg_partner
                }
                
                encrypted_response = encrypt_aes(
                    json.dumps(response_data),
                    merchant['aes_key'],
                    merchant['aes_iv']
                )
                
                return jsonify({
                    'success': True,
                    'message': 'Order created successfully',
                    'data': encrypted_response
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Create payin order error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@payin_bp.route('/callback/success', methods=['POST'])
def payin_callback_success():
    """PayU success callback"""
    try:
        response_data = request.form.to_dict()
        
        # Verify hash
        if not payu_service.verify_payment_hash(response_data):
            return jsonify({'success': False, 'message': 'Invalid hash'}), 400
        
        txn_id = response_data.get('txnid')
        status = response_data.get('status')
        pg_txn_id = response_data.get('mihpayid')
        bank_ref_no = response_data.get('bank_ref_num')
        payment_mode = response_data.get('mode')
        
        # Update transaction status
        success = payu_service.update_transaction_status(
            txn_id, 'SUCCESS', pg_txn_id, bank_ref_no, payment_mode
        )
        
        if success:
            # Get transaction details for callback
            txn_data = payu_service.get_transaction_status(txn_id)
            if txn_data:
                # Get merchant ID from transaction
                conn = get_db_connection()
                if conn:
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute("""
                                SELECT merchant_id, net_amount, charge_amount FROM payin_transactions WHERE txn_id = %s
                            """, (txn_id,))
                            txn_record = cursor.fetchone()
                            
                            if txn_record:
                                # Check if wallet already credited (idempotency)
                                cursor.execute("""
                                    SELECT COUNT(*) as count FROM merchant_wallet_transactions
                                    WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                                """, (txn_id,))
                                
                                wallet_already_credited = cursor.fetchone()['count'] > 0
                                
                                if wallet_already_credited:
                                    print(f"⚠ Wallet already credited for this transaction - skipping")
                                else:
                                    # Credit merchant unsettled wallet with net amount (after charges)
                                    from wallet_service import wallet_service as wallet_svc
                                    wallet_result = wallet_svc.credit_unsettled_wallet(
                                        merchant_id=txn_record['merchant_id'],
                                        amount=float(txn_record['net_amount']),
                                        description=f"PayIn received - {txn_id}",
                                        reference_id=txn_id
                                    )
                                    
                                    if wallet_result['success']:
                                        print(f"✓ Credited merchant unsettled wallet: ₹{txn_record['net_amount']}")
                                    else:
                                        print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")
                                    
                                    # Credit admin unsettled wallet with charge amount
                                    admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                        admin_id='admin',
                                        amount=float(txn_record['charge_amount']),
                                        description=f"PayIn charge - {txn_id}",
                                        reference_id=txn_id
                                    )
                                    
                                    if admin_wallet_result['success']:
                                        print(f"✓ Credited admin unsettled wallet: ₹{txn_record['charge_amount']}")
                                    else:
                                        print(f"✗ Failed to credit admin unsettled wallet: {admin_wallet_result.get('message')}")
                                
                                # Send callback to merchant
                                payu_service.send_callback_notification(
                                    txn_record['merchant_id'], txn_data
                                )
                    finally:
                        conn.close()
        
        return jsonify({'success': True, 'message': 'Payment successful'}), 200
        
    except Exception as e:
        print(f"Callback success error: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@payin_bp.route('/callback/failure', methods=['POST'])
def payin_callback_failure():
    """PayU failure callback"""
    try:
        response_data = request.form.to_dict()
        
        txn_id = response_data.get('txnid')
        status = response_data.get('status', 'FAILED')
        error_message = response_data.get('error_Message', 'Payment failed')
        
        # Update transaction status
        payu_service.update_transaction_status(
            txn_id, 'FAILED', error_message=error_message
        )
        
        return jsonify({'success': False, 'message': error_message}), 200
        
    except Exception as e:
        print(f"Callback failure error: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@payin_bp.route('/status/<txn_id>', methods=['GET'])
@jwt_required()
def get_payin_status(txn_id):
    """Get payin transaction status (for dashboard use)"""
    try:
        current_merchant = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM payin_transactions
                    WHERE txn_id = %s AND merchant_id = %s
                """, (txn_id, current_merchant))
                
                txn = cursor.fetchone()
                
                if not txn:
                    return jsonify({'success': False, 'message': 'Transaction not found'}), 404
                
                return jsonify({
                    'success': True,
                    'transaction': {
                        'txn_id': txn['txn_id'],
                        'order_id': txn['order_id'],
                        'amount': float(txn['amount']),
                        'charge_amount': float(txn['charge_amount']),
                        'net_amount': float(txn['net_amount']),
                        'status': txn['status'],
                        'payment_mode': txn.get('payment_mode'),
                        'created_at': txn['created_at'].isoformat() if txn.get('created_at') else None,
                        'completed_at': txn['completed_at'].isoformat() if txn.get('completed_at') else None
                    }
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Get payin status error: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@payin_bp.route('/verify-payment', methods=['POST'])
@jwt_required()
def verify_payment():
    """
    Verify payment status (for merchant API integration)
    Accepts encrypted request with order_id or txn_id
    Returns encrypted response with real-time payment status
    """
    try:
        current_merchant = get_jwt_identity()
        data = request.get_json()
        
        encrypted_data = data.get('data')
        if not encrypted_data:
            return jsonify({'success': False, 'message': 'Encrypted data required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Get merchant AES credentials
                cursor.execute("""
                    SELECT aes_key, aes_iv FROM merchants WHERE merchant_id = %s
                """, (current_merchant,))
                
                merchant = cursor.fetchone()
                if not merchant:
                    return jsonify({'success': False, 'message': 'Merchant not found'}), 404
                
                # Decrypt request
                decrypted_data = decrypt_aes(encrypted_data, merchant['aes_key'], merchant['aes_iv'])
                if not decrypted_data:
                    return jsonify({'success': False, 'message': 'Failed to decrypt data'}), 400
                
                request_data = json.loads(decrypted_data)
                
                # Get order_id or txn_id from request
                order_id = request_data.get('order_id') or request_data.get('orderid')
                txn_id = request_data.get('txn_id')
                
                if not order_id and not txn_id:
                    return jsonify({'success': False, 'message': 'order_id or txn_id required'}), 400
                
                # Find transaction
                if order_id:
                    cursor.execute("""
                        SELECT * FROM payin_transactions
                        WHERE order_id = %s AND merchant_id = %s
                        ORDER BY created_at DESC LIMIT 1
                    """, (order_id, current_merchant))
                else:
                    cursor.execute("""
                        SELECT * FROM payin_transactions
                        WHERE txn_id = %s AND merchant_id = %s
                    """, (txn_id, current_merchant))
                
                txn = cursor.fetchone()
                
                if not txn:
                    return jsonify({'success': False, 'message': 'Transaction not found'}), 404
                
                # Check real-time status from payment gateway if not final
                if txn['status'] in ['INITIATED', 'PENDING']:
                    pg_partner = txn.get('pg_partner', 'PayU').upper()
                    
                    print(f"Checking real-time status for {txn['txn_id']} from {pg_partner}")
                    
                    if pg_partner == 'MUDRAPE':
                        # Check status from Mudrape using order_id (RefID)
                        status_result = mudrape_service.check_payment_status(txn['order_id'])
                        
                        if status_result.get('success'):
                            new_status = status_result.get('status', 'INITIATED')
                            utr = status_result.get('utr')
                            pg_txn_id = status_result.get('txnId')
                            payment_mode = status_result.get('payment_mode', 'UPI')
                            created_at_ist = status_result.get('created_at')
                            completed_at_ist = status_result.get('completed_at')
                            
                            print(f"Mudrape Status Result: Status={new_status}, UTR={utr}, Created={created_at_ist}, Completed={completed_at_ist}")
                            
                            # Update transaction if status changed
                            if new_status != txn['status']:
                                if new_status == 'SUCCESS':
                                    # Update with timestamps from Mudrape
                                    if completed_at_ist:
                                        cursor.execute("""
                                            UPDATE payin_transactions
                                            SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                                                completed_at = %s, updated_at = NOW()
                                            WHERE txn_id = %s
                                        """, (new_status, utr, pg_txn_id, payment_mode, completed_at_ist, txn['txn_id']))
                                    else:
                                        cursor.execute("""
                                            UPDATE payin_transactions
                                            SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                                                completed_at = NOW(), updated_at = NOW()
                                            WHERE txn_id = %s
                                        """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                    
                                    # Check if wallet already credited (idempotency)
                                    cursor.execute("""
                                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                                        WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                                    """, (txn['txn_id'],))
                                    
                                    wallet_already_credited = cursor.fetchone()['count'] > 0
                                    
                                    if not wallet_already_credited:
                                        # Credit merchant unsettled wallet with net amount
                                        from wallet_service import wallet_service as wallet_svc
                                        wallet_result = wallet_svc.credit_unsettled_wallet(
                                            merchant_id=current_merchant,
                                            amount=float(txn['net_amount']),
                                            description=f"PayIn received (Mudrape) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )
                                        
                                        if wallet_result['success']:
                                            print(f"✓ Merchant unsettled wallet credited: ₹{txn['net_amount']}")
                                        else:
                                            print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")
                                        
                                        # Credit admin unsettled wallet with charge amount
                                        admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                            admin_id='admin',
                                            amount=float(txn['charge_amount']),
                                            description=f"PayIn charge (Mudrape) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )
                                        
                                        if admin_wallet_result['success']:
                                            print(f"✓ Admin unsettled wallet credited: ₹{txn['charge_amount']}")
                                        else:
                                            print(f"✗ Failed to credit admin unsettled wallet: {admin_wallet_result.get('message')}")
                                    else:
                                        print(f"⚠ Wallet already credited for this transaction - skipping")
                                    
                                elif new_status == 'FAILED':
                                    # Update with timestamps from Mudrape
                                    if completed_at_ist:
                                        cursor.execute("""
                                            UPDATE payin_transactions
                                            SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                                                completed_at = %s, updated_at = NOW()
                                            WHERE txn_id = %s
                                        """, (new_status, utr, pg_txn_id, payment_mode, completed_at_ist, txn['txn_id']))
                                    else:
                                        cursor.execute("""
                                            UPDATE payin_transactions
                                            SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                                                updated_at = NOW()
                                            WHERE txn_id = %s
                                        """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                else:
                                    # Still pending/initiated
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                
                                conn.commit()
                                
                                # Update txn dict with new values
                                txn['status'] = new_status
                                txn['bank_ref_no'] = utr  # Fixed: use bank_ref_no
                                txn['pg_txn_id'] = pg_txn_id
                                txn['payment_mode'] = payment_mode
                                if completed_at_ist:
                                    txn['completed_at'] = datetime.strptime(completed_at_ist, '%Y-%m-%d %H:%M:%S')
                                
                                print(f"✓ Updated transaction {txn['txn_id']} to {new_status}")
                    
                    elif pg_partner == 'TOURQUEST':
                        # Check status from Tourquest using pg_txn_id (clientrefno)
                        clientrefno = txn.get('pg_txn_id')
                        if clientrefno:
                            status_result = tourquest_service.check_payment_status(clientrefno)
                            
                            if status_result.get('success'):
                                new_status = status_result.get('status', 'INITIATED')
                                utr = status_result.get('utr')
                                pg_txn_id = status_result.get('txnId')
                                
                                print(f"Tourquest Status Result: Status={new_status}, UTR={utr}")
                                
                                # Update transaction if status changed
                                if new_status != txn['status']:
                                    if new_status == 'SUCCESS':
                                        cursor.execute("""
                                            UPDATE payin_transactions
                                            SET status = %s, bank_ref_no = %s, payment_mode = 'UPI',
                                                completed_at = NOW(), updated_at = NOW()
                                            WHERE txn_id = %s
                                        """, (new_status, utr, txn['txn_id']))
                                        
                                        # Check if wallet already credited (idempotency)
                                        cursor.execute("""
                                            SELECT COUNT(*) as count FROM merchant_wallet_transactions
                                            WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                                        """, (txn['txn_id'],))
                                        
                                        wallet_already_credited = cursor.fetchone()['count'] > 0
                                        
                                        if not wallet_already_credited:
                                            # Credit merchant unsettled wallet with net amount
                                            from wallet_service import wallet_service as wallet_svc
                                            wallet_result = wallet_svc.credit_unsettled_wallet(
                                                merchant_id=current_merchant,
                                                amount=float(txn['net_amount']),
                                                description=f"PayIn received (Tourquest) - {txn['order_id']}",
                                                reference_id=txn['txn_id']
                                            )
                                            
                                            if wallet_result['success']:
                                                print(f"✓ Merchant unsettled wallet credited: ₹{txn['net_amount']}")
                                            else:
                                                print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")
                                            
                                            # Credit admin unsettled wallet with charge amount
                                            admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                                admin_id='admin',
                                                amount=float(txn['charge_amount']),
                                                description=f"PayIn charge (Tourquest) - {txn['order_id']}",
                                                reference_id=txn['txn_id']
                                            )
                                            
                                            if admin_wallet_result['success']:
                                                print(f"✓ Admin unsettled wallet credited: ₹{txn['charge_amount']}")
                                            else:
                                                print(f"✗ Failed to credit admin unsettled wallet: {admin_wallet_result.get('message')}")
                                        else:
                                            print(f"⚠ Wallet already credited for this transaction - skipping")
                                        
                                    elif new_status == 'FAILED':
                                        cursor.execute("""
                                            UPDATE payin_transactions
                                            SET status = %s, bank_ref_no = %s, updated_at = NOW()
                                            WHERE txn_id = %s
                                        """, (new_status, utr, txn['txn_id']))
                                    else:
                                        cursor.execute("""
                                            UPDATE payin_transactions
                                            SET status = %s, bank_ref_no = %s, updated_at = NOW()
                                            WHERE txn_id = %s
                                        """, (new_status, utr, txn['txn_id']))
                                    
                                    conn.commit()
                                    
                                    # Update txn dict with new values
                                    txn['status'] = new_status
                                    txn['bank_ref_no'] = utr  # Fixed: use bank_ref_no
                                    
                                    print(f"✓ Updated transaction {txn['txn_id']} to {new_status}")
                    
                    elif pg_partner == 'AIRPAY':
                        # Check status from Airpay using order_id
                        status_result = airpay_service.check_payment_status(txn['order_id'])
                        
                        if status_result.get('success'):
                            new_status = status_result.get('status', 'INITIATED')
                            utr = status_result.get('utr')
                            pg_txn_id = status_result.get('txnId')
                            payment_mode = 'UPI'
                            
                            print(f"Airpay Status Result: Status={new_status}, UTR={utr}")
                            
                            # Update transaction if status changed
                            if new_status != txn['status']:
                                if new_status == 'SUCCESS':
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                                            completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                    
                                    # Check if wallet already credited (idempotency)
                                    cursor.execute("""
                                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                                        WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                                    """, (txn['txn_id'],))
                                    
                                    wallet_already_credited = cursor.fetchone()['count'] > 0
                                    
                                    if not wallet_already_credited:
                                        # Credit merchant unsettled wallet with net amount
                                        from wallet_service import wallet_service as wallet_svc
                                        wallet_result = wallet_svc.credit_unsettled_wallet(
                                            merchant_id=current_merchant,
                                            amount=float(txn['net_amount']),
                                            description=f"PayIn received (Airpay) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )
                                        
                                        if wallet_result['success']:
                                            print(f"✓ Merchant unsettled wallet credited: ₹{txn['net_amount']}")
                                        else:
                                            print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")
                                        
                                        # Credit admin unsettled wallet with charge amount
                                        admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                            admin_id='admin',
                                            amount=float(txn['charge_amount']),
                                            description=f"PayIn charge (Airpay) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )
                                        
                                        if admin_wallet_result['success']:
                                            print(f"✓ Admin unsettled wallet credited: ₹{txn['charge_amount']}")
                                        else:
                                            print(f"✗ Failed to credit admin unsettled wallet: {admin_wallet_result.get('message')}")
                                    else:
                                        print(f"⚠ Wallet already credited for this transaction - skipping")
                                    
                                elif new_status == 'FAILED':
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                                            completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                else:
                                    # Still pending/initiated
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                
                                conn.commit()
                                
                                # Update txn dict with new values
                                txn['status'] = new_status
                                txn['bank_ref_no'] = utr
                                txn['pg_txn_id'] = pg_txn_id
                                txn['payment_mode'] = payment_mode
                                
                                print(f"✓ Updated transaction {txn['txn_id']} to {new_status}")

                    elif pg_partner == 'NEXTPAY':
                        # Check status from Nextpay using txn_id
                        status_result = nextpay_service.check_payment_status(txn['pg_txn_id'])
                        
                        if status_result.get('success'):
                            new_status = status_result.get('status', 'INITIATED')
                            utr = status_result.get('utr')
                            pg_txn_id = status_result.get('txnId')
                            payment_mode = 'UPI'
                            
                            print(f"Nextpay Status Result: Status={new_status}, UTR={utr}")
                            
                            # Update transaction if status changed
                            if new_status != txn['status']:
                                if new_status == 'SUCCESS':
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                                            completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                    
                                    # Check if wallet already credited (idempotency)
                                    cursor.execute("""
                                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                                        WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                                    """, (txn['txn_id'],))
                                    
                                    wallet_already_credited = cursor.fetchone()['count'] > 0
                                    
                                    if not wallet_already_credited:
                                        # Credit merchant unsettled wallet with net amount
                                        from wallet_service import wallet_service as wallet_svc
                                        wallet_result = wallet_svc.credit_unsettled_wallet(
                                            merchant_id=current_merchant,
                                            amount=float(txn['net_amount']),
                                            description=f"PayIn received (Nextpay) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )
                                        
                                        if wallet_result['success']:
                                            print(f"✓ Merchant unsettled wallet credited: ₹{txn['net_amount']}")
                                        else:
                                            print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")
                                        
                                        # Credit admin unsettled wallet with charge amount
                                        admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                            admin_id='admin',
                                            amount=float(txn['charge_amount']),
                                            description=f"PayIn charge (Nextpay) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )
                                        
                                        if admin_wallet_result['success']:
                                            print(f"✓ Admin unsettled wallet credited: ₹{txn['charge_amount']}")
                                        else:
                                            print(f"✗ Failed to credit admin unsettled wallet: {admin_wallet_result.get('message')}")
                                    else:
                                        print(f"⚠ Wallet already credited for this transaction - skipping")
                                    
                                elif new_status == 'FAILED':
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                                            completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                else:
                                    # Still pending/initiated
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                
                                conn.commit()
                                
                                # Update txn dict with new values
                                txn['status'] = new_status
                                txn['bank_ref_no'] = utr
                                txn['pg_txn_id'] = pg_txn_id
                                txn['payment_mode'] = payment_mode
                                
                                print(f"✓ Updated transaction {txn['txn_id']} to {new_status}")
                    
                    elif pg_partner == 'LOCALPAISA':
                        # Check status from Localpaisa using txn_id
                        status_result = localpaisa_service.check_payment_status(txn['pg_txn_id'])
                        
                        if status_result.get('success'):
                            new_status = status_result.get('status', 'INITIATED')
                            utr = status_result.get('utr')
                            pg_txn_id = status_result.get('txnId')
                            payment_mode = 'UPI'
                            
                            print(f"Localpaisa Status Result: Status={new_status}, UTR={utr}")
                            
                            # Update transaction if status changed
                            if new_status != txn['status']:
                                if new_status == 'SUCCESS':
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                                            completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                    
                                    # Check if wallet already credited (idempotency)
                                    cursor.execute("""
                                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                                        WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                                    """, (txn['txn_id'],))
                                    
                                    wallet_already_credited = cursor.fetchone()['count'] > 0
                                    
                                    if not wallet_already_credited:
                                        # Credit merchant unsettled wallet with net amount
                                        from wallet_service import wallet_service as wallet_svc
                                        wallet_result = wallet_svc.credit_unsettled_wallet(
                                            merchant_id=current_merchant,
                                            amount=float(txn['net_amount']),
                                            description=f"PayIn received (Localpaisa) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )
                                        
                                        if wallet_result['success']:
                                            print(f"✓ Merchant unsettled wallet credited: ₹{txn['net_amount']}")
                                        else:
                                            print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")
                                        
                                        # Credit admin unsettled wallet with charge amount
                                        admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                            admin_id='admin',
                                            amount=float(txn['charge_amount']),
                                            description=f"PayIn charge (Localpaisa) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )
                                        
                                        if admin_wallet_result['success']:
                                            print(f"✓ Admin unsettled wallet credited: ₹{txn['charge_amount']}")
                                        else:
                                            print(f"✗ Failed to credit admin unsettled wallet: {admin_wallet_result.get('message')}")
                                    else:
                                        print(f"⚠ Wallet already credited for this transaction - skipping")
                                    
                                elif new_status == 'FAILED':
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                                            completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                else:
                                    # Still pending/initiated
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                
                                conn.commit()
                                
                                # Update txn dict with new values
                                txn['status'] = new_status
                                txn['bank_ref_no'] = utr
                                txn['pg_txn_id'] = pg_txn_id
                                txn['payment_mode'] = payment_mode
                                
                                print(f"✓ Updated transaction {txn['txn_id']} to {new_status}")
                    
                    elif pg_partner == 'MONEYONE':
                        # Check status from MoneyOne using order_id
                        status_result = moneyone_service.check_payment_status(txn['order_id'])
                        
                        if status_result.get('success'):
                            new_status = status_result.get('status', 'INITIATED')
                            utr = status_result.get('utr')
                            pg_txn_id = status_result.get('txnId')
                            payment_mode = status_result.get('payment_mode', 'UPI')
                            
                            print(f"MoneyOne Status Result: Status={new_status}, UTR={utr}")
                            
                            # Update transaction if status changed
                            if new_status != txn['status']:
                                if new_status == 'SUCCESS':
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                                            completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                    
                                    # Check if wallet already credited
                                    cursor.execute("""
                                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                                        WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                                    """, (txn['txn_id'],))
                                    
                                    wallet_already_credited = cursor.fetchone()['count'] > 0
                                    
                                    if not wallet_already_credited:
                                        from wallet_service import wallet_service as wallet_svc
                                        wallet_result = wallet_svc.credit_unsettled_wallet(
                                            merchant_id=current_merchant,
                                            amount=float(txn['net_amount']),
                                            description=f"PayIn received (MoneyOne) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )
                                        
                                        if wallet_result['success']:
                                            print(f"✓ Merchant unsettled wallet credited: ₹{txn['net_amount']}")
                                        
                                        admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                            admin_id='admin',
                                            amount=float(txn['charge_amount']),
                                            description=f"PayIn charge (MoneyOne) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )
                                        
                                        if admin_wallet_result['success']:
                                            print(f"✓ Admin unsettled wallet credited: ₹{txn['charge_amount']}")
                                    else:
                                        print(f"⚠ Wallet already credited for this transaction - skipping")
                                    
                                elif new_status == 'FAILED':
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                                            completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                else:
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                
                                conn.commit()
                                
                                # Update txn dict with new values
                                txn['status'] = new_status
                                txn['bank_ref_no'] = utr
                                txn['pg_txn_id'] = pg_txn_id
                                txn['payment_mode'] = payment_mode
                                
                                print(f"✓ Updated transaction {txn['txn_id']} to {new_status}")
                    
                    elif pg_partner == 'VIYONAPAY':
                        # Check status from VIYONAPAY using order_id (Truaxis)
                        status_result = viyonapay_service.check_payment_status(txn['order_id'])
                    
                    elif pg_partner == 'VIYONAPAY_BARRINGER':
                        # Check status from VIYONAPAY using order_id (Barringer)
                        status_result = viyonapay_barringer_service.check_payment_status(txn['order_id'])
                        
                        if status_result.get('success'):
                            new_status = status_result.get('status', 'INITIATED')
                            utr = status_result.get('bank_reference_number')
                            pg_txn_id = status_result.get('transaction_id')
                            payment_mode = status_result.get('payment_mode', 'UPI')
                            
                            print(f"VIYONAPAY Status Result: Status={new_status}, UTR={utr}")
                            
                            # Update transaction if status changed
                            if new_status != txn['status']:
                                if new_status == 'SUCCESS':
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                                            completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                    
                                    # Check if wallet already credited (idempotency)
                                    cursor.execute("""
                                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                                        WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                                    """, (txn['txn_id'],))
                                    
                                    wallet_already_credited = cursor.fetchone()['count'] > 0
                                    
                                    if not wallet_already_credited:
                                        # Credit merchant unsettled wallet with net amount
                                        from wallet_service import wallet_service as wallet_svc
                                        wallet_result = wallet_svc.credit_unsettled_wallet(
                                            merchant_id=current_merchant,
                                            amount=float(txn['net_amount']),
                                            description=f"PayIn received (VIYONAPAY) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )
                                        
                                        if wallet_result['success']:
                                            print(f"✓ Merchant unsettled wallet credited: ₹{txn['net_amount']}")
                                        else:
                                            print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")
                                        
                                        # Credit admin unsettled wallet with charge amount
                                        admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                            admin_id='admin',
                                            amount=float(txn['charge_amount']),
                                            description=f"PayIn charge (VIYONAPAY) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )
                                        
                                        if admin_wallet_result['success']:
                                            print(f"✓ Admin unsettled wallet credited: ₹{txn['charge_amount']}")
                                        else:
                                            print(f"✗ Failed to credit admin unsettled wallet: {admin_wallet_result.get('message')}")
                                    else:
                                        print(f"⚠ Wallet already credited for this transaction - skipping")
                                    
                                elif new_status == 'FAILED':
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s,
                                            completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                else:
                                    # Still pending/initiated
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, pg_txn_id = %s, payment_mode = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, pg_txn_id, payment_mode, txn['txn_id']))
                                
                                conn.commit()
                                
                                # Update txn dict with new values
                                txn['status'] = new_status
                                txn['bank_ref_no'] = utr
                                txn['pg_txn_id'] = pg_txn_id
                                txn['payment_mode'] = payment_mode
                                
                                print(f"✓ Updated transaction {txn['txn_id']} to {new_status}")
                    
                    elif pg_partner in ['PES', 'SECTORPE']:
                        # Check status from SectorPe using order_id (txnid)
                        status_result = sectorpe_service.check_payment_status(txn['order_id'])

                        if status_result.get('success'):
                            new_status = status_result.get('status', 'INITIATED')
                            utr = status_result.get('utr', '')
                            payment_mode = 'UPI'

                            print(f"SectorPe Status Result: Status={new_status}, UTR={utr}")

                            if new_status != txn['status']:
                                if new_status == 'SUCCESS':
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, payment_mode = %s,
                                            completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, payment_mode, txn['txn_id']))

                                    # Idempotency check
                                    cursor.execute("""
                                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                                        WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                                    """, (txn['txn_id'],))

                                    wallet_already_credited = cursor.fetchone()['count'] > 0

                                    if not wallet_already_credited:
                                        from wallet_service import wallet_service as wallet_svc
                                        wallet_result = wallet_svc.credit_unsettled_wallet(
                                            merchant_id=current_merchant,
                                            amount=float(txn['net_amount']),
                                            description=f"PayIn received (SectorPe) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )

                                        if wallet_result['success']:
                                            print(f"✓ Merchant unsettled wallet credited: ₹{txn['net_amount']}")
                                        else:
                                            print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")

                                        admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                            admin_id='admin',
                                            amount=float(txn['charge_amount']),
                                            description=f"PayIn charge (SectorPe) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )

                                        if admin_wallet_result['success']:
                                            print(f"✓ Admin unsettled wallet credited: ₹{txn['charge_amount']}")
                                        else:
                                            print(f"✗ Failed to credit admin unsettled wallet: {admin_wallet_result.get('message')}")
                                    else:
                                        print(f"⚠ Wallet already credited for this transaction - skipping")

                                elif new_status == 'FAILED':
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, payment_mode = %s,
                                            completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, payment_mode, txn['txn_id']))
                                else:
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, payment_mode = %s,
                                            updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, payment_mode, txn['txn_id']))

                                conn.commit()

                                txn['status'] = new_status
                                txn['bank_ref_no'] = utr
                                txn['payment_mode'] = payment_mode

                                print(f"✓ Updated transaction {txn['txn_id']} to {new_status}")

                    elif pg_partner == 'OQPAY':
                        # Check status from OQPay
                        status_result = oqpay_service.check_payment_status(txn['pg_txn_id'])

                        if status_result.get('success'):
                            new_status = status_result.get('status', 'INITIATED')
                            utr = status_result.get('utr', '')
                            payment_mode = 'UPI'

                            print(f"OQPay Status Result: Status={new_status}, UTR={utr}")

                            if new_status != txn['status']:
                                if new_status == 'SUCCESS':
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, payment_mode = %s,
                                            completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, payment_mode, txn['txn_id']))

                                    # Idempotency check
                                    cursor.execute("""
                                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                                        WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                                    """, (txn['txn_id'],))

                                    wallet_already_credited = cursor.fetchone()['count'] > 0

                                    if not wallet_already_credited:
                                        from wallet_service import wallet_service as wallet_svc
                                        wallet_result = wallet_svc.credit_unsettled_wallet(
                                            merchant_id=current_merchant,
                                            amount=float(txn['net_amount']),
                                            description=f"PayIn received (OQPay status verification) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )

                                        if wallet_result['success']:
                                            print(f"✓ Merchant unsettled wallet credited: ₹{txn['net_amount']}")
                                        else:
                                            print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")

                                        admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                            admin_id='admin',
                                            amount=float(txn['charge_amount']),
                                            description=f"PayIn charge (OQPay status verification) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )

                                        if admin_wallet_result['success']:
                                            print(f"✓ Admin unsettled wallet credited: ₹{txn['charge_amount']}")
                                        else:
                                            print(f"✗ Failed to credit admin wallet: {admin_wallet_result.get('message')}")
                                    else:
                                        print(f"⚠ Wallet already credited for this transaction - skipping")

                                elif new_status == 'FAILED':
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, payment_mode = %s,
                                            completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, payment_mode, txn['txn_id']))
                                else:
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, payment_mode = %s,
                                            updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, payment_mode, txn['txn_id']))

                                conn.commit()

                                txn['status'] = new_status
                                txn['bank_ref_no'] = utr
                                txn['payment_mode'] = payment_mode

                                print(f"✓ Updated transaction {txn['txn_id']} to {new_status}")

                    elif pg_partner == 'PAYU':
                        # Check status from PayU
                        status_result = payu_service.get_transaction_status(txn['txn_id'])
                        if status_result:
                            txn = status_result
                            
                    elif pg_partner == 'PAYU_LEGALHALT':
                        # Check status from PayU legalhalt
                        status_result = payu_legalhalt_service.check_payment_status(txn['txn_id'])

                        if status_result.get('success'):
                            new_status = status_result.get('status', 'INITIATED')
                            utr = status_result.get('utr', '')
                            payment_mode = status_result.get('payment_mode', 'UPI')

                            print(f"PayU legalhalt Status Result: Status={new_status}, UTR={utr}")

                            if new_status != txn['status']:
                                if new_status == 'SUCCESS':
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, payment_mode = %s,
                                            completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, payment_mode, txn['txn_id']))

                                    # Idempotency check
                                    cursor.execute("""
                                        SELECT COUNT(*) as count FROM merchant_wallet_transactions
                                        WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                                    """, (txn['txn_id'],))

                                    wallet_already_credited = cursor.fetchone()['count'] > 0

                                    if not wallet_already_credited:
                                        from wallet_service import wallet_service as wallet_svc
                                        wallet_result = wallet_svc.credit_unsettled_wallet(
                                            merchant_id=current_merchant,
                                            amount=float(txn['net_amount']),
                                            description=f"PayIn received (PayU legalhalt verification) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )

                                        if wallet_result['success']:
                                            print(f"✓ Merchant unsettled wallet credited: ₹{txn['net_amount']}")
                                        else:
                                            print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")

                                        admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                            admin_id='admin',
                                            amount=float(txn['charge_amount']),
                                            description=f"PayIn charge (PayU legalhalt verification) - {txn['order_id']}",
                                            reference_id=txn['txn_id']
                                        )

                                        if admin_wallet_result['success']:
                                            print(f"✓ Admin unsettled wallet credited: ₹{txn['charge_amount']}")
                                        else:
                                            print(f"✗ Failed to credit admin wallet: {admin_wallet_result.get('message')}")
                                    else:
                                        print(f"⚠ Wallet already credited for this transaction - skipping")

                                elif new_status == 'FAILED':
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, payment_mode = %s,
                                            completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, payment_mode, txn['txn_id']))
                                else:
                                    cursor.execute("""
                                        UPDATE payin_transactions
                                        SET status = %s, bank_ref_no = %s, payment_mode = %s,
                                            updated_at = NOW()
                                        WHERE txn_id = %s
                                    """, (new_status, utr, payment_mode, txn['txn_id']))

                                conn.commit()

                                txn['status'] = new_status
                                txn['bank_ref_no'] = utr
                                txn['payment_mode'] = payment_mode

                                print(f"✓ Updated transaction {txn['txn_id']} to {new_status}")
                
                # Prepare response
                response_data = {
                    'txn_id': txn['txn_id'],
                    'order_id': txn['order_id'],
                    'amount': str(txn['amount']),
                    'charge_amount': str(txn['charge_amount']),
                    'net_amount': str(txn['net_amount']),
                    'status': txn['status'],
                    'pg_partner': txn.get('pg_partner', 'PayU'),
                    'pg_txn_id': txn.get('pg_txn_id'),
                    'bank_ref_no': txn.get('bank_ref_no'),
                    'payment_mode': txn.get('payment_mode'),
                    'payee_name': txn.get('payee_name'),
                    'payee_mobile': txn.get('payee_mobile'),
                    'payee_email': txn.get('payee_email'),
                    'created_at': txn['created_at'].isoformat() if txn.get('created_at') else None,
                    'completed_at': txn['completed_at'].isoformat() if txn.get('completed_at') else None,
                    'message': 'Payment verification successful'
                }
                
                # Encrypt response
                encrypted_response = encrypt_aes(
                    json.dumps(response_data),
                    merchant['aes_key'],
                    merchant['aes_iv']
                )
                
                return jsonify({
                    'success': True,
                    'message': 'Payment verified successfully',
                    'data': encrypted_response
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Verify payment error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@payin_bp.route('/transactions', methods=['GET'])
@jwt_required()
def get_payin_transactions():
    """Get all payin transactions for merchant with search and date filters"""
    try:
        current_merchant = get_jwt_identity()

        # Get query parameters
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        status = request.args.get('status')
        search = request.args.get('search')
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')

        offset = (page - 1) * limit

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        try:
            with conn.cursor() as cursor:
                # Build query - check if utr column exists, fallback to bank_ref_no
                query = """
                    SELECT txn_id, order_id, amount, charge_amount, charge_type, net_amount,
                           status, payment_mode, payee_name, payee_mobile, bank_ref_no, pg_txn_id,
                           created_at, completed_at
                    FROM payin_transactions
                    WHERE merchant_id = %s
                """
                params = [current_merchant]

                if status:
                    query += " AND status = %s"
                    params.append(status)

                # Add search filter
                if search:
                    query += """ AND (
                        txn_id LIKE %s OR
                        order_id LIKE %s OR
                        bank_ref_no LIKE %s OR
                        payee_name LIKE %s OR
                        payee_mobile LIKE %s
                    )"""
                    search_pattern = f"%{search}%"
                    params.extend([search_pattern] * 5)

                # Add date filters
                if from_date:
                    query += " AND DATE(created_at) >= %s"
                    params.append(from_date)

                if to_date:
                    query += " AND DATE(created_at) <= %s"
                    params.append(to_date)

                query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                cursor.execute(query, params)
                transactions = cursor.fetchall()

                # Get total count with same filters
                count_query = "SELECT COUNT(*) as total FROM payin_transactions WHERE merchant_id = %s"
                count_params = [current_merchant]

                if status:
                    count_query += " AND status = %s"
                    count_params.append(status)

                if search:
                    count_query += """ AND (
                        txn_id LIKE %s OR
                        order_id LIKE %s OR
                        bank_ref_no LIKE %s OR
                        payee_name LIKE %s OR
                        payee_mobile LIKE %s
                    )"""
                    search_pattern = f"%{search}%"
                    count_params.extend([search_pattern] * 5)

                if from_date:
                    count_query += " AND DATE(created_at) >= %s"
                    count_params.append(from_date)

                if to_date:
                    count_query += " AND DATE(created_at) <= %s"
                    count_params.append(to_date)

                cursor.execute(count_query, count_params)
                total = cursor.fetchone()['total']

                # Format dates and add utr field (using bank_ref_no)
                for txn in transactions:
                    if txn.get('created_at'):
                        txn['created_at'] = txn['created_at'].isoformat()
                    if txn.get('completed_at'):
                        txn['completed_at'] = txn['completed_at'].isoformat()
                    # Convert Decimal to float
                    txn['amount'] = float(txn['amount']) if txn.get('amount') else 0.0
                    txn['charge_amount'] = float(txn['charge_amount']) if txn.get('charge_amount') else 0.0
                    txn['net_amount'] = float(txn['net_amount']) if txn.get('net_amount') else 0.0
                    # Add utr field (same as bank_ref_no for compatibility)
                    txn['utr'] = txn.get('bank_ref_no')

                return jsonify({
                    'success': True,
                    'transactions': transactions,
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
        print(f"Get payin transactions error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@payin_bp.route('/transactions/all', methods=['GET'])
@jwt_required()
def get_all_payin_transactions():
    """Get ALL payin transactions for merchant (for download) with filters"""
    try:
        current_merchant = get_jwt_identity()

        # Get query parameters
        status = request.args.get('status')
        search = request.args.get('search')
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        try:
            with conn.cursor() as cursor:
                # Build query - NO LIMIT for download
                query = """
                    SELECT txn_id, order_id, amount, charge_amount, charge_type, net_amount,
                           status, payment_mode, payee_name, payee_mobile, bank_ref_no, pg_txn_id,
                           created_at, completed_at
                    FROM payin_transactions
                    WHERE merchant_id = %s
                """
                params = [current_merchant]

                if status:
                    query += " AND status = %s"
                    params.append(status)

                # Add search filter
                if search:
                    query += """ AND (
                        txn_id LIKE %s OR
                        order_id LIKE %s OR
                        bank_ref_no LIKE %s OR
                        payee_name LIKE %s OR
                        payee_mobile LIKE %s
                    )"""
                    search_pattern = f"%{search}%"
                    params.extend([search_pattern] * 5)

                # Add date filters
                if from_date:
                    query += " AND DATE(created_at) >= %s"
                    params.append(from_date)

                if to_date:
                    query += " AND DATE(created_at) <= %s"
                    params.append(to_date)

                query += " ORDER BY created_at DESC"

                cursor.execute(query, params)
                transactions = cursor.fetchall()

                # Format dates and add utr field
                for txn in transactions:
                    if txn.get('created_at'):
                        txn['created_at'] = txn['created_at'].isoformat()
                    if txn.get('completed_at'):
                        txn['completed_at'] = txn['completed_at'].isoformat()
                    # Convert Decimal to float
                    txn['amount'] = float(txn['amount']) if txn.get('amount') else 0.0
                    txn['charge_amount'] = float(txn['charge_amount']) if txn.get('charge_amount') else 0.0
                    txn['net_amount'] = float(txn['net_amount']) if txn.get('net_amount') else 0.0
                    # Add utr field (same as bank_ref_no for compatibility)
                    txn['utr'] = txn.get('bank_ref_no')

                return jsonify({
                    'success': True,
                    'transactions': transactions,
                    'count': len(transactions)
                }), 200

        finally:
            conn.close()

    except Exception as e:
        print(f"Get all payin transactions error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@payin_bp.route('/transactions/today', methods=['GET'])
@jwt_required()
def get_today_payin_transactions():
    """Get today's payin transactions for merchant (for download)"""
    try:
        current_merchant = get_jwt_identity()

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        try:
            with conn.cursor() as cursor:
                # Get today's transactions
                query = """
                    SELECT txn_id, order_id, amount, charge_amount, charge_type, net_amount,
                           status, payment_mode, payee_name, payee_mobile, bank_ref_no, pg_txn_id,
                           created_at, completed_at
                    FROM payin_transactions
                    WHERE merchant_id = %s AND DATE(created_at) = CURDATE()
                    ORDER BY created_at DESC
                """

                cursor.execute(query, [current_merchant])
                transactions = cursor.fetchall()

                # Format dates and add utr field
                for txn in transactions:
                    if txn.get('created_at'):
                        txn['created_at'] = txn['created_at'].isoformat()
                    if txn.get('completed_at'):
                        txn['completed_at'] = txn['completed_at'].isoformat()
                    # Convert Decimal to float
                    txn['amount'] = float(txn['amount']) if txn.get('amount') else 0.0
                    txn['charge_amount'] = float(txn['charge_amount']) if txn.get('charge_amount') else 0.0
                    txn['net_amount'] = float(txn['net_amount']) if txn.get('net_amount') else 0.0
                    # Add utr field (same as bank_ref_no for compatibility)
                    txn['utr'] = txn.get('bank_ref_no')

                return jsonify({
                    'success': True,
                    'transactions': transactions,
                    'count': len(transactions)
                }), 200

        finally:
            conn.close()

    except Exception as e:
        print(f"Get today payin transactions error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500



# Admin routes for payin management

@payin_bp.route('/admin/transactions', methods=['GET'])
@jwt_required()
def admin_get_all_payin_transactions():
    """Get all payin transactions (admin only) with search and date filters"""
    try:
        current_admin = get_jwt_identity()
        
        # Verify admin
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Check if user is admin or QR admin
                if current_admin != 'qr_admin_special':
                    cursor.execute("SELECT admin_id FROM admin_users WHERE admin_id = %s", (current_admin,))
                    if not cursor.fetchone():
                        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
                
                # Get query parameters
                page = int(request.args.get('page', 1))
                limit = int(request.args.get('limit', 50))
                status = request.args.get('status')
                merchant_id = request.args.get('merchant_id')
                search = request.args.get('search')  # New: search parameter
                from_date = request.args.get('from_date')  # New: from date
                to_date = request.args.get('to_date')  # New: to date
                
                offset = (page - 1) * limit
                
                # Build query
                query = """
                    SELECT pt.*, m.full_name as merchant_name
                    FROM payin_transactions pt
                    LEFT JOIN merchants m ON pt.merchant_id = m.merchant_id
                    WHERE 1=1
                """
                params = []
                
                if status:
                    query += " AND pt.status = %s"
                    params.append(status)
                
                if merchant_id:
                    query += " AND pt.merchant_id = %s"
                    params.append(merchant_id)
                
                # Add search filter (searches across multiple fields)
                if search:
                    query += """ AND (
                        pt.txn_id LIKE %s OR 
                        pt.order_id LIKE %s OR 
                        pt.merchant_id LIKE %s OR 
                        m.full_name LIKE %s OR
                        pt.bank_ref_no LIKE %s OR
                        pt.payee_name LIKE %s OR
                        pt.payee_mobile LIKE %s
                    )"""
                    search_pattern = f"%{search}%"
                    params.extend([search_pattern] * 7)
                
                # Add date filters
                if from_date:
                    query += " AND DATE(pt.created_at) >= %s"
                    params.append(from_date)
                
                if to_date:
                    query += " AND DATE(pt.created_at) <= %s"
                    params.append(to_date)
                
                query += " ORDER BY pt.created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                transactions = cursor.fetchall()
                
                # Get total count with same filters
                count_query = """
                    SELECT COUNT(*) as total 
                    FROM payin_transactions pt
                    LEFT JOIN merchants m ON pt.merchant_id = m.merchant_id
                    WHERE 1=1
                """
                count_params = []
                
                if status:
                    count_query += " AND pt.status = %s"
                    count_params.append(status)
                
                if merchant_id:
                    count_query += " AND pt.merchant_id = %s"
                    count_params.append(merchant_id)
                
                if search:
                    count_query += """ AND (
                        pt.txn_id LIKE %s OR 
                        pt.order_id LIKE %s OR 
                        pt.merchant_id LIKE %s OR 
                        m.full_name LIKE %s OR
                        pt.bank_ref_no LIKE %s OR
                        pt.payee_name LIKE %s OR
                        pt.payee_mobile LIKE %s
                    )"""
                    search_pattern = f"%{search}%"
                    count_params.extend([search_pattern] * 7)
                
                if from_date:
                    count_query += " AND DATE(pt.created_at) >= %s"
                    count_params.append(from_date)
                
                if to_date:
                    count_query += " AND DATE(pt.created_at) <= %s"
                    count_params.append(to_date)
                
                cursor.execute(count_query, count_params)
                total = cursor.fetchone()['total']
                
                # Format data
                for txn in transactions:
                    if txn.get('created_at'):
                        txn['created_at'] = txn['created_at'].isoformat()
                    if txn.get('completed_at'):
                        txn['completed_at'] = txn['completed_at'].isoformat()
                    txn['amount'] = float(txn['amount']) if txn.get('amount') else 0.0
                    txn['charge_amount'] = float(txn['charge_amount']) if txn.get('charge_amount') else 0.0
                    txn['net_amount'] = float(txn['net_amount']) if txn.get('net_amount') else 0.0
                    # Add utr field (same as bank_ref_no for compatibility)
                    txn['utr'] = txn.get('bank_ref_no')
                
                return jsonify({
                    'success': True,
                    'transactions': transactions,
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
        print(f"Admin get payin transactions error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@payin_bp.route('/admin/transactions/all', methods=['GET'])
@jwt_required()
def admin_get_all_payin_transactions_download():
    """Get ALL payin transactions for admin (for download) with filters - no pagination"""
    try:
        current_admin = get_jwt_identity()
        
        # Verify admin
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Check if user is admin or QR admin
                if current_admin != 'qr_admin_special':
                    cursor.execute("SELECT admin_id FROM admin_users WHERE admin_id = %s", (current_admin,))
                    if not cursor.fetchone():
                        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
                
                # Get query parameters
                status = request.args.get('status')
                merchant_id = request.args.get('merchant_id')
                search = request.args.get('search')
                from_date = request.args.get('from_date')
                to_date = request.args.get('to_date')
                
                # Build query - NO LIMIT for download
                query = """
                    SELECT pt.*, m.full_name as merchant_name
                    FROM payin_transactions pt
                    LEFT JOIN merchants m ON pt.merchant_id = m.merchant_id
                    WHERE 1=1
                """
                params = []
                
                if status:
                    query += " AND pt.status = %s"
                    params.append(status)
                
                if merchant_id:
                    query += " AND pt.merchant_id = %s"
                    params.append(merchant_id)
                
                # Add search filter
                if search:
                    query += """ AND (
                        pt.txn_id LIKE %s OR 
                        pt.order_id LIKE %s OR 
                        pt.merchant_id LIKE %s OR 
                        m.full_name LIKE %s OR
                        pt.bank_ref_no LIKE %s OR
                        pt.payee_name LIKE %s OR
                        pt.payee_mobile LIKE %s
                    )"""
                    search_pattern = f"%{search}%"
                    params.extend([search_pattern] * 7)
                
                # Add date filters
                if from_date:
                    query += " AND DATE(pt.created_at) >= %s"
                    params.append(from_date)
                
                if to_date:
                    query += " AND DATE(pt.created_at) <= %s"
                    params.append(to_date)
                
                query += " ORDER BY pt.created_at DESC"
                
                cursor.execute(query, params)
                transactions = cursor.fetchall()
                
                # Format data
                for txn in transactions:
                    if txn.get('created_at'):
                        txn['created_at'] = txn['created_at'].isoformat()
                    if txn.get('completed_at'):
                        txn['completed_at'] = txn['completed_at'].isoformat()
                    txn['amount'] = float(txn['amount']) if txn.get('amount') else 0.0
                    txn['charge_amount'] = float(txn['charge_amount']) if txn.get('charge_amount') else 0.0
                    txn['net_amount'] = float(txn['net_amount']) if txn.get('net_amount') else 0.0
                    # Add utr field (same as bank_ref_no for compatibility)
                    txn['utr'] = txn.get('bank_ref_no')
                
                return jsonify({
                    'success': True,
                    'transactions': transactions,
                    'count': len(transactions)
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Admin get all payin transactions error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@payin_bp.route('/admin/transactions/today', methods=['GET'])
@jwt_required()
def admin_get_today_payin_transactions():
    """Get ALL payin transactions for today (admin only) - for report download"""
    try:
        current_admin = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Check if user is admin or QR admin
                if current_admin != 'qr_admin_special':
                    cursor.execute("SELECT admin_id FROM admin_users WHERE admin_id = %s", (current_admin,))
                    if not cursor.fetchone():
                        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
                
                # Get ALL transactions for today (no pagination)
                query = """
                    SELECT pt.*, m.full_name as merchant_name
                    FROM payin_transactions pt
                    LEFT JOIN merchants m ON pt.merchant_id = m.merchant_id
                    WHERE DATE(pt.created_at) = CURDATE()
                    ORDER BY pt.created_at DESC
                """
                
                cursor.execute(query)
                transactions = cursor.fetchall()
                
                # Format data
                for txn in transactions:
                    if txn.get('created_at'):
                        txn['created_at'] = txn['created_at'].isoformat()
                    if txn.get('completed_at'):
                        txn['completed_at'] = txn['completed_at'].isoformat()
                    txn['amount'] = float(txn['amount'])
                    txn['charge_amount'] = float(txn['charge_amount'])
                    txn['net_amount'] = float(txn['net_amount'])
                
                return jsonify({
                    'success': True,
                    'transactions': transactions,
                    'count': len(transactions)
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Admin get today payin transactions error: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@payin_bp.route('/admin/pending', methods=['GET'])
@jwt_required()
def admin_get_pending_payin():
    """Get pending payin transactions (admin only)"""
    try:
        current_admin = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Check if user is admin or QR admin
                if current_admin != 'qr_admin_special':
                    cursor.execute("SELECT admin_id FROM admin_users WHERE admin_id = %s", (current_admin,))
                    if not cursor.fetchone():
                        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
                    return jsonify({'success': False, 'message': 'Unauthorized'}), 403
                
                # Get pending transactions
                cursor.execute("""
                    SELECT pt.*, m.full_name as merchant_name
                    FROM payin_transactions pt
                    LEFT JOIN merchants m ON pt.merchant_id = m.merchant_id
                    WHERE pt.status IN ('INITIATED', 'PENDING')
                    ORDER BY pt.created_at DESC
                """)
                
                transactions = cursor.fetchall()
                
                # Format data
                for txn in transactions:
                    if txn.get('created_at'):
                        txn['created_at'] = txn['created_at'].isoformat()
                    txn['amount'] = float(txn['amount'])
                    txn['charge_amount'] = float(txn['charge_amount'])
                    txn['net_amount'] = float(txn['net_amount'])
                
                return jsonify({
                    'success': True,
                    'transactions': transactions
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Admin get pending payin error: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@payin_bp.route('/admin/check-status/<txn_id>', methods=['GET'])
@jwt_required()
def admin_check_payin_status(txn_id):
    """Check payin transaction status (admin only) - checks Mudrape API and updates database"""
    try:
        current_admin = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Check if user is admin or QR admin
                if current_admin != 'qr_admin_special':
                    cursor.execute("SELECT admin_id FROM admin_users WHERE admin_id = %s", (current_admin,))
                    if not cursor.fetchone():
                        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
                
                # Get transaction details
                cursor.execute("""
                    SELECT pt.*, m.full_name as merchant_name
                    FROM payin_transactions pt
                    LEFT JOIN merchants m ON pt.merchant_id = m.merchant_id
                    WHERE pt.txn_id = %s
                """, (txn_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    return jsonify({'success': False, 'message': 'Transaction not found'}), 404
                
                # Check real-time status from payment gateway if transaction is not final
                pg_partner = txn.get('pg_partner', '').upper()
                
                if txn['status'] in ['INITIATED', 'PENDING'] and pg_partner == 'MUDRAPE':
                    print(f"Admin checking Mudrape status for {txn_id}")
                    
                    # Use pg_txn_id if available, otherwise use order_id
                    identifier = txn.get('pg_txn_id') or txn.get('order_id')
                    
                    if identifier:
                        print(f"Checking Mudrape with identifier: {identifier}")
                        status_result = mudrape_service.check_payment_status(identifier)
                        
                        if status_result.get('success'):
                            mudrape_status = status_result.get('status', '').upper()
                            print(f"Mudrape returned status: {mudrape_status}")
                            
                            # Update database if status changed
                            if mudrape_status == 'SUCCESS' and txn['status'] != 'SUCCESS':
                                print(f"Updating {txn_id} to SUCCESS")
                                
                                # Update transaction
                                cursor.execute("""
                                    UPDATE payin_transactions
                                    SET status = 'SUCCESS',
                                        bank_ref_no = %s,
                                        pg_txn_id = %s,
                                        payment_mode = 'UPI',
                                        completed_at = NOW(),
                                        updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (status_result.get('utr'), status_result.get('txnId'), txn_id))
                                
                                # Credit merchant unsettled wallet with net amount
                                from wallet_service import wallet_service as wallet_svc
                                net_amount = float(txn['net_amount'])
                                charge_amount = float(txn['charge_amount'])
                                
                                wallet_result = wallet_svc.credit_unsettled_wallet(
                                    merchant_id=txn['merchant_id'],
                                    amount=net_amount,
                                    description=f"PayIn received (Mudrape Admin Check) - {txn['order_id']}",
                                    reference_id=txn_id
                                )
                                
                                if wallet_result['success']:
                                    print(f"✓ Merchant unsettled wallet credited: ₹{net_amount}")
                                else:
                                    print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")
                                
                                # Credit admin unsettled wallet with charge amount
                                admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                    admin_id='admin',
                                    amount=charge_amount,
                                    description=f"PayIn charge (Mudrape Admin Check) - {txn['order_id']}",
                                    reference_id=txn_id
                                )
                                
                                if admin_wallet_result['success']:
                                    print(f"✓ Admin unsettled wallet credited: ₹{charge_amount}")
                                else:
                                    print(f"✗ Failed to credit admin unsettled wallet: {admin_wallet_result.get('message')}")
                                
                                conn.commit()
                                
                                # Update txn dict
                                txn['status'] = 'SUCCESS'
                                txn['bank_ref_no'] = status_result.get('utr')
                                txn['pg_txn_id'] = status_result.get('txnId')
                                txn['payment_mode'] = 'UPI'
                                
                                print(f"✓ Updated {txn_id} to SUCCESS and credited wallet")
                            
                            elif mudrape_status == 'FAILED' and txn['status'] != 'FAILED':
                                print(f"Updating {txn_id} to FAILED")
                                
                                cursor.execute("""
                                    UPDATE payin_transactions
                                    SET status = 'FAILED',
                                        pg_txn_id = %s,
                                        completed_at = NOW(),
                                        updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (status_result.get('txnId'), txn_id))
                                
                                conn.commit()
                                
                                txn['status'] = 'FAILED'
                                txn['pg_txn_id'] = status_result.get('txnId')
                                
                                print(f"✓ Updated {txn_id} to FAILED")
                        else:
                            print(f"Failed to check Mudrape status: {status_result.get('message')}")
                
                elif txn['status'] in ['INITIATED', 'PENDING'] and pg_partner == 'VIYONAPAY':
                    print(f"Admin checking VIYONAPAY status for {txn_id}")
                    
                    order_id = txn.get('order_id')
                    
                    if order_id:
                        print(f"Checking VIYONAPAY with order_id: {order_id}")
                        status_result = viyonapay_service.check_payment_status(order_id)
                        
                        if status_result.get('success'):
                            viyonapay_status = status_result.get('status', '').upper()
                            print(f"VIYONAPAY returned status: {viyonapay_status}")
                            
                            # Update database if status changed
                            if viyonapay_status == 'SUCCESS' and txn['status'] != 'SUCCESS':
                                print(f"Updating {txn_id} to SUCCESS")
                                
                                # Update transaction
                                cursor.execute("""
                                    UPDATE payin_transactions
                                    SET status = 'SUCCESS',
                                        bank_ref_no = %s,
                                        pg_txn_id = %s,
                                        payment_mode = %s,
                                        completed_at = NOW(),
                                        updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (
                                    status_result.get('bank_reference_number'),
                                    status_result.get('transaction_id'),
                                    status_result.get('payment_mode', 'UPI'),
                                    txn_id
                                ))
                                
                                # Credit merchant unsettled wallet with net amount
                                from wallet_service import wallet_service as wallet_svc
                                net_amount = float(txn['net_amount'])
                                charge_amount = float(txn['charge_amount'])
                                
                                wallet_result = wallet_svc.credit_unsettled_wallet(
                                    merchant_id=txn['merchant_id'],
                                    amount=net_amount,
                                    description=f"PayIn received (VIYONAPAY Admin Check) - {order_id}",
                                    reference_id=txn_id
                                )
                                
                                if wallet_result['success']:
                                    print(f"✓ Merchant unsettled wallet credited: ₹{net_amount}")
                                else:
                                    print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")
                                
                                # Credit admin unsettled wallet with charge amount
                                admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                    admin_id='admin',
                                    amount=charge_amount,
                                    description=f"PayIn charge (VIYONAPAY Admin Check) - {order_id}",
                                    reference_id=txn_id
                                )
                                
                                if admin_wallet_result['success']:
                                    print(f"✓ Admin unsettled wallet credited: ₹{charge_amount}")
                                else:
                                    print(f"✗ Failed to credit admin unsettled wallet: {admin_wallet_result.get('message')}")
                                
                                conn.commit()
                                
                                # Update txn dict
                                txn['status'] = 'SUCCESS'
                                txn['bank_ref_no'] = status_result.get('bank_reference_number')
                                txn['pg_txn_id'] = status_result.get('transaction_id')
                                txn['payment_mode'] = status_result.get('payment_mode', 'UPI')
                                
                                print(f"✓ Updated {txn_id} to SUCCESS and credited wallet")
                            
                            elif viyonapay_status in ['FAILED', 'EXPIRED'] and txn['status'] != 'FAILED':
                                print(f"Updating {txn_id} to FAILED")
                                
                                cursor.execute("""
                                    UPDATE payin_transactions
                                    SET status = 'FAILED',
                                        pg_txn_id = %s,
                                        error_message = %s,
                                        completed_at = NOW(),
                                        updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (
                                    status_result.get('transaction_id'),
                                    status_result.get('message', 'Payment failed'),
                                    txn_id
                                ))
                                
                                conn.commit()
                                
                                txn['status'] = 'FAILED'
                                txn['pg_txn_id'] = status_result.get('transaction_id')
                                
                                print(f"✓ Updated {txn_id} to FAILED")
                        else:
                            print(f"Failed to check VIYONAPAY status: {status_result.get('message')}")
                
                elif txn['status'] in ['INITIATED', 'PENDING'] and pg_partner == 'VIYONAPAY_BARRINGER':
                    print(f"Admin checking VIYONAPAY_BARRINGER status for {txn_id}")
                    
                    order_id = txn.get('order_id')
                    
                    if order_id:
                        print(f"Checking VIYONAPAY_BARRINGER with order_id: {order_id}")
                        status_result = viyonapay_barringer_service.check_payment_status(order_id)
                        
                        if status_result.get('success'):
                            viyonapay_status = status_result.get('status', '').upper()
                            print(f"VIYONAPAY_BARRINGER returned status: {viyonapay_status}")
                            
                            # Update database if status changed
                            if viyonapay_status == 'SUCCESS' and txn['status'] != 'SUCCESS':
                                print(f"Updating {txn_id} to SUCCESS")
                                
                                # Update transaction
                                cursor.execute("""
                                    UPDATE payin_transactions
                                    SET status = 'SUCCESS',
                                        bank_ref_no = %s,
                                        pg_txn_id = %s,
                                        payment_mode = %s,
                                        completed_at = NOW(),
                                        updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (
                                    status_result.get('bank_reference_number'),
                                    status_result.get('transaction_id'),
                                    status_result.get('payment_mode', 'UPI'),
                                    txn_id
                                ))
                                
                                # Credit merchant unsettled wallet with net amount
                                from wallet_service import wallet_service as wallet_svc
                                net_amount = float(txn['net_amount'])
                                charge_amount = float(txn['charge_amount'])
                                
                                wallet_result = wallet_svc.credit_unsettled_wallet(
                                    merchant_id=txn['merchant_id'],
                                    amount=net_amount,
                                    description=f"PayIn received (VIYONAPAY_BARRINGER Admin Check) - {order_id}",
                                    reference_id=txn_id
                                )
                                
                                if wallet_result['success']:
                                    print(f"✓ Merchant unsettled wallet credited: ₹{net_amount}")
                                else:
                                    print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")
                                
                                # Credit admin unsettled wallet with charge amount
                                admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                    admin_id='admin',
                                    amount=charge_amount,
                                    description=f"PayIn charge (VIYONAPAY_BARRINGER Admin Check) - {order_id}",
                                    reference_id=txn_id
                                )
                                
                                if admin_wallet_result['success']:
                                    print(f"✓ Admin unsettled wallet credited: ₹{charge_amount}")
                                else:
                                    print(f"✗ Failed to credit admin unsettled wallet: {admin_wallet_result.get('message')}")
                                
                                conn.commit()
                                
                                # Update txn dict
                                txn['status'] = 'SUCCESS'
                                txn['bank_ref_no'] = status_result.get('bank_reference_number')
                                txn['pg_txn_id'] = status_result.get('transaction_id')
                                txn['payment_mode'] = status_result.get('payment_mode', 'UPI')
                                
                                print(f"✓ Updated {txn_id} to SUCCESS and credited wallet")
                            
                            elif viyonapay_status in ['FAILED', 'EXPIRED'] and txn['status'] != 'FAILED':
                                print(f"Updating {txn_id} to FAILED")
                                
                                cursor.execute("""
                                    UPDATE payin_transactions
                                    SET status = 'FAILED',
                                        pg_txn_id = %s,
                                        error_message = %s,
                                        completed_at = NOW(),
                                        updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (
                                    status_result.get('transaction_id'),
                                    status_result.get('message', 'Payment failed'),
                                    txn_id
                                ))
                                
                                conn.commit()
                                
                                txn['status'] = 'FAILED'
                                txn['pg_txn_id'] = status_result.get('transaction_id')
                                
                                print(f"✓ Updated {txn_id} to FAILED")
                        else:
                            print(f"Failed to check VIYONAPAY_BARRINGER status: {status_result.get('message')}")
                
                elif txn['status'] in ['INITIATED', 'PENDING'] and pg_partner == 'LOCALPAISA':
                    print(f"Admin checking LOCALPAISA status for {txn_id}")
                    
                    pg_txn_id = txn.get('pg_txn_id')
                    
                    if pg_txn_id:
                        print(f"Checking LOCALPAISA with txn_id: {pg_txn_id}")
                        status_result = localpaisa_service.check_payment_status(pg_txn_id)
                        
                        if status_result.get('success'):
                            localpaisa_status = status_result.get('status', '').upper()
                            print(f"LOCALPAISA returned status: {localpaisa_status}")
                            
                            # Update database if status changed
                            if localpaisa_status == 'SUCCESS' and txn['status'] != 'SUCCESS':
                                print(f"Updating {txn_id} to SUCCESS")
                                
                                # Update transaction
                                cursor.execute("""
                                    UPDATE payin_transactions
                                    SET status = 'SUCCESS',
                                        bank_ref_no = %s,
                                        pg_txn_id = %s,
                                        payment_mode = %s,
                                        completed_at = NOW(),
                                        updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (
                                    status_result.get('utr'),
                                    status_result.get('txnId'),
                                    status_result.get('payment_mode', 'UPI'),
                                    txn_id
                                ))
                                
                                # Credit merchant unsettled wallet with net amount
                                from wallet_service import wallet_service as wallet_svc
                                net_amount = float(txn['net_amount'])
                                charge_amount = float(txn['charge_amount'])
                                
                                wallet_result = wallet_svc.credit_unsettled_wallet(
                                    merchant_id=txn['merchant_id'],
                                    amount=net_amount,
                                    description=f"PayIn received (LOCALPAISA Admin Check) - {txn.get('order_id')}",
                                    reference_id=txn_id
                                )
                                
                                if wallet_result['success']:
                                    print(f"✓ Merchant unsettled wallet credited: ₹{net_amount}")
                                else:
                                    print(f"✗ Failed to credit merchant unsettled wallet: {wallet_result.get('message')}")
                                
                                # Credit admin unsettled wallet with charge amount
                                admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                                    admin_id='admin',
                                    amount=charge_amount,
                                    description=f"PayIn charge (LOCALPAISA Admin Check) - {txn.get('order_id')}",
                                    reference_id=txn_id
                                )
                                
                                if admin_wallet_result['success']:
                                    print(f"✓ Admin unsettled wallet credited: ₹{charge_amount}")
                                else:
                                    print(f"✗ Failed to credit admin unsettled wallet: {admin_wallet_result.get('message')}")
                                
                                conn.commit()
                                
                                # Update txn dict
                                txn['status'] = 'SUCCESS'
                                txn['bank_ref_no'] = status_result.get('utr')
                                txn['pg_txn_id'] = status_result.get('txnId')
                                txn['payment_mode'] = status_result.get('payment_mode', 'UPI')
                                
                                print(f"✓ Updated {txn_id} to SUCCESS and credited wallet")
                            
                            elif localpaisa_status in ['FAILED', 'FAILURE'] and txn['status'] != 'FAILED':
                                print(f"Updating {txn_id} to FAILED")
                                
                                cursor.execute("""
                                    UPDATE payin_transactions
                                    SET status = 'FAILED',
                                        pg_txn_id = %s,
                                        completed_at = NOW(),
                                        updated_at = NOW()
                                    WHERE txn_id = %s
                                """, (
                                    status_result.get('txnId'),
                                    txn_id
                                ))
                                
                                conn.commit()
                                
                                txn['status'] = 'FAILED'
                                txn['pg_txn_id'] = status_result.get('txnId')
                                
                                print(f"✓ Updated {txn_id} to FAILED")
                        else:
                            print(f"Failed to check LOCALPAISA status: {status_result.get('message')}")
                
                # Format data
                if txn.get('created_at'):
                    txn['created_at'] = txn['created_at'].isoformat()
                if txn.get('completed_at'):
                    txn['completed_at'] = txn['completed_at'].isoformat()
                txn['amount'] = float(txn['amount'])
                txn['charge_amount'] = float(txn['charge_amount'])
                txn['net_amount'] = float(txn['net_amount'])
                
                return jsonify({
                    'success': True,
                    'transaction': txn
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Admin check payin status error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal server error'}), 500



@payin_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_payin_stats():
    """Get payin transaction statistics for merchant with date ranges"""
    try:
        current_merchant = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Get transaction counts and amounts by status
                cursor.execute("""
                    SELECT 
                        COUNT(CASE WHEN status = 'SUCCESS' THEN 1 END) as success_count,
                        COUNT(CASE WHEN status IN ('INITIATED', 'PENDING') THEN 1 END) as pending_count,
                        COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as failed_count,
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as success_amount,
                        COALESCE(SUM(CASE WHEN status IN ('INITIATED', 'PENDING') THEN amount ELSE 0 END), 0) as pending_amount,
                        COALESCE(SUM(CASE WHEN status = 'FAILED' THEN amount ELSE 0 END), 0) as failed_amount
                    FROM payin_transactions
                    WHERE merchant_id = %s
                """, (current_merchant,))
                
                stats = cursor.fetchone()
                
                # Get today's stats
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as payin,
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payin
                    FROM payin_transactions
                    WHERE merchant_id = %s AND DATE(created_at) = CURDATE()
                """, (current_merchant,))
                today = cursor.fetchone()
                
                # Get yesterday's stats
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as payin,
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payin
                    FROM payin_transactions
                    WHERE merchant_id = %s AND DATE(created_at) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)
                """, (current_merchant,))
                yesterday = cursor.fetchone()
                
                # Get last 7 days stats
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as payin,
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payin
                    FROM payin_transactions
                    WHERE merchant_id = %s AND DATE(created_at) >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                """, (current_merchant,))
                last7days = cursor.fetchone()
                
                # Get last 30 days stats
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as payin,
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payin
                    FROM payin_transactions
                    WHERE merchant_id = %s AND DATE(created_at) >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                """, (current_merchant,))
                last30days = cursor.fetchone()
                
                return jsonify({
                    'success': True,
                    'stats': {
                        'success': {
                            'count': int(stats['success_count']),
                            'amount': float(stats['success_amount'])
                        },
                        'pending': {
                            'count': int(stats['pending_count']),
                            'amount': float(stats['pending_amount'])
                        },
                        'failed': {
                            'count': int(stats['failed_count']),
                            'amount': float(stats['failed_amount'])
                        }
                    },
                    'timeRanges': {
                        'today': {
                            'payin': float(today['payin']),
                            'net_payin': float(today['net_payin'])
                        },
                        'yesterday': {
                            'payin': float(yesterday['payin']),
                            'net_payin': float(yesterday['net_payin'])
                        },
                        'last7days': {
                            'payin': float(last7days['payin']),
                            'net_payin': float(last7days['net_payin'])
                        },
                        'last30days': {
                            'payin': float(last30days['payin']),
                            'net_payin': float(last30days['net_payin'])
                        }
                    }
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Get payin stats error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@payin_bp.route('/admin/stats', methods=['GET'])
@jwt_required()
def admin_get_payin_stats():
    """Get payin transaction statistics for all merchants (admin only) with date ranges"""
    try:
        current_admin = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Check if user is admin
                cursor.execute("SELECT admin_id FROM admin_users WHERE admin_id = %s", (current_admin,))
                if not cursor.fetchone():
                    return jsonify({'success': False, 'message': 'Unauthorized'}), 403
                
                # Get overall stats
                cursor.execute("""
                    SELECT 
                        COUNT(CASE WHEN status = 'SUCCESS' THEN 1 END) as success_count,
                        COUNT(CASE WHEN status IN ('INITIATED', 'PENDING') THEN 1 END) as pending_count,
                        COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as failed_count,
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as success_amount,
                        COALESCE(SUM(CASE WHEN status IN ('INITIATED', 'PENDING') THEN amount ELSE 0 END), 0) as pending_amount,
                        COALESCE(SUM(CASE WHEN status = 'FAILED' THEN amount ELSE 0 END), 0) as failed_amount,
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN charge_amount ELSE 0 END), 0) as total_payin_charges
                    FROM payin_transactions
                """)
                
                stats = cursor.fetchone()
                
                # Get today's stats
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as payin,
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payin
                    FROM payin_transactions
                    WHERE DATE(created_at) = CURDATE()
                """)
                today = cursor.fetchone()
                
                # Get yesterday's stats
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as payin,
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payin
                    FROM payin_transactions
                    WHERE DATE(created_at) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)
                """)
                yesterday = cursor.fetchone()
                
                # Get last 7 days stats
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as payin,
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payin
                    FROM payin_transactions
                    WHERE DATE(created_at) >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                """)
                last7days = cursor.fetchone()
                
                # Get last 30 days stats
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as payin,
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payin
                    FROM payin_transactions
                    WHERE DATE(created_at) >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                """)
                last30days = cursor.fetchone()
                
                return jsonify({
                    'success': True,
                    'stats': {
                        'success': {
                            'count': int(stats['success_count']),
                            'amount': float(stats['success_amount'])
                        },
                        'pending': {
                            'count': int(stats['pending_count']),
                            'amount': float(stats['pending_amount'])
                        },
                        'failed': {
                            'count': int(stats['failed_count']),
                            'amount': float(stats['failed_amount'])
                        }
                    },
                    'totals': {
                        'total_payin_charges': float(stats['total_payin_charges'])
                    },
                    'timeRanges': {
                        'today': {
                            'payin': float(today['payin']),
                            'net_payin': float(today['net_payin'])
                        },
                        'yesterday': {
                            'payin': float(yesterday['payin']),
                            'net_payin': float(yesterday['net_payin'])
                        },
                        'last7days': {
                            'payin': float(last7days['payin']),
                            'net_payin': float(last7days['net_payin'])
                        },
                        'last30days': {
                            'payin': float(last30days['payin']),
                            'net_payin': float(last30days['net_payin'])
                        }
                    }
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Admin get payin stats error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@payin_bp.route('/admin/create-invoice/<txn_id>', methods=['POST'])
@jwt_required()
def admin_create_invoice(txn_id):
    """
    Create invoice for a successful payin transaction
    Uses EXACT same logic as test_invoice_api_with_real_data.py
    """
    conn = None
    cursor = None
    
    try:
        # Get database connection
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'success': False,
                'message': 'Database connection failed'
            }), 500
        
        cursor = conn.cursor()
        
        # Fetch transaction details - EXACT query from test script
        cursor.execute("""
            SELECT 
                txn_id,
                order_id,
                amount,
                payee_name,
                payee_email,
                payee_mobile,
                bank_ref_no,
                pg_txn_id,
                status,
                completed_at,
                created_at
            FROM payin_transactions
            WHERE txn_id = %s
        """, (txn_id,))
        
        txn = cursor.fetchone()
        
        if not txn:
            return jsonify({
                'success': False,
                'message': 'Transaction not found'
            }), 404
        
        # Check if transaction is successful
        if txn['status'] != 'SUCCESS':
            return jsonify({
                'success': False,
                'message': 'Invoice can only be created for successful transactions'
            }), 400
        
        # Format timestamp - EXACT logic from test script
        timestamp = txn['completed_at'] or txn['created_at']
        if timestamp:
            formatted_timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        else:
            formatted_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Extract last 14 digits from order_id
        order_id_str = str(txn['order_id'])
        last_14_digits = order_id_str[-14:] if len(order_id_str) >= 14 else order_id_str
        
        # Get last 5 digits of order_id for making email/mobile unique
        last_5_digits = order_id_str[-5:] if len(order_id_str) >= 5 else order_id_str
        
        # Make email unique by adding last 5 digits before @
        original_email = txn['payee_email']
        if '@' in original_email:
            email_parts = original_email.split('@')
            unique_email = f"{email_parts[0]}{last_5_digits}@{email_parts[1]}"
        else:
            unique_email = f"{original_email}{last_5_digits}"
        
        # Make mobile unique by appending last 5 digits
        original_mobile = str(txn['payee_mobile'])
        unique_mobile = f"{original_mobile}{last_5_digits}"
        
        # Prepare invoice data with unique email and mobile
        invoice_data = {
            'amount': float(txn['amount']),
            'orderid': last_14_digits,
            'payee_name': txn['payee_name'],
            'payee_email': unique_email,
            'payee_mobile': unique_mobile,
            'UTR': txn['bank_ref_no'] or txn['pg_txn_id'] or 'N/A',
            'Refno': txn['pg_txn_id'] or txn['bank_ref_no'] or txn['txn_id'],
            'TimeStamp': formatted_timestamp
        }
        
        print("=" * 80)
        print(f"CREATING INVOICE FOR TRANSACTION: {txn_id}")
        print("-" * 80)
        print(f"Transaction Data:")
        print(f"  Order ID: {txn['order_id']}")
        print(f"  Amount: {txn['amount']}")
        print(f"  Customer: {txn['payee_name']}")
        print(f"  Email: {txn['payee_email']}")
        print(f"  Mobile: {txn['payee_mobile']}")
        print("-" * 80)
        print(f"Invoice Data Being Sent:")
        print(json.dumps(invoice_data, indent=2))
        print("-" * 80)
        
        # Send to external invoice API - EXACT request from test script
        response = requests.post(
            'https://api.truaxisventures.in/api/auto-order/create',
            json=invoice_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"Response Status: {response.status_code}")
        
        response_data = response.json()
        print(f"Response Data:")
        print(json.dumps(response_data, indent=2))
        print("=" * 80)
        
        # Check response - EXACT logic from test script
        if response.status_code == 201:
            return jsonify({
                'success': True,
                'message': 'Invoice created successfully',
                'data': response_data
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': response_data.get('message', 'Failed to create invoice'),
                'data': response_data
            }), 400
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Invoice API request error: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to connect to invoice API: {str(e)}'
        }), 500
        
    except Exception as e:
        print(f"❌ Create invoice error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@payin_bp.route('/admin/manual-complete/<txn_id>', methods=['POST'])
@jwt_required()
def admin_manual_complete_payin(txn_id):
    """Manually complete payin transaction (admin only)"""
    try:
        current_admin = get_jwt_identity()
        data = request.get_json()
        
        action = data.get('action')  # 'success' or 'failed'
        utr = data.get('utr', '')
        remarks = data.get('remarks', '')
        
        if action not in ['success', 'failed']:
            return jsonify({'success': False, 'message': 'Invalid action'}), 400
            
        if action == 'success' and not utr:
            return jsonify({'success': False, 'message': 'UTR is required for success'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Check if user is admin or QR admin
                if current_admin != 'qr_admin_special':
                    cursor.execute("SELECT admin_id FROM admin_users WHERE admin_id = %s", (current_admin,))
                    if not cursor.fetchone():
                        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
                
                # Get transaction details
                cursor.execute("""
                    SELECT * FROM payin_transactions WHERE txn_id = %s
                """, (txn_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    return jsonify({'success': False, 'message': 'Transaction not found'}), 404
                
                if txn['status'] not in ['INITIATED', 'PENDING']:
                    return jsonify({'success': False, 'message': 'Transaction already processed'}), 400
                
                if action == 'success':
                    # Update transaction to SUCCESS
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = 'SUCCESS',
                            bank_ref_no = %s,
                            payment_mode = 'UPI',
                            completed_at = NOW(),
                            updated_at = NOW(),
                            remarks = %s
                        WHERE txn_id = %s
                    """, (utr, remarks, txn_id))
                    
                    # Credit merchant unsettled wallet with net amount
                    from wallet_service import wallet_service as wallet_svc
                    wallet_result = wallet_svc.credit_unsettled_wallet(
                        merchant_id=txn['merchant_id'],
                        amount=float(txn['net_amount']),
                        description=f"PayIn received ({txn.get('pg_partner', 'Manual')}) - {txn['order_id']}. {remarks}",
                        reference_id=txn_id
                    )
                    
                    if not wallet_result['success']:
                        conn.rollback()
                        return jsonify({
                            'success': False,
                            'message': f"Failed to credit merchant wallet: {wallet_result.get('message')}"
                        }), 500
                    
                    # Credit admin unsettled wallet with charge amount
                    admin_wallet_result = wallet_svc.credit_admin_unsettled_wallet(
                        admin_id=current_admin,
                        amount=float(txn['charge_amount']),
                        description=f"PayIn charge ({txn.get('pg_partner', 'Manual')}) - {txn['order_id']}",
                        reference_id=txn_id
                    )
                    
                    if not admin_wallet_result['success']:
                        conn.rollback()
                        return jsonify({
                            'success': False,
                            'message': f"Failed to credit admin wallet: {admin_wallet_result.get('message')}"
                        }), 500
                    
                    conn.commit()
                    
                    # Send callback
                    from manual_callback_trigger import send_callback
                    send_callback(txn_id=txn_id)
                    
                    return jsonify({
                        'success': True,
                        'message': 'Transaction marked as SUCCESS and callback sent',
                        'status': 'SUCCESS'
                    }), 200
                    
                else:  # action == 'failed'
                    # Update transaction to FAILED
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = 'FAILED',
                            error_message = %s,
                            updated_at = NOW(),
                            remarks = %s
                        WHERE txn_id = %s
                    """, ('Marked as failed by admin (No UTR)', remarks, txn_id))
                    
                    conn.commit()
                    
                    # Send callback
                    from manual_callback_trigger import send_callback
                    send_callback(txn_id=txn_id)
                    
                    return jsonify({
                        'success': True,
                        'message': 'Transaction marked as FAILED and callback sent',
                        'status': 'FAILED'
                    }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Admin manual complete payin error: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

