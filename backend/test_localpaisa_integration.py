import os
import sys
import json
import random
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

# Add the current directory to path to allow importing backend modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

def test_create_payin_order(merchant_id="M12345"):
    """
    Test the creation of a Localpaisa payin order directly via the service.
    This will bypass the HTTP layer and directly test the service integration and Localpaisa API.
    """
    print("\n--- Testing Localpaisa Service Order Creation ---")
    try:
        from localpaisa_service import localpaisa_service
        
        # Generate a random order ID
        order_id = f"TEST_ORD_{int(time.time())}_{random.randint(1000, 9999)}"
        
        order_data = {
            "amount": "100.00",
            "orderid": order_id,
            "payee_fname": "Test",
            "payee_lname": "User",
            "payee_mobile": "9999999999",
            "payee_email": "test@example.com",
            "productinfo": "Test Payin",
            "callbackurl": "https://webhook.site/your-webhook-url" # Optional
        }
        
        print(f"Using Merchant ID: {merchant_id}")
        print(f"Order Data: {json.dumps(order_data, indent=2)}")
        print("\nCalling create_payin_order...")
        
        # Ensure credentials exist
        if localpaisa_service.client_id == 'YOUR_CLIENT_ID' or localpaisa_service.client_secret == 'YOUR_CLIENT_SECRET':
            print("⚠️ WARNING: LOCALPAISA_CLIENT_ID or LOCALPAISA_CLIENT_SECRET not set in environment.")
            print("The API call to Localpaisa will likely fail with unauthorized/invalid credentials.\n")

        result = localpaisa_service.create_payin_order(merchant_id, order_data)
        
        print("\nResult:")
        print(json.dumps(result, indent=2))
        
        return result
    except ImportError as e:
        print(f"Error importing service: {e}")
        print("Make sure you are running this script from the backend directory.")
        return None
    except Exception as e:
        print(f"Error testing order creation: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_webhook_callback(pg_txn_id="TXN123456789", status="SUCCESS"):
    """
    Test the webhook callback endpoint locally.
    This simulates Localpaisa sending a server-to-server callback.
    """
    print("\n--- Testing Localpaisa Webhook Callback ---")
    
    # URL assumes your flask app is running on localhost:5000
    base_url = "http://127.0.0.1:5000"
    webhook_url = f"{base_url}/api/callback/localpaisa/payin"
    
    # Generate mock Localpaisa webhook payload
    utr_number = f"UTR{int(time.time())}"
    
    payload = {
        "event": "payin.status",
        "transaction_id": pg_txn_id,
        "utr_number": utr_number,
        "status": status,
        "amount": "10.00",
        "created_at": datetime.now().isoformat(),
        "processed_at": datetime.now().isoformat()
    }
    
    print(f"Sending POST request to: {webhook_url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        print(f"\nResponse Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Could not connect to {base_url}.")
        print("Please ensure your Flask backend server is running (e.g., `python app.py` or `flask run`).")
    except Exception as e:
        print(f"❌ Error sending webhook: {e}")

if __name__ == "__main__":
    print("========================================")
    print("    LOCALPAISA INTEGRATION TEST SCRIPT  ")
    print("========================================")
    
    print("\nSelect a test to run:")
    print("1. Test Order Creation (Directly calls service)")
    print("2. Test Webhook Callback (Simulates Localpaisa callback over HTTP)")
    print("3. Run Both")
    
    try:
        choice = input("\nEnter choice (1/2/3) [1]: ").strip() or "1"
        
        if choice in ['1', '3']:
            merchant_id = input("\nEnter a valid Merchant ID from your DB [M12345]: ").strip() or "M12345"
            result = test_create_payin_order(merchant_id)
            
            # If we created an order, we can use its transaction ID for the webhook test
            if choice == '3' and result and result.get('success'):
                pg_txn_id = result.get('pg_txn_id')
                if pg_txn_id:
                    print(f"\nUsing generated pg_txn_id '{pg_txn_id}' for webhook test...")
                    test_webhook_callback(pg_txn_id=pg_txn_id, status="SUCCESS")
                else:
                    print("\nCould not get pg_txn_id from order creation result. Skipping webhook test.")
            elif choice == '3':
                print("\nOrder creation failed. Webhook test using the generated transaction ID skipped.")
                
        elif choice == '2':
            pg_txn_id = input("\nEnter a transaction_id (pg_txn_id) that exists in payin_transactions: ").strip()
            if not pg_txn_id:
                print("Transaction ID is required for a valid webhook test.")
            else:
                status_input = input("Enter status (SUCCESS/FAILED) [SUCCESS]: ").strip().upper() or "SUCCESS"
                test_webhook_callback(pg_txn_id=pg_txn_id, status=status_input)
        else:
            print("Invalid choice.")
            
    except KeyboardInterrupt:
        print("\nTest cancelled.")
