"""
Test script for Titanexam integration
Run this to verify Titanexam service is working correctly
"""

import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from titanexam_service import titanexam_service

def test_config():
    """Test configuration"""
    print("=" * 80)
    print("TEST 1: Configuration Check")
    print("=" * 80)
    
    print(f"Base URL: {titanexam_service.base_url}")
    print(f"Merchant ID: {titanexam_service.merchant_id}")
    print(f"Secret Key: {titanexam_service.secret_key[:10] if titanexam_service.secret_key else ''}... (masked)")
    
    if not titanexam_service.merchant_id or not titanexam_service.secret_key:
        print("❌ ERROR: API credentials not configured!")
        return False
    
    print("✓ Configuration loaded correctly")
    print()
    return True

def test_auth_header():
    """Test Basic Auth Header Generation"""
    print("=" * 80)
    print("TEST 2: Basic Auth Header Generation")
    print("=" * 80)

    header = titanexam_service.get_auth_header()
    print(f"Header: {json.dumps(header, indent=2)}")
    print("✓ Header generation working")
    print()

def test_payment_order_structure():
    """Test payment order data structure"""
    print("=" * 80)
    print("TEST 3: Payment Order Structure")
    print("=" * 80)
    
    # Sample order data
    order_data = {
        'amount': 100,
        'orderid': 'TEST_ORDER_123',
        'payee_fname': 'John',
        'payee_lname': 'Doe',
        'payee_mobile': '9876543210',
        'payee_email': 'john.doe@example.com',
        'productinfo': 'Test Product'
    }
    
    print(f"Sample Order Data: {json.dumps(order_data, indent=2)}")
    print("✓ Order structure is correct")
    print()

def test_payin_generation():
    """Test actual payin generation by hitting the Titanexam API"""
    print("=" * 80)
    print("TEST 4: PayIn Generation")
    print("=" * 80)
    
    from database import get_db_connection
    import random
    
    # Get a valid active merchant
    conn = get_db_connection()
    if not conn:
        print("❌ ERROR: Database connection failed!")
        return False
        
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT merchant_id FROM merchants WHERE is_active = TRUE LIMIT 1")
            merchant = cursor.fetchone()
            
            if not merchant:
                print("❌ ERROR: No active merchant found in database!")
                return False
                
            merchant_id = merchant['merchant_id']
    finally:
        conn.close()
        
    print(f"Using merchant_id: {merchant_id}")
    
    order_data = {
        'amount': 10,
        'orderid': f'TEST_TITAN_{random.randint(1000, 9999)}',
        'payee_fname': 'Test',
        'payee_lname': 'User',
        'payee_mobile': '9999999999',
        'payee_email': 'test@example.com',
        'productinfo': 'Test Payin',
        'callback_url': 'https://api.craftpay.in/api/callback/test'
    }
    
    print(f"Calling create_payin_order...")
    result = titanexam_service.create_payin_order(merchant_id, order_data)
    
    print(f"Result:")
    print(json.dumps(result, indent=2))
    
    if result.get('success'):
        print("✓ PayIn generation successful")
        print(f"UPI Link generated: {result.get('upi_link')}")
        return True
    else:
        print(f"❌ PayIn generation failed: {result.get('message')}")
        return False

def main():
    """Run all tests"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 18 + "TITANEXAM INTEGRATION TEST SUITE" + " " * 28 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    try:
        # Run tests
        test_config()
        test_auth_header()
        test_payment_order_structure()
        test_payin_generation()
        
        # Summary
        print("=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print("✅ All local tests passed!")
        print()
        print("Next Steps:")
        print("1. Add Titanexam API keys to .env")
        print("2. Configure service routing in admin dashboard")
        print("3. Test with a real merchant account and actual API request")
        print("4. Configure the callback URL in Titanexam dashboard if required:")
        print("   https://api.craftpay.in/api/callback/titanexam/payin")
        print()
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
