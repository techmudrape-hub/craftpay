import os
import sys
import time
import uuid

# Add current dir to path to import config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import Config
from nextpay_service import nextpay_service

def test_payin():
    print("=========================================")
    print("Testing Nextpay Payin API Integration")
    print("=========================================")
    
    # Payload for generating payin order
    payload = {
        'amount': 1.0,
        'customer_name': 'Test User',
        'customer_mobile': '9999999999',
        'customer_email': 'test@orchpay.in',
        'remarks': 'Test Payin',
        'client_order_id': f"TEST_PAYIN_{int(time.time())}",
        'return_url': 'https://api.craftpay.in/api/callback/nextpay/payin'
    }
    
    timestamp = int(time.time())
    request_id = nextpay_service.generate_request_id()
    
    # Generate signature
    data_to_sign = payload.copy()
    data_to_sign['timestamp'] = str(timestamp)
    data_to_sign['request_id'] = request_id
    
    signature = nextpay_service.generate_signature(data_to_sign)
    headers = nextpay_service.get_headers(timestamp, request_id, signature)
    
    url = f"{nextpay_service.base_url}/api/v1/payin/create"
    
    print(f"Endpoint URL: {url}")
    print(f"Request Payload: {payload}")
    print(f"Request Headers: {headers}")
    print("-----------------------------------------")
    
    try:
        response = nextpay_service.session.post(url, headers=headers, json=payload, timeout=15)
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
    except Exception as e:
        print(f"Error calling API: {e}")

if __name__ == '__main__':
    test_payin()
