#!/usr/bin/env python3
"""Fix all missing columns in database tables"""

from config import Config
import pymysql

print("=" * 70)
print("Fixing All Missing Database Columns")
print("=" * 70)

def add_column_if_missing(cursor, table, column, definition, after=None):
    """Add a column to a table if it doesn't exist"""
    try:
        # Check if column exists
        cursor.execute(f"DESCRIBE {table}")
        columns = [col[0] for col in cursor.fetchall()]
        
        if column not in columns:
            after_clause = f"AFTER {after}" if after else ""
            sql = f"ALTER TABLE {table} ADD COLUMN {column} {definition} {after_clause}"
            cursor.execute(sql)
            print(f"   ✅ Added '{column}' to {table}")
            return True
        else:
            print(f"   ℹ️  '{column}' already exists in {table}")
            return False
    except Exception as e:
        print(f"   ⚠️  Error adding '{column}' to {table}: {e}")
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
    
    # Fix payin_transactions table
    print("1️⃣  Fixing payin_transactions table...")
    add_column_if_missing(cursor, 'payin_transactions', 'txn_id', 
                          "VARCHAR(100)", 'transaction_id')
    add_column_if_missing(cursor, 'payin_transactions', 'txn_type', 
                          "VARCHAR(50) DEFAULT 'PAYIN'", 'txn_id')
    
    # Fix payout_transactions table
    print("\n2️⃣  Fixing payout_transactions table...")
    add_column_if_missing(cursor, 'payout_transactions', 'txn_id', 
                          "VARCHAR(100)", 'transaction_id')
    add_column_if_missing(cursor, 'payout_transactions', 'txn_type', 
                          "VARCHAR(50) DEFAULT 'PAYOUT'", 'txn_id')
    
    # Fix merchant_wallet table
    print("\n3️⃣  Fixing merchant_wallet table...")
    add_column_if_missing(cursor, 'merchant_wallet', 'main_balance', 
                          "DECIMAL(15,2) DEFAULT 0.00", 'balance')
    add_column_if_missing(cursor, 'merchant_wallet', 'unsettled_balance', 
                          "DECIMAL(15,2) DEFAULT 0.00", 'main_balance')
    add_column_if_missing(cursor, 'merchant_wallet', 'settled_balance', 
                          "DECIMAL(15,2) DEFAULT 0.00", 'unsettled_balance')
    
    # Copy balance to main_balance if main_balance is 0
    print("\n4️⃣  Syncing balance data...")
    try:
        cursor.execute("""
            UPDATE merchant_wallet 
            SET main_balance = balance 
            WHERE main_balance = 0 AND balance > 0
        """)
        rows = cursor.rowcount
        if rows > 0:
            print(f"   ✅ Synced {rows} wallet balances")
        else:
            print(f"   ℹ️  No balance sync needed")
    except Exception as e:
        print(f"   ℹ️  Balance sync: {e}")
    
    # Commit all changes
    conn.commit()
    
    # Show updated structures
    print("\n" + "=" * 70)
    print("Verification")
    print("=" * 70)
    
    tables = ['payin_transactions', 'payout_transactions', 'merchant_wallet']
    
    for table in tables:
        try:
            print(f"\n📋 {table} structure:")
            cursor.execute(f"DESCRIBE {table}")
            columns = cursor.fetchall()
            for col in columns:
                print(f"   - {col[0]}: {col[1]}")
        except Exception as e:
            print(f"   ⚠️  Table {table} not found or error: {e}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 70)
    print("✅ All missing columns have been fixed!")
    print("=" * 70)
    print("\n💡 Tip: Restart your backend service:")
    print("   sudo systemctl restart orchpay-api")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
