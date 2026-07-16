"""
Test script for Risexpay Payin - Real Transaction Test
Tests actual API call with 100 rupees
"""

import os
import sys
import time
import hmac
import hashlib
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def generate_signature(payload, timestamp, secret_key):
    """
    Generate HMAC-SHA256 signature for Risexpay API
    
    IMPORTANT: The exact canonical string format is provided by Risexpay Integration Helper Package.
    This implementation follows the standard pattern, but may need adjustment based on
    Risexpay's specific requirements.
    """
    # Sort keys alphabetically
    sorted_keys = sorted(payload.keys())
    
    # Build canonical string: key=value&key=value
    canonical_parts = []
    for key in sorted_keys:
        value = str(payload[key])
        canonical_parts.append(f"{key}={value}")
    
    # Add timestamp to canonical string
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
    
    return signature, canonical_string

def test_create_order_100_rupees():
    """Test creating a real payment order with 100 rupees"""
    print("\n" + "="*80)
    print("🚀 RISEXPAY PAYIN - REAL TRANSACTION TEST (₹100)")
    print("="*80)
    
    # Get credentials from environment
    base_url = os.getenv('RISEXPAY_BASE_URL', 'https://risexpay.in')
    mid = os.getenv('RISEXPAY_MID', '')
    api_key = os.getenv('RISEXPAY_API_KEY', '')
    secret_key = os.getenv('RISEXPAY_SECRET_KEY', '')
    
    # Validate credentials
    if not all([mid, api_key, secret_key]):
        print("\n❌ ERROR: Missing required credentials")
        print("   Please ensure the following are set in your .env file:")
        print("   - RISEXPAY_MID")
        print("   - RISEXPAY_API_KEY")
        print("   - RISEXPAY_SECRET_KEY")
        return False
    
    print(f"\n📋 Configuration:")
    print(f"   Base URL: {base_url}")
    print(f"   MID: {mid}")
    print(f"   API Key: {api_key[:10]}...")
    print(f"   Secret Key: {secret_key[:10]}...")
    
    # Generate timestamp
    timestamp = int(time.time())
    
    # Prepare payload
    payload = {
        'mid': mid,
        'apikey': api_key,
        'amount': 100,  # 100 rupees
        'customer_mobile': '9876543210',
        'redirect_url': 'https://api.craftpay.in/api/callback/risexpay/payin'
    }
    
    print(f"\n📦 Request Payload:")
    print(json.dumps(payload, indent=2))
    print(f"\n⏰ Timestamp: {timestamp}")
    
    # Generate signature
    signature, canonical_string = generate_signature(payload, timestamp, secret_key)
    
    print(f"\n🔐 Signature Details:")
    print(f"   Canonical String: {canonical_string}")
    print(f"   Generated Signature: {signature}")
    
    # Prepare headers
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Timestamp': str(timestamp),
        'X-Signature': signature
    }
    
    print(f"\n📤 Request Headers:")
    for key, value in headers.items():
        if key == 'X-Signature':
            print(f"   {key}: {value[:20]}...")
        else:
            print(f"   {key}: {value}")
    
    # API endpoint
    url = f"{base_url}/api/v1/imb/create_order.php"
    print(f"\n🌐 API Endpoint: {url}")
    
    # Make API request
    print(f"\n🔄 Sending request to Risexpay...")
    
    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"\n📥 Response Status: {response.status_code}")
        print(f"📄 Response Headers:")
        for key, value in response.headers.items():
            if key.lower() in ['x-timestamp', 'x-signature', 'content-type']:
                print(f"   {key}: {value}")
        
        print(f"\n📄 Response Body:")
        try:
            response_json = response.json()
            print(json.dumps(response_json, indent=2))
            
            # Check if successful
            if response.status_code == 200 and response_json.get('status'):
                print(f"\n✅ SUCCESS! Payment order created successfully!")
                
                data = response_json.get('data', {})
                print(f"\n💳 Payment Details:")
                print(f"   Order ID: {data.get('order_id', 'N/A')}")
                print(f"   IMB Order ID: {data.get('imb_order_id', 'N/A')}")
                print(f"   Amount: ₹{data.get('amount', 'N/A')}")
                print(f"   Payment URL: {data.get('payment_url', 'N/A')}")
                print(f"   BHIM Link: {data.get('bhim_link', 'N/A')[:50]}...")
                print(f"   Paytm Link: {data.get('paytm_link', 'N/A')[:50]}...")
                
                return True
            else:
                print(f"\n❌ FAILED! Error from Risexpay:")
                print(f"   Message: {response_json.get('message', 'Unknown error')}")
                
                # If signature error, provide debugging help
                if 'signature' in response_json.get('message', '').lower():
                    print(f"\n🔍 SIGNATURE ERROR DEBUGGING:")
                    print(f"   1. Verify RISEXPAY_SECRET_KEY is correct")
                    print(f"   2. Check if there are any extra spaces or quotes in the key")
                    print(f"   3. Contact Risexpay support for the Integration Helper Package")
                    print(f"   4. The canonical string format might need adjustment")
                    print(f"\n   Current canonical string format:")
                    print(f"   {canonical_string}")
                    print(f"\n   Alternative formats to try:")
                    print(f"   - Without timestamp in canonical string")
                    print(f"   - Different field ordering")
                    print(f"   - Different separator characters")
                
                return False
        except json.JSONDecodeError:
            print(response.text)
            print(f"\n❌ Failed to parse JSON response")
            return False
            
    except requests.exceptions.Timeout:
        print(f"\n❌ Request timeout after 30 seconds")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ Connection error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_alternative_signature_formats():
    """Test alternative signature generation formats"""
    print("\n" + "="*80)
    print("🔍 TESTING ALTERNATIVE SIGNATURE FORMATS")
    print("="*80)
    
    secret_key = os.getenv('RISEXPAY_SECRET_KEY', '')
    
    if not secret_key:
        print("❌ RISEXPAY_SECRET_KEY not found")
        return
    
    timestamp = int(time.time())
    payload = {
        'mid': os.getenv('RISEXPAY_MID', 'TEST'),
        'apikey': os.getenv('RISEXPAY_API_KEY', 'TEST'),
        'amount': 100,
        'customer_mobile': '9876543210',
        'redirect_url': 'https://api.craftpay.in/api/callback/risexpay/payin'
    }
    
    print(f"\n📦 Test Payload:")
    print(json.dumps(payload, indent=2))
    print(f"⏰ Timestamp: {timestamp}")
    
    # Format 1: Standard format (current implementation)
    print(f"\n1️⃣  Format 1: key=value&key=value&timestamp={timestamp}")
    sorted_keys = sorted(payload.keys())
    canonical_parts = []
    for key in sorted_keys:
        canonical_parts.append(f"{key}={payload[key]}")
    canonical_parts.append(f"timestamp={timestamp}")
    canonical_string_1 = "&".join(canonical_parts)
    signature_1 = hmac.new(secret_key.encode('utf-8'), canonical_string_1.encode('utf-8'), hashlib.sha256).hexdigest()
    print(f"   Canonical: {canonical_string_1}")
    print(f"   Signature: {signature_1}")
    
    # Format 2: Without timestamp in canonical string
    print(f"\n2️⃣  Format 2: key=value&key=value (no timestamp)")
    canonical_parts = []
    for key in sorted_keys:
        canonical_parts.append(f"{key}={payload[key]}")
    canonical_string_2 = "&".join(canonical_parts)
    signature_2 = hmac.new(secret_key.encode('utf-8'), canonical_string_2.encode('utf-8'), hashlib.sha256).hexdigest()
    print(f"   Canonical: {canonical_string_2}")
    print(f"   Signature: {signature_2}")
    
    # Format 3: JSON string
    print(f"\n3️⃣  Format 3: JSON string")
    json_string = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    signature_3 = hmac.new(secret_key.encode('utf-8'), json_string.encode('utf-8'), hashlib.sha256).hexdigest()
    print(f"   Canonical: {json_string}")
    print(f"   Signature: {signature_3}")
    
    # Format 4: Timestamp + JSON
    print(f"\n4️⃣  Format 4: timestamp + JSON")
    canonical_string_4 = f"{timestamp}{json_string}"
    signature_4 = hmac.new(secret_key.encode('utf-8'), canonical_string_4.encode('utf-8'), hashlib.sha256).hexdigest()
    print(f"   Canonical: {canonical_string_4}")
    print(f"   Signature: {signature_4}")
    
    print(f"\n💡 TIP: Contact Risexpay support (support@risexpay.in) for the")
    print(f"   Integration Helper Package which contains the exact canonical")
    print(f"   string format required for signature generation.")

