"""
Check what columns exist in payout_transactions table
"""

from database_pooled import get_db_connection

conn = get_db_connection()
if conn:
    with conn.cursor() as cursor:
        cursor.execute("DESCRIBE payout_transactions")
        columns = cursor.fetchall()
        
        print("Columns in payout_transactions table:")
        print("=" * 60)
        for col in columns:
            print(f"  {col['Field']:30} {col['Type']:20} {col['Null']:5} {col['Key']:5}")
    
    conn.close()
