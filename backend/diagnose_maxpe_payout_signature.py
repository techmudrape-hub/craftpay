"""
Diagnose MaxPe Payout Signature Issue
This script tests different signature generation methods to find the correct one
"""

import hmac
import hashlib
import time
import uuid
import requests
from config import Config

def generate_nonce():
    """Generate unique nonce for request (16 character hex)"""
    return uuid.uuid4().hex[:16]

def test_signature_method_1(data, api_secret):
    """
    Method 1: Alphabetically sorted (current implementation)
    """
    sorted_keys = sorted(data.keys())
    canonical_parts = []
    for key in sorted_keys:
        value = str(data[key])
        canonical_parts.append(f"{key}={value}")
    
    canonical_string = "&".join(canonical_parts)
    
    signature = hmac.new(
        api_secret.encode('utf-8'),
        canonical_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return canonical_string, signature

def test_signature_method_2(data, api_secret):
    """
    Method 2: Specific order (as listed in API docs)
    Order: merchant_order_id, payee_name, payee_account_number, ifsc, bank, amount, email, mobile, timestamp, nonce
    """
    key_order = [
        'merchant_order_id',
        'payee_name',
        'payee_account_number',
        'ifsc',
        'bank',
        'amount',
        'email',
        'mobile',
        'timestamp',
        'nonce'
    ]
    
    canonical_parts = []
    for key in key_order:
        if key in data:
            value = str(data[key])
            canonical_parts.append(f"{key}={value}")
    
    canonical_string = "&".join(canonical_parts)
    
    signature = hmac.new(
        api_secret.encode('utf-8'),
        canonical_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return canonical_string, signature

def test_signature_method_3(data, api_secret):
    """
    Method 3: Only timestamp and nonce (minimal signature)
    """
    canonical_string = f"nonce={data['nonce']}&timestamp={data['timestamp']}"
    
    signature = hmac.new(
        api_secret.encode('utf-8'),
        canonical_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return canonical_string, signature

def test_payout_api_call(method_name, canonical_string, signature, timestamp, nonce, payload):
    """
    Test actual API call with given signature
    """
    print(f"\n{'='*80}")
    print(f"Testing {method_name}")
    print(f"{'='*80}")
    print(f"Canonical String: {canonical_string}")
    print(f"Signature: {signature}")
    
    headers = {
        'Accept': 'application/json',
        'X-API-KEY': Config.MAXPE_API_KEY,
        'X-TIMESTAMP': str(timestamp),
        'X-NONCE': nonce,
        'X-SIGNATURE': signature
    }
    
    url = f"{Config.MAXPE_BASE_URL}/api/prod/payout/create"
    
    print(f"\nHeaders:")
    for key, value in headers.items():
        if key == 'X-API-KEY':
            print(f"  {key}: {value[:10]}...")
        else:
            print(f"  {key}: {value}")
    
    print(f"\nPayload:")
    for key, value in payload.items():
        print(f"  {key}: {value}")
    
    try:
        response = requests.post(
            url,
            headers=headers,
            data=payload,
            timeout=30
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        if response.status_code in [200, 201]:
            response_json = response.json()
            if response_json.get('status'):
                print(f"\n✅ SUCCESS! This signature method works!")
                return True
            else:
                print(f"\n❌ FAILED: {response_json.get('message')}")
                return False
        else:
            print(f"\n❌ FAILED: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

def main():
    """Main test function"""
    
    print("="*80)
    print("MaxPe Payout Signature Diagnosis")
    print("="*80)
    
    # Test data
    timestamp = int(time.time())
    nonce = generate_nonce()
    
    # Prepare test payout data (small amount for testing)
    test_data = {
        'merchant_order_id': f'TEST_{timestamp}',
        'payee_name': 'Test User',
        'payee_account_number': '1234567890',
        'ifsc': 'ICIC0000001',
        'bank': 'ICICI BANK',
        'amount': '10',  # Small test amount
        'email': 'test@example.com',
        'mobile': '9999999999',
        'timestamp': str(timestamp),
        'nonce': nonce
    }
    
    # Payload for API (includes latitude/longitude)
    payload = {
        'merchant_order_id': test_data['merchant_order_id'],
        'payee_name': test_data['payee_name'],
        'payee_account_number': test_data['payee_account_number'],
        'ifsc': test_data['ifsc'],
        'bank': test_data['bank'],
        'amount': test_data['amount'],
        'email': test_data['email'],
        'mobile': test_data['mobile'],
        'latitude': '28.6139',
        'longitude': '77.2090'
    }
    
    print(f"\nTest Data:")
    for key, value in test_data.items():
        print(f"  {key}: {value}")
    
    print(f"\nAPI Secret (first 10 chars): {Config.MAXPE_API_SECRET[:10]}...")
    
    # Test Method 1: Alphabetically sorted
    canonical_1, signature_1 = test_signature_method_1(test_data, Config.MAXPE_API_SECRET)
    success_1 = test_payout_api_call("Method 1: Alphabetically Sorted", canonical_1, signature_1, timestamp, nonce, payload)
    
    if success_1:
        print("\n" + "="*80)
        print("✅ SOLUTION FOUND: Method 1 (Alphabetically Sorted)")
        print("="*80)
        return
    
    # Test Method 2: Specific order
    canonical_2, signature_2 = test_signature_method_2(test_data, Config.MAXPE_API_SECRET)
    success_2 = test_payout_api_call("Method 2: Specific Order", canonical_2, signature_2, timestamp, nonce, payload)
    
    if success_2:
        print("\n" + "="*80)
        print("✅ SOLUTION FOUND: Method 2 (Specific Order)")
        print("="*80)
        print("\nUpdate maxpe_payout_service.py to use this order:")
        print("merchant_order_id, payee_name, payee_account_number, ifsc, bank, amount, email, mobile, timestamp, nonce")
        return
    
    # Test Method 3: Minimal (only timestamp and nonce)
    canonical_3, signature_3 = test_signature_method_3(test_data, Config.MAXPE_API_SECRET)
    success_3 = test_payout_api_call("Method 3: Minimal (timestamp + nonce only)", canonical_3, signature_3, timestamp, nonce, payload)
    
    if success_3:
        print("\n" + "="*80)
        print("✅ SOLUTION FOUND: Method 3 (Minimal - timestamp + nonce only)")
        print("="*80)
        print("\nUpdate maxpe_payout_service.py to only sign timestamp and nonce")
        return
    
    print("\n" + "="*80)
    print("❌ NO SOLUTION FOUND")
    print("="*80)
    print("\nPossible issues:")
    print("1. API credentials are incorrect")
    print("2. API secret has special characters that need escaping")
    print("3. MaxPe expects a different signature format")
    print("4. Account is not activated for payouts")
    print("\nNext steps:")
    print("1. Verify MAXPE_API_KEY and MAXPE_API_SECRET in .env")
    print("2. Contact MaxPe support with the test output")
    print("3. Request MaxPe's signature generation example")

if __name__ == '__main__':
    main()
