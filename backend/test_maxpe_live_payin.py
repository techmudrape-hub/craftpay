"""
Test script to create a live PayIn order on MaxPe API directly.
This bypasses the local database and tests the MaxPe API connection and payload structure.
"""

import sys
import os
import time
import json
import random
import string

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from maxpe_service import maxpe_service

def test_live_payin():
    print("=" * 80)
    print("MAXPE LIVE PAYIN TEST")
    print("=" * 80)
    
    # Check if credentials are set
    if not maxpe_service.api_key or not maxpe_service.api_secret:
        print("❌ ERROR: MaxPe credentials not found in config.py")
        return
        
    print(f"Base URL: {maxpe_service.base_url}")
    print(f"API Key: {maxpe_service.api_key[:10]}... (masked)")
        
    amount = "10.00" # Use a small real amount
    customer_name = "Test User"
    customer_mobile = "9999999999"
    customer_email = "test.payin@example.com"
    merchant_order_id = f"TEST_PAYIN_{int(time.time())}"
    
    # Random VPA generation just like we do in the service
    random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    payer_vpa = f"usr{random_string}@okaxis"
    
    timestamp = int(time.time())
    nonce = maxpe_service.generate_nonce()
    
    # Prepare payload for signature
    data_to_sign = {
        'amount': amount,
        'email': customer_email,
        'mobile': customer_mobile,
        'name': customer_name,
        'nonce': nonce,
        'payer_vpa': payer_vpa,
        'timestamp': str(timestamp),
        'merchant_order_id': merchant_order_id
    }
    
    signature = maxpe_service.generate_signature(data_to_sign)
    
    # Prepare request payload
    payload = {
        'name': customer_name,
        'mobile': customer_mobile,
        'email': customer_email,
        'amount': amount,
        'payer_vpa': payer_vpa,
        'merchant_order_id': merchant_order_id
    }
    
    url = f"{maxpe_service.base_url}/api/prod/payin/create-payment"
    
    print("\n[Request Payload]")
    print(json.dumps(payload, indent=2))
    
    print("\n[Request Headers]")
    headers = maxpe_service.get_headers(timestamp, nonce, signature)
    # Mask API key in output
    display_headers = headers.copy()
    display_headers['X-API-KEY'] = f"{headers['X-API-KEY'][:10]}..."
    print(json.dumps(display_headers, indent=2))
    
    print(f"\nSending request to MaxPe: {url}")
    start_time = time.time()
    
    try:
        response = maxpe_service.session.post(
            url,
            headers=headers,
            json=payload,
            timeout=(10, 60)
        )
        
        elapsed = time.time() - start_time
        print(f"Response received in {elapsed:.2f}s")
        print(f"Status Code: {response.status_code}")
        
        try:
            resp_json = response.json()
            print("\n[Response JSON]")
            print(json.dumps(resp_json, indent=2))
            
            if resp_json.get('status'):
                print("\n✅ SUCCESS: PayIn order created successfully!")
                if 'payment_url' in resp_json:
                    print(f"Payment URL: {resp_json['payment_url']}")
                elif 'upi_deeplink' in resp_json:
                    print(f"UPI Deeplink: {resp_json['upi_deeplink']}")
            else:
                print("\n❌ FAILED: MaxPe API rejected the request")
                
        except json.JSONDecodeError:
            print("\n[Response Text]")
            print(response.text)
            print("\n❌ FAILED: MaxPe API returned non-JSON response")
            
    except Exception as e:
        print(f"\n❌ ERROR testing API: {e}")

if __name__ == "__main__":
    test_live_payin()
