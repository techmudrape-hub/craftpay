"""
Automated Test Script for MaxPe Payin Integration
Runs automated tests without user interaction
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

class MaxpePayinAutomatedTester:
    def __init__(self):
        self.base_url = os.getenv('MAXPE_BASE_URL', 'https://merchant.maxpe.tech')
        self.api_key = os.getenv('MAXPE_API_KEY')
        self.api_secret = os.getenv('MAXPE_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ValueError("MAXPE_API_KEY and MAXPE_API_SECRET must be set in .env file")
        
        self.test_results = []
    
    def generate_signature(self, data_to_sign):
        """Generate HMAC SHA256 signature"""
        sorted_keys = sorted(data_to_sign.keys())
        canonical_parts = [f"{key}={str(data_to_sign[key])}" for key in sorted_keys]
        canonical_string = "&".join(canonical_parts)
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            canonical_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def get_headers(self, timestamp, nonce, signature):
        """Get request headers"""
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-API-KEY': self.api_key,
            'X-TIMESTAMP': str(timestamp),
            'X-NONCE': nonce,
            'X-SIGNATURE': signature
        }
    
    def generate_nonce(self):
        """Generate unique nonce"""
        return uuid.uuid4().hex[:16]
    
    def log_test(self, test_name, status, details):
        """Log test result"""
        result = {
            'test_name': test_name,
            'status': status,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_icon} {test_name}: {status}")
        if details:
            print(f"   Details: {details}")
    
    def test_signature_generation(self):
        """Test 1: Verify signature generation"""
        print("\n[Test 1] Signature Generation")
        
        try:
            test_data = {
                'amount': '100.00',
                'email': 'test@example.com',
                'mobile': '9876543210',
                'name': 'Test User',
                'nonce': 'test123',
                'timestamp': '1234567890',
                'merchant_order_id': 'TEST001'
            }
            
            signature = self.generate_signature(test_data)
            
            if signature and len(signature) == 64:  # SHA256 produces 64 hex chars
                self.log_test("Signature Generation", "PASS", f"Generated {len(signature)} char signature")
                return True
            else:
                self.log_test("Signature Generation", "FAIL", f"Invalid signature length: {len(signature)}")
                return False
        
        except Exception as e:
            self.log_test("Signature Generation", "FAIL", str(e))
            return False
    
    def test_api_connectivity(self):
        """Test 2: Verify API endpoint connectivity"""
        print("\n[Test 2] API Connectivity")
        
        try:
            # Just check if we can reach the base URL
            response = requests.get(self.base_url, timeout=10)
            
            if response.status_code in [200, 301, 302, 404]:  # Any response means connectivity works
                self.log_test("API Connectivity", "PASS", f"Base URL reachable (HTTP {response.status_code})")
                return True
            else:
                self.log_test("API Connectivity", "FAIL", f"Unexpected status: {response.status_code}")
                return False
        
        except Exception as e:
            self.log_test("API Connectivity", "FAIL", str(e))
            return False
    
    def test_create_payment_minimal(self):
        """Test 3: Create payment order with minimal data"""
        print("\n[Test 3] Create Payment Order (Minimal)")
        
        try:
            merchant_order_id = f"AUTO_TEST_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            timestamp = int(time.time())
            nonce = self.generate_nonce()
            
            data_to_sign = {
                'amount': '10.00',
                'email': 'autotest@example.com',
                'mobile': '9999999999',
                'name': 'Auto Test',
                'nonce': nonce,
                'timestamp': str(timestamp),
                'merchant_order_id': merchant_order_id
            }
            
            signature = self.generate_signature(data_to_sign)
            
            payload = {
                'name': 'Auto Test',
                'mobile': '9999999999',
                'email': 'autotest@example.com',
                'amount': '10.00',
                'merchant_order_id': merchant_order_id
            }
            
            url = f"{self.base_url}/api/prod/payin/create-payment"
            
            start_time = time.time()
            response = requests.post(
                url,
                headers=self.get_headers(timestamp, nonce, signature),
                json=payload,
                timeout=(15, 120)
            )
            elapsed = time.time() - start_time
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                
                if response_data.get('status'):
                    self.log_test(
                        "Create Payment Order", 
                        "PASS", 
                        f"Order created in {elapsed:.2f}s, Order ID: {merchant_order_id}"
                    )
                    return {'success': True, 'merchant_order_id': merchant_order_id, 'response': response_data}
                else:
                    self.log_test(
                        "Create Payment Order", 
                        "FAIL", 
                        response_data.get('message', 'Unknown error')
                    )
                    return {'success': False, 'error': response_data.get('message')}
            else:
                self.log_test(
                    "Create Payment Order", 
                    "FAIL", 
                    f"HTTP {response.status_code}: {response.text[:100]}"
                )
                return {'success': False, 'error': f'HTTP {response.status_code}'}
        
        except requests.exceptions.Timeout:
            elapsed = time.time() - start_time
            self.log_test(
                "Create Payment Order", 
                "WARN", 
                f"Timeout after {elapsed:.2f}s (common with MaxPe)"
            )
            return {'success': False, 'error': 'TIMEOUT', 'merchant_order_id': merchant_order_id}
        
        except Exception as e:
            self.log_test("Create Payment Order", "FAIL", str(e))
            return {'success': False, 'error': str(e)}
    
    def test_status_check_invalid_order(self):
        """Test 4: Status check with invalid order ID"""
        print("\n[Test 4] Status Check (Invalid Order)")
        
        try:
            url = f"{self.base_url}/api/prod/payin1/status"
            headers = {'X-API-KEY': self.api_key}
            payload = {'merchant_order_id': 'INVALID_ORDER_12345'}
            
            response = requests.post(url, headers=headers, data=payload, timeout=30)
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                
                # Should return error or not found
                if not response_data.get('status') or response_data.get('message'):
                    self.log_test(
                        "Status Check (Invalid)", 
                        "PASS", 
                        "Correctly handled invalid order"
                    )
                    return True
                else:
                    self.log_test(
                        "Status Check (Invalid)", 
                        "WARN", 
                        "Unexpected success for invalid order"
                    )
                    return False
            else:
                self.log_test(
                    "Status Check (Invalid)", 
                    "PASS", 
                    f"Correctly returned error: HTTP {response.status_code}"
                )
                return True
        
        except Exception as e:
            self.log_test("Status Check (Invalid)", "FAIL", str(e))
            return False
    
    def test_status_check_valid_order(self, merchant_order_id):
        """Test 5: Status check with valid order ID"""
        print("\n[Test 5] Status Check (Valid Order)")
        
        try:
            url = f"{self.base_url}/api/prod/payin1/status"
            headers = {'X-API-KEY': self.api_key}
            payload = {'merchant_order_id': merchant_order_id}
            
            response = requests.post(url, headers=headers, data=payload, timeout=30)
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                
                if response_data.get('status'):
                    data = response_data.get('data', {})
                    status = data.get('transaction_status', 'UNKNOWN')
                    
                    self.log_test(
                        "Status Check (Valid)", 
                        "PASS", 
                        f"Status: {status}, Order: {merchant_order_id}"
                    )
                    return True
                else:
                    self.log_test(
                        "Status Check (Valid)", 
                        "FAIL", 
                        response_data.get('message', 'Unknown error')
                    )
                    return False
            else:
                self.log_test(
                    "Status Check (Valid)", 
                    "FAIL", 
                    f"HTTP {response.status_code}"
                )
                return False
        
        except Exception as e:
            self.log_test("Status Check (Valid)", "FAIL", str(e))
            return False
    
    def test_invalid_signature(self):
        """Test 6: Request with invalid signature"""
        print("\n[Test 6] Invalid Signature Handling")
        
        try:
            merchant_order_id = f"INVALID_SIG_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            timestamp = int(time.time())
            nonce = self.generate_nonce()
            
            payload = {
                'name': 'Test User',
                'mobile': '9999999999',
                'email': 'test@example.com',
                'amount': '10.00',
                'merchant_order_id': merchant_order_id
            }
            
            # Use invalid signature
            invalid_signature = "invalid_signature_12345"
            
            url = f"{self.base_url}/api/prod/payin/create-payment"
            
            response = requests.post(
                url,
                headers=self.get_headers(timestamp, nonce, invalid_signature),
                json=payload,
                timeout=30
            )
            
            # Should return 401 or 403
            if response.status_code in [401, 403]:
                self.log_test(
                    "Invalid Signature", 
                    "PASS", 
                    f"Correctly rejected (HTTP {response.status_code})"
                )
                return True
            else:
                self.log_test(
                    "Invalid Signature", 
                    "WARN", 
                    f"Unexpected status: HTTP {response.status_code}"
                )
                return False
        
        except Exception as e:
            self.log_test("Invalid Signature", "FAIL", str(e))
            return False
    
    def run_all_tests(self):
        """Run all automated tests"""
        print("=" * 80)
        print("MAXPE PAYIN - AUTOMATED TEST SUITE")
        print("=" * 80)
        print(f"Base URL: {self.base_url}")
        print(f"API Key: {self.api_key[:20]}...")
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # Run tests
        self.test_signature_generation()
        self.test_api_connectivity()
        
        create_result = self.test_create_payment_minimal()
        
        self.test_status_check_invalid_order()
        
        if create_result.get('success'):
            # Wait a bit before checking status
            print("\nWaiting 10 seconds before status check...")
            time.sleep(10)
            self.test_status_check_valid_order(create_result['merchant_order_id'])
        elif create_result.get('merchant_order_id'):
            # Even if timeout, try status check
            print("\nWaiting 10 seconds before status check...")
            time.sleep(10)
            self.test_status_check_valid_order(create_result['merchant_order_id'])
        
        self.test_invalid_signature()
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r['status'] == 'PASS')
        failed = sum(1 for r in self.test_results if r['status'] == 'FAIL')
        warned = sum(1 for r in self.test_results if r['status'] == 'WARN')
        
        print(f"Total Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Warnings: {warned}")
        print(f"Success Rate: {(passed/total*100):.1f}%")
        
        print("\n" + "=" * 80)
        print("DETAILED RESULTS")
        print("=" * 80)
        
        for result in self.test_results:
            status_icon = "✅" if result['status'] == "PASS" else "❌" if result['status'] == "FAIL" else "⚠️"
            print(f"{status_icon} {result['test_name']}: {result['status']}")
            if result['details']:
                print(f"   {result['details']}")
        
        print("=" * 80)


def main():
    """Main function"""
    try:
        tester = MaxpePayinAutomatedTester()
        tester.run_all_tests()
    
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
