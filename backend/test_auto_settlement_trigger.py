"""
Test auto-settlement trigger to diagnose the 400 error
"""
from auto_settlement_service import AutoSettlementService
from database_pooled import get_db_connection

def test_trigger():
    """Test triggering auto-settlement"""
    print("=" * 60)
    print("Testing Auto-Settlement Trigger")
    print("=" * 60)
    
    # Get a test merchant
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        with conn.cursor() as cursor:
            # Get a merchant with unsettled balance
            cursor.execute("""
                SELECT m.merchant_id, m.full_name, 
                       mw.unsettled_balance, mw.settled_balance
                FROM merchants m
                JOIN merchant_wallet mw ON m.merchant_id = mw.merchant_id
                WHERE mw.unsettled_balance > 0
                LIMIT 1
            """)
            merchant = cursor.fetchone()
            
            if not merchant:
                print("❌ No merchant with unsettled balance found")
                print("\nTrying any merchant...")
                cursor.execute("""
                    SELECT m.merchant_id, m.full_name, 
                           COALESCE(mw.unsettled_balance, 0) as unsettled_balance,
                           COALESCE(mw.settled_balance, 0) as settled_balance
                    FROM merchants m
                    LEFT JOIN merchant_wallet mw ON m.merchant_id = mw.merchant_id
                    LIMIT 1
                """)
                merchant = cursor.fetchone()
                
                if not merchant:
                    print("❌ No merchants found in database")
                    return
            
            merchant_id = merchant['merchant_id']
            print(f"\n📋 Test Merchant:")
            print(f"   ID: {merchant_id}")
            print(f"   Name: {merchant['full_name']}")
            print(f"   Unsettled: ₹{float(merchant['unsettled_balance']):.2f}")
            print(f"   Settled: ₹{float(merchant['settled_balance']):.2f}")
            
            # Check if auto-settlement config exists
            print(f"\n🔍 Checking auto-settlement config...")
            cursor.execute("""
                SELECT * FROM auto_settlement_config
                WHERE merchant_id = %s
            """, (merchant_id,))
            config = cursor.fetchone()
            
            if config:
                print(f"   ✅ Config exists")
                print(f"      Enabled: {bool(config['is_enabled'])}")
                print(f"      Frequency: {config['settlement_frequency']}")
                print(f"      Hold %: {float(config['hold_percentage'])}")
                print(f"      Min Amount: ₹{float(config['minimum_settlement_amount'])}")
            else:
                print(f"   ⚠️  No config found - creating default config...")
                cursor.execute("""
                    INSERT INTO auto_settlement_config
                    (merchant_id, is_enabled, settlement_frequency, hold_percentage, minimum_settlement_amount)
                    VALUES (%s, TRUE, 'DAILY', 10.00, 0.00)
                """, (merchant_id,))
                conn.commit()
                print(f"   ✅ Default config created")
            
            # Get a valid admin_id
            print(f"\n🔑 Getting valid admin ID...")
            cursor.execute("SELECT admin_id FROM admin_users LIMIT 1")
            admin_row = cursor.fetchone()
            if not admin_row:
                print("   ❌ No admin users found")
                return
            admin_id = admin_row['admin_id']
            print(f"   ✅ Using admin: {admin_id}")
            
            # Test the service
            print(f"\n🧪 Testing auto-settlement service...")
            service = AutoSettlementService()
            
            # Get config
            config = service.get_merchant_auto_settlement_config(merchant_id)
            if config:
                print(f"   ✅ Service can read config")
            else:
                print(f"   ❌ Service cannot read config")
                return
            
            # Try to perform settlement
            print(f"\n💰 Attempting settlement...")
            result = service.perform_auto_settlement(merchant_id, admin_id)
            
            if result['success']:
                print(f"   ✅ Settlement successful!")
                print(f"      Settlement ID: {result.get('settlement_id')}")
                print(f"      Settled: ₹{result.get('settled_amount', 0):.2f}")
                print(f"      Held: ₹{result.get('held_amount', 0):.2f}")
            else:
                print(f"   ⚠️  Settlement not completed")
                print(f"      Reason: {result.get('message')}")
            
            # Check logs
            print(f"\n📊 Recent settlement logs:")
            cursor.execute("""
                SELECT status, settled_amount, held_amount, reason, created_at
                FROM auto_settlement_logs
                WHERE merchant_id = %s
                ORDER BY created_at DESC
                LIMIT 3
            """, (merchant_id,))
            logs = cursor.fetchall()
            
            if logs:
                for log in logs:
                    print(f"   - {log['status']}: ₹{float(log['settled_amount']):.2f} (Held: ₹{float(log['held_amount']):.2f})")
                    print(f"     {log['reason']} - {log['created_at']}")
            else:
                print(f"   No logs found")
            
            print("\n" + "=" * 60)
            print("✅ Test completed")
            print("=" * 60)
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    test_trigger()
