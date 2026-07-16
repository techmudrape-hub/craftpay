"""
Test script for ClocksPay Payin Integration
Tests payment link creation and status check
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clockspay_service import clockspay_service
from database import get_db_connection
import json

def test_create_payment_link():
    """Test creating a payment link"""
    print("=" * 80)
    print("TEST: Create ClocksPay Payment Link")
    print("=" * 80)
    
    # Test merchant ID (replace with actual merchant ID from your database)
    merchant_id = "test_merchant_001"
    
    # Test order data
    order_data = {
        'amount': '100',
        'orderid': f'TEST_CLOCKSPAY_{int(time.time())}',
        'payee_fname': 'Alice',
        'payee_lname': 'Johnson',
        'payee_mobile': '9988776655',
        'payee_email': 'alice.j@example.com',
        'productinfo': 'Test Product',
        'callbackurl': 'https://api.craftpay.in/api/callback/clockspay/payin'
    }
    
    print(f"\nTest Data:")
    print(json.dumps(order_data, indent=2))
    
    # Create payment link
    result = clockspay_service.create_payin_order(merchant_id, order_data)
    
    print(f"\nResult:")
    print(json.dumps(result, indent=2, default=str))
    
    if result.get('success'):
        print("\n✅ Payment link created successfully!")
        print(f"Transaction ID: {result.get('txn_id')}")
        print(f"Order ID: {result.get('order_id')}")
        print(f"Payment Link: {result.get('payment_link')}")
        print(f"UPI Link: {result.get('upi_link')}")
        return result.get('order_id')
    else:
        print(f"\n❌ Failed to create payment link: {result.get('message')}")
        return None

def test_check_status(order_id):
    """Test checking payment status"""
    print("\n" + "=" * 80)
    print("TEST: Check ClocksPay Payment Status")
    print("=" * 80)
    
    print(f"\nChecking status for order: {order_id}")
    
    # Check status
    result = clockspay_service.check_payment_status(order_id)
    
    print(f"\nResult:")
    print(json.dumps(result, indent=2, default=str))
    
    if result.get('success'):
        print(f"\n✅ Status check successful!")
        print(f"Status: {result.get('status')}")
        print(f"Amount: {result.get('amount')}")
        print(f"UTR: {result.get('utr')}")
    else:
        print(f"\n❌ Status check failed: {result.get('message')}")

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

def test_config():
    """Test ClocksPay configuration"""
    print("=" * 80)
    print("TEST: ClocksPay Configuration")
    print("=" * 80)
    
    from config import Config
    
    print(f"Base URL: {Config.CLOCKSPAY_BASE_URL}")
    print(f"Token: {'*' * 10 if Config.CLOCKSPAY_TOKEN else 'NOT SET'}")
    
    if not Config.CLOCKSPAY_TOKEN:
        print("\n⚠ WARNING: CLOCKSPAY_TOKEN is not set in environment variables")
        print("Please add to .env file:")
        print("CLOCKSPAY_TOKEN=your_token_here")
        return False
    
    print("\n✅ Configuration looks good")
    return True

if __name__ == '__main__':
    import time
    
    print("\n" + "=" * 80)
    print("ClocksPay Payin Integration Test Suite")
    print("=" * 80 + "\n")
    
    # Test 1: Configuration
    if not test_config():
        print("\n❌ Configuration test failed. Please fix configuration before proceeding.")
        sys.exit(1)
    
    print("\n")
    
    # Test 2: Database Connection
    merchant_id = test_database_connection()
    if not merchant_id:
        print("\n❌ Database test failed. Please check database connection.")
        sys.exit(1)
    
    print("\n")
    
    # Test 3: Create Payment Link
    print("Do you want to test payment link creation? (y/n): ", end='')
    response = input().strip().lower()
    
    if response == 'y':
        order_id = test_create_payment_link()
        
        if order_id:
            print("\n")
            print("Do you want to test status check? (y/n): ", end='')
            response = input().strip().lower()
            
            if response == 'y':
                test_check_status(order_id)
    
    print("\n" + "=" * 80)
    print("Test Suite Complete")
    print("=" * 80)
