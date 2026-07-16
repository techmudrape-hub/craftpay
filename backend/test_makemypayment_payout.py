import os
import uuid
from makemypayment_payout_service import makemypayment_payout_service
from config import Config
from dotenv import load_dotenv

# Load environment variables just in case
load_dotenv()

def test_makemypayment():
    print("="*50)
    print("MakeMyPayment Payout Service Test")
    print("="*50)

    # Check configuration
    print("\n--- Configuration ---")
    print(f"Base URL: {Config.MAKEMYPAYMENT_BASE_URL}")
    print(f"API Key configured: {bool(Config.MAKEMYPAYMENT_API_KEY)}")
    print(f"API Secret configured: {bool(Config.MAKEMYPAYMENT_API_SECRET)}")
    
    if not Config.MAKEMYPAYMENT_API_KEY or not Config.MAKEMYPAYMENT_API_SECRET:
        print("\n[WARNING] API Key or Secret is missing. The requests will likely fail.")
        print("Please ensure they are added to your .env file.")

    # 1. Test Balance Check
    print("\n--- 1. Testing get_balance() ---")
    balance_result = makemypayment_payout_service.get_balance()
    print(f"Result: {balance_result}")

    # To fully test the single payout, uncomment the following block and provide real bank details
    print("\n--- 2. Testing initiate_single_payout() ---")
    test_ref_id = f"TEST_MMP_{uuid.uuid4().hex[:8].upper()}"
    
    payout_result = makemypayment_payout_service.initiate_single_payout(
        merchant_reference_id=test_ref_id,
        account_holder="Test User",
        account_number="98673719234", # REPLACE WITH REAL ACCOUNT FOR TESTING
        ifsc_code="SBIN0000001",       # REPLACE WITH REAL IFSC FOR TESTING
        bank_name="State Bank of India",
        mobile="9993829912",
        amount="1000.00",
        mode="imps",
        purpose="Testing",
        email="test@example.com"
    )
    print(f"Payout Result: {payout_result}")

    if payout_result.get('success'):
        print("\n--- 3. Testing check_payout_status() ---")
        status_result = makemypayment_payout_service.check_payout_status(merchant_reference_id=test_ref_id)
        print(f"Status Result: {status_result}")
    print("="*50)

if __name__ == "__main__":
    test_makemypayment()
