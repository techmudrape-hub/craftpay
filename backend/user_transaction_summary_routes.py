"""
User Transaction Summary Routes
Admin can view payin/payout summary for any user with date and time filtering
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database_pooled import get_db_connection
from datetime import datetime, time
import pytz

user_txn_summary_bp = Blueprint('user_txn_summary', __name__, url_prefix='/api/admin/user-transaction-summary')

# Indian timezone
IST = pytz.timezone('Asia/Kolkata')

@user_txn_summary_bp.route('/merchants', methods=['GET'])
@jwt_required()
def get_merchants_for_summary():
    """Get all merchants for dropdown selection"""
    try:
        current_admin = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Verify admin
                cursor.execute("SELECT admin_id FROM admin_users WHERE admin_id = %s", (current_admin,))
                if not cursor.fetchone():
                    return jsonify({'success': False, 'message': 'Unauthorized'}), 403
                
                # Get all merchants
                cursor.execute("""
                    SELECT merchant_id, full_name, email, mobile
                    FROM merchants
                    WHERE is_active = TRUE
                    ORDER BY full_name ASC
                """)
                
                merchants = cursor.fetchall()
                
                return jsonify({
                    'success': True,
                    'merchants': merchants
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Get merchants for summary error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@user_txn_summary_bp.route('/summary', methods=['GET'])
@jwt_required()
def get_user_transaction_summary():
    """
    Get payin and payout summary for a user
    Query params:
    - merchant_id (required)
    - from_date (optional, format: YYYY-MM-DD)
    - to_date (optional, format: YYYY-MM-DD)
    - from_time (optional, format: HH:MM, in IST)
    - to_time (optional, format: HH:MM, in IST)
    """
    try:
        current_admin = get_jwt_identity()
        
        # Get query parameters
        merchant_id = request.args.get('merchant_id')
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        from_time = request.args.get('from_time')  # HH:MM format
        to_time = request.args.get('to_time')  # HH:MM format
        
        if not merchant_id:
            return jsonify({'success': False, 'message': 'merchant_id is required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Verify admin
                cursor.execute("SELECT admin_id FROM admin_users WHERE admin_id = %s", (current_admin,))
                if not cursor.fetchone():
                    return jsonify({'success': False, 'message': 'Unauthorized'}), 403
                
                # Get merchant details
                cursor.execute("""
                    SELECT merchant_id, full_name, email, mobile
                    FROM merchants
                    WHERE merchant_id = %s
                """, (merchant_id,))
                
                merchant = cursor.fetchone()
                if not merchant:
                    return jsonify({'success': False, 'message': 'Merchant not found'}), 404
                
                # Build date-time filter conditions
                date_time_conditions = []
                params = []
                
                if from_date and to_date:
                    # Both dates provided
                    if from_time and to_time:
                        # With time range
                        date_time_conditions.append("""
                            (DATE(created_at) > %s OR 
                             (DATE(created_at) = %s AND TIME(created_at) >= %s))
                            AND
                            (DATE(created_at) < %s OR 
                             (DATE(created_at) = %s AND TIME(created_at) <= %s))
                        """)
                        params.extend([from_date, from_date, from_time, to_date, to_date, to_time])
                    else:
                        # Without time range
                        date_time_conditions.append("DATE(created_at) >= %s AND DATE(created_at) <= %s")
                        params.extend([from_date, to_date])
                elif from_date:
                    # Only from_date
                    if from_time:
                        date_time_conditions.append("""
                            (DATE(created_at) > %s OR 
                             (DATE(created_at) = %s AND TIME(created_at) >= %s))
                        """)
                        params.extend([from_date, from_date, from_time])
                    else:
                        date_time_conditions.append("DATE(created_at) >= %s")
                        params.append(from_date)
                elif to_date:
                    # Only to_date
                    if to_time:
                        date_time_conditions.append("""
                            (DATE(created_at) < %s OR 
                             (DATE(created_at) = %s AND TIME(created_at) <= %s))
                        """)
                        params.extend([to_date, to_date, to_time])
                    else:
                        date_time_conditions.append("DATE(created_at) <= %s")
                        params.append(to_date)
                
                date_time_filter = " AND " + " AND ".join(date_time_conditions) if date_time_conditions else ""
                
                # Get PAYIN summary
                payin_query = f"""
                    SELECT 
                        COUNT(*) as total_count,
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as total_payin,
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN charge_amount ELSE 0 END), 0) as total_charges,
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payin,
                        COUNT(CASE WHEN status = 'SUCCESS' THEN 1 END) as success_count,
                        COUNT(CASE WHEN status = 'PENDING' THEN 1 END) as pending_count,
                        COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as failed_count
                    FROM payin_transactions
                    WHERE merchant_id = %s {date_time_filter}
                """
                
                cursor.execute(payin_query, [merchant_id] + params)
                payin_summary = cursor.fetchone()
                
                # Get PAYOUT summary
                payout_query = f"""
                    SELECT 
                        COUNT(*) as total_count,
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as total_payout,
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN charge_amount ELSE 0 END), 0) as total_charges,
                        COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN (amount + charge_amount) ELSE 0 END), 0) as net_payout,
                        COUNT(CASE WHEN status = 'SUCCESS' THEN 1 END) as success_count,
                        COUNT(CASE WHEN status IN ('PENDING', 'QUEUED') THEN 1 END) as pending_count,
                        COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as failed_count
                    FROM payout_transactions
                    WHERE merchant_id = %s {date_time_filter}
                """
                
                cursor.execute(payout_query, [merchant_id] + params)
                payout_summary = cursor.fetchone()
                
                # Get recent transactions for preview
                recent_payin_query = f"""
                    SELECT 
                        txn_id, order_id, amount, charge_amount, net_amount, 
                        status, payment_mode, created_at, completed_at
                    FROM payin_transactions
                    WHERE merchant_id = %s {date_time_filter}
                    ORDER BY created_at DESC
                    LIMIT 10
                """
                
                cursor.execute(recent_payin_query, [merchant_id] + params)
                recent_payins = cursor.fetchall()
                
                recent_payout_query = f"""
                    SELECT 
                        txn_id, order_id, amount, charge_amount, 
                        status, bene_name, account_no, created_at, completed_at
                    FROM payout_transactions
                    WHERE merchant_id = %s {date_time_filter}
                    ORDER BY created_at DESC
                    LIMIT 10
                """
                
                cursor.execute(recent_payout_query, [merchant_id] + params)
                recent_payouts = cursor.fetchall()
                
                # Format data
                for txn in recent_payins:
                    if txn.get('created_at'):
                        txn['created_at'] = txn['created_at'].isoformat()
                    if txn.get('completed_at'):
                        txn['completed_at'] = txn['completed_at'].isoformat()
                    txn['amount'] = float(txn['amount']) if txn.get('amount') else 0.0
                    txn['charge_amount'] = float(txn['charge_amount']) if txn.get('charge_amount') else 0.0
                    txn['net_amount'] = float(txn['net_amount']) if txn.get('net_amount') else 0.0
                
                for txn in recent_payouts:
                    if txn.get('created_at'):
                        txn['created_at'] = txn['created_at'].isoformat()
                    if txn.get('completed_at'):
                        txn['completed_at'] = txn['completed_at'].isoformat()
                    txn['amount'] = float(txn['amount']) if txn.get('amount') else 0.0
                    txn['charge_amount'] = float(txn['charge_amount']) if txn.get('charge_amount') else 0.0
                
                return jsonify({
                    'success': True,
                    'merchant': merchant,
                    'filters': {
                        'from_date': from_date,
                        'to_date': to_date,
                        'from_time': from_time,
                        'to_time': to_time
                    },
                    'payin_summary': {
                        'total_count': payin_summary['total_count'],
                        'total_payin': float(payin_summary['total_payin']),
                        'total_charges': float(payin_summary['total_charges']),
                        'net_payin': float(payin_summary['net_payin']),
                        'success_count': payin_summary['success_count'],
                        'pending_count': payin_summary['pending_count'],
                        'failed_count': payin_summary['failed_count']
                    },
                    'payout_summary': {
                        'total_count': payout_summary['total_count'],
                        'total_payout': float(payout_summary['total_payout']),
                        'total_charges': float(payout_summary['total_charges']),
                        'net_payout': float(payout_summary['net_payout']),
                        'success_count': payout_summary['success_count'],
                        'pending_count': payout_summary['pending_count'],
                        'failed_count': payout_summary['failed_count']
                    },
                    'recent_payins': recent_payins,
                    'recent_payouts': recent_payouts
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Get user transaction summary error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal server error'}), 500
