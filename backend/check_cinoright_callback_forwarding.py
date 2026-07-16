"""
Check Cinoright Callback Forwarding Configuration
This script checks if merchant callback URLs are configured for Cinoright payouts
"""

from database import get_db_connection
import json

def check_callback_configuration():
    """Check callback URL configuration for recent Cinoright transactions"""
    
    print("=" * 80)
    print("CINORIGHT CALLBACK FORWARDING DIAGNOSTIC")
    print("=" * 80)
    
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        with conn.cursor() as cursor:
            # Check recent Cinoright transactions
            print("\n1. Recent Cinoright Transactions:")
            print("-" * 80)
            
            cursor.execute("""
                SELECT 
                    txn_id,
                    reference_id,
                    merchant_id,
                    status,
                    callback_url,
                    created_at,
                    updated_at
                FROM payout_transactions
                WHERE pg_partner = 'CINORIGHT'
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            transactions = cursor.fetchall()
            
            if not transactions:
                print("⚠ No Cinoright transactions found")
                return
            
            print(f"Found {len(transactions)} recent transactions:\n")
            
            for txn in transactions:
                print(f"Transaction ID: {txn['txn_id']}")
                print(f"  Reference ID: {txn['reference_id']}")
                print(f"  Merchant ID: {txn['merchant_id']}")
                print(f"  Status: {txn['status']}")
                print(f"  Callback URL (in transaction): {txn['callback_url'] if txn['callback_url'] else 'NOT SET'}")
                print(f"  Created: {txn['created_at']}")
                print(f"  Updated: {txn['updated_at']}")
                
                # Check merchant_callbacks table
                if txn['merchant_id']:
                    cursor.execute("""
                        SELECT payout_callback_url 
                        FROM merchant_callbacks
                        WHERE merchant_id = %s
                    """, (txn['merchant_id'],))
                    
                    merchant_callback = cursor.fetchone()
                    if merchant_callback:
                        print(f"  Callback URL (in merchant_callbacks): {merchant_callback['payout_callback_url'] if merchant_callback['payout_callback_url'] else 'NOT SET'}")
                    else:
                        print(f"  Callback URL (in merchant_callbacks): NO RECORD FOUND")
                else:
                    print(f"  Callback URL (in merchant_callbacks): N/A (no merchant_id)")
                
                print()
            
            # Check callback logs
            print("\n2. Recent Callback Logs for Cinoright:")
            print("-" * 80)
            
            cursor.execute("""
                SELECT 
                    cl.merchant_id,
                    cl.txn_id,
                    cl.callback_url,
                    cl.response_code,
                    cl.created_at,
                    pt.reference_id
                FROM callback_logs cl
                LEFT JOIN payout_transactions pt ON cl.txn_id = pt.txn_id
                WHERE pt.pg_partner = 'CINORIGHT'
                ORDER BY cl.created_at DESC
                LIMIT 10
            """)
            
            logs = cursor.fetchall()
            
            if not logs:
                print("⚠ No callback logs found for Cinoright transactions")
            else:
                print(f"Found {len(logs)} callback log(s):\n")
                
                for log in logs:
                    print(f"Transaction ID: {log['txn_id']}")
                    print(f"  Reference ID: {log['reference_id']}")
                    print(f"  Merchant ID: {log['merchant_id']}")
                    print(f"  Callback URL: {log['callback_url']}")
                    print(f"  Response Code: {log['response_code']}")
                    print(f"  Created: {log['created_at']}")
                    print()
            
            # Check merchant_callbacks table structure
            print("\n3. All Merchants with Payout Callback URLs:")
            print("-" * 80)
            
            cursor.execute("""
                SELECT 
                    merchant_id,
                    payout_callback_url
                FROM merchant_callbacks
                WHERE payout_callback_url IS NOT NULL 
                AND payout_callback_url != ''
            """)
            
            merchants = cursor.fetchall()
            
            if not merchants:
                print("⚠ No merchants have payout_callback_url configured")
            else:
                print(f"Found {len(merchants)} merchant(s) with payout callback URLs:\n")
                
                for merchant in merchants:
                    print(f"Merchant ID: {merchant['merchant_id']}")
                    print(f"  Payout Callback URL: {merchant['payout_callback_url']}")
                    print()
            
            print("=" * 80)
            print("DIAGNOSTIC COMPLETE")
            print("=" * 80)
            
            print("\nRECOMMENDATIONS:")
            print("-" * 80)
            
            # Check if any transaction has callback_url
            has_txn_callback = any(txn['callback_url'] for txn in transactions)
            
            # Check if any merchant has payout_callback_url
            has_merchant_callback = len(merchants) > 0
            
            if not has_txn_callback and not has_merchant_callback:
                print("❌ NO CALLBACK URLs CONFIGURED!")
                print("\nTo enable callback forwarding, you need to either:")
                print("1. Include 'callback_url' in the payout request payload, OR")
                print("2. Configure 'payout_callback_url' in the merchant_callbacks table")
                print("\nExample SQL to configure merchant callback:")
                print("UPDATE merchant_callbacks SET payout_callback_url = 'https://merchant.com/callback' WHERE merchant_id = 'MERCHANT_ID';")
            elif not has_txn_callback:
                print("⚠ Transactions don't have callback_url in payload")
                print("✓ But some merchants have payout_callback_url configured")
                print("\nCallbacks will be forwarded to merchants with configured URLs")
            elif not has_merchant_callback:
                print("⚠ No merchants have payout_callback_url configured")
                print("✓ But transactions may have callback_url in payload")
                print("\nCallbacks will be forwarded if callback_url is in the payout request")
            else:
                print("✓ Callback forwarding is configured!")
                print("  - Some transactions have callback_url in payload")
                print("  - Some merchants have payout_callback_url configured")
            
    finally:
        conn.close()

if __name__ == '__main__':
    try:
        check_callback_configuration()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
