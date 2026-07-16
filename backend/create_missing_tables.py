#!/usr/bin/env python3
"""Create missing settlement_transactions and merchant_ip_security tables"""

from config import Config
import pymysql

print("=" * 80)
print("Creating Missing Tables")
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
    
    # Create settlement_transactions table
    print("1️⃣  Creating settlement_transactions table...")
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settlement_transactions (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                settlement_id VARCHAR(100) NOT NULL UNIQUE,
                merchant_id VARCHAR(50) NOT NULL,
                amount DECIMAL(15,2) NOT NULL,
                settled_by VARCHAR(50) NOT NULL,
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_merchant_id (merchant_id),
                INDEX idx_created_at (created_at),
                INDEX fk_settlement_admin (settled_by)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("   ✅ Created settlement_transactions table")
    except Exception as e:
        print(f"   ℹ️  {e}")
    
    # Create merchant_ip_security table
    print("\n2️⃣  Creating merchant_ip_security table...")
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS merchant_ip_security (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                merchant_id VARCHAR(50) NOT NULL,
                ip_address VARCHAR(45) NOT NULL,
                description VARCHAR(255),
                is_active TINYINT(1) DEFAULT 1,
                created_by VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_merchant_ip (merchant_id, ip_address),
                INDEX idx_merchant_ip_active (merchant_id, ip_address, is_active),
                INDEX idx_created_by (created_by)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("   ✅ Created merchant_ip_security table")
    except Exception as e:
        print(f"   ℹ️  {e}")
    
    conn.commit()
    
    # Verify tables exist
    print("\n" + "=" * 80)
    print("Verification")
    print("=" * 80)
    
    cursor.execute("SHOW TABLES LIKE 'settlement_transactions'")
    if cursor.fetchone():
        print("✅ settlement_transactions table exists")
        cursor.execute("DESCRIBE settlement_transactions")
        print("   Columns:")
        for col in cursor.fetchall():
            print(f"   - {col[0]}: {col[1]}")
    
    print()
    cursor.execute("SHOW TABLES LIKE 'merchant_ip_security'")
    if cursor.fetchone():
        print("✅ merchant_ip_security table exists")
        cursor.execute("DESCRIBE merchant_ip_security")
        print("   Columns:")
        for col in cursor.fetchall():
            print(f"   - {col[0]}: {col[1]}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ Missing tables created successfully!")
    print("=" * 80)
    print("\n💡 Restart backend: sudo systemctl restart orchpay-api")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
