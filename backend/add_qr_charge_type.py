from database_pooled import get_db_connection

def add_col():
    conn = get_db_connection()
    if not conn:
        print("No db connection")
        return
    try:
        with conn.cursor() as cursor:
            cursor.execute("ALTER TABLE qr_transactions ADD COLUMN charge_type ENUM('PERCENTAGE', 'FIXED') NOT NULL DEFAULT 'FIXED' AFTER charge_amount")
            conn.commit()
            print("Successfully added charge_type to qr_transactions")
    except Exception as e:
        if "Duplicate column name" in str(e):
            print("Column already exists")
        else:
            print("Error:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    add_col()
