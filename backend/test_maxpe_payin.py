"""
Test script for MaxPe Payin Integration
Tests the complete payin flow including order creation and status checking
"""

import requests
import json
import time
import hmac
import hashlib
import uuid
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MaxpePayinTester:
    def __init__(self):
        self.base_url = os.getenv('MAXPE_BASE_URL', 'https://merchant.maxpe.tech')
        self.api_key = os.getenv('MAXPE_API_KEY')
        self.api_secret = os.getenv('MAXPE_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ValueError("MAXPE_API_KEY and MAXPE_API_SECRET must be set in .env file")
        
        print("=" * 80)
        print("MaxPe Payin Test Configuration")
        print("=" * 80)
        print(f"Base URL: {self.base_url}")
        print(f"API Key: {self.api_key[:20]}...")
        print(f"API Secret: {self.api_secret[:20]}...")
        print("=" * 80)
    
    def generate_signature(self, data_to_sign):
        """
        Generate HMAC SHA256 signature for MaxPe API
        
        Args:
            data_to_sign: Dictionary containing fields to sign
        
        Returns:
            str: HMAC SHA256 signature
        """
        # Sort keys alphabetically
        sorted_keys = sorted(data_to_sign.keys())
        
        # Build canonical string: key=value&key=value
        canonical_parts = []
        for key in sorted_keys:
            value = str(data_to_sign[key])
            canonical_parts.append(f"{key}={value}")
        
        canonical_string = "&".join(canonical_parts)
        
        print(f"\n[Signature Generation]")
        print(f"Canonical String: {canonical_string}")
        
        # Generate HMAC SHA256 signature
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            canonical_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        print(f"Generated Signature: {signature}")
        
        return signature
    
    def get_headers(self, timestamp, nonce, signature):
        """Get request headers for MaxPe API"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-API-KEY': self.api_key,
            'X-TIMESTAMP': str(timestamp),
            'X-NONCE': nonce,
            'X-SIGNATURE': signature
        }
        return headers
    
    def generate_nonce(self):
        """Generate unique nonce for request"""
        return uuid.uuid4().hex[:16]
    
    def test_create_payment_order(self, amount=100.00, test_name="Test Payment"):
        """
        Test creating a payment order
        
        Args:
            amount: Payment amount (default: 100.00)
            test_name: Test identifier for customer name
        
        Returns:
            dict: Response from MaxPe API
        """
        print("\n" + "=" * 80)
        print("TEST 1: Create Payment Order")
        print("=" * 80)
        
        # Generate unique merchant order ID
        merchant_order_id = f"TEST_MAXPE_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Generate timestamp and nonce
        timestamp = int(time.time())
        nonce = self.generate_nonce()
        
        # Prepare test customer data
        customer_name = f"{test_name} User"
        customer_mobile = "9876523450"
        customer_email = "tes23423t@gmail.com"
        
        # Prepare payload for signature
        data_to_sign = {
            'amount': str(amount),
            'email': customer_email,
            'mobile': customer_mobile,
            'name': customer_name,
            'nonce': nonce,
            'timestamp': str(timestamp),
            'merchant_order_id': merchant_order_id
        }
        
        # Generate signature
        signature = self.generate_signature(data_to_sign)
        
        # Prepare request payload (without nonce and timestamp - they go in headers)
        payload = {
            'name': customer_name,
            'mobile': customer_mobile,
            'email': customer_email,
            'amount': str(amount),
            'merchant_order_id': merchant_order_id
        }
        
        print(f"\n[Request Details]")
        print(f"Endpoint: {self.base_url}/api/prod/payin/create-payment")
        print(f"Merchant Order ID: {merchant_order_id}")
        print(f"Amount: ₹{amount}")
        print(f"Customer: {customer_name} ({customer_mobile})")
        print(f"Email: {customer_email}")
        print(f"Timestamp: {timestamp}")
        print(f"Nonce: {nonce}")
        print(f"\n[Request Payload]")
        print(json.dumps(payload, indent=2))
        
        # Create payment order
        url = f"{self.base_url}/api/prod/payin/create-payment"
        
        try:
            print(f"\n[Sending Request]")
            print(f"Timeout: 120 seconds (MaxPe API can be slow)")
            
            start_time = time.time()
            
            response = requests.post(
                url,
                headers=self.get_headers(timestamp, nonce, signature),
                json=payload,
                timeout=(15, 120)  # 15s to connect, 120s to read response
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
                
                if response_data.get('status'):
                    print(f"\n✅ SUCCESS: Payment order created")
                    print(f"UPI Deeplink: {response_data.get('upi_deeplink', 'N/A')[:100]}...")
                    
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
            print(f"This is common with MaxPe API - transaction may still be created")
            print(f"Use status check to verify: {merchant_order_id}")
            
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
    
    def test_check_payment_status(self, merchant_order_id):
        """
        Test checking payment status
        
        Args:
            merchant_order_id: The merchant order ID to check
        
        Returns:
            dict: Status information
        """
        print("\n" + "=" * 80)
        print("TEST 2: Check Payment Status")
        print("=" * 80)
        
        url = f"{self.base_url}/api/prod/payin1/status"
        
        # Status check uses form data and only requires X-API-KEY header
        headers = {
            'X-API-KEY': self.api_key
        }
        
        payload = {
            'merchant_order_id': merchant_order_id
        }
        
        print(f"\n[Request Details]")
        print(f"Endpoint: {url}")
        print(f"Merchant Order ID: {merchant_order_id}")
        print(f"\n[Request Payload]")
        print(json.dumps(payload, indent=2))
        
        try:
            print(f"\n[Sending Request]")
            
            start_time = time.time()
            
            response = requests.post(
                url,
                headers=headers,
                data=payload,  # Use form data, not JSON
                timeout=(10, 60)
            )
            
            elapsed_time = time.time() - start_time
            
            print(f"\n[Response Received]")
            print(f"Status Code: {response.status_code}")
            print(f"Response Time: {elapsed_time:.2f}s")
            print(f"\n[Response Body]")
            print(response.text)
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                
                if response_data.get('status'):
                    data = response_data.get('data', {})
                    transaction_status = data.get('transaction_status', 'PENDING').upper()
                    
                    print(f"\n✅ SUCCESS: Status retrieved")
                    print(f"Transaction Status: {transaction_status}")
                    print(f"Amount: ₹{data.get('amount', 'N/A')}")
                    print(f"UTR: {data.get('utr', 'N/A')}")
                    print(f"Created At: {data.get('created_at', 'N/A')}")
                    
                    return {
                        'success': True,
                        'status': transaction_status,
                        'data': data,
                        'elapsed_time': elapsed_time
                    }
                else:
                    print(f"\n❌ FAILED: {response_data.get('message', 'Unknown error')}")
                    return {
                        'success': False,
                        'error': response_data.get('message', 'Unknown error')
                    }
            else:
                print(f"\n❌ HTTP ERROR: {response.status_code}")
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text}'
                }
        
        except Exception as e:
            print(f"\n❌ EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def run_full_test(self, amount=100.00):
        """
        Run complete payin test flow
        1. Create payment order
        2. Wait for user to complete payment (or timeout)
        3. Check payment status
        
        Args:
            amount: Payment amount (default: 100.00)
        """
        print("\n" + "=" * 80)
        print("MAXPE PAYIN - FULL TEST FLOW")
        print("=" * 80)
        print(f"Test Amount: ₹{amount}")
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # Step 1: Create payment order
        create_result = self.test_create_payment_order(amount=amount)
        
        if not create_result.get('success'):
            print("\n" + "=" * 80)
            print("TEST FAILED: Could not create payment order")
            print("=" * 80)
            
            # If timeout, still try to check status
            if create_result.get('error') == 'TIMEOUT':
                merchant_order_id = create_result.get('merchant_order_id')
                print(f"\nAttempting status check for: {merchant_order_id}")
                
                # Wait a bit before checking
                print("\nWaiting 30 seconds before status check...")
                time.sleep(30)
                
                status_result = self.test_check_payment_status(merchant_order_id)
                
                print("\n" + "=" * 80)
                print("TEST SUMMARY (After Timeout)")
                print("=" * 80)
                print(f"Create Order: TIMEOUT")
                print(f"Status Check: {'SUCCESS' if status_result.get('success') else 'FAILED'}")
                if status_result.get('success'):
                    print(f"Payment Status: {status_result.get('status')}")
                print("=" * 80)
            
            return
        
        merchant_order_id = create_result.get('merchant_order_id')
        upi_link = create_result.get('response', {}).get('upi_deeplink', '')
        
        # Step 2: Display payment link and wait
        print("\n" + "=" * 80)
        print("PAYMENT LINK GENERATED")
        print("=" * 80)
        print(f"UPI Link: {upi_link}")
        print("\nOptions:")
        print("1. Open this link on your phone to complete payment")
        print("2. Wait for automatic status check (60 seconds)")
        print("3. Press Ctrl+C to skip waiting and check status now")
        print("=" * 80)
        
        try:
            print("\nWaiting 60 seconds before status check...")
            time.sleep(60)
        except KeyboardInterrupt:
            print("\n\nSkipping wait, checking status now...")
        
        # Step 3: Check payment status
        status_result = self.test_check_payment_status(merchant_order_id)
        
        # Step 4: Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Merchant Order ID: {merchant_order_id}")
        print(f"Create Order: {'SUCCESS' if create_result.get('success') else 'FAILED'}")
        print(f"Create Time: {create_result.get('elapsed_time', 0):.2f}s")
        print(f"Status Check: {'SUCCESS' if status_result.get('success') else 'FAILED'}")
        if status_result.get('success'):
            print(f"Payment Status: {status_result.get('status')}")
            print(f"Amount: ₹{status_result.get('data', {}).get('amount', 'N/A')}")
            print(f"UTR: {status_result.get('data', {}).get('utr', 'N/A')}")
        print("=" * 80)


def main():
    """Main test function"""
    print("\n" + "=" * 80)
    print("MAXPE PAYIN TEST SCRIPT")
    print("=" * 80)
    print("This script tests the MaxPe payin integration")
    print("=" * 80)
    
    try:
        tester = MaxpePayinTester()
        
        # Menu
        print("\nSelect test to run:")
        print("1. Create Payment Order Only")
        print("2. Check Payment Status Only")
        print("3. Full Test Flow (Create + Wait + Check)")
        print("4. Quick Test (Create + Immediate Status Check)")
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == '1':
            amount = input("Enter amount (default 100.00): ").strip()
            amount = float(amount) if amount else 100.00
            tester.test_create_payment_order(amount=amount)
        
        elif choice == '2':
            merchant_order_id = input("Enter merchant_order_id: ").strip()
            if not merchant_order_id:
                print("❌ merchant_order_id is required")
                return
            tester.test_check_payment_status(merchant_order_id)
        
        elif choice == '3':
            amount = input("Enter amount (default 100.00): ").strip()
            amount = float(amount) if amount else 100.00
            tester.run_full_test(amount=amount)
        
        elif choice == '4':
            amount = input("Enter amount (default 100.00): ").strip()
            amount = float(amount) if amount else 100.00
            
            # Create order
            create_result = tester.test_create_payment_order(amount=amount)
            
            if create_result.get('success') or create_result.get('error') == 'TIMEOUT':
                merchant_order_id = create_result.get('merchant_order_id')
                
                # Wait 10 seconds
                print("\nWaiting 10 seconds before status check...")
                time.sleep(10)
                
                # Check status
                tester.test_check_payment_status(merchant_order_id)
        
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
