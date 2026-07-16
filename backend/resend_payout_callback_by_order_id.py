#!/usr/bin/env python3
"""
Script to resend a payout callback to the merchant using order_id
"""

import sys
import argparse
import json
from datetime import datetime
from database import get_db_connection
from callback_forwarder import forward_payout_callback

def resend_callback(order_id, dry_run=False):
    """
    Find the payout transaction by order_id and resend its callback
    """
    conn = get_db_connection()
    if not conn:
        print("❌ Could not connect to the database")
        return

    try:
        with conn.cursor() as cursor:
            # 1. Find transaction by order_id
            cursor.execute("""
                SELECT 
                    txn_id, reference_id, order_id, status, utr, 
                    pg_txn_id, pg_partner, amount, merchant_id, callback_url
                FROM payout_transactions
                WHERE order_id = %s OR reference_id = %s
            """, (order_id, order_id))
            
            txn = cursor.fetchone()
            
            if not txn:
                print(f"❌ No payout transaction found for order_id: {order_id}")
                return
            
            print(f"✅ Found transaction: {txn['txn_id']} (Status: {txn['status']})")
            
            merchant_id = txn['merchant_id']
            if not merchant_id:
                print(f"❌ This transaction does not belong to a merchant (merchant_id is null).")
                return

            # 2. Determine the callback URL
            callback_url = txn.get('callback_url')
            
            if not callback_url:
                print(f"ℹ️ No transaction-specific callback URL found. Checking merchant_callbacks table for merchant {merchant_id}...")
                cursor.execute("""
                    SELECT payout_callback_url FROM merchant_callbacks
                    WHERE merchant_id = %s AND is_active = TRUE
                """, (merchant_id,))
                
                merchant_callback = cursor.fetchone()
                callback_url = merchant_callback.get('payout_callback_url') if merchant_callback else None
            
            if not callback_url:
                print(f"❌ No callback URL configured for merchant {merchant_id}")
                return
            
            print(f"🔗 Target Callback URL: {callback_url}")

            # 3. Construct the callback payload
            merchant_callback_data = {
                'txn_id': txn['txn_id'],
                'order_id': txn.get('order_id') or txn.get('reference_id'),
                'reference_id': txn.get('reference_id'),
                'status': txn['status'],
                'utr': txn.get('utr') or '',
                'pg_txn_id': txn.get('pg_txn_id') or '',
                'pg_partner': txn.get('pg_partner') or '',
                'amount': float(txn['amount']) if txn.get('amount') else 0.0,
                'timestamp': datetime.now().isoformat()
            }

            print("\n📦 Callback Payload:")
            print(json.dumps(merchant_callback_data, indent=2))

            if dry_run:
                print("\n[DRY RUN MODE] Use --execute to actually send the callback.")
                return

            print("\n🔄 Sending callback...")
            # 4. Forward the callback
            forward_result = forward_payout_callback(
                txn_id=txn['txn_id'],
                merchant_id=merchant_id,
                callback_url=callback_url,
                callback_data=merchant_callback_data
            )
            
            if forward_result and forward_result.get('success'):
                print(f"✅ Callback successfully sent! (HTTP {forward_result.get('status_code')})")
            else:
                print(f"❌ Callback failed: {forward_result.get('message')}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(
        description='Resend a payout callback for a specific transaction using order_id'
    )
    parser.add_argument('--order-id', required=True, help='The order_id (or reference_id) of the payout transaction')
    parser.add_argument('--execute', action='store_true', help='Execute the callback (default is dry-run)')
    
    args = parser.parse_args()
    dry_run = not args.execute

    if dry_run:
        print("="*60)
        print("RUNNING IN DRY-RUN MODE - Callback will NOT be sent")
        print("="*60)
        
    resend_callback(order_id=args.order_id, dry_run=dry_run)

if __name__ == '__main__':
    main()
