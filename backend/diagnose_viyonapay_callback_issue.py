#!/usr/bin/env python3
"""
Diagnose ViyonaPay Callback "Transaction not found" Issue
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
import json

def diagnose_callback_issue():
    """Diagnose why ViyonaPay callback returns 'Transaction not found'"""
    
    print("\n" + "="*80)
    print("🔍 VIYONAPAY CALLBACK DIAGNOSTIC")
    print("="*80)
    
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        with conn.cursor() as cursor:
            # Check recent ViyonaPay transactions
            print("\n1️⃣  Checking recent ViyonaPay transactions...")
            print("-" * 80)
            
            cursor.execute("""
                SELECT 
                    txn_id,
                    order_id,
                    merchant_id,
                    pg_partner,
                    status,
                    amount,
                    created_at
                FROM payin_transactions
                WHERE pg_partner LIKE '%VIYONA%'
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            transactions = cursor.fetchall()
            
            if not transactions:
                print("❌ No ViyonaPay transactions found in database")
                print("\n💡 Possible issues:")
                print("   - Transactions are being created with wrong pg_partner value")
                print("   - No ViyonaPay transactions have been created yet")
                return
            
            print(f"✅ Found {len(transactions)} recent ViyonaPay transaction(s):\n")
            
            for txn in transactions:
                print(f"  Order ID: {txn['order_id']}")
                print(f"  TXN ID: {txn['txn_id']}")
                print(f"  PG Partner: {txn['pg_partner']}")
                print(f"  Status: {txn['status']}")
                print(f"  Amount: ₹{txn['amount']}")
                print(f"  Created: {txn['created_at']}")
                print()
            
            # Check callback logs
            print("\n2️⃣  Checking callback logs...")
            print("-" * 80)
            
            cursor.execute("""
                SELECT 
                    callback_url,
                    request_data,
                    response_code,
                    response_data,
                    created_at
                FROM callback_logs
                WHERE callback_url LIKE '%viyonapay%'
                   OR request_data LIKE '%VIYONAPAY%'
                   OR request_data LIKE '%viyonapay%'
                ORDER BY created_at DESC
                LIMIT 5
            """)
            
            callbacks = cursor.fetchall()
            
            if callbacks:
                print(f"✅ Found {len(callbacks)} callback log(s):\n")
                for cb in callbacks:
                    print(f"  URL: {cb['callback_url']}")
                    print(f"  Response Code: {cb['response_code']}")
                    print(f"  Response: {cb['response_data'][:100]}")
                    print(f"  Time: {cb['created_at']}")
                    print()
            else:
                print("⚠️  No callback logs found")
            
            # Check for transactions with wrong pg_partner
            print("\n3️⃣  Checking for potential pg_partner mismatches...")
            print("-" * 80)
            
            cursor.execute("""
                SELECT DISTINCT pg_partner, COUNT(*) as count
                FROM payin_transactions
                GROUP BY pg_partner
                ORDER BY count DESC
            """)
            
            partners = cursor.fetchall()
            
            print("PG Partners in database:")
            for p in partners:
                marker = "✓" if 'VIYONA' in p['pg_partner'] else " "
                print(f"  {marker} {p['pg_partner']}: {p['count']} transactions")
            
            # Provide recommendations
            print("\n" + "="*80)
            print("💡 DIAGNOSTIC RESULTS")
            print("="*80)
            
            viyona_txns = [t for t in transactions if 'VIYONA' in t['pg_partner']]
            
            if not viyona_txns:
                print("\n❌ ISSUE FOUND: No transactions with VIYONAPAY pg_partner")
                print("\n🔧 SOLUTION:")
                print("   Check your ViyonaPay service/routes to ensure pg_partner is set to:")
                print("   - 'VIYONAPAY' (for Truaxis)")
                print("   - 'VIYONAPAY_BARRINGER' (for Barringer)")
            else:
                print("\n✅ ViyonaPay transactions exist with correct pg_partner")
                print("\n🔍 Next steps:")
                print("   1. Decrypt the callback payload to see the order_id ViyonaPay is sending")
                print("   2. Compare with order_id in your database")
                print("   3. Check if order_id format matches")
                
                print("\n📋 Sample order_ids in database:")
                for txn in viyona_txns[:3]:
                    print(f"   - {txn['order_id']}")
    
    finally:
        conn.close()

if __name__ == '__main__':
    diagnose_callback_issue()
