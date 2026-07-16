#!/usr/bin/env python3
"""
Create OrchPay Admin User
Creates admin user with credentials: admin.orchpay.in / Admin@123
"""

import pymysql
import bcrypt
from config import Config

def create_orchpay_admin():
    """Create admin user for OrchPay"""
    try:
        print("=" * 80)
        print("Creating OrchPay Admin User")
        print("=" * 80)
        print()
        
        # Connect to database
        print("Connecting to database...")
        connection = pymysql.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            # Admin credentials
            admin_id = "admin.orchpay.in"
            password = "Admin@123"
            
            # Hash password
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Check if admin already exists
            cursor.execute("SELECT admin_id FROM admin_users WHERE admin_id = %s", (admin_id,))
            existing_admin = cursor.fetchone()
            
            if existing_admin:
                print(f"⚠️  Admin user '{admin_id}' already exists")
                print("Updating password...")
                
                cursor.execute("""
                    UPDATE admin_users 
                    SET password_hash = %s,
                        is_active = TRUE,
                        must_change_password = FALSE,
                        login_attempts = 0,
                        locked_until = NULL
                    WHERE admin_id = %s
                """, (password_hash, admin_id))
                
                connection.commit()
                print(f"✅ Admin user '{admin_id}' password updated successfully")
            else:
                print(f"Creating new admin user '{admin_id}'...")
                
                cursor.execute("""
                    INSERT INTO admin_users (
                        admin_id,
                        password_hash,
                        pin_hash,
                        is_active,
                        must_change_password,
                        login_attempts,
                        locked_until,
                        last_login,
                        created_at,
                        updated_at
                    ) VALUES (
                        %s, %s, NULL, TRUE, FALSE, 0, NULL, NULL, NOW(), NOW()
                    )
                """, (admin_id, password_hash))
                
                connection.commit()
                print(f"✅ Admin user '{admin_id}' created successfully")
            
            print()
            print("=" * 80)
            print("Admin Credentials:")
            print("=" * 80)
            print(f"Username: {admin_id}")
            print(f"Password: {password}")
            print("=" * 80)
            print()
            print("✅ You can now login to the admin panel with these credentials")
            print()
            
        connection.close()
        return True
        
    except pymysql.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = create_orchpay_admin()
    exit(0 if success else 1)
