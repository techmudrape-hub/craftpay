"""
Diagnostic script to check ClocksPay callback forwarding
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
import json
from datetime import datetime, timedelta

def check_recent_clockspay_transactions():
    """Check recent ClocksPay transactions"""
    print("=" * 80)
    print("CHECKING RECENT CLOCKSPAY TRANSACTIONS")
    print("=" * 80)
    
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        with conn.cursor() as cursor:
            # Get recent ClocksPay transactions
            cursor.execute("""
                SELECT 
                    txn_id,
                    merchant_id,
                    order_id,
                    amount,
                    status,
                    callback_url,
                    created_at,
                    completed_at
                FROM payin_transactions
                WHERE pg_partner = 'CLOCKSPAY'
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            transactions = cursor.fetchall()
            
            if not transactions:
                print("\n⚠ No ClocksPay transactions found")
                return
            
            print(f"\nFound {len(transactions)} recent ClocksPay transactions:\n")
            
            for txn in transactions:
                print(f"Transaction: {txn['txn_id']}")
                print(f"  Merchant ID: {txn['merchant_id']}")
                print(f"  Order ID: {txn['order_id']}")
                print(f"  Amount: ₹{txn['amount']}")
                print(f"  Status: {txn['status']}")
                print(f"  Callback URL in txn: {txn['callback_url'] if txn['callback_url'] else 'NOT SET'}")
                print(f"  Created: {txn['created_at']}")
                print(f"  Completed: {txn['completed_at'] if txn['completed_at'] else 'N/A'}")
                
                # Check merchant callback configuration
                if txn['merchant_id']:
                    cursor.execute("""
                        SELECT payin_callback_url 
                        FROM merchant_callbacks
                        WHERE merchant_id = %s
                    """, (txn['merchant_id'],))
                    
                    merchant_callback = cursor.fetchone()
                    if merchant_callback:
                        print(f"  Merchant callback URL: {merchant_callback['payin_callback_url'] if merchant_callback['payin_callback_url'] else 'NOT SET'}")
                    else:
                        print(f"  Merchant callback: NO ENTRY IN merchant_callbacks TABLE")
                
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
                    LIMIT 5
                """, (txn['txn_id'],))
                
                callback_logs = cursor.fetchall()
                
                if callback_logs:
                    print(f"  Callback Attempts: {len(callback_logs)}")
                    for i, log in enumerate(callback_logs, 1):
                        print(f"    Attempt {i}:")
                        print(f"      URL: {log['callback_url']}")
                        print(f"      Response Code: {log['response_code']}")
                        print(f"      Time: {log['created_at']}")
                        
                        # Parse request data
                        try:
                            request_data = json.loads(log['request_data'])
                            print(f"      Request Status: {request_data.get('status')}")
                            print(f"      Request Amount: {request_data.get('amount')}")
                        except:
                            pass
                        
                        # Show response
                        if log['response_code'] == 0:
                            print(f"      Error: {log['response_data'][:100]}")
                        else:
                            print(f"      Response: {log['response_data'][:100]}")
                else:
                    print(f"  ⚠ NO CALLBACK LOGS FOUND - Callback was NOT forwarded!")
                
                print()
    
    finally:
        conn.close()

def check_merchant_callback_config():
    """Check merchant callback configurations"""
    print("=" * 80)
    print("CHECKING MERCHANT CALLBACK CONFIGURATIONS")
    print("=" * 80)
    
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        with conn.cursor() as cursor:
            # Get merchants with ClocksPay transactions
            cursor.execute("""
                SELECT DISTINCT 
                    pt.merchant_id,
                    m.full_name,
                    m.email
                FROM payin_transactions pt
                JOIN merchants m ON pt.merchant_id = m.merchant_id
                WHERE pt.pg_partner = 'CLOCKSPAY'
            """)
            
            merchants = cursor.fetchall()
            
            if not merchants:
                print("\n⚠ No merchants with ClocksPay transactions found")
                return
            
            print(f"\nFound {len(merchants)} merchants with ClocksPay transactions:\n")
            
            for merchant in merchants:
                print(f"Merchant: {merchant['merchant_id']}")
                print(f"  Name: {merchant['full_name']}")
                print(f"  Email: {merchant['email']}")
                
                # Check callback configuration
                cursor.execute("""
                    SELECT 
                        payin_callback_url,
                        payout_callback_url,
                        created_at,
                        updated_at
                    FROM merchant_callbacks
                    WHERE merchant_id = %s
                """, (merchant['merchant_id'],))
                
                callback_config = cursor.fetchone()
                
                if callback_config:
                    print(f"  Payin Callback URL: {callback_config['payin_callback_url'] if callback_config['payin_callback_url'] else '❌ NOT SET'}")
                    print(f"  Payout Callback URL: {callback_config['payout_callback_url'] if callback_config['payout_callback_url'] else 'NOT SET'}")
                    print(f"  Config Updated: {callback_config['updated_at']}")
                else:
                    print(f"  ❌ NO CALLBACK CONFIGURATION FOUND")
                    print(f"  Action Required: Add entry to merchant_callbacks table")
                
                print()
    
    finally:
        conn.close()

def simulate_callback_check(order_id):
    """Simulate what happens when a callback is received"""
    print("=" * 80)
    print(f"SIMULATING CALLBACK CHECK FOR ORDER: {order_id}")
    print("=" * 80)
    
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        with conn.cursor() as cursor:
            # Find transaction
            cursor.execute("""
                SELECT 
                    txn_id,
                    merchant_id,
                    order_id,
                    amount,
                    status,
                    callback_url,
                    net_amount,
                    charge_amount
                FROM payin_transactions
                WHERE order_id = %s AND pg_partner = 'CLOCKSPAY'
            """, (order_id,))
            
            txn = cursor.fetchone()
            
            if not txn:
                print(f"\n❌ Transaction not found for order_id: {order_id}")
                return
            
            print(f"\n✅ Transaction Found:")
            print(f"  TXN ID: {txn['txn_id']}")
            print(f"  Merchant ID: {txn['merchant_id']}")
            print(f"  Status: {txn['status']}")
            print(f"  Amount: ₹{txn['amount']}")
            
            print(f"\n📋 Callback URL Resolution:")
            
            # Step 1: Check transaction callback_url
            callback_url = None
            if txn.get('callback_url'):
                callback_url = txn['callback_url'].strip()
                if callback_url:
                    print(f"  ✅ Step 1: Found in transaction: {callback_url}")
                else:
                    print(f"  ❌ Step 1: Empty in transaction")
            else:
                print(f"  ❌ Step 1: Not set in transaction")
            
            # Step 2: Check merchant_callbacks table
            if not callback_url and txn['merchant_id']:
                cursor.execute("""
                    SELECT payin_callback_url 
                    FROM merchant_callbacks
                    WHERE merchant_id = %s
                """, (txn['merchant_id'],))
                
                merchant_callback = cursor.fetchone()
                if merchant_callback and merchant_callback.get('payin_callback_url'):
                    callback_url = merchant_callback['payin_callback_url'].strip()
                    if callback_url:
                        print(f"  ✅ Step 2: Found in merchant_callbacks: {callback_url}")
                    else:
                        print(f"  ❌ Step 2: Empty in merchant_callbacks")
                else:
                    print(f"  ❌ Step 2: Not found in merchant_callbacks")
            
            print(f"\n🎯 Final Result:")
            if callback_url:
                print(f"  ✅ Callback URL: {callback_url}")
                print(f"  ✅ Callback WILL BE forwarded")
                
                # Show what would be sent
                print(f"\n📦 Callback Data (MAXPE Format):")
                callback_data = {
                    'txn_id': txn['txn_id'],
                    'order_id': txn['order_id'],
                    'status': txn['status'],
                    'utr': 'UTR_EXAMPLE',
                    'pg_partner': 'CLOCKSPAY',
                    'amount': float(txn['amount']),
                    'net_amount': float(txn['net_amount']),
                    'charge_amount': float(txn['charge_amount'])
                }
                print(json.dumps(callback_data, indent=2))
            else:
                print(f"  ❌ No callback URL found")
                print(f"  ❌ Callback will NOT be forwarded")
                print(f"\n💡 Solution:")
                print(f"     Add callback URL to merchant_callbacks table:")
                print(f"     INSERT INTO merchant_callbacks (merchant_id, payin_callback_url)")
                print(f"     VALUES ('{txn['merchant_id']}', 'https://merchant.com/callback')")
    
    finally:
        conn.close()

if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("CLOCKSPAY CALLBACK DIAGNOSTIC TOOL")
    print("=" * 80 + "\n")
    
    # Check recent transactions
    check_recent_clockspay_transactions()
    
    print("\n")
    
    # Check merchant configurations
    check_merchant_callback_config()
    
    print("\n")
    
    # Simulate callback for specific order
    print("Enter order_id to simulate callback check (or press Enter to skip): ", end='')
    order_id = input().strip()
    
    if order_id:
        print()
        simulate_callback_check(order_id)
    
    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)
