import os
import json
import pymysql
from database_pooled import get_db_connection

def check_recent_mmp_callbacks(limit=5):
    print(f"={'='*60}")
    print(f"Checking {limit} Most Recent MakeMyPayment Merchant Callbacks")
    print(f"={'='*60}")
    
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database.")
        return
        
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Query callback_logs for MakeMyPayment partner
            query = """
                SELECT id, merchant_id, txn_id, callback_url, request_data, 
                       response_code, response_data, created_at
                FROM callback_logs
                WHERE request_data LIKE '%%MAKEMYPAYMENT%%'
                ORDER BY created_at DESC
                LIMIT %s
            """
            cursor.execute(query, (limit,))
            results = cursor.fetchall()
            
            if not results:
                print("No MakeMyPayment callbacks found in the recent logs.")
                return
                
            for row in results:
                print(f"\nTime: {row['created_at']}")
                print(f"Merchant ID: {row['merchant_id']} | TXN ID: {row['txn_id']}")
                print(f"Callback URL: {row['callback_url']}")
                print(f"Response Code: {row['response_code']}")
                
                try:
                    req_data = json.loads(row['request_data'])
                    print(f"Request Payload (sent to merchant):")
                    print(json.dumps(req_data, indent=2))
                    
                    # Highlight UTR specifically
                    utr = req_data.get('utr')
                    status = req_data.get('status')
                    print(f"-> UTR Extracted: {utr if utr else 'NONE'}")
                    print(f"-> Status: {status}")
                except:
                    print(f"Request Data (Raw): {row['request_data']}")
                    
                print("-" * 40)
                
    except Exception as e:
        print(f"Error querying database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_recent_mmp_callbacks(5)
