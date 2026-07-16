#!/usr/bin/env python3
"""
Fix Tablespace Issues and Create Admin User
This script handles orphaned tablespace files and creates the admin user
"""

import pymysql
import bcrypt
from config import Config

def fix_tablespace_and_create_admin():
    """Fix tablespace issues and create admin user"""
    try:
        print("=" * 80)
        print("Fixing Tablespace and Creating Admin User")
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
        
        # Use the database
        print(f"Step 2: Using database '{Config.DB_NAME}'...")
        try:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            connection.commit()
        except Exception as e:
            print(f"Note: {e}")
        
        cursor.execute(f"USE {Config.DB_NAME}")
        print(f"✅ Using database '{Config.DB_NAME}'")
        print()
        
        # Drop admin_users table if it exists (to clear tablespace issues)
        print("Step 3: Cleaning up existing admin_users table...")
        try:
            cursor.execute("DROP TABLE IF EXISTS admin_users")
            connection.commit()
            print("✅ Cleaned up existing table")
        except Exception as e:
            print(f"Note: {e}")
        print()
        
        # Create admin_users table
        print("Step 4: Creating admin_users table...")
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
                password_changed_at DATETIME DEFAULT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        connection.commit()
        print("✅ admin_users table created")
        print()
        
        # Create admin_activity_logs table if it doesn't exist
        print("Step 5: Creating admin_activity_logs table...")
        try:
            cursor.execute("DROP TABLE IF EXISTS admin_activity_logs")
            cursor.execute("""
                CREATE TABLE admin_activity_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    admin_id VARCHAR(50) NOT NULL,
                    action VARCHAR(100) NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    details TEXT,
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_admin_id (admin_id),
                    INDEX idx_created_at (created_at),
                    INDEX idx_action (action),
                    INDEX idx_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            connection.commit()
            print("✅ admin_activity_logs table created")
        except Exception as e:
            print(f"Note: {e}")
        print()
        
        # Create admin user
        print("Step 6: Creating admin user...")
        admin_id = "admin.orchpay.in"
        password = "Admin@123"
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Check if admin already exists
        cursor.execute("SELECT admin_id FROM admin_users WHERE admin_id = %s", (admin_id,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"Admin user '{admin_id}' already exists, updating password...")
            cursor.execute("""
                UPDATE admin_users 
                SET password_hash = %s, 
                    is_active = 1, 
                    must_change_password = 0,
                    login_attempts = 0,
                    locked_until = NULL
                WHERE admin_id = %s
            """, (password_hash, admin_id))
        else:
            cursor.execute("""
                INSERT INTO admin_users 
                (admin_id, password_hash, is_active, must_change_password) 
                VALUES (%s, %s, 1, 0)
            """, (admin_id, password_hash))
        
        connection.commit()
        print("✅ Admin user created/updated")
        print()
        
        # Verify
        cursor.execute("SELECT admin_id, is_active FROM admin_users WHERE admin_id = %s", (admin_id,))
        admin = cursor.fetchone()
        
        if admin:
            print("=" * 80)
            print("✅ SUCCESS! Admin User Ready")
            print("=" * 80)
            print(f"Username: {admin_id}")
            print(f"Password: {password}")
            print(f"Active: {'Yes' if admin['is_active'] else 'No'}")
            print("=" * 80)
            print()
            print("You can now:")
            print("1. Start the Flask server: python app.py")
            print("2. Login to the admin panel with the credentials above")
            print()
            print("Note: Other tables (merchants, transactions, etc.) will be")
            print("created automatically when needed, or you can run:")
            print("python create_complete_database.py")
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
    success = fix_tablespace_and_create_admin()
    exit(0 if success else 1)
