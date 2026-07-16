"""
Test script for OQPay Payin Integration
Tests order creation and database recording
"""

import sys
import os
import time
from dotenv import load_dotenv

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oqpay_service import oqpay_service
from database import get_db_connection
import json

# Load env
load_dotenv()

def test_config():
    """Test ClocksPay/OQPay configuration"""
    print("=" * 80)
    print("TEST: OQPay Configuration")
    print("=" * 80)
    
    from config import Config
    
    print(f"Payin Base URL: {Config.OQPAY_PAYIN_BASE_URL}")
    print(f"Payout Base URL: {Config.OQPAY_PAYOUT_BASE_URL}")
    print(f"Registration ID: {Config.OQPAY_REGISTRATION_ID}")
    
    if not Config.OQPAY_REGISTRATION_ID or Config.OQPAY_REGISTRATION_ID == "OQP-XXXX":
        print("\n⚠ WARNING: OQPAY_REGISTRATION_ID is not properly set in environment variables")
        print("Please check your .env file.")
        return False
    
    print("\n✅ Configuration looks good")
    return True

def test_database_connection():
    """Test database connection"""
    print("=" * 80)
    print("TEST: Database Connection")
    print("=" * 80)
    
    conn = get_db_connection()
    if conn:
        print("✅ Database connection successful")
        
        # Check if test merchant exists
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT merchant_id, full_name, email, scheme_id, is_active
                    FROM merchants
                    LIMIT 1
                """)
                merchant = cursor.fetchone()
                
                if merchant:
                    print(f"\nSample Merchant Found:")
                    print(f"  Merchant ID: {merchant['merchant_id']}")
                    print(f"  Name: {merchant['full_name']}")
                    print(f"  Email: {merchant['email']}")
                    print(f"  Scheme ID: {merchant['scheme_id']}")
                    print(f"  Active: {merchant['is_active']}")
                    return merchant['merchant_id']
                else:
                    print("\n⚠ No merchants found in database")
                    return None
        finally:
            conn.close()
    else:
        print("❌ Database connection failed")
        return None

def test_create_payin_order(merchant_id):
    """Test creating a payin order"""
    print("=" * 80)
    print("TEST: Create OQPay Dynamic QR Payin Order")
    print("=" * 80)
    
    if not merchant_id:
        print("❌ No merchant_id available for test")
        return None
        
    order_data = {
        'amount': '50',
        'orderid': f'TEST_OQ_{int(time.time())}',
        'payee_fname': 'Alice',
        'payee_lname': 'Tester',
        'payee_mobile': '9876543210',
        'payee_email': 'alice.test@gmail.com',
        'productinfo': 'Test product payin',
        'callbackurl': 'https://api.craftpay.in/api/callback/oqpay/payin'
    }
    
    print(f"\nTest Data:")
    print(json.dumps(order_data, indent=2))
    
    # Try calling OQPay order creation
    result = oqpay_service.create_payin_order(merchant_id, order_data)
    
    print(f"\nResult:")
    print(json.dumps(result, indent=2, default=str))
    
    if result.get('success'):
        print("\n✅ Payin Order / Dynamic QR created successfully!")
        print(f"Transaction ID: {result.get('txn_id')}")
        print(f"Order ID: {result.get('order_id')}")
        print(f"UPI intent/link: {result.get('upi_link')}")
        return result.get('order_id')
    else:
        print(f"\n❌ Failed to create order: {result.get('message')}")
        return None

if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("OQPay Payin Integration Test Suite")
    print("=" * 80 + "\n")
    
    # Test 1: Configuration
    config_ok = test_config()
    print("\n")
    
    # Test 2: Database Connection
    merchant_id = test_database_connection()
    print("\n")
    
    # Test 3: Create order (only if database and config are fine)
    if merchant_id:
        print("Do you want to test order creation? (y/n): ", end='')
        response = input().strip().lower() if sys.stdin.isatty() else 'n'
        
        # If running automatically or 'y', run it
        if response == 'y' or not sys.stdin.isatty():
            test_create_payin_order(merchant_id)
            
    print("\n" + "=" * 80)
    print("Test Suite Complete")
    print("=" * 80)
