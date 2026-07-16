#!/usr/bin/env python3
"""
Add 100,000 to merchant's unsettled balance
"""

import pymysql
from config import Config
import sys
from datetime import datetime

def add_unsettled_balance(merchant_id, amount=100000.00):
    """Add balance to merchant's unsettled wallet"""
    try:
        connection = pymysql.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            # Check if merchant exists
            cursor.execute("SELECT merchant_id, full_name FROM merchants WHERE merchant_id = %s", (merchant_id,))
            merchant = cursor.fetchone()
            
            if not merchant:
                print(f"❌ Merchant {merchant_id} not found!")
                return False
            
            print(f"Merchant: {merchant['full_name']} ({merchant_id})")
            print("=" * 80)
            
            # Get current balance
            cursor.execute("""
                SELECT unsettled_balance, main_balance, settled_balance 
                FROM merchant_wallet 
                WHERE merchant_id = %s
            """, (merchant_id,))
            wallet = cursor.fetchone()
            
            if not wallet:
                print(f"❌ Wallet not found for merchant {merchant_id}")
                print("Creating wallet entry...")
                
                # Create wallet if it doesn't exist
                cursor.execute("""
                    INSERT INTO merchant_wallet 
                    (merchant_id, balance, main_balance, unsettled_balance, settled_balance, last_updated)
                    VALUES (%s, %s, 0, %s, 0, CURRENT_TIMESTAMP)
                """, (merchant_id, amount, amount))
                
                print(f"✅ Created wallet with unsettled balance: ₹{amount:,.2f}")
                
                # Create transaction record
                cursor.execute("""
                    INSERT INTO merchant_wallet_transactions 
                    (merchant_id, transaction_type, amount, balance_before, balance_after, 
                     description, txn_type, created_by, reference_id)
                    VALUES (%s, 'CREDIT', %s, 0, %s, %s, 'CREDIT', 'SYSTEM', %s)
                """, (
                    merchant_id, amount, amount,
                    f'Manual credit for testing - Added ₹{amount:,.2f} to unsettled balance',
                    f'MANUAL_CREDIT_{datetime.now().strftime("%Y%m%d%H%M%S")}'
                ))
                
            else:
                current_unsettled = float(wallet['unsettled_balance'])
                current_main = float(wallet['main_balance'])
                current_settled = float(wallet['settled_balance'])
                
                new_unsettled = current_unsettled + amount
                new_main = current_main + amount
                
                print(f"\nCurrent Balances:")
                print(f"  Unsettled Balance: ₹{current_unsettled:,.2f}")
                print(f"  Main Balance: ₹{current_main:,.2f}")
                print(f"  Settled Balance: ₹{current_settled:,.2f}")
                print(f"\nAdding: ₹{amount:,.2f}")
                print(f"\nNew Balances:")
                print(f"  Unsettled Balance: ₹{new_unsettled:,.2f}")
                print(f"  Main Balance: ₹{new_main:,.2f}")
                print(f"  Settled Balance: ₹{current_settled:,.2f}")
                
                # Update balance
                cursor.execute("""
                    UPDATE merchant_wallet 
                    SET unsettled_balance = %s,
                        balance = %s,
                        main_balance = %s,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE merchant_id = %s
                """, (new_unsettled, new_main, new_main, merchant_id))
                
                # Create transaction record
                cursor.execute("""
                    INSERT INTO merchant_wallet_transactions 
                    (merchant_id, transaction_type, amount, balance_before, balance_after, 
                     description, txn_type, created_by, reference_id)
                    VALUES (%s, 'CREDIT', %s, %s, %s, %s, 'CREDIT', 'SYSTEM', %s)
                """, (
                    merchant_id, amount, current_unsettled, new_unsettled,
                    f'Manual credit for testing - Added ₹{amount:,.2f} to unsettled balance',
                    f'MANUAL_CREDIT_{datetime.now().strftime("%Y%m%d%H%M%S")}'
                ))
                
                print(f"\n✅ Successfully added ₹{amount:,.2f} to unsettled balance")
            
        connection.commit()
        connection.close()
        
        print("\n" + "=" * 80)
        print("✅ Transaction completed successfully!")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def list_merchants():
    """List all active merchants"""
    try:
        connection = pymysql.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT m.merchant_id, m.full_name, m.email, 
                       COALESCE(mw.unsettled_balance, 0) as unsettled_balance
                FROM merchants m
                LEFT JOIN merchant_wallet mw ON m.merchant_id = mw.merchant_id
                WHERE m.is_active = TRUE
                ORDER BY m.merchant_id
            """)
            merchants = cursor.fetchall()
            
            print("\nActive Merchants:")
            print("=" * 100)
            print(f"{'Merchant ID':<15} {'Name':<30} {'Email':<35} {'Unsettled Balance':>15}")
            print("=" * 100)
            
            for merchant in merchants:
                unsettled = float(merchant['unsettled_balance'])
                print(f"{merchant['merchant_id']:<15} {merchant['full_name']:<30} {merchant['email']:<35} ₹{unsettled:>13,.2f}")
            
            print("=" * 100)
            print(f"Total merchants: {len(merchants)}")
        
        connection.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("=" * 80)
        print("Add Unsettled Balance to Merchant Wallet")
        print("=" * 80)
        print("\nUsage:")
        print("  python3 add_unsettled_balance.py <merchant_id> [amount]")
        print("  python3 add_unsettled_balance.py list")
        print("\nExamples:")
        print("  python3 add_unsettled_balance.py MERCH001")
        print("  python3 add_unsettled_balance.py MERCH001 100000")
        print("  python3 add_unsettled_balance.py MERCH001 50000")
        print("  python3 add_unsettled_balance.py list")
        print("\nDefault amount: ₹100,000.00")
        print("=" * 80)
        sys.exit(1)
    
    if sys.argv[1].lower() == 'list':
        list_merchants()
    else:
        merchant_id = sys.argv[1]
        amount = float(sys.argv[2]) if len(sys.argv) > 2 else 100000.00
        
        print("\n" + "=" * 80)
        print("Add Unsettled Balance to Merchant Wallet")
        print("=" * 80)
        
        add_unsettled_balance(merchant_id, amount)
