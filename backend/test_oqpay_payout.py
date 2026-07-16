"""
Test script for OQPay Payout Integration
Tests payout creation and database recording
"""

import sys
import os
import time
from dotenv import load_dotenv

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oqpay_payout_service import oqpay_payout_service
from database import get_db_connection
import json

# Load env
load_dotenv()

def test_config():
    """Test ClocksPay/OQPay configuration"""
    print("=" * 80)
    print("TEST: OQPay Payout Configuration")
    print("=" * 80)
    
    from config import Config
    
    print(f"Payout Base URL: {Config.OQPAY_PAYOUT_BASE_URL}")
    print(f"Registration ID: {Config.OQPAY_REGISTRATION_ID}")
    
    if not Config.OQPAY_REGISTRATION_ID or Config.OQPAY_REGISTRATION_ID == "OQP-XXXX":
        print("\n⚠ WARNING: OQPAY_REGISTRATION_ID is not properly set in environment variables")
        print("Please check your .env file.")
        return False
    
    print("\n✅ Configuration looks good")
    return True

def test_database_connection():
    """Test database connection"""
    print("=" * 80)
    print("TEST: Database Connection")
    print("=" * 80)
    
    conn = get_db_connection()
    if conn:
        print("✅ Database connection successful")
        
        # Check if test merchant exists
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT merchant_id, full_name, email, scheme_id, is_active
                    FROM merchants
                    LIMIT 1
                """)
                merchant = cursor.fetchone()
                
                if merchant:
                    print(f"\nSample Merchant Found:")
                    print(f"  Merchant ID: {merchant['merchant_id']}")
                    print(f"  Name: {merchant['full_name']}")
                    print(f"  Email: {merchant['email']}")
                    print(f"  Scheme ID: {merchant['scheme_id']}")
                    print(f"  Active: {merchant['is_active']}")
                    return merchant['merchant_id']
                else:
                    print("\n⚠ No merchants found in database")
                    return None
        finally:
            conn.close()
    else:
        print("❌ Database connection failed")
        return None

def test_payout_transfer():
    """Test payout transfer call"""
    print("=" * 80)
    print("TEST: Call OQPay Payout API")
    print("=" * 80)
    
    # Mock beneficiary details
    account_number = "1234567890"
    ifsc_code = "UTIB0000001"
    bank_name = "AXIS BANK"
    merchant_order_id = f"TEST_OQP_PO_{int(time.time())}"
    amount = 100.00
    payee_name = "Alice Beneficiary"
    email = "alice.bene@gmail.com"
    mobile = "9876543210"
    
    print(f"\nBeneficiary Payout Details:")
    print(f"  Account Number: {account_number}")
    print(f"  IFSC: {ifsc_code}")
    print(f"  Bank: {bank_name}")
    print(f"  Order ID: {merchant_order_id}")
    print(f"  Amount: ₹{amount}")
    print(f"  Name: {payee_name}")
    
    # Send payout request
    result = oqpay_payout_service.call_payout_api(
        account_number=account_number,
        ifsc_code=ifsc_code,
        bank_name=bank_name,
        merchant_order_id=merchant_order_id,
        amount=amount,
        payee_name=payee_name,
        email=email,
        mobile=mobile,
        mode='IMPS'
    )
    
    print(f"\nResult:")
    print(json.dumps(result, indent=2, default=str))
    
    if result.get('success'):
        print("\n✅ Payout initiated successfully!")
        print(f"OQPay Transaction ID: {result.get('pg_txn_id')}")
        print(f"Status: {result.get('status')}")
        print(f"UTR: {result.get('utr')}")
    else:
        print(f"\n❌ Payout request failed: {result.get('message')}")

if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("OQPay Payout Integration Test Suite")
    print("=" * 80 + "\n")
    
    # Test 1: Configuration
    config_ok = test_config()
    print("\n")
    
    # Test 2: Database Connection
    merchant_id = test_database_connection()
    print("\n")
    
    # Test 3: Call payout (optional, user input required)
    if merchant_id:
        print("Do you want to test payout API call? (y/n): ", end='')
        response = input().strip().lower() if sys.stdin.isatty() else 'n'
        
        if response == 'y':
            test_payout_transfer()
            
    print("\n" + "=" * 80)
    print("Test Suite Complete")
    print("=" * 80)
