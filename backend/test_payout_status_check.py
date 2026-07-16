"""
Test script for Payout Status Check API with Client Order ID

This script demonstrates how merchants can:
1. Login to get JWT token
2. Check payout status using their order ID

Similar to MoneyStake API pattern
"""

import requests
import json

# Configuration
BASE_URL = 'https://api.craftpay.in'  # Change to your API URL
# BASE_URL = 'http://localhost:5000'  # For local testing

# Merchant credentials
MERCHANT_ID = 'your_merchant_id'  # Replace with actual merchant ID
PASSWORD = 'your_password'  # Replace with actual password

# Order ID to check
ORDER_ID = 'ORDER12345'  # Replace with actual order ID


def print_section(title):
    """Print section header"""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def print_response(response):
    """Print formatted response"""
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))


def step1_merchant_login():
    """
    Step 1: Merchant Login and get token
    
    POST https://api.craftpay.in/api/merchant/login
    NO HEADER
    Body: {
        "merchantId": "your_merchant_id",
        "password": "your_password"
    }
    
    Response: {
        "success": true,
        "message": "Login successful",
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "merchantId": "your_merchant_id",
        "merchantName": "Your Business Name",
        "email": "your@email.com"
    }
    """
    print_section("STEP 1: Merchant Login")
    
    url = f"{BASE_URL}/api/merchant/login"
    
    payload = {
        "merchantId": MERCHANT_ID,
        "password": PASSWORD
    }
    
    print(f"\nRequest URL: {url}")
    print(f"Request Method: POST")
    print(f"Request Body:")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(url, json=payload)
        print_response(response)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                token = data.get('token')
                print(f"\n✓ Login successful!")
                print(f"✓ Token: {token[:50]}...")
                return token
            else:
                print(f"\n✗ Login failed: {data.get('message')}")
                return None
        else:
            print(f"\n✗ Login failed with status code: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        return None


def step2_check_payout_status(token):
    """
    Step 2: Check Payout Status with Client Order ID
    
    GET https://api.craftpay.in/api/payout/client/check-status-by-order-id/<ORDER_ID>
    HEADER: Authorization: Bearer <token>
    No Body
    
    Response: {
        "success": true,
        "message": "Payout status retrieved successfully",
        "data": {
            "order_id": "ORDER12345",
            "reference_id": "DP2026040221520368FF8E",
            "txn_id": "TXN5074C9A5A1B5",
            "amount": 2015.0,
            "status": "SUCCESS",
            "pg_partner": "Pg",
            "utr": "609221495505",
            "created_at": "2026-04-02 21:52:03",
            "completed_at": "2026-04-02 21:57:23"
        }
    }
    """
    print_section("STEP 2: Check Payout Status by Order ID")
    
    url = f"{BASE_URL}/api/payout/client/check-status-by-order-id/{ORDER_ID}"
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    print(f"\nRequest URL: {url}")
    print(f"Request Method: GET")
    print(f"Request Headers:")
    print(json.dumps({"Authorization": f"Bearer {token[:50]}..."}, indent=2))
    
    try:
        response = requests.get(url, headers=headers)
        print_response(response)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                payout_data = data.get('data', {})
                print(f"\n✓ Payout status retrieved successfully!")
                print(f"\n--- Payout Details ---")
                print(f"Order ID: {payout_data.get('order_id')}")
                print(f"Reference ID: {payout_data.get('reference_id')}")
                print(f"Transaction ID: {payout_data.get('txn_id')}")
                print(f"Amount: ₹{payout_data.get('amount')}")
                print(f"Status: {payout_data.get('status')}")
                print(f"PG Partner: {payout_data.get('pg_partner')}")
                print(f"UTR: {payout_data.get('utr')}")
                print(f"Created At: {payout_data.get('created_at')}")
                print(f"Completed At: {payout_data.get('completed_at')}")
                return True
            else:
                print(f"\n✗ Failed: {data.get('message')}")
                return False
        else:
            print(f"\n✗ Request failed with status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        return False


def main():
    """Main test flow"""
    print("\n" + "=" * 80)
    print(" ORCHPAY PAYOUT STATUS CHECK API TEST")
    print(" Similar to MoneyStake API Pattern")
    print("=" * 80)
    
    # Step 1: Login
    token = step1_merchant_login()
    
    if not token:
        print("\n✗ Test failed: Could not login")
        return
    
    # Step 2: Check payout status
    success = step2_check_payout_status(token)
    
    if success:
        print("\n" + "=" * 80)
        print(" ✓ TEST COMPLETED SUCCESSFULLY")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print(" ✗ TEST FAILED")
        print("=" * 80)


if __name__ == "__main__":
    main()
