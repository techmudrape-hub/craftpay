"""
MaxPe Checkout Routes - MySQL-Based Time Calculation Fix
This version uses MySQL's TIMESTAMPDIFF to avoid all Python timezone issues
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection

maxpe_checkout_bp = Blueprint('maxpe_checkout', __name__, url_prefix='/api/checkout')

@maxpe_checkout_bp.route('/maxpe/validate', methods=['GET'])
def validate_checkout_link():
    """
    Validate if checkout link is still valid
    Uses MySQL TIMESTAMPDIFF to avoid timezone issues
    """
    try:
        order_id = request.args.get('order_id')
        
        print(f"[Checkout Validate] Validating order_id: {order_id}")
        
        if not order_id:
            return jsonify({'valid': False, 'reason': 'order_id is required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'valid': True, 'reason': 'Unable to validate'}), 200
        
        try:
            with conn.cursor() as cursor:
                # Use MySQL's TIMESTAMPDIFF - works globally regardless of timezone
                cursor.execute("""
                    SELECT 
                        status, completed_at, checkout_expired_at, bank_ref_no, 
                        amount, txn_id, created_at, error_message,
                        TIMESTAMPDIFF(SECOND, created_at, NOW()) as seconds_elapsed
                    FROM payin_transactions
                    WHERE order_id = %s AND pg_partner = 'MAXPE'
                    ORDER BY created_at DESC LIMIT 1
                """, (order_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    return jsonify({'valid': True, 'reason': 'OK'}), 200
                
                seconds_elapsed = txn['seconds_elapsed'] or 0
                print(f"[Validate] Elapsed: {seconds_elapsed}s ({seconds_elapsed/60:.1f}min)")
                
                # Already expired?
                if txn['checkout_expired_at']:
                    return jsonify({
                        'valid': False,
                        'reason': 'EXPIRED_TIMEOUT',
                        'transaction': {
                            'order_id': order_id,
                            'status': 'EXPIRED',
                            'created_at': txn['created_at'].isoformat() if txn['created_at'] else None,
                            'expired_at': txn['checkout_expired_at'].isoformat(),
                            'amount': float(txn['amount']) if txn['amount'] else 0,
                            'txn_id': txn['txn_id']
                        }
                    }), 200
                
                # Already completed?
                if txn['status'] in ('SUCCESS', 'FAILED'):
                    return jsonify({
                        'valid': False,
                        'reason': 'ALREADY_COMPLETED',
                        'transaction': {
                            'order_id': order_id,
                            'status': txn['status'],
                            'completed_at': txn['completed_at'].isoformat() if txn['completed_at'] else None,
                            'utr': txn['bank_ref_no'],
                            'amount': float(txn['amount']) if txn['amount'] else 0,
                            'txn_id': txn['txn_id']
                        }
                    }), 200
                
                # Should expire? (> 360 seconds = 6 minutes)
                if seconds_elapsed > 360:
                    print(f"[Validate] Expiring link (>{seconds_elapsed}s)")
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET checkout_expired_at = NOW(), status = 'FAILED',
                            error_message = 'Checkout link expired - No callback received within 6 minutes',
                            updated_at = NOW()
                        WHERE order_id = %s AND pg_partner = 'MAXPE'
                        AND status IN ('INITIATED', 'PENDING')
                    """, (order_id,))
                    conn.commit()
                    
                    return jsonify({
                        'valid': False,
                        'reason': 'EXPIRED_TIMEOUT',
                        'transaction': {
                            'order_id': order_id,
                            'status': 'EXPIRED',
                            'created_at': txn['created_at'].isoformat() if txn['created_at'] else None,
                            'amount': float(txn['amount']) if txn['amount'] else 0,
                            'txn_id': txn['txn_id']
                        }
                    }), 200
                
                return jsonify({'valid': True, 'reason': 'OK'}), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[Checkout Validate] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'valid': True, 'reason': 'Unable to validate'}), 200

@maxpe_checkout_bp.route('/maxpe/status', methods=['GET'])
def get_maxpe_checkout_status():
    """
    Get payment status - uses MySQL TIMESTAMPDIFF
    """
    try:
        order_id = request.args.get('order_id')
        
        if not order_id:
            return jsonify({'success': False, 'message': 'order_id is required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        txn_id, order_id, amount, status, bank_ref_no, 
                        payment_mode, completed_at, created_at, checkout_expired_at,
                        error_message,
                        TIMESTAMPDIFF(SECOND, created_at, NOW()) as seconds_elapsed
                    FROM payin_transactions
                    WHERE order_id = %s AND pg_partner = 'MAXPE'
                    ORDER BY created_at DESC LIMIT 1
                """, (order_id,))
                
                txn = cursor.fetchone()
                
                if txn:
                    seconds_elapsed = txn['seconds_elapsed'] or 0
                    
                    # Already expired?
                    if txn['checkout_expired_at']:
                        return jsonify({
                            'success': True,
                            'transaction': {
                                'txn_id': txn['txn_id'],
                                'order_id': txn['order_id'],
                                'amount': float(txn['amount']) if txn['amount'] else 0,
                                'status': 'EXPIRED',
                                'created_at': txn['created_at'].isoformat() if txn['created_at'] else None,
                                'expired_at': txn['checkout_expired_at'].isoformat()
                            }
                        }), 200
                    
                    # Should expire?
                    if txn['status'] in ('INITIATED', 'PENDING') and seconds_elapsed > 360:
                        cursor.execute("""
                            UPDATE payin_transactions
                            SET checkout_expired_at = NOW(), status = 'FAILED',
                                error_message = 'Checkout link expired - No callback received within 6 minutes',
                                updated_at = NOW()
                            WHERE order_id = %s AND pg_partner = 'MAXPE'
                            AND status IN ('INITIATED', 'PENDING')
                        """, (order_id,))
                        conn.commit()
                        
                        return jsonify({
                            'success': True,
                            'transaction': {
                                'txn_id': txn['txn_id'],
                                'order_id': txn['order_id'],
                                'amount': float(txn['amount']) if txn['amount'] else 0,
                                'status': 'EXPIRED',
                                'created_at': txn['created_at'].isoformat() if txn['created_at'] else None
                            }
                        }), 200
                    
                    return jsonify({
                        'success': True,
                        'transaction': {
                            'txn_id': txn['txn_id'],
                            'order_id': txn['order_id'],
                            'amount': float(txn['amount']) if txn['amount'] else 0,
                            'status': txn['status'],
                            'bank_ref_no': txn['bank_ref_no'],
                            'utr': txn['bank_ref_no'],
                            'payment_mode': txn['payment_mode'] or 'UPI',
                            'completed_at': txn['completed_at'].isoformat() if txn['completed_at'] else None,
                            'created_at': txn['created_at'].isoformat() if txn['created_at'] else None
                        }
                    }), 200
                else:
                    return jsonify({
                        'success': True,
                        'transaction': {'order_id': order_id, 'status': 'PENDING', 'amount': 0}
                    }), 200
                    
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[Checkout Status] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal server error'}), 500
