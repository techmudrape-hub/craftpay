"""
Diagnose MaxPe Payin Callback Forwarding Issue
Check if merchant callback URLs are configured correctly
"""

from database import get_db_connection
import json

def diagnose_callback_forwarding():
    """Check callback URL configuration for recent MaxPe transactions"""
    
    conn = get_db_connection()
    if not conn:
        print("ERROR: Database connection failed")
        return
    
    try:
        with conn.cursor() as cursor:
            print("=" * 80)
            print("MaxPe Payin Callback Forwarding Diagnosis")
            print("=" * 80)
            
            # Get recent MaxPe payin transactions
            cursor.execute("""
                SELECT 
                    txn_id,
                    order_id,
                    merchant_id,
                    status,
                    callback_url,
                    created_at,
                    amount,
                    net_amount,
                    charge_amount
                FROM payin_transactions
                WHERE pg_partner = 'MAXPE'
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            transactions = cursor.fetchall()
            
            if not transactions:
                print("\n❌ No MaxPe payin transactions found")
                return
            
            print(f"\n✅ Found {len(transactions)} recent MaxPe payin transactions\n")
            
            for txn in transactions:
                print("=" * 80)
                print(f"Transaction: {txn['txn_id']}")
                print(f"Order ID: {txn['order_id']}")
                print(f"Merchant ID: {txn['merchant_id']}")
                print(f"Status: {txn['status']}")
                print(f"Amount: ₹{txn['amount']}")
                print(f"Created: {txn['created_at']}")
                print("-" * 80)
                
                # Check callback URL in transaction
                txn_callback_url = txn.get('callback_url')
                if txn_callback_url and txn_callback_url.strip():
                    print(f"✅ Transaction callback_url: {txn_callback_url}")
                else:
                    print(f"❌ Transaction callback_url: NOT SET")
                
                # Check merchant_callbacks table
                if txn['merchant_id']:
                    cursor.execute("""
                        SELECT payin_callback_url, payout_callback_url
                        FROM merchant_callbacks
                        WHERE merchant_id = %s
                    """, (txn['merchant_id'],))
                    
                    merchant_callback = cursor.fetchone()
                    
                    if merchant_callback:
                        payin_url = merchant_callback.get('payin_callback_url')
                        payout_url = merchant_callback.get('payout_callback_url')
                        
                        if payin_url and payin_url.strip():
                            print(f"✅ Merchant payin_callback_url: {payin_url}")
                        else:
                            print(f"❌ Merchant payin_callback_url: NOT SET")
                        
                        if payout_url and payout_url.strip():
                            print(f"✅ Merchant payout_callback_url: {payout_url}")
                        else:
                            print(f"❌ Merchant payout_callback_url: NOT SET")
                    else:
                        print(f"❌ No entry in merchant_callbacks table for merchant: {txn['merchant_id']}")
                else:
                    print(f"⚠️  No merchant_id (admin transaction)")
                
                # Check callback logs
                cursor.execute("""
                    SELECT 
                        callback_url,
                        request_data,
                        response_code,
                        response_data,
                        created_at
                    FROM callback_logs
                    WHERE txn_id = %s
                    ORDER BY created_at DESC
                    LIMIT 3
                """, (txn['txn_id'],))
                
                callback_logs = cursor.fetchall()
                
                if callback_logs:
                    print(f"\n📋 Callback Logs ({len(callback_logs)}):")
                    for log in callback_logs:
                        print(f"  - URL: {log['callback_url']}")
                        print(f"    Response Code: {log['response_code']}")
                        print(f"    Time: {log['created_at']}")
                        if log['response_code'] == 0:
                            print(f"    Error: {log['response_data'][:200]}")
                        else:
                            print(f"    Response: {log['response_data'][:200]}")
                else:
                    print(f"\n❌ No callback logs found (callback was not attempted)")
                
                print()
            
            # Summary
            print("=" * 80)
            print("SUMMARY")
            print("=" * 80)
            
            # Count transactions with callback URLs
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM payin_transactions
                WHERE pg_partner = 'MAXPE'
                AND (callback_url IS NOT NULL AND callback_url != '')
            """)
            txn_with_url = cursor.fetchone()['count']
            
            # Count merchants with callback URLs
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM merchant_callbacks
                WHERE payin_callback_url IS NOT NULL AND payin_callback_url != ''
            """)
            merchants_with_url = cursor.fetchone()['count']
            
            # Count callback attempts
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM callback_logs cl
                JOIN payin_transactions pt ON cl.txn_id = pt.txn_id
                WHERE pt.pg_partner = 'MAXPE'
            """)
            callback_attempts = cursor.fetchone()['count']
            
            print(f"Transactions with callback_url: {txn_with_url}")
            print(f"Merchants with payin_callback_url: {merchants_with_url}")
            print(f"Total callback attempts: {callback_attempts}")
            
            if callback_attempts == 0:
                print("\n⚠️  WARNING: No callback attempts found!")
                print("   Possible reasons:")
                print("   1. No callback URLs configured")
                print("   2. Callback forwarding code not executing")
                print("   3. Transactions are not reaching SUCCESS status")
            
            # Check if merchant_callbacks table exists
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                AND table_name = 'merchant_callbacks'
            """)
            
            table_exists = cursor.fetchone()['count'] > 0
            
            if not table_exists:
                print("\n❌ ERROR: merchant_callbacks table does not exist!")
                print("   You need to create this table first.")
            else:
                print(f"\n✅ merchant_callbacks table exists")
            
    finally:
        conn.close()

if __name__ == '__main__':
    diagnose_callback_forwarding()
