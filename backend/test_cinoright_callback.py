"""
Test Cinoright Callback Endpoint
Monitor and simulate callbacks from Cinoright
"""

import requests
import json
from datetime import datetime

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def test_callback_endpoint():
    """Test if the callback endpoint is accessible"""
    print_section("STEP 1: Testing Callback Endpoint Accessibility")
    
    callback_url = "https://api.craftpay.in/api/callback/cinoright/payout"
    
    print(f"Callback URL: {callback_url}")
    print("\nTesting if endpoint is accessible...")
    
    try:
        # Try a GET request first to see if endpoint exists
        response = requests.get(callback_url, timeout=10)
        print(f"GET Response: {response.status_code}")
        
        if response.status_code == 405:
            print("✓ Endpoint exists (405 Method Not Allowed is expected for GET)")
        elif response.status_code == 404:
            print("❌ Endpoint not found (404)")
        else:
            print(f"Response: {response.text[:200]}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error accessing endpoint: {e}")
        return False
    
    return True

def simulate_success_callback():
    """Simulate a SUCCESS callback from Cinoright with actual format"""
    print_section("STEP 2: Simulating SUCCESS Callback")
    
    callback_url = "https://api.craftpay.in/api/callback/cinoright/payout"
    
    # Actual Cinoright callback format
    callback_data = {
        "success": True,
        "data": {
            "status": "SUCCESS",
            "statusCode": "200",
            "message": "Transaction Successfully",
            "data": {
                "transactionId": "ARNPY334239241PT194",
                "utr": "UTR123456789TEST",
                "client_referenceId": "TEST1776935987",  # Use a real reference_id from your test
                "acknowledged": 0
            }
        }
    }
    
    print("Callback Data (SUCCESS) - Actual Cinoright Format:")
    print(json.dumps(callback_data, indent=2))
    
    print("\nSending callback to endpoint...")
    
    try:
        response = requests.post(
            callback_url,
            json=callback_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body:")
        print(json.dumps(response.json() if response.headers.get('content-type') == 'application/json' else response.text, indent=2))
        
        if response.status_code == 200:
            print("\n✓ Callback processed successfully")
            return True
        else:
            print(f"\n⚠ Callback returned status {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error sending callback: {e}")
        return False

def simulate_failed_callback():
    """Simulate a FAILED callback from Cinoright with actual format"""
    print_section("STEP 3: Simulating FAILED Callback")
    
    callback_url = "https://api.craftpay.in/api/callback/cinoright/payout"
    
    # Actual Cinoright callback format for FAILED
    callback_data = {
        "success": True,
        "data": {
            "status": "FAILED",
            "statusCode": "400",
            "message": "Transaction failed - Insufficient balance",
            "data": {
                "transactionId": "ARNPY334239241PT195",
                "utr": None,
                "client_referenceId": "TEST1776935987",  # Use a real reference_id from your test
                "acknowledged": 0
            }
        }
    }
    
    print("Callback Data (FAILED) - Actual Cinoright Format:")
    print(json.dumps(callback_data, indent=2))
    
    print("\nSending callback to endpoint...")
    
    try:
        response = requests.post(
            callback_url,
            json=callback_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body:")
        print(json.dumps(response.json() if response.headers.get('content-type') == 'application/json' else response.text, indent=2))
        
        if response.status_code == 200:
            print("\n✓ Callback processed successfully")
            return True
        else:
            print(f"\n⚠ Callback returned status {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error sending callback: {e}")
        return False

def check_callback_logs():
    """Check callback logs in database"""
    print_section("STEP 4: Checking Callback Logs in Database")
    
    try:
        from database import get_db_connection
        
        conn = get_db_connection()
        if not conn:
            print("❌ Database connection failed")
            return
        
        with conn.cursor() as cursor:
            # Check recent callback logs
            cursor.execute("""
                SELECT 
                    merchant_id,
                    txn_id,
                    callback_url,
                    request_data,
                    response_code,
                    response_data,
                    created_at
                FROM callback_logs
                WHERE callback_url LIKE '%cinoright%'
                ORDER BY created_at DESC
                LIMIT 5
            """)
            
            logs = cursor.fetchall()
            
            if not logs:
                print("\n⚠ No Cinoright callback logs found")
                return
            
            print(f"\nFound {len(logs)} recent callback log(s):\n")
            
            for i, log in enumerate(logs, 1):
                print(f"\n{'─' * 80}")
                print(f"Callback Log #{i}")
                print(f"{'─' * 80}")
                print(f"Merchant ID:   {log['merchant_id']}")
                print(f"TXN ID:        {log['txn_id']}")
                print(f"Callback URL:  {log['callback_url']}")
                print(f"Response Code: {log['response_code']}")
                print(f"Created At:    {log['created_at']}")
                
                print(f"\nRequest Data:")
                try:
                    request_data = json.loads(log['request_data'])
                    print(json.dumps(request_data, indent=2))
                except:
                    print(log['request_data'])
                
                print(f"\nResponse Data:")
                print(log['response_data'][:500] if log['response_data'] else 'N/A')
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking logs: {e}")

def monitor_real_callbacks():
    """Instructions for monitoring real callbacks from Cinoright"""
    print_section("STEP 5: Monitoring Real Callbacks from Cinoright")
    
    print("""
To monitor real callbacks from Cinoright, you can:

1. Check Application Logs:
   tail -f /var/log/your-app/app.log | grep -i cinoright

2. Check Nginx Access Logs:
   tail -f /var/log/nginx/access.log | grep cinoright

3. Monitor Database:
   Watch the payout_transactions table for status updates:
   
   SELECT txn_id, reference_id, status, utr, updated_at 
   FROM payout_transactions 
   WHERE pg_partner = 'CINORIGHT' 
   ORDER BY updated_at DESC 
   LIMIT 10;

4. Check Callback Logs Table:
   SELECT * FROM callback_logs 
   WHERE callback_url LIKE '%cinoright%' 
   ORDER BY created_at DESC 
   LIMIT 10;

5. Real-time Monitoring Script:
   Create a simple Flask endpoint to log all incoming requests:
   
   @app.before_request
   def log_request():
       if 'cinoright' in request.path:
           print(f"Cinoright Callback: {request.json}")
""")

def provide_callback_info():
    """Provide callback URL information for Cinoright team"""
    print_section("Callback URL Information for Cinoright Team")
    
    print("""
CALLBACK URL TO PROVIDE TO CINORIGHT:
================================================================================
Production: https://api.craftpay.in/api/callback/cinoright/payout
================================================================================

EXPECTED CALLBACK FORMAT (Actual Cinoright Format):
{
  "success": true,
  "data": {
    "status": "SUCCESS",
    "statusCode": "200",
    "message": "Transaction Successfully",
    "data": {
      "transactionId": "ARNPY334239241PT194",
      "utr": null,
      "client_referenceId": "Br2140002556",
      "acknowledged": 0
    }
  }
}

FIELD MAPPING:
- transactionId: Cinoright's transaction ID (stored as pg_txn_id)
- client_referenceId: Our reference_id (used to find transaction)
- utr: Bank UTR number
- status: SUCCESS, FAILED, or PENDING

CALLBACK REQUIREMENTS:
- Method: POST
- Content-Type: application/json
- No authentication required (public endpoint)

CALLBACK RESPONSES:
- 200 OK: Callback processed successfully
- 400 Bad Request: Missing required fields
- 404 Not Found: Transaction not found
- 500 Internal Server Error: Processing error

WHAT HAPPENS WHEN CALLBACK IS RECEIVED:
1. Transaction is found by reference_id (client_referenceId)
2. Transaction status is updated in database
3. UTR and pg_txn_id (transactionId) are recorded
4. Callback is forwarded to merchant (if configured)
5. Response is sent back to Cinoright
""")

def main():
    """Main test function"""
    print("\n" + "=" * 80)
    print("  CINORIGHT CALLBACK TESTING & MONITORING")
    print("=" * 80)
    print("\nThis script will help you test and monitor Cinoright callbacks")
    
    # Step 1: Test endpoint accessibility
    if not test_callback_endpoint():
        print("\n❌ Callback endpoint is not accessible")
        print("Please check:")
        print("1. Is the Flask app running?")
        print("2. Is Nginx configured correctly?")
        print("3. Is the domain pointing to the correct server?")
        return
    
    # Step 2: Ask if user wants to simulate callbacks
    print("\n" + "=" * 80)
    response = input("Do you want to simulate a SUCCESS callback? (yes/no): ")
    if response.lower() in ['yes', 'y']:
        print("\n⚠ IMPORTANT: Make sure you have a real transaction with the reference_id")
        print("   in the database before simulating the callback!")
        reference_id = input("\nEnter the reference_id (client_referenceId) from a real transaction: ").strip()
        
        if reference_id:
            # Update the callback data with user's reference_id (actual Cinoright format)
            callback_url = "https://api.craftpay.in/api/callback/cinoright/payout"
            callback_data = {
                "success": True,
                "data": {
                    "status": "SUCCESS",
                    "statusCode": "200",
                    "message": "Transaction Successfully",
                    "data": {
                        "transactionId": f"ARNPY{reference_id[-10:]}",
                        "utr": f"UTR{int(datetime.now().timestamp())}",
                        "client_referenceId": reference_id,
                        "acknowledged": 0
                    }
                }
            }
            
            print("\nSending SUCCESS callback...")
            try:
                response = requests.post(
                    callback_url,
                    json=callback_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                print(f"\nResponse Status: {response.status_code}")
                print(f"Response Body:")
                try:
                    print(json.dumps(response.json(), indent=2))
                except:
                    print(response.text)
            except Exception as e:
                print(f"❌ Error: {e}")
    
    # Step 3: Check callback logs
    check_callback_logs()
    
    # Step 4: Provide monitoring instructions
    monitor_real_callbacks()
    
    # Step 5: Provide callback info
    provide_callback_info()
    
    print("\n" + "=" * 80)
    print("  TESTING COMPLETED")
    print("=" * 80)
    print("\nNext Steps:")
    print("1. Provide callback URL to Cinoright team")
    print("2. Ask them to configure it in their system")
    print("3. Make a test payout and wait for callback")
    print("4. Monitor logs to see if callback is received")
    print("5. Check database to verify status update")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⊘ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
