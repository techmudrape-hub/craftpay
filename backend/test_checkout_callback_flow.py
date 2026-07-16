"""
Test MaxPe Checkout Callback Flow
This script tests the complete callback flow to the checkout page
"""

import requests
import json

# Test data matching your actual callback
test_callback_data = {
    'order_id': 'ORDER1235341111456789',
    'status': 'SUCCESS',
    'amount': 100,
    'utr': '451925607434',
    'txn_id': 'MAXPE_7679022140_ORDER1235341111456789_20260514224151',
    'bank_ref_no': '451925607434',
    'completed_at': '2026-05-14T22:41:51'
}

print("=" * 80)
print("TESTING CHECKOUT CALLBACK FLOW")
print("=" * 80)

# Step 1: Send callback to checkout endpoint
print("\n1. Sending callback to checkout endpoint...")
print(f"Data: {json.dumps(test_callback_data, indent=2)}")

try:
    response = requests.post(
        'http://localhost:5000/api/checkout/maxpe/callback',
        json=test_callback_data,
        headers={'Content-Type': 'application/json'},
        timeout=5
    )
    
    print(f"Response Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 200:
        print("✅ Callback received successfully!")
    else:
        print("❌ Callback failed!")
        exit(1)
        
except Exception as e:
    print(f"❌ Error sending callback: {e}")
    exit(1)

# Step 2: Check status endpoint
print("\n2. Checking status endpoint...")
try:
    status_response = requests.get(
        f'http://localhost:5000/api/checkout/maxpe/status?order_id={test_callback_data["order_id"]}',
        timeout=5
    )
    
    print(f"Response Status: {status_response.status_code}")
    status_data = status_response.json()
    print(f"Response: {json.dumps(status_data, indent=2)}")
    
    if status_data.get('success') and status_data.get('transaction', {}).get('status') == 'SUCCESS':
        print("✅ Status check successful!")
        print(f"✅ UTR: {status_data['transaction']['utr']}")
        print(f"✅ Amount: {status_data['transaction']['amount']}")
    else:
        print("❌ Status check failed or status not SUCCESS!")
        
except Exception as e:
    print(f"❌ Error checking status: {e}")
    exit(1)

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
