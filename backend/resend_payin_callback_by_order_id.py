#!/usr/bin/env python3
"""
Script to resend a payin callback to the merchant using order_id
"""

import sys
import argparse
import json
import requests
from datetime import datetime
from database import get_db_connection

def resend_payin_callback(order_id, dry_run=False):
    """
    Find the payin transaction by order_id and resend its callback
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
                    txn_id, order_id, status, amount, bank_ref_no, 
                    pg_txn_id, pg_partner, payment_mode, merchant_id, callback_url
                FROM payin_transactions
                WHERE order_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (order_id,))
            
            txn = cursor.fetchone()
            
            if not txn:
                print(f"❌ No payin transaction found for order_id: {order_id}")
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
                    SELECT payin_callback_url FROM merchant_callbacks
                    WHERE merchant_id = %s AND is_active = TRUE
                """, (merchant_id,))
                
                merchant_callback = cursor.fetchone()
                callback_url = merchant_callback.get('payin_callback_url') if merchant_callback else None
            
            if not callback_url:
                print(f"❌ No callback URL configured for merchant {merchant_id}")
                return
            
            print(f"🔗 Target Callback URL: {callback_url}")

            # 3. Construct the callback payload
            callback_data = {
                'txn_id': txn['txn_id'],
                'order_id': txn['order_id'],
                'status': txn['status'],
                'amount': float(txn['amount']) if txn.get('amount') else 0.0,
                'utr': txn.get('bank_ref_no') or '',
                'pg_txn_id': txn.get('pg_txn_id') or '',
                'pg_partner': txn.get('pg_partner') or '',
                'payment_mode': txn.get('payment_mode') or '',
                'timestamp': datetime.now().isoformat()
            }

            print("\n📦 Callback Payload:")
            print(json.dumps(callback_data, indent=2))

            if dry_run:
                print("\n[DRY RUN MODE] Use --execute to actually send the callback.")
                return

            print("\n🔄 Sending callback...")
            # 4. Forward the callback
            try:
                response = requests.post(
                    callback_url,
                    json=callback_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                
                if response.status_code == 200:
                    print(f"✅ Callback successfully sent! (HTTP {response.status_code})")
                else:
                    print(f"⚠️ Callback sent, but received HTTP {response.status_code}")
                
                print(f"Response: {response.text[:200]}")
                
                # Log callback attempt
                cursor.execute("""
                    INSERT INTO callback_logs 
                    (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (
                    merchant_id,
                    txn['txn_id'],
                    callback_url,
                    json.dumps(callback_data),
                    response.status_code,
                    response.text[:1000]
                ))
                conn.commit()
                print("✅ Logged callback attempt to database.")
                
            except requests.exceptions.RequestException as e:
                print(f"❌ Callback request failed: {e}")
                # Log failed callback attempt
                cursor.execute("""
                    INSERT INTO callback_logs 
                    (merchant_id, txn_id, callback_url, request_data, response_code, response_data, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (
                    merchant_id,
                    txn['txn_id'],
                    callback_url,
                    json.dumps(callback_data),
                    0,
                    str(e)[:1000]
                ))
                conn.commit()
                
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(
        description='Resend a payin callback for a specific transaction using order_id'
    )
    parser.add_argument('--order-id', required=True, help='The order_id of the payin transaction')
    parser.add_argument('--execute', action='store_true', help='Execute the callback (default is dry-run)')
    
    args = parser.parse_args()
    dry_run = not args.execute

    if dry_run:
        print("="*60)
        print("RUNNING IN DRY-RUN MODE - Callback will NOT be sent")
        print("="*60)
        
    resend_payin_callback(order_id=args.order_id, dry_run=dry_run)

if __name__ == '__main__':
    main()
