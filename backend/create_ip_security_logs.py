#!/usr/bin/env python3
"""Create ip_security_logs table"""

from config import Config
import pymysql

print("=" * 80)
print("Creating ip_security_logs Table")
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
    
    print("Creating ip_security_logs table...")
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ip_security_logs (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                merchant_id VARCHAR(50) NOT NULL,
                ip_address VARCHAR(45) NOT NULL,
                endpoint VARCHAR(255) NOT NULL,
                action VARCHAR(100) NOT NULL,
                status ENUM('ALLOWED','BLOCKED') NOT NULL,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_ip_logs_merchant (merchant_id, created_at),
                INDEX idx_ip_logs_status (status, created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
        """)
        print("   ✅ Created ip_security_logs table")
    except Exception as e:
        print(f"   ℹ️  {e}")
    
    conn.commit()
    
    # Verify table
    print("\n" + "=" * 80)
    print("Verification")
    print("=" * 80)
    
    cursor.execute("SHOW TABLES LIKE 'ip_security_logs'")
    if cursor.fetchone():
        print("✅ ip_security_logs table exists")
        cursor.execute("DESCRIBE ip_security_logs")
        print("\nColumns:")
        for col in cursor.fetchall():
            print(f"   - {col[0]}: {col[1]}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ Table created successfully!")
    print("=" * 80)
    print("\n💡 Restart backend: sudo systemctl restart orchpay-api")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
