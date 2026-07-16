from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from database_pooled import get_db_connection
import csv
import io
from datetime import datetime
import secrets
from werkzeug.utils import secure_filename
import os

chargeback_bp = Blueprint('chargeback', __name__, url_prefix='/api/chargeback')

ALLOWED_EXTENSIONS = {'csv'}
UPLOAD_FOLDER = 'uploads/chargebacks'

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_date(date_str):
    """Parse date from various formats"""
    try:
        # Try DD-MM-YY format first
        return datetime.strptime(date_str, '%d-%m-%y').date()
    except:
        try:
            # Try DD-MM-YYYY format
            return datetime.strptime(date_str, '%d-%m-%Y').date()
        except:
            try:
                # Try YYYY-MM-DD format
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except:
                return None

# ==================== ADMIN ROUTES ====================

@chargeback_bp.route('/admin/merchants', methods=['GET'])
@jwt_required()
def get_merchants_for_chargeback():
    """Get list of merchants for chargeback upload"""
    try:
        current_admin = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT merchant_id, full_name, email, mobile, merchant_type, is_active
                    FROM merchants
                    WHERE is_active = TRUE
                    ORDER BY full_name
                """)
                merchants = cursor.fetchall()
                
                return jsonify({
                    'success': True,
                    'merchants': merchants
                }), 200
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Get merchants error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@chargeback_bp.route('/admin/upload', methods=['POST'])
@jwt_required()
def upload_chargeback_csv():
    """Upload chargeback CSV file for a merchant"""
    try:
        current_admin = get_jwt_identity()
        
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        file = request.files['file']
        merchant_id = request.form.get('merchant_id')
        
        if not merchant_id:
            return jsonify({'success': False, 'message': 'Merchant ID is required'}), 400
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'message': 'Only CSV files are allowed'}), 400
        
        # Read CSV file
        try:
            # Read file content
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.DictReader(stream)
            
            # Validate CSV headers
            required_headers = ['Transaction ID', 'Order ID', 'Chargeback Amount', 'Status', 
                              'Payment Mode', 'Customer Name', 'Customer Mobile', 'UTR', 'Date']
            
            if not all(header in csv_reader.fieldnames for header in required_headers):
                return jsonify({
                    'success': False, 
                    'message': f'Invalid CSV format. Required headers: {", ".join(required_headers)}'
                }), 400
            
            # Parse CSV data
            chargebacks = []
            for row in csv_reader:
                # Parse date
                chargeback_date = parse_date(row['Date'].strip())
                if not chargeback_date:
                    continue  # Skip invalid dates
                
                # Parse amount
                try:
                    amount = float(row['Chargeback Amount'].strip())
                except:
                    continue  # Skip invalid amounts
                
                chargebacks.append({
                    'transaction_id': row['Transaction ID'].strip(),
                    'order_id': row['Order ID'].strip(),
                    'chargeback_amount': amount,
                    'status': row['Status'].strip(),
                    'payment_mode': row['Payment Mode'].strip(),
                    'customer_name': row['Customer Name'].strip(),
                    'customer_mobile': row['Customer Mobile'].strip(),
                    'utr': row['UTR'].strip(),
                    'chargeback_date': chargeback_date
                })
            
            if not chargebacks:
                return jsonify({'success': False, 'message': 'No valid records found in CSV'}), 400
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error parsing CSV: {str(e)}'}), 400
        
        # Save to database
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Verify merchant exists
                cursor.execute("SELECT merchant_id FROM merchants WHERE merchant_id = %s", (merchant_id,))
                if not cursor.fetchone():
                    return jsonify({'success': False, 'message': 'Merchant not found'}), 404
                
                # Create upload record
                upload_id = f"CBUP_{secrets.token_hex(8).upper()}"
                cursor.execute("""
                    INSERT INTO chargeback_uploads 
                    (upload_id, merchant_id, filename, total_records, uploaded_by, upload_status)
                    VALUES (%s, %s, %s, %s, %s, 'PROCESSING')
                """, (upload_id, merchant_id, secure_filename(file.filename), len(chargebacks), current_admin))
                
                # Insert chargebacks
                successful = 0
                failed = 0
                
                for cb in chargebacks:
                    try:
                        cursor.execute("""
                            INSERT INTO chargebacks 
                            (merchant_id, transaction_id, order_id, chargeback_amount, status, 
                             payment_mode, customer_name, customer_mobile, utr, chargeback_date, uploaded_by)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            merchant_id, cb['transaction_id'], cb['order_id'], cb['chargeback_amount'],
                            cb['status'], cb['payment_mode'], cb['customer_name'], cb['customer_mobile'],
                            cb['utr'], cb['chargeback_date'], current_admin
                        ))
                        successful += 1
                    except Exception as e:
                        print(f"Error inserting chargeback: {e}")
                        failed += 1
                
                # Update upload record
                cursor.execute("""
                    UPDATE chargeback_uploads 
                    SET successful_records = %s, failed_records = %s, upload_status = 'COMPLETED'
                    WHERE upload_id = %s
                """, (successful, failed, upload_id))
                
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': f'Successfully uploaded {successful} chargebacks',
                'upload_id': upload_id,
                'total_records': len(chargebacks),
                'successful_records': successful,
                'failed_records': failed
            }), 200
            
        except Exception as e:
            conn.rollback()
            print(f"Database error: {e}")
            return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Upload chargeback error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@chargeback_bp.route('/admin/uploads', methods=['GET'])