def main():
    """Run the test"""
    print("\n" + "="*80)
    print("🧪 RISEXPAY PAYIN INTEGRATION - REAL TRANSACTION TEST")
    print("="*80)
    
    # Test 1: Create order with 100 rupees
    success = test_create_order_100_rupees()
    
    if not success:
        print("\n" + "="*80)
        print("⚠️  Transaction failed. Testing alternative signature formats...")
        print("="*80)
        test_alternative_signature_formats()
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    if success:
        print("✅ Transaction test PASSED")
        print("\n🎉 Risexpay integration is working correctly!")
        print("\n📋 Next Steps:")
        print("   1. Configure service routing in admin dashboard")
        print("   2. Test with real customer transactions")
        print("   3. Monitor callbacks and wallet credits")
    else:
        print("❌ Transaction test FAILED")
        print("\n🔍 Troubleshooting Steps:")
        print("   1. Verify all credentials in .env file are correct")
        print("   2. Check if credentials are for the correct environment (test/production)")
        print("   3. Contact Risexpay support for Integration Helper Package")
        print("   4. Email: support@risexpay.in")
        print("   5. Request the exact canonical string format for signature generation")
        print("\n💡 The signature format might need adjustment based on Risexpay's")
        print("   specific requirements. The Integration Helper Package will provide")
        print("   the exact implementation for your programming language.")
    
    print("="*80 + "\n")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
