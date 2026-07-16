"""
Test Razorpay Callback - Debug Script
Simulates a Razorpay callback to test the integration
"""

import requests
import json

# Your callback URL
CALLBACK_URL = "https://api.craftpay.in/api/callback/razorpay/payin"

# Test callback data (from your screenshot)
callback_params = {
    'razorpay_payment_id': 'pay_SnLDdfWU62JpSh',
    'razorpay_payment_link_id': 'plink_SnLcnAMDEma3j1',
    'razorpay_payment_link_reference_id': '',  # Empty in your case
    'razorpay_payment_link_status': 'paid',
    'razorpay_signature': 'da4f23dfb4f69a64a81e9a17bb2ea93837e9999892a8bea3cf2eefda15174989'
}

print("=" * 80)
print("Testing Razorpay Callback")
print("=" * 80)
print(f"Callback URL: {CALLBACK_URL}")
print(f"Callback Params: {json.dumps(callback_params, indent=2)}")
print("=" * 80)

# Send GET request (Razorpay sends GET)
try:
    response = requests.get(
        CALLBACK_URL,
        params=callback_params,
        timeout=30
    )
    
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"\nResponse Body:")
    print(response.text)
    
    if response.status_code == 200:
        print("\n✅ Callback processed successfully!")
    else:
        print(f"\n❌ Callback failed with status {response.status_code}")
        
except Exception as e:
    print(f"\n❌ Error sending callback: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("Test Complete")
print("=" * 80)
