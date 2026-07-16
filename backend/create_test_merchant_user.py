#!/usr/bin/env python3
"""
Create Test Merchant User
=========================
Creates a test merchant account for testing the merchant portal.

Merchant Credentials:
- Merchant ID: TEST001
- Password: Test@123
- PIN: 1234
"""

import pymysql
import bcrypt
import secrets
import base64
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from config import Config

def generate_keys():
    """Generate authorization key, module secret, AES key and IV"""
    authorization_key = secrets.token_urlsafe(32)
    module_secret = secrets.token_urlsafe(32)
    aes_key = base64.b64encode(get_random_bytes(32)).decode('utf-8')
    aes_iv = base64.b64encode(get_random_bytes(16)).decode('utf-8')
    
    return authorization_key, module_secret, aes_key, aes_iv

def create_test_merchant():
    """Create a test merchant account"""
    try:
        # Connect to database
        connection = pymysql.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        print("=" * 60)
        print("Creating Test Merchant Account")
        print("=" * 60)
        
        with connection.cursor() as cursor:
            # Check if admin exists (required for foreign key)
            cursor.execute("SELECT admin_id FROM admin_users LIMIT 1")
            admin = cursor.fetchone()
            
            if not admin:
                print("\n❌ Error: No admin user found!")
                print("Please create an admin user first using create_admin_user.py")
                return False
            
            admin_id = admin['admin_id']
            
            # Check if merchant already exists
            cursor.execute("SELECT merchant_id FROM merchants WHERE merchant_id = 'TEST001'")
            if cursor.fetchone():
                print("\n⚠️  Merchant TEST001 already exists!")
                print("\nDeleting existing merchant...")
                
                # Delete related records first (foreign key constraints)
                cursor.execute("DELETE FROM merchant_documents WHERE merchant_id = 'TEST001'")
                cursor.execute("DELETE FROM merchant_ip_whitelist WHERE merchant_id = 'TEST001'")
                cursor.execute("DELETE FROM merchant_callbacks WHERE merchant_id = 'TEST001'")
                cursor.execute("DELETE FROM merchant_banks WHERE merchant_id = 'TEST001'")
                cursor.execute("DELETE FROM merchant_wallet WHERE merchant_id = 'TEST001'")
                cursor.execute("DELETE FROM merchant_unsettled_wallet WHERE merchant_id = 'TEST001'")
                cursor.execute("DELETE FROM payin_transactions WHERE merchant_id = 'TEST001'")
                cursor.execute("DELETE FROM payout_transactions WHERE merchant_id = 'TEST001'")
                cursor.execute("DELETE FROM wallet_transactions WHERE merchant_id = 'TEST001'")
                cursor.execute("DELETE FROM service_routing WHERE merchant_id = 'TEST001'")
                cursor.execute("DELETE FROM fund_requests WHERE merchant_id = 'TEST001'")
                cursor.execute("DELETE FROM merchants WHERE merchant_id = 'TEST001'")
                connection.commit()
                print("✓ Existing merchant deleted")
            
            # Generate credentials
            merchant_id = 'TEST001'
            password = 'Test@123'
            pin = '1234'
            
            # Hash password and PIN
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            pin_hash = bcrypt.hashpw(pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Generate API keys
            authorization_key, module_secret, aes_key, aes_iv = generate_keys()
            
            # Create merchant
            print("\n📝 Creating merchant account...")
            cursor.execute("""
                INSERT INTO merchants (
                    merchant_id, password_hash, pin_hash,
                    full_name, email, mobile,
                    aadhar_card, pan_no, pincode, state, city,
                    address,
                    merchant_type, account_number, ifsc_code, gst_no,
                    authorization_key, module_secret, aes_iv, aes_key,
                    is_active, created_by, scheme_id
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
            """, (
                merchant_id, password_hash, pin_hash,
                'Test Merchant', 'test@orchpay.com', '9999999999',
                '123456789012', 'ABCDE1234F', '110001', 'Delhi', 'New Delhi',
                'Test Address, Test Street, New Delhi',
                'BOTH', '1234567890', 'SBIN0001234', '29ABCDE1234F1',
                authorization_key, module_secret, aes_iv, aes_key,
                True, admin_id, 1
            ))
            
            # Create merchant wallet
            print("💰 Creating merchant wallet...")
            cursor.execute("""
                INSERT INTO merchant_wallet (merchant_id, balance)
                VALUES (%s, 10000.00)
            """, (merchant_id,))
            
            # Create merchant unsettled wallet
            cursor.execute("""
                INSERT INTO merchant_unsettled_wallet (merchant_id, balance)
                VALUES (%s, 0.00)
            """, (merchant_id,))
            
            # Create merchant documents entry
            print("📄 Creating documents entry...")
            cursor.execute("""
                INSERT INTO merchant_documents (merchant_id)
                VALUES (%s)
            """, (merchant_id,))
            
            # Create merchant callbacks
            print("🔗 Creating callback URLs...")
            cursor.execute("""
                INSERT INTO merchant_callbacks (
                    merchant_id, payin_callback_url, payout_callback_url
                ) VALUES (%s, %s, %s)
            """, (
                merchant_id,
                'https://test.orchpay.com/payin/callback',
                'https://test.orchpay.com/payout/callback'
            ))
            
            # Create a test bank account
            print("🏦 Creating bank account...")
            cursor.execute("""
                INSERT INTO merchant_banks (
                    merchant_id, bank_name, account_number, ifsc_code,
                    account_holder_name, account_type, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                merchant_id, 'State Bank of India', '1234567890', 'SBIN0001234',
                'Test Merchant', 'SAVINGS', True
            ))
            
            connection.commit()
            
            print("\n" + "=" * 60)
            print("✅ Test Merchant Created Successfully!")
            print("=" * 60)
            print("\n📋 Merchant Credentials:")
            print(f"   Merchant ID: {merchant_id}")
            print(f"   Password: {password}")
            print(f"   PIN: {pin}")
            print("\n💰 Wallet Balance:")
            print(f"   Main Balance: ₹10,000.00")
            print(f"   Unsettled Balance: ₹0.00")
            print("\n🔑 API Credentials:")
            print(f"   Authorization Key: {authorization_key}")
            print(f"   Module Secret: {module_secret}")
            print("\n🌐 Login URL:")
            print(f"   http://localhost:5173 (Merchant Portal)")
            print("\n" + "=" * 60)
            
            return True
            
    except Exception as e:
        print(f"\n❌ Error creating test merchant: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if connection:
            connection.close()

if __name__ == '__main__':
    create_test_merchant()
