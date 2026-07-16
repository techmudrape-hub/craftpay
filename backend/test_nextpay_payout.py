import os
import sys
import time
import uuid

# Add current dir to path to import config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import Config
from nextpay_payout_service import nextpay_payout_service

def test_payout():
    print("=========================================")
    print("Testing Nextpay Payout API Integration")
    print("=========================================")
    
    # Payload for generating payout request
    payload = {
        'transaction_id': f"TEST_PAYOUT_{int(time.time())}",
        'account_holder_name': 'Sumit',
        'account_number': '9448272727',
        'ifsc_code': 'KKBK0005333',
        'amount': 1.0,
        'mode': 'IMPS',
        'mobile': '9876543210',
        'remarks': 'Test transaction',
        'latitude': 28.7041,
        'longitude': 77.1025,
        'purpose': 'Payment for services'
    }
    
    timestamp = int(time.time())
    request_id = nextpay_payout_service.generate_request_id()
    
    # Generate signature
    data_to_sign = payload.copy()
    data_to_sign['timestamp'] = str(timestamp)
    data_to_sign['request_id'] = request_id
    
    signature = nextpay_payout_service.generate_signature(data_to_sign)
    headers = nextpay_payout_service.get_headers(timestamp, request_id, signature)
    
    url = f"{nextpay_payout_service.base_url}/api/v1/payout/transfer"
    
    print(f"Endpoint URL: {url}")
    print(f"Request Payload: {payload}")
    print(f"Request Headers: {headers}")
    print("-----------------------------------------")
    
    try:
        response = nextpay_payout_service.session.post(url, headers=headers, json=payload, timeout=15)
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
    except Exception as e:
        print(f"Error calling API: {e}")

if __name__ == '__main__':
    test_payout()
