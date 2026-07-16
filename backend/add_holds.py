import os
from dotenv import load_dotenv
load_dotenv()
from database_pooled import get_db_connection

conn = get_db_connection()
if conn:
    try:
        with conn.cursor() as cursor:
            try:
                cursor.execute("ALTER TABLE merchant_wallet ADD COLUMN cyber_hold_amount DECIMAL(15,2) DEFAULT 0.00;")
                print("cyber_hold_amount added")
            except Exception as e:
                print(f"cyber_hold_amount error: {e}")
            try:
                cursor.execute("ALTER TABLE merchant_wallet ADD COLUMN total_hold_amount DECIMAL(15,2) DEFAULT 0.00;")
                print("total_hold_amount added")
            except Exception as e:
                print(f"total_hold_amount error: {e}")
            conn.commit()
            print("Done")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
else:
    print("Could not connect to DB")
