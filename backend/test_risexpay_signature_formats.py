"""
Interactive test to find the correct Risexpay signature format
This script will try different formats and help identify which one works
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

def generate_signature_format_1(payload, timestamp, secret_key):
    """Format 1: key=value&key=value&timestamp=X"""
    sorted_keys = sorted(payload.keys())
    parts = [f"{k}={payload[k]}" for k in sorted_keys]
    parts.append(f"timestamp={timestamp}")
    canonical = "&".join(parts)
    signature = hmac.new(secret_key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return signature, canonical

def generate_signature_format_2(payload, timestamp, secret_key):
    """Format 2: key=value&key=value (no timestamp)"""
    sorted_keys = sorted(payload.keys())
    parts = [f"{k}={payload[k]}" for k in sorted_keys]
    canonical = "&".join(parts)
    signature = hmac.new(secret_key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return signature, canonical

def generate_signature_format_3(payload, timestamp, secret_key):
    """Format 3: timestamp=X&key=value&key=value"""
    sorted_keys = sorted(payload.keys())
    parts = [f"timestamp={timestamp}"] + [f"{k}={payload[k]}" for k in sorted_keys]
    canonical = "&".join(parts)
    signature = hmac.new(secret_key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return signature, canonical

def generate_signature_format_4(payload, timestamp, secret_key):
    """Format 4: All fields including timestamp sorted"""
    all_fields = {**payload, 'timestamp': timestamp}
    sorted_keys = sorted(all_fields.keys())
    parts = [f"{k}={all_fields[k]}" for k in sorted_keys]
    canonical = "&".join(parts)
    signature = hmac.new(secret_key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return signature, canonical

def test_format(format_num, format_func, payload, timestamp, secret_key, base_url):
    """Test a specific signature format"""
    print(f"\n{'='*80}")
    print(f"Testing Format {format_num}: {format_func.__doc__}")
    print(f"{'='*80}")
    
    signature, canonical = format_func(payload, timestamp, secret_key)
    
    print(f"Canonical String: {canonical}")
    print(f"Signature: {signature}")
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Timestamp': str(timestamp),
        'X-Signature': signature
    }
    
    url = f"{base_url}/api/v1/imb/create_order.php"
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        print(f"\nResponse Status: {response.status_code}")
        
        try:
            response_json = response.json()
            print(f"Response: {json.dumps(response_json, indent=2)}")
            
            if response.status_code == 200 and response_json.get('status'):
                print(f"\n✅ SUCCESS! This format works!")
                return True, format_num
            else:
                error_msg = response_json.get('message', 'Unknown error')
                print(f"\n❌ Failed: {error_msg}")
                return False, None
        except:
            print(f"Response Text: {response.text}")
            return False, None
            
    except Exception as e:
        print(f"\n❌ Request failed: {e}")
        return False, None

def main():
    """Test all signature formats"""
    print("\n" + "="*80)
    print("🔍 RISEXPAY SIGNATURE FORMAT FINDER")
    print("="*80)
    
    # Get credentials
    base_url = os.getenv('RISEXPAY_BASE_URL', 'https://risexpay.in')
    mid = os.getenv('RISEXPAY_MID', '')
    api_key = os.getenv('RISEXPAY_API_KEY', '')
    secret_key = os.getenv('RISEXPAY_SECRET_KEY', '')
    
    if not all([mid, api_key, secret_key]):
        print("\n❌ Missing credentials in .env file")
        return False
    
    print(f"\nConfiguration:")
    print(f"  Base URL: {base_url}")
    print(f"  MID: {mid}")
    print(f"  API Key: {api_key[:10]}...")
    
    # Prepare test payload
    timestamp = int(time.time())
    payload = {
        'mid': mid,
        'apikey': api_key,
        'amount': 100,
        'customer_mobile': '9876543210',
        'redirect_url': 'https://api.craftpay.in/api/callback/risexpay/payin'
    }
    
    print(f"\nTest Payload:")
    print(json.dumps(payload, indent=2))
    print(f"Timestamp: {timestamp}")
    
    # Test all formats
    formats = [
        (1, generate_signature_format_1),
        (2, generate_signature_format_2),
        (3, generate_signature_format_3),
        (4, generate_signature_format_4)
    ]
    
    working_format = None
    
    for format_num, format_func in formats:
        success, found_format = test_format(
            format_num, format_func, payload, timestamp, secret_key, base_url
        )
        
        if success:
            working_format = found_format
            break
        
        # Wait a bit between requests
        time.sleep(2)
    
    # Summary
    print("\n" + "="*80)
    print("📊 RESULTS")
    print("="*80)
    
    if working_format:
        print(f"\n✅ Found working format: Format {working_format}")
        print(f"\n📝 Update risexpay_service.py to use this format")
        print(f"   Look for the generate_signature() method")
        return True
    else:
        print(f"\n❌ None of the standard formats worked")
        print(f"\n💡 Next Steps:")
        print(f"   1. Contact Risexpay support: support@risexpay.in")
        print(f"   2. Request the Integration Helper Package")
        print(f"   3. Ask for the exact canonical string format")
        print(f"   4. Verify your RISEXPAY_SECRET_KEY is correct")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
