#!/usr/bin/env python3
"""
NodePay Payout Test Script
Tests the NodePay payout integration with the same interface as MaxPe
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from maxpe_payout_service import get_payout_service
import uuid
from datetime import datetime

def test_nodepay_payout():
    """Test NodePay payout API integration"""
    
    print("="*80)
    print("🧪 TESTING NODEPAY PAYOUT INTEGRATION")
    print("="*80)
    
    # Get NodePay service instance
    nodepay_service = get_payout_service('NODEPAY')
    
    print(f"✅ Service Provider: {nodepay_service.service_provider}")
    print(f"✅ Base URL: {nodepay_service.base_url}")
    print(f"✅ API Key: {nodepay_service.api_key[:10]}..." if nodepay_service.api_key else "❌ API Key not set")
    print(f"✅ API Secret: {nodepay_service.api_secret[:10]}..." if nodepay_service.api_secret else "❌ API Secret not set")
    print(f"✅ Latitude/Longitude: {'Disabled (NodePay)' if not nodepay_service.latitude else 'Enabled (MaxPe)'}")
    
    if not nodepay_service.api_key or not nodepay_service.api_secret:
        print("\n❌ ERROR: NodePay credentials not configured in .env file")
        print("Please add:")
        print("NODEPAY_API_KEY=your_nodepay_api_key")
        print("NODEPAY_API_SECRET=your_nodepay_api_secret")
        return False
    
    # Test data
    test_data = {
        'account_number': '123456789',
        'ifsc_code': 'ICIC0000001',
        'bank_name': 'ICICI Bank',
        'merchant_order_id': f'TEST_NODEPAY_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
        'amount': 100.00,
        'payee_name': 'Test User',
        'email': 'test@example.com',
        'mobile': '9999999999'
    }
    
    print(f"\n📋 Test Payout Data:")
    for key, value in test_data.items():
        print(f"   {key}: {value}")
    
    print(f"\n🚀 Calling NodePay Payout API...")
    print("-" * 50)
    
    # Call payout API
    result = nodepay_service.call_payout_api(
        account_number=test_data['account_number'],
        ifsc_code=test_data['ifsc_code'],
        bank_name=test_data['bank_name'],
        merchant_order_id=test_data['merchant_order_id'],
        amount=test_data['amount'],
        payee_name=test_data['payee_name'],
        email=test_data['email'],
        mobile=test_data['mobile']
    )
    
    print(f"\n📊 NodePay API Response:")
    print("-" * 50)
    
    if result['success']:
        print("✅ SUCCESS!")
        print(f"   Status: {result.get('status')}")
        print(f"   Merchant Order ID: {result.get('merchant_order_id')}")
        print(f"   Amount: ₹{result.get('amount')}")
        print(f"   Charge: ₹{result.get('charge', '0')}")
        print(f"   GST: ₹{result.get('gst', '0')}")
        print(f"   Total Debit: ₹{result.get('total_debit_amount')}")
        print(f"   Message: {result.get('message')}")
        
        # Test status check if payout was initiated
        if result.get('status') in ['INITIATED', 'QUEUED']:
            print(f"\n🔍 Testing Status Check...")
            print("-" * 50)
            
            status_result = nodepay_service.check_payout_status(test_data['merchant_order_id'])
            
            if status_result['success']:
                print("✅ Status Check SUCCESS!")
                print(f"   Status: {status_result.get('status')}")
                print(f"   Amount: ₹{status_result.get('amount', 0)}")
                print(f"   UTR: {status_result.get('utr', 'N/A')}")
                print(f"   Created At: {status_result.get('created_at', 'N/A')}")
            else:
                print("❌ Status Check FAILED!")
                print(f"   Error: {status_result.get('message')}")
        
        return True
    else:
        print("❌ FAILED!")
        print(f"   Error: {result.get('message')}")
        return False

def test_maxpe_vs_nodepay():
    """Compare MaxPe and NodePay service configurations"""
    
    print("\n" + "="*80)
    print("🔄 COMPARING MAXPE VS NODEPAY CONFIGURATIONS")
    print("="*80)
    
    maxpe_service = get_payout_service('MAXPE')
    nodepay_service = get_payout_service('NODEPAY')
    
    print(f"\n📊 Service Comparison:")
    print("-" * 50)
    print(f"{'Attribute':<20} {'MaxPe':<30} {'NodePay':<30}")
    print("-" * 80)
    print(f"{'Provider':<20} {maxpe_service.service_provider:<30} {nodepay_service.service_provider:<30}")
    print(f"{'Base URL':<20} {maxpe_service.base_url:<30} {nodepay_service.base_url:<30}")
    print(f"{'API Key':<20} {(maxpe_service.api_key[:15] + '...'):<30} {(nodepay_service.api_key[:15] + '...' if nodepay_service.api_key else 'Not Set'):<30}")
    print(f"{'Latitude':<20} {(maxpe_service.latitude or 'None'):<30} {(nodepay_service.latitude or 'None'):<30}")
    print(f"{'Longitude':<20} {(maxpe_service.longitude or 'None'):<30} {(nodepay_service.longitude or 'None'):<30}")
    
    print(f"\n✅ Key Differences:")
    print("   • NodePay uses different base URL: https://merchant.nodepay.in")
    print("   • NodePay does NOT use latitude/longitude (disabled)")
    print("   • NodePay uses different API credentials")
    print("   • Same API signature and request format")

if __name__ == "__main__":
    print("🧪 NodePay Payout Integration Test")
    print("=" * 80)
    
    # Test service comparison first
    test_maxpe_vs_nodepay()
    
    # Test NodePay payout
    success = test_nodepay_payout()
    
    print(f"\n{'='*80}")
    if success:
        print("🎉 ALL TESTS PASSED!")
        print("✅ NodePay integration is working correctly")
    else:
        print("❌ TESTS FAILED!")
        print("🔧 Please check NodePay credentials and configuration")
    print("=" * 80)