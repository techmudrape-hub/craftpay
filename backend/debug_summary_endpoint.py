"""
Debug the summary endpoint to find the exact error
"""

from database_pooled import get_db_connection
from datetime import datetime

merchant_id = "8130055250"
from_date = "2026-05-01"
to_date = "2026-05-13"

print("=" * 60)
print("Debugging Summary Endpoint")
print("=" * 60)

try:
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        exit(1)
    
    print("✅ Database connected")
    
    with conn.cursor() as cursor:
        # Test 1: Get merchant details
        print("\n1. Testing merchant query...")
        cursor.execute("""
            SELECT merchant_id, full_name, email, mobile
            FROM merchants
            WHERE merchant_id = %s
        """, (merchant_id,))
        
        merchant = cursor.fetchone()
        if merchant:
            print(f"✅ Merchant found: {merchant['full_name']}")
        else:
            print(f"❌ Merchant not found: {merchant_id}")
            exit(1)
        
        # Test 2: Build date filter
        print("\n2. Building date filter...")
        date_time_conditions = []
        params = []
        
        if from_date and to_date:
            date_time_conditions.append("DATE(created_at) >= %s AND DATE(created_at) <= %s")
            params.extend([from_date, to_date])
        
        date_time_filter = " AND " + " AND ".join(date_time_conditions) if date_time_conditions else ""
        print(f"   Filter: {date_time_filter}")
        print(f"   Params: {params}")
        
        # Test 3: Payin summary query
        print("\n3. Testing payin summary query...")
        payin_query = f"""
            SELECT 
                COUNT(*) as total_count,
                COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as total_payin,
                COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN charge_amount ELSE 0 END), 0) as total_charges,
                COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN net_amount ELSE 0 END), 0) as net_payin,
                COUNT(CASE WHEN status = 'SUCCESS' THEN 1 END) as success_count,
                COUNT(CASE WHEN status = 'PENDING' THEN 1 END) as pending_count,
                COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as failed_count
            FROM payin_transactions
            WHERE merchant_id = %s {date_time_filter}
        """
        
        print(f"   Query: {payin_query}")
        print(f"   Params: {[merchant_id] + params}")
        
        try:
            cursor.execute(payin_query, [merchant_id] + params)
            payin_summary = cursor.fetchone()
            print(f"✅ Payin summary retrieved")
            print(f"   Total count: {payin_summary['total_count']}")
            print(f"   Total payin: {payin_summary['total_payin']}")
            print(f"   Success count: {payin_summary['success_count']}")
        except Exception as e:
            print(f"❌ Payin query failed: {e}")
            import traceback
            traceback.print_exc()
            exit(1)
        
        # Test 4: Payout summary query
        print("\n4. Testing payout summary query...")
        payout_query = f"""
            SELECT 
                COUNT(*) as total_count,
                COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 0) as total_payout,
                COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN charge_amount ELSE 0 END), 0) as total_charges,
                COALESCE(SUM(CASE WHEN status = 'SUCCESS' THEN (amount + charge_amount) ELSE 0 END), 0) as net_payout,
                COUNT(CASE WHEN status = 'SUCCESS' THEN 1 END) as success_count,
                COUNT(CASE WHEN status IN ('PENDING', 'QUEUED') THEN 1 END) as pending_count,
                COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as failed_count
            FROM payout_transactions
            WHERE merchant_id = %s {date_time_filter}
        """
        
        print(f"   Query: {payout_query}")
        print(f"   Params: {[merchant_id] + params}")
        
        try:
            cursor.execute(payout_query, [merchant_id] + params)
            payout_summary = cursor.fetchone()
            print(f"✅ Payout summary retrieved")
            print(f"   Total count: {payout_summary['total_count']}")
            print(f"   Total payout: {payout_summary['total_payout']}")
            print(f"   Success count: {payout_summary['success_count']}")
        except Exception as e:
            print(f"❌ Payout query failed: {e}")
            import traceback
            traceback.print_exc()
            exit(1)
        
        # Test 5: Recent payins
        print("\n5. Testing recent payins query...")
        recent_payin_query = f"""
            SELECT 
                txn_id, order_id, amount, charge_amount, net_amount, 
                status, payment_mode, created_at, completed_at
            FROM payin_transactions
            WHERE merchant_id = %s {date_time_filter}
            ORDER BY created_at DESC
            LIMIT 10
        """
        
        try:
            cursor.execute(recent_payin_query, [merchant_id] + params)
            recent_payins = cursor.fetchall()
            print(f"✅ Recent payins retrieved: {len(recent_payins)} transactions")
        except Exception as e:
            print(f"❌ Recent payins query failed: {e}")
            import traceback
            traceback.print_exc()
            exit(1)
        
        # Test 6: Recent payouts
        print("\n6. Testing recent payouts query...")
        recent_payout_query = f"""
            SELECT 
                txn_id, order_id, amount, charge_amount, 
                status, bene_name, account_no, created_at, completed_at
            FROM payout_transactions
            WHERE merchant_id = %s {date_time_filter}
            ORDER BY created_at DESC
            LIMIT 10
        """
        
        try:
            cursor.execute(recent_payout_query, [merchant_id] + params)
            recent_payouts = cursor.fetchall()
            print(f"✅ Recent payouts retrieved: {len(recent_payouts)} transactions")
        except Exception as e:
            print(f"❌ Recent payouts query failed: {e}")
            import traceback
            traceback.print_exc()
            exit(1)
        
        # Test 7: Format data
        print("\n7. Testing data formatting...")
        try:
            for txn in recent_payins:
                if txn.get('created_at'):
                    txn['created_at'] = txn['created_at'].isoformat()
                if txn.get('completed_at'):
                    txn['completed_at'] = txn['completed_at'].isoformat()
                txn['amount'] = float(txn['amount']) if txn.get('amount') else 0.0
                txn['charge_amount'] = float(txn['charge_amount']) if txn.get('charge_amount') else 0.0
                txn['net_amount'] = float(txn['net_amount']) if txn.get('net_amount') else 0.0
            
            for txn in recent_payouts:
                if txn.get('created_at'):
                    txn['created_at'] = txn['created_at'].isoformat()
                if txn.get('completed_at'):
                    txn['completed_at'] = txn['completed_at'].isoformat()
                txn['amount'] = float(txn['amount']) if txn.get('amount') else 0.0
                txn['charge_amount'] = float(txn['charge_amount']) if txn.get('charge_amount') else 0.0
            
            print("✅ Data formatting successful")
        except Exception as e:
            print(f"❌ Data formatting failed: {e}")
            import traceback
            traceback.print_exc()
            exit(1)
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print("\nThe logic works correctly when run directly.")
    print("The issue must be in the Flask route or server configuration.")
    print("\n🔧 NEXT STEPS:")
    print("1. Check backend server logs for the actual error")
    print("2. Restart the backend server: sudo systemctl restart orchpay-backend")
    print("3. Check logs: sudo journalctl -u orchpay-backend -n 50")

except Exception as e:
    print(f"\n❌ UNEXPECTED ERROR: {e}")
    import traceback
    traceback.print_exc()
