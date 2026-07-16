#!/usr/bin/env python3
"""
Top up merchant wallet for chargeback testing
"""

import pymysql
from config import Config

def topup_merchant_wallet(merchant_id, amount=5000.00):
    """Add balance to merchant's unsettled wallet for testing"""
    try:
        connection = pymysql.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            # Get current balance
            cursor.execute("""
                SELECT unsettled_balance FROM merchant_wallet 
                WHERE merchant_id = %s
            """, (merchant_id,))
            wallet = cursor.fetchone()
            
            if not wallet:
                print(f"❌ Wallet not found for merchant {merchant_id}")
                return False
            
            current_balance = float(wallet['unsettled_balance'])
            new_balance = current_balance + amount
            
            print(f"Merchant: {merchant_id}")
            print(f"Current unsettled balance: ₹{current_balance:.2f}")
            print(f"Adding: ₹{amount:.2f}")
            print(f"New balance: ₹{new_balance:.2f}")
            
            # Update balance
            cursor.execute("""
                UPDATE merchant_wallet 
                SET unsettled_balance = %s,
                    last_updated = CURRENT_TIMESTAMP
                WHERE merchant_id = %s
            """, (new_balance, merchant_id))
            
            # Create transaction record
            cursor.execute("""
                INSERT INTO merchant_wallet_transactions 
                (merchant_id, transaction_type, amount, balance_before, balance_after, 
                 description, txn_type, created_by)
                VALUES (%s, 'CREDIT', %s, %s, %s, %s, 'CREDIT', 'SYSTEM')
            """, (
                merchant_id, amount, current_balance, new_balance,
                f'Test top-up for chargeback acceptance testing'
            ))
            
        connection.commit()
        connection.close()
        
        print(f"\n✅ Successfully topped up ₹{amount:.2f} to merchant {merchant_id}")
        print(f"✅ New unsettled balance: ₹{new_balance:.2f}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 topup_merchant_for_chargeback_test.py <merchant_id> [amount]")
        print("Example: python3 topup_merchant_for_chargeback_test.py MERCH001 5000")
        sys.exit(1)
    
    merchant_id = sys.argv[1]
    amount = float(sys.argv[2]) if len(sys.argv) > 2 else 5000.00
    
    topup_merchant_wallet(merchant_id, amount)
