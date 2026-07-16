"""
RockyPayz Payout Direct Test Script
Tests the RockyPayz payout integration directly without going through the full API
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rockypayz_payout_service import rockypayz_payout_service
from config import Config
import json
from datetime import datetime
import time

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_config():
    """Print current RockyPayz configuration"""
    print_section("ROCKYPAYZ CONFIGURATION")
    print(f"Base URL: {Config.ROCKYPAYZ_BASE_URL}")
    print(f"MID: {Config.ROCKYPAYZ_MID}")
    print(f"API Key: {Config.ROCKYPAYZ_API_KEY[:10]}..." if Config.ROCKYPAYZ_API_KEY else "API Key: NOT SET")
    print(f"Route: {Config.ROCKYPAYZ_ROUTE}")
    
    # Check if credentials are set
    if not Config.ROCKYPAYZ_MID or not Config.ROCKYPAYZ_API_KEY:
        print("\n⚠️  WARNING: RockyPayz credentials are not configured!")
        print("Please add the following to your .env file:")
        print("\nROCKYPAYZ_MID=YOUR_MERCHANT_ID")
        print("ROCKYPAYZ_API_KEY=YOUR_API_KEY")
        print("ROCKYPAYZ_ROUTE=1")
        return False
    
    return True

def test_payout_initiation():
    """Test payout initiation"""
    print_section("TEST 1: PAYOUT INITIATION")
    
    # Generate unique reference ID
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    reference_id = f"RCK_TXN_TEST_{timestamp}"
    
    print(f"Reference ID: {reference_id}")
    print(f"Testing payout initiation...")
    
    # Test data
    test_data = {
        'account_number': '3301127000001',  # Test account number
        'ifsc_code': 'SBIN0000001',
        'bank_name': 'STATE BANK OF INDIA',
        'merchant_order_id': reference_id,
        'amount': 100,  # Test with ₹100
        'payee_name': 'Test Customer',
        'mobile': '9876543210',
        'remarks': 'Test Payout'
    }
    
    print("\nTest Data:")
    print(json.dumps(test_data, indent=2))
    
    print("\nCalling RockyPayz API...")
    
    try:
        result = rockypayz_payout_service.call_payout_api(
            account_number=test_data['account_number'],
            ifsc_code=test_data['ifsc_code'],
            bank_name=test_data['bank_name'],
            merchant_order_id=test_data['merchant_order_id'],
            amount=test_data['amount'],
            payee_name=test_data['payee_name'],
            mobile=test_data['mobile'],
            remarks=test_data['remarks']
        )
        
        print("\n" + "-" * 80)
        print("RESULT:")
        print("-" * 80)
        print(json.dumps(result, indent=2, default=str))
        
        if result.get('success'):
            print("\n✅ SUCCESS: Payout initiated successfully!")
            print(f"Status: {result.get('status')}")
            print(f"TXN ID: {result.get('txn_id')}")
            print(f"Amount: ₹{result.get('amount')}")
            print(f"Fees: ₹{result.get('fees')}")
            print(f"UTR: {result.get('utr')}")
            return reference_id, result
        else:
            print(f"\n❌ FAILED: {result.get('message')}")
            return None, result
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None

def test_status_check(merchant_order_id):
    """Test status check"""
    print_section("TEST 2: STATUS CHECK")
    
    print(f"Merchant Order ID: {merchant_order_id}")
    print(f"Checking payout status...")
    
    try:
        result = rockypayz_payout_service.check_payout_status(merchant_order_id)
        
        print("\n" + "-" * 80)
        print("RESULT:")
        print("-" * 80)
        print(json.dumps(result, indent=2, default=str))
        
        if result.get('success'):
            print("\n✅ SUCCESS: Status retrieved successfully!")
            print(f"Status: {result.get('status')}")
            print(f"TXN ID: {result.get('txn_id')}")
            print(f"Amount: ₹{result.get('amount')}")
            print(f"UTR: {result.get('utr')}")
            print(f"TXN Time: {result.get('txn_time')}")
            return result
        else:
            print(f"\n❌ FAILED: {result.get('message')}")
            return result
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_callback_simulation(reference_id):
    """Simulate a callback from RockyPayz"""
    print_section("TEST 3: CALLBACK SIMULATION")
    
    print(f"Simulating callback for: {reference_id}")
    
    # Simulate callback data
    callback_data = {
        "statuscode": "TXN",
        "msg": "Payout completed",
        "data": {
            "TXN_Time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "TXN_ID": reference_id,
            "Amount": 100,
            "Fees": 10.62,
            "UTR": "TEST" + str(int(time.time())),
            "status": "success"
        }
    }
    
    print("\nCallback Data:")
    print(json.dumps(callback_data, indent=2))
    
    print("\n📝 To test callback, send this data to:")
    print(f"POST http://localhost:5000/api/callback/rockypayz/payout")
    print("\nOr use curl:")
    print(f"\ncurl -X POST http://localhost:5000/api/callback/rockypayz/payout \\")
    print(f"  -H 'Content-Type: application/json' \\")
    print(f"  -d '{json.dumps(callback_data)}'")
    
    return callback_data

def run_full_test():
    """Run complete test suite"""
    print_section("ROCKYPAYZ PAYOUT TEST SUITE")
    print("This script will test the RockyPayz payout integration")
    print("Make sure you have configured your .env file with RockyPayz credentials")
    
    # Check configuration
    if not print_config():
        return
    
    # Ask for confirmation
    print("\n" + "=" * 80)
    print("⚠️  WARNING: This will make a REAL API call to RockyPayz!")
    print("Make sure you are using TEST credentials if available.")
    print("=" * 80)
    
    response = input("\nDo you want to proceed? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("\n❌ Test cancelled by user")
        return
    
    # Test 1: Payout Initiation
    reference_id, payout_result = test_payout_initiation()
    
    if not reference_id:
        print("\n❌ Payout initiation failed. Stopping tests.")
        return
    
    # Wait a bit before status check
    print("\n⏳ Waiting 3 seconds before status check...")
    time.sleep(3)
    
    # Test 2: Status Check
    status_result = test_status_check(reference_id)
    
    # Test 3: Callback Simulation
    callback_data = test_callback_simulation(reference_id)
    
    # Summary
    print_section("TEST SUMMARY")
    print(f"✅ Test 1: Payout Initiation - {'PASSED' if payout_result and payout_result.get('success') else 'FAILED'}")
    print(f"✅ Test 2: Status Check - {'PASSED' if status_result and status_result.get('success') else 'FAILED'}")
    print(f"📝 Test 3: Callback Simulation - Manual test required")
    
    print("\n" + "=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print("1. Check the RockyPayz dashboard for transaction status")
    print("2. Test the callback endpoint using the curl command above")
    print("3. Verify transaction is stored in payout_transactions table")
    print("4. Check callback logs in callback_logs table")
    print("\nDatabase Queries:")
    print(f"\n-- Check transaction")
    print(f"SELECT * FROM payout_transactions WHERE reference_id = '{reference_id}';")
    print(f"\n-- Check callback logs")
    print(f"SELECT * FROM callback_logs WHERE txn_id IN (SELECT txn_id FROM payout_transactions WHERE reference_id = '{reference_id}');")

def test_with_custom_data():
    """Test with custom data provided by user"""
    print_section("CUSTOM DATA TEST")
    
    print("Enter test data (press Enter to use defaults):")
    
    account_number = input("Account Number [3301127000001]: ").strip() or "3301127000001"
    ifsc_code = input("IFSC Code [SBIN0000001]: ").strip() or "SBIN0000001"
    bank_name = input("Bank Name [STATE BANK OF INDIA]: ").strip() or "STATE BANK OF INDIA"
    amount = input("Amount [100]: ").strip() or "100"
    payee_name = input("Payee Name [Test Customer]: ").strip() or "Test Customer"
    mobile = input("Mobile [9876543210]: ").strip() or "9876543210"
    remarks = input("Remarks [Test Payout]: ").strip() or "Test Payout"
    
    # Generate reference ID
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    reference_id = f"RCK_TXN_CUSTOM_{timestamp}"
    
    print(f"\nGenerated Reference ID: {reference_id}")
    print("\nCalling RockyPayz API...")
    
    try:
        result = rockypayz_payout_service.call_payout_api(
            account_number=account_number,
            ifsc_code=ifsc_code,
            bank_name=bank_name,
            merchant_order_id=reference_id,
            amount=float(amount),
            payee_name=payee_name,
            mobile=mobile,
            remarks=remarks
        )
        
        print("\n" + "-" * 80)
        print("RESULT:")
        print("-" * 80)
        print(json.dumps(result, indent=2, default=str))
        
        if result.get('success'):
            print("\n✅ SUCCESS!")
            return reference_id
        else:
            print(f"\n❌ FAILED: {result.get('message')}")
            return None
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main function"""
    print("\n" + "=" * 80)
    print("  ROCKYPAYZ PAYOUT TEST SCRIPT")
    print("=" * 80)
    print("\nSelect test mode:")
    print("1. Full automated test (recommended)")
    print("2. Custom data test")
    print("3. Status check only")
    print("4. Show configuration")
    print("5. Exit")
    
    choice = input("\nEnter your choice (1-5): ").strip()
    
    if choice == '1':
        run_full_test()
    elif choice == '2':
        if print_config():
            test_with_custom_data()
    elif choice == '3':
        if print_config():
            merchant_order_id = input("\nEnter Merchant Order ID (reference_id): ").strip()
            if merchant_order_id:
                test_status_check(merchant_order_id)
            else:
                print("❌ Merchant Order ID is required")
    elif choice == '4':
        print_config()
    elif choice == '5':
        print("\n👋 Goodbye!")
        return
    else:
        print("\n❌ Invalid choice")
        return
    
    print("\n" + "=" * 80)
    print("Test completed!")
    print("=" * 80)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
