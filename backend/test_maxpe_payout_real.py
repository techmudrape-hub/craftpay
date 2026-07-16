"""
Test MaxPe Payout with Real Credentials
This script tests the payout API with the actual credentials
"""

import hmac
import hashlib
import time
import uuid
import requests
from urllib.parse import urlencode, unquote

# Real credentials
API_KEY = "537a3441b91c8cf767362c9647d4fc6fd3f2"
API_SECRET = "a0fb8bb4e88226fc62b7bd121507741fac1442a12242acb8b486856514c011a6cb4b4b020c7b4e8ea451c375d7"
BASE_URL = "https://merchant.maxpe.tech"

def generate_nonce():
    """Generate unique nonce (16 character hex)"""
    return uuid.uuid4().hex[:16]

def generate_signature(data_to_sign, api_secret):
    """
    Generate HMAC SHA256 signature - SAME as working payin service
    """
    # Sort keys alphabetically
    sorted_keys = sorted(data_to_sign.keys())
    
    # Build canonical string: key=value&key=value
    canonical_parts = []
    for key in sorted_keys:
        value = str(data_to_sign[key])
        canonical_parts.append(f"{key}={value}")
    
    canonical_string = "&".join(canonical_parts)
    
    # Generate HMAC SHA256 signature
    signature = hmac.new(
        api_secret.encode('utf-8'),
        canonical_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return canonical_string, signature

def test_payout():
    """Test payout API call"""
    
    print("="*80)
    print("MaxPe Payout API Test - Real Credentials")
    print("="*80)
    
    # Generate timestamp and nonce
    timestamp = int(time.time())
    nonce = generate_nonce()
    
    # Test payout data (small amount)
    merchant_order_id = f"TEST_{timestamp}"
    
    # Data to sign (10 fields - NO latitude/longitude)
    data_to_sign = {
        'merchant_order_id': merchant_order_id,
        'payee_name': 'Test User',
        'payee_account_number': '1234567890',
        'ifsc': 'ICIC0000001',
        'bank': 'ICICI BANK',
        'amount': '10',
        'email': 'test@example.com',
        'mobile': '9999999999',
        'timestamp': str(timestamp),
        'nonce': nonce
    }
    
    print(f"\nTest Data:")
    for key, value in data_to_sign.items():
        print(f"  {key}: {value}")
    
    # Generate signature
    canonical_string, signature = generate_signature(data_to_sign, API_SECRET)
    
    print(f"\nSignature Generation:")
    print(f"  Canonical String: {canonical_string}")
    print(f"  Signature: {signature}")
    
    # Prepare headers
    headers = {
        'Accept': 'application/json',
        'X-API-KEY': API_KEY,
        'X-TIMESTAMP': str(timestamp),
        'X-NONCE': nonce,
        'X-SIGNATURE': signature
    }
    
    # Prepare payload (form data - includes latitude/longitude as per new docs)
    payload = {
        'merchant_order_id': merchant_order_id,
        'payee_name': 'Test User',
        'payee_account_number': '1234567890',
        'ifsc': 'ICIC0000001',
        'bank': 'ICICI BANK',
        'amount': '10',
        'email': 'test@example.com',
        'mobile': '9999999999',
        'latitude': '28.6139',
        'longitude': '77.6240'
    }
    
    url = f"{BASE_URL}/api/prod/payout/create"
    
    print(f"\nAPI Call:")
    print(f"  URL: {url}")
    print(f"  Method: POST")
    print(f"  Content-Type: form data")
    
    print(f"\nHeaders:")
    for key, value in headers.items():
        if key == 'X-API-KEY':
            print(f"  {key}: {value[:10]}...")
        elif key == 'X-SIGNATURE':
            print(f"  {key}: {value[:20]}...")
        else:
            print(f"  {key}: {value}")
    
    print(f"\nPayload:")
    for key, value in payload.items():
        print(f"  {key}: {value}")
    
    try:
        print(f"\n{'='*80}")
        print("Sending Request...")
        print(f"{'='*80}")
        
        response = requests.post(
            url,
            headers=headers,
            data=payload,  # Form data
            timeout=30
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"\nResponse Body:")
        print(response.text)
        
        if response.status_code in [200, 201]:
            try:
                response_json = response.json()
                print(f"\nParsed Response:")
                import json
                print(json.dumps(response_json, indent=2))
                
                if response_json.get('status'):
                    print(f"\n{'='*80}")
                    print("✅ SUCCESS! Payout API is working!")
                    print(f"{'='*80}")
                    print(f"\nPayout Details:")
                    data = response_json.get('data', {})
                    print(f"  Merchant Order ID: {data.get('merchant_order_id')}")
                    print(f"  Amount: ₹{data.get('amount')}")
                    print(f"  Charge: ₹{data.get('charge')}")
                    print(f"  GST: ₹{data.get('gst')}")
                    print(f"  Total Debit: ₹{data.get('total_debit_amount')}")
                    print(f"  Status: {data.get('status')}")
                    return True
                else:
                    print(f"\n{'='*80}")
                    print(f"❌ FAILED: {response_json.get('message')}")
                    print(f"{'='*80}")
                    return False
            except:
                print(f"\n❌ Could not parse JSON response")
                return False
        else:
            print(f"\n{'='*80}")
            print(f"❌ FAILED: HTTP {response.status_code}")
            print(f"{'='*80}")
            return False
            
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"❌ ERROR: {e}")
        print(f"{'='*80}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_payout()
    
    if success:
        print("\n" + "="*80)
        print("✅ INTEGRATION VERIFIED")
        print("="*80)
        print("\nThe MaxPe payout integration is working correctly!")
        print("You can now use MaxPe for payouts in production.")
    else:
        print("\n" + "="*80)
        print("❌ INTEGRATION FAILED")
        print("="*80)
        print("\nPlease check:")
        print("1. API credentials are correct")
        print("2. Account is activated for payouts")
        print("3. IP is whitelisted (if required)")
        print("4. Contact MaxPe support with the error details above")
