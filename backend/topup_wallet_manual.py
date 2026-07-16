#!/usr/bin/env python3
"""
Manual Wallet Top-up Script
Allows manual top-up of admin wallet and merchant settled wallet
"""

import sys
import os
from datetime import datetime
from decimal import Decimal

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
from wallet_service import wallet_service


def print_header(title):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_section(title):
    """Print formatted section"""
    print(f"\n{title}")
    print("-" * 80)


def get_admin_wallet_info():
    """Get current admin wallet information"""
    wallet = wallet_service.get_admin_wallet('admin')
    if wallet:
        print_section("📊 Current Admin Wallet Status")
        print(f"  Main Balance: ₹{float(wallet.get('main_balance', 0)):,.2f}")
        print(f"  Total Credits: ₹{float(wallet.get('total_credit', 0)):,.2f}")
        print(f"  Total Debits: ₹{float(wallet.get('total_debit', 0)):,.2f}")
        return wallet
    return None


def get_merchant_wallet_info(merchant_id):
    """Get current merchant wallet information"""
    wallet = wallet_service.get_merchant_wallet(merchant_id)
    if wallet:
        print_section(f"📊 Current Merchant Wallet Status ({merchant_id})")
        print(f"  Main Balance: ₹{float(wallet.get('main_balance', 0)):,.2f}")
        print(f"  Settled Balance: ₹{float(wallet.get('settled_balance', 0)):,.2f}")
        print(f"  Unsettled Balance: ₹{float(wallet.get('unsettled_balance', 0)):,.2f}")
        print(f"  Total Balance: ₹{float(wallet.get('balance', 0)):,.2f}")
        return wallet
    return None


