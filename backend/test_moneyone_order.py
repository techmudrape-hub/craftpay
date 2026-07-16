"""
Test MoneyOne Payin Order Creation
Tests the complete flow: Merchant -> OrchPay -> MoneyOne
"""

import requests
import json
import sys
import os

# Add parent directory to path to import utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import encrypt_aes, decrypt_aes
import time

# OrchPay API Configuration
ORCHPAY_API_URL = 'https://api.craftpay.in/api/payin/order/create'
ORCHPAY_LOGIN_URL = 'https://api.craftpay.in/api/merchant/login'

# Your OrchPay Merchant Credentials
MERCHANT_ID = '7679022140'
MERCHANT_PASSWORD = 'So@080903'
MERCHANT_AES_KEY = '37d384e12f4830159177843df8'
MERCHANT_AES_IV = 'jLHrd909PF7XsbpV'

def login_merchant():
    """Step 1: Login to OrchPay to get JWT token"""
    print("=" * 80)
    print("STEP 1: Login to OrchPay")
    print("=" * 80)
    print(f"Merchant ID: {MERCHANT_ID}")
    print(f"Login URL: {ORCHPAY_LOGIN_URL}")
    
    try:
        response = requests.post(
            ORCHPAY_LOGIN_URL,
            json={
                'merchantId': MERCHANT_ID,  # Note: camelCase
                'password': MERCHANT_PASSWORD
            },
            timeout=30
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                token = data.get('token')
                print(f"\n✓ Login successful!")
                print(f"JWT Token: {token[:50]}...")
                return token
            else:
                print(f"\n✗ Login failed: {data.get('message')}")
                return None
        else:
            print(f"\n✗ Login failed with status {response.status_code}")
            return None
            
    except Exception as e:
        print(f"\n✗ Login error: {e}")
        return None

def create_payin_order(jwt_token):
    """Step 2: Create payin order through OrchPay (routes to MoneyOne)"""
    print("\n" + "=" * 80)
    print("STEP 2: Create Payin Order")
    print("=" * 80)
    
    # Prepare order data
    order_data = {
        'amount': 100.0,
        'orderid': f'TEST_{int(time.time())}',
        'payee_fname': 'John',
        'payee_lname': 'Doe',
        'payee_mobile': '9876543210',
        'payee_email': 'john.doe@example.com',
        'callbackurl': 'https://yourwebsite.com/callback'
    }
    
    print(f"Order Data:")
    print(json.dumps(order_data, indent=2))
    
    # Encrypt with MERCHANT's AES credentials
    print(f"\nEncrypting with Merchant AES Key: {MERCHANT_AES_KEY}")
    print(f"Encrypting with Merchant AES IV: {MERCHANT_AES_IV}")
    
    encrypted_payload = encrypt_aes(
        json.dumps(order_data),
        MERCHANT_AES_KEY,
        MERCHANT_AES_IV
    )
    
    if not encrypted_payload:
        print("\n✗ Failed to encrypt payload")
        return None
    
    print(f"\n✓ Payload encrypted successfully")
    print(f"Encrypted (first 100 chars): {encrypted_payload[:100]}...")
    
    # Send request to OrchPay
    print(f"\nSending request to: {ORCHPAY_API_URL}")
    
    try:
        response = requests.post(
            ORCHPAY_API_URL,
            headers={
                'Authorization': f'Bearer {jwt_token}',
                'Content-Type': 'application/json'
            },
            json={
                'data': encrypted_payload
            },
            timeout=60
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response: {response.text[:1000]}")
        
        if response.status_code == 200:
            response_data = response.json()
            
            if response_data.get('success'):
                print("\n✓ Order created successfully!")
                
                # Decrypt response with MERCHANT's AES credentials
                encrypted_response = response_data.get('data')
                if encrypted_response:
                    print(f"\nDecrypting response with Merchant AES credentials...")
                    
                    decrypted_response = decrypt_aes(
                        encrypted_response,
                        MERCHANT_AES_KEY,
                        MERCHANT_AES_IV
                    )
                    
                    if decrypted_response:
                        order_response = json.loads(decrypted_response)
                        
                        print("\n" + "=" * 80)
                        print("PAYMENT DETAILS")
                        print("=" * 80)
                        print(json.dumps(order_response, indent=2))
                        
                        print("\n" + "=" * 80)
                        print("KEY INFORMATION")
                        print("=" * 80)
                        print(f"Transaction ID: {order_response.get('txn_id')}")
                        print(f"Order ID: {order_response.get('order_id')}")
                        print(f"Amount: ₹{order_response.get('amount')}")
                        print(f"Charge: ₹{order_response.get('charge_amount')}")
                        print(f"Net Amount: ₹{order_response.get('net_amount')}")
                        print(f"PG Partner: {order_response.get('pg_partner')}")
                        
                        # Extract payment links
                        qr_string = order_response.get('qr_string', '')
                        upi_link = order_response.get('upi_link', '')
                        payment_link = order_response.get('payment_link', '')
                        intent_url = order_response.get('intent_url', '')
                        
                        if qr_string:
                            print(f"\n📱 QR String: {qr_string[:100]}...")
                        if upi_link:
                            print(f"\n💳 UPI Link: {upi_link}")
                        if payment_link:
                            print(f"\n🔗 Payment Link: {payment_link}")
                        if intent_url:
                            print(f"\n🔗 Intent URL: {intent_url}")
                        
                        return order_response
                    else:
                        print("\n✗ Failed to decrypt response")
                        return None
                else:
                    print("\n⚠ No encrypted data in response")
                    return response_data
            else:
                print(f"\n✗ Order creation failed: {response_data.get('message')}")
                return None
        else:
            print(f"\n✗ Request failed with status {response.status_code}")
            return None
            
    except Exception as e:
        print(f"\n✗ Request error: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("=" * 80)
    print("MoneyOne Payin Integration Test")
    print("=" * 80)
    print("\nThis test will:")
    print("1. Login to OrchPay with merchant credentials")
    print("2. Create a payin order (OrchPay will route to MoneyOne)")
    print("3. Display the payment link/QR code")
    print("\n" + "=" * 80)
    
    # Step 1: Login
    jwt_token = login_merchant()
    if not jwt_token:
        print("\n" + "=" * 80)
        print("✗ TEST FAILED - Could not login")
        print("=" * 80)
        return
    
    # Step 2: Create order
    order_result = create_payin_order(jwt_token)
    
    if order_result:
        print("\n" + "=" * 80)
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print("\nNext Steps:")
        print("1. Use the UPI link/QR code to make a test payment")
        print("2. Check the transaction status in the database")
        print("3. Verify the callback is received")
        print("4. Confirm wallet is credited")
    else:
        print("\n" + "=" * 80)
        print("✗ TEST FAILED - Could not create order")
        print("=" * 80)

if __name__ == '__main__':
    main()
