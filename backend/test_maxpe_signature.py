"""
Test MaxPe Signature Generation
Compare with PHP example from documentation
"""

import hmac
import hashlib
import time
import uuid

# Test data from MaxPe documentation
test_data = {
    'merchant_order_id': 'txn_00001',
    'payee_name': 'Amit Kumar',
    'payee_account_number': '123456789',
    'ifsc': 'ICIC0000001',
    'bank': 'ICICI BANK',
    'amount': '1000',
    'email': 'amit@gmail.com',
    'mobile': '9999999999',
}

# Use test values from docs
timestamp = 1774877770
nonce = '352f9344fb3de74a'
api_secret = 'YOUR_API_SECRET'  # Replace with your actual secret

# Build data to sign (exactly as in PHP example)
data_to_sign = {
    'amount': str(test_data['amount']),
    'bank': test_data['bank'].upper().strip(),
    'email': test_data['email'].strip(),
    'ifsc': test_data['ifsc'].upper().strip(),
    'merchant_order_id': test_data['merchant_order_id'].strip(),
    'mobile': test_data['mobile'].strip(),
    'nonce': nonce,
    'payee_account_number': test_data['payee_account_number'].strip(),
    'payee_name': test_data['payee_name'].strip(),
    'timestamp': str(timestamp),
}

print("=" * 80)
print("MaxPe Signature Generation Test")
print("=" * 80)

# Sort keys alphabetically
sorted_keys = sorted(data_to_sign.keys())
print(f"\nSorted keys: {sorted_keys}")

# Build canonical string
canonical_parts = []
for key in sorted_keys:
    value = str(data_to_sign[key])
    canonical_parts.append(f"{key}={value}")
    print(f"  {key}={value}")

canonical_string = "&".join(canonical_parts)

print(f"\nCanonical String:")
print(canonical_string)

# Generate signature
signature = hmac.new(
    api_secret.encode('utf-8'),
    canonical_string.encode('utf-8'),
    hashlib.sha256
).hexdigest()

print(f"\nGenerated Signature:")
print(signature)

print(f"\nExpected from docs:")
print("ba0755163279218ecadd6583ddd8bf3efbe374d9850afe0788de40716e5886be")

print("\n" + "=" * 80)
print("Now test with your actual credentials:")
print("=" * 80)

# Import your config
try:
    from config import Config
    
    api_secret_real = Config.MAXPE_API_SECRET
    
    # Generate new timestamp and nonce
    timestamp_real = int(time.time())
    nonce_real = uuid.uuid4().hex[:16]
    
    data_to_sign_real = {
        'amount': '100',
        'bank': 'STATE BANK OF INDIA',
        'email': 'test@example.com',
        'ifsc': 'SBIN0001234',
        'merchant_order_id': 'TEST_' + str(timestamp_real),
        'mobile': '9999999999',
        'nonce': nonce_real,
        'payee_account_number': '1234567890',
        'payee_name': 'Test User',
        'timestamp': str(timestamp_real),
    }
    
    print(f"\nTimestamp: {timestamp_real}")
    print(f"Nonce: {nonce_real}")
    
    # Sort and build canonical string
    sorted_keys_real = sorted(data_to_sign_real.keys())
    canonical_parts_real = []
    for key in sorted_keys_real:
        value = str(data_to_sign_real[key])
        canonical_parts_real.append(f"{key}={value}")
    
    canonical_string_real = "&".join(canonical_parts_real)
    print(f"\nCanonical String:")
    print(canonical_string_real)
    
    # Generate signature
    signature_real = hmac.new(
        api_secret_real.encode('utf-8'),
        canonical_string_real.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    print(f"\nGenerated Signature:")
    print(signature_real)
    
    print(f"\nAPI Key: {Config.MAXPE_API_KEY}")
    print(f"API Secret (first 10 chars): {api_secret_real[:10]}...")
    
    print("\n" + "=" * 80)
    print("Test cURL command:")
    print("=" * 80)
    
    curl_cmd = f"""curl --location 'https://merchant.maxpe.tech/api/prod/payout/create' \\
--header 'Accept: application/json' \\
--header 'X-API-KEY: {Config.MAXPE_API_KEY}' \\
--header 'X-TIMESTAMP: {timestamp_real}' \\
--header 'X-NONCE: {nonce_real}' \\
--header 'X-SIGNATURE: {signature_real}' \\
--form 'merchant_order_id="{data_to_sign_real["merchant_order_id"]}"' \\
--form 'payee_name="{data_to_sign_real["payee_name"]}"' \\
--form 'payee_account_number="{data_to_sign_real["payee_account_number"]}"' \\
--form 'ifsc="{data_to_sign_real["ifsc"]}"' \\
--form 'bank="{data_to_sign_real["bank"]}"' \\
--form 'amount="{data_to_sign_real["amount"]}"' \\
--form 'email="{data_to_sign_real["email"]}"' \\
--form 'mobile="{data_to_sign_real["mobile"]}"' \\
--form 'latitude="28.6139"' \\
--form 'longitude="77.2090"'"""
    
    print(curl_cmd)
    
except Exception as e:
    print(f"\nError loading config: {e}")
    print("Make sure you're running this from the backend directory")
