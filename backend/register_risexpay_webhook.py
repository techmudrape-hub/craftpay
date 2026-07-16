"""
Register webhook URL with Risexpay
One-time setup to configure webhook notifications
"""

import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def register_webhook():
    """Register webhook URL with Risexpay"""
    
    # Get credentials
    api_key = os.getenv('RISEXPAY_API_KEY', '')
    mid = os.getenv('RISEXPAY_MID', '')
    backend_url = os.getenv('BACKEND_URL', 'https://api.craftpay.in')
    
    if not all([api_key, mid]):
        print("❌ Missing credentials in .env file")
        print("   Required: RISEXPAY_API_KEY, RISEXPAY_MID")
        return False
    
    # Webhook URL
    webhook_url = f"{backend_url}/api/callback/risexpay/payin"
    
    print("\n" + "="*80)
    print("RISEXPAY WEBHOOK REGISTRATION")
    print("="*80)
    print(f"\nConfiguration:")
    print(f"  API Key: {api_key[:10]}...")
    print(f"  MID: {mid}")
    print(f"  Webhook URL: {webhook_url}")
    
    # Prepare request
    url = "https://risexpay.in/api/v1/imb/register_webhook.php"
    payload = {
        "apikey": api_key,
        "mid": mid,
        "url": webhook_url
    }
    
    print(f"\n📤 Sending registration request...")
    print(f"   Endpoint: {url}")
    print(f"   Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"\n📥 Response Status: {response.status_code}")
        
        try:
            response_json = response.json()
            print(f"📄 Response:")
            print(json.dumps(response_json, indent=2))
            
            if response.status_code == 200 and response_json.get('status'):
                print(f"\n✅ SUCCESS! Webhook registered successfully!")
                print(f"\n📋 Webhook Details:")
                print(f"   URL: {webhook_url}")
                print(f"   Status: Active")
                print(f"\n💡 Risexpay will now send payment notifications to this URL")
                return True
            else:
                print(f"\n❌ Failed: {response_json.get('message', 'Unknown error')}")
                return False
                
        except json.JSONDecodeError:
            print(f"Response Text: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"\n❌ Request timeout")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ Connection error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n⚠️  This script will register your webhook URL with Risexpay")
    print("   This is a one-time setup")
    print("   Press Ctrl+C to cancel\n")
    
    try:
        import time
        time.sleep(2)
        
        success = register_webhook()
        
        if success:
            print("\n" + "="*80)
            print("✅ WEBHOOK REGISTRATION COMPLETE")
            print("="*80)
            print("\n📋 Next Steps:")
            print("   1. Configure service routing in admin dashboard")
            print("   2. Create test transaction")
            print("   3. Verify webhook is received")
            print("   4. Check wallet credits")
        else:
            print("\n" + "="*80)
            print("❌ WEBHOOK REGISTRATION FAILED")
            print("="*80)
            print("\n📞 Contact Risexpay Support:")
            print("   Email: support@risexpay.in")
            print("   Ask them to register your webhook URL manually")
            print(f"   URL: {os.getenv('BACKEND_URL', 'https://api.craftpay.in')}/api/callback/risexpay/payin")
        
        print("="*80 + "\n")
        
        return success
        
    except KeyboardInterrupt:
        print("\n\n❌ Registration cancelled by user")
        return False

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
