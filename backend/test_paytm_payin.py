"""
Test script for Paytm PayIn integration
Tests payment link creation and callback handling
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from paytm_service import paytm_service
import json

def test_create_payment_link():
    """Test creating a Paytm payment link"""
    print("=" * 80)
    print("Testing Paytm Payment Link Creation")
    print("=" * 80)
    
    # Test merchant ID (replace with actual merchant ID from your database)
    merchant_id = "MERCHANT123"
    
    # Test order data
    order_data = {
        'amount': 100.00,
        'orderid': 'TEST_PAYTM_001',
        'payee_fname': 'John',
        'payee_lname': 'Doe',
        'payee_mobile': '9876543210',
        'payee_email': 'john.doe@example.com',
        'productinfo': 'Test Payment for Paytm Integration',
        'callbackurl': 'https://api.craftpay.in/api/callback/paytm/payin'
    }
    
    print(f"\nTest Order Data:")
    print(json.dumps(order_data, indent=2))
    
    print(f"\nCreating payment link...")
    result = paytm_service.create_payin_order(merchant_id, order_data)
    
    print(f"\n{'=' * 80}")
    print("Result:")
    print(f"{'=' * 80}")
    print(json.dumps(result, indent=2, default=str))
    
    if result.get('success'):
        print(f"\n✅ SUCCESS!")
        print(f"\n📋 Payment Details:")
        print(f"   Transaction ID: {result.get('txn_id')}")
        print(f"   Order ID: {result.get('order_id')}")
        print(f"   Amount: ₹{result.get('amount')}")
        print(f"   Charge: ₹{result.get('charge_amount')}")
        print(f"   Net Amount: ₹{result.get('net_amount')}")
        print(f"\n🔗 Payment Link:")
        print(f"   {result.get('payment_link')}")
        print(f"\n📱 Share this link with customer to complete payment")
        
        return result
    else:
        print(f"\n❌ FAILED!")
        print(f"   Error: {result.get('message')}")
        print(f"   Error Type: {result.get('error_type', 'Unknown')}")
        
        return None

def test_callback_format():
    """Show expected callback format from Paytm"""
    print("\n" + "=" * 80)
    print("Expected Callback Format from Paytm")
    print("=" * 80)
    
    callback_example = {
        'ORDERID': 'TEST_PAYTM_001',
        'MID': 'wOXLNq62001505667648',
        'TXNID': '20240515111212800110168001234567890',
        'TXNAMOUNT': '100.00',
        'PAYMENTMODE': 'UPI',
        'CURRENCY': 'INR',
        'TXNDATE': '2024-05-15 11:12:12.0',
        'STATUS': 'TXN_SUCCESS',
        'RESPCODE': '01',
        'RESPMSG': 'Txn Success',
        'GATEWAYNAME': 'PPBLC',
        'BANKTXNID': '608919646598',
        'CHECKSUMHASH': 'glEBpHd9yJ5g9ReTNkpjfFsvBEb1aYIdQN1mSCbMVNcn6CGDr3UUf3psseqKGPswoU0Xdl6g9P9Jc6U9Q9Ol/JuwcudfMLRgaUjj2rsAl/8='
    }
    
    print("\nPaytm will send POST form data to:")
    print("https://api.craftpay.in/api/callback/paytm/payin")
    print("\nCallback Parameters:")
    for key, value in callback_example.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 80)
    print("Merchant Callback Format (MAXPE Format)")
    print("=" * 80)
    
    merchant_callback = {
        'txn_id': 'PAYTM_MERCHANT123_TEST_PAYTM_001_20260515120000',
        'order_id': 'TEST_PAYTM_001',
        'status': 'SUCCESS',
        'utr': '608919646598',
        'pg_partner': 'PAYTM',
        'amount': 100.00,
        'net_amount': 98.00,
        'charge_amount': 2.00
    }
    
    print("\nMerchant will receive:")
    print(json.dumps(merchant_callback, indent=2))

def check_configuration():
    """Check if Paytm is properly configured"""
    print("=" * 80)
    print("Checking Paytm Configuration")
    print("=" * 80)
    
    from config import Config
    
    print(f"\n✓ Base URL: {Config.PAYTM_BASE_URL}")
    print(f"✓ Merchant ID: {Config.PAYTM_MERCHANT_ID}")
    
    if Config.PAYTM_MERCHANT_KEY:
        print(f"✓ Merchant Key: {'*' * 20} (configured)")
    else:
        print(f"✗ Merchant Key: NOT CONFIGURED")
        print(f"  ⚠️  Please add PAYTM_MERCHANT_KEY to .env file")
        return False
    
    print(f"\n✅ Configuration looks good!")
    return True

def main():
    """Main test function"""
    print("\n" + "=" * 80)
    print("PAYTM PAYIN INTEGRATION TEST")
    print("=" * 80)
    
    # Check configuration
    if not check_configuration():
        print("\n❌ Configuration incomplete. Please fix and try again.")
        return
    
    # Test payment link creation
    result = test_create_payment_link()
    
    # Show callback format
    test_callback_format()
    
    print("\n" + "=" * 80)
    print("Test Complete")
    print("=" * 80)
    
    if result:
        print("\n✅ Paytm integration is working!")
        print("\nNext Steps:")
        print("1. Share the payment link with a test customer")
        print("2. Complete the payment")
        print("3. Check callback logs in database")
        print("4. Verify transaction status and wallet credits")
    else:
        print("\n❌ Test failed. Please check the error messages above.")
        print("\nCommon Issues:")
        print("1. PAYTM_MERCHANT_KEY not configured in .env")
        print("2. Database connection failed")
        print("3. Merchant not found or inactive")
        print("4. Network connectivity issues")

if __name__ == '__main__':
    main()
