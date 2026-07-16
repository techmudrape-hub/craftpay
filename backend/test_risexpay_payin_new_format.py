import requests
import time
import json
import hmac
import hashlib
import sys
import os

# Add current directory to path to import config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import Config

def test_risexpay_callback(order_id="ORD_42_1720000000_1234", amount=1500, status="COMPLETED"):
    url = "http://localhost:5000/api/callback/risexpay/payin"
    secret_key = Config.RISEXPAY_SECRET_KEY
    
    if not secret_key:
        print("ERROR: RISEXPAY_SECRET_KEY not found in config.")
        return
        
    payload = {
        "event": "payment.update",
        "payment_status": status,
        "order": {
            "order_id": order_id,
            "imb_order_id": "IMB20250101ABCD",
            "amount": amount,
            "customer_mobile": "9876543210",
            "status": status,
            "txn_id": "TXN123456789",
            "utr": "HDFC0012345678",
            "remark1": "Order #001",
            "remark2": "",
            "created_at": "2025-01-01 10:00:00",
            "updated_at": "2025-01-01 10:05:00"
        }
    }
    
    timestamp = str(int(time.time()))
    
    # Generate signature
    parts = [f"timestamp={timestamp}"]
    for k in sorted(payload.keys()):
        v = payload[k]
        if isinstance(v, (dict, list)):
            val_str = json.dumps(v, separators=(',', ':'))
        elif isinstance(v, bool):
            val_str = "1" if v else ""
        elif v is None:
            val_str = ""
        else:
            val_str = str(v)
        parts.append(f"{k}={val_str}")
        
    sig_string = "&".join(parts)
    print("Signing String:", sig_string)
    
    signature = hmac.new(
        secret_key.encode('utf-8'),
        sig_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        "Content-Type": "application/json",
        "X-Timestamp": timestamp,
        "X-Signature": signature
    }
    
    print("-" * 50)
    print("Testing Risexpay Payin Webhook")
    print("-" * 50)
    print(f"URL: {url}")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("-" * 50)
    
    print(f"Sending POST request...")
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"Response Code: {response.status_code}")
        print(f"Response Body: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_risexpay_callback()
