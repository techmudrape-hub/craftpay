"""
Comprehensive Risexpay Signature Format Tester
Tests ALL possible signature formats to find the working one
"""

import os
import sys
import time
import hmac
import hashlib
import json
import requests
from dotenv import load_dotenv
from urllib.parse import urlencode

load_dotenv()

# Get credentials
BASE_URL = os.getenv('RISEXPAY_BASE_URL', 'https://risexpay.in')
MID = os.getenv('RISEXPAY_MID', '')
API_KEY = os.getenv('RISEXPAY_API_KEY', '')
SECRET_KEY = os.getenv('RISEXPAY_SECRET_KEY', '')

def test_format(format_num, format_name, canonical_string, payload, timestamp):
    """Test a specific signature format"""
    print(f"\n{'='*80}")
    print(f"Format {format_num}: {format_name}")
    print(f"{'='*80}")
    print(f"Canonical: {canonical_string}")
    
    # Generate signature
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        canonical_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    print(f"Signature: {signature}")
    
    # Prepare headers
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Timestamp': str(timestamp),
        'X-Signature': signature
    }
    
    # Make request
    url = f"{BASE_URL}/api/v1/imb/create_order.php"
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"Response: {response.status_code}")
        
        try:
            response_json = response.json()
            print(f"Body: {json.dumps(response_json, indent=2)}")
            
            if response.status_code == 200 and response_json.get('status'):
                print(f"\n🎉 SUCCESS! This format works!")
                return True, format_num, canonical_string
            else:
                print(f"❌ Failed: {response_json.get('message', 'Unknown error')}")
                return False, None, None
        except:
            print(f"Response Text: {response.text}")
            return False, None, None
            
    except Exception as e:
        print(f"❌ Request error: {e}")
        return False, None, None

