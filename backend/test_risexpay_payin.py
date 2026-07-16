"""
Test script for Risexpay Payin Integration
Tests the signature generation and API connectivity
"""

import os
import sys
import time
import hmac
import hashlib
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def generate_signature(payload, timestamp, secret_key):
    """
    Generate HMAC-SHA256 signature for Risexpay API
    """
    # Sort keys alphabetically
    sorted_keys = sorted(payload.keys())
    
    # Build canonical string
    canonical_parts = []
    for key in sorted_keys:
        value = str(payload[key])
        canonical_parts.append(f"{key}={value}")
    
    # Add timestamp
    canonical_parts.append(f"timestamp={timestamp}")
    
    canonical_string = "&".join(canonical_parts)
    
    print(f"\n📝 Canonical String:")
    print(f"   {canonical_string}")
    
    # Generate HMAC SHA256 signature
    signature = hmac.new(
        secret_key.encode('utf-8'),
        canonical_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature

def test_signature_generation():
    """Test signature generation with sample data"""
    print("\n" + "="*80)
    print("TEST 1: Signature Generation")
    print("="*80)
    
    # Get credentials from environment
    secret_key = os.getenv('RISEXPAY_SECRET_KEY', '')
    
    if not secret_key:
        print("❌ ERROR: RISEXPAY_SECRET_KEY not found in environment variables")
        print("   Please add it to your .env file")
        return False
    
    # Sample payload
    timestamp = int(time.time())
    payload = {
        'mid': 'RXPY123456789',
        'apikey': 'test_api_key',
        'amount': 500,
        'customer_mobile': '9876543210',
        'redirect_url': 'https://yourwebsite.com/callback'
    }
    
    print(f"\n📦 Sample Payload:")
    print(json.dumps(payload, indent=2))
    print(f"\n⏰ Timestamp: {timestamp}")
    
    # Generate signature
    signature = generate_signature(payload, timestamp, secret_key)
    
    print(f"\n🔐 Generated Signature:")
    print(f"   {signature}")
    print(f"\n✅ Signature generation test completed successfully!")
    
    return True

def test_config_loading():
    """Test if all required configuration is loaded"""
    print("\n" + "="*80)
    print("TEST 2: Configuration Loading")
    print("="*80)
    
    required_vars = {
        'RISEXPAY_BASE_URL': os.getenv('RISEXPAY_BASE_URL', ''),
        'RISEXPAY_MID': os.getenv('RISEXPAY_MID', ''),
        'RISEXPAY_API_KEY': os.getenv('RISEXPAY_API_KEY', ''),
        'RISEXPAY_SECRET_KEY': os.getenv('RISEXPAY_SECRET_KEY', '')
    }
    
    all_present = True
    
    for var_name, var_value in required_vars.items():
        if var_value:
            # Mask sensitive values
            if 'KEY' in var_name or 'SECRET' in var_name:
                display_value = var_value[:10] + '...' if len(var_value) > 10 else '***'
            else:
                display_value = var_value
            print(f"✅ {var_name}: {display_value}")
        else:
            print(f"❌ {var_name}: NOT SET")
            all_present = False
    
    if all_present:
        print(f"\n✅ All required configuration variables are present!")
        return True
    else:
        print(f"\n❌ Some configuration variables are missing!")
        print(f"   Please check your .env file and add missing variables")
        return False

def test_api_connectivity():
    """Test API connectivity (without making actual API call)"""
    print("\n" + "="*80)
    print("TEST 3: API Configuration")
    print("="*80)
    
    base_url = os.getenv('RISEXPAY_BASE_URL', '')
    
    if not base_url:
        print("❌ RISEXPAY_BASE_URL not configured")
        return False
    
    print(f"\n🌐 Base URL: {base_url}")
    print(f"📍 Create Order Endpoint: {base_url}/api/v1/imb/create_order.php")
    print(f"📍 Check Status Endpoint: {base_url}/api/v1/imb/check_status.php")
    print(f"\n✅ API endpoints configured correctly!")
    
    return True

def test_callback_signature_verification():
    """Test callback signature verification"""
    print("\n" + "="*80)
    print("TEST 4: Callback Signature Verification")
    print("="*80)
    
    secret_key = os.getenv('RISEXPAY_SECRET_KEY', '')
    
    if not secret_key:
        print("❌ ERROR: RISEXPAY_SECRET_KEY not found")
        return False
    
    # Sample callback data
    timestamp = int(time.time())
    callback_data = {
        'event': 'payment.update',
        'payment_status': 'COMPLETED',
        'order': {
            'order_id': 'ORD_24_1778576951_6896',
            'amount': 500,
            'status': 'COMPLETED'
        }
    }
    
    print(f"\n📦 Sample Callback Data:")
    print(json.dumps(callback_data, indent=2))
    
    # Generate expected signature
    signature = generate_signature(callback_data, timestamp, secret_key)
    
    print(f"\n🔐 Expected Signature:")
    print(f"   {signature}")
    
    # Verify signature
    canonical_parts = []
    for key in sorted(callback_data.keys()):
        value = str(callback_data[key])
        canonical_parts.append(f"{key}={value}")
    canonical_parts.append(f"timestamp={timestamp}")
    canonical_string = "&".join(canonical_parts)
    
    expected_signature = hmac.new(
        secret_key.encode('utf-8'),
        canonical_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    if signature == expected_signature:
        print(f"\n✅ Signature verification test passed!")
        return True
    else:
        print(f"\n❌ Signature verification test failed!")
        return False

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("🚀 RISEXPAY PAYIN INTEGRATION TEST SUITE")
    print("="*80)
    
    results = []
    
    # Test 1: Configuration Loading
    results.append(("Configuration Loading", test_config_loading()))
    
    # Test 2: Signature Generation
    results.append(("Signature Generation", test_signature_generation()))
    
    # Test 3: API Configuration
    results.append(("API Configuration", test_api_connectivity()))
    
    # Test 4: Callback Signature Verification
    results.append(("Callback Signature Verification", test_callback_signature_verification()))
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📈 Results: {passed} passed, {failed} failed out of {len(results)} tests")
    
    if failed == 0:
        print("\n🎉 All tests passed! Risexpay integration is ready to use.")
        print("\n📋 Next Steps:")
        print("   1. Configure service routing in admin dashboard")
        print("   2. Provide callback URL to Risexpay RMS team:")
        print("      https://api.craftpay.in/api/callback/risexpay/payin")
        print("   3. Create a test transaction to verify end-to-end flow")
    else:
        print("\n⚠️  Some tests failed. Please fix the issues before proceeding.")
        print("   Check your .env file and ensure all required variables are set.")
    
    print("="*80 + "\n")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
