import requests
import json
import time
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
SECTORPE_BASE_URL = os.getenv('SECTORPE_BASE_URL', 'https://banking.sectorpe.com')
SECTORPE_TOKEN = os.getenv('SECTORPE_TOKEN', 'YOUR_SECTORPE_TOKEN_HERE')

def test_generate_payment_link():
    """Test the SectorPe generate payment link API"""
    print("="*50)
    print("TESTING SECTORPE PAYIN API")
    print("="*50)

    if not SECTORPE_TOKEN or SECTORPE_TOKEN == 'YOUR_SECTORPE_TOKEN_HERE':
        print("⚠️ WARNING: SECTORPE_TOKEN is not set properly in .env")
        print("Please set your actual token before running in production.")
        print("-" * 50)

    # Generate a random transaction ID for testing
    txnid = f"TEST_{int(time.time())}"
    
    # Request Payload
    payload = {
        "txnid": txnid,
        "name": "Test User",
        "email": "test@example.com",
        "mobile": "9876543210",
        "amount": "100",  # Test amount
        "token": SECTORPE_TOKEN
    }

    url = f"{SECTORPE_BASE_URL}/routes/generate_payment_link.php"
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    print(f"Endpoint: POST {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("\nSending request...")

    try:
        start_time = time.time()
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        elapsed_time = time.time() - start_time

        print(f"\nResponse Time: {elapsed_time:.2f} seconds")
        print(f"Status Code: {response.status_code}")
        
        try:
            response_json = response.json()
            print(f"Response Body:\n{json.dumps(response_json, indent=2)}")
            
            if response_json.get('error') == False or response_json.get('status') == 'success':
                print("\n✅ SUCCESS: Payment link generated successfully!")
                print(f"Payment Link: {response_json.get('paymentLink', 'N/A')}")
                print(f"UPI Link: {response_json.get('upiLink', 'N/A')}")
                
                # Check the status of this newly created order
                print("\nWaiting 2 seconds before checking status...")
                time.sleep(2)
                test_check_status(txnid)
            else:
                print(f"\n❌ FAILED: API returned an error: {response_json.get('message')}")
                
        except json.JSONDecodeError:
            print(f"Response Body (Raw): {response.text}")
            print("\n❌ FAILED: Response was not valid JSON")

    except requests.exceptions.RequestException as e:
        print(f"\n❌ FAILED: Request error: {e}")

def test_check_status(txnid):
    """Test the SectorPe get order status API"""
    print("="*50)
    print("TESTING SECTORPE STATUS CHECK API")
    print("="*50)

    payload = {
        "txnid": txnid,
        "type": "payin",
        "token": SECTORPE_TOKEN
    }

    url = f"{SECTORPE_BASE_URL}/routes/get_order_status.php"
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    print(f"Endpoint: POST {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("\nSending request...")

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        
        try:
            response_json = response.json()
            print(f"Response Body:\n{json.dumps(response_json, indent=2)}")
            
            if response_json.get('status') != 'error':
                print("\n✅ SUCCESS: Status check completed successfully!")
                print(f"Transaction Status: {response_json.get('txn_status', 'N/A')}")
            else:
                print(f"\n❌ FAILED: API returned an error: {response_json.get('message')}")
                
        except json.JSONDecodeError:
            print(f"Response Body (Raw): {response.text}")
            print("\n❌ FAILED: Response was not valid JSON")

    except requests.exceptions.RequestException as e:
        print(f"\n❌ FAILED: Request error: {e}")

if __name__ == "__main__":
    test_generate_payment_link()
