"""
Manual Reconciliation Routes
Admin feature for searching and manually marking transactions as failed
"""

from flask import Blueprint, request, jsonify, Response, stream_with_context
from flask_jwt_extended import jwt_required, get_jwt_identity
from database_pooled import get_db_connection
from datetime import datetime
import requests
import json
import time
import traceback

manual_recon_bp = Blueprint('manual_reconciliation', __name__)


def send_transaction_callback(txn_data, txn_type='payin', callback_format='default'):
    """
    Send callback for a transaction
    Returns: (success: bool, message: str)
    """
    try:
        callback_url = txn_data.get('callback_url')
        
        if not callback_url:
            return False, 'No callback URL configured'
        
        # Prepare callback payload
        if txn_type == 'payin':
            callback_data = {
                'txn_id': txn_data.get('txn_id'),
                'order_id': txn_data.get('order_id'),
                'amount': str(txn_data.get('amount', 0)),
                'status': txn_data.get('status'),
                'pg_txn_id': txn_data.get('pg_txn_id', ''),
                'bank_ref_no': txn_data.get('bank_ref_no', ''),
                'message': txn_data.get('error_message', 'INTENT EXPIRED. Transaction was not processed'),
                'timestamp': datetime.now().isoformat()
            }
        else:  # payout
            if callback_format == 'maxpe':
                callback_data = {
                    'txn_id': txn_data.get('txn_id'),
                    'reference_id': txn_data.get('reference_id') or txn_data.get('order_id', ''),
                    'status': txn_data.get('status'),
                    'utr': txn_data.get('utr', ''),
                    'pg_partner': txn_data.get('pg_partner', ''),
                    'pg_txn_id': txn_data.get('pg_txn_id', '') or txn_data.get('reference_id') or txn_data.get('order_id', ''),
                    'amount': float(txn_data.get('net_amount', 0)) if txn_data.get('net_amount') else float(txn_data.get('amount', 0)),
                    'message': f"Payout {txn_data.get('status', '').lower()}"
                }
            else:
                callback_data = {
                    'txn_id': txn_data.get('txn_id'),
                    'reference_id': txn_data.get('reference_id'),
                    'order_id': txn_data.get('order_id', ''),
                    'amount': str(txn_data.get('amount', 0)),
                    'status': txn_data.get('status'),
                    'utr': txn_data.get('utr', ''),
                    'pg_txn_id': txn_data.get('pg_txn_id', ''),
                    'message': txn_data.get('error_message', 'Transaction was not processed'),
                    'timestamp': datetime.now().isoformat()
                }
        
        # Send callback with timeout
        response = requests.post(
            callback_url,
            json=callback_data,
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )
        
        # Log callback attempt
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO callback_logs 
                        (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    """, (
                        txn_data.get('merchant_id'),
                        txn_data.get('txn_id'),
                        callback_url,
                        json.dumps(callback_data),
                        response.status_code,
                        response.text[:1000]  # Limit response data
                    ))
                    conn.commit()
            finally:
                conn.close()
        
        if response.status_code == 200:
            return True, 'Callback sent successfully'
        else:
            return False, f'Callback failed with status {response.status_code}'
            
    except requests.Timeout:
        return False, 'Callback timeout'
    except requests.ConnectionError:
        return False, 'Callback connection error'
    except Exception as e:
        return False, f'Callback error: {str(e)}'


@manual_recon_bp.route('/api/admin/manual-reconciliation/search', methods=['POST'])
@jwt_required()
def search_transactions():
    """
    Search transactions by various criteria with date/time filtering
    Supports: reference_id, txn_id, pg_txn_id, utr, order_id
    """
    try:
        admin_id = get_jwt_identity()
        data = request.json
        
        search_type = data.get('search_type')  # 'payin' or 'payout'
        search_field = data.get('search_field')  # 'reference_id', 'txn_id', 'pg_txn_id', 'utr', 'order_id'
        search_value = data.get('search_value', '').strip()
        from_datetime = data.get('from_datetime')  # ISO format: 2024-01-01T00:00:00
        to_datetime = data.get('to_datetime')
        page = data.get('page', 1)
        page_size = min(data.get('page_size', 50), 100)  # Max 100 per page
        
        if not all([search_type, search_field, search_value]):
            return jsonify({
                'success': False,
                'message': 'search_type, search_field, and search_value are required'
            }), 400
        
        if search_type not in ['payin', 'payout']:
            return jsonify({
                'success': False,
                'message': 'search_type must be "payin" or "payout"'
            }), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Build query based on transaction type
                if search_type == 'payin':
                    # Map search fields to database columns
                    field_mapping = {
                        'txn_id': 'pt.txn_id',
                        'order_id': 'pt.order_id',
                        'pg_txn_id': 'pt.pg_txn_id',
                        'bank_ref_no': 'pt.bank_ref_no'
                    }
                    
                    if search_field not in field_mapping:
                        return jsonify({
                            'success': False,
                            'message': f'Invalid search_field for payin: {search_field}'
                        }), 400
                    
                    db_field = field_mapping[search_field]
                    
                    # Count query
                    count_query = f"""
                        SELECT COUNT(*) as total
                        FROM payin_transactions pt
                        WHERE {db_field} LIKE %s
                    """
                    count_params = [f'%{search_value}%']
                    
                    if from_datetime:
                        count_query += " AND pt.created_at >= %s"
                        count_params.append(from_datetime)
                    if to_datetime:
                        count_query += " AND pt.created_at <= %s"
                        count_params.append(to_datetime)
                    
                    cursor.execute(count_query, count_params)
                    total_count = cursor.fetchone()['total']
                    
                    # Data query
                    offset = (page - 1) * page_size
                    query = f"""
                        SELECT 
                            pt.id,
                            pt.txn_id,
                            pt.order_id,
                            pt.merchant_id,
                            pt.amount,
                            pt.charge_amount,
                            pt.net_amount,
                            pt.status,
                            pt.pg_partner,
                            pt.pg_txn_id,
                            pt.bank_ref_no,
                            pt.payment_mode,
                            pt.error_message,
                            pt.callback_url,
                            pt.created_at,
                            pt.updated_at,
                            pt.completed_at,
                            m.full_name as merchant_name,
                            m.mobile as merchant_mobile
                        FROM payin_transactions pt
                        LEFT JOIN merchants m ON pt.merchant_id = m.merchant_id
                        WHERE {db_field} LIKE %s
                    """
                    query_params = [f'%{search_value}%']
                    
                    if from_datetime:
                        query += " AND pt.created_at >= %s"
                        query_params.append(from_datetime)
                    if to_datetime:
                        query += " AND pt.created_at <= %s"
                        query_params.append(to_datetime)
                    
                    query += " ORDER BY pt.created_at DESC LIMIT %s OFFSET %s"
                    query_params.extend([page_size, offset])
                    
                    cursor.execute(query, query_params)
                    transactions = cursor.fetchall()
                    
                else:  # payout
                    field_mapping = {
                        'txn_id': 'p.txn_id',
                        'reference_id': 'p.reference_id',
                        'order_id': 'p.order_id',
                        'pg_txn_id': 'p.pg_txn_id',
                        'utr': 'p.utr'
                    }
                    
                    if search_field not in field_mapping:
                        return jsonify({
                            'success': False,
                            'message': f'Invalid search_field for payout: {search_field}'
                        }), 400
                    
                    db_field = field_mapping[search_field]
                    
                    # Count query
                    count_query = f"""
                        SELECT COUNT(*) as total
                        FROM payout_transactions p
                        WHERE {db_field} LIKE %s
                    """
                    count_params = [f'%{search_value}%']
                    
                    if from_datetime:
                        count_query += " AND p.created_at >= %s"
                        count_params.append(from_datetime)
                    if to_datetime:
                        count_query += " AND p.created_at <= %s"
                        count_params.append(to_datetime)
                    
                    cursor.execute(count_query, count_params)
                    total_count = cursor.fetchone()['total']
                    
                    # Data query
                    offset = (page - 1) * page_size
                    query = f"""
                        SELECT 
                            p.id,
                            p.txn_id,
                            p.reference_id,
                            p.order_id,
                            p.merchant_id,
                            p.amount,
                            p.charge_amount,
                            p.net_amount,
                            p.status,
                            p.bene_name,
                            p.account_no,
                            p.ifsc_code,
                            p.vpa,
                            p.payment_type,
                            p.pg_partner,
                            p.pg_txn_id,
                            p.utr,
                            p.bank_ref_no,
                            p.error_message,
                            p.callback_url,
                            p.created_at,
                            p.updated_at,
                            p.completed_at,
                            m.full_name as merchant_name,
                            m.mobile as merchant_mobile
                        FROM payout_transactions p
                        LEFT JOIN merchants m ON p.merchant_id = m.merchant_id
                        WHERE {db_field} LIKE %s
                    """
                    query_params = [f'%{search_value}%']
                    
                    if from_datetime:
                        query += " AND p.created_at >= %s"
                        query_params.append(from_datetime)
                    if to_datetime:
                        query += " AND p.created_at <= %s"
                        query_params.append(to_datetime)
                    
                    query += " ORDER BY p.created_at DESC LIMIT %s OFFSET %s"
                    query_params.extend([page_size, offset])
                    
                    cursor.execute(query, query_params)
                    transactions = cursor.fetchall()
                
                return jsonify({
                    'success': True,
                    'transactions': transactions,
                    'count': len(transactions),
                    'total_count': total_count,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total_count + page_size - 1) // page_size if total_count > 0 else 0
                })
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[MANUAL_RECON] Search error: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@manual_recon_bp.route('/api/admin/manual-reconciliation/mark-failed', methods=['POST'])
@jwt_required()
def mark_transaction_failed():
    """
    Mark a single transaction as failed with reason and send callback
    """
    try:
        admin_id = get_jwt_identity()
        data = request.json
        
        txn_type = data.get('txn_type')  # 'payin' or 'payout'
        txn_id = data.get('txn_id')
        reason = data.get('reason', 'Marked as failed by admin').strip()
        
        if not all([txn_type, txn_id, reason]):
            return jsonify({
                'success': False,
                'message': 'txn_type, txn_id, and reason are required'
            }), 400
        
        if txn_type not in ['payin', 'payout']:
            return jsonify({
                'success': False,
                'message': 'txn_type must be "payin" or "payout"'
            }), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Get transaction details
                if txn_type == 'payin':
                    cursor.execute("""
                        SELECT * FROM payin_transactions 
                        WHERE txn_id = %s
                    """, (txn_id,))
                else:
                    cursor.execute("""
                        SELECT * FROM payout_transactions 
                        WHERE txn_id = %s
                    """, (txn_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    return jsonify({
                        'success': False,
                        'message': 'Transaction not found'
                    }), 404
                
                # Check if already failed
                if txn['status'] == 'FAILED':
                    return jsonify({
                        'success': False,
                        'message': 'Transaction is already marked as FAILED'
                    }), 400
                
                # Update transaction status
                if txn_type == 'payin':
                    cursor.execute("""
                        UPDATE payin_transactions 
                        SET status = 'FAILED',
                            error_message = %s,
                            updated_at = NOW(),
                            completed_at = NOW()
                        WHERE txn_id = %s
                    """, (reason, txn_id))
                else:
                    cursor.execute("""
                        UPDATE payout_transactions 
                        SET status = 'FAILED',
                            error_message = %s,
                            updated_at = NOW(),
                            completed_at = NOW()
                        WHERE txn_id = %s
                    """, (reason, txn_id))
                    
                    # Refund amount to merchant wallet if it's a payout
                    if txn.get('merchant_id'):
                        try:
                            # Calculate total deducted (amount + charge)
                            total_deducted = float(txn.get('amount', 0)) + float(txn.get('charge_amount', 0))
                            if total_deducted > 0:
                                from wallet_service import WalletService
                                wallet_svc = WalletService()
                                wallet_svc.credit_merchant_wallet(
                                    merchant_id=txn['merchant_id'],
                                    amount=total_deducted,
                                    description=f"Refund for manual failed payout: {txn_id}",
                                    reference_id=txn_id
                                )
                        except Exception as e:
                            print(f"[MANUAL_RECON] Wallet refund error: {str(e)}")
                
                conn.commit()
                
                # Log admin activity
                cursor.execute("""
                    INSERT INTO admin_activity_logs 
                    (admin_id, action, details, ip_address, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                """, (
                    admin_id,
                    'MANUAL_RECONCILIATION_MARK_FAILED',
                    json.dumps({
                        'txn_type': txn_type,
                        'txn_id': txn_id,
                        'reason': reason,
                        'previous_status': txn['status']
                    }),
                    request.remote_addr
                ))
                conn.commit()
                
                # Send callback if URL exists
                callback_sent = False
                callback_message = 'No callback URL'
                
                if txn.get('callback_url'):
                    txn['status'] = 'FAILED'
                    txn['error_message'] = reason
                    callback_format = data.get('callback_format', 'maxpe' if txn_type == 'payout' else 'default')
                    callback_sent, callback_message = send_transaction_callback(txn, txn_type, callback_format)
                
                return jsonify({
                    'success': True,
                    'message': 'Transaction marked as failed',
                    'txn_id': txn_id,
                    'callback_sent': callback_sent,
                    'callback_message': callback_message
                })
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[MANUAL_RECON] Mark failed error: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@manual_recon_bp.route('/api/admin/manual-reconciliation/mark-success', methods=['POST'])
@jwt_required()
def mark_transaction_success():
    """
    Mark a single transaction as success with optional UTR/reference and send callback
    """
    try:
        admin_id = get_jwt_identity()
        data = request.json

        txn_type = data.get('txn_type')  # 'payin' or 'payout'
        txn_id = data.get('txn_id')
        utr = data.get('utr', '').strip()
        remarks = data.get('remarks', 'Marked as success by admin').strip()
        callback_format = data.get('callback_format', 'default')

        if not all([txn_type, txn_id]):
            return jsonify({
                'success': False,
                'message': 'txn_type and txn_id are required'
            }), 400

        if txn_type not in ['payin', 'payout']:
            return jsonify({
                'success': False,
                'message': 'txn_type must be "payin" or "payout"'
            }), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        try:
            with conn.cursor() as cursor:
                # Get transaction details
                if txn_type == 'payin':
                    cursor.execute("SELECT * FROM payin_transactions WHERE txn_id = %s", (txn_id,))
                else:
                    cursor.execute("SELECT * FROM payout_transactions WHERE txn_id = %s", (txn_id,))

                txn = cursor.fetchone()

                if not txn:
                    return jsonify({
                        'success': False,
                        'message': 'Transaction not found'
                    }), 404

                # Check if already success
                if txn['status'] == 'SUCCESS':
                    return jsonify({
                        'success': False,
                        'message': 'Transaction is already marked as SUCCESS'
                    }), 400

                # Update transaction status
                if txn_type == 'payin':
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = 'SUCCESS',
                            bank_ref_no = COALESCE(NULLIF(%s, ''), bank_ref_no),
                            error_message = NULL,
                            updated_at = NOW(),
                            completed_at = NOW()
                        WHERE txn_id = %s
                    """, (utr, txn_id))
                else:
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = 'SUCCESS',
                            utr = COALESCE(NULLIF(%s, ''), utr),
                            error_message = NULL,
                            updated_at = NOW(),
                            completed_at = NOW()
                        WHERE txn_id = %s
                    """, (utr, txn_id))
                    
                    # Deduct from settled_balance for payout manual success
                    if txn.get('merchant_id') and float(txn.get('amount', 0)) > 0:
                        try:
                            # Use WalletService to safely deduct and record transaction
                            from wallet_service import WalletService
                            wallet_svc = WalletService()
                            wallet_svc.debit_merchant_wallet(
                                merchant_id=txn['merchant_id'],
                                amount=float(txn['amount']),
                                description=f"Manual Success Deduction",
                                reference_id=txn_id
                            )
                        except Exception as e:
                            print(f"[MANUAL_RECON] Wallet deduction error: {str(e)}")

                conn.commit()

                # Log admin activity
                cursor.execute("""
                    INSERT INTO admin_activity_logs
                    (admin_id, action, details, ip_address, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                """, (
                    admin_id,
                    'MANUAL_RECONCILIATION_MARK_SUCCESS',
                    json.dumps({
                        'txn_type': txn_type,
                        'txn_id': txn_id,
                        'utr': utr,
                        'remarks': remarks,
                        'previous_status': txn['status']
                    }),
                    request.remote_addr
                ))
                conn.commit()

                # Send callback if URL exists
                callback_sent = False
                callback_message = 'No callback URL'

                if txn.get('callback_url'):
                    txn['status'] = 'SUCCESS'
                    txn['error_message'] = None
                    if utr:
                        if txn_type == 'payin':
                            txn['bank_ref_no'] = utr
                        else:
                            txn['utr'] = utr
                    callback_sent, callback_message = send_transaction_callback(txn, txn_type, callback_format)

                return jsonify({
                    'success': True,
                    'message': 'Transaction marked as success',
                    'txn_id': txn_id,
                    'callback_sent': callback_sent,
                    'callback_message': callback_message
                })

        finally:
            conn.close()

    except Exception as e:
        print(f"[MANUAL_RECON] Mark success error: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@manual_recon_bp.route('/api/admin/manual-reconciliation/bulk-initiated', methods=['POST'])
@jwt_required()
def get_bulk_initiated_transactions():
    """
    Get initiated transactions for bulk operations
    """
    try:
        admin_id = get_jwt_identity()
        data = request.json
        
        txn_type = data.get('txn_type')  # 'payin' or 'payout'
        merchant_id = data.get('merchant_id')
        from_datetime = data.get('from_datetime')
        to_datetime = data.get('to_datetime')
        page = data.get('page', 1)
        page_size = min(data.get('page_size', 100), 500)  # Max 500 per page
        
        if not all([txn_type, merchant_id, from_datetime, to_datetime]):
            return jsonify({
                'success': False,
                'message': 'txn_type, merchant_id, from_datetime, and to_datetime are required'
            }), 400
        
        if txn_type not in ['payin', 'payout']:
            return jsonify({
                'success': False,
                'message': 'txn_type must be "payin" or "payout"'
            }), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                if txn_type == 'payin':
                    # Count query
                    count_query = """
                        SELECT COUNT(*) as total
                        FROM payin_transactions pt
                        WHERE pt.merchant_id = %s
                        AND pt.status = 'INITIATED'
                        AND pt.created_at >= %s
                        AND pt.created_at <= %s
                    """
                    cursor.execute(count_query, (merchant_id, from_datetime, to_datetime))
                    total_count = cursor.fetchone()['total']
                    
                    # Limit check
                    if total_count > 10000:
                        return jsonify({
                            'success': False,
                            'message': f'Too many records ({total_count}). Please narrow your date range to less than 10,000 records.'
                        }), 400
                    
                    # Data query
                    offset = (page - 1) * page_size
                    query = """
                        SELECT 
                            pt.id,
                            pt.txn_id,
                            pt.order_id,
                            pt.merchant_id,
                            pt.amount,
                            pt.charge_amount,
                            pt.net_amount,
                            pt.status,
                            pt.pg_partner,
                            pt.pg_txn_id,
                            pt.callback_url,
                            pt.created_at,
                            m.full_name as merchant_name
                        FROM payin_transactions pt
                        LEFT JOIN merchants m ON pt.merchant_id = m.merchant_id
                        WHERE pt.merchant_id = %s
                        AND pt.status = 'INITIATED'
                        AND pt.created_at >= %s
                        AND pt.created_at <= %s
                        ORDER BY pt.created_at DESC
                        LIMIT %s OFFSET %s
                    """
                    cursor.execute(query, (merchant_id, from_datetime, to_datetime, page_size, offset))
                    transactions = cursor.fetchall()
                    
                else:  # payout
                    # Count query
                    count_query = """
                        SELECT COUNT(*) as total
                        FROM payout_transactions p
                        WHERE p.merchant_id = %s
                        AND p.status IN ('INITIATED', 'QUEUED')
                        AND p.created_at >= %s
                        AND p.created_at <= %s
                    """
                    cursor.execute(count_query, (merchant_id, from_datetime, to_datetime))
                    total_count = cursor.fetchone()['total']
                    
                    # Limit check
                    if total_count > 10000:
                        return jsonify({
                            'success': False,
                            'message': f'Too many records ({total_count}). Please narrow your date range to less than 10,000 records.'
                        }), 400
                    
                    # Data query
                    offset = (page - 1) * page_size
                    query = """
                        SELECT 
                            p.id,
                            p.txn_id,
                            p.reference_id,
                            p.order_id,
                            p.merchant_id,
                            p.amount,
                            p.charge_amount,
                            p.net_amount,
                            p.status,
                            p.bene_name,
                            p.account_no,
                            p.pg_partner,
                            p.pg_txn_id,
                            p.callback_url,
                            p.created_at,
                            m.full_name as merchant_name
                        FROM payout_transactions p
                        LEFT JOIN merchants m ON p.merchant_id = m.merchant_id
                        WHERE p.merchant_id = %s
                        AND p.status IN ('INITIATED', 'QUEUED')
                        AND p.created_at >= %s
                        AND p.created_at <= %s
                        ORDER BY p.created_at DESC
                        LIMIT %s OFFSET %s
                    """
                    cursor.execute(query, (merchant_id, from_datetime, to_datetime, page_size, offset))
                    transactions = cursor.fetchall()
                
                return jsonify({
                    'success': True,
                    'transactions': transactions,
                    'count': len(transactions),
                    'total_count': total_count,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total_count + page_size - 1) // page_size if total_count > 0 else 0
                })
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[MANUAL_RECON] Bulk initiated error: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@manual_recon_bp.route('/api/admin/manual-reconciliation/bulk-mark-failed', methods=['POST'])
@jwt_required()
def bulk_mark_failed():
    """
    Bulk mark transactions as failed with streaming progress
    No timeout - streams progress updates
    """
    admin_id = get_jwt_identity()
    
    def generate():
        try:
            data = request.json
            
            txn_type = data.get('txn_type')
            txn_ids = data.get('txn_ids', [])
            reason = data.get('reason', 'Bulk marked as failed by admin').strip()
            
            if not all([txn_type, txn_ids, reason]):
                yield f"data: {json.dumps({'error': 'txn_type, txn_ids, and reason are required'})}\n\n"
                return
            
            if txn_type not in ['payin', 'payout']:
                yield f"data: {json.dumps({'error': 'txn_type must be payin or payout'})}\n\n"
                return
            
            if len(txn_ids) > 10000:
                yield f"data: {json.dumps({'error': 'Maximum 10,000 transactions allowed per bulk operation'})}\n\n"
                return
            
            total = len(txn_ids)
            processed = 0
            success_count = 0
            failed_count = 0
            callback_success = 0
            callback_failed = 0
            
            # Send initial status
            yield f"data: {json.dumps({'status': 'started', 'total': total})}\n\n"
            
            conn = get_db_connection()
            if not conn:
                yield f"data: {json.dumps({'error': 'Database connection failed'})}\n\n"
                return
            
            try:
                for txn_id in txn_ids:
                    try:
                        with conn.cursor() as cursor:
                            # Get transaction
                            if txn_type == 'payin':
                                cursor.execute("SELECT * FROM payin_transactions WHERE txn_id = %s", (txn_id,))
                            else:
                                cursor.execute("SELECT * FROM payout_transactions WHERE txn_id = %s", (txn_id,))
                            
                            txn = cursor.fetchone()
                            
                            if not txn:
                                failed_count += 1
                                processed += 1
                                yield f"data: {json.dumps({'progress': processed, 'total': total, 'txn_id': txn_id, 'status': 'not_found'})}\n\n"
                                continue
                            
                            if txn['status'] == 'FAILED':
                                failed_count += 1
                                processed += 1
                                yield f"data: {json.dumps({'progress': processed, 'total': total, 'txn_id': txn_id, 'status': 'already_failed'})}\n\n"
                                continue
                            
                            # Update status
                            if txn_type == 'payin':
                                cursor.execute("""
                                    UPDATE payin_transactions 
                                    SET status = 'FAILED', error_message = %s, updated_at = NOW(), completed_at = NOW()
                                    WHERE txn_id = %s
                                """, (reason, txn_id))
                            else:
                                cursor.execute("""
                                    UPDATE payout_transactions 
                                    SET status = 'FAILED', error_message = %s, updated_at = NOW(), completed_at = NOW()
                                    WHERE txn_id = %s
                                """, (reason, txn_id))
                                
                                # Refund amount to merchant wallet if it's a payout
                                if txn.get('merchant_id'):
                                    try:
                                        total_deducted = float(txn.get('amount', 0)) + float(txn.get('charge_amount', 0))
                                        if total_deducted > 0:
                                            from wallet_service import WalletService
                                            wallet_svc = WalletService()
                                            wallet_svc.credit_merchant_wallet(
                                                merchant_id=txn['merchant_id'],
                                                amount=total_deducted,
                                                description=f"Refund for manual failed payout: {txn_id}",
                                                reference_id=txn_id
                                            )
                                    except Exception as e:
                                        print(f"[MANUAL_RECON] Bulk wallet refund error: {str(e)}")
                            
                            conn.commit()
                            success_count += 1
                            
                            # Send callback if exists
                            callback_sent = False
                            if txn.get('callback_url'):
                                txn['status'] = 'FAILED'
                                txn['error_message'] = reason
                                callback_format = data.get('callback_format', 'maxpe' if txn_type == 'payout' else 'default')
                                callback_sent, _ = send_transaction_callback(txn, txn_type, callback_format)
                                
                                if callback_sent:
                                    callback_success += 1
                                else:
                                    callback_failed += 1
                            
                            processed += 1
                            
                            # Send progress update
                            yield f"data: {json.dumps({'progress': processed, 'total': total, 'txn_id': txn_id, 'status': 'success', 'callback_sent': callback_sent})}\n\n"
                            
                    except Exception as e:
                        failed_count += 1
                        processed += 1
                        yield f"data: {json.dumps({'progress': processed, 'total': total, 'txn_id': txn_id, 'status': 'error', 'error': str(e)})}\n\n"
                
                # Log bulk activity
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO admin_activity_logs 
                        (admin_id, action, details, ip_address, created_at)
                        VALUES (%s, %s, %s, %s, NOW())
                    """, (
                        admin_id,
                        'MANUAL_RECONCILIATION_BULK_MARK_FAILED',
                        json.dumps({
                            'txn_type': txn_type,
                            'total': total,
                            'success': success_count,
                            'failed': failed_count,
                            'callback_success': callback_success,
                            'callback_failed': callback_failed,
                            'reason': reason
                        }),
                        request.remote_addr
                    ))
                    conn.commit()
                
                # Send completion
                yield f"data: {json.dumps({'status': 'completed', 'total': total, 'success': success_count, 'failed': failed_count, 'callback_success': callback_success, 'callback_failed': callback_failed})}\n\n"
                
            finally:
                conn.close()
                
        except Exception as e:
            print(f"[MANUAL_RECON] Bulk mark failed error: {str(e)}")
            traceback.print_exc()
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@manual_recon_bp.route('/api/admin/manual-reconciliation/merchants', methods=['GET'])
@jwt_required()
def get_merchants_list():
    """
    Get list of all merchants for dropdown
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT merchant_id, full_name, mobile, email
                    FROM merchants
                    WHERE is_active = TRUE
                    ORDER BY full_name
                """)
                merchants = cursor.fetchall()
                
                return jsonify({
                    'success': True,
                    'merchants': merchants
                })
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[MANUAL_RECON] Get merchants error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
