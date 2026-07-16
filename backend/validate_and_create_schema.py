#!/usr/bin/env python3
"""
Complete Database Schema Validator and Creator
Checks all tables and columns against expected schema and creates missing ones
"""

from config import Config
import pymysql

print("=" * 80)
print("DATABASE SCHEMA VALIDATOR AND CREATOR")
print("=" * 80)

# Define the complete expected schema based on your database
EXPECTED_SCHEMA = {
    'admin_activity_logs': {
        'columns': [
            ('id', 'INT NOT NULL AUTO_INCREMENT PRIMARY KEY'),
            ('admin_id', 'VARCHAR(50) NOT NULL'),
            ('action', 'VARCHAR(100) NOT NULL'),
            ('ip_address', 'VARCHAR(45)'),
            ('user_agent', 'TEXT'),
            ('status', 'VARCHAR(20)'),
            ('created_at', 'TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP'),
        ],
        'indexes': [
            ('idx_admin_id', 'admin_id'),
        ]
    },
    
    'admin_banks': {
        'columns': [
            ('id', 'INT NOT NULL AUTO_INCREMENT PRIMARY KEY'),
            ('admin_id', 'VARCHAR(50) NOT NULL'),
            ('bank_name', 'VARCHAR(255) NOT NULL'),
            ('account_number', 'VARCHAR(50) NOT NULL'),
            ('ifsc_code', 'VARCHAR(20) NOT NULL'),
            ('branch_name', 'VARCHAR(255)'),
            ('account_holder_name', 'VARCHAR(255) NOT NULL'),
            ('tpin_hash', 'VARCHAR(255) NOT NULL'),
            ('is_active', 'TINYINT(1) DEFAULT 1'),
            ('created_at', 'TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP'),
            ('updated_at', 'TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
        ],
        'indexes': [
            ('idx_admin_id', 'admin_id'),
        ]
    },
    
    'admin_users': {
        'columns': [
            ('id', 'INT NOT NULL AUTO_INCREMENT PRIMARY KEY'),
            ('admin_id', 'VARCHAR(50) NOT NULL UNIQUE'),
            ('password_hash', 'VARCHAR(255) NOT NULL'),
            ('is_active', 'TINYINT(1) DEFAULT 1'),
            ('created_at', 'TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP'),
            ('last_login', 'TIMESTAMP NULL'),
            ('login_attempts', 'INT DEFAULT 0'),
            ('locked_until', 'TIMESTAMP NULL'),
            ('password_changed_at', 'TIMESTAMP NULL'),
            ('must_change_password', 'TINYINT(1) DEFAULT 0'),
            ('pin_hash', 'VARCHAR(255)'),
            ('pin_changed_at', 'TIMESTAMP NULL'),
        ],
        'indexes': []
    },
    
    'admin_wallet': {
        'columns': [
            ('id', 'INT NOT NULL AUTO_INCREMENT PRIMARY KEY'),
            ('admin_id', 'VARCHAR(50) NOT NULL UNIQUE'),
            ('main_balance', 'DECIMAL(15,2) NOT NULL DEFAULT 0.00'),
            ('unsettled_balance', 'DECIMAL(15,2) NOT NULL DEFAULT 0.00'),
            ('settled_balance', 'DECIMAL(15,2) DEFAULT 0.00'),
            ('last_updated', 'TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
        ],
        'indexes': []
    },
    
    'admin_wallet_transactions': {
        'columns': [
            ('id', 'INT NOT NULL AUTO_INCREMENT PRIMARY KEY'),
            ('admin_id', 'VARCHAR(50) NOT NULL'),
            ('txn_id', 'VARCHAR(100) NOT NULL'),
            ('wallet_type', "ENUM('MAIN','UNSETTLED') NOT NULL"),
            ('txn_type', "ENUM('CREDIT','DEBIT','UNSETTLED_CREDIT','SETTLEMENT','UNSETTLED_DEBIT') NOT NULL"),
            ('amount', 'DECIMAL(15,2) NOT NULL'),
            ('balance_before', 'DECIMAL(15,2) NOT NULL'),
            ('balance_after', 'DECIMAL(15,2) NOT NULL'),
            ('description', 'VARCHAR(500)'),
            ('reference_id', 'VARCHAR(100)'),
            ('created_at', 'TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP'),
        ],
        'indexes': [
            ('idx_admin_id', 'admin_id'),
            ('idx_wallet_type', 'wallet_type'),
            ('idx_created_at', 'created_at'),
        ]
    },
    
    'merchant_wallet': {
        'columns': [
            ('id', 'INT NOT NULL AUTO_INCREMENT PRIMARY KEY'),
            ('merchant_id', 'VARCHAR(50) NOT NULL UNIQUE'),
            ('balance', 'DECIMAL(15,2) DEFAULT 0.00'),
            ('main_balance', 'DECIMAL(15,2) DEFAULT 0.00'),
            ('settled_balance', 'DECIMAL(15,2) DEFAULT 0.00'),
            ('unsettled_balance', 'DECIMAL(15,2) DEFAULT 0.00'),
            ('last_updated', 'TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
        ],
        'indexes': []
    },
    
    'merchant_wallet_transactions': {
        'columns': [
            ('id', 'INT NOT NULL AUTO_INCREMENT PRIMARY KEY'),
            ('merchant_id', 'VARCHAR(50) NOT NULL'),
            ('txn_id', 'VARCHAR(100) NOT NULL UNIQUE'),
            ('txn_type', "ENUM('CREDIT','DEBIT','HOLD','RELEASE','UNSETTLED_CREDIT','SETTLEMENT') NOT NULL"),
            ('amount', 'DECIMAL(15,2) NOT NULL'),
            ('balance_before', 'DECIMAL(15,2) NOT NULL'),
            ('balance_after', 'DECIMAL(15,2) NOT NULL'),
            ('on_hold_before', 'DECIMAL(15,2) DEFAULT 0.00'),
            ('on_hold_after', 'DECIMAL(15,2) DEFAULT 0.00'),
            ('description', 'TEXT'),
            ('reference_id', 'VARCHAR(100)'),
            ('created_at', 'TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP'),
        ],
        'indexes': [
            ('idx_merchant_id', 'merchant_id'),
            ('idx_txn_type', 'txn_type'),
            ('idx_created_at', 'created_at'),
            ('idx_reference', 'reference_id'),
        ]
    },
    
    'merchant_unsettled_wallet': {
        'columns': [
            ('id', 'INT NOT NULL AUTO_INCREMENT PRIMARY KEY'),
            ('merchant_id', 'VARCHAR(50) NOT NULL UNIQUE'),
            ('balance', 'DECIMAL(15,2) DEFAULT 0.00'),
            ('last_updated', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
        ],
        'indexes': [
            ('idx_merchant_id', 'merchant_id'),
        ]
    },
    
    'payin_transactions': {
        'columns': [
            ('id', 'INT NOT NULL AUTO_INCREMENT PRIMARY KEY'),
            ('txn_id', 'VARCHAR(100) NOT NULL UNIQUE'),
            ('merchant_id', 'VARCHAR(50) NOT NULL'),
            ('order_id', 'VARCHAR(100) NOT NULL'),
            ('amount', 'DECIMAL(15,2) NOT NULL'),
            ('charge_amount', 'DECIMAL(15,2) NOT NULL DEFAULT 0.00'),
            ('charge_type', "ENUM('PERCENTAGE','FIXED') NOT NULL DEFAULT 'FIXED'"),
            ('net_amount', 'DECIMAL(15,2) NOT NULL'),
            ('txn_type', "VARCHAR(50) DEFAULT 'PAYIN'"),
            ('payee_name', 'VARCHAR(255)'),
            ('payee_email', 'VARCHAR(255)'),
            ('payee_mobile', 'VARCHAR(20)'),
            ('product_info', 'VARCHAR(500)'),
            ('payment_url', 'TEXT'),
            ('status', "ENUM('INITIATED','PENDING','SUCCESS','FAILED','CANCELLED') NOT NULL DEFAULT 'INITIATED'"),
            ('pg_partner', "VARCHAR(50) DEFAULT 'PayU'"),
            ('pg_txn_id', 'VARCHAR(100)'),
            ('bank_ref_no', 'VARCHAR(100)'),
            ('payment_mode', 'VARCHAR(50)'),
            ('error_message', 'TEXT'),
            ('remarks', 'TEXT'),
            ('callback_url', 'VARCHAR(500)'),
            ('created_at', 'TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP'),
            ('updated_at', 'TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
            ('completed_at', 'TIMESTAMP NULL'),
        ],
        'indexes': [
            ('idx_merchant_id', 'merchant_id'),
            ('idx_status', 'status'),
            ('idx_created_at', 'created_at'),
            ('idx_order_merchant', 'order_id, merchant_id'),
        ]
    },
    
    'payout_transactions': {
        'columns': [
            ('id', 'INT NOT NULL AUTO_INCREMENT PRIMARY KEY'),
            ('txn_id', 'VARCHAR(100) NOT NULL UNIQUE'),
            ('merchant_id', 'VARCHAR(50)'),
            ('admin_id', 'VARCHAR(50)'),
            ('reference_id', 'VARCHAR(100) NOT NULL'),
            ('order_id', 'VARCHAR(100)'),
            ('batch_id', 'VARCHAR(100)'),
            ('amount', 'DECIMAL(15,2) NOT NULL'),
            ('charge_amount', 'DECIMAL(15,2) NOT NULL DEFAULT 0.00'),
            ('charge_type', "ENUM('PERCENTAGE','FIXED') NOT NULL DEFAULT 'FIXED'"),
            ('net_amount', 'DECIMAL(15,2) NOT NULL'),
            ('txn_type', "VARCHAR(50) DEFAULT 'PAYOUT'"),
            ('bene_name', 'VARCHAR(255) NOT NULL'),
            ('bene_email', 'VARCHAR(255)'),
            ('bene_mobile', 'VARCHAR(20)'),
            ('bene_bank', 'VARCHAR(255)'),
            ('ifsc_code', 'VARCHAR(20)'),
            ('account_no', 'VARCHAR(50)'),
            ('vpa', 'VARCHAR(100)'),
            ('payment_type', "ENUM('IMPS','NEFT','RTGS','UPI') NOT NULL DEFAULT 'IMPS'"),
            ('purpose', 'VARCHAR(500)'),
            ('mobile', 'VARCHAR(20)'),
            ('status', "ENUM('PENDING','INITIATED','QUEUED','PROCESSING','INPROCESS','SUCCESS','FAILED','REVERSED') DEFAULT 'PENDING'"),
            ('pg_partner', "VARCHAR(50) DEFAULT 'PayU'"),
            ('pg_txn_id', 'VARCHAR(100)'),
            ('bank_ref_no', 'VARCHAR(100)'),
            ('utr', 'VARCHAR(100)'),
            ('name_with_bank', 'VARCHAR(255)'),
            ('name_match_score', 'INT'),
            ('error_message', 'TEXT'),
            ('remarks', 'TEXT'),
            ('callback_url', 'VARCHAR(500)'),
            ('created_at', 'TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP'),
            ('updated_at', 'TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
            ('completed_at', 'TIMESTAMP NULL'),
        ],
        'indexes': [
            ('idx_merchant_id', 'merchant_id'),
            ('idx_admin_id', 'admin_id'),
            ('idx_status', 'status'),
            ('idx_created_at', 'created_at'),
            ('idx_reference_id', 'reference_id'),
        ]
    },
}

def table_exists(cursor, table_name):
    """Check if a table exists"""
    cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
    return cursor.fetchone() is not None

def column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table"""
    cursor.execute(f"DESCRIBE {table_name}")
    columns = [col[0] for col in cursor.fetchall()]
    return column_name in columns

def create_table(cursor, table_name, schema):
    """Create a table with the given schema"""
    columns_sql = []
    for col_name, col_def in schema['columns']:
        columns_sql.append(f"{col_name} {col_def}")
    
    create_sql = f"CREATE TABLE {table_name} ({', '.join(columns_sql)}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
    cursor.execute(create_sql)
    print(f"   ✅ Created table '{table_name}'")

def add_column(cursor, table_name, column_name, column_def):
    """Add a column to an existing table"""
    try:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
        print(f"   ✅ Added column '{column_name}' to '{table_name}'")
        return True
    except pymysql.err.OperationalError as e:
        if "Duplicate column" in str(e):
            return False
        raise

def add_index(cursor, table_name, index_name, columns):
    """Add an index to a table"""
    try:
        cursor.execute(f"SHOW INDEX FROM {table_name} WHERE Key_name = '{index_name}'")
        if not cursor.fetchone():
            cursor.execute(f"ALTER TABLE {table_name} ADD INDEX {index_name} ({columns})")
            print(f"   ✅ Added index '{index_name}' to '{table_name}'")
    except Exception as e:
        print(f"   ⚠️  Could not add index '{index_name}': {e}")

try:
    conn = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME
    )
    print(f"✅ Connected to database: {Config.DB_NAME}\n")
    print("=" * 80)
    
    cursor = conn.cursor()
    
    tables_created = 0
    columns_added = 0
    indexes_added = 0
    
    # Process each table in the expected schema
    for table_name, schema in EXPECTED_SCHEMA.items():
        print(f"\n📋 Checking table: {table_name}")
        print("-" * 80)
        
        # Check if table exists
        if not table_exists(cursor, table_name):
            print(f"   ⚠️  Table '{table_name}' does not exist. Creating...")
            create_table(cursor, table_name, schema)
            tables_created += 1
            
            # Add indexes
            for index_name, columns in schema['indexes']:
                add_index(cursor, table_name, index_name, columns)
                indexes_added += 1
        else:
            print(f"   ✓ Table exists")
            
            # Check each column
            for col_name, col_def in schema['columns']:
                # Skip PRIMARY KEY in column definition for ALTER TABLE
                col_def_clean = col_def.replace(' PRIMARY KEY', '').replace(' UNIQUE', '')
                
                if not column_exists(cursor, table_name, col_name):
                    print(f"   ⚠️  Column '{col_name}' missing")
                    if add_column(cursor, table_name, col_name, col_def_clean):
                        columns_added += 1
            
            # Check indexes
            for index_name, columns in schema['indexes']:
                cursor.execute(f"SHOW INDEX FROM {table_name} WHERE Key_name = '{index_name}'")
                if not cursor.fetchone():
                    add_index(cursor, table_name, index_name, columns)
                    indexes_added += 1
    
    # Commit all changes
    conn.commit()
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ Tables created: {tables_created}")
    print(f"✅ Columns added: {columns_added}")
    print(f"✅ Indexes added: {indexes_added}")
    
    if tables_created == 0 and columns_added == 0:
        print("\n🎉 Database schema is complete! No changes needed.")
    else:
        print("\n✅ Database schema has been updated successfully!")
        print("\n💡 Next steps:")
        print("   1. Restart backend: sudo systemctl restart orchpay-api")
        print("   2. Refresh your admin dashboard")
    
    cursor.close()
    conn.close()
    
    print("=" * 80)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
