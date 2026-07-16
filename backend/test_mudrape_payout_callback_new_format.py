#!/usr/bin/env python3
"""
Test Mudrape Payout Callback - NEW FORMAT (April 2026)
Tests the updated callback handler with the new webhook payload format
"""

import requests
import json
from datetime import datetime

# Your callback URL
CALLBACK_URL = "https://yourdomain.com/api/callback/mudrape/payout"

# NEW FORMAT test payload (from Mudrape docs)
test_payload_success = {
    "payoutId": "cmnu09uuj000555555gvrxyf",
    "referenceId": "TXN4830995555001",  # This should match your client_txn_id
    "externalTxnId": "610112455543",
    "amount": 100,
    "status": "SUCCESS",
    "utr": "610112455543",
    "channel": "IMPS",
    "payeeName": "Test User",
    "timestamp": "2026-04-11T12:52:28.471435",
    "provider": "PAYMENT GATEWAY"
}

test_payload_failed = {
    "payoutId": "cmnu09uuj000555555gvrxyf",
    "referenceId": "TXN4830995555002",
    "externalTxnId": "610112455544",
    "amount": 100,
    "status": "FAILED",
    "utr": "",
    "channel": "IMPS",
    "payeeName": "Test User",
    "timestamp": "2026-04-11T12:52:28.471435",
    "provider": "PAYMENT GATEWAY"
}

def test_callback(payload, test_name):
    """Test callback with given payload"""
    print(f"\n{'='*80}")
    print(f"TESTING: {test_name}")
    print(f"{'='*80}")
    
    print(f"URL: {CALLBACK_URL}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            CALLBACK_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            print("✅ SUCCESS - Callback processed successfully")
        else:
            print("❌ FAILED - Callback returned error")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: {e}")

def main():
    print("🧪 MUDRAPE PAYOUT CALLBACK TESTER - NEW FORMAT")
    print("=" * 80)
    
    print("\n📋 CALLBACK URL INFORMATION:")
    print(f"   Your callback endpoint: /api/callback/mudrape/payout")
    print(f"   Full URL to provide to Mudrape: https://yourdomain.com/api/callback/mudrape/payout")
    print(f"   Replace 'yourdomain.com' with your actual domain")
    
    print("\n📝 MUDRAPE CONFIGURATION:")
    print("   1. Contact Mudrape integration team")
    print("   2. Provide them your payout webhook URL (different from payin)")
    print("   3. Ensure URL is HTTPS and publicly accessible")
    print("   4. Test with the payloads below")
    
    # Test SUCCESS callback
    test_callback(test_payload_success, "SUCCESS Callback - NEW FORMAT")
    
    # Test FAILED callback  
    test_callback(test_payload_failed, "FAILED Callback - NEW FORMAT")
    
    print(f"\n{'='*80}")
    print("TESTING COMPLETE")
    print(f"{'='*80}")
    
    print("\n💡 NEXT STEPS:")
    print("   1. Update CALLBACK_URL variable with your actual domain")
    print("   2. Ensure you have test transactions with matching referenceId")
    print("   3. Run this script to verify callback handling")
    print("   4. Provide the callback URL to Mudrape team")

if __name__ == '__main__':
    main()