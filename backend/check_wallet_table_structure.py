"""
Check wallet_transactions table structure
"""

from database import get_db_connection

conn = get_db_connection()
if conn:
    try:
        with conn.cursor() as cursor:
            cursor.execute("DESCRIBE wallet_transactions")
            columns = cursor.fetchall()
            
            print("wallet_transactions table structure:")
            print("=" * 80)
            for col in columns:
                print(f"{col['Field']}: {col['Type']} {col['Null']} {col['Key']} {col['Default']}")
    finally:
        conn.close()
