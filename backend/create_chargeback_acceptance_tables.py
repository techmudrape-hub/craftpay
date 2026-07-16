#!/usr/bin/env python3
"""
Create chargeback acceptance tables for merchant acceptance workflow
"""

import pymysql
from config import Config

def create_chargeback_acceptance_tables():
    """Create chargeback acceptance and deduction tables"""
    try:
        connection = pymysql.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            # Check and add acceptance status column to chargebacks table
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'chargebacks' 
                AND COLUMN_NAME = 'acceptance_status'
            """, (Config.DB_NAME,))
            
            if cursor.fetchone()['count'] == 0:
                cursor.execute("""
                    ALTER TABLE chargebacks 
                    ADD COLUMN acceptance_status ENUM('PENDING', 'ACCEPTED', 'REJECTED') 
                    DEFAULT 'PENDING' AFTER status
                """)
                print("✅ Added acceptance_status column")
            else:
                print("ℹ️  acceptance_status column already exists")
            
            # Check and add accepted_at column
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'chargebacks' 
                AND COLUMN_NAME = 'accepted_at'
            """, (Config.DB_NAME,))
            
            if cursor.fetchone()['count'] == 0:
                cursor.execute("""
                    ALTER TABLE chargebacks 
                    ADD COLUMN accepted_at TIMESTAMP NULL AFTER acceptance_status
                """)
                print("✅ Added accepted_at column")
            else:
                print("ℹ️  accepted_at column already exists")
            
            # Check and add accepted_by column
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'chargebacks' 
                AND COLUMN_NAME = 'accepted_by'
            """, (Config.DB_NAME,))
            
            if cursor.fetchone()['count'] == 0:
                cursor.execute("""
                    ALTER TABLE chargebacks 
                    ADD COLUMN accepted_by VARCHAR(50) NULL AFTER accepted_at
                """)
                print("✅ Added accepted_by column")
            else:
                print("ℹ️  accepted_by column already exists")
            
            # Check and add rejection_reason column
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'chargebacks' 
                AND COLUMN_NAME = 'rejection_reason'
            """, (Config.DB_NAME,))
            
            if cursor.fetchone()['count'] == 0:
                cursor.execute("""
                    ALTER TABLE chargebacks 
                    ADD COLUMN rejection_reason TEXT NULL AFTER accepted_by
                """)
                print("✅ Added rejection_reason column")
            else:
                print("ℹ️  rejection_reason column already exists")
            
            print("✅ Chargeback acceptance columns added successfully!")
            
            # Create chargeback deductions table to track wallet deductions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chargeback_deductions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    deduction_id VARCHAR(100) UNIQUE NOT NULL,
                    chargeback_id INT NOT NULL,
                    merchant_id VARCHAR(50) NOT NULL,
                    transaction_id VARCHAR(100) NOT NULL,
                    order_id VARCHAR(100) NOT NULL,
                    deduction_amount DECIMAL(15, 2) NOT NULL,
                    previous_unsettled_balance DECIMAL(15, 2) NOT NULL,
                    new_unsettled_balance DECIMAL(15, 2) NOT NULL,
                    deduction_status ENUM('SUCCESS', 'FAILED', 'INSUFFICIENT_BALANCE') NOT NULL DEFAULT 'SUCCESS',
                    deduction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    remarks TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chargeback_id) REFERENCES chargebacks(id) ON DELETE CASCADE,
                    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE,
                    INDEX idx_merchant_id (merchant_id),
                    INDEX idx_chargeback_id (chargeback_id),
                    INDEX idx_transaction_id (transaction_id),
                    INDEX idx_deduction_date (deduction_date),
                    INDEX idx_deduction_status (deduction_status)
                )
            """)
            
            print("✅ Chargeback acceptance tables created successfully!")
            print("✅ Added acceptance_status, accepted_at, accepted_by, rejection_reason columns to chargebacks table")
            print("✅ Created chargeback_deductions table")
            
        connection.commit()
        connection.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating chargeback acceptance tables: {e}")
        return False

if __name__ == '__main__':
    create_chargeback_acceptance_tables()
