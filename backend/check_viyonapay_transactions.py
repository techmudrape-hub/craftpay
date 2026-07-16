#!/usr/bin/env python3
"""
Check ViyonaPay transactions in database
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
import json

def main():
    print("="*80)
    print("🔍 CHECKING VIYONAPAY TRANSACTIONS IN DATABASE")
    print("="*80)
    
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        with conn.cursor() as cursor:
            # Check all ViyonaPay transactions
            print("\n📋 All ViyonaPay transactions:")
            cursor.execute("""
                SELECT txn_id, order_id, pg_partner, status, amount, merchant_id, created_at
                FROM payin_transactions
                WHERE pg_partner LIKE '%VIYO%'
                ORDER BY created_at DESC
                LIMIT 20
            """)
            
            txns = cursor.fetchall()
            
            if txns:
                print(f"\nFound {len(txns)} ViyonaPay transactions:\n")
                for txn in txns:
                    print(f"  Order ID: {txn['order_id']}")
                    print(f"    - Transaction ID: {txn['txn_id']}")
                    print(f"    - PG Partner: {txn['pg_partner']}")
                    print(f"    - Status: {txn['status']}")
                    print(f"    - Amount: ₹{txn['amount']}")
                    print(f"    - Merchant: {txn['merchant_id']}")
                    print(f"    - Created: {txn['created_at']}")
                    print()
            else:
                print("\n❌ No ViyonaPay transactions found")
                
                # Show all transactions
                print("\n📋 All recent transactions (any PG partner):")
                cursor.execute("""
                    SELECT txn_id, order_id, pg_partner, status, amount, created_at
                    FROM payin_transactions
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                
                all_txns = cursor.fetchall()
                if all_txns:
                    for txn in all_txns:
                        print(f"  - {txn['order_id']} | {txn['pg_partner']} | {txn['status']} | ₹{txn['amount']}")
                else:
                    print("  No transactions found at all")
            
            # Check for PENDING transactions
            print("\n" + "="*80)
            print("📋 PENDING ViyonaPay transactions (waiting for callback):")
            print("="*80)
            cursor.execute("""
                SELECT txn_id, order_id, pg_partner, status, amount, merchant_id, created_at
                FROM payin_transactions
                WHERE pg_partner LIKE '%VIYO%' AND status IN ('INITIATED', 'PENDING')
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            pending = cursor.fetchall()
            if pending:
                print(f"\nFound {len(pending)} pending transactions:\n")
                for txn in pending:
                    print(f"  Order ID: {txn['order_id']}")
                    print(f"    - Transaction ID: {txn['txn_id']}")
                    print(f"    - Status: {txn['status']}")
                    print(f"    - Amount: ₹{txn['amount']}")
                    print(f"    - Created: {txn['created_at']}")
                    print()
            else:
                print("\n✓ No pending transactions")
                
    finally:
        conn.close()
    
    print("\n" + "="*80)
    print("💡 NEXT STEPS:")
    print("="*80)
    print("1. Check your server logs for the callback details:")
    print("   sudo journalctl -u orchpay-backend -n 100 --no-pager")
    print()
    print("2. Look for lines containing:")
    print("   - 'VIYONAPAY Payin Callback Received'")
    print("   - 'Order ID:'")
    print("   - 'Transaction not found'")
    print()
    print("3. The logs will show what order_id ViyonaPay is sending")
    print()
    print("4. Compare that with the order_id values shown above")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
