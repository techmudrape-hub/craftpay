#!/usr/bin/env python3
"""
Script to delete all chargeback data for a particular merchant/user

This script will delete:
1. Chargeback deductions records
2. Chargeback records
3. Chargeback upload records

WARNING: This operation is IRREVERSIBLE. Use with caution!
"""

import pymysql
from config import Config
import sys

def delete_user_chargeback_data(merchant_id, dry_run=True):
    """
    Delete all chargeback data for a specific merchant
    
    Args:
        merchant_id (str): The merchant ID whose chargeback data should be deleted
        dry_run (bool): If True, only show what would be deleted without actually deleting
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        connection = pymysql.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            # First, verify the merchant exists
            cursor.execute("""
                SELECT merchant_id, full_name, email, mobile 
                FROM merchants 
                WHERE merchant_id = %s
            """, (merchant_id,))
            merchant = cursor.fetchone()
            
            if not merchant:
                print(f"❌ Merchant with ID '{merchant_id}' not found!")
                return False
            
            print("\n" + "="*80)
            print(f"MERCHANT INFORMATION")
            print("="*80)
            print(f"Merchant ID: {merchant['merchant_id']}")
            print(f"Full Name: {merchant['full_name']}")
            print(f"Email: {merchant['email']}")
            print(f"Mobile: {merchant['mobile']}")
            print("="*80 + "\n")
            
            # Get counts of records to be deleted
            print("ANALYZING CHARGEBACK DATA...")
            print("-"*80)
            
            # Count chargeback deductions
            cursor.execute("""
                SELECT COUNT(*) as count, 
                       COALESCE(SUM(deduction_amount), 0) as total_amount
                FROM chargeback_deductions 
                WHERE merchant_id = %s
            """, (merchant_id,))
            deductions_info = cursor.fetchone()
            deductions_count = deductions_info['count']
            deductions_amount = float(deductions_info['total_amount'])
            
            # Count chargebacks
            cursor.execute("""
                SELECT COUNT(*) as count,
                       COALESCE(SUM(chargeback_amount), 0) as total_amount
                FROM chargebacks 
                WHERE merchant_id = %s
            """, (merchant_id,))
            chargebacks_info = cursor.fetchone()
            chargebacks_count = chargebacks_info['count']
            chargebacks_amount = float(chargebacks_info['total_amount'])
            
            # Count chargeback uploads
            cursor.execute("""
                SELECT COUNT(*) as count,
                       COALESCE(SUM(total_records), 0) as total_records
                FROM chargeback_uploads 
                WHERE merchant_id = %s
            """, (merchant_id,))
            uploads_info = cursor.fetchone()
            uploads_count = uploads_info['count']
            uploads_records = uploads_info['total_records']
            
            print(f"📊 Chargeback Deductions: {deductions_count} records (Total: ₹{deductions_amount:,.2f})")
            print(f"📊 Chargebacks: {chargebacks_count} records (Total: ₹{chargebacks_amount:,.2f})")
            print(f"📊 Chargeback Uploads: {uploads_count} uploads ({uploads_records} total records)")
            print("-"*80 + "\n")
            
            if deductions_count == 0 and chargebacks_count == 0 and uploads_count == 0:
                print("✅ No chargeback data found for this merchant.")
                return True
            
            # Show sample records
            if chargebacks_count > 0:
                print("SAMPLE CHARGEBACK RECORDS (First 5):")
                print("-"*80)
                cursor.execute("""
                    SELECT id, transaction_id, order_id, chargeback_amount, 
                           status, acceptance_status, chargeback_date, created_at
                    FROM chargebacks 
                    WHERE merchant_id = %s
                    ORDER BY created_at DESC
                    LIMIT 5
                """, (merchant_id,))
                sample_chargebacks = cursor.fetchall()
                
                for cb in sample_chargebacks:
                    print(f"  ID: {cb['id']} | TXN: {cb['transaction_id']}")
                    print(f"  Amount: ₹{float(cb['chargeback_amount']):,.2f} | Status: {cb['status']} | Acceptance: {cb['acceptance_status']}")
                    print(f"  Date: {cb['chargeback_date']} | Created: {cb['created_at']}")
                    print("-"*80)
            
            if dry_run:
                print("\n" + "="*80)
                print("🔍 DRY RUN MODE - NO DATA WILL BE DELETED")
                print("="*80)
                print("\nTo actually delete the data, run the script with dry_run=False")
                print("Example: delete_user_chargeback_data('MERCHANT_ID', dry_run=False)")
                print("\n⚠️  WARNING: This operation is IRREVERSIBLE!")
                print("="*80 + "\n")
                return True
            
            # Confirm deletion
            print("\n" + "="*80)
            print("⚠️  WARNING: YOU ARE ABOUT TO DELETE ALL CHARGEBACK DATA!")
            print("="*80)
            print(f"This will permanently delete:")
            print(f"  • {deductions_count} chargeback deduction records")
            print(f"  • {chargebacks_count} chargeback records")
            print(f"  • {uploads_count} chargeback upload records")
            print("\n⚠️  THIS OPERATION CANNOT BE UNDONE!")
            print("="*80 + "\n")
            
            confirmation = input("Type 'DELETE' to confirm deletion: ")
            
            if confirmation != 'DELETE':
                print("\n❌ Deletion cancelled. No data was deleted.")
                return False
            
            print("\n🗑️  Starting deletion process...")
            print("-"*80)
            
            # Delete in correct order (respecting foreign key constraints)
            
            # 1. Delete chargeback deductions (has FK to chargebacks)
            if deductions_count > 0:
                cursor.execute("""
                    DELETE FROM chargeback_deductions 
                    WHERE merchant_id = %s
                """, (merchant_id,))
                print(f"✅ Deleted {cursor.rowcount} chargeback deduction records")
            
            # 2. Delete chargebacks (has FK to merchants and chargeback_uploads)
            if chargebacks_count > 0:
                cursor.execute("""
                    DELETE FROM chargebacks 
                    WHERE merchant_id = %s
                """, (merchant_id,))
                print(f"✅ Deleted {cursor.rowcount} chargeback records")
            
            # 3. Delete chargeback uploads
            if uploads_count > 0:
                cursor.execute("""
                    DELETE FROM chargeback_uploads 
                    WHERE merchant_id = %s
                """, (merchant_id,))
                print(f"✅ Deleted {cursor.rowcount} chargeback upload records")
            
            print("-"*80)
            
            # Commit the transaction
            connection.commit()
            
            print("\n" + "="*80)
            print("✅ CHARGEBACK DATA DELETION COMPLETED SUCCESSFULLY!")
            print("="*80)
            print(f"All chargeback data for merchant '{merchant_id}' has been permanently deleted.")
            print("="*80 + "\n")
            
        connection.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Error deleting chargeback data: {e}")
        if 'connection' in locals():
            connection.rollback()
            connection.close()
        return False


def list_merchants_with_chargebacks():
    """List all merchants who have chargeback data"""
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
                SELECT 
                    m.merchant_id,
                    m.full_name,
                    m.email,
                    m.mobile,
                    COUNT(DISTINCT c.id) as chargeback_count,
                    COALESCE(SUM(c.chargeback_amount), 0) as total_chargeback_amount,
                    COUNT(DISTINCT cd.id) as deduction_count,
                    COUNT(DISTINCT cu.id) as upload_count
                FROM merchants m
                LEFT JOIN chargebacks c ON m.merchant_id = c.merchant_id
                LEFT JOIN chargeback_deductions cd ON m.merchant_id = cd.merchant_id
                LEFT JOIN chargeback_uploads cu ON m.merchant_id = cu.merchant_id
                WHERE c.id IS NOT NULL OR cd.id IS NOT NULL OR cu.id IS NOT NULL
                GROUP BY m.merchant_id, m.full_name, m.email, m.mobile
                ORDER BY chargeback_count DESC
            """)
            merchants = cursor.fetchall()
            
            if not merchants:
                print("\n✅ No merchants found with chargeback data.")
                return
            
            print("\n" + "="*100)
            print("MERCHANTS WITH CHARGEBACK DATA")
            print("="*100)
            print(f"{'Merchant ID':<20} {'Name':<25} {'Chargebacks':<15} {'Amount':<20} {'Deductions':<12} {'Uploads':<10}")
            print("-"*100)
            
            for merchant in merchants:
                print(f"{merchant['merchant_id']:<20} "
                      f"{merchant['full_name']:<25} "
                      f"{merchant['chargeback_count']:<15} "
                      f"₹{float(merchant['total_chargeback_amount']):>15,.2f}    "
                      f"{merchant['deduction_count']:<12} "
                      f"{merchant['upload_count']:<10}")
            
            print("="*100 + "\n")
            
        connection.close()
        
    except Exception as e:
        print(f"\n❌ Error listing merchants: {e}")


def main():
    """Main function to run the script"""
    print("\n" + "="*80)
    print("CHARGEBACK DATA DELETION SCRIPT")
    print("="*80 + "\n")
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  1. List all merchants with chargeback data:")
        print("     python delete_user_chargeback_data.py list")
        print("\n  2. Delete chargeback data for a specific merchant (dry run):")
        print("     python delete_user_chargeback_data.py <merchant_id>")
        print("\n  3. Delete chargeback data for a specific merchant (actual deletion):")
        print("     python delete_user_chargeback_data.py <merchant_id> confirm")
        print("\nExamples:")
        print("  python delete_user_chargeback_data.py list")
        print("  python delete_user_chargeback_data.py MERCH001")
        print("  python delete_user_chargeback_data.py MERCH001 confirm")
        print("\n" + "="*80 + "\n")
        return
    
    command = sys.argv[1]
    
    if command.lower() == 'list':
        list_merchants_with_chargebacks()
    else:
        merchant_id = command
        dry_run = True if len(sys.argv) < 3 or sys.argv[2].lower() != 'confirm' else False
        delete_user_chargeback_data(merchant_id, dry_run=dry_run)


if __name__ == '__main__':
    main()
