"""
QR Payment System - Database Migration Script
Run this ONCE on your server to create the necessary tables and columns.
"""

from database_pooled import get_db_connection

def run_migration():
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return False

    try:
        with conn.cursor() as cursor:

            # -------------------------------------------------------
            # 1. Add qr_enabled column to merchants table
            # -------------------------------------------------------
            try:
                cursor.execute("""
                    ALTER TABLE merchants
                    ADD COLUMN qr_enabled BOOLEAN NOT NULL DEFAULT FALSE
                """)
                print("✅ Added qr_enabled column to merchants table")
            except Exception as e:
                if "Duplicate column name" in str(e) or "already exists" in str(e):
                    print("ℹ️  qr_enabled column already exists on merchants - skipping")
                else:
                    raise

            # -------------------------------------------------------
            # 2. Create qr_codes table (uploaded QR images)
            # -------------------------------------------------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS qr_codes (
                    id          INT AUTO_INCREMENT PRIMARY KEY,
                    name        VARCHAR(255) NOT NULL,
                    qr_image_path VARCHAR(512) NOT NULL,
                    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            print("✅ Created qr_codes table")

            # -------------------------------------------------------
            # 3. Create qr_merchant_routing table
            #    (which merchant → which QR code, and enabled/disabled)
            # -------------------------------------------------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS qr_merchant_routing (
                    id          INT AUTO_INCREMENT PRIMARY KEY,
                    merchant_id VARCHAR(50) NOT NULL,
                    qr_code_id  INT NOT NULL,
                    is_enabled  BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_merchant_qr (merchant_id),
                    FOREIGN KEY (qr_code_id) REFERENCES qr_codes(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            print("✅ Created qr_merchant_routing table")

            # -------------------------------------------------------
            # 4. Create qr_transactions table
            # -------------------------------------------------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS qr_transactions (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    txn_id          VARCHAR(100) NOT NULL UNIQUE,
                    order_id        VARCHAR(100) NOT NULL,
                    merchant_id     VARCHAR(50)  NOT NULL,
                    qr_code_id      INT,
                    amount          DECIMAL(15,2) NOT NULL,
                    charge_amount   DECIMAL(15,2) NOT NULL DEFAULT 0.00,
                    net_amount      DECIMAL(15,2) NOT NULL DEFAULT 0.00,
                    customer_name   VARCHAR(255),
                    mobile          VARCHAR(20),
                    email           VARCHAR(255),
                    status          ENUM('INITIATED','UTR_SUBMITTED','SUCCESS','FAILED') NOT NULL DEFAULT 'INITIATED',
                    utr             VARCHAR(100),
                    pg_partner      VARCHAR(50) NOT NULL DEFAULT 'QR',
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    completed_at    DATETIME,
                    INDEX idx_merchant_id  (merchant_id),
                    INDEX idx_order_id     (order_id),
                    INDEX idx_txn_id       (txn_id),
                    INDEX idx_status       (status),
                    INDEX idx_created_at   (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            print("✅ Created qr_transactions table")

        conn.commit()
        print("\n🎉 QR Payment System migration completed successfully!")
        return True

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
