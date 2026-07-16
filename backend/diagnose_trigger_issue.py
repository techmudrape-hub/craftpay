"""
Diagnose why trigger is returning 400
"""
from auto_settlement_service import AutoSettlementService
from database_pooled import get_db_connection

merchant_id = '7679022140'

print("=" * 60)
print(f"Diagnosing Trigger Issue for {merchant_id}")
print("=" * 60)

service = AutoSettlementService()

# Get config
print("\n1. Checking config...")
config = service.get_merchant_auto_settlement_config(merchant_id)
if config:
    print(f"   ✅ Config found")
    print(f"      Enabled: {config['is_enabled']}")
    print(f"      Hold %: {config['hold_percentage']}")
    print(f"      Min Amount: {config['minimum_settlement_amount']}")
else:
    print(f"   ❌ No config found")
    exit(1)

# Get wallet
print("\n2. Checking wallet...")
conn = get_db_connection()
with conn.cursor() as cursor:
    cursor.execute("""
        SELECT unsettled_balance, settled_balance
        FROM merchant_wallet
        WHERE merchant_id = %s
    """, (merchant_id,))
    wallet = cursor.fetchone()
    
if wallet:
    print(f"   ✅ Wallet found")
    print(f"      Unsettled: ₹{wallet['unsettled_balance']}")
    print(f"      Settled: ₹{wallet['settled_balance']}")
    unsettled = float(wallet['unsettled_balance'])
else:
    print(f"   ❌ No wallet found")
    conn.close()
    exit(1)

# Get admin
print("\n3. Checking admin...")
with conn.cursor() as cursor:
    cursor.execute("SELECT admin_id FROM admin_users LIMIT 1")
    admin = cursor.fetchone()
    
if admin:
    admin_id = admin['admin_id']
    print(f"   ✅ Admin found: {admin_id}")
else:
    print(f"   ❌ No admin found")
    conn.close()
    exit(1)

conn.close()

# Calculate settlement
print("\n4. Calculating settlement...")
hold_pct = float(config['hold_percentage'])
held = (unsettled * hold_pct) / 100
to_settle = unsettled - held

print(f"   Unsettled: ₹{unsettled:.2f}")
print(f"   Hold {hold_pct}%: ₹{held:.2f}")
print(f"   To Settle: ₹{to_settle:.2f}")

if to_settle <= 0:
    print(f"   ❌ Nothing to settle!")
    exit(1)

# Try settlement
print("\n5. Attempting settlement...")
result = service.perform_auto_settlement(merchant_id, admin_id, force=True)

print(f"\n6. Result:")
print(f"   Success: {result['success']}")
if result['success']:
    print(f"   Settlement ID: {result.get('settlement_id')}")
    print(f"   Settled: ₹{result.get('settled_amount')}")
    print(f"   Held: ₹{result.get('held_amount')}")
else:
    print(f"   Message: {result.get('message')}")

print("\n" + "=" * 60)
