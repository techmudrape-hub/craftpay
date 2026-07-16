"""
Check if merchant has callback URL configured
"""

from database import get_db_connection

def check_merchant_callback():
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        with conn.cursor() as cursor:
            # Get merchant from recent Razorpay transaction
            cursor.execute("""
                SELECT DISTINCT merchant_id, callback_url
                FROM payin_transactions
                WHERE pg_partner = 'RAZORPAY'
                ORDER BY created_at DESC
                LIMIT 5
            """)
            
            txns = cursor.fetchall()
            
            print("=" * 80)
            print("MERCHANT CALLBACK URL CHECK")
            print("=" * 80)
            
            for txn in txns:
                merchant_id = txn['merchant_id']
                callback_url = txn['callback_url']
                
                print(f"\nMerchant: {merchant_id}")
                print(f"  Callback URL in transaction: {callback_url or 'NOT SET'}")
                
                # Check merchant_callbacks table
                cursor.execute("""
                    SELECT payin_callback_url
                    FROM merchant_callbacks
                    WHERE merchant_id = %s
                """, (merchant_id,))
                
                merchant_callback = cursor.fetchone()
                
                if merchant_callback:
                    print(f"  Callback URL in merchant_callbacks: {merchant_callback['payin_callback_url'] or 'NOT SET'}")
                else:
                    print(f"  ⚠ No entry in merchant_callbacks table")
                
                # Check merchant details
                cursor.execute("""
                    SELECT full_name, email, is_active
                    FROM merchants
                    WHERE merchant_id = %s
                """, (merchant_id,))
                
                merchant = cursor.fetchone()
                
                if merchant:
                    print(f"  Merchant Name: {merchant['full_name']}")
                    print(f"  Email: {merchant['email']}")
                    print(f"  Active: {merchant['is_active']}")
                
                print("-" * 80)
    
    finally:
        conn.close()

if __name__ == '__main__':
    check_merchant_callback()
