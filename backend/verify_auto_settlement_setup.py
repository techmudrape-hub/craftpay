"""
Verify auto-settlement setup
"""
from database_pooled import get_db_connection

def verify_setup():
    """Verify auto-settlement tables and structure"""
    print("=" * 60)
    print("Verifying Auto-Settlement Setup")
    print("=" * 60)
    
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return False
    
    try:
        with conn.cursor() as cursor:
            # Check auto_settlement_config table
            print("\n1️⃣  Checking auto_settlement_config table...")
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'auto_settlement_config'
            """)
            if cursor.fetchone()['count'] == 1:
                print("   ✅ Table exists")
                
                # Check structure
                cursor.execute("""
                    DESCRIBE auto_settlement_config
                """)
                columns = cursor.fetchall()
                print(f"   ✅ Columns: {len(columns)}")
                for col in columns:
                    print(f"      - {col['Field']}: {col['Type']}")
            else:
                print("   ❌ Table does not exist")
                return False
            
            # Check auto_settlement_logs table
            print("\n2️⃣  Checking auto_settlement_logs table...")
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'auto_settlement_logs'
            """)
            if cursor.fetchone()['count'] == 1:
                print("   ✅ Table exists")
                
                # Check structure
                cursor.execute("""
                    DESCRIBE auto_settlement_logs
                """)
                columns = cursor.fetchall()
                print(f"   ✅ Columns: {len(columns)}")
                for col in columns:
                    print(f"      - {col['Field']}: {col['Type']}")
            else:
                print("   ❌ Table does not exist")
                return False
            
            # Check foreign key constraints
            print("\n3️⃣  Checking foreign key constraints...")
            cursor.execute("""
                SELECT 
                    CONSTRAINT_NAME,
                    TABLE_NAME,
                    COLUMN_NAME,
                    REFERENCED_TABLE_NAME,
                    REFERENCED_COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME IN ('auto_settlement_config', 'auto_settlement_logs')
                AND REFERENCED_TABLE_NAME IS NOT NULL
            """)
            constraints = cursor.fetchall()
            if constraints:
                print(f"   ✅ Found {len(constraints)} foreign key(s)")
                for fk in constraints:
                    print(f"      - {fk['TABLE_NAME']}.{fk['COLUMN_NAME']} -> {fk['REFERENCED_TABLE_NAME']}.{fk['REFERENCED_COLUMN_NAME']}")
            else:
                print("   ⚠️  No foreign keys found")
            
            # Check indexes
            print("\n4️⃣  Checking indexes...")
            cursor.execute("""
                SELECT 
                    TABLE_NAME,
                    INDEX_NAME,
                    COLUMN_NAME
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME IN ('auto_settlement_config', 'auto_settlement_logs')
                ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
            """)
            indexes = cursor.fetchall()
            if indexes:
                print(f"   ✅ Found {len(indexes)} index(es)")
                current_table = None
                current_index = None
                for idx in indexes:
                    if idx['TABLE_NAME'] != current_table or idx['INDEX_NAME'] != current_index:
                        print(f"      - {idx['TABLE_NAME']}.{idx['INDEX_NAME']} ({idx['COLUMN_NAME']})")
                        current_table = idx['TABLE_NAME']
                        current_index = idx['INDEX_NAME']
            else:
                print("   ⚠️  No indexes found")
            
            # Test insert and delete
            print("\n5️⃣  Testing data operations...")
            
            # Get a test merchant
            cursor.execute("""
                SELECT merchant_id FROM merchants LIMIT 1
            """)
            merchant = cursor.fetchone()
            
            if merchant:
                test_merchant_id = merchant['merchant_id']
                print(f"   Using test merchant: {test_merchant_id}")
                
                # Insert test config
                cursor.execute("""
                    INSERT INTO auto_settlement_config
                    (merchant_id, is_enabled, settlement_frequency, hold_percentage)
                    VALUES (%s, FALSE, 'DAILY', 10.00)
                    ON DUPLICATE KEY UPDATE is_enabled = FALSE
                """, (test_merchant_id,))
                print("   ✅ Insert/Update config successful")
                
                # Insert test log
                cursor.execute("""
                    INSERT INTO auto_settlement_logs
                    (merchant_id, attempted_amount, settled_amount, held_amount, status, reason)
                    VALUES (%s, 1000.00, 900.00, 100.00, 'SUCCESS', 'Test log')
                """, (test_merchant_id,))
                print("   ✅ Insert log successful")
                
                # Clean up test data
                cursor.execute("""
                    DELETE FROM auto_settlement_logs 
                    WHERE merchant_id = %s AND reason = 'Test log'
                """, (test_merchant_id,))
                print("   ✅ Delete log successful")
                
                conn.commit()
            else:
                print("   ⚠️  No merchants found for testing")
            
            print("\n" + "=" * 60)
            print("✅ Auto-Settlement Setup Verified Successfully!")
            print("=" * 60)
            print("\nNext Steps:")
            print("1. Start the scheduler: python auto_settlement_scheduler.py")
            print("2. Or setup as systemd service (see AUTO_SETTLEMENT_SETUP_GUIDE.md)")
            print("3. Access admin UI: Fund Manager > Auto-Settlement")
            print("=" * 60)
            
            return True
            
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    verify_setup()