def main():
    print("\n" + "="*80)
    print("🔍 RISEXPAY COMPREHENSIVE SIGNATURE FORMAT TESTER")
    print("="*80)
    
    if not all([MID, API_KEY, SECRET_KEY]):
        print("\n❌ Missing credentials in .env file")
        print("Required: RISEXPAY_MID, RISEXPAY_API_KEY, RISEXPAY_SECRET_KEY")
        return False
    
    print(f"\nConfiguration:")
    print(f"  Base URL: {BASE_URL}")
    print(f"  MID: {MID}")
    print(f"  API Key: {API_KEY[:10]}...")
    print(f"  Secret Key: {SECRET_KEY[:10]}...")
    
    # Prepare test data
    timestamp = int(time.time())
    payload = {
        'mid': MID,
        'apikey': API_KEY,
        'amount': 100,
        'customer_mobile': '9876543210',
        'redirect_url': 'https://api.craftpay.in/api/callback/risexpay/payin'
    }
    
    print(f"\nTest Payload:")
    print(json.dumps(payload, indent=2))
    print(f"Timestamp: {timestamp}")
    
    # All possible formats to test
    formats = []
    
    # Format 1: Sorted keys + timestamp appended
    sorted_keys = sorted(payload.keys())
    parts = [f"{k}={payload[k]}" for k in sorted_keys]
    parts.append(f"timestamp={timestamp}")
    formats.append((
        1,
        "Sorted keys + timestamp appended",
        "&".join(parts),
        payload,
        timestamp
    ))
    
    # Format 2: Sorted keys (no timestamp)
    parts = [f"{k}={payload[k]}" for k in sorted_keys]
    formats.append((
        2,
        "Sorted keys (no timestamp)",
        "&".join(parts),
        payload,
        timestamp
    ))
    
    # Format 3: Timestamp first + sorted keys
    parts = [f"timestamp={timestamp}"] + [f"{k}={payload[k]}" for k in sorted_keys]
    formats.append((
        3,
        "Timestamp first + sorted keys",
        "&".join(parts),
        payload,
        timestamp
    ))
    
    # Format 4: All fields including timestamp sorted
    all_fields = {**payload, 'timestamp': timestamp}
    sorted_all = sorted(all_fields.keys())
    parts = [f"{k}={all_fields[k]}" for k in sorted_all]
    formats.append((
        4,
        "All fields including timestamp sorted",
        "&".join(parts),
        payload,
        timestamp
    ))
    
    # Format 5: JSON string (sorted keys)
    json_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    formats.append((
        5,
        "JSON string (sorted keys)",
        json_str,
        payload,
        timestamp
    ))
    
    # Format 6: Timestamp + JSON
    formats.append((
        6,
        "Timestamp + JSON",
        f"{timestamp}{json_str}",
        payload,
        timestamp
    ))
    
    # Format 7: URL encoded (sorted)
    url_encoded = urlencode(sorted(payload.items()))
    formats.append((
        7,
        "URL encoded (sorted)",
        url_encoded,
        payload,
        timestamp
    ))
    
    # Format 8: URL encoded + timestamp
    formats.append((
        8,
        "URL encoded + timestamp",
        f"{url_encoded}&timestamp={timestamp}",
        payload,
        timestamp
    ))
    
    # Format 9: Concatenated values only
    values = [str(payload[k]) for k in sorted_keys]
    formats.append((
        9,
        "Concatenated values only",
        "".join(values),
        payload,
        timestamp
    ))
    
    # Format 10: Concatenated values + timestamp
    formats.append((
        10,
        "Concatenated values + timestamp",
        "".join(values) + str(timestamp),
        payload,
        timestamp
    ))
    
    # Format 11: JSON with timestamp field
    payload_with_ts = {**payload, 'timestamp': timestamp}
    json_with_ts = json.dumps(payload_with_ts, sort_keys=True, separators=(',', ':'))
    formats.append((
        11,
        "JSON with timestamp field",
        json_with_ts,
        payload,
        timestamp
    ))
    
    # Format 12: Raw JSON (as sent in body)
    raw_json = json.dumps(payload, separators=(',', ':'))
    formats.append((
        12,
        "Raw JSON (as sent in body)",
        raw_json,
        payload,
        timestamp
    ))
    
    # Format 13: Raw JSON + timestamp
    formats.append((
        13,
        "Raw JSON + timestamp",
        f"{raw_json}{timestamp}",
        payload,
        timestamp
    ))
    
    # Format 14: Timestamp + raw JSON
    formats.append((
        14,
        "Timestamp + raw JSON",
        f"{timestamp}{raw_json}",
        payload,
        timestamp
    ))
    
    # Format 15: Query string style (unsorted)
    query_parts = [f"{k}={payload[k]}" for k in payload.keys()]
    formats.append((
        15,
        "Query string (unsorted)",
        "&".join(query_parts),
        payload,
        timestamp
    ))
    
    # Test all formats
    print(f"\n{'='*80}")
    print(f"TESTING {len(formats)} DIFFERENT FORMATS")
    print(f"{'='*80}")
    
    working_format = None
    working_canonical = None
    
    for format_data in formats:
        success, format_num, canonical = test_format(*format_data)
        
        if success:
            working_format = format_num
            working_canonical = canonical
            break
        
        # Wait between requests to avoid rate limiting
        time.sleep(1)
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 TEST RESULTS")
    print(f"{'='*80}")
    
    if working_format:
        print(f"\n✅ FOUND WORKING FORMAT!")
        print(f"\nFormat {working_format}:")
        print(f"Canonical String: {working_canonical}")
        print(f"\n📝 Update risexpay_service.py:")
        print(f"   Look for the generate_signature() method")
        print(f"   Use this canonical string format")
        
        # Generate code snippet
        print(f"\n💻 Code to use:")
        print("```python")
        if working_format == 1:
            print("# Sorted keys + timestamp appended")
            print("sorted_keys = sorted(payload.keys())")
            print("parts = [f\"{k}={payload[k]}\" for k in sorted_keys]")
            print("parts.append(f\"timestamp={timestamp}\")")
            print("canonical_string = \"&\".join(parts)")
        elif working_format == 2:
            print("# Sorted keys (no timestamp)")
            print("sorted_keys = sorted(payload.keys())")
            print("parts = [f\"{k}={payload[k]}\" for k in sorted_keys]")
            print("canonical_string = \"&\".join(parts)")
        elif working_format == 4:
            print("# All fields including timestamp sorted")
            print("all_fields = {**payload, 'timestamp': timestamp}")
            print("sorted_keys = sorted(all_fields.keys())")
            print("parts = [f\"{k}={all_fields[k]}\" for k in sorted_keys]")
            print("canonical_string = \"&\".join(parts)")
        elif working_format == 5:
            print("# JSON string (sorted keys)")
            print("canonical_string = json.dumps(payload, sort_keys=True, separators=(',', ':'))")
        print("```")
        
        return True
    else:
        print(f"\n❌ NO WORKING FORMAT FOUND")
        print(f"\nTested {len(formats)} different formats, all failed.")
        print(f"\n📞 Next Steps:")
        print(f"   1. Verify RISEXPAY_SECRET_KEY is correct")
        print(f"   2. Check if credentials are for correct environment")
        print(f"   3. Contact Risexpay support: support@risexpay.in")
        print(f"   4. Request Integration Helper Package for Python")
        print(f"   5. Ask for exact canonical string format")
        
        print(f"\n💡 The signature format might be:")
        print(f"   - Using a different hash algorithm (not SHA256)")
        print(f"   - Using a different encoding (not UTF-8)")
        print(f"   - Including additional fields we don't know about")
        print(f"   - Using a proprietary format")
        
        return False

if __name__ == "__main__":
    print("\n⚠️  This script will make multiple API requests to Risexpay")
    print("   Each request will be spaced 1 second apart")
    print("   Press Ctrl+C to cancel\n")
    
    try:
        time.sleep(2)
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Test cancelled by user")
        sys.exit(1)
