#!/usr/bin/env python3
import pymysql
import sys
import json
from config import Config

def check_payout_callback(order_id):
    try:
        conn = pymysql.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            port=3306,
            cursorclass=pymysql.cursors.DictCursor
        )
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return

    try:
        with conn.cursor() as cursor:
            # 1. Find the payout transaction
            print(f"\n🔍 Searching for Order ID: {order_id}")
            print("-" * 60)
            
            # Checking payout_transactions table
            query = """
                SELECT *
                FROM payout_transactions
                WHERE order_id = %s OR txn_id = %s OR reference_id = %s
            """
            cursor.execute(query, (order_id, order_id, order_id))
            payout = cursor.fetchone()
            
            if not payout:
                print("❌ No payout transaction found with this Order ID.")
                return
                
            print(f"✅ Found Payout Transaction:")
            print(f"  Txn ID:      {payout.get('txn_id')}")
            print(f"  Order ID:    {payout.get('order_id')}")
            print(f"  Merchant ID: {payout.get('merchant_id')}")
            print(f"  PG Partner:  {payout.get('pg_partner')} (SectorPe/PES)")
            print(f"  Status:      {payout.get('status')}")
            print(f"  Amount:      ₹{payout.get('amount')}")
            print(f"  Created At:  {payout.get('created_at')}")
            
            txn_id = payout.get('txn_id')
            merchant_id = payout.get('merchant_id')
            
            # 2. Check the callback logs for this transaction
            print(f"\n🔍 Checking Callback Logs for Txn ID: {txn_id} / Order ID: {order_id}")
            print("-" * 60)
            
            cb_query = """
                SELECT *
                FROM callback_logs
                WHERE txn_id = %s OR request_data LIKE %s
                ORDER BY created_at DESC
            """
            like_order_id = f"%{order_id}%"
            cursor.execute(cb_query, (txn_id, like_order_id))
            callbacks = cursor.fetchall()
            
            if not callbacks:
                print("❌ No callback logs found for this transaction.")
                print("   The merchant callback has NOT been sent or recorded in callback_logs.")
            else:
                print(f"✅ Found {len(callbacks)} Callback Attempt(s):")
                for idx, cb in enumerate(callbacks, 1):
                    print(f"\n  Attempt #{idx}:")
                    print(f"  Time:          {cb.get('created_at')}")
                    print(f"  URL:           {cb.get('callback_url')}")
                    print(f"  Response Code: {cb.get('response_code')}")
                    
                    try:
                        resp_data = json.loads(cb.get('response_data', '{}'))
                        print(f"  Response Data: {json.dumps(resp_data, indent=2)}")
                    except:
                        print(f"  Response Data: {cb.get('response_data')}")
                        
            # 3. Check the merchant's configured callback URL
            print(f"\n🔍 Checking Merchant Configuration")
            print("-" * 60)
            merchant_cb_query = "SELECT payout_callback_url FROM merchant_callbacks WHERE merchant_id = %s"
            cursor.execute(merchant_cb_query, (merchant_id,))
            m_cb = cursor.fetchone()
            if m_cb and m_cb.get('payout_callback_url'):
                print(f"✅ Merchant {merchant_id} has Payout Callback URL configured:")
                print(f"   {m_cb.get('payout_callback_url')}")
            else:
                print(f"⚠️  No payout callback URL is configured for merchant {merchant_id}.")
                print(f"   (This is why the callback wasn't sent, if the list above is empty)")

    finally:
        conn.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 check_payout_callback.py <ORDER_ID>")
        sys.exit(1)
        
    order_id = sys.argv[1]
    check_payout_callback(order_id)
