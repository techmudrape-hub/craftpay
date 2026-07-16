"""
Test Risexpay with the most likely correct signature format
Based on the documentation, the timestamp should be part of the sorted fields
"""

import os
import sys
import time
import hmac
import hashlib
import json
import requests
from dotenv import load_dotenv

load_dotenv()

def test_with_timestamp_in_payload():
    """
    Test with timestamp as part of the payload fields (not appended)
    This is the most common pattern for HMAC-SHA256 signing
    """
    print("\n" + "="*80)
    print("🧪 TESTING: Timestamp as part of payload fields")
    print("="*80)
    
    # Get credentials
    base_url = os.getenv('RISEXPAY_BASE_URL', 'https://risexpay.in')
    mid = os.getenv('RISEXPAY_MID', '')
    api_key = os.getenv('RISEXPAY_API_KEY', '')
    secret_key = os.getenv('RISEXPAY_SECRET_KEY', '')
    
    if not all([mid, api_key, secret_key]):
        print("❌ Missing credentials")
        return False
    
    # Generate timestamp
    timestamp = int(time.time())
    
    # Prepare payload (WITHOUT timestamp - it goes in header only)
    payload = {
        'mid': mid,
        'apikey': api_key,
        'amount': 100,
        'customer_mobile': '9876543210',
        'redirect_url': 'https://api.craftpay.in/api/callback/risexpay/payin'
    }
    
    print(f"\n📦 Payload (for API):")
    print(json.dumps(payload, indent=2))
    print(f"\n⏰ Timestamp: {timestamp}")
    
    # Create signing payload (includes timestamp as a field)
    signing_payload = {**payload, 'timestamp': str(timestamp)}
    
    # Sort all keys alphabetically (including timestamp)
    sorted_keys = sorted(signing_payload.keys())
    
    # Build canonical string
    parts = [f"{k}={signing_payload[k]}" for k in sorted_keys]
    canonical_string = "&".join(parts)
    
    print(f"\n📝 Canonical String (for signing):")
    print(f"   {canonical_string}")
    
    # Generate signature
    signature = hmac.new(
        secret_key.encode('utf-8'),
        canonical_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    print(f"\n🔐 Signature: {signature}")
    
    # Prepare headers
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Timestamp': str(timestamp),
        'X-Signature': signature
    }
    
    # Make request
    url = f"{base_url}/api/v1/imb/create_order.php"
    print(f"\n🌐 Sending request to: {url}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        print(f"\n📥 Response Status: {response.status_code}")
        
        try:
            response_json = response.json()
            print(f"📄 Response:")
            print(json.dumps(response_json, indent=2))
            
            if response.status_code == 200 and response_json.get('status'):
                print(f"\n✅ SUCCESS! Payment order created!")
                
                data = response_json.get('data', {})
                print(f"\n💳 Payment Details:")
                print(f"   Order ID: {data.get('order_id')}")
                print(f"   Amount: ₹{data.get('amount')}")
                print(f"   Payment URL: {data.get('payment_url')}")
                print(f"   BHIM Link: {data.get('bhim_link', '')[:60]}...")
                
                return True
            else:
                print(f"\n❌ Failed: {response_json.get('message')}")
                return False
                
        except:
            print(f"Response Text: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

def test_without_timestamp_in_canonical():
    """
    Test without timestamp in canonical string at all
    Timestamp only in header
    """
    print("\n" + "="*80)
    print("🧪 TESTING: No timestamp in canonical string")
    print("="*80)
    
    # Get credentials
    base_url = os.getenv('RISEXPAY_BASE_URL', 'https://risexpay.in')
    mid = os.getenv('RISEXPAY_MID', '')
    api_key = os.getenv('RISEXPAY_API_KEY', '')
    secret_key = os.getenv('RISEXPAY_SECRET_KEY', '')
    
    if not all([mid, api_key, secret_key]):
        print("❌ Missing credentials")
        return False
    
    # Generate timestamp
    timestamp = int(time.time())
    
    # Prepare payload
    payload = {
        'mid': mid,
        'apikey': api_key,
        'amount': 100,
        'customer_mobile': '9876543210',
        'redirect_url': 'https://api.craftpay.in/api/callback/risexpay/payin'
    }
    
    print(f"\n📦 Payload:")
    print(json.dumps(payload, indent=2))
    print(f"\n⏰ Timestamp: {timestamp}")
    
    # Sort keys alphabetically (NO timestamp)
    sorted_keys = sorted(payload.keys())
    
    # Build canonical string (NO timestamp)
    parts = [f"{k}={payload[k]}" for k in sorted_keys]
    canonical_string = "&".join(parts)
    
    print(f"\n📝 Canonical String (for signing):")
    print(f"   {canonical_string}")
    
    # Generate signature
    signature = hmac.new(
        secret_key.encode('utf-8'),
        canonical_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    print(f"\n🔐 Signature: {signature}")
    
    # Prepare headers
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Timestamp': str(timestamp),
        'X-Signature': signature
    }
    
    # Make request
    url = f"{base_url}/api/v1/imb/create_order.php"
    print(f"\n🌐 Sending request to: {url}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        print(f"\n📥 Response Status: {response.status_code}")
        
        try:
            response_json = response.json()
            print(f"📄 Response:")
            print(json.dumps(response_json, indent=2))
            
            if response.status_code == 200 and response_json.get('status'):
                print(f"\n✅ SUCCESS! Payment order created!")
                
                data = response_json.get('data', {})
                print(f"\n💳 Payment Details:")
                print(f"   Order ID: {data.get('order_id')}")
                print(f"   Amount: ₹{data.get('amount')}")
                print(f"   Payment URL: {data.get('payment_url')}")
                print(f"   BHIM Link: {data.get('bhim_link', '')[:60]}...")
                
                return True
            else:
                print(f"\n❌ Failed: {response_json.get('message')}")
                return False
                
        except:
            print(f"Response Text: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

def main():
    print("\n" + "="*80)
    print("🔍 RISEXPAY SIGNATURE FORMAT TESTING")
    print("="*80)
    
    # Test Format 1: Timestamp as part of sorted fields
    print("\n\n" + "="*80)
    print("TEST 1: Timestamp included in sorted fields")
    print("="*80)
    success1 = test_with_timestamp_in_payload()
    
    if success1:
        print("\n\n" + "="*80)
        print("✅ FOUND WORKING FORMAT!")
        print("="*80)
        print("\nFormat: Include timestamp in sorted fields")
        print("Canonical: amount=X&apikey=X&customer_mobile=X&mid=X&redirect_url=X&timestamp=X")
        return True
    
    # Wait before next test
    time.sleep(2)
    
    # Test Format 2: No timestamp in canonical string
    print("\n\n" + "="*80)
    print("TEST 2: No timestamp in canonical string")
    print("="*80)
    success2 = test_without_timestamp_in_canonical()
    
    if success2:
        print("\n\n" + "="*80)
        print("✅ FOUND WORKING FORMAT!")
        print("="*80)
        print("\nFormat: No timestamp in canonical string")
        print("Canonical: amount=X&apikey=X&customer_mobile=X&mid=X&redirect_url=X")
        return True
    
    # Neither worked
    print("\n\n" + "="*80)
    print("❌ BOTH FORMATS FAILED")
    print("="*80)
    print("\n📞 Contact Risexpay Support:")
    print("   Email: support@risexpay.in")
    print("   Request: Integration Helper Package for Python")
    print("   Ask for: Exact canonical string format for HMAC-SHA256 signing")
    print("\n💡 The secret key might also be incorrect. Double-check:")
    print("   - RISEXPAY_SECRET_KEY in .env file")
    print("   - No extra spaces or quotes")
    print("   - Correct key for your environment (test/production)")
    
    return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
