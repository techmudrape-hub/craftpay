"""
Create auto-settlement configuration tables
"""
from database_pooled import get_db_connection

def create_auto_settlement_tables():
    """Create tables for auto-settlement feature"""
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return False
    
    try:
        with conn.cursor() as cursor:
            # First, check the merchants table collation
            print("\n🔍 Checking merchants table structure...")
            cursor.execute("""
                SELECT CHARACTER_SET_NAME, COLLATION_NAME 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'merchants' 
                AND COLUMN_NAME = 'merchant_id'
            """)
            merchant_col_info = cursor.fetchone()
            
            if merchant_col_info:
                charset = merchant_col_info['CHARACTER_SET_NAME']
                collation = merchant_col_info['COLLATION_NAME']
                print(f"   Merchants.merchant_id: {charset} / {collation}")
            else:
                # Default fallback
                charset = 'utf8mb4'
                collation = 'utf8mb4_unicode_ci'
                print(f"   Using default: {charset} / {collation}")
            
            # Create auto_settlement_config table
            print("\n1️⃣  Creating auto_settlement_config table...")
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS auto_settlement_config (
                    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    merchant_id VARCHAR(50) CHARACTER SET {charset} COLLATE {collation} NOT NULL UNIQUE,
                    is_enabled BOOLEAN DEFAULT FALSE,
                    settlement_frequency ENUM('HOURLY', 'DAILY', 'WEEKLY') DEFAULT 'DAILY',
                    settlement_hour INT DEFAULT 0 COMMENT 'Hour of day (0-23) for DAILY/WEEKLY',
                    settlement_minute INT DEFAULT 0 COMMENT 'Minute of hour (0-59)',
                    settlement_day INT DEFAULT 1 COMMENT 'Day of week (1-7) for WEEKLY, 1=Monday',
                    hold_percentage DECIMAL(5,2) DEFAULT 0.00 COMMENT 'Percentage to hold in unsettled (0-100)',
                    minimum_settlement_amount DECIMAL(15,2) DEFAULT 0.00 COMMENT 'Minimum amount to trigger settlement',
                    last_settlement_at TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_enabled (is_enabled),
                    INDEX idx_last_settlement (last_settlement_at),
                    CONSTRAINT fk_auto_settlement_merchant 
                        FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET={charset} COLLATE={collation}
            """)
            print("   ✅ Created auto_settlement_config table")
            
            # Create auto_settlement_logs table
            print("\n2️⃣  Creating auto_settlement_logs table...")
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS auto_settlement_logs (
                    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    merchant_id VARCHAR(50) CHARACTER SET {charset} COLLATE {collation} NOT NULL,
                    settlement_id VARCHAR(100) NULL,
                    attempted_amount DECIMAL(15,2) NOT NULL,
                    settled_amount DECIMAL(15,2) DEFAULT 0.00,
                    held_amount DECIMAL(15,2) DEFAULT 0.00,
                    status ENUM('SUCCESS', 'FAILED', 'SKIPPED') NOT NULL,
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_merchant_id (merchant_id),
                    INDEX idx_status (status),
                    INDEX idx_created_at (created_at),
                    CONSTRAINT fk_auto_settlement_logs_merchant 
                        FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET={charset} COLLATE={collation}
            """)
            print("   ✅ Created auto_settlement_logs table")
            
            conn.commit()
            print("\n✅ All auto-settlement tables created successfully!")
            return True
            
    except Exception as e:
        print(f"\n❌ Error creating tables: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 60)
    print("Creating Auto-Settlement Tables")
    print("=" * 60)
    create_auto_settlement_tables()
