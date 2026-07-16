"""
Test MoneyOne Payin Order Creation
This script tests creating a payin order through OrchPay that routes to MoneyOne
"""

import requests
import json
from utils import encrypt_aes, decrypt_aes

# Configuration
API_URL = 'https://api.craftpay.in/api/payin/order/create'
# API_URL = 'http://localhost:5000/api/payin/order/create'  # For local testing

# Step 1: Login to get JWT token
LOGIN_URL = 'https://api.craftpay.in/api/merchant/login'
# LOGIN_URL = 'http://localhost:5000/api/merchant/login'  # For local testing

def login_merchant(merchant_id, password):
    """Login to get JWT token"""
    print("=" * 80)
    print("STEP 1: Merchant Login")
    print("=" * 80)
    
    response = requests.post(
        LOGIN_URL,
        json={
            'merchant_id': merchant_id,
            'password': password
        }
    )
    
    print(f"Login Response: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            token = data.get('token')
            print(f"✓ Login successful, token obtained")
            return token
    
    print("✗ Login failed")
    return None

def create_payin_order(jwt_token, merchant_aes_key, merchant_aes_iv):
    """Create payin order"""
    print("\n" + "=" * 80)
    print("STEP 2: Create Payin Order")
    print("=" * 80)
    
    # Prepare order data
    order_data = {
        'amount': 100.0,
        'orderid': 'TEST_ORDER_' + str(int(time.time())),
        'payee_fname': 'John',
        'payee_lname': 'Doe',
        'payee_mobile': '9876543210',
        'payee_email': 'john.doe@example.com',
        'callbackurl': 'https://yourwebsite.com/callback'  # Optional
    }
    
    print(f"Order Data: {json.dumps(order_data, indent=2)}")
    
    # Encrypt with MERCHANT's AES key/IV (not MoneyOne's)
    print(f"\nEncrypting with merchant AES key: {merchant_aes_key}")
    print(f"Encrypting with merchant AES IV: {merchant_aes_iv}")
    
    encrypted_payload = encrypt_aes(
        json.dumps(order_data),
        merchant_aes_key,
        merchant_aes_iv
    )
    
    if not encrypted_payload:
        print("✗ Failed to encrypt payload")
        return None
    
    print(f"✓ Payload encrypted successfully")
    print(f"Encrypted payload (first 100 chars): {encrypted_payload[:100]}...")
    
    # Send request
    print(f"\nSending request to: {API_URL}")
    
    response = requests.post(
        API_URL,
        headers={
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        },
        json={
            'data': encrypted_payload
        }
    )
    
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        response_data = response.json()
        
        if response_data.get('success'):
            print("\n✓ Order created successfully!")
            
            # Decrypt response
            encrypted_response = response_data.get('data')
            if encrypted_response:
                print(f"\nDecrypting response with merchant AES key...")
                decrypted_response = decrypt_aes(
                    encrypted_response,
                    merchant_aes_key,
                    merchant_aes_iv
                )
                
                if decrypted_response:
                    order_response = json.loads(decrypted_response)
                    print(f"\nDecrypted Response:")
                    print(json.dumps(order_response, indent=2))
                    
                    # Extract payment link/QR
                    qr_string = order_response.get('qr_string', '')
                    upi_link = order_response.get('upi_link', '')
                    payment_link = order_response.get('payment_link', '')
                    
                    print(f"\n" + "=" * 80)
                    print("PAYMENT DETAILS")
                    print("=" * 80)
                    print(f"Transaction ID: {order_response.get('txn_id')}")
                    print(f"Order ID: {order_response.get('order_id')}")
                    print(f"Amount: ₹{order_response.get('amount')}")
                    print(f"Charge: ₹{order_response.get('charge_amount')}")
                    print(f"Net Amount: ₹{order_response.get('net_amount')}")
                    print(f"PG Partner: {order_response.get('pg_partner')}")
                    
                    if qr_string:
                        print(f"\nQR String: {qr_string[:100]}...")
                    if upi_link:
                        print(f"\nUPI Link: {upi_link}")
                    if payment_link:
                        print(f"\nPayment Link: {payment_link}")
                    
                    return order_response
                else:
                    print("✗ Failed to decrypt response")
        else:
            print(f"✗ Order creation failed: {response_data.get('message')}")
    else:
        print(f"✗ Request failed with status {response.status_code}")
    
    return None

if __name__ == '__main__':
    import time
    
    print("=" * 80)
    print("MoneyOne Payin Test Script")
    print("=" * 80)
    
    # IMPORTANT: Replace these with your actual merchant credentials
    MERCHANT_ID = 'YOUR_MERCHANT_ID'  # e.g., '7679022140'
    MERCHANT_PASSWORD = 'YOUR_MERCHANT_PASSWORD'
    MERCHANT_AES_KEY = 'YOUR_MERCHANT_AES_KEY'  # From merchants table
    MERCHANT_AES_IV = 'YOUR_MERCHANT_AES_IV'    # From merchants table
    
    print(f"\nMerchant ID: {MERCHANT_ID}")
    print(f"Merchant AES Key: {MERCHANT_AES_KEY}")
    print(f"Merchant AES IV: {MERCHANT_AES_IV}")
    
    # Step 1: Login
    jwt_token = login_merchant(MERCHANT_ID, MERCHANT_PASSWORD)
    
    if not jwt_token:
        print("\n✗ Cannot proceed without JWT token")
        exit(1)
    
    # Step 2: Create order
    order_result = create_payin_order(jwt_token, MERCHANT_AES_KEY, MERCHANT_AES_IV)
    
    if order_result:
        print("\n" + "=" * 80)
        print("✓ TEST COMPLETED SUCCESSFULLY")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("✗ TEST FAILED")
        print("=" * 80)