@jwt_required()
def get_chargeback_uploads():
    """Get list of chargeback uploads with filters"""
    try:
        current_admin = get_jwt_identity()
        
        # Get query parameters
        merchant_id = request.args.get('merchant_id', '')
        from_date = request.args.get('from_date', '')
        to_date = request.args.get('to_date', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Build query
                query = """
                    SELECT cu.*, m.full_name as merchant_name
                    FROM chargeback_uploads cu
                    LEFT JOIN merchants m ON cu.merchant_id = m.merchant_id
                    WHERE 1=1
                """
                params = []
                
                if merchant_id:
                    query += " AND cu.merchant_id = %s"
                    params.append(merchant_id)
                
                if from_date:
                    query += " AND DATE(cu.created_at) >= %s"
                    params.append(from_date)
                
                if to_date:
                    query += " AND DATE(cu.created_at) <= %s"
                    params.append(to_date)
                
                # Get total count
                count_query = query.replace("SELECT cu.*, m.full_name as merchant_name", "SELECT COUNT(*) as total")
                cursor.execute(count_query, params)
                total_records = cursor.fetchone()['total']
                
                # Add pagination
                query += " ORDER BY cu.created_at DESC LIMIT %s OFFSET %s"
                params.extend([per_page, (page - 1) * per_page])
                
                cursor.execute(query, params)
                uploads = cursor.fetchall()
                
                # Format dates
                for upload in uploads:
                    if upload.get('created_at'):
                        upload['created_at'] = upload['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                
                total_pages = (total_records + per_page - 1) // per_page
                
                return jsonify({
                    'success': True,
                    'uploads': uploads,
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total_records': total_records,
                        'total_pages': total_pages,
                        'has_next': page < total_pages,
                        'has_prev': page > 1
                    }
                }), 200
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Get uploads error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@chargeback_bp.route('/admin/chargebacks', methods=['GET'])
@jwt_required()
def get_admin_chargebacks():
    """Get chargebacks for admin with filters"""
    try:
        current_admin = get_jwt_identity()
        
        # Get query parameters
        merchant_id = request.args.get('merchant_id', '')
        from_date = request.args.get('from_date', '')
        to_date = request.args.get('to_date', '')
        transaction_id = request.args.get('transaction_id', '')
        acceptance_status = request.args.get('acceptance_status', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Build query with deduction info
                query = """
                    SELECT c.*, m.full_name as merchant_name,
                           cd.deduction_id, cd.deduction_status, cd.deduction_date,
                           cd.previous_unsettled_balance, cd.new_unsettled_balance
                    FROM chargebacks c
                    LEFT JOIN merchants m ON c.merchant_id = m.merchant_id
                    LEFT JOIN chargeback_deductions cd ON c.id = cd.chargeback_id
                    WHERE 1=1
                """
                params = []
                
                if merchant_id:
                    query += " AND c.merchant_id = %s"
                    params.append(merchant_id)
                
                if from_date:
                    query += " AND c.chargeback_date >= %s"
                    params.append(from_date)
                
                if to_date:
                    query += " AND c.chargeback_date <= %s"
                    params.append(to_date)
                
                if transaction_id:
                    query += " AND (c.transaction_id LIKE %s OR c.order_id LIKE %s)"
                    search_param = f"%{transaction_id}%"
                    params.extend([search_param, search_param])
                
                if acceptance_status:
                    query += " AND c.acceptance_status = %s"
                    params.append(acceptance_status)
                
                # Get total count - use a simpler subquery approach
                count_query = f"""
                    SELECT COUNT(*) as total FROM (
                        {query.replace('SELECT c.*, m.full_name as merchant_name, cd.deduction_id, cd.deduction_status, cd.deduction_date, cd.previous_unsettled_balance, cd.new_unsettled_balance', 'SELECT c.id')}
                    ) as count_table
                """
                # Remove ORDER BY and LIMIT from count query
                count_query = count_query.split('ORDER BY')[0]
                cursor.execute(count_query, params)
                total_records = cursor.fetchone()['total']
                
                # Add pagination
                query += " ORDER BY c.chargeback_date DESC, c.created_at DESC LIMIT %s OFFSET %s"
                params.extend([per_page, (page - 1) * per_page])
                
                cursor.execute(query, params)
                chargebacks = cursor.fetchall()
                
                # Format dates and amounts
                for cb in chargebacks:
                    if cb.get('chargeback_date'):
                        cb['chargeback_date'] = cb['chargeback_date'].strftime('%Y-%m-%d')
                    if cb.get('created_at'):
                        cb['created_at'] = cb['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                    if cb.get('accepted_at'):
                        cb['accepted_at'] = cb['accepted_at'].strftime('%Y-%m-%d %H:%M:%S')
                    if cb.get('deduction_date'):
                        cb['deduction_date'] = cb['deduction_date'].strftime('%Y-%m-%d %H:%M:%S')
                    if cb.get('chargeback_amount'):
                        cb['chargeback_amount'] = float(cb['chargeback_amount'])
                    if cb.get('previous_unsettled_balance'):
                        cb['previous_unsettled_balance'] = float(cb['previous_unsettled_balance'])
                    if cb.get('new_unsettled_balance'):
                        cb['new_unsettled_balance'] = float(cb['new_unsettled_balance'])
                
                total_pages = (total_records + per_page - 1) // per_page
                
                return jsonify({
                    'success': True,
                    'chargebacks': chargebacks,
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total_records': total_records,
                        'total_pages': total_pages,
                        'has_next': page < total_pages,
                        'has_prev': page > 1
                    }
                }), 200
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Get chargebacks error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@chargeback_bp.route('/admin/deductions', methods=['GET'])
@jwt_required()
def get_admin_deductions():
    """Get all chargeback deductions for admin"""
    try:
        current_admin = get_jwt_identity()
        
        # Get query parameters
        merchant_id = request.args.get('merchant_id', '')
        from_date = request.args.get('from_date', '')
        to_date = request.args.get('to_date', '')
        transaction_id = request.args.get('transaction_id', '')
        status = request.args.get('status', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Build query
                query = """
                    SELECT cd.*, c.customer_name, c.customer_mobile, c.payment_mode, 
                           c.utr, c.chargeback_date, m.full_name as merchant_name
                    FROM chargeback_deductions cd
                    LEFT JOIN chargebacks c ON cd.chargeback_id = c.id
                    LEFT JOIN merchants m ON cd.merchant_id = m.merchant_id
                    WHERE 1=1
                """
                params = []
                
                if merchant_id:
                    query += " AND cd.merchant_id = %s"
                    params.append(merchant_id)
                
                if from_date:
                    query += " AND DATE(cd.deduction_date) >= %s"
                    params.append(from_date)
                
                if to_date:
                    query += " AND DATE(cd.deduction_date) <= %s"
                    params.append(to_date)
                
                if transaction_id:
                    query += " AND (cd.transaction_id LIKE %s OR cd.order_id LIKE %s)"
                    search_param = f"%{transaction_id}%"
                    params.extend([search_param, search_param])
                
                if status:
                    query += " AND cd.deduction_status = %s"
                    params.append(status)
                
                # Get total count
                count_query = query.replace(
                    "SELECT cd.*, c.customer_name, c.customer_mobile, c.payment_mode, c.utr, c.chargeback_date, m.full_name as merchant_name", 
                    "SELECT COUNT(*) as total"
                )
                cursor.execute(count_query, params)
                total_records = cursor.fetchone()['total']
                
                # Add pagination
                query += " ORDER BY cd.deduction_date DESC LIMIT %s OFFSET %s"
                params.extend([per_page, (page - 1) * per_page])
                
                cursor.execute(query, params)
                deductions = cursor.fetchall()
                
                # Format dates and amounts
                for ded in deductions:
                    if ded.get('deduction_date'):
                        ded['deduction_date'] = ded['deduction_date'].strftime('%Y-%m-%d %H:%M:%S')
                    if ded.get('chargeback_date'):
                        ded['chargeback_date'] = ded['chargeback_date'].strftime('%Y-%m-%d')
                    if ded.get('created_at'):
                        ded['created_at'] = ded['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                    if ded.get('deduction_amount'):
                        ded['deduction_amount'] = float(ded['deduction_amount'])
                    if ded.get('previous_unsettled_balance'):
                        ded['previous_unsettled_balance'] = float(ded['previous_unsettled_balance'])
                    if ded.get('new_unsettled_balance'):
                        ded['new_unsettled_balance'] = float(ded['new_unsettled_balance'])
                
                total_pages = (total_records + per_page - 1) // per_page
                
                # Get summary stats
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_deductions,
                        SUM(CASE WHEN deduction_status = 'SUCCESS' THEN deduction_amount ELSE 0 END) as total_deducted
                    FROM chargeback_deductions
                """)
                summary = cursor.fetchone()
                
                return jsonify({
                    'success': True,
                    'deductions': deductions,
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total_records': total_records,
                        'total_pages': total_pages,
                        'has_next': page < total_pages,
                        'has_prev': page > 1
                    },
                    'summary': {
                        'total_deductions': summary['total_deductions'] or 0,
                        'total_deducted': float(summary['total_deducted'] or 0)
                    }
                }), 200
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Get admin deductions error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@chargeback_bp.route('/admin/merchant-holds/<merchant_id>', methods=['GET'])
@jwt_required()
def get_merchant_holds(merchant_id):
    """Get manual hold amounts for a merchant"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(cyber_hold_amount, 0.00) as cyber_hold_amount, 
                       COALESCE(total_hold_amount, 0.00) as total_hold_amount 
                FROM merchant_wallet 
                WHERE merchant_id = %s
            """, (merchant_id,))
            wallet = cursor.fetchone()
            
            if not wallet:
                return jsonify({'success': True, 'cyber_hold_amount': 0.00, 'total_hold_amount': 0.00}), 200
                
            return jsonify({
                'success': True,
                'cyber_hold_amount': float(wallet['cyber_hold_amount']),
                'total_hold_amount': float(wallet['total_hold_amount'])
            }), 200
    except Exception as e:
        print(f"Get merchant holds error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@chargeback_bp.route('/admin/merchant-holds', methods=['POST'])
@jwt_required()
def update_merchant_holds():
    """Update manual hold amounts for a merchant"""
    try:
        data = request.json
        merchant_id = data.get('merchant_id')
        cyber_hold_amount = data.get('cyber_hold_amount', 0)
        total_hold_amount = data.get('total_hold_amount', 0)
        
        if not merchant_id:
            return jsonify({'success': False, 'message': 'Merchant ID is required'}), 400
            
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
            
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM merchant_wallet WHERE merchant_id = %s", (merchant_id,))
            if cursor.fetchone():
                cursor.execute("""
                    UPDATE merchant_wallet 
                    SET cyber_hold_amount = %s, total_hold_amount = %s, last_updated = NOW()
                    WHERE merchant_id = %s
                """, (cyber_hold_amount, total_hold_amount, merchant_id))
            else:
                cursor.execute("""
                    INSERT INTO merchant_wallet (merchant_id, balance, cyber_hold_amount, total_hold_amount)
                    VALUES (%s, 0.00, %s, %s)
                """, (merchant_id, cyber_hold_amount, total_hold_amount))
            conn.commit()
            
        return jsonify({
            'success': True,
            'message': 'Hold amounts updated successfully'
        }), 200
    except Exception as e:
        print(f"Update merchant holds error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@chargeback_bp.route('/admin/stats', methods=['GET'])
@jwt_required()
def get_admin_chargeback_stats():
    """Get chargeback statistics for admin"""
    try:
        current_admin = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Get overall stats
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_chargebacks,
                        SUM(chargeback_amount) as total_amount,
                        COUNT(CASE WHEN acceptance_status = 'PENDING' THEN 1 END) as pending_count,
                        SUM(CASE WHEN acceptance_status = 'PENDING' THEN chargeback_amount ELSE 0 END) as pending_amount,
                        COUNT(CASE WHEN acceptance_status = 'ACCEPTED' THEN 1 END) as accepted_count,
                        SUM(CASE WHEN acceptance_status = 'ACCEPTED' THEN chargeback_amount ELSE 0 END) as accepted_amount
                    FROM chargebacks
                """)
                stats = cursor.fetchone()
                
                # Get deduction stats
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_deductions,
                        SUM(CASE WHEN deduction_status = 'SUCCESS' THEN deduction_amount ELSE 0 END) as total_deducted
                    FROM chargeback_deductions
                """)
                deduction_stats = cursor.fetchone()
                
                return jsonify({
                    'success': True,
                    'stats': {
                        'total_chargebacks': stats['total_chargebacks'] or 0,
                        'total_amount': float(stats['total_amount'] or 0),
                        'pending_count': stats['pending_count'] or 0,
                        'pending_amount': float(stats['pending_amount'] or 0),
                        'accepted_count': stats['accepted_count'] or 0,
                        'accepted_amount': float(stats['accepted_amount'] or 0),
                        'total_deductions': deduction_stats['total_deductions'] or 0,
                        'total_deducted': float(deduction_stats['total_deducted'] or 0)
                    }
                }), 200
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Get admin stats error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@chargeback_bp.route('/admin/template', methods=['GET'])
def download_template():
    """Download CSV template for chargeback upload"""
    try:
        # Create CSV template
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Transaction ID', 'Order ID', 'Chargeback Amount', 'Status', 
            'Payment Mode', 'Customer Name', 'Customer Mobile', 'UTR', 'Date'
        ])
        
        # Write sample data
        writer.writerow([
            'MAXPE_8967274930_a1411463175500480512_20260503235844',
            'a1411463175500480512',
            '1000',
            'SUCCESS',
            'UPI',
            'Amit Verma',
            '8884223387',
            '205000000000',
            '03-05-26'
        ])
        
        # Prepare response
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'chargeback_template_{datetime.now().strftime("%Y%m%d")}.csv'
        )
        
    except Exception as e:
        print(f"Download template error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ==================== MERCHANT ROUTES ====================

@chargeback_bp.route('/merchant/chargebacks', methods=['GET'])
@jwt_required()
def get_merchant_chargebacks():
    """Get chargebacks for logged-in merchant"""
    try:
        current_merchant = get_jwt_identity()
        
        # Get query parameters
        from_date = request.args.get('from_date', '')
        to_date = request.args.get('to_date', '')
        transaction_id = request.args.get('transaction_id', '')
        status = request.args.get('status', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Build query
                query = """
                    SELECT *
                    FROM chargebacks
                    WHERE merchant_id = %s
                """
                params = [current_merchant]
                
                if from_date:
                    query += " AND chargeback_date >= %s"
                    params.append(from_date)
                
                if to_date:
                    query += " AND chargeback_date <= %s"
                    params.append(to_date)
                
                if transaction_id:
                    query += " AND (transaction_id LIKE %s OR order_id LIKE %s)"
                    search_param = f"%{transaction_id}%"
                    params.extend([search_param, search_param])
                
                if status:
                    query += " AND status = %s"
                    params.append(status)
                
                # Get total count
                count_query = query.replace("SELECT *", "SELECT COUNT(*) as total")
                cursor.execute(count_query, params)
                total_records = cursor.fetchone()['total']
                
                # Add pagination
                query += " ORDER BY chargeback_date DESC, created_at DESC LIMIT %s OFFSET %s"
                params.extend([per_page, (page - 1) * per_page])
                
                cursor.execute(query, params)
                chargebacks = cursor.fetchall()
                
                # Format dates and amounts
                for cb in chargebacks:
                    if cb.get('chargeback_date'):
                        cb['chargeback_date'] = cb['chargeback_date'].strftime('%Y-%m-%d')
                    if cb.get('created_at'):
                        cb['created_at'] = cb['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                    if cb.get('chargeback_amount'):
                        cb['chargeback_amount'] = float(cb['chargeback_amount'])
                
                total_pages = (total_records + per_page - 1) // per_page
                
                return jsonify({
                    'success': True,
                    'chargebacks': chargebacks,
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total_records': total_records,
                        'total_pages': total_pages,
                        'has_next': page < total_pages,
                        'has_prev': page > 1
                    }
                }), 200
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Get merchant chargebacks error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@chargeback_bp.route('/merchant/download', methods=['GET'])
@jwt_required()
def download_merchant_chargebacks():
    """Download chargeback report for merchant"""
    try:
        current_merchant = get_jwt_identity()
        
        # Get query parameters
        from_date = request.args.get('from_date', '')
        to_date = request.args.get('to_date', '')
        transaction_id = request.args.get('transaction_id', '')
        status = request.args.get('status', '')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Build query
                query = """
                    SELECT transaction_id, order_id, chargeback_amount, status, 
                           payment_mode, customer_name, customer_mobile, utr, chargeback_date
                    FROM chargebacks
                    WHERE merchant_id = %s
                """
                params = [current_merchant]
                
                if from_date:
                    query += " AND chargeback_date >= %s"
                    params.append(from_date)
                
                if to_date:
                    query += " AND chargeback_date <= %s"
                    params.append(to_date)
                
                if transaction_id:
                    query += " AND (transaction_id LIKE %s OR order_id LIKE %s)"
                    search_param = f"%{transaction_id}%"
                    params.extend([search_param, search_param])
                
                if status:
                    query += " AND status = %s"
                    params.append(status)
                
                query += " ORDER BY chargeback_date DESC"
                
                cursor.execute(query, params)
                chargebacks = cursor.fetchall()
                
                # Create CSV
                output = io.StringIO()
                writer = csv.writer(output)
                
                # Write header
                writer.writerow([
                    'Transaction ID', 'Order ID', 'Chargeback Amount', 'Status', 
                    'Payment Mode', 'Customer Name', 'Customer Mobile', 'UTR', 'Date'
                ])
                
                # Write data
                for cb in chargebacks:
                    writer.writerow([
                        cb.get('transaction_id', ''),
                        cb.get('order_id', ''),
                        cb.get('chargeback_amount', ''),
                        cb.get('status', ''),
                        cb.get('payment_mode', ''),
                        cb.get('customer_name', ''),
                        cb.get('customer_mobile', ''),
                        cb.get('utr', ''),
                        cb.get('chargeback_date', '').strftime('%d-%m-%Y') if cb.get('chargeback_date') else ''
                    ])
                
                # Prepare response
                output.seek(0)
                return send_file(
                    io.BytesIO(output.getvalue().encode('utf-8')),
                    mimetype='text/csv',
                    as_attachment=True,
                    download_name=f'chargebacks_{current_merchant}_{datetime.now().strftime("%Y%m%d")}.csv'
                )
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Download chargebacks error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@chargeback_bp.route('/merchant/stats', methods=['GET'])
@jwt_required()
def get_merchant_chargeback_stats():
    """Get chargeback statistics for merchant"""
    try:
        current_merchant = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Get total chargebacks
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_count,
                        SUM(chargeback_amount) as total_amount
                    FROM chargebacks
                    WHERE merchant_id = %s
                """, (current_merchant,))
                total_stats = cursor.fetchone()
                
                # Get this month's chargebacks
                cursor.execute("""
                    SELECT 
                        COUNT(*) as month_count,
                        SUM(chargeback_amount) as month_amount
                    FROM chargebacks
                    WHERE merchant_id = %s
                    AND MONTH(chargeback_date) = MONTH(CURRENT_DATE())
                    AND YEAR(chargeback_date) = YEAR(CURRENT_DATE())
                """, (current_merchant,))
                month_stats = cursor.fetchone()
                
                # Get pending chargebacks
                cursor.execute("""
                    SELECT 
                        COUNT(*) as pending_count,
                        SUM(chargeback_amount) as pending_amount
                    FROM chargebacks
                    WHERE merchant_id = %s
                    AND acceptance_status = 'PENDING'
                """, (current_merchant,))
                pending_stats = cursor.fetchone()
                
                # Get accepted chargebacks
                cursor.execute("""
                    SELECT 
                        COUNT(*) as accepted_count,
                        SUM(chargeback_amount) as accepted_amount
                    FROM chargebacks
                    WHERE merchant_id = %s
                    AND acceptance_status = 'ACCEPTED'
                """, (current_merchant,))
                accepted_stats = cursor.fetchone()
                
                return jsonify({
                    'success': True,
                    'stats': {
                        'total_count': total_stats['total_count'] or 0,
                        'total_amount': float(total_stats['total_amount'] or 0),
                        'month_count': month_stats['month_count'] or 0,
                        'month_amount': float(month_stats['month_amount'] or 0),
                        'pending_count': pending_stats['pending_count'] or 0,
                        'pending_amount': float(pending_stats['pending_amount'] or 0),
                        'accepted_count': accepted_stats['accepted_count'] or 0,
                        'accepted_amount': float(accepted_stats['accepted_amount'] or 0)
                    }
                }), 200
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Get stats error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@chargeback_bp.route('/merchant/accept/<int:chargeback_id>', methods=['POST'])
@jwt_required()
def accept_chargeback(chargeback_id):
    """Accept a chargeback and deduct from unsettled balance"""
    try:
        current_merchant = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Get chargeback details
                cursor.execute("""
                    SELECT * FROM chargebacks 
                    WHERE id = %s AND merchant_id = %s
                """, (chargeback_id, current_merchant))
                chargeback = cursor.fetchone()
                
                if not chargeback:
                    return jsonify({'success': False, 'message': 'Chargeback not found'}), 404
                
                if chargeback['acceptance_status'] == 'ACCEPTED':
                    return jsonify({'success': False, 'message': 'Chargeback already accepted'}), 400
                
                # Get current wallet balance
                cursor.execute("""
                    SELECT unsettled_balance FROM merchant_wallet 
                    WHERE merchant_id = %s
                """, (current_merchant,))
                wallet = cursor.fetchone()
                
                if not wallet:
                    return jsonify({'success': False, 'message': 'Wallet not found'}), 404
                
                previous_balance = float(wallet['unsettled_balance'])
                deduction_amount = float(chargeback['chargeback_amount'])
                
                # Check if sufficient balance
                if previous_balance < deduction_amount:
                    # Create failed deduction record
                    deduction_id = f"CBDED_{secrets.token_hex(8).upper()}"
                    cursor.execute("""
                        INSERT INTO chargeback_deductions 
                        (deduction_id, chargeback_id, merchant_id, transaction_id, order_id, 
                         deduction_amount, previous_unsettled_balance, new_unsettled_balance, 
                         deduction_status, remarks)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'INSUFFICIENT_BALANCE', %s)
                    """, (
                        deduction_id, chargeback_id, current_merchant, 
                        chargeback['transaction_id'], chargeback['order_id'],
                        deduction_amount, previous_balance, previous_balance,
                        f'Insufficient balance. Required: {deduction_amount}, Available: {previous_balance}'
                    ))
                    
                    conn.commit()
                    return jsonify({
                        'success': False, 
                        'message': f'Insufficient unsettled balance. Required: ₹{deduction_amount:.2f}, Available: ₹{previous_balance:.2f}'
                    }), 400
                
                # Deduct from unsettled balance
                new_balance = previous_balance - deduction_amount
                
                cursor.execute("""
                    UPDATE merchant_wallet 
                    SET unsettled_balance = %s,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE merchant_id = %s
                """, (new_balance, current_merchant))
                
                # Update chargeback status
                cursor.execute("""
                    UPDATE chargebacks 
                    SET acceptance_status = 'ACCEPTED',
                        accepted_at = CURRENT_TIMESTAMP,
                        accepted_by = %s
                    WHERE id = %s
                """, (current_merchant, chargeback_id))
                
                # Create deduction record
                deduction_id = f"CBDED_{secrets.token_hex(8).upper()}"
                cursor.execute("""
                    INSERT INTO chargeback_deductions 
                    (deduction_id, chargeback_id, merchant_id, transaction_id, order_id, 
                     deduction_amount, previous_unsettled_balance, new_unsettled_balance, 
                     deduction_status, remarks)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'SUCCESS', %s)
                """, (
                    deduction_id, chargeback_id, current_merchant, 
                    chargeback['transaction_id'], chargeback['order_id'],
                    deduction_amount, previous_balance, new_balance,
                    f'Chargeback accepted and deducted from unsettled balance'
                ))
                
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Chargeback accepted successfully',
                'deduction_id': deduction_id,
                'deduction_amount': deduction_amount,
                'previous_balance': previous_balance,
                'new_balance': new_balance
            }), 200
            
        except Exception as e:
            conn.rollback()
            print(f"Accept chargeback error: {e}")
            return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Accept chargeback error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@chargeback_bp.route('/merchant/deductions', methods=['GET'])
