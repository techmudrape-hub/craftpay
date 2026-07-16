"""
Debug script for Risexpay signature generation
Helps identify the correct canonical string format
"""

import os
import hmac
import hashlib
import json
from dotenv import load_dotenv

load_dotenv()

def test_all_signature_formats():
    """Test all possible signature formats"""
    
    secret_key = os.getenv('RISEXPAY_SECRET_KEY', '')
    
    if not secret_key:
        print("❌ RISEXPAY_SECRET_KEY not found in .env")
        return
    
    # Sample data
    timestamp = 1716000000
    payload = {
        'mid': 'RXPY123456789',
        'apikey': 'test_api_key',
        'amount': 100,
        'customer_mobile': '9876543210',
        'redirect_url': 'https://api.craftpay.in/callback'
    }
    
    print("="*80)
    print("RISEXPAY SIGNATURE FORMAT TESTING")
    print("="*80)
    print(f"\nPayload: {json.dumps(payload, indent=2)}")
    print(f"Timestamp: {timestamp}")
    print(f"Secret Key: {secret_key[:10]}...")
    
    print("\n" + "="*80)
    print("TESTING DIFFERENT CANONICAL STRING FORMATS")
    print("="*80)
    
    # Format 1: Sorted keys with timestamp at end
    print("\n1️⃣  Format: amount=100&apikey=...&customer_mobile=...&mid=...&redirect_url=...&timestamp=1716000000")
    sorted_keys = sorted(payload.keys())
    parts = [f"{k}={payload[k]}" for k in sorted_keys]
    parts.append(f"timestamp={timestamp}")
    canonical_1 = "&".join(parts)
    sig_1 = hmac.new(secret_key.encode(), canonical_1.encode(), hashlib.sha256).hexdigest()
    print(f"   Canonical: {canonical_1}")
    print(f"   Signature: {sig_1}")
    
    # Format 2: Without timestamp
    print("\n2️⃣  Format: amount=100&apikey=...&customer_mobile=...&mid=...&redirect_url=...")
    parts = [f"{k}={payload[k]}" for k in sorted_keys]
    canonical_2 = "&".join(parts)
    sig_2 = hmac.new(secret_key.encode(), canonical_2.encode(), hashlib.sha256).hexdigest()
    print(f"   Canonical: {canonical_2}")
    print(f"   Signature: {sig_2}")
    
    # Format 3: Timestamp first
    print("\n3️⃣  Format: timestamp=1716000000&amount=100&apikey=...&customer_mobile=...&mid=...&redirect_url=...")
    parts = [f"timestamp={timestamp}"] + [f"{k}={payload[k]}" for k in sorted_keys]
    canonical_3 = "&".join(parts)
    sig_3 = hmac.new(secret_key.encode(), canonical_3.encode(), hashlib.sha256).hexdigest()
    print(f"   Canonical: {canonical_3}")
    print(f"   Signature: {sig_3}")
    
    # Format 4: JSON sorted
    print("\n4️⃣  Format: JSON string (sorted keys)")
    json_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    sig_4 = hmac.new(secret_key.encode(), json_str.encode(), hashlib.sha256).hexdigest()
    print(f"   Canonical: {json_str}")
    print(f"   Signature: {sig_4}")
    
    # Format 5: Timestamp + JSON
    print("\n5️⃣  Format: timestamp + JSON")
    canonical_5 = f"{timestamp}{json_str}"
    sig_5 = hmac.new(secret_key.encode(), canonical_5.encode(), hashlib.sha256).hexdigest()
    print(f"   Canonical: {canonical_5}")
    print(f"   Signature: {sig_5}")
    
    # Format 6: All fields including timestamp in sorted order
    print("\n6️⃣  Format: All fields including timestamp sorted alphabetically")
    all_fields = {**payload, 'timestamp': timestamp}
    sorted_all = sorted(all_fields.keys())
    parts = [f"{k}={all_fields[k]}" for k in sorted_all]
    canonical_6 = "&".join(parts)
    sig_6 = hmac.new(secret_key.encode(), canonical_6.encode(), hashlib.sha256).hexdigest()
    print(f"   Canonical: {canonical_6}")
    print(f"   Signature: {sig_6}")
    
    # Format 7: Query string style (URL encoded)
    print("\n7️⃣  Format: URL encoded query string")
    from urllib.parse import urlencode
    canonical_7 = urlencode(sorted(payload.items()))
    sig_7 = hmac.new(secret_key.encode(), canonical_7.encode(), hashlib.sha256).hexdigest()
    print(f"   Canonical: {canonical_7}")
    print(f"   Signature: {sig_7}")
    
    # Format 8: Concatenated values only (no keys)
    print("\n8️⃣  Format: Concatenated values only")
    values = [str(payload[k]) for k in sorted_keys]
    canonical_8 = "".join(values) + str(timestamp)
    sig_8 = hmac.new(secret_key.encode(), canonical_8.encode(), hashlib.sha256).hexdigest()
    print(f"   Canonical: {canonical_8}")
    print(f"   Signature: {sig_8}")
    
    print("\n" + "="*80)
    print("SUMMARY OF ALL SIGNATURES")
    print("="*80)
    print(f"Format 1: {sig_1}")
    print(f"Format 2: {sig_2}")
    print(f"Format 3: {sig_3}")
    print(f"Format 4: {sig_4}")
    print(f"Format 5: {sig_5}")
    print(f"Format 6: {sig_6}")
    print(f"Format 7: {sig_7}")
    print(f"Format 8: {sig_8}")
    
    print("\n" + "="*80)
    print("INSTRUCTIONS")
    print("="*80)
    print("1. Run the test_risexpay_payin_real.py script")
    print("2. Note the signature that Risexpay expects")
    print("3. Compare with the signatures above")
    print("4. Update risexpay_service.py with the correct format")
    print("\nOR")
    print("Contact Risexpay support (support@risexpay.in) for the")
    print("Integration Helper Package with the exact format.")
    print("="*80)

if __name__ == "__main__":
    test_all_signature_formats()
