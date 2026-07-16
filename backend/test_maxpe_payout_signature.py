"""
Test MaxPe Payout Signature Generation
This script helps diagnose the signature issue
"""

import hmac
import hashlib
import time
import uuid
from config import Config

def generate_nonce():
    """Generate unique nonce for request (16 character hex)"""
    return uuid.uuid4().hex[:16]

def generate_signature_v1(data_to_sign, api_secret):
    """
    Current signature generation (alphabetically sorted)
    """
    # Sort keys alphabetically
    sorted_keys = sorted(data_to_sign.keys())
    
    print(f"\n=== V1 Signature (Alphabetically Sorted) ===")
    print(f"Sorted keys: {sorted_keys}")
    
    # Build canonical string: key=value&key=value
    canonical_parts = []
    for key in sorted_keys:
        value = str(data_to_sign[key])
        canonical_parts.append(f"{key}={value}")
        print(f"  {key}={value}")
    
    canonical_string = "&".join(canonical_parts)
    
    print(f"\nCanonical String: {canonical_string}")
    
    # Generate HMAC SHA256 signature
    signature = hmac.new(
        api_secret.encode('utf-8'),
        canonical_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    print(f"Signature: {signature}")
    
    return signature

def generate_signature_v2(data_to_sign, api_secret):
    """
    Alternative signature generation (specific order as per docs)
    Try this order: merchant_order_id, payee_name, payee_account_number, ifsc, bank, amount, email, mobile, timestamp, nonce
    """
    # Specific order based on common API patterns
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
    
    print(f"\n=== V2 Signature (Specific Order) ===")
    print(f"Key order: {key_order}")
    
    # Build canonical string in specific order
    canonical_parts = []
    for key in key_order:
        if key in data_to_sign:
            value = str(data_to_sign[key])
            canonical_parts.append(f"{key}={value}")
            print(f"  {key}={value}")
    
    canonical_string = "&".join(canonical_parts)
    
    print(f"\nCanonical String: {canonical_string}")
    
    # Generate HMAC SHA256 signature
    signature = hmac.new(
        api_secret.encode('utf-8'),
        canonical_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    print(f"Signature: {signature}")
    
    return signature

def generate_signature_v3(data_to_sign, api_secret):
    """
    Alternative: Only include specific fields (not latitude/longitude)
    And use the order from payin which works
    """
    # Only include fields that should be signed (exclude latitude/longitude)
    fields_to_sign = [
        'amount',
        'bank',
        'email',
        'ifsc',
        'merchant_order_id',
        'mobile',
        'nonce',
        'payee_account_number',
        'payee_name',
        'timestamp'
    ]
    
    print(f"\n=== V3 Signature (Filtered & Alphabetically Sorted) ===")
    
    # Filter and sort
    filtered_data = {k: v for k, v in data_to_sign.items() if k in fields_to_sign}
    sorted_keys = sorted(filtered_data.keys())
    
    print(f"Sorted keys: {sorted_keys}")
    
    # Build canonical string
    canonical_parts = []
    for key in sorted_keys:
        value = str(filtered_data[key])
        canonical_parts.append(f"{key}={value}")
        print(f"  {key}={value}")
    
    canonical_string = "&".join(canonical_parts)
    
    print(f"\nCanonical String: {canonical_string}")
    
    # Generate HMAC SHA256 signature
    signature = hmac.new(
        api_secret.encode('utf-8'),
        canonical_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    print(f"Signature: {signature}")
    
    return signature

def main():
    """Test signature generation with sample data"""
    
    print("=" * 80)
    print("MaxPe Payout Signature Testing")
    print("=" * 80)
    
    # Get credentials from config
    api_secret = Config.MAXPE_API_SECRET
    
    print(f"\nAPI Secret (first 10 chars): {api_secret[:10]}...")
    print(f"API Secret length: {len(api_secret)}")
    
    # Sample payout data
    timestamp = int(time.time())
    nonce = generate_nonce()
    
    test_data = {
        'merchant_order_id': 'TEST_ORDER_123',
        'payee_name': 'John Doe',
        'payee_account_number': '1234567890',
        'ifsc': 'ICIC0000001',
        'bank': 'ICICI BANK',
        'amount': '1000',
        'email': 'john@example.com',
        'mobile': '9876543210',
        'timestamp': str(timestamp),
        'nonce': nonce,
        'latitude': '28.6139',
        'longitude': '77.2090'
    }
    
    print(f"\nTest Data:")
    for key, value in test_data.items():
        print(f"  {key}: {value}")
    
    # Test all signature methods
    sig1 = generate_signature_v1(test_data, api_secret)
    sig2 = generate_signature_v2(test_data, api_secret)
    sig3 = generate_signature_v3(test_data, api_secret)
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"V1 (Current - Alphabetical with all fields): {sig1}")
    print(f"V2 (Specific Order): {sig2}")
    print(f"V3 (Filtered & Alphabetical - no lat/lon): {sig3}")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    print("Try these signatures in order:")
    print("1. V3 - Most likely correct (matches payin pattern)")
    print("2. V2 - If MaxPe requires specific field order")
    print("3. V1 - Current implementation")
    
    print("\nThe issue is likely:")
    print("- latitude/longitude should NOT be included in signature")
    print("- They are only sent in the payload, not signed")

if __name__ == '__main__':
    main()
