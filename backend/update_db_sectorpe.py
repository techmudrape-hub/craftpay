import traceback
from database import get_db_connection

def update_db():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to db")
        return

    try:
        with conn.cursor() as cursor:
            # Update service_routing
            cursor.execute("UPDATE service_routing SET pg_partner = 'PES' WHERE pg_partner = 'SECTORPE'")
            print(f"Updated service_routing: {cursor.rowcount} rows")

            # Update payout_transactions
            cursor.execute("UPDATE payout_transactions SET pg_partner = 'PES' WHERE pg_partner = 'SECTORPE'")
            print(f"Updated payout_transactions: {cursor.rowcount} rows")

            # Update payin_transactions
            cursor.execute("UPDATE payin_transactions SET pg_partner = 'PES' WHERE pg_partner = 'SECTORPE'")
            print(f"Updated payin_transactions: {cursor.rowcount} rows")

        conn.commit()
        print("Database updated successfully")
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    update_db()
