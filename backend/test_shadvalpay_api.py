import os
import time
import json
import uuid
import hmac
import hashlib
import requests
import jwt
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration from .env
BASE_URL = os.getenv('SHADVALPAY_BASE_URL', 'https://partners.shadvalpay.co.in/api')
MERCHANT_ID = os.getenv('SHADVALPAY_MERCHANT_ID', 'XXXXXXXXXXXXXX') # Default for demonstration if not in .env
SHADVAL_KEY = os.getenv('SHADVALPAY_KEY', 'Your_ShadvalKey_Here')

def generate_signature(plain_text, key):
    """Generate HMAC SHA256 signature"""
    return hmac.new(
        key.encode('utf-8'),
        plain_text.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def test_create_qr_intent():
    print("==================================================")
    print("        TEST 1: CREATE UPI INTENT (QR CODE)       ")
    print("==================================================")
    
    url = f"{BASE_URL}/payment_gateway/upi_intent"
    
    # Test Data
    txn_amount = "1"
    txn_unique_id = f"TEST{int(time.time())}"
    customer_name = "JOHN DOE"
    email_address = "john.doe@example.com"
    mobile_number = "9876543210"
    remarks = "Test Payment API Approval"
    
    # Plain Text Format: ShadvalKey + merchant_id + txn_amount + txn_unique_id + customer_name + email_address + mobile_number
    plain_text = f"{SHADVAL_KEY}{MERCHANT_ID}{txn_amount}{txn_unique_id}{customer_name}{email_address}{mobile_number}"
    signature = generate_signature(plain_text, SHADVAL_KEY)
    
    headers = {
        'Content-Type': 'application/json',
        'authorization': SHADVAL_KEY,
        'payload': signature
    }
    
    payload = {
        "merchant_id": MERCHANT_ID,
        "txn_amount": txn_amount,
        "currency": "INR",
        "txn_unique_id": txn_unique_id,
        "customer_name": customer_name,
        "email_address": email_address,
        "mobile_number": mobile_number,
        "remarks": remarks,
        "device_os": "ANDROID"
    }
    
    print(f"\n[REQUEST]")
    print(f"URL     : POST {url}")
    print(f"HEADERS : {json.dumps(headers, indent=2)}")
    print(f"BODY    : {json.dumps(payload, indent=2)}")
    print(f"STRING TO SIGN: {plain_text}")
    print(f"SIGNATURE     : {signature}")
    
    try:
        print("\n[SENDING REQUEST...]")
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        print(f"\n[RESPONSE]")
        print(f"STATUS CODE : {response.status_code}")
        print(f"RESPONSE    : {json.dumps(response.json(), indent=2)}")
        
        response_data = response.json()
        payment_id = response_data.get('data', {}).get('payment_id')
        
        return txn_unique_id, payment_id
        
    except Exception as e:
        print(f"\n[ERROR] Request failed: {e}")
        return txn_unique_id, None

def test_check_status(txn_unique_id, payment_id):
    if not payment_id:
        print("\n[INFO] Skipping status check since no payment_id was generated in the previous step.")
        return

    print("\n==================================================")
    print("        TEST 2: CHECK UPI INTENT STATUS           ")
    print("==================================================")
    
    url = f"{BASE_URL}/payment_gateway/get_invoice_status"
    
    unique_request_id = f"CHK_{uuid.uuid4().hex[:10]}"
    
    # Plain Text Format: ShadvalKey + merchant_id + unique_request_id + txn_unique_id + payment_id
    plain_text = f"{SHADVAL_KEY}{MERCHANT_ID}{unique_request_id}{txn_unique_id}{payment_id}"
    signature = generate_signature(plain_text, SHADVAL_KEY)
    
    headers = {
        'Content-Type': 'application/json',
        'authorization': SHADVAL_KEY,
        'payload': signature
    }
    
    payload = {
        "merchant_id": MERCHANT_ID,
        "unique_request_id": unique_request_id,
        "txn_unique_id": txn_unique_id,
        "payment_id": payment_id
    }
    
    print(f"\n[REQUEST]")
    print(f"URL     : POST {url}")
    print(f"HEADERS : {json.dumps(headers, indent=2)}")
    print(f"BODY    : {json.dumps(payload, indent=2)}")
    print(f"STRING TO SIGN: {plain_text}")
    print(f"SIGNATURE     : {signature}")
    
    try:
        print("\n[SENDING REQUEST...]")
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        print(f"\n[RESPONSE]")
        print(f"STATUS CODE : {response.status_code}")
        print(f"RAW RESPONSE: {json.dumps(response.json(), indent=2)}")
        
        response_data = response.json()
        
        # Try to decrypt the 'data' field using JWT HS256
        encrypted_data = response_data.get('data')
        if encrypted_data and isinstance(encrypted_data, str) and response_data.get('status') == 'SUCCESS':
            print("\n[DECRYPTING RESPONSE DATA...]")
            try:
                decrypted_data = jwt.decode(
                    encrypted_data, 
                    MERCHANT_ID, 
                    algorithms=["HS256"]
                )
                print(f"DECRYPTED DATA: {json.dumps(decrypted_data, indent=2)}")
            except Exception as e:
                print(f"DECRYPTION ERROR: {e}")
                
    except Exception as e:
        print(f"\n[ERROR] Request failed: {e}")

if __name__ == "__main__":
    print(f"Testing with Merchant ID: {MERCHANT_ID}")
    print(f"Testing with ShadvalKey length: {len(SHADVAL_KEY) if SHADVAL_KEY else 0} characters")
    
    if MERCHANT_ID == 'XXXXXXXXXXXXXX' or not SHADVAL_KEY:
        print("\n[WARNING] It looks like the ShadvalPay credentials are not set in your .env file.")
        print("The test will use mock/default values and may fail authentication on the gateway side.")
        print("Please configure SHADVALPAY_MERCHANT_ID and SHADVALPAY_KEY in your .env file.")
    
    # Run tests
    txn_unique_id, payment_id = test_create_qr_intent()
    test_check_status(txn_unique_id, payment_id)
