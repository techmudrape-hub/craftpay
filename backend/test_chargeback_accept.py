#!/usr/bin/env python3
"""
Test chargeback acceptance endpoint
"""

import requests
import json

# Configuration
API_BASE_URL = "http://localhost:5000/api"
# Replace with your actual merchant credentials
MERCHANT_ID = "7679022140"
PASSWORD = "So@080903"

def test_chargeback_accept():
    """Test the chargeback acceptance flow"""
    
    # Step 1: Login to get token
    print("Step 1: Logging in...")
    login_response = requests.post(
        f"{API_BASE_URL}/merchant/login",
        json={
            "merchantId": MERCHANT_ID,
            "password": PASSWORD
        }
    )
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.text}")
        return
    
    login_data = login_response.json()
    if not login_data.get('success'):
        print(f"❌ Login failed: {login_data.get('message')}")
        return
    
    token = login_data.get('token')
    print(f"✅ Login successful. Token: {token[:20]}...")
    
    # Step 2: Get chargebacks
    print("\nStep 2: Getting chargebacks...")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    chargebacks_response = requests.get(
        f"{API_BASE_URL}/chargeback/merchant/chargebacks",
        headers=headers
    )
    
    if chargebacks_response.status_code != 200:
        print(f"❌ Get chargebacks failed: {chargebacks_response.text}")
        return
    
    chargebacks_data = chargebacks_response.json()
    if not chargebacks_data.get('success'):
        print(f"❌ Get chargebacks failed: {chargebacks_data.get('message')}")
        return
    
    chargebacks = chargebacks_data.get('chargebacks', [])
    print(f"✅ Found {len(chargebacks)} chargebacks")
    
    # Find a pending chargeback
    pending_chargeback = None
    for cb in chargebacks:
        if cb.get('acceptance_status') == 'PENDING':
            pending_chargeback = cb
            break
    
    if not pending_chargeback:
        print("⚠️  No pending chargebacks found to test")
        return
    
    print(f"\nFound pending chargeback:")
    print(f"  ID: {pending_chargeback['id']}")
    print(f"  Transaction ID: {pending_chargeback['transaction_id']}")
    print(f"  Amount: {pending_chargeback['chargeback_amount']}")
    
    # Step 3: Accept the chargeback
    print(f"\nStep 3: Accepting chargeback ID {pending_chargeback['id']}...")
    accept_response = requests.post(
        f"{API_BASE_URL}/chargeback/merchant/accept/{pending_chargeback['id']}",
        headers=headers,
        json={}  # Send empty JSON body
    )
    
    print(f"Response Status Code: {accept_response.status_code}")
    print(f"Response Headers: {dict(accept_response.headers)}")
    print(f"Response Text: {accept_response.text[:500]}")
    
    if accept_response.status_code != 200:
        print(f"❌ Accept chargeback failed with status {accept_response.status_code}")
        return
    
    try:
        accept_data = accept_response.json()
        if accept_data.get('success'):
            print(f"✅ Chargeback accepted successfully!")
            print(f"  Deduction ID: {accept_data.get('deduction_id')}")
            print(f"  Deduction Amount: {accept_data.get('deduction_amount')}")
            print(f"  Previous Balance: {accept_data.get('previous_balance')}")
            print(f"  New Balance: {accept_data.get('new_balance')}")
        else:
            print(f"❌ Accept failed: {accept_data.get('message')}")
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse JSON response: {e}")
        print(f"Response content: {accept_response.text}")

if __name__ == '__main__':
    test_chargeback_accept()
