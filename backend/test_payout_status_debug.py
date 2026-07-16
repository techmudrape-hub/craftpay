"""
Debug script to test payout status check API and diagnose issues
"""

import requests
import json
import sys

# Configuration
BASE_URL = 'https://api.craftpay.in'
# BASE_URL = 'http://localhost:5000'  # Uncomment for local testing

# Test credentials - UPDATE THESE
MERCHANT_ID = 'your_merchant_id'  # Replace with actual merchant ID
PASSWORD = 'your_password'  # Replace with actual password
ORDER_ID = 'TEST989sssddfg1116872rrewe'  # Replace with actual order ID


def print_header(title):
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def print_request(method, url, headers=None, body=None):
    print(f"\n→ REQUEST:")
    print(f"  Method: {method}")
    print(f"  URL: {url}")
    if headers:
        print(f"  Headers:")
        for key, value in headers.items():
            if key.lower() == 'authorization' and len(value) > 50:
                print(f"    {key}: {value[:50]}...")
            else:
                print(f"    {key}: {value}")
    if body:
        print(f"  Body:")
        print(f"    {json.dumps(body, indent=4)}")


def print_response(response):
    print(f"\n← RESPONSE:")
    print(f"  Status Code: {response.status_code}")
    print(f"  Headers:")
    for key, value in response.headers.items():
        print(f"    {key}: {value}")
    print(f"  Body:")
    try:
        print(f"    {json.dumps(response.json(), indent=4)}")
    except:
        print(f"    {response.text}")


def test_login():
    """Test merchant login"""
    print_header("TEST 1: MERCHANT LOGIN")
    
    url = f"{BASE_URL}/api/merchant/login"
    headers = {'Content-Type': 'application/json'}
    body = {
        'merchantId': MERCHANT_ID,
        'password': PASSWORD
    }
    
    print_request('POST', url, headers, body)
    
    try:
        response = requests.post(url, json=body, headers=headers)
        print_response(response)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                token = data.get('token')
                print(f"\n✓ LOGIN SUCCESSFUL")
                print(f"✓ Token: {token[:50]}...")
                return token
            else:
                print(f"\n✗ LOGIN FAILED: {data.get('message')}")
                return None
        else:
            print(f"\n✗ LOGIN FAILED: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        return None


def test_status_check(token):
    """Test payout status check"""
    print_header("TEST 2: CHECK PAYOUT STATUS")
    
    url = f"{BASE_URL}/api/payout/client/check-status-by-order-id/{ORDER_ID}"
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    print_request('GET', url, headers)
    
    try:
        response = requests.get(url, headers=headers)
        print_response(response)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"\n✓ STATUS CHECK SUCCESSFUL")
                payout = data.get('data', {})
                print(f"\n--- PAYOUT DETAILS ---")
                print(f"Order ID: {payout.get('order_id')}")
                print(f"Status: {payout.get('status')}")
                print(f"Amount: ₹{payout.get('amount')}")
                print(f"UTR: {payout.get('utr')}")
                print(f"Created: {payout.get('created_at')}")
                print(f"Completed: {payout.get('completed_at')}")
                return True
            else:
                print(f"\n✗ STATUS CHECK FAILED: {data.get('message')}")
                return False
        elif response.status_code == 404:
            print(f"\n✗ TRANSACTION NOT FOUND")
            print(f"  Order ID '{ORDER_ID}' not found for this merchant")
            return False
        elif response.status_code == 401:
            print(f"\n✗ UNAUTHORIZED")
            print(f"  Token is invalid or expired")
            return False
        elif response.status_code == 500:
            print(f"\n✗ INTERNAL SERVER ERROR")
            print(f"  Check server logs for details")
            data = response.json()
            if 'error' in data:
                print(f"  Error: {data['error']}")
            return False
        else:
            print(f"\n✗ UNEXPECTED STATUS CODE: {response.status_code}")
            return False
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_without_token():
    """Test status check without token (should fail)"""
    print_header("TEST 3: CHECK STATUS WITHOUT TOKEN (Should Fail)")
    
    url = f"{BASE_URL}/api/payout/client/check-status-by-order-id/{ORDER_ID}"
    
    print_request('GET', url)
    
    try:
        response = requests.get(url)
        print_response(response)
        
        if response.status_code == 401:
            print(f"\n✓ CORRECTLY REJECTED (No token)")
        else:
            print(f"\n✗ UNEXPECTED: Should have returned 401")
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")


def main():
    print("\n" + "=" * 80)
    print(" ORCHPAY PAYOUT STATUS CHECK API - DEBUG TEST")
    print("=" * 80)
    print(f"\nConfiguration:")
    print(f"  Base URL: {BASE_URL}")
    print(f"  Merchant ID: {MERCHANT_ID}")
    print(f"  Order ID: {ORDER_ID}")
    
    # Check if credentials are set
    if MERCHANT_ID == 'your_merchant_id' or PASSWORD == 'your_password':
        print("\n" + "!" * 80)
        print(" WARNING: Please update MERCHANT_ID and PASSWORD in the script")
        print("!" * 80)
        sys.exit(1)
    
    # Test 1: Login
    token = test_login()
    if not token:
        print("\n" + "=" * 80)
        print(" TEST FAILED: Could not login")
        print("=" * 80)
        sys.exit(1)
    
    # Test 2: Check status with token
    success = test_status_check(token)
    
    # Test 3: Check status without token
    test_without_token()
    
    # Summary
    print("\n" + "=" * 80)
    if success:
        print(" ✓ ALL TESTS PASSED")
    else:
        print(" ✗ SOME TESTS FAILED")
    print("=" * 80)


if __name__ == "__main__":
    main()
