"""
Test RisexPay QR Generation
Verify that RisexPay returns proper intent_url/upi_link for QR code generation
"""

import sys
import json
from risexpay_service import risexpay_service

def test_risexpay_qr():
    """Test RisexPay payin order creation and verify QR data"""
    
    print("=" * 80)
    print("TESTING RISEXPAY QR CODE GENERATION")
    print("=" * 80)
    
    # Test merchant ID (replace with actual merchant ID)
    merchant_id = 'ORCH001'
    
    # Test order data
    order_data = {
        'amount': '100.00',
        'orderid': f'TEST_QR_{int(time.time())}',
        'payee_fname': 'Test',
        'payee_lname': 'Customer',
        'payee_mobile': '9876543210',
        'payee_email': 'test@example.com',
        'productinfo': 'Test Payment for QR'
    }
    
    print(f"\n1. Creating RisexPay order...")
    print(f"   Merchant ID: {merchant_id}")
    print(f"   Order ID: {order_data['orderid']}")
    print(f"   Amount: ₹{order_data['amount']}")
    
    try:
        result = risexpay_service.create_payin_order(merchant_id, order_data)
        
        print(f"\n2. Response received:")
        print(f"   Success: {result.get('success')}")
        
        if not result.get('success'):
            print(f"   ❌ Error: {result.get('message')}")
            return False
        
        print(f"   ✓ Transaction ID: {result.get('txn_id')}")
        print(f"   ✓ Order ID: {result.get('order_id')}")
        print(f"   ✓ IMB Order ID: {result.get('imb_order_id')}")
        
        print(f"\n3. Payment Links:")
        print(f"   payment_link: {result.get('payment_link', 'NOT PROVIDED')}")
        print(f"   upi_link: {result.get('upi_link', 'NOT PROVIDED')}")
        print(f"   intent_url: {result.get('intent_url', 'NOT PROVIDED')}")
        print(f"   qr_string: {result.get('qr_string', 'NOT PROVIDED')}")
        
        # Verify QR generation data
        print(f"\n4. QR Generation Verification:")
        
        intent_url = result.get('intent_url') or result.get('upi_link') or result.get('qr_string')
        payment_link = result.get('payment_link')
        
        if intent_url:
            print(f"   ✓ Intent URL available: {intent_url[:100]}...")
            
            # Check if it's a UPI string
            if intent_url.startswith('upi://'):
                print(f"   ✓ Valid UPI string format detected")
                
                # Parse UPI parameters
                if '?' in intent_url:
                    params_str = intent_url.split('?')[1]
                    params = dict(param.split('=') for param in params_str.split('&') if '=' in param)
                    
                    print(f"\n   UPI Parameters:")
                    for key, value in params.items():
                        print(f"     - {key}: {value}")
                else:
                    print(f"   ⚠ No parameters found in UPI string")
            else:
                print(f"   ⚠ Not a UPI string format (doesn't start with upi://)")
                print(f"   ℹ This might be a web URL - check if it's correct")
        else:
            print(f"   ❌ No intent_url/upi_link/qr_string found!")
            print(f"   ⚠ QR code generation will fail on frontend")
        
        if payment_link:
            print(f"\n   Payment Link: {payment_link[:100]}...")
            if payment_link.startswith('http'):
                print(f"   ℹ This is a web URL (not for QR generation)")
        
        print(f"\n5. Frontend Behavior Prediction:")
        if intent_url and intent_url.startswith('upi://'):
            print(f"   ✓ Frontend will generate QR code from intent_url")
            print(f"   ✓ QR code will contain UPI payment string")
        elif intent_url:
            print(f"   ⚠ Frontend will try to generate QR from intent_url")
            print(f"   ⚠ May not work if it's not a valid UPI string")
        else:
            print(f"   ❌ Frontend will fail to generate QR code")
            print(f"   ❌ No valid UPI string available")
        
        print(f"\n" + "=" * 80)
        print(f"TEST COMPLETED")
        print(f"=" * 80)
        
        return result.get('success')
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    import time
    success = test_risexpay_qr()
    sys.exit(0 if success else 1)
