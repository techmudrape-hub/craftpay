"""
Test script for ORO Payin Integration
Tests the payin flow including order creation
"""

import requests
import json
import time
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class OroPayinTester:
    def __init__(self):
        self.base_url = os.getenv('ORO_BASE_URL', 'http://oroitsolution.info/api')
        self.client_id = os.getenv('ORO_CLIENT_ID')
        self.secret_id = os.getenv('ORO_SECRET_ID')
        
        if not self.client_id or not self.secret_id:
            print("WARNING: ORO_CLIENT_ID and ORO_SECRET_ID should be set in .env file")
            print("Using dummy values for testing if not provided.")
            self.client_id = self.client_id or "TEST_CLIENT_ID"
            self.secret_id = self.secret_id or "TEST_SECRET_ID"
        
        print("=" * 80)
        print("ORO Payin Test Configuration")
        print("=" * 80)
        print(f"Base URL: {self.base_url}")
        print(f"Client ID: {self.client_id[:5]}...")
        print(f"Secret ID: {self.secret_id[:5]}...")
        print("=" * 80)
    
    def get_headers(self):
        """Get request headers for ORO API"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Client-Id': self.client_id,
            'X-Secret-Id': self.secret_id
        }
        return headers
    
    def test_create_payment_order(self, amount=10.00, test_name="Test ORO"):
        """
        Test creating a payment order
        
        Args:
            amount: Payment amount (default: 10.00)
            test_name: Test identifier for customer name
        
        Returns:
            dict: Response from ORO API
        """
        print("\n" + "=" * 80)
        print("TEST: Create Payment Order")
        print("=" * 80)
        
        # Generate unique merchant order ID
        merchant_order_id = f"TEST_ORO_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Prepare test customer data
        customer_name = f"{test_name} User"
        customer_mobile = "9876523450"
        
        # Prepare payload
        payload = {
            'name': customer_name,
            'amount': amount,
            'mobile_number': customer_mobile,
            'order_id': merchant_order_id,
            'redirect_url': "https://orchpay.in/payment/success"
        }
        
        print(f"\n[Request Details]")
        print(f"Endpoint: {self.base_url}/payin/data")
        print(f"Merchant Order ID: {merchant_order_id}")
        print(f"Amount: ₹{amount}")
        print(f"Customer: {customer_name} ({customer_mobile})")
        print(f"\n[Request Payload]")
        print(json.dumps(payload, indent=2))
        
        # Create payment order
        url = f"{self.base_url}/payin/data"
        
        try:
            print(f"\n[Sending Request]")
            start_time = time.time()
            
            response = requests.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=(10, 60)
            )
            
            elapsed_time = time.time() - start_time
            
            print(f"\n[Response Received]")
            print(f"Status Code: {response.status_code}")
            print(f"Response Time: {elapsed_time:.2f}s")
            print(f"Response Headers: {dict(response.headers)}")
            print(f"\n[Response Body]")
            print(response.text)
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                
                is_success = response_data.get('status') is True or str(response_data.get('status')).lower() in ['true', 'success', '1']
                if not is_success and 'body' in response_data and 'resultInfo' in response_data['body']:
                    if response_data['body']['resultInfo'].get('resultStatus') == 'SUCCESS':
                        is_success = True
                
                if is_success:
                    print(f"\n✅ SUCCESS: Payment order created")
                    
                    # Extract payment URL or QR Data
                    upi_link = ""
                    if 'body' in response_data and 'qrData' in response_data['body']:
                        upi_link = response_data['body']['qrData']
                    elif 'payment_url' in response_data:
                        upi_link = response_data['payment_url']
                    
                    print(f"Payment Link / QR Data: {upi_link[:100]}...")
                    
                    return {
                        'success': True,
                        'merchant_order_id': merchant_order_id,
                        'response': response_data,
                        'elapsed_time': elapsed_time
                    }
                else:
                    print(f"\n❌ FAILED: {response_data.get('message', 'Unknown error')}")
                    return {
                        'success': False,
                        'merchant_order_id': merchant_order_id,
                        'error': response_data.get('message', 'Unknown error')
                    }
            else:
                print(f"\n❌ HTTP ERROR: {response.status_code}")
                return {
                    'success': False,
                    'merchant_order_id': merchant_order_id,
                    'error': f'HTTP {response.status_code}: {response.text}'
                }
        
        except requests.exceptions.Timeout as e:
            elapsed_time = time.time() - start_time
            print(f"\n⚠️ TIMEOUT after {elapsed_time:.2f}s")
            return {
                'success': False,
                'merchant_order_id': merchant_order_id,
                'error': 'TIMEOUT',
                'elapsed_time': elapsed_time
            }
        
        except Exception as e:
            print(f"\n❌ EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'success': False,
                'merchant_order_id': merchant_order_id,
                'error': str(e)
            }

def main():
    """Main test function"""
    print("\n" + "=" * 80)
    print("ORO PAYIN TEST SCRIPT")
    print("=" * 80)
    print("This script tests the ORO payin integration directly against the ORO API")
    print("=" * 80)
    
    try:
        tester = OroPayinTester()
        
        amount = input("\nEnter amount to test (default 10.00): ").strip()
        amount = float(amount) if amount else 10.00
        
        tester.test_create_payment_order(amount=amount)
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")

if __name__ == '__main__':
    main()