def topup_admin_wallet():
    """Top-up admin wallet"""
    print_header("💰 TOP-UP ADMIN WALLET")
    
    # Show current balance
    get_admin_wallet_info()
    
    # Get amount
    print_section("Enter Top-up Details")
    try:
        amount = float(input("  Enter amount to top-up (₹): "))
        if amount <= 0:
            print("  ❌ Amount must be greater than 0")
            return False
        
        description = input("  Enter description/reason: ").strip()
        if not description:
            description = "Manual top-up"
        
        reference_id = input("  Enter reference ID (optional): ").strip()
        
        # Confirm
        print_section("Confirmation")
        print(f"  Amount: ₹{amount:,.2f}")
        print(f"  Description: {description}")
        if reference_id:
            print(f"  Reference ID: {reference_id}")
        
        confirm = input("\n  Proceed with top-up? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("  ❌ Top-up cancelled")
            return False
        
        # Process top-up
        print_section("Processing...")
        result = wallet_service.credit_admin_wallet(
            admin_id='admin',
            amount=amount,
            description=description,
            reference_id=reference_id if reference_id else None
        )
        
        if result['success']:
            print(f"  ✅ Top-up successful!")
            print(f"  Transaction ID: {result['txn_id']}")
            print(f"  Balance Before: ₹{result['balance_before']:,.2f}")
            print(f"  Balance After: ₹{result['balance_after']:,.2f}")
            
            # Show updated balance
            get_admin_wallet_info()
            return True
        else:
            print(f"  ❌ Top-up failed: {result['message']}")
            return False
            
    except ValueError:
        print("  ❌ Invalid amount entered")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def topup_merchant_settled_wallet():
    """Top-up merchant settled wallet"""
    print_header("💰 TOP-UP MERCHANT SETTLED WALLET")
    
    # Get merchant ID
    print_section("Enter Merchant Details")
    merchant_id = input("  Enter merchant ID: ").strip()
    if not merchant_id:
        print("  ❌ Merchant ID is required")
        return False
    
    # Show current balance
    wallet = get_merchant_wallet_info(merchant_id)
    if not wallet:
        print(f"  ❌ Merchant '{merchant_id}' not found")
        return False
    
    # Get amount
    print_section("Enter Top-up Details")
    try:
        amount = float(input("  Enter amount to top-up (₹): "))
        if amount <= 0:
            print("  ❌ Amount must be greater than 0")
            return False
        
        description = input("  Enter description/reason: ").strip()
        if not description:
            description = "Manual settled wallet top-up"
        
        reference_id = input("  Enter reference ID (optional): ").strip()
        
        # Confirm
        print_section("Confirmation")
        print(f"  Merchant ID: {merchant_id}")
        print(f"  Amount: ₹{amount:,.2f}")
        print(f"  Description: {description}")
        if reference_id:
            print(f"  Reference ID: {reference_id}")
        
        confirm = input("\n  Proceed with top-up? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("  ❌ Top-up cancelled")
            return False
        
        # Process top-up - credit settled wallet
        print_section("Processing...")
        
        conn = get_db_connection()
        if not conn:
            print("  ❌ Database connection failed")
            return False
        
        try:
            with conn.cursor() as cursor:
                # Get current settled balance
                cursor.execute("""
                    SELECT settled_balance FROM merchant_wallet WHERE merchant_id = %s
                """, (merchant_id,))
                wallet_row = cursor.fetchone()
                
                if not wallet_row:
                    print(f"  ❌ Merchant wallet not found")
                    return False
                
                balance_before = float(wallet_row['settled_balance'])
                balance_after = balance_before + amount
                
                # Update settled balance
                cursor.execute("""
                    UPDATE merchant_wallet 
                    SET settled_balance = %s,
                        balance = balance + %s,
                        last_updated = NOW()
                    WHERE merchant_id = %s
                """, (balance_after, amount, merchant_id))
                
                # Record transaction
                txn_id = wallet_service.generate_txn_id('MWT')
                cursor.execute("""
                    INSERT INTO merchant_wallet_transactions 
                    (merchant_id, txn_id, txn_type, amount, balance_before, balance_after, 
                     description, reference_id, created_at)
                    VALUES (%s, %s, 'CREDIT_SETTLED', %s, %s, %s, %s, %s, NOW())
                """, (merchant_id, txn_id, amount, balance_before, balance_after, 
                      description, reference_id if reference_id else None))
                
                conn.commit()
                
                print(f"  ✅ Top-up successful!")
                print(f"  Transaction ID: {txn_id}")
                print(f"  Settled Balance Before: ₹{balance_before:,.2f}")
                print(f"  Settled Balance After: ₹{balance_after:,.2f}")
                
                # Show updated balance
                get_merchant_wallet_info(merchant_id)
                return True
                
        except Exception as e:
            conn.rollback()
            print(f"  ❌ Error: {e}")
            return False
        finally:
            conn.close()
            
    except ValueError:
        print("  ❌ Invalid amount entered")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def view_admin_wallet():
    """View admin wallet details"""
    print_header("👁️  VIEW ADMIN WALLET")
    get_admin_wallet_info()
    
    # Show recent transactions
    print_section("Recent Transactions")
    try:
        transactions = wallet_service.get_admin_transactions('admin', {'limit': 10})
        if transactions:
            for txn in transactions:
                print(f"  {txn['created_at']} | {txn['txn_type']:6} | ₹{float(txn['amount']):>10,.2f} | {txn['description']}")
        else:
            print("  No transactions found")
    except Exception as e:
        print(f"  Error fetching transactions: {e}")


def view_merchant_wallet():
    """View merchant wallet details"""
    print_header("👁️  VIEW MERCHANT WALLET")
    
    merchant_id = input("  Enter merchant ID: ").strip()
    if not merchant_id:
        print("  ❌ Merchant ID is required")
        return
    
    get_merchant_wallet_info(merchant_id)
    
    # Show recent transactions
    print_section("Recent Transactions")
    try:
        transactions = wallet_service.get_merchant_transactions(merchant_id, {'limit': 10})
        if transactions:
            for txn in transactions:
                print(f"  {txn['created_at']} | {txn['txn_type']:15} | ₹{float(txn['amount']):>10,.2f} | {txn['description']}")
        else:
            print("  No transactions found")
    except Exception as e:
        print(f"  Error fetching transactions: {e}")


def main_menu():
    """Display main menu"""
    print_header("🏦 WALLET MANAGEMENT - MANUAL TOP-UP TOOL")
    print("""
  1. Top-up Admin Wallet
  2. Top-up Merchant Settled Wallet
  3. View Admin Wallet
  4. View Merchant Wallet
  5. Exit
    """)


def main():
    """Main function"""
    while True:
        main_menu()
        choice = input("  Select option (1-5): ").strip()
        
        if choice == '1':
            topup_admin_wallet()
        elif choice == '2':
            topup_merchant_settled_wallet()
        elif choice == '3':
            view_admin_wallet()
        elif choice == '4':
            view_merchant_wallet()
        elif choice == '5':
            print("\n  👋 Goodbye!\n")
            break
        else:
            print("  ❌ Invalid option. Please try again.")
        
        input("\n  Press Enter to continue...")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  ⚠️  Script interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n  ❌ Fatal error: {e}")
        sys.exit(1)
