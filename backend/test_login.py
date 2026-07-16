#!/usr/bin/env python3
"""Test admin login to debug the issue"""

from config import Config
import pymysql
import bcrypt
from datetime import datetime

# Test credentials
admin_id = "admin@orchpay.in"
password = "Admin@123"

print(f"Testing login for: {admin_id}")
print("-" * 60)

try:
    # Connect to database
    conn = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )
    print("✅ Database connected")
    
    with conn.cursor() as cursor:
        # Get admin user
        cursor.execute("SELECT * FROM admin_users WHERE admin_id = %s", (admin_id,))
        admin = cursor.fetchone()
        
        if not admin:
            print("❌ Admin user not found")
            exit(1)
        
        print(f"✅ Admin user found")
        print(f"   Active: {admin['is_active']}")
        print(f"   Login attempts: {admin.get('login_attempts', 0)}")
        print(f"   Locked until: {admin.get('locked_until', 'Not locked')}")
        
        # Check password
        stored_hash = admin['password_hash']
        print(f"\n🔐 Password hash (first 50 chars): {stored_hash[:50]}...")
        
        try:
            # Try to verify password
            if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
                print("✅ Password matches!")
            else:
                print("❌ Password does not match")
                
                # Try to create a new hash and compare
                print("\n🔧 Creating new hash for comparison...")
                new_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
                print(f"   New hash: {new_hash.decode('utf-8')[:50]}...")
                
        except Exception as e:
            print(f"❌ Error checking password: {e}")
            print(f"   Error type: {type(e).__name__}")
            
            # Check if hash format is correct
            if stored_hash.startswith('$2b$') or stored_hash.startswith('$2a$') or stored_hash.startswith('$2y$'):
                print("   Hash format looks correct (bcrypt)")
            else:
                print(f"   ⚠️  Hash format might be wrong: {stored_hash[:10]}")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
