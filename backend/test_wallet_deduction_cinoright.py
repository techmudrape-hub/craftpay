"""
Test Wallet Deduction for Cinoright Callback
This script simulates what should happen when a SUCCESS callback is received
"""

from database import get_db_connection
from wallet_service import WalletService
import json

def test_wallet_deduction():
    """Test wallet deduction for a recent Cinoright transaction"""
    
    print("=" * 80)
    print("CINORIGHT WALLET DEDUCTION TEST")
    print("=" * 80)
    
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        with conn.cursor() as cursor:
            # Get the most recent SUCCESS Cinoright transaction
            cursor.execute("""
                SELECT 
                    txn_id,
                    reference_id,
                    merchant_id,
                    amount,
                    status,
                    pg_txn_id,
                    utr,
                    created_at,
                    updated_at
                FROM payout_transactions
                WHERE pg_partner = 'CINORIGHT'
                AND status = 'SUCCESS'
                ORDER BY updated_at DESC
                LIMIT 1
            """)
            
            txn = cursor.fetchone()
            
            if not txn:
                print("⚠ No SUCCESS Cinoright transactions found")
                print("\nLet's check all recent Cinoright transactions:")
                
                cursor.execute("""
                    SELECT 
                        txn_id,
                        reference_id,
                        merchant_id,
                        amount,
                        status,
                        created_at
                    FROM payout_transactions
                    WHERE pg_partner = 'CINORIGHT'
                    ORDER BY created_at DESC
                    LIMIT 5
                """)
                
                all_txns = cursor.fetchall()
                for t in all_txns:
                    print(f"\nTXN: {t['txn_id']}")
                    print(f"  Ref: {t['reference_id']}")
                    print(f"  Merchant: {t['merchant_id']}")
                    print(f"  Amount: ₹{t['amount']}")
                    print(f"  Status: {t['status']}")
                    print(f"  Created: {t['created_at']}")
                
                return
            
            print(f"\nFound SUCCESS transaction:")
            print(f"  TXN ID: {txn['txn_id']}")
            print(f"  Reference ID: {txn['reference_id']}")
            print(f"  Merchant ID: {txn['merchant_id']}")
            print(f"  Amount: ₹{txn['amount']}")
            print(f"  Status: {txn['status']}")
            print(f"  PG TXN ID: {txn['pg_txn_id']}")
            print(f"  UTR: {txn['utr']}")
            print(f"  Created: {txn['created_at']}")
            print(f"  Updated: {txn['updated_at']}")
            
            if not txn['merchant_id']:
                print("\n⚠ This is an admin payout (no merchant_id) - wallet deduction not applicable")
                return
            
            # Check if wallet was already deducted
            print("\n" + "-" * 80)
            print("Checking wallet_transactions for deduction:")
            print("-" * 80)
            
            cursor.execute("""
                SELECT 
                    id,
                    merchant_id,
                    txn_type,
                    amount,
                    balance_before,
                    balance_after,
                    description,
                    txn_id,
                    created_at
                FROM wallet_transactions
                WHERE txn_id = %s
                ORDER BY created_at DESC
            """, (txn['txn_id'],))
            
            wallet_txns = cursor.fetchall()
            
            if not wallet_txns:
                print("❌ NO WALLET DEDUCTION FOUND!")
                print(f"   Expected to find a DEBIT transaction with reference_id = {txn['txn_id']}")
                
                # Try to deduct now
                print("\n" + "=" * 80)
                print("ATTEMPTING WALLET DEDUCTION NOW")
                print("=" * 80)
                
                wallet_svc = WalletService()
                
                debit_result = wallet_svc.debit_merchant_wallet(
                    merchant_id=txn['merchant_id'],
                    amount=float(txn['amount']),
                    description=f"Payout completed - Ref: {txn['reference_id']}",
                    reference_id=txn['txn_id']
                )
                
                if debit_result['success']:
                    print(f"✅ WALLET DEBITED SUCCESSFULLY!")
                    print(f"   Balance Before: ₹{debit_result['balance_before']:.2f}")
                    print(f"   Amount Debited: ₹{float(txn['amount']):.2f}")
                    print(f"   Balance After: ₹{debit_result['balance_after']:.2f}")
                else:
                    print(f"❌ WALLET DEDUCTION FAILED!")
                    print(f"   Error: {debit_result['message']}")
                
            else:
                print(f"✅ Found {len(wallet_txns)} wallet transaction(s):")
                
                for wt in wallet_txns:
                    print(f"\n  ID: {wt['id']}")
                    print(f"  Type: {wt['txn_type']}")
                    print(f"  Amount: ₹{wt['amount']}")
                    print(f"  Balance Before: ₹{wt['balance_before']}")
                    print(f"  Balance After: ₹{wt['balance_after']}")
                    print(f"  Description: {wt['description']}")
                    print(f"  Created: {wt['created_at']}")
                
                print("\n✅ Wallet was already deducted for this transaction")
    
    finally:
        conn.close()
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    try:
        test_wallet_deduction()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
