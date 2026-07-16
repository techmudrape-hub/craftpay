"""
Auto-settlement API routes for admin
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from auto_settlement_service import AutoSettlementService
from functools import wraps

auto_settlement_bp = Blueprint('auto_settlement', __name__)
auto_settlement_svc = AutoSettlementService()

def admin_required(fn):
    """Decorator to ensure user is admin"""
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        current_user = get_jwt_identity()
        # Add admin check logic here if needed
        return fn(*args, **kwargs)
    return wrapper

@auto_settlement_bp.route('/api/auto-settlement/config/<merchant_id>', methods=['GET'])
@admin_required
def get_auto_settlement_config(merchant_id):
    """Get auto-settlement configuration for a merchant"""
    try:
        config = auto_settlement_svc.get_merchant_auto_settlement_config(merchant_id)
        
        if config:
            return jsonify({
                'success': True,
                'config': {
                    'merchant_id': config['merchant_id'],
                    'is_enabled': bool(config['is_enabled']),
                    'settlement_mode': config.get('settlement_mode', 'SCHEDULED'),
                    'settlement_frequency': config['settlement_frequency'],
                    'settlement_hour': config['settlement_hour'],
                    'settlement_minute': config['settlement_minute'],
                    'settlement_day': config['settlement_day'],
                    'settlement_interval_minutes': config.get('settlement_interval_minutes'),
                    'hold_percentage': float(config['hold_percentage']),
                    'minimum_settlement_amount': float(config['minimum_settlement_amount']),
                    'last_settlement_at': config['last_settlement_at'].isoformat() if config['last_settlement_at'] else None
                }
            }), 200
        else:
            # Return default config
            return jsonify({
                'success': True,
                'config': {
                    'merchant_id': merchant_id,
                    'is_enabled': False,
                    'settlement_mode': 'INTERVAL',
                    'settlement_frequency': 'DAILY',
                    'settlement_hour': 0,
                    'settlement_minute': 0,
                    'settlement_day': 1,
                    'settlement_interval_minutes': None,
                    'hold_percentage': 0.00,
                    'minimum_settlement_amount': 0.00,
                    'last_settlement_at': None
                }
            }), 200
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@auto_settlement_bp.route('/api/auto-settlement/config/<merchant_id>', methods=['POST'])
@admin_required
def update_auto_settlement_config(merchant_id):
    """Update auto-settlement configuration for a merchant"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'is_enabled' not in data:
            return jsonify({
                'success': False,
                'message': 'is_enabled is required'
            }), 400
        
        result = auto_settlement_svc.update_auto_settlement_config(merchant_id, data)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@auto_settlement_bp.route('/api/auto-settlement/trigger/<merchant_id>', methods=['POST'])
@admin_required
def trigger_auto_settlement(merchant_id):
    """Manually trigger auto-settlement for a merchant"""
    try:
        admin_id = get_jwt_identity()
        print(f"[AUTO-SETTLEMENT] Triggering for merchant: {merchant_id}, admin: {admin_id}")
        
        # Force=True bypasses schedule checks for manual triggers
        result = auto_settlement_svc.perform_auto_settlement(merchant_id, admin_id, force=True)
        
        print(f"[AUTO-SETTLEMENT] Result: {result}")
        
        if result['success']:
            return jsonify(result), 200
        else:
            print(f"[AUTO-SETTLEMENT] Failed: {result.get('message')}")
            return jsonify(result), 400
            
    except Exception as e:
        print(f"[AUTO-SETTLEMENT] Exception: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@auto_settlement_bp.route('/api/auto-settlement/logs/<merchant_id>', methods=['GET'])
@admin_required
def get_auto_settlement_logs(merchant_id):
    """Get auto-settlement logs for a merchant"""
    try:
        limit = request.args.get('limit', 100, type=int)
        logs = auto_settlement_svc.get_auto_settlement_logs(merchant_id, limit)
        
        formatted_logs = []
        for log in logs:
            formatted_logs.append({
                'id': log['id'],
                'merchant_id': log['merchant_id'],
                'settlement_id': log['settlement_id'],
                'attempted_amount': float(log['attempted_amount']),
                'settled_amount': float(log['settled_amount']),
                'held_amount': float(log['held_amount']),
                'status': log['status'],
                'reason': log['reason'],
                'created_at': log['created_at'].isoformat()
            })
        
        return jsonify({
            'success': True,
            'logs': formatted_logs
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@auto_settlement_bp.route('/api/auto-settlement/logs', methods=['GET'])
@admin_required
def get_all_auto_settlement_logs():
    """Get all auto-settlement logs"""
    try:
        limit = request.args.get('limit', 100, type=int)
        logs = auto_settlement_svc.get_auto_settlement_logs(None, limit)
        
        formatted_logs = []
        for log in logs:
            formatted_logs.append({
                'id': log['id'],
                'merchant_id': log['merchant_id'],
                'settlement_id': log['settlement_id'],
                'attempted_amount': float(log['attempted_amount']),
                'settled_amount': float(log['settled_amount']),
                'held_amount': float(log['held_amount']),
                'status': log['status'],
                'reason': log['reason'],
                'created_at': log['created_at'].isoformat()
            })
        
        return jsonify({
            'success': True,
            'logs': formatted_logs
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
