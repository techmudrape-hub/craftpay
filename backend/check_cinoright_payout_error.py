"""
Check Cinoright Payout Transaction Errors
Query the database to see what error occurred
"""

from database import get_db_connection
import json

def check_recent_cinoright_payouts():
    """Check recent Cinoright payout transactions and their errors"""
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ Database connection failed")
            return
        
        with conn.cursor() as cursor:
            print("=" * 80)
            print("RECENT CINORIGHT PAYOUT TRANSACTIONS")
            print("=" * 80)
            
            # Get recent Cinoright transactions
            cursor.execute("""
                SELECT 
                    txn_id,
                    reference_id,
                    order_id,
                    merchant_id,
                    amount,
                    charge_amount,
                    net_amount,
                    bene_name,
                    account_no,
                    ifsc_code,
                    status,
                    pg_txn_id,
                    utr,
                    error_message,
                    created_at,
                    updated_at,
                    completed_at
                FROM payout_transactions
                WHERE pg_partner = 'CINORIGHT'
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            transactions = cursor.fetchall()
            
            if not transactions:
                print("\n⚠ No Cinoright transactions found in database")
                return
            
            print(f"\nFound {len(transactions)} recent Cinoright transaction(s):\n")
            
            for i, txn in enumerate(transactions, 1):
                print(f"\n{'─' * 80}")
                print(f"Transaction #{i}")
                print(f"{'─' * 80}")
                print(f"TXN ID:        {txn['txn_id']}")
                print(f"Reference ID:  {txn['reference_id']}")
                print(f"Order ID:      {txn['order_id']}")
                print(f"Merchant ID:   {txn['merchant_id']}")
                print(f"Amount:        ₹{txn['amount']:.2f}")
                print(f"Charges:       ₹{txn['charge_amount']:.2f}")
                print(f"Net Amount:    ₹{txn['net_amount']:.2f}")
                print(f"Beneficiary:   {txn['bene_name']}")
                print(f"Account:       {txn['account_no']}")
                print(f"IFSC:          {txn['ifsc_code']}")
                print(f"Status:        {txn['status']}")
                print(f"PG TXN ID:     {txn['pg_txn_id'] or 'N/A'}")
                print(f"UTR:           {txn['utr'] or 'N/A'}")
                print(f"Created:       {txn['created_at']}")
                print(f"Updated:       {txn['updated_at']}")
                print(f"Completed:     {txn['completed_at'] or 'N/A'}")
                
                if txn['error_message']:
                    print(f"\n❌ ERROR MESSAGE:")
                    print(f"{'─' * 80}")
                    # Try to parse as JSON for better formatting
                    try:
                        error_data = json.loads(txn['error_message'])
                        print(json.dumps(error_data, indent=2))
                    except:
                        print(txn['error_message'])
                    print(f"{'─' * 80}")
                
                # Analyze the status
                if txn['status'] == 'FAILED':
                    print("\n⚠ ANALYSIS:")
                    if not txn['error_message']:
                        print("  - Transaction failed but no error message recorded")
                        print("  - Check Cinoright API response logs")
                    elif 'Insufficient balance' in str(txn['error_message']):
                        print("  - Insufficient balance in Cinoright account")
                        print("  - Action: Top up your Cinoright account")
                    elif 'Invalid IFSC' in str(txn['error_message']):
                        print("  - Invalid IFSC code format")
                        print("  - Action: Verify IFSC code format (AAAA0XXXXXX)")
                    elif 'IP' in str(txn['error_message']):
                        print("  - IP not whitelisted")
                        print("  - Action: Contact Cinoright to whitelist your server IP")
                    else:
                        print("  - Check error message above for details")
                        print("  - Contact Cinoright support if needed")
                
                elif txn['status'] == 'INITIATED':
                    print("\n⚠ ANALYSIS:")
                    print("  - Transaction is still pending")
                    print("  - Waiting for callback from Cinoright")
                    print("  - Or status check hasn't been performed yet")
                
                elif txn['status'] == 'SUCCESS':
                    print("\n✓ ANALYSIS:")
                    print("  - Transaction completed successfully")
                    print(f"  - UTR: {txn['utr']}")
            
            print("\n" + "=" * 80)
            print("SUMMARY")
            print("=" * 80)
            
            # Count by status
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM payout_transactions
                WHERE pg_partner = 'CINORIGHT'
                GROUP BY status
            """)
            
            status_counts = cursor.fetchall()
            
            print("\nTransaction Status Distribution:")
            for status in status_counts:
                print(f"  {status['status']}: {status['count']}")
            
            # Get most common errors
            cursor.execute("""
                SELECT error_message, COUNT(*) as count
                FROM payout_transactions
                WHERE pg_partner = 'CINORIGHT'
                AND error_message IS NOT NULL
                AND error_message != ''
                GROUP BY error_message
                ORDER BY count DESC
                LIMIT 5
            """)
            
            common_errors = cursor.fetchall()
            
            if common_errors:
                print("\nMost Common Errors:")
                for i, error in enumerate(common_errors, 1):
                    print(f"\n{i}. Occurred {error['count']} time(s):")
                    try:
                        error_data = json.loads(error['error_message'])
                        print(f"   {json.dumps(error_data, indent=3)}")
                    except:
                        print(f"   {error['error_message'][:200]}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    check_recent_cinoright_payouts()
