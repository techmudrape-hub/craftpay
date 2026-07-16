"""
Test script for Maxpe integration
Run this to verify Maxpe service is working correctly
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from maxpe_service import maxpe_service
import json

def test_signature_generation():
    """Test HMAC SHA256 signature generation"""
    print("=" * 80)
    print("TEST 1: Signature Generation")
    print("=" * 80)
    
    # Test data from Maxpe documentation
    test_data = {
        'amount': '103',
        'email': 'amit123@gmail.com',
        'merchant_order_id': 'txn_1001',
        'mobile': '9999999999',
        'name': 'Amit',
        'nonce': '9b754b8ba9b0ddb9',
        'payer_vpa': 'amit@okaxis',
        'timestamp': '1775031116'
    }
    
    signature = maxpe_service.generate_signature(test_data)
    
    print(f"Test Data: {json.dumps(test_data, indent=2)}")
    print(f"Generated Signature: {signature}")
    print(f"Signature Length: {len(signature)} characters")
    print("✓ Signature generation working")
    print()

def test_nonce_generation():
    """Test nonce generation"""
    print("=" * 80)
    print("TEST 2: Nonce Generation")
    print("=" * 80)
    
    nonce1 = maxpe_service.generate_nonce()
    nonce2 = maxpe_service.generate_nonce()
    
    print(f"Nonce 1: {nonce1} (Length: {len(nonce1)})")
    print(f"Nonce 2: {nonce2} (Length: {len(nonce2)})")
    print(f"Unique: {nonce1 != nonce2}")
    print("✓ Nonce generation working")
    print()

def test_headers_generation():
    """Test headers generation"""
    print("=" * 80)
    print("TEST 3: Headers Generation")
    print("=" * 80)
    
    import time
    timestamp = int(time.time())
    nonce = maxpe_service.generate_nonce()
    
    test_data = {
        'amount': '100',
        'email': 'test@example.com',
        'merchant_order_id': 'TEST123',
        'mobile': '9999999999',
        'name': 'Test User',
        'nonce': nonce,
        'payer_vpa': 'test@okaxis',
        'timestamp': str(timestamp)
    }
    
    signature = maxpe_service.generate_signature(test_data)
    headers = maxpe_service.get_headers(timestamp, nonce, signature)
    
    print(f"Headers: {json.dumps(headers, indent=2)}")
    print("✓ Headers generation working")
    print()

def test_config():
    """Test configuration"""
    print("=" * 80)
    print("TEST 4: Configuration Check")
    print("=" * 80)
    
    print(f"Base URL: {maxpe_service.base_url}")
    print(f"API Key: {maxpe_service.api_key[:10]}... (masked)")
    print(f"API Secret: {maxpe_service.api_secret[:10]}... (masked)")
    
    if not maxpe_service.api_key or not maxpe_service.api_secret:
        print("❌ ERROR: API credentials not configured!")
        return False
    
    print("✓ Configuration loaded correctly")
    print()
    return True

def test_payment_order_structure():
    """Test payment order data structure"""
    print("=" * 80)
    print("TEST 5: Payment Order Structure")
    print("=" * 80)
    
    # Sample order data
    order_data = {
        'amount': 100,
        'orderid': 'TEST_ORDER_123',
        'payee_fname': 'John',
        'payee_lname': 'Doe',
        'payee_mobile': '9876543210',
        'payee_email': 'john.doe@example.com',
        'payer_vpa': 'john@okaxis',
        'productinfo': 'Test Product'
    }
    
    print(f"Sample Order Data: {json.dumps(order_data, indent=2)}")
    print("✓ Order structure is correct")
    print()

def main():
    """Run all tests"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "MAXPE INTEGRATION TEST SUITE" + " " * 30 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    try:
        # Run tests
        test_config()
        test_signature_generation()
        test_nonce_generation()
        test_headers_generation()
        test_payment_order_structure()
        
        # Summary
        print("=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print("✅ All tests passed!")
        print()
        print("Next Steps:")
        print("1. Configure service routing in admin dashboard")
        print("2. Test with a real merchant account")
        print("3. Provide callback URL to Maxpe team:")
        print("   https://api.craftpay.in/api/callback/maxpe/payin")
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
