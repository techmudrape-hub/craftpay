"""
Test script for Acceptpay Payin API Integration
Tests the complete payin flow including order creation and status checking
"""

import requests
import json
import time
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AcceptpayPayinTester:
    def __init__(self):
        self.base_url = os.getenv('ACCEPTPAY_BASE_URL', 'https://acceptpayfrontend.vercel.app').strip().strip('"').strip("'")
        self.token = os.getenv('ACCEPTPAY_TOKEN', '').strip().strip('"').strip("'")
        self.merchant_id = os.getenv('ACCEPTPAY_MERCHANT_ID', '').strip().strip('"').strip("'")
        self.api_secret = os.getenv('ACCEPTPAY_WEBHOOK_SECRET', '').strip().strip('"').strip("'")
        
        if not self.token:
            print("⚠️ WARNING: ACCEPTPAY_TOKEN is not set in .env file")
            self.token = "test_token_not_set"
            
        print("=" * 80)
        print("Acceptpay Payin Test Configuration")
        print("=" * 80)
        print(f"Base URL: {self.base_url}")
        print(f"Token: {self.token[:5]}...{self.token[-5:] if len(self.token) > 10 else ''}")
        print("=" * 80)
    
    def get_headers(self):
        """Get request headers for Acceptpay API"""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}',
            'X-API-Key': self.token,
            'apikey': self.token
        }
        if self.api_secret:
            headers['X-API-Secret'] = self.api_secret
        if self.merchant_id:
            headers['X-Merchant-Id'] = self.merchant_id
            headers['merchantId'] = self.merchant_id
        return headers
    
    def test_initiate_transaction(self, amount=100, test_name="Test User"):
        """
        Test initiating a payment transaction
        
        Args:
            amount: Payment amount (minimum 1)
            test_name: Test identifier
        
        Returns:
            dict: Response from Acceptpay API
        """
        print("\n" + "=" * 80)
        print("TEST 1: Initiate Transaction")
        print("=" * 80)
        
        # Generate unique bill ID
        bill_id = f"TEST_ACC_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        customer_mobile = "9876543210"
        customer_email = "test@example.com"
        
        # Prepare request payload
        payload = {
            'amount': int(amount),
            'mobile': customer_mobile,
            'email': customer_email,
            'billId': bill_id,
            'description': f"Payment from {test_name}",
            'customerName': test_name
        }
        
        if self.merchant_id:
            payload['merchantId'] = self.merchant_id
        
        url = f"{self.base_url}/api/v1/transaction/initiate-transaction"
        
        print(f"\n[Request Details]")
        print(f"Endpoint: {url}")
        print(f"Bill ID: {bill_id}")
        print(f"Amount: ₹{amount}")
        print(f"\n[Request Payload]")
        print(json.dumps(payload, indent=2))
        
        try:
            print(f"\n[Sending Request]")
            start_time = time.time()
            
            response = requests.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=30,
                allow_redirects=False  # Crucial to see if we're getting redirected!
            )
            
            elapsed_time = time.time() - start_time
            
            print(f"\n[Response Received]")
            print(f"Status Code: {response.status_code}")
            print(f"Response Time: {elapsed_time:.2f}s")
            if response.is_redirect:
                print(f"⚠️ REDIRECT DETECTED! Redirected to: {response.headers.get('Location')}")
            print(f"Response Headers: {dict(response.headers)}")
            print(f"\n[Response Body]")
            
            try:
                response_data = response.json()
                print(json.dumps(response_data, indent=2))
            except ValueError:
                response_data = None
                print(response.text)
                
            if response.status_code in [200, 201] and response_data and response_data.get('status') == 'success':
                print(f"\n✅ SUCCESS: Payment order created")
                data = response_data.get('data', {})
                txn_id = data.get('transactionId') or data.get('_id', '')
                print(f"Transaction ID: {txn_id}")
                print(f"Payment Link: {data.get('paymentLink')}")
                
                return {
                    'success': True,
                    'transaction_id': txn_id,
                    'bill_id': bill_id,
                    'payment_link': data.get('paymentLink'),
                    'response': response_data
                }
            else:
                error_msg = response_data.get('message') if response_data else "Unknown error"
                print(f"\n❌ FAILED: {error_msg}")
                return {
                    'success': False,
                    'bill_id': bill_id,
                    'error': error_msg
                }
                
        except Exception as e:
            print(f"\n❌ EXCEPTION: {e}")
            return {
                'success': False,
                'bill_id': bill_id,
                'error': str(e)
            }
            
    def test_check_status(self, transaction_id):
        """
        Test checking payment status
        
        Args:
            transaction_id: The transaction ID from Acceptpay
        """
        print("\n" + "=" * 80)
        print("TEST 2: Check Payment Status")
        print("=" * 80)
        
        url = f"{self.base_url}/api/v1/transaction/status-of-transaction/{transaction_id}"
        
        print(f"\n[Request Details]")
        print(f"Endpoint: {url}")
        print(f"Transaction ID: {transaction_id}")
        
        try:
            print(f"\n[Sending Request]")
            start_time = time.time()
            
            response = requests.get(
                url,
                headers=self.get_headers(),
                timeout=30
            )
            
            elapsed_time = time.time() - start_time
            
            print(f"\n[Response Received]")
            print(f"Status Code: {response.status_code}")
            print(f"Response Time: {elapsed_time:.2f}s")
            print(f"\n[Response Body]")
            
            try:
                response_data = response.json()
                print(json.dumps(response_data, indent=2))
            except ValueError:
                response_data = None
                print(response.text)
                
            if response.status_code == 200 and response_data and response_data.get('status') == 'success':
                data = response_data.get('data', {})
                print(f"\n✅ SUCCESS: Status retrieved")
                print(f"Transaction Status: {data.get('status', 'UNKNOWN').upper()}")
                print(f"Amount: ₹{data.get('amount')}")
                print(f"Gateway Payment ID: {data.get('gatewayPaymentId', 'N/A')}")
                
                return {
                    'success': True,
                    'status': data.get('status'),
                    'data': data
                }
            else:
                error_msg = response_data.get('message') if response_data else "Unknown error"
                print(f"\n❌ FAILED: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            print(f"\n❌ EXCEPTION: {e}")
            return {
                'success': False,
                'error': str(e)
            }

def main():
    """Main test function"""
    print("\n" + "=" * 80)
    print("ACCEPTPAY PAYIN TEST SCRIPT")
    print("=" * 80)
    
    try:
        tester = AcceptpayPayinTester()
        
        print("\nSelect test to run:")
        print("1. Initiate Payment Transaction")
        print("2. Check Payment Status")
        print("3. Quick Test (Initiate + Wait 10s + Check Status)")
        
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == '1':
            amount = input("Enter amount (default 100): ").strip()
            amount = int(amount) if amount else 100
            tester.test_initiate_transaction(amount=amount)
            
        elif choice == '2':
            txn_id = input("Enter Transaction ID (from Acceptpay): ").strip()
            if not txn_id:
                print("❌ Transaction ID is required")
                return
            tester.test_check_status(txn_id)
            
        elif choice == '3':
            amount = input("Enter amount (default 100): ").strip()
            amount = int(amount) if amount else 100
            
            result = tester.test_initiate_transaction(amount=amount)
            
            if result.get('success'):
                txn_id = result.get('transaction_id')
                print(f"\nPayment Link: {result.get('payment_link')}")
                print("\nWaiting 10 seconds before status check...")
                time.sleep(10)
                tester.test_check_status(txn_id)
                
        else:
            print("❌ Invalid choice")
            
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
