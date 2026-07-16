#!/usr/bin/env python3
"""
Complete Database Schema Fix
Analyzes current schema and fixes all missing columns/tables
"""

from config import Config
import pymysql

print("=" * 80)
print("COMPLETE DATABASE SCHEMA FIX")
print("=" * 80)

def column_exists(cursor, table, column):
    """Check if a column exists in a table"""
    cursor.execute(f"DESCRIBE {table}")
    columns = [col[0] for col in cursor.fetchall()]
    return column in columns

def add_column(cursor, table, column, definition, after=None):
    """Add a column if it doesn't exist"""
    if not column_exists(cursor, table, column):
        after_clause = f"AFTER {after}" if after else ""
        sql = f"ALTER TABLE {table} ADD COLUMN {column} {definition} {after_clause}"
        cursor.execute(sql)
        print(f"   ✅ Added '{column}' to {table}")
        return True
    else:
        print(f"   ℹ️  '{column}' already exists in {table}")
        return False

try:
    conn = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME
    )
    print(f"✅ Connected to database: {Config.DB_NAME}\n")
    
    cursor = conn.cursor()
    
    # ========================================================================
    # FIX 1: merchant_wallet - Add main_balance column
    # ========================================================================
    print("1️⃣  Fixing merchant_wallet table...")
    print("-" * 80)
    
    # Add main_balance if missing
    if add_column(cursor, 'merchant_wallet', 'main_balance', 
                  "DECIMAL(15,2) DEFAULT 0.00", 'balance'):
        # Copy balance to main_balance
        cursor.execute("""
            UPDATE merchant_wallet 
            SET main_balance = balance 
            WHERE main_balance = 0 AND balance > 0
        """)
        print(f"   ✅ Synced balance → main_balance")
    
    # Ensure other columns exist
    add_column(cursor, 'merchant_wallet', 'unsettled_balance', 
               "DECIMAL(15,2) DEFAULT 0.00", 'main_balance')
    add_column(cursor, 'merchant_wallet', 'settled_balance', 
               "DECIMAL(15,2) DEFAULT 0.00", 'unsettled_balance')
    
    # ========================================================================
    # FIX 2: payin_transactions - Add txn_type column
    # ========================================================================
    print("\n2️⃣  Fixing payin_transactions table...")
    print("-" * 80)
    
    add_column(cursor, 'payin_transactions', 'txn_type', 
               "VARCHAR(50) DEFAULT 'PAYIN'", 'txn_id')
    
    # ========================================================================
    # FIX 3: payout_transactions - Add txn_type column
    # ========================================================================
    print("\n3️⃣  Fixing payout_transactions table...")
    print("-" * 80)
    
    add_column(cursor, 'payout_transactions', 'txn_type', 
               "VARCHAR(50) DEFAULT 'PAYOUT'", 'txn_id')
    
    # ========================================================================
    # FIX 4: Ensure merchant_unsettled_wallet table exists
    # ========================================================================
    print("\n4️⃣  Checking merchant_unsettled_wallet table...")
    print("-" * 80)
    
    try:
        cursor.execute("DESCRIBE merchant_unsettled_wallet")
        print("   ℹ️  Table 'merchant_unsettled_wallet' already exists")
    except pymysql.err.ProgrammingError:
        print("   📝 Creating 'merchant_unsettled_wallet' table...")
        cursor.execute("""
            CREATE TABLE merchant_unsettled_wallet (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id VARCHAR(50) NOT NULL UNIQUE,
                balance DECIMAL(15,2) DEFAULT 0.00,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_merchant_id (merchant_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("   ✅ Created 'merchant_unsettled_wallet' table")
    
    # ========================================================================
    # FIX 5: Add missing indexes for performance
    # ========================================================================
    print("\n5️⃣  Adding performance indexes...")
    print("-" * 80)
    
    indexes_to_add = [
        ('payin_transactions', 'idx_txn_type', 'txn_type'),
        ('payout_transactions', 'idx_txn_type', 'txn_type'),
    ]
    
    for table, index_name, column in indexes_to_add:
        try:
            cursor.execute(f"SHOW INDEX FROM {table} WHERE Key_name = '{index_name}'")
            if not cursor.fetchone():
                cursor.execute(f"ALTER TABLE {table} ADD INDEX {index_name} ({column})")
                print(f"   ✅ Added index '{index_name}' to {table}")
            else:
                print(f"   ℹ️  Index '{index_name}' already exists on {table}")
        except Exception as e:
            print(f"   ⚠️  Could not add index '{index_name}' to {table}: {e}")
    
    # Commit all changes
    conn.commit()
    
    # ========================================================================
    # VERIFICATION
    # ========================================================================
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    tables_to_verify = [
        'merchant_wallet',
        'merchant_unsettled_wallet',
        'payin_transactions',
        'payout_transactions'
    ]
    
    for table in tables_to_verify:
        try:
            print(f"\n📋 {table}:")
            cursor.execute(f"DESCRIBE {table}")
            columns = cursor.fetchall()
            for col in columns:
                print(f"   - {col[0]}: {col[1]}")
        except Exception as e:
            print(f"   ⚠️  Error: {e}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ SCHEMA FIX COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    print("\n💡 Next steps:")
    print("   1. Restart backend: sudo systemctl restart orchpay-api")
    print("   2. Clear browser cache and refresh admin dashboard")
    print("=" * 80)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
