"""
Fix payout_transactions foreign key constraint to allow NULL merchant_id
This is needed for admin personal payouts which don't belong to any merchant
"""

from database import get_db_connection

def fix_payout_transactions_foreign_key():
    """
    Remove the foreign key constraint on merchant_id and recreate it to allow NULL
    """
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ Database connection failed")
            return False
        
        with conn.cursor() as cursor:
            print("=" * 80)
            print("Fixing payout_transactions foreign key constraint")
            print("=" * 80)
            
            # Step 1: Check if the foreign key exists
            cursor.execute("""
                SELECT CONSTRAINT_NAME 
                FROM information_schema.KEY_COLUMN_USAGE 
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'payout_transactions' 
                AND COLUMN_NAME = 'merchant_id'
                AND REFERENCED_TABLE_NAME = 'merchants'
            """)
            
            fk_result = cursor.fetchone()
            
            if fk_result:
                fk_name = fk_result['CONSTRAINT_NAME']
                print(f"✓ Found foreign key constraint: {fk_name}")
                
                # Step 2: Drop the existing foreign key constraint
                print(f"Dropping foreign key constraint: {fk_name}...")
                cursor.execute(f"""
                    ALTER TABLE payout_transactions 
                    DROP FOREIGN KEY {fk_name}
                """)
                print(f"✓ Dropped foreign key constraint: {fk_name}")
            else:
                print("⚠ No foreign key constraint found on merchant_id")
            
            # Step 3: Modify merchant_id column to allow NULL
            print("Modifying merchant_id column to allow NULL...")
            cursor.execute("""
                ALTER TABLE payout_transactions 
                MODIFY COLUMN merchant_id VARCHAR(50) DEFAULT NULL
            """)
            print("✓ Modified merchant_id column to allow NULL")
            
            # Step 4: Recreate the foreign key constraint with ON DELETE SET NULL
            # This allows merchant_id to be NULL and sets it to NULL if merchant is deleted
            print("Recreating foreign key constraint with NULL support...")
            cursor.execute("""
                ALTER TABLE payout_transactions 
                ADD CONSTRAINT payout_transactions_ibfk_1 
                FOREIGN KEY (merchant_id) 
                REFERENCES merchants(merchant_id) 
                ON DELETE SET NULL
            """)
            print("✓ Recreated foreign key constraint with ON DELETE SET NULL")
            
            conn.commit()
            
            print("=" * 80)
            print("✅ Successfully fixed payout_transactions foreign key constraint")
            print("=" * 80)
            print("\nChanges made:")
            print("1. Dropped old foreign key constraint")
            print("2. Modified merchant_id to allow NULL values")
            print("3. Recreated foreign key with ON DELETE SET NULL")
            print("\nNow admin personal payouts can have NULL merchant_id")
            
            return True
            
    except Exception as e:
        print(f"❌ Error fixing foreign key: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("PAYOUT TRANSACTIONS FOREIGN KEY FIX")
    print("=" * 80)
    print("\nThis script will:")
    print("1. Drop the existing foreign key constraint on merchant_id")
    print("2. Modify merchant_id column to allow NULL")
    print("3. Recreate foreign key with ON DELETE SET NULL")
    print("\nThis allows admin personal payouts to have NULL merchant_id")
    print("=" * 80)
    
    response = input("\nDo you want to proceed? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        success = fix_payout_transactions_foreign_key()
        if success:
            print("\n✅ Database migration completed successfully!")
        else:
            print("\n❌ Database migration failed!")
    else:
        print("\n❌ Migration cancelled by user")
