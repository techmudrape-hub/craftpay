"""
Add checkout_expired_at column to payin_transactions table
This column tracks when a checkout link expired due to 6-minute timeout
"""

import pymysql
from database import get_db_connection

def add_checkout_expiry_column():
    """Add checkout_expired_at column to payin_transactions table"""
    
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return False
    
    try:
        with conn.cursor() as cursor:
            # Check if column already exists
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'payin_transactions'
                AND COLUMN_NAME = 'checkout_expired_at'
            """)
            
            result = cursor.fetchone()
            
            if result['count'] > 0:
                print("✓ Column 'checkout_expired_at' already exists")
                return True
            
            # Add the column
            print("Adding 'checkout_expired_at' column to payin_transactions table...")
            cursor.execute("""
                ALTER TABLE payin_transactions
                ADD COLUMN checkout_expired_at TIMESTAMP NULL DEFAULT NULL
                AFTER completed_at
            """)
            
            conn.commit()
            print("✅ Successfully added 'checkout_expired_at' column")
            
            # Verify the column was added
            cursor.execute("""
                SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'payin_transactions'
                AND COLUMN_NAME = 'checkout_expired_at'
            """)
            
            column_info = cursor.fetchone()
            if column_info:
                print(f"\nColumn details:")
                print(f"  Name: {column_info['COLUMN_NAME']}")
                print(f"  Type: {column_info['COLUMN_TYPE']}")
                print(f"  Nullable: {column_info['IS_NULLABLE']}")
                print(f"  Default: {column_info['COLUMN_DEFAULT']}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 60)
    print("Adding checkout_expired_at column to payin_transactions")
    print("=" * 60)
    
    success = add_checkout_expiry_column()
    
    if success:
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration failed!")
