import os
import sys
import json
from dotenv import load_dotenv

# Add the current directory to path to allow importing backend modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

def find_recent_callback():
    """
    Finds the most recent Localpaisa transactions and their corresponding 
    callback data that was sent to the merchant.
    """
    try:
        from database import get_db_connection
    except ImportError:
        print("Please run this script from inside the backend directory.")
        return

    print("Connecting to the database...")
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return
        
    try:
        with conn.cursor() as cursor:
            print("\nSearching for recent Localpaisa payin transactions...")
            
            # Find the most recent payin transactions for Localpaisa
            cursor.execute("""
                SELECT txn_id, order_id, merchant_id, status, created_at, updated_at, pg_txn_id
                FROM payin_transactions
                WHERE pg_partner = 'LOCALPAISA'
                ORDER BY updated_at DESC
                LIMIT 5
            """)
            
            recent_txns = cursor.fetchall()
            
            if not recent_txns:
                print("No Localpaisa transactions found in the database yet.")
                return
                
            print(f"Found {len(recent_txns)} recent Localpaisa transactions. Checking for callback logs...\n")
            
            for index, txn in enumerate(recent_txns):
                print("=" * 60)
                print(f"[{index + 1}] Transaction ID: {txn['txn_id']}")
                print(f"    Order ID:    {txn['order_id']}")
                print(f"    PG Txn ID:   {txn['pg_txn_id']}")
                print(f"    Status:      {txn['status']}")
                print(f"    Updated At:  {txn['updated_at']}")
                
                # Now find the callback logs for this transaction
                cursor.execute("""
                    SELECT callback_url, request_data, response_code, response_data, created_at
                    FROM callback_logs
                    WHERE txn_id = %s
                    ORDER BY created_at DESC
                """, (txn['txn_id'],))
                
                callbacks = cursor.fetchall()
                
                if callbacks:
                    print(f"\n    ✅ Found {len(callbacks)} callback log(s) sent to the merchant:")
                    latest = callbacks[0]
                    print(f"    Sent to: {latest['callback_url']}")
                    print(f"    Sent at: {latest['created_at']}")
                    print(f"    HTTP Response Code: {latest['response_code']}")
                    
                    try:
                        parsed_request = json.loads(latest['request_data'])
                        print("\n    [Callback Payload Sent to Merchant]")
                        print(json.dumps(parsed_request, indent=6))
                    except:
                        print("\n    [Raw Callback Payload Sent to Merchant]")
                        print(f"      {latest['request_data']}")
                        
                    print(f"\n    Merchant Server Response: {latest['response_data'][:200]}...")
                else:
                    print("\n    ⚠️ No callback logs found for this transaction.")
                    print("       (Either it's still PENDING, or the merchant hasn't configured a callback URL)")
                    
            print("=" * 60)
            
            print("\nNote: The RAW incoming webhook payload from Localpaisa is not stored directly in the database.")
            print("It is parsed, updates the transaction, and then the structured payload above is forwarded to the merchant.")
            print("To see the raw incoming payload from Localpaisa, check your backend console/application logs for the text: 'Localpaisa Payin Callback Received'.")
                    
    except Exception as e:
        print(f"Error querying database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    find_recent_callback()