@jwt_required()
def get_chargeback_deductions():
    """Get chargeback deduction history for merchant"""
    try:
        current_merchant = get_jwt_identity()
        
        # Get query parameters
        from_date = request.args.get('from_date', '')
        to_date = request.args.get('to_date', '')
        transaction_id = request.args.get('transaction_id', '')
        status = request.args.get('status', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Build query
                query = """
                    SELECT cd.*, c.customer_name, c.customer_mobile, c.payment_mode, c.utr, c.chargeback_date
                    FROM chargeback_deductions cd
                    LEFT JOIN chargebacks c ON cd.chargeback_id = c.id
                    WHERE cd.merchant_id = %s
                """
                params = [current_merchant]
                
                if from_date:
                    query += " AND DATE(cd.deduction_date) >= %s"
                    params.append(from_date)
                
                if to_date:
                    query += " AND DATE(cd.deduction_date) <= %s"
                    params.append(to_date)
                
                if transaction_id:
                    query += " AND (cd.transaction_id LIKE %s OR cd.order_id LIKE %s)"
                    search_param = f"%{transaction_id}%"
                    params.extend([search_param, search_param])
                
                if status:
                    query += " AND cd.deduction_status = %s"
                    params.append(status)
                
                # Get total count
                count_query = query.replace(
                    "SELECT cd.*, c.customer_name, c.customer_mobile, c.payment_mode, c.utr, c.chargeback_date", 
                    "SELECT COUNT(*) as total"
                )
                cursor.execute(count_query, params)
                total_records = cursor.fetchone()['total']
                
                # Add pagination
                query += " ORDER BY cd.deduction_date DESC LIMIT %s OFFSET %s"
                params.extend([per_page, (page - 1) * per_page])
                
                cursor.execute(query, params)
                deductions = cursor.fetchall()
                
                # Format dates and amounts
                for ded in deductions:
                    if ded.get('deduction_date'):
                        ded['deduction_date'] = ded['deduction_date'].strftime('%Y-%m-%d %H:%M:%S')
                    if ded.get('chargeback_date'):
                        ded['chargeback_date'] = ded['chargeback_date'].strftime('%Y-%m-%d')
                    if ded.get('created_at'):
                        ded['created_at'] = ded['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                    if ded.get('deduction_amount'):
                        ded['deduction_amount'] = float(ded['deduction_amount'])
                    if ded.get('previous_unsettled_balance'):
                        ded['previous_unsettled_balance'] = float(ded['previous_unsettled_balance'])
                    if ded.get('new_unsettled_balance'):
                        ded['new_unsettled_balance'] = float(ded['new_unsettled_balance'])
                
                total_pages = (total_records + per_page - 1) // per_page
                
                # Get summary stats
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_deductions,
                        SUM(CASE WHEN deduction_status = 'SUCCESS' THEN deduction_amount ELSE 0 END) as total_deducted
                    FROM chargeback_deductions
                    WHERE merchant_id = %s
                """, (current_merchant,))
                summary = cursor.fetchone()
                
                return jsonify({
                    'success': True,
                    'deductions': deductions,
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total_records': total_records,
                        'total_pages': total_pages,
                        'has_next': page < total_pages,
                        'has_prev': page > 1
                    },
                    'summary': {
                        'total_deductions': summary['total_deductions'] or 0,
                        'total_deducted': float(summary['total_deducted'] or 0)
                    }
                }), 200
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Get deductions error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@chargeback_bp.route('/merchant/deductions/download', methods=['GET'])
@jwt_required()
def download_deduction_report():
    """Download chargeback deduction report for merchant"""
    try:
        current_merchant = get_jwt_identity()
        
        # Get query parameters
        from_date = request.args.get('from_date', '')
        to_date = request.args.get('to_date', '')
        transaction_id = request.args.get('transaction_id', '')
        status = request.args.get('status', '')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        try:
            with conn.cursor() as cursor:
                # Build query
                query = """
                    SELECT 
                        cd.deduction_id,
                        cd.transaction_id,
                        cd.order_id,
                        cd.deduction_amount,
                        cd.previous_unsettled_balance,
                        cd.new_unsettled_balance,
                        cd.deduction_status,
                        cd.deduction_date,
                        cd.remarks,
                        c.customer_name,
                        c.customer_mobile,
                        c.payment_mode,
                        c.utr,
                        c.chargeback_date
                    FROM chargeback_deductions cd
                    LEFT JOIN chargebacks c ON cd.chargeback_id = c.id
                    WHERE cd.merchant_id = %s
                """
                params = [current_merchant]
                
                if from_date:
                    query += " AND DATE(cd.deduction_date) >= %s"
                    params.append(from_date)
                
                if to_date:
                    query += " AND DATE(cd.deduction_date) <= %s"
                    params.append(to_date)
                
                if transaction_id:
                    query += " AND (cd.transaction_id LIKE %s OR cd.order_id LIKE %s)"
                    search_param = f"%{transaction_id}%"
                    params.extend([search_param, search_param])
                
                if status:
                    query += " AND cd.deduction_status = %s"
                    params.append(status)
                
                query += " ORDER BY cd.deduction_date DESC"
                
                cursor.execute(query, params)
                deductions = cursor.fetchall()
                
                # Create CSV
                output = io.StringIO()
                writer = csv.writer(output)
                
                # Write header
                writer.writerow([
                    'Deduction ID', 'Transaction ID', 'Order ID', 'Deduction Amount',
                    'Previous Balance', 'New Balance', 'Status', 'Deduction Date',
                    'Customer Name', 'Customer Mobile', 'Payment Mode', 'UTR',
                    'Chargeback Date', 'Remarks'
                ])
                
                # Write data
                for ded in deductions:
                    writer.writerow([
                        ded.get('deduction_id', ''),
                        ded.get('transaction_id', ''),
                        ded.get('order_id', ''),
                        ded.get('deduction_amount', ''),
                        ded.get('previous_unsettled_balance', ''),
                        ded.get('new_unsettled_balance', ''),
                        ded.get('deduction_status', ''),
                        ded.get('deduction_date', '').strftime('%Y-%m-%d %H:%M:%S') if ded.get('deduction_date') else '',
                        ded.get('customer_name', ''),
                        ded.get('customer_mobile', ''),
                        ded.get('payment_mode', ''),
                        ded.get('utr', ''),
                        ded.get('chargeback_date', '').strftime('%Y-%m-%d') if ded.get('chargeback_date') else '',
                        ded.get('remarks', '')
                    ])
                
                # Prepare response
                output.seek(0)
                return send_file(
                    io.BytesIO(output.getvalue().encode('utf-8')),
                    mimetype='text/csv',
                    as_attachment=True,
                    download_name=f'chargeback_deductions_{current_merchant}_{datetime.now().strftime("%Y%m%d")}.csv'
                )
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Download deductions error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
