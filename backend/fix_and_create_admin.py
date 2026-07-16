#!/usr/bin/env python3
"""
Fix Database and Create Admin User
Ensures admin_users table exists and creates admin user
"""

import pymysql
import bcrypt
from config import Config

def fix_and_create_admin():
    """Fix database and create admin user"""
    try:
        print("=" * 80)
        print("Fixing Database and Creating Admin User")
        print("=" * 80)
        print()
        
        # Connect to MySQL server
        print("Step 1: Connecting to MySQL...")
        connection = pymysql.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        cursor = connection.cursor()
        
        # Create database if not exists
        print("Step 2: Creating/verifying database...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME}")
        cursor.execute(f"USE {Config.DB_NAME}")
        connection.commit()
        print(f"✅ Database '{Config.DB_NAME}' ready")
        print()
        
        # Drop and recreate admin_users table
        print("Step 3: Creating admin_users table...")
        cursor.execute("DROP TABLE IF EXISTS admin_users")
        cursor.execute("""
            CREATE TABLE admin_users (
                admin_id VARCHAR(50) PRIMARY KEY,
                password_hash VARCHAR(255) NOT NULL,
                pin_hash VARCHAR(255) DEFAULT NULL,
                is_active TINYINT(1) DEFAULT 1,
                must_change_password TINYINT(1) DEFAULT 0,
                login_attempts INT DEFAULT 0,
                locked_until DATETIME DEFAULT NULL,
                last_login DATETIME DEFAULT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        connection.commit()
        print("✅ admin_users table created")
        print()
        
        # Create admin user
        print("Step 4: Creating admin user...")
        admin_id = "admin.orchpay.in"
        password = "Admin@123"
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        cursor.execute("""
            INSERT INTO admin_users 
            (admin_id, password_hash, is_active, must_change_password) 
            VALUES (%s, %s, 1, 0)
        """, (admin_id, password_hash))
        
        connection.commit()
        print("✅ Admin user created")
        print()
        
        # Verify
        cursor.execute("SELECT admin_id, is_active FROM admin_users WHERE admin_id = %s", (admin_id,))
        admin = cursor.fetchone()
        
        if admin:
            print("=" * 80)
            print("✅ SUCCESS! Admin User Created")
            print("=" * 80)
            print(f"Username: {admin_id}")
            print(f"Password: {password}")
            print(f"Active: {'Yes' if admin['is_active'] else 'No'}")
            print("=" * 80)
            print()
            print("You can now login to the admin panel!")
            print()
        else:
            print("❌ Failed to verify admin user")
            return False
        
        cursor.close()
        connection.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = fix_and_create_admin()
    exit(0 if success else 1)
