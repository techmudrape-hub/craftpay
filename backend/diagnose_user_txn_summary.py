"""
Diagnose User Transaction Summary endpoint issues
"""

import sys
import traceback

print("=" * 60)
print("Diagnosing User Transaction Summary")
print("=" * 60)

# Test 1: Import the blueprint
print("\n1. Testing blueprint import...")
try:
    from user_transaction_summary_routes import user_txn_summary_bp
    print(f"✅ Blueprint imported successfully")
    print(f"   Name: {user_txn_summary_bp.name}")
    print(f"   URL Prefix: {user_txn_summary_bp.url_prefix}")
except Exception as e:
    print(f"❌ Failed to import blueprint: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 2: Check database connection
print("\n2. Testing database connection...")
try:
    from database_pooled import get_db_connection
    conn = get_db_connection()
    if conn:
        print("✅ Database connection successful")
        conn.close()
    else:
        print("❌ Database connection returned None")
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    traceback.print_exc()

# Test 3: Check if app has the blueprint registered
print("\n3. Checking if blueprint is registered in app...")
try:
    from app import app
    
    # Check if blueprint is registered
    blueprint_names = [bp.name for bp in app.blueprints.values()]
    
    if 'user_txn_summary' in blueprint_names:
        print("✅ Blueprint is registered in app")
    else:
        print("❌ Blueprint NOT registered in app")
        print(f"   Registered blueprints: {blueprint_names}")
        print("\n   ⚠️  You need to restart the backend server!")
        print("   Run: sudo systemctl restart orchpay-backend")
        print("   Or: pkill -f gunicorn && gunicorn -w 4 -b 0.0.0.0:5000 app:app")
except Exception as e:
    print(f"❌ Failed to check app: {e}")
    traceback.print_exc()

# Test 4: Check routes
print("\n4. Checking registered routes...")
try:
    from app import app
    
    user_txn_routes = []
    for rule in app.url_map.iter_rules():
        if 'user-transaction-summary' in rule.rule:
            user_txn_routes.append(f"{rule.rule} [{', '.join(rule.methods)}]")
    
    if user_txn_routes:
        print("✅ User Transaction Summary routes found:")
        for route in user_txn_routes:
            print(f"   {route}")
    else:
        print("❌ No User Transaction Summary routes found")
        print("\n   ⚠️  Backend server needs to be restarted!")
except Exception as e:
    print(f"❌ Failed to check routes: {e}")
    traceback.print_exc()

# Test 5: Test a simple query
print("\n5. Testing database query...")
try:
    from database_pooled import get_db_connection
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM merchants WHERE is_active = TRUE")
            result = cursor.fetchone()
            print(f"✅ Found {result['count']} active merchants")
        conn.close()
except Exception as e:
    print(f"❌ Database query failed: {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("Diagnosis Complete")
print("=" * 60)

print("\n📋 SUMMARY:")
print("If blueprint is NOT registered or routes are NOT found:")
print("  → Restart the backend server")
print("  → Command: sudo systemctl restart orchpay-backend")
print("\nIf database connection failed:")
print("  → Check MySQL is running: sudo systemctl status mysql")
print("  → Check .env file has correct DB credentials")
