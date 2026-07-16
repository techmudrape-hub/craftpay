#!/usr/bin/env python3
"""Fix collation mismatch in merchant_ip_security table"""

from config import Config
import pymysql

print("=" * 80)
print("Fixing Collation Mismatch")
print("=" * 80)

try:
    conn = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME
    )
    print(f"✅ Connected to database: {Config.DB_NAME}\n")
    
    cursor = conn.cursor()
    
    # Check current collation of merchants table
    print("1️⃣  Checking merchants table collation...")
    cursor.execute("""
        SELECT TABLE_COLLATION 
        FROM information_schema.TABLES 
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'merchants'
    """, (Config.DB_NAME,))
    merchants_collation = cursor.fetchone()
    if merchants_collation:
        print(f"   Merchants table collation: {merchants_collation[0]}")
    
    # Check current collation of merchant_ip_security table
    print("\n2️⃣  Checking merchant_ip_security table collation...")
    cursor.execute("""
        SELECT TABLE_COLLATION 
        FROM information_schema.TABLES 
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'merchant_ip_security'
    """, (Config.DB_NAME,))
    ip_security_collation = cursor.fetchone()
    if ip_security_collation:
        print(f"   merchant_ip_security table collation: {ip_security_collation[0]}")
    
    # Fix the collation - convert merchant_ip_security to utf8mb4_0900_ai_ci
    print("\n3️⃣  Converting merchant_ip_security table to utf8mb4_0900_ai_ci...")
    try:
        cursor.execute("""
            ALTER TABLE merchant_ip_security 
            CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci
        """)
        print("   ✅ Converted merchant_ip_security table collation")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # Also fix the specific columns that are used in joins
    print("\n4️⃣  Fixing merchant_id column collation...")
    try:
        cursor.execute("""
            ALTER TABLE merchant_ip_security 
            MODIFY COLUMN merchant_id VARCHAR(50) 
            CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL
        """)
        print("   ✅ Fixed merchant_id column collation")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    print("\n5️⃣  Fixing created_by column collation...")
    try:
        cursor.execute("""
            ALTER TABLE merchant_ip_security 
            MODIFY COLUMN created_by VARCHAR(50) 
            CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL
        """)
        print("   ✅ Fixed created_by column collation")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    conn.commit()
    
    # Verify the fix
    print("\n" + "=" * 80)
    print("Verification")
    print("=" * 80)
    
    cursor.execute("""
        SELECT COLUMN_NAME, CHARACTER_SET_NAME, COLLATION_NAME 
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = %s 
        AND TABLE_NAME = 'merchant_ip_security' 
        AND COLUMN_NAME IN ('merchant_id', 'created_by')
    """, (Config.DB_NAME,))
    
    print("\nmerchant_ip_security columns:")
    for col in cursor.fetchall():
        print(f"   - {col[0]}: {col[1]} / {col[2]}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ Collation mismatch fixed!")
    print("=" * 80)
    print("\n💡 Restart backend: sudo systemctl restart orchpay-api")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
