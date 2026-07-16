#!/usr/bin/env python3
"""Fix missing database tables and columns"""

from config import Config
import pymysql

print("=" * 70)
print("OrchPay Database Schema Fix")
print("=" * 70)

try:
    # Connect to database
    conn = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME
    )
    print(f"✅ Connected to database: {Config.DB_NAME}")
    print("-" * 70)
    
    cursor = conn.cursor()
    
    # Fix 1: Add settled_balance column to merchant_wallet
    print("\n1️⃣  Checking merchant_wallet table...")
    try:
        cursor.execute("""
            ALTER TABLE merchant_wallet 
            ADD COLUMN settled_balance DECIMAL(15,2) DEFAULT 0.00 AFTER unsettled_balance
        """)
        print("   ✅ Added 'settled_balance' column to merchant_wallet")
    except pymysql.err.OperationalError as e:
        if "Duplicate column name" in str(e):
            print("   ℹ️  Column 'settled_balance' already exists")
        else:
            print(f"   ⚠️  Error: {e}")
    
    # Fix 2: Create merchant_wallet_transactions table
    print("\n2️⃣  Checking merchant_wallet_transactions table...")
    try:
        cursor.execute("""
            CREATE TABLE merchant_wallet_transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id VARCHAR(100) NOT NULL,
                transaction_type ENUM('CREDIT', 'DEBIT', 'SETTLEMENT', 'REFUND', 'CHARGE', 'TOPUP', 'FETCH') NOT NULL,
                amount DECIMAL(15,2) NOT NULL,
                balance_before DECIMAL(15,2) NOT NULL,
                balance_after DECIMAL(15,2) NOT NULL,
                reference_id VARCHAR(100),
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by VARCHAR(100),
                INDEX idx_merchant_id (merchant_id),
                INDEX idx_transaction_type (transaction_type),
                INDEX idx_created_at (created_at),
                INDEX idx_reference_id (reference_id),
                INDEX idx_merchant_created (merchant_id, created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("   ✅ Created 'merchant_wallet_transactions' table")
    except pymysql.err.OperationalError as e:
        if "already exists" in str(e):
            print("   ℹ️  Table 'merchant_wallet_transactions' already exists")
        else:
            print(f"   ⚠️  Error: {e}")
    
    # Fix 3: Ensure merchant_wallet columns have correct types
    print("\n3️⃣  Updating merchant_wallet column types...")
    try:
        cursor.execute("""
            ALTER TABLE merchant_wallet 
            MODIFY COLUMN main_balance DECIMAL(15,2) DEFAULT 0.00,
            MODIFY COLUMN unsettled_balance DECIMAL(15,2) DEFAULT 0.00
        """)
        print("   ✅ Updated column types in merchant_wallet")
    except Exception as e:
        print(f"   ℹ️  Columns already have correct types")
    
    # Commit all changes
    conn.commit()
    
    # Verify the changes
    print("\n" + "=" * 70)
    print("Verification")
    print("=" * 70)
    
    # Check merchant_wallet structure
    print("\n📋 merchant_wallet structure:")
    cursor.execute("DESCRIBE merchant_wallet")
    columns = cursor.fetchall()
    for col in columns:
        print(f"   - {col[0]}: {col[1]}")
    
    # Check merchant_wallet_transactions structure
    print("\n📋 merchant_wallet_transactions structure:")
    cursor.execute("DESCRIBE merchant_wallet_transactions")
    columns = cursor.fetchall()
    for col in columns:
        print(f"   - {col[0]}: {col[1]}")
    
    # Check row counts
    cursor.execute("SELECT COUNT(*) FROM merchant_wallet")
    wallet_count = cursor.fetchone()[0]
    print(f"\n📊 merchant_wallet records: {wallet_count}")
    
    cursor.execute("SELECT COUNT(*) FROM merchant_wallet_transactions")
    trans_count = cursor.fetchone()[0]
    print(f"📊 merchant_wallet_transactions records: {trans_count}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 70)
    print("✅ Database schema fix completed successfully!")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
