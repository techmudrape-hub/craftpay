"""
Add interval-based settlement columns
"""
from database_pooled import get_db_connection

def add_columns():
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        with conn.cursor() as cursor:
            # Add settlement_interval_minutes column
            print("1️⃣  Adding settlement_interval_minutes column...")
            try:
                cursor.execute("""
                    ALTER TABLE auto_settlement_config 
                    ADD COLUMN settlement_interval_minutes INT DEFAULT NULL 
                    COMMENT 'Settle after X minutes (NULL = use hour/minute)'
                """)
                print("   ✅ Added settlement_interval_minutes")
            except Exception as e:
                if "Duplicate column" in str(e):
                    print("   ℹ️  Column already exists")
                else:
                    raise
            
            # Add settlement_mode column
            print("\n2️⃣  Adding settlement_mode column...")
            try:
                cursor.execute("""
                    ALTER TABLE auto_settlement_config 
                    ADD COLUMN settlement_mode ENUM('SCHEDULED', 'INTERVAL') DEFAULT 'SCHEDULED'
                    COMMENT 'SCHEDULED=specific time, INTERVAL=after X minutes'
                """)
                print("   ✅ Added settlement_mode")
            except Exception as e:
                if "Duplicate column" in str(e):
                    print("   ℹ️  Column already exists")
                else:
                    raise
            
            conn.commit()
            print("\n✅ Database schema updated successfully!")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 60)
    print("Adding Interval Settlement Columns")
    print("=" * 60)
    add_columns()
