"""
Add 'details' column to admin_activity_logs table
This column will store JSON data with additional information about admin actions
"""

from database_pooled import get_db_connection

def add_details_column():
    """Add details column to admin_activity_logs table"""
    try:
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
                    AND TABLE_NAME = 'admin_activity_logs'
                    AND COLUMN_NAME = 'details'
                """)
                result = cursor.fetchone()
                
                if result['count'] > 0:
                    print("✅ Column 'details' already exists in admin_activity_logs table")
                    return True
                
                # Add the details column
                print("Adding 'details' column to admin_activity_logs table...")
                cursor.execute("""
                    ALTER TABLE admin_activity_logs
                    ADD COLUMN details TEXT NULL AFTER action
                """)
                conn.commit()
                
                print("✅ Successfully added 'details' column to admin_activity_logs table")
                return True
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"❌ Error adding details column: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Adding 'details' column to admin_activity_logs table")
    print("=" * 60)
    
    success = add_details_column()
    
    if success:
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration failed!")
