"""
Diagnose Razorpay Callback Issue
Check logs, database, and test the callback manually
"""

import sys
from database import get_db_connection
from razorpay_service import razorpay_service

def check_recent_transactions():
    """Check recent Razorpay transactions"""
    print("=" * 80)
    print("CHECKING RECENT RAZORPAY TRANSACTIONS")
    print("=" * 80)
    
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    txn_id, order_id, pg_txn_id, status, amount, 
                    bank_ref_no, created_at, completed_at
                FROM payin_transactions
                WHERE pg_partner = 'RAZORPAY'
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            txns = cursor.fetchall()
            
            if not txns:
                print("❌ No Razorpay transactions found")
                return
            
            print(f"Found {len(txns)} recent Razorpay transactions:\n")
            
            for txn in txns:
                print(f"Transaction: {txn['txn_id']}")
                print(f"  Order ID: {txn['order_id']}")
                print(f"  Payment Link ID: {txn['pg_txn_id']}")
                print(f"  Status: {txn['status']}")
                print(f"  Amount: ₹{txn['amount']}")
                print(f"  Bank UTR: {txn['bank_ref_no'] or 'NOT SET'}")
                print(f"  Created: {txn['created_at']}")
                print(f"  Completed: {txn['completed_at'] or 'NOT COMPLETED'}")
                print("-" * 80)
                
                # If status is INITIATED, check with Razorpay
                if txn['status'] in ['INITIATED', 'PENDING'] and txn['pg_txn_id']:
                    print(f"  ⚠ Transaction still {txn['status']}, checking with Razorpay...")
                    
                    status_result = razorpay_service.check_payment_status(txn['pg_txn_id'])
                    
                    if status_result.get('success'):
                        print(f"  Razorpay Status: {status_result.get('status')}")
                        print(f"  Razorpay Amount: ₹{status_result.get('amount')}")
                        print(f"  Razorpay UTR: {status_result.get('utr') or 'NOT AVAILABLE'}")
                        
                        if status_result.get('status') == 'SUCCESS':
                            print(f"  ✅ Payment is SUCCESS on Razorpay but not updated in database!")
                            print(f"  💡 Callback may have failed. Run manual update.")
                    else:
                        print(f"  ❌ Failed to check status: {status_result.get('message')}")
                    
                    print("-" * 80)
    
    finally:
        conn.close()

def check_callback_logs():
    """Check callback logs"""
    print("\n" + "=" * 80)
    print("CHECKING CALLBACK LOGS")
    print("=" * 80)
    
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        with conn.cursor() as cursor:
            # Check if callback_logs table exists
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() 
                AND table_name = 'callback_logs'
            """)
            
            if cursor.fetchone()['count'] == 0:
                print("⚠ callback_logs table does not exist")
                return
            
            cursor.execute("""
                SELECT 
                    merchant_id, txn_id, callback_url, 
                    response_code, response_data, created_at
                FROM callback_logs
                WHERE txn_id LIKE 'RAZORPAY%'
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            logs = cursor.fetchall()
            
            if not logs:
                print("❌ No Razorpay callback logs found")
                return
            
            print(f"Found {len(logs)} recent Razorpay callback logs:\n")
            
            for log in logs:
                print(f"Callback Log:")
                print(f"  TXN ID: {log['txn_id']}")
                print(f"  Merchant: {log['merchant_id']}")
                print(f"  Callback URL: {log['callback_url']}")
                print(f"  Response Code: {log['response_code']}")
                print(f"  Response: {log['response_data'][:200] if log['response_data'] else 'NONE'}")
                print(f"  Time: {log['created_at']}")
                print("-" * 80)
    
    finally:
        conn.close()

