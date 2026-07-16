"""
Test script for User Transaction Summary endpoints
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:5000"
ADMIN_ID = "admin"
PASSWORD = "Admin@123"

def test_user_transaction_summary():
    """Test the user transaction summary endpoints"""
    
    print("=" * 60)
    print("Testing User Transaction Summary Endpoints")
    print("=" * 60)
    
    # Step 1: Login as admin
    print("\n1. Logging in as admin...")
    login_response = requests.post(
        f"{BASE_URL}/api/admin/login",
        json={
            "adminId": ADMIN_ID,
            "password": PASSWORD
        }
    )
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        print(login_response.text)
        return
    
    login_data = login_response.json()
    if not login_data.get('success'):
        print(f"❌ Login failed: {login_data.get('message')}")
        return
    
    token = login_data.get('token')
    print(f"✅ Login successful! Token: {token[:20]}...")
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Step 2: Get merchants list
    print("\n2. Fetching merchants list...")
    merchants_response = requests.get(
        f"{BASE_URL}/api/admin/user-transaction-summary/merchants",
        headers=headers
    )
    
    print(f"Status Code: {merchants_response.status_code}")
    print(f"Response: {json.dumps(merchants_response.json(), indent=2)}")
    
    if merchants_response.status_code != 200:
        print(f"❌ Failed to fetch merchants")
        return
    
    merchants_data = merchants_response.json()
    if not merchants_data.get('success'):
        print(f"❌ Failed to fetch merchants: {merchants_data.get('message')}")
        return
    
    merchants = merchants_data.get('merchants', [])
    print(f"✅ Found {len(merchants)} merchants")
    
    if len(merchants) == 0:
        print("⚠️  No merchants found. Cannot test summary endpoint.")
        return
    
    # Step 3: Get summary for first merchant
    test_merchant_id = merchants[0]['merchant_id']
    print(f"\n3. Fetching summary for merchant: {test_merchant_id}")
    
    summary_response = requests.get(
        f"{BASE_URL}/api/admin/user-transaction-summary/summary",
        headers=headers,
        params={
            'merchant_id': test_merchant_id,
            'from_date': '2026-05-01',
            'to_date': '2026-05-13'
        }
    )
    
    print(f"Status Code: {summary_response.status_code}")
    
    if summary_response.status_code != 200:
        print(f"❌ Failed to fetch summary")
        print(f"Response: {summary_response.text}")
        return
    
    summary_data = summary_response.json()
    print(f"Response: {json.dumps(summary_data, indent=2)}")
    
    if summary_data.get('success'):
        print(f"\n✅ Summary fetched successfully!")
        print(f"   Merchant: {summary_data['merchant']['full_name']}")
        print(f"   Payin - Total: ₹{summary_data['payin_summary']['total_payin']}, Net: ₹{summary_data['payin_summary']['net_payin']}")
        print(f"   Payout - Total: ₹{summary_data['payout_summary']['total_payout']}, Net: ₹{summary_data['payout_summary']['net_payout']}")
    else:
        print(f"❌ Failed to fetch summary: {summary_data.get('message')}")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    test_user_transaction_summary()
