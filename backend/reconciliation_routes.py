from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_db_connection
from datetime import datetime
import requests
import json

reconciliation_bp = Blueprint('reconciliation', __name__)


@reconciliation_bp.route('/api/admin/reconciliation/payins', methods=['POST'])
@jwt_required()
def get_reconciliation_payins():
    """Get initiated payins for reconciliation - IST date filtering"""
    try:
        admin_id = get_jwt_identity()
        data = request.json
        merchant_id = data.get('merchant_id')
        from_date = data.get('from_date')
        to_date = data.get('to_date')
        page = data.get('page', 1)
        page_size = data.get('page_size', 500)
        
        print(f"[RECONCILIATION] Fetching payins for merchant: {merchant_id}, from: {from_date}, to: {to_date}")
        
        if not all([merchant_id, from_date, to_date]):
            return jsonify({
                'success': False,
                'message': 'merchant_id, from_date, and to_date are required'
            }), 400
        
        conn = get_db_connection()
        
        with conn.cursor() as cursor:
            # Count query - session timezone is already IST, use DATE directly
            count_query = """
                SELECT COUNT(*) as total
                FROM payin_transactions pt
                WHERE pt.merchant_id = %s
                AND pt.status = 'INITIATED'
                AND DATE(pt.created_at) BETWEEN %s AND %s
            """
            
            cursor.execute(count_query, (merchant_id, from_date, to_date))
            count_result = cursor.fetchone()
            total_count = count_result['total'] if count_result else 0
            
            print(f"[RECONCILIATION] Total matching records: {total_count}")
            
            if total_count > 20000:
                return jsonify({
                    'success': False,
                    'message': f'Too many records found ({total_count}). Please narrow your date range to less than 20,000 records.',
                    'total_count': total_count
                }), 400
            
            offset = (page - 1) * page_size
            
            # Fetch payins - session timezone is already IST, no conversion needed
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
                    pt.created_at,
                    pt.callback_url,
                    m.full_name as merchant_name,
                    m.mobile as merchant_mobile
                FROM payin_transactions pt
                LEFT JOIN merchants m ON pt.merchant_id = m.merchant_id
                WHERE pt.merchant_id = %s
                AND pt.status = 'INITIATED'
                AND DATE(pt.created_at) BETWEEN %s AND %s
                ORDER BY pt.created_at DESC
                LIMIT %s OFFSET %s
            """
            
            cursor.execute(query, (merchant_id, from_date, to_date, page_size, offset))
            payins = cursor.fetchall()
            
            print(f"[RECONCILIATION] Found {len(payins)} initiated payins")
        
        conn.close()
        
        return jsonify({
            'success': True,
            'payins': payins,
            'count': len(payins),
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size if total_count > 0 else 0
        })
        
    except Exception as e:
        print(f"[RECONCILIATION] Error fetching payins: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@reconciliation_bp.route('/api/admin/reconciliation/payouts', methods=['POST'])
@jwt_required()
def get_reconciliation_payouts():
    """Get queued/initiated payouts for reconciliation - IST date filtering"""
    try:
        admin_id = get_jwt_identity()
        data = request.json
        merchant_id = data.get('merchant_id')
        from_date = data.get('from_date')
        to_date = data.get('to_date')
        page = data.get('page', 1)
        page_size = data.get('page_size', 500)
        
        print(f"[RECONCILIATION] Fetching payouts for merchant: {merchant_id}, from: {from_date}, to: {to_date}")
        
        if not all([merchant_id, from_date, to_date]):
            return jsonify({
                'success': False,
                'message': 'merchant_id, from_date, and to_date are required'
            }), 400
        
        conn = get_db_connection()
        
        with conn.cursor() as cursor:
            # Count query - session timezone is already IST, use DATE directly
            count_query = """
                SELECT COUNT(*) as total
                FROM payout_transactions p
                WHERE p.merchant_id = %s
                AND p.status IN ('QUEUED', 'INITIATED')
                AND DATE(p.created_at) BETWEEN %s AND %s
            """
            
            cursor.execute(count_query, (merchant_id, from_date, to_date))
            count_result = cursor.fetchone()
            total_count = count_result['total'] if count_result else 0
            
            print(f"[RECONCILIATION] Total matching records: {total_count}")
            
            if total_count > 20000:
                return jsonify({
                    'success': False,
                    'message': f'Too many records found ({total_count}). Please narrow your date range to less than 20,000 records.',
                    'total_count': total_count
                }), 400
            
            offset = (page - 1) * page_size
            
            # Fetch payouts - session timezone is already IST, no conversion needed
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
                    p.ifsc_code,
                    p.pg_partner,
                    p.pg_txn_id,
                    p.created_at,
                    p.callback_url,
                    m.full_name as merchant_name,
                    m.mobile as merchant_mobile
                FROM payout_transactions p
                LEFT JOIN merchants m ON p.merchant_id = m.merchant_id
                WHERE p.merchant_id = %s
                AND p.status IN ('QUEUED', 'INITIATED')
                AND DATE(p.created_at) BETWEEN %s AND %s
                ORDER BY p.created_at DESC
                LIMIT %s OFFSET %s
            """
            
            cursor.execute(query, (merchant_id, from_date, to_date, page_size, offset))
            payouts = cursor.fetchall()
            
            print(f"[RECONCILIATION] Found {len(payouts)} queued/initiated payouts")
        
        conn.close()
        
        return jsonify({
            'success': True,
            'payouts': payouts,
            'count': len(payouts),
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size if total_count > 0 else 0
        })
        
    except Exception as e:
        print(f"[RECONCILIATION] Error fetching payouts: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@reconciliation_bp.route('/api/admin/reconciliation/process-failed-payins', methods=['POST'])
@jwt_required()
def process_failed_payins():
    """Process selected payins as failed and send callbacks - Robust error handling"""
    try:
        admin_id = get_jwt_identity()
        data = request.json
        txn_ids = data.get('txn_ids', [])
        
        print(f"[RECONCILIATION] Processing {len(txn_ids)} payins as failed")
        
        if not txn_ids:
            return jsonify({
                'success': False,
                'message': 'No transaction IDs provided'
            }), 400
        
        conn = get_db_connection()
        
        processed = []
        failed = []
        
        for idx, txn_id in enumerate(txn_ids, 1):
            print(f"[RECONCILIATION] Processing {idx}/{len(txn_ids)}: {txn_id}")
            
            try:
                with conn.cursor() as cursor:
                    # Get transaction details
                    cursor.execute("""
                        SELECT txn_id, order_id, merchant_id, amount, status, callback_url
                        FROM payin_transactions
                        WHERE txn_id = %s AND status = 'INITIATED'
                    """, (txn_id,))
                    
                    txn = cursor.fetchone()
                    
                    if not txn:
                        failed.append({
                            'txn_id': txn_id,
                            'reason': 'Transaction not found or not in INITIATED status'
                        })
                        continue
                    
                    # Update status to FAILED
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET status = 'FAILED',
                            remarks = 'PAYMENT NOT RECEIVED. QR EXPIRED AUTOMATICALLY.',
                            error_message = 'Manual reconciliation - QR expired',
                            completed_at = NOW()
                        WHERE txn_id = %s
                    """, (txn_id,))
                    
                    conn.commit()
                    
                    print(f"[RECONCILIATION] ✓ Marked payin {txn_id} as FAILED")
                    
                    # Send callback if URL exists - with robust error handling
                    callback_sent = False
                    callback_response = None
                    
                    if txn['callback_url']:
                        try:
                            callback_payload = {
                                'txn_id': txn['txn_id'],
                                'order_id': txn['order_id'],
                                'merchant_id': txn['merchant_id'],
                                'amount': float(txn['amount']),
                                'status': 'FAILED',
                                'message': 'PAYMENT NOT RECEIVED. QR EXPIRED AUTOMATICALLY.',
                                'timestamp': datetime.now().isoformat()
                            }
                            
                            print(f"[RECONCILIATION] Sending callback to: {txn['callback_url']}")
                            
                            response = requests.post(
                                txn['callback_url'],
                                json=callback_payload,
                                timeout=60  # Increased to 60 seconds
                            )
                            
                            callback_sent = True
                            callback_response = {
                                'status_code': response.status_code,
                                'response': response.text[:200]
                            }
                            
                            print(f"[RECONCILIATION] ✓ Callback sent for {txn_id}: HTTP {response.status_code}")
                            
                        except requests.exceptions.Timeout:
                            print(f"[RECONCILIATION] ⚠ Callback timeout for {txn_id} (60s)")
                            callback_response = {
                                'error': 'Callback timeout after 60 seconds'
                            }
                        except requests.exceptions.ConnectionError as e:
                            print(f"[RECONCILIATION] ⚠ Callback connection error for {txn_id}: {str(e)}")
                            callback_response = {
                                'error': f'Connection error: {str(e)[:100]}'
                            }
                        except Exception as callback_error:
                            print(f"[RECONCILIATION] ⚠ Callback error for {txn_id}: {str(callback_error)}")
                            callback_response = {
                                'error': str(callback_error)[:200]
                            }
                    else:
                        print(f"[RECONCILIATION] No callback URL for {txn_id}")
                    
                    processed.append({
                        'txn_id': txn_id,
                        'callback_sent': callback_sent,
                        'callback_response': callback_response
                    })
                    
            except Exception as e:
                conn.rollback()
                print(f"[RECONCILIATION] ✗ Error processing payin {txn_id}: {str(e)}")
                failed.append({
                    'txn_id': txn_id,
                    'reason': str(e)[:200]
                })
        
        conn.close()
        
        print(f"[RECONCILIATION] Complete: {len(processed)} processed, {len(failed)} failed")
        
        return jsonify({
            'success': True,
            'processed': processed,
            'failed': failed,
            'total_processed': len(processed),
            'total_failed': len(failed)
        })
        
    except Exception as e:
        print(f"[RECONCILIATION] Error processing failed payins: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@reconciliation_bp.route('/api/admin/reconciliation/process-failed-payouts', methods=['POST'])
@jwt_required()
def process_failed_payouts():
    """Process selected payouts as failed and send callbacks - Robust error handling"""
    try:
        admin_id = get_jwt_identity()
        data = request.json
        txn_ids = data.get('txn_ids', [])
        
        print(f"[RECONCILIATION] Processing {len(txn_ids)} payouts as failed")
        
        if not txn_ids:
            return jsonify({
                'success': False,
                'message': 'No transaction IDs provided'
            }), 400
        
        conn = get_db_connection()
        
        processed = []
        failed = []
        
        for idx, txn_id in enumerate(txn_ids, 1):
            print(f"[RECONCILIATION] Processing {idx}/{len(txn_ids)}: {txn_id}")
            
            try:
                with conn.cursor() as cursor:
                    # Get transaction details
                    cursor.execute("""
                        SELECT txn_id, reference_id, order_id, merchant_id, amount, net_amount, 
                               status, callback_url, charge_amount
                        FROM payout_transactions
                        WHERE txn_id = %s AND status IN ('QUEUED', 'INITIATED')
                    """, (txn_id,))
                    
                    txn = cursor.fetchone()
                    
                    if not txn:
                        failed.append({
                            'txn_id': txn_id,
                            'reason': 'Transaction not found or not in QUEUED/INITIATED status'
                        })
                        continue
                    
                    # Update status to FAILED
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET status = 'FAILED',
                            remarks = 'Manual reconciliation - marked as failed',
                            error_message = 'Failed during manual reconciliation',
                            completed_at = NOW()
                        WHERE txn_id = %s
                    """, (txn_id,))
                    
                    conn.commit()
                    
                    print(f"[RECONCILIATION] ✓ Marked payout {txn_id} as FAILED")
                    
                    # Send callback if URL exists - with robust error handling
                    callback_sent = False
                    callback_response = None
                    
                    if txn['callback_url']:
                        try:
                            callback_payload = {
                                'txn_id': txn['txn_id'],
                                'reference_id': txn['reference_id'],
                                'order_id': txn['order_id'],
                                'merchant_id': txn['merchant_id'],
                                'amount': float(txn['amount']),
                                'status': 'FAILED',
                                'message': 'Payout failed during manual reconciliation',
                                'timestamp': datetime.now().isoformat()
                            }
                            
                            print(f"[RECONCILIATION] Sending callback to: {txn['callback_url']}")
                            
                            response = requests.post(
                                txn['callback_url'],
                                json=callback_payload,
                                timeout=60  # Increased to 60 seconds
                            )
                            
                            callback_sent = True
                            callback_response = {
                                'status_code': response.status_code,
                                'response': response.text[:200]
                            }
                            
                            print(f"[RECONCILIATION] ✓ Callback sent for {txn_id}: HTTP {response.status_code}")
                            
                        except requests.exceptions.Timeout:
                            print(f"[RECONCILIATION] ⚠ Callback timeout for {txn_id} (60s)")
                            callback_response = {
                                'error': 'Callback timeout after 60 seconds'
                            }
                        except requests.exceptions.ConnectionError as e:
                            print(f"[RECONCILIATION] ⚠ Callback connection error for {txn_id}: {str(e)}")
                            callback_response = {
                                'error': f'Connection error: {str(e)[:100]}'
                            }
                        except Exception as callback_error:
                            print(f"[RECONCILIATION] ⚠ Callback error for {txn_id}: {str(callback_error)}")
                            callback_response = {
                                'error': str(callback_error)[:200]
                            }
                    else:
                        print(f"[RECONCILIATION] No callback URL for {txn_id}")
                    
                    processed.append({
                        'txn_id': txn_id,
                        'callback_sent': callback_sent,
                        'callback_response': callback_response
                    })
                    
            except Exception as e:
                conn.rollback()
                print(f"[RECONCILIATION] ✗ Error processing payout {txn_id}: {str(e)}")
                failed.append({
                    'txn_id': txn_id,
                    'reason': str(e)[:200]
                })
        
        conn.close()
        
        print(f"[RECONCILIATION] Complete: {len(processed)} processed, {len(failed)} failed")
        
        return jsonify({
            'success': True,
            'processed': processed,
            'failed': failed,
            'total_processed': len(processed),
            'total_failed': len(failed)
        })
        
    except Exception as e:
        print(f"[RECONCILIATION] Error processing failed payouts: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@reconciliation_bp.route('/api/admin/reconciliation/merchants', methods=['GET'])
@jwt_required()
def get_merchants_list():
    """Get list of all merchants for dropdown"""
    try:
        admin_id = get_jwt_identity()
        conn = get_db_connection()
        
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT merchant_id, full_name, mobile, email
                FROM merchants
                WHERE is_active = 1
                ORDER BY full_name
            """)
            
            merchants = cursor.fetchall()
            
            print(f"[RECONCILIATION] Fetched {len(merchants)} active merchants")
        
        conn.close()
        
        return jsonify({
            'success': True,
            'merchants': merchants
        })
        
    except Exception as e:
        print(f"[RECONCILIATION] Error fetching merchants: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
