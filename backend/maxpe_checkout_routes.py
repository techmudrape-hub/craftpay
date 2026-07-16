"""
MaxPe Checkout Routes
Public routes for MaxPe checkout page (no authentication required)
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from datetime import datetime, timedelta
import threading
import time

maxpe_checkout_bp = Blueprint('maxpe_checkout', __name__, url_prefix='/api/checkout')

# Simple in-memory cache for checkout callbacks (order_id -> callback_data)
# In production, use Redis or similar
checkout_callback_cache = {}

# Cache cleanup function
def cleanup_expired_cache():
    """Remove expired cache entries (older than 10 minutes)"""
    while True:
        try:
            time.sleep(60)  # Run every minute
            current_time = datetime.now()
            expired_keys = []
            
            for order_id, data in checkout_callback_cache.items():
                if (current_time - data['timestamp']).total_seconds() > 600:  # 10 minutes
                    expired_keys.append(order_id)
            
            for key in expired_keys:
                del checkout_callback_cache[key]
                print(f"[Cache Cleanup] Removed expired cache for order_id: {key}")
                
        except Exception as e:
            print(f"[Cache Cleanup] Error: {e}")

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_expired_cache, daemon=True)
cleanup_thread.start()

@maxpe_checkout_bp.route('/maxpe/callback', methods=['POST'])
def receive_checkout_callback():
    """
    Receive callback notification for checkout page
    This endpoint is called by the MaxPe callback handler to notify the checkout page
    """
    try:
        data = request.get_json()
        
        print(f"[Checkout Callback] Received callback: {data}")
        
        order_id = data.get('order_id')
        status = data.get('status')
        amount = data.get('amount')
        utr = data.get('utr')
        txn_id = data.get('txn_id')
        
        if not order_id or not status:
            return jsonify({
                'success': False,
                'message': 'order_id and status are required'
            }), 400
        
        print(f"[Checkout Callback] Order: {order_id}, Status: {status}, UTR: {utr}")
        
        # Store in cache with timestamp
        checkout_callback_cache[order_id] = {
            'order_id': order_id,
            'status': status,
            'amount': amount,
            'utr': utr,
            'bank_ref_no': utr,
            'txn_id': txn_id,
            'completed_at': data.get('completed_at'),
            'timestamp': datetime.now()
        }
        
        print(f"[Checkout Callback] ✅ Stored in cache for order: {order_id}")
        
        return jsonify({
            'success': True,
            'message': 'Checkout callback received'
        }), 200
        
    except Exception as e:
        print(f"[Checkout Callback] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@maxpe_checkout_bp.route('/maxpe/clear-cache', methods=['POST'])
def clear_checkout_cache():
    """
    Clear cache for a specific order_id
    This is called when user starts a new payment attempt to prevent showing old success data
    """
    try:
        order_id = request.args.get('order_id')
        
        if not order_id:
            return jsonify({
                'success': False,
                'message': 'order_id is required'
            }), 400
        
        # Remove from cache if exists
        if order_id in checkout_callback_cache:
            del checkout_callback_cache[order_id]
            print(f"[Clear Cache] ✅ Cleared cache for order: {order_id}")
        else:
            print(f"[Clear Cache] No cache found for order: {order_id}")
        
        return jsonify({
            'success': True,
            'message': 'Cache cleared'
        }), 200
        
    except Exception as e:
        print(f"[Clear Cache] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@maxpe_checkout_bp.route('/maxpe/validate', methods=['GET'])
def validate_checkout_link():
    """
    Validate if checkout link is still valid (not already completed or expired)
    Query params: order_id
    Returns: { valid: true/false, reason: string, transaction: {...} }
    """
    try:
        order_id = request.args.get('order_id')
        
        print(f"[Checkout Validate] Validating order_id: {order_id}")
        
        if not order_id:
            return jsonify({
                'valid': False,
                'reason': 'order_id is required'
            }), 400
        
        # Check database to see if this order_id already has a completed/failed/expired payment
        conn = get_db_connection()
        if not conn:
            print(f"[Checkout Validate] Database connection failed")
            # On DB error, allow payment to proceed
            return jsonify({
                'valid': True,
                'reason': 'Unable to validate'
            }), 200
        
        try:
            with conn.cursor() as cursor:
                # Use MySQL's TIMESTAMPDIFF to calculate elapsed time
                # This avoids all Python timezone issues - MySQL handles it internally
                cursor.execute("""
                    SELECT status, completed_at, checkout_expired_at, bank_ref_no, 
                           amount, txn_id, created_at, error_message,
                           TIMESTAMPDIFF(SECOND, created_at, NOW()) as seconds_elapsed
                    FROM payin_transactions
                    WHERE order_id = %s 
                    AND pg_partner = 'MAXPE'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (order_id,))
                
                txn = cursor.fetchone()
                
                if not txn:
                    print(f"[Checkout Validate] ✅ Order not found, link is valid: {order_id}")
                    return jsonify({
                        'valid': True,
                        'reason': 'OK'
                    }), 200
                
                seconds_elapsed = txn['seconds_elapsed'] or 0
                print(f"[Checkout Validate] Elapsed: {seconds_elapsed}s ({seconds_elapsed/60:.1f}min)")
                
                # Check if expired due to timeout
                if txn['checkout_expired_at'] is not None:
                    print(f"[Checkout Validate] ❌ Link expired due to timeout: {order_id}")
                    print(f"  - Created: {txn['created_at']}")
                    print(f"  - Expired: {txn['checkout_expired_at']}")
                    
                    return jsonify({
                        'valid': False,
                        'reason': 'EXPIRED_TIMEOUT',
                        'transaction': {
                            'order_id': order_id,
                            'status': 'EXPIRED',
                            'created_at': txn['created_at'].isoformat() if txn.get('created_at') else None,
                            'expired_at': txn['checkout_expired_at'].isoformat() if txn.get('checkout_expired_at') else None,
                            'amount': float(txn['amount']) if txn['amount'] else 0,
                            'txn_id': txn['txn_id'],
                            'error_message': txn['error_message']
                        }
                    }), 200
                
                # Check if already completed (SUCCESS or FAILED)
                if txn['status'] in ('SUCCESS', 'FAILED'):
                    print(f"[Checkout Validate] ❌ Order already completed: {order_id}")
                    print(f"  - Status: {txn['status']}")
                    print(f"  - Completed: {txn['completed_at']}")
                    print(f"  - UTR: {txn['bank_ref_no']}")
                    
                    return jsonify({
                        'valid': False,
                        'reason': 'ALREADY_COMPLETED',
                        'transaction': {
                            'order_id': order_id,
                            'status': txn['status'],
                            'completed_at': txn['completed_at'].isoformat() if txn.get('completed_at') else None,
                            'utr': txn['bank_ref_no'],
                            'amount': float(txn['amount']) if txn['amount'] else 0,
                            'txn_id': txn['txn_id']
                        }
                    }), 200
                
                # Check if link should be expired (> 360 seconds = 6 minutes)
                if seconds_elapsed > 360:
                    print(f"[Checkout Validate] ❌ Link expired (>{seconds_elapsed}s): {order_id}")
                    
                    # Mark as expired (but keep original status, don't change to FAILED)
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET checkout_expired_at = NOW(),
                            error_message = 'Checkout link expired - No callback received within 6 minutes',
                            updated_at = NOW()
                        WHERE order_id = %s
                        AND pg_partner = 'MAXPE'
                        AND status IN ('INITIATED', 'PENDING')
                    """, (order_id,))
                    conn.commit()
                    
                    return jsonify({
                        'valid': False,
                        'reason': 'EXPIRED_TIMEOUT',
                        'transaction': {
                            'order_id': order_id,
                            'status': 'EXPIRED',
                            'created_at': txn['created_at'].isoformat() if txn.get('created_at') else None,
                            'amount': float(txn['amount']) if txn['amount'] else 0,
                            'txn_id': txn['txn_id']
                        }
                    }), 200
                
                print(f"[Checkout Validate] ✅ Order is valid: {order_id}")
                return jsonify({
                    'valid': True,
                    'reason': 'OK'
                }), 200
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[Checkout Validate] ERROR: {e}")
        import traceback
        traceback.print_exc()
        # On error, allow payment to proceed
        return jsonify({
            'valid': True,
            'reason': 'Unable to validate'
        }), 200

@maxpe_checkout_bp.route('/maxpe/status', methods=['GET'])
def get_maxpe_checkout_status():
    """
    Get payment status for MaxPe checkout page (no auth required)
    Query params: order_id
    """
    try:
        order_id = request.args.get('order_id')
        
        print(f"[Checkout Status] Checking status for order_id: {order_id}")
        
        if not order_id:
            return jsonify({
                'success': False,
                'message': 'order_id is required'
            }), 400
        
        # Check DATABASE directly for real-time status
        # This ensures we detect SUCCESS immediately when callback updates the database
        conn = get_db_connection()
        if not conn:
            print(f"[Checkout Status] Database connection failed")
            return jsonify({
                'success': False,
                'message': 'Database connection failed'
            }), 500
        
        try:
            with conn.cursor() as cursor:
                # Use MySQL's TIMESTAMPDIFF to calculate elapsed time
                cursor.execute("""
                    SELECT txn_id, order_id, amount, status, bank_ref_no, 
                           payment_mode, completed_at, created_at, checkout_expired_at,
                           error_message,
                           TIMESTAMPDIFF(SECOND, created_at, NOW()) as seconds_elapsed
                    FROM payin_transactions
                    WHERE order_id = %s 
                    AND pg_partner = 'MAXPE'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (order_id,))
                
                txn = cursor.fetchone()
                
                if txn:
                    seconds_elapsed = txn['seconds_elapsed'] or 0
                    print(f"[Checkout Status] Elapsed: {seconds_elapsed}s ({seconds_elapsed/60:.1f}min)")
                    
                    # Check if expired due to timeout
                    if txn['checkout_expired_at'] is not None:
                        print(f"[Checkout Status] ⏰ Transaction expired: {order_id}")
                        return jsonify({
                            'success': True,
                            'transaction': {
                                'txn_id': txn['txn_id'],
                                'order_id': txn['order_id'],
                                'amount': float(txn['amount']) if txn['amount'] else 0,
                                'status': 'EXPIRED',
                                'created_at': txn['created_at'].isoformat() if txn.get('created_at') else None,
                                'expired_at': txn['checkout_expired_at'].isoformat() if txn.get('checkout_expired_at') else None,
                                'error_message': txn['error_message']
                            }
                        }), 200
                    
                    # Check if should be expired (> 360 seconds = 6 minutes)
                    if txn['status'] in ('INITIATED', 'PENDING') and seconds_elapsed > 360:
                        print(f"[Checkout Status] ⏰ Marking as expired (>{seconds_elapsed}s): {order_id}")
                        
                        # Mark as expired (but keep original status, don't change to FAILED)
                        cursor.execute("""
                            UPDATE payin_transactions
                            SET checkout_expired_at = NOW(),
                                error_message = 'Checkout link expired - No callback received within 6 minutes',
                                updated_at = NOW()
                            WHERE order_id = %s
                            AND pg_partner = 'MAXPE'
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
                                'created_at': txn['created_at'].isoformat() if txn.get('created_at') else None
                            }
                        }), 200
                    
                    print(f"[Checkout Status] ✅ Found in database: Status={txn['status']}, UTR={txn['bank_ref_no']}")
                    
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
                            'completed_at': txn['completed_at'].isoformat() if txn.get('completed_at') else None,
                            'created_at': txn['created_at'].isoformat() if txn.get('created_at') else None,
                            'seconds_elapsed': seconds_elapsed,
                            'seconds_remaining': max(0, 360 - seconds_elapsed)
                        }
                    }), 200
                else:
                    # Transaction not found in database - return PENDING
                    print(f"[Checkout Status] Transaction not found in database - returning PENDING")
                    return jsonify({
                        'success': True,
                        'transaction': {
                            'order_id': order_id,
                            'status': 'PENDING',
                            'amount': 0
                        }
                    }), 200
                    
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[Checkout Status] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500
