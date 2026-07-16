#!/usr/bin/env python3
"""
OrchPay Database Migration Script
==================================
This script safely migrates the database schema by:
1. Backing up existing data
2. Creating new tables if they don't exist
3. Adding missing columns to existing tables
4. Creating missing indexes
5. Preserving all existing data

Usage:
    python migrate_database.py [--backup-only] [--dry-run]

Options:
    --backup-only    Only create a backup, don't run migrations
    --dry-run        Show what would be done without making changes
"""

import pymysql
import sys
import os
from datetime import datetime
from config import Config

class DatabaseMigrator:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.connection = None
        self.backup_file = None
        
    def connect(self):
        """Establish database connection"""
        try:
            self.connection = pymysql.connect(
                host=Config.DB_HOST,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                cursorclass=pymysql.cursors.DictCursor
            )
            print(f"✓ Connected to database: {Config.DB_NAME}")
            return True
        except Exception as e:
            print(f"✗ Database connection error: {e}")
            return False
    
    def backup_database(self):
        """Create a backup of the database"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.backup_file = f"backup_{Config.DB_NAME}_{timestamp}.sql"
            
            print(f"\n📦 Creating database backup: {self.backup_file}")
            
            # Use mysqldump command
            backup_cmd = f"mysqldump -h {Config.DB_HOST} -u {Config.DB_USER} -p{Config.DB_PASSWORD} {Config.DB_NAME} > {self.backup_file}"
            
            if self.dry_run:
                print(f"[DRY RUN] Would execute: {backup_cmd.replace(Config.DB_PASSWORD, '****')}")
                return True
            
            os.system(backup_cmd)
            
            if os.path.exists(self.backup_file):
                size = os.path.getsize(self.backup_file)
                print(f"✓ Backup created successfully ({size} bytes)")
                return True
            else:
                print("✗ Backup file not created")
                return False
                
        except Exception as e:
            print(f"✗ Backup error: {e}")
            return False
    
    def table_exists(self, table_name):
        """Check if a table exists"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
                return cursor.fetchone() is not None
        except Exception as e:
            print(f"Error checking table {table_name}: {e}")
            return False
    
    def column_exists(self, table_name, column_name):
        """Check if a column exists in a table"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE '{column_name}'")
                return cursor.fetchone() is not None
        except Exception as e:
            print(f"Error checking column {table_name}.{column_name}: {e}")
            return False
    
    def index_exists(self, table_name, index_name):
        """Check if an index exists"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"SHOW INDEX FROM {table_name} WHERE Key_name = '{index_name}'")
                return cursor.fetchone() is not None
        except Exception as e:
            print(f"Error checking index {table_name}.{index_name}: {e}")
            return False
    
    def execute_sql(self, sql, description):
        """Execute SQL with error handling"""
        try:
            if self.dry_run:
                print(f"[DRY RUN] {description}")
                print(f"  SQL: {sql[:100]}...")
                return True
            
            with self.connection.cursor() as cursor:
                cursor.execute(sql)
            self.connection.commit()
            print(f"✓ {description}")
            return True
        except Exception as e:
            print(f"✗ {description} - Error: {e}")
            return False
    
    def create_tables(self):
        """Create all tables if they don't exist"""
        print("\n🔨 Creating tables...")
        
        tables = {
            'admin_users': """
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    admin_id VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    pin_hash VARCHAR(255) NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP NULL,
                    login_attempts INT DEFAULT 0,
                    locked_until TIMESTAMP NULL,
                    password_changed_at TIMESTAMP NULL,
                    pin_changed_at TIMESTAMP NULL,
                    must_change_password BOOLEAN DEFAULT FALSE
                )
            """,
            'admin_activity_logs': """
                CREATE TABLE IF NOT EXISTS admin_activity_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    admin_id VARCHAR(50) NOT NULL,
                    action VARCHAR(100) NOT NULL,
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    status VARCHAR(20),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (admin_id) REFERENCES admin_users(admin_id)
                )
            """,
            'commercial_schemes': """
                CREATE TABLE IF NOT EXISTS commercial_schemes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    scheme_name VARCHAR(100) UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_by VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (created_by) REFERENCES admin_users(admin_id)
                )
            """,
            'commercial_charges': """
                CREATE TABLE IF NOT EXISTS commercial_charges (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    scheme_id INT NOT NULL,
                    service_type ENUM('PAYOUT', 'PAYIN') NOT NULL,
                    product_name VARCHAR(100) NOT NULL,
                    min_amount DECIMAL(10, 2) NOT NULL,
                    max_amount DECIMAL(10, 2) NOT NULL,
                    charge_value DECIMAL(10, 4) NOT NULL,
                    charge_type ENUM('PERCENTAGE', 'FIXED') NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (scheme_id) REFERENCES commercial_schemes(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_scheme_product (scheme_id, service_type, product_name)
                )
            """,
            'merchants': """
                CREATE TABLE IF NOT EXISTS merchants (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    merchant_id VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    pin_hash VARCHAR(255) NULL,
                    full_name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    mobile VARCHAR(20) NOT NULL,
                    dob DATE,
                    aadhar_card VARCHAR(20) NOT NULL,
                    pan_no VARCHAR(20) NOT NULL,
                    pincode VARCHAR(10) NOT NULL,
                    state VARCHAR(100) NOT NULL,
                    city VARCHAR(100) NOT NULL,
                    house_number VARCHAR(100),
                    address TEXT NOT NULL,
                    landmark VARCHAR(255),
                    merchant_type ENUM('PAYIN', 'PAYOUT', 'BOTH') NOT NULL,
                    account_number VARCHAR(50) NOT NULL,
                    ifsc_code VARCHAR(20) NOT NULL,
                    gst_no VARCHAR(50) NOT NULL,
                    scheme_id INT,
                    authorization_key VARCHAR(255) UNIQUE NOT NULL,
                    module_secret VARCHAR(255) UNIQUE NOT NULL,
                    aes_iv VARCHAR(255) NOT NULL,
                    aes_key VARCHAR(255) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_by VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    password_changed_at TIMESTAMP NULL,
                    pin_changed_at TIMESTAMP NULL,
                    FOREIGN KEY (scheme_id) REFERENCES commercial_schemes(id),
                    FOREIGN KEY (created_by) REFERENCES admin_users(admin_id)
                )
            """,
            'merchant_documents': """
                CREATE TABLE IF NOT EXISTS merchant_documents (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    merchant_id VARCHAR(50) NOT NULL,
                    aadhar_front_path VARCHAR(500),
                    aadhar_back_path VARCHAR(500),
                    pan_card_path VARCHAR(500),
                    gst_certificate_path VARCHAR(500),
                    cancelled_cheque_path VARCHAR(500),
                    shop_photo_path VARCHAR(500),
                    profile_photo_path VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE
                )
            """,
            'merchant_ip_whitelist': """
                CREATE TABLE IF NOT EXISTS merchant_ip_whitelist (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    merchant_id VARCHAR(50) NOT NULL,
                    ip_address VARCHAR(45) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE,
                    UNIQUE KEY unique_merchant_ip (merchant_id, ip_address)
                )
            """,
            'merchant_callbacks': """
                CREATE TABLE IF NOT EXISTS merchant_callbacks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    merchant_id VARCHAR(50) UNIQUE NOT NULL,
                    payin_callback_url VARCHAR(500),
                    payout_callback_url VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE
                )
            """,
            'merchant_banks': """
                CREATE TABLE IF NOT EXISTS merchant_banks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    merchant_id VARCHAR(50) NOT NULL,
                    bank_name VARCHAR(255) NOT NULL,
                    account_number VARCHAR(50) NOT NULL,
                    ifsc_code VARCHAR(20) NOT NULL,
                    branch_name VARCHAR(255),
                    account_holder_name VARCHAR(255) NOT NULL,
                    tpin_hash VARCHAR(255) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE
                )
            """,
            'admin_banks': """
                CREATE TABLE IF NOT EXISTS admin_banks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    admin_id VARCHAR(50) NOT NULL,
                    bank_name VARCHAR(255) NOT NULL,
                    account_number VARCHAR(50) NOT NULL,
                    ifsc_code VARCHAR(20) NOT NULL,
                    branch_name VARCHAR(255),
                    account_holder_name VARCHAR(255) NOT NULL,
                    tpin_hash VARCHAR(255) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (admin_id) REFERENCES admin_users(admin_id) ON DELETE CASCADE
                )
            """,
            'payin_transactions': """
                CREATE TABLE IF NOT EXISTS payin_transactions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    txn_id VARCHAR(100) UNIQUE NOT NULL,
                    merchant_id VARCHAR(50) NOT NULL,
                    order_id VARCHAR(100) NOT NULL,
                    amount DECIMAL(15, 2) NOT NULL,
                    charge_amount DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                    charge_type ENUM('PERCENTAGE', 'FIXED') NOT NULL DEFAULT 'FIXED',
                    net_amount DECIMAL(15, 2) NOT NULL,
                    payee_name VARCHAR(255),
                    payee_email VARCHAR(255),
                    payee_mobile VARCHAR(20),
                    product_info VARCHAR(500),
                    status ENUM('INITIATED', 'PENDING', 'SUCCESS', 'FAILED', 'CANCELLED') NOT NULL DEFAULT 'INITIATED',
                    pg_partner VARCHAR(50) DEFAULT 'PayU',
                    pg_txn_id VARCHAR(100),
                    bank_ref_no VARCHAR(100),
                    payment_mode VARCHAR(50),
                    error_message TEXT,
                    remarks TEXT,
                    callback_url VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP NULL,
                    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE
                )
            """,
            'merchant_wallet': """
                CREATE TABLE IF NOT EXISTS merchant_wallet (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    merchant_id VARCHAR(50) UNIQUE NOT NULL,
                    balance DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE
                )
            """,
            'wallet_transactions': """
                CREATE TABLE IF NOT EXISTS wallet_transactions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    merchant_id VARCHAR(50) NOT NULL,
                    txn_id VARCHAR(100) NOT NULL,
                    txn_type ENUM('CREDIT', 'DEBIT') NOT NULL,
                    amount DECIMAL(15, 2) NOT NULL,
                    balance_before DECIMAL(15, 2) NOT NULL,
                    balance_after DECIMAL(15, 2) NOT NULL,
                    description VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE
                )
            """,
            'callback_logs': """
                CREATE TABLE IF NOT EXISTS callback_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    merchant_id VARCHAR(50) NOT NULL,
                    txn_id VARCHAR(100) NOT NULL,
                    callback_url VARCHAR(500),
                    request_data TEXT,
                    response_code INT,
                    response_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE
                )
            """,
            'payu_webhook_config': """
                CREATE TABLE IF NOT EXISTS payu_webhook_config (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    event_type VARCHAR(100) NOT NULL,
                    webhook_url VARCHAR(500) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_event (event_type)
                )
            """,
            'payu_webhook_logs': """
                CREATE TABLE IF NOT EXISTS payu_webhook_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    event_type VARCHAR(100) NOT NULL,
                    merchant_ref_id VARCHAR(100),
                    payu_ref_id VARCHAR(100),
                    payload TEXT,
                    status ENUM('RECEIVED', 'PROCESSED', 'FAILED') NOT NULL DEFAULT 'RECEIVED',
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP NULL
                )
            """,
            'payu_tokens': """
                CREATE TABLE IF NOT EXISTS payu_tokens (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    token_type VARCHAR(50),
                    expires_at TIMESTAMP NOT NULL,
                    user_uuid VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """,
            'service_routing': """
                CREATE TABLE IF NOT EXISTS service_routing (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    merchant_id VARCHAR(50),
                    service_type ENUM('PAYIN', 'PAYOUT') NOT NULL,
                    routing_type ENUM('SINGLE_USER', 'ALL_USERS') NOT NULL,
                    pg_partner VARCHAR(50) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    priority INT DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE,
                    UNIQUE KEY unique_routing (merchant_id, service_type, routing_type, pg_partner)
                )
            """,
            'payout_transactions': """
                CREATE TABLE IF NOT EXISTS payout_transactions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    txn_id VARCHAR(100) UNIQUE NOT NULL,
                    merchant_id VARCHAR(50) NOT NULL,
                    reference_id VARCHAR(100) NOT NULL,
                    order_id VARCHAR(100) NULL,
                    batch_id VARCHAR(100),
                    amount DECIMAL(15, 2) NOT NULL,
                    charge_amount DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                    charge_type ENUM('PERCENTAGE', 'FIXED') NOT NULL DEFAULT 'FIXED',
                    net_amount DECIMAL(15, 2) NOT NULL,
                    bene_name VARCHAR(255) NOT NULL,
                    bene_email VARCHAR(255),
                    bene_mobile VARCHAR(20),
                    bene_bank VARCHAR(255),
                    ifsc_code VARCHAR(20),
                    account_no VARCHAR(50),
                    vpa VARCHAR(100),
                    payment_type ENUM('IMPS', 'NEFT', 'RTGS', 'UPI') NOT NULL DEFAULT 'IMPS',
                    purpose VARCHAR(500),
                    status ENUM('INITIATED', 'QUEUED', 'INPROCESS', 'SUCCESS', 'FAILED', 'REVERSED') NOT NULL DEFAULT 'INITIATED',
                    pg_partner VARCHAR(50) DEFAULT 'PayU',
                    pg_txn_id VARCHAR(100),
                    bank_ref_no VARCHAR(100),
                    utr VARCHAR(100),
                    name_with_bank VARCHAR(255),
                    name_match_score INT,
                    error_message TEXT,
                    remarks TEXT,
                    callback_url VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP NULL,
                    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE
                )
            """,
            'fund_requests': """
                CREATE TABLE IF NOT EXISTS fund_requests (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    request_id VARCHAR(100) UNIQUE NOT NULL,
                    merchant_id VARCHAR(50) NOT NULL,
                    amount DECIMAL(15, 2) NOT NULL,
                    request_type ENUM('TOPUP', 'SETTLEMENT') NOT NULL,
                    status ENUM('PENDING', 'APPROVED', 'REJECTED') NOT NULL DEFAULT 'PENDING',
                    remarks TEXT,
                    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP NULL,
                    processed_by VARCHAR(50),
                    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE,
                    FOREIGN KEY (processed_by) REFERENCES admin_users(admin_id)
                )
            """,
            'merchant_unsettled_wallet': """
                CREATE TABLE IF NOT EXISTS merchant_unsettled_wallet (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    merchant_id VARCHAR(50) UNIQUE NOT NULL,
                    balance DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE
                )
            """,
            'admin_wallet': """
                CREATE TABLE IF NOT EXISTS admin_wallet (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    admin_id VARCHAR(50) UNIQUE NOT NULL,
                    main_balance DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                    unsettled_balance DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (admin_id) REFERENCES admin_users(admin_id) ON DELETE CASCADE
                )
            """,
            'admin_wallet_transactions': """
                CREATE TABLE IF NOT EXISTS admin_wallet_transactions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    admin_id VARCHAR(50) NOT NULL,
                    txn_id VARCHAR(100) NOT NULL,
                    wallet_type ENUM('MAIN', 'UNSETTLED') NOT NULL,
                    txn_type ENUM('CREDIT', 'DEBIT') NOT NULL,
                    amount DECIMAL(15, 2) NOT NULL,
                    balance_before DECIMAL(15, 2) NOT NULL,
                    balance_after DECIMAL(15, 2) NOT NULL,
                    description VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (admin_id) REFERENCES admin_users(admin_id) ON DELETE CASCADE
                )
            """
        }
        
        for table_name, sql in tables.items():
            if not self.table_exists(table_name):
                self.execute_sql(sql, f"Creating table: {table_name}")
            else:
                print(f"⊙ Table already exists: {table_name}")
    
    def create_indexes(self):
        """Create missing indexes for performance"""
        print("\n📊 Creating indexes...")
        
        indexes = [
            ('payin_transactions', 'idx_merchant_id', 'merchant_id'),
            ('payin_transactions', 'idx_status', 'status'),
            ('payin_transactions', 'idx_created_at', 'created_at'),
            ('payout_transactions', 'idx_merchant_id', 'merchant_id'),
            ('payout_transactions', 'idx_status', 'status'),
            ('payout_transactions', 'idx_created_at', 'created_at'),
            ('payout_transactions', 'idx_reference_id', 'reference_id'),
            ('payout_transactions', 'idx_order_id', 'order_id'),
            ('wallet_transactions', 'idx_merchant_id', 'merchant_id'),
            ('wallet_transactions', 'idx_created_at', 'created_at'),
            ('callback_logs', 'idx_txn_id', 'txn_id'),
            ('payu_webhook_logs', 'idx_event_type', 'event_type'),
            ('payu_webhook_logs', 'idx_merchant_ref_id', 'merchant_ref_id'),
            ('payu_webhook_logs', 'idx_created_at', 'created_at'),
            ('fund_requests', 'idx_merchant_id', 'merchant_id'),
            ('fund_requests', 'idx_status', 'status'),
            ('admin_wallet_transactions', 'idx_admin_id', 'admin_id'),
            ('admin_wallet_transactions', 'idx_wallet_type', 'wallet_type'),
            ('admin_wallet_transactions', 'idx_created_at', 'created_at'),
        ]
        
        for table_name, index_name, column_name in indexes:
            if self.table_exists(table_name) and not self.index_exists(table_name, index_name):
                sql = f"CREATE INDEX {index_name} ON {table_name}({column_name})"
                self.execute_sql(sql, f"Creating index: {table_name}.{index_name}")
            else:
                if self.table_exists(table_name):
                    print(f"⊙ Index already exists: {table_name}.{index_name}")
    
    def verify_schema(self):
        """Verify the database schema"""
        print("\n🔍 Verifying schema...")
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                print(f"✓ Total tables: {len(tables)}")
                
                for table in tables:
                    table_name = list(table.values())[0]
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                    count = cursor.fetchone()['count']
                    print(f"  - {table_name}: {count} rows")
            
            return True
        except Exception as e:
            print(f"✗ Schema verification error: {e}")
            return False
    
    def run(self, backup_only=False):
        """Run the migration"""
        print("=" * 60)
        print("OrchPay Database Migration")
        print("=" * 60)
        
        if self.dry_run:
            print("\n⚠️  DRY RUN MODE - No changes will be made\n")
        
        # Step 1: Connect to database
        if not self.connect():
            return False
        
        # Step 2: Create backup
        if not self.backup_database():
            print("\n⚠️  Warning: Backup failed. Continue anyway? (yes/no)")
            response = input().strip().lower()
            if response != 'yes':
                print("Migration cancelled.")
                return False
        
        if backup_only:
            print("\n✓ Backup completed. Exiting (backup-only mode).")
            return True
        
        # Step 3: Create tables
        self.create_tables()
        
        # Step 4: Create indexes
        self.create_indexes()
        
        # Step 5: Verify schema
        self.verify_schema()
        
        print("\n" + "=" * 60)
        if self.dry_run:
            print("✓ Dry run completed successfully!")
        else:
            print("✓ Migration completed successfully!")
        print("=" * 60)
        
        if self.backup_file:
            print(f"\n📦 Backup file: {self.backup_file}")
            print("   Keep this file safe in case you need to restore.")
        
        return True
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            print("\n✓ Database connection closed")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='OrchPay Database Migration Script')
    parser.add_argument('--backup-only', action='store_true', help='Only create backup, skip migration')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    migrator = DatabaseMigrator(dry_run=args.dry_run)
    
    try:
        success = migrator.run(backup_only=args.backup_only)
        migrator.close()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrupted by user")
        migrator.close()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        migrator.close()
        sys.exit(1)

if __name__ == '__main__':
    main()
