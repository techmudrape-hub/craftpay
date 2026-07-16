#!/usr/bin/env python3
"""Add missing columns to merchant_wallet table"""

from config import Config
import pymysql

print("=" * 70)
print("Adding Missing Columns to merchant_wallet")
print("=" * 70)

try:
    conn = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME
    )
    print(f"✅ Connected to database: {Config.DB_NAME}\n")
    
    cursor = conn.cursor()
    
    # Check current structure
    print("📋 Current merchant_wallet structure:")
    cursor.execute("DESCRIBE merchant_wallet")
    columns = cursor.fetchall()
    existing_columns = [col[0] for col in columns]
    for col in columns:
        print(f"   - {col[0]}: {col[1]}")
    
    print("\n" + "-" * 70)
    print("Adding missing columns...\n")
    
    # Add main_balance if it doesn't exist
    if 'main_balance' not in existing_columns:
        print("1️⃣  Adding 'main_balance' column...")
        cursor.execute("""
            ALTER TABLE merchant_wallet 
            ADD COLUMN main_balance DECIMAL(15,2) DEFAULT 0.00 AFTER balance
        """)
        print("   ✅ Added 'main_balance' column")
        
        # Copy balance to main_balance
        cursor.execute("""
            UPDATE merchant_wallet 
            SET main_balance = balance 
            WHERE main_balance = 0
        """)
        print("   ✅ Copied existing balance to main_balance")
    else:
        print("1️⃣  ℹ️  'main_balance' column already exists")
    
    # Add unsettled_balance if it doesn't exist
    if 'unsettled_balance' not in existing_columns:
        print("\n2️⃣  Adding 'unsettled_balance' column...")
        cursor.execute("""
            ALTER TABLE merchant_wallet 
            ADD COLUMN unsettled_balance DECIMAL(15,2) DEFAULT 0.00 AFTER main_balance
        """)
        print("   ✅ Added 'unsettled_balance' column")
    else:
        print("\n2️⃣  ℹ️  'unsettled_balance' column already exists")
    
    # Add settled_balance if it doesn't exist
    if 'settled_balance' not in existing_columns:
        print("\n3️⃣  Adding 'settled_balance' column...")
        cursor.execute("""
            ALTER TABLE merchant_wallet 
            ADD COLUMN settled_balance DECIMAL(15,2) DEFAULT 0.00 AFTER unsettled_balance
        """)
        print("   ✅ Added 'settled_balance' column")
    else:
        print("\n3️⃣  ℹ️  'settled_balance' column already exists")
    
    conn.commit()
    
    # Show updated structure
    print("\n" + "=" * 70)
    print("📋 Updated merchant_wallet structure:")
    print("=" * 70)
    cursor.execute("DESCRIBE merchant_wallet")
    columns = cursor.fetchall()
    for col in columns:
        print(f"   - {col[0]}: {col[1]}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 70)
    print("✅ Successfully added missing columns!")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
