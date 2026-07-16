#!/usr/bin/env python3
"""
Simple Admin User Creation
Creates admin user: admin.orchpay.in / Admin@123
"""

import pymysql
import bcrypt
from config import Config

def create_admin():
    """Create admin user"""
    try:
        print("Creating OrchPay Admin User...")
        print()
        
        # Connect to database
        connection = pymysql.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False
        )
        
        cursor = connection.cursor()
        
        # Admin credentials
        admin_id = "admin.orchpay.in"
        password = "Admin@123"
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Check if admin exists
        cursor.execute("SELECT admin_id FROM admin_users WHERE admin_id = %s", (admin_id,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"Admin '{admin_id}' already exists. Updating password...")
            cursor.execute("""
                UPDATE admin_users 
                SET password_hash = %s, is_active = 1, must_change_password = 0
                WHERE admin_id = %s
            """, (password_hash, admin_id))
        else:
            print(f"Creating admin '{admin_id}'...")
            cursor.execute("""
                INSERT INTO admin_users 
                (admin_id, password_hash, is_active, must_change_password, created_at, updated_at) 
                VALUES (%s, %s, 1, 0, NOW(), NOW())
            """, (admin_id, password_hash))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print()
        print("=" * 60)
        print("✅ Admin User Created Successfully!")
        print("=" * 60)
        print(f"Username: {admin_id}")
        print(f"Password: {password}")
        print("=" * 60)
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    create_admin()