def manual_callback_test(payment_link_id):
    """Manually test callback processing"""
    print("\n" + "=" * 80)
    print(f"MANUAL CALLBACK TEST FOR: {payment_link_id}")
    print("=" * 80)
    
    # Step 1: Check payment status from Razorpay
    print("\nStep 1: Fetching payment details from Razorpay...")
    status_result = razorpay_service.check_payment_status(payment_link_id)
    
    if not status_result.get('success'):
        print(f"❌ Failed to fetch payment details: {status_result.get('message')}")
        return
    
    print(f"✅ Payment details fetched:")
    print(f"  Status: {status_result.get('status')}")
    print(f"  Amount: ₹{status_result.get('amount')}")
    print(f"  Amount Paid: ₹{status_result.get('amount_paid')}")
    print(f"  Payment ID: {status_result.get('payment_id')}")
    print(f"  UTR: {status_result.get('utr')}")
    
    # Step 2: Check database
    print("\nStep 2: Checking database...")
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    txn_id, order_id, merchant_id, status, amount,
                    net_amount, charge_amount, callback_url
                FROM payin_transactions
                WHERE pg_txn_id = %s AND pg_partner = 'RAZORPAY'
            """, (payment_link_id,))
            
            txn = cursor.fetchone()
            
            if not txn:
                print(f"❌ Transaction not found in database for payment_link_id: {payment_link_id}")
                return
            
            print(f"✅ Transaction found:")
            print(f"  TXN ID: {txn['txn_id']}")
            print(f"  Order ID: {txn['order_id']}")
            print(f"  Merchant ID: {txn['merchant_id']}")
            print(f"  Status: {txn['status']}")
            print(f"  Amount: ₹{txn['amount']}")
            print(f"  Net Amount: ₹{txn['net_amount']}")
            print(f"  Charge: ₹{txn['charge_amount']}")
            print(f"  Callback URL: {txn['callback_url'] or 'NOT SET'}")
            
            # Step 3: Update if needed
            razorpay_status = status_result.get('status')
            if razorpay_status == 'SUCCESS' and txn['status'] != 'SUCCESS':
                print(f"\n⚠ Status mismatch! Razorpay: {razorpay_status}, Database: {txn['status']}")
                print(f"💡 Updating database...")
                
                bank_utr = status_result.get('utr') or status_result.get('payment_id')
                
                cursor.execute("""
                    UPDATE payin_transactions
                    SET status = 'SUCCESS',
                        bank_ref_no = %s,
                        payment_mode = 'UPI',
                        completed_at = NOW(),
                        updated_at = NOW()
                    WHERE txn_id = %s
                """, (bank_utr, txn['txn_id']))
                
                conn.commit()
                print(f"✅ Database updated to SUCCESS")
                
                # Credit wallet
                print(f"\n💰 Crediting wallets...")
                
                # Check if already credited
                cursor.execute("""
                    SELECT COUNT(*) as count FROM merchant_wallet_transactions
                    WHERE reference_id = %s AND txn_type = 'UNSETTLED_CREDIT'
                """, (txn['txn_id'],))
                
                if cursor.fetchone()['count'] > 0:
                    print(f"⚠ Wallet already credited")
                else:
                    from wallet_service import wallet_service as wallet_svc
                    
                    # Credit merchant
                    wallet_result = wallet_svc.credit_unsettled_wallet(
                        merchant_id=txn['merchant_id'],
                        amount=float(txn['net_amount']),
                        description=f"PayIn received (Razorpay Manual) - {txn['order_id']}",
                        reference_id=txn['txn_id']
                    )
                    
                    if wallet_result['success']:
                        print(f"✅ Merchant wallet credited: ₹{txn['net_amount']}")
                    else:
                        print(f"❌ Failed to credit merchant wallet: {wallet_result.get('message')}")
                    
                    # Credit admin
                    admin_result = wallet_svc.credit_admin_unsettled_wallet(
                        admin_id='admin',
                        amount=float(txn['charge_amount']),
                        description=f"PayIn charge (Razorpay Manual) - {txn['order_id']}",
                        reference_id=txn['txn_id']
                    )
                    
                    if admin_result['success']:
                        print(f"✅ Admin wallet credited: ₹{txn['charge_amount']}")
                    else:
                        print(f"❌ Failed to credit admin wallet: {admin_result.get('message')}")
                
                # Forward to merchant
                if txn['callback_url']:
                    print(f"\n📤 Forwarding callback to merchant...")
                    
                    import requests
                    import json
                    
                    callback_data = {
                        'txn_id': txn['txn_id'],
                        'order_id': txn['order_id'],
                        'status': 'SUCCESS',
                        'utr': bank_utr,
                        'pg_partner': 'RAZORPAY',
                        'amount': float(txn['amount']),
                        'net_amount': float(txn['net_amount']),
                        'charge_amount': float(txn['charge_amount'])
                    }
                    
                    try:
                        response = requests.post(
                            txn['callback_url'],
                            json=callback_data,
                            headers={'Content-Type': 'application/json'},
                            timeout=10
                        )
                        
                        print(f"✅ Merchant callback sent: {response.status_code}")
                        print(f"Response: {response.text[:200]}")
                    except Exception as e:
                        print(f"❌ Failed to send merchant callback: {e}")
                else:
                    print(f"\n⚠ No merchant callback URL configured")
            
            elif txn['status'] == 'SUCCESS':
                print(f"\n✅ Transaction already SUCCESS in database")
            else:
                print(f"\n⚠ Razorpay status: {razorpay_status}, Database status: {txn['status']}")
    
    finally:
        conn.close()

if __name__ == '__main__':
    print("Razorpay Callback Diagnostic Tool")
    print("=" * 80)
    
    # Check recent transactions
    check_recent_transactions()
    
    # Check callback logs
    check_callback_logs()
    
    # Manual test if payment_link_id provided
    if len(sys.argv) > 1:
        payment_link_id = sys.argv[1]
        manual_callback_test(payment_link_id)
    else:
        print("\n" + "=" * 80)
        print("MANUAL CALLBACK TEST")
        print("=" * 80)
        print("To manually process a callback, run:")
        print("  python diagnose_razorpay_callback.py <payment_link_id>")
        print("\nExample:")
        print("  python diagnose_razorpay_callback.py plink_SnLcnAMDEma3j1")
