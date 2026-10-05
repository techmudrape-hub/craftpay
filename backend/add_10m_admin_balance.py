#!/usr/bin/env python3
"""
Script to precisely add 10,000,000 to the admin wallet balance.
This checks the current balance first, then updates it by adding 10,000,000,
which allows you to approve fund requests on the top-up page.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
from datetime import datetime

def add_ten_million_balance():
    amount_to_add = 10000000.0
    
    print("\n" + "=" * 80)
    print(f"ADD ₹{amount_to_add:,.2f} TO ADMIN WALLET BALANCE")
    print("=" * 80)
    
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ Database connection failed")
            return False
        
        with conn.cursor() as cursor:
            # 1. Check current balance
            print("\n1. Calculating current admin balance...")
            
            # PayIN amount (credits)
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0) as total_payin
                FROM payin_transactions
                WHERE status = 'SUCCESS'
            """)
            total_payin = float(cursor.fetchone()['total_payin'])
            
            # Approved fund requests (debits)
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0) as total_topup
                FROM fund_requests
                WHERE status = 'APPROVED'
            """)
            total_topup = float(cursor.fetchone()['total_topup'])
            
            # Fetch from merchants (credits)
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0) as total_fetch
                FROM merchant_wallet_transactions
                WHERE txn_type = 'DEBIT' 
                AND description LIKE '%fetched by admin%'
            """)
            total_fetch = float(cursor.fetchone()['total_fetch'])
            
            # Admin payouts (debits)
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0) as total_payout
                FROM payout_transactions
                WHERE status IN ('SUCCESS', 'QUEUED')
                AND reference_id LIKE 'ADMIN%'
            """)
            total_payout = float(cursor.fetchone()['total_payout'])
            
            # Calculate current balance
            current_balance = total_payin + total_fetch - total_topup - total_payout
            target_amount = current_balance + amount_to_add
            
            print(f"   Current Balance: ₹{current_balance:,.2f}")
            print(f"   Amount to Add:   ₹{amount_to_add:,.2f}")
            print(f"   New Target:      ₹{target_amount:,.2f}")
            
            # 2. Create a manual PayIN transaction to reflect the credit
            print("\n2. Creating manual PayIN transaction for credit...")
            
            txn_id = f"PAYIN{datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}"
            order_id = f"ORDER{datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}"
            
            cursor.execute("SET FOREIGN_KEY_CHECKS=0;")
            cursor.execute("""
                INSERT INTO payin_transactions 
                (txn_id, merchant_id, order_id, amount, charge_amount, net_amount, 
                 status, pg_partner, created_at)
                VALUES (%s, 'ADMIN_CREDIT', %s, %s, 0.00, %s, 'SUCCESS', 'MANUAL', NOW())
            """, (txn_id, order_id, amount_to_add, amount_to_add))
            cursor.execute("SET FOREIGN_KEY_CHECKS=1;")
            
            print(f"   ✓ Created PayIN transaction: {txn_id}")
            
            # 3. Record in admin wallet transactions
            print("\n3. Recording admin wallet transaction...")
            
            awt_id = f"AWT{datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}"
            
            cursor.execute("SET FOREIGN_KEY_CHECKS=0;")
            cursor.execute("""
                INSERT INTO admin_wallet_transactions 
                (admin_id, txn_id, txn_type, amount, balance_before, balance_after, 
                 description, reference_id, created_at)
                VALUES ('admin', %s, 'CREDIT', %s, %s, %s, %s, %s, NOW())
            """, (awt_id, amount_to_add, current_balance, target_amount, 
                  f"Manual balance addition of ₹{amount_to_add:,.2f}", txn_id))
            cursor.execute("SET FOREIGN_KEY_CHECKS=1;")
            
            print(f"   ✓ Recorded admin wallet transaction: {awt_id}")
            
            conn.commit()
            
            print("\n" + "=" * 80)
            print("✅ SUCCESS - Admin wallet balance updated")
            print("=" * 80)
            print(f"\nOld Balance:  ₹{current_balance:,.2f}")
            print(f"New Balance:  ₹{target_amount:,.2f}")
            print(f"Amount Added: ₹{amount_to_add:,.2f}")
            print("\nYou can now approve fund requests up to this amount!")
            
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    print(f"\nYou are about to ADD ₹10,000,000.00 to the admin wallet balance.")
    
    confirm = input("\nProceed? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Cancelled")
        sys.exit(0)
    
    success = add_ten_million_balance()
    sys.exit(0 if success else 1)
