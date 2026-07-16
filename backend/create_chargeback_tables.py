#!/usr/bin/env python3
"""
Create chargeback tables for the chargeback management system
"""

import pymysql
from config import Config

def create_chargeback_tables():
    """Create chargeback tables"""
    try:
        connection = pymysql.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            # Create chargebacks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chargebacks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    merchant_id VARCHAR(50) NOT NULL,
                    transaction_id VARCHAR(100) NOT NULL,
                    order_id VARCHAR(100) NOT NULL,
                    chargeback_amount DECIMAL(15, 2) NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    payment_mode VARCHAR(50),
                    customer_name VARCHAR(255),
                    customer_mobile VARCHAR(20),
                    utr VARCHAR(100),
                    chargeback_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    uploaded_by VARCHAR(50) NOT NULL,
                    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE,
                    FOREIGN KEY (uploaded_by) REFERENCES admin_users(admin_id),
                    INDEX idx_merchant_id (merchant_id),
                    INDEX idx_transaction_id (transaction_id),
                    INDEX idx_order_id (order_id),
                    INDEX idx_chargeback_date (chargeback_date),
                    INDEX idx_created_at (created_at)
                )
            """)
            
            # Create chargeback uploads table to track CSV uploads
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chargeback_uploads (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    upload_id VARCHAR(100) UNIQUE NOT NULL,
                    merchant_id VARCHAR(50) NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    total_records INT NOT NULL DEFAULT 0,
                    successful_records INT NOT NULL DEFAULT 0,
                    failed_records INT NOT NULL DEFAULT 0,
                    uploaded_by VARCHAR(50) NOT NULL,
                    upload_status ENUM('PROCESSING', 'COMPLETED', 'FAILED') NOT NULL DEFAULT 'PROCESSING',
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE,
                    FOREIGN KEY (uploaded_by) REFERENCES admin_users(admin_id),
                    INDEX idx_merchant_id (merchant_id),
                    INDEX idx_upload_status (upload_status),
                    INDEX idx_created_at (created_at)
                )
            """)
            
            print("✅ Chargeback tables created successfully!")
            
        connection.commit()
        connection.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating chargeback tables: {e}")
        return False

if __name__ == '__main__':
    create_chargeback_tables()
