"""
Test MaxPe Payin Callback Forwarding
Simulate a callback to test if forwarding works
"""

import requests
import json

# Use the transaction that has SUCCESS status
test_callback = {
    "status": "SUCCESS",
    "transaction_details": {
        "amount": "200.00",
        "transaction_id": "ORDER12311112fff2211456789",  # This transaction exists
        "utr": "611456505391",
        "charge": "10.00",
        "gst": "1.80",
        "paid_amount": "188.20"
    }
}

print("=" * 80)
print("Testing MaxPe Payin Callback Forwarding")
print("=" * 80)
print(f"\nSending callback for transaction: ORDER12311112fff2211456789")
print(f"Expected callback URL: https://webhook.site/afa7c45a-40f2-4e4a-9be4-6a8e289171c1")
print(f"\nCallback payload:")
print(json.dumps(test_callback, indent=2))

# Send to local callback endpoint
url = "http://localhost:5000/api/callback/maxpe/payin"

print(f"\n🔄 Sending POST request to: {url}")

try:
    response = requests.post(
        url,
        json=test_callback,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )
    
    print(f"\n✅ Response Status: {response.status_code}")
    print(f"📄 Response Body:")
    print(json.dumps(response.json(), indent=2))
    
    if response.status_code == 200:
        print("\n✅ Callback processed successfully!")
        print("\nNow check:")
        print("1. Server logs for callback forwarding messages")
        print("2. callback_logs table for the forwarding attempt")
        print("3. webhook.site for the forwarded callback")
    else:
        print(f"\n❌ Callback failed with status {response.status_code}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nMake sure:")
    print("1. The Flask server is running (python app.py)")
    print("2. The server is accessible on localhost:5000")
