"""
Test Cinoright Payout Service
Diagnose and test Cinoright IMPS payout API
"""

import sys
import json
import time
from cinoright_service import cinoright_service
from config import Config

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def test_cinoright_credentials():
    """Test if Cinoright credentials are configured"""
    print_section("STEP 1: Checking Cinoright Credentials")
    
    print(f"Base URL: {Config.CINORIGHT_BASE_URL}")
    print(f"API Key: {Config.CINORIGHT_API_KEY[:20]}..." if Config.CINORIGHT_API_KEY else "API Key: NOT SET")
    print(f"Secret Key: {Config.CINORIGHT_SECRET_KEY[:20]}..." if Config.CINORIGHT_SECRET_KEY else "Secret Key: NOT SET")
    print(f"User ID: {Config.CINORIGHT_USER_ID}")
    
    if not Config.CINORIGHT_API_KEY or not Config.CINORIGHT_SECRET_KEY or not Config.CINORIGHT_USER_ID:
        print("\n❌ ERROR: Cinoright credentials are not properly configured in .env file")
        return False
    
    print("\n✓ All credentials are configured")
    return True

def test_cinoright_headers():
    """Test if headers are properly formatted"""
    print_section("STEP 2: Testing Request Headers")
    
    headers = cinoright_service.get_headers()
    
    print("Headers that will be sent to Cinoright:")
    for key, value in headers.items():
        if key in ['ApiKey', 'SecretKey']:
            print(f"  {key}: {value[:20]}...")
        else:
            print(f"  {key}: {value}")
    
    required_headers = ['ApiKey', 'SecretKey', 'UserId', 'Content-Type']
    missing_headers = [h for h in required_headers if h not in headers]
    
    if missing_headers:
        print(f"\n❌ ERROR: Missing required headers: {missing_headers}")
        return False
    
    print("\n✓ All required headers are present")
    return True

def test_cinoright_payout_api():
    """Test actual Cinoright payout API call"""
    print_section("STEP 3: Testing Cinoright Payout API")
    
    # Test data
    test_data = {
        'account_number': '50100496014066',
        'ifsc_code': 'HDFC0009117',
        'reference_id': f'TEST{int(time.time())}',
        'amount': 100,  # Minimum amount as per Cinoright requirement
        'beneficiary_name': 'TEST USER',
        'email': 'test@example.com',
        'phone': '9999999999'
    }
    
    print("Test Payout Data:")
    print(json.dumps(test_data, indent=2))
    
    print("\nCalling Cinoright API...")
    
    result = cinoright_service.call_imps_payout_api(
        account_number=test_data['account_number'],
        ifsc_code=test_data['ifsc_code'],
        reference_id=test_data['reference_id'],
        amount=test_data['amount'],
        beneficiary_name=test_data['beneficiary_name'],
        email=test_data['email'],
        phone=test_data['phone']
    )
    
    print("\n" + "-" * 80)
    print("API Response:")
    print("-" * 80)
    print(json.dumps(result, indent=2))
    print("-" * 80)
    
    if result.get('success'):
        print("\n✓ API call successful")
        print(f"Status: {result.get('status')}")
        print(f"Transaction ID: {result.get('cinoright_txn_id')}")
        print(f"Message: {result.get('message')}")
        
        if result.get('status') == 'FAILED':
            print("\n⚠ WARNING: Payout was initiated but status is FAILED")
            print("This could mean:")
            print("  1. Insufficient balance in Cinoright account")
            print("  2. Invalid bank details")
            print("  3. IP not whitelisted")
            print("  4. Account/API restrictions")
        
        return True
    else:
        print("\n❌ API call failed")
        print(f"Error: {result.get('message')}")
        return False

def test_cinoright_status_check():
    """Test Cinoright status check API"""
    print_section("STEP 4: Testing Status Check API")
    
    print("To test status check, we need a transaction ID from a previous payout.")
    txn_id = input("Enter Cinoright transaction ID (or press Enter to skip): ").strip()
    
    if not txn_id:
        print("⊘ Skipping status check test")
        return True
    
    print(f"\nChecking status for transaction: {txn_id}")
    
    result = cinoright_service.check_payout_status(txn_id)
    
    print("\n" + "-" * 80)
    print("Status Check Response:")
    print("-" * 80)
    print(json.dumps(result, indent=2))
    print("-" * 80)
    
    if result.get('success'):
        print("\n✓ Status check successful")
        print(f"Status: {result.get('status')}")
        print(f"UTR: {result.get('utr')}")
        return True
    else:
        print("\n❌ Status check failed")
        print(f"Error: {result.get('message')}")
        return False

def diagnose_failed_payout():
    """Diagnose why payout might be failing"""
    print_section("STEP 5: Diagnosing Common Issues")
    
    print("\nCommon reasons for Cinoright payout failures:")
    print("\n1. ❌ Insufficient Balance")
    print("   - Check your Cinoright account balance")
    print("   - Ensure you have enough funds for the payout amount")
    
    print("\n2. ❌ IP Not Whitelisted")
    print("   - Your server IP must be whitelisted in Cinoright system")
    print("   - Contact Cinoright support to whitelist your IP")
    
    print("\n3. ❌ Invalid Bank Details")
    print("   - IFSC code must be in format: AAAA0XXXXXX (e.g., HDFC0009117)")
    print("   - Account number must be valid")
    print("   - Beneficiary name should match bank records")
    
    print("\n4. ❌ API Credentials")
    print("   - Verify API Key, Secret Key, and User ID are correct")
    print("   - Check if credentials are for production or test environment")
    
    print("\n5. ❌ Minimum Amount")
    print("   - Cinoright requires minimum ₹100 per transaction")
    
    print("\n6. ❌ Account Status")
    print("   - Check if your Cinoright account is active")
    print("   - Verify if there are any restrictions on your account")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS:")
    print("=" * 80)
    print("1. Contact Cinoright support with the transaction details")
    print("2. Ask them to check:")
    print("   - Account balance")
    print("   - IP whitelist status")
    print("   - Any API restrictions")
    print("   - Transaction logs on their end")
    print("3. Provide them with:")
    print("   - Your User ID: " + Config.CINORIGHT_USER_ID)
    print("   - Reference ID from failed transaction")
    print("   - Timestamp of the transaction")

def main():
    """Main test function"""
    print("\n" + "=" * 80)
    print("  CINORIGHT PAYOUT SERVICE TEST")
    print("=" * 80)
    print("\nThis script will test the Cinoright payout integration")
    print("and help diagnose any issues.")
    
    # Step 1: Check credentials
    if not test_cinoright_credentials():
        print("\n❌ Test failed at Step 1: Credentials check")
        return
    
    # Step 2: Check headers
    if not test_cinoright_headers():
        print("\n❌ Test failed at Step 2: Headers check")
        return
    
    # Step 3: Test payout API
    print("\n" + "=" * 80)
    response = input("Do you want to test the actual Cinoright API? (yes/no): ")
    if response.lower() in ['yes', 'y']:
        if not test_cinoright_payout_api():
            print("\n❌ Test failed at Step 3: API call")
            diagnose_failed_payout()
            return
    else:
        print("⊘ Skipping API test")
    
    # Step 4: Test status check
    test_cinoright_status_check()
    
    # Step 5: Diagnosis
    diagnose_failed_payout()
    
    print("\n" + "=" * 80)
    print("  TEST COMPLETED")
    print("=" * 80)
    print("\nIf payouts are still failing, please:")
    print("1. Check the detailed error messages above")
    print("2. Contact Cinoright support with transaction details")
    print("3. Verify your account balance and IP whitelist status")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⊘ Test interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
