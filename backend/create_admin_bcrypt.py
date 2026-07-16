#!/usr/bin/env python3
"""Create admin user with bcrypt password hash"""

from config import Config
import pymysql
import bcrypt

# Admin credentials
admin_id = "admin@orchpay.in"
password = "Admin@123"

print(f"Creating admin user with bcrypt hash...")
print(f"Admin ID: {admin_id}")
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
    
    # Generate bcrypt hash
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    password_hash_str = password_hash.decode('utf-8')
    
    print(f"✅ Password hash generated (bcrypt)")
    print(f"   Hash: {password_hash_str[:50]}...")
    
    with conn.cursor() as cursor:
        # Check if admin exists
        cursor.execute("SELECT admin_id FROM admin_users WHERE admin_id = %s", (admin_id,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"\n⚠️  Admin user already exists. Updating password...")
            cursor.execute("""
                UPDATE admin_users 
                SET password_hash = %s,
                    login_attempts = 0,
                    locked_until = NULL,
                    is_active = 1
                WHERE admin_id = %s
            """, (password_hash_str, admin_id))
            print("✅ Password updated successfully")
        else:
            print(f"\n📝 Creating new admin user...")
            cursor.execute("""
                INSERT INTO admin_users (admin_id, password_hash, is_active, created_at)
                VALUES (%s, %s, 1, NOW())
            """, (admin_id, password_hash_str))
            print("✅ Admin user created successfully")
        
        conn.commit()
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("✅ SUCCESS!")
    print("=" * 60)
    print(f"Admin ID: {admin_id}")
    print(f"Password: {password}")
    print(f"Login URL: https://admin.orchpay.in")
    print("=" * 60)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
