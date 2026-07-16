import requests
import json

def test_api():
    url = "https://acceptpayfrontend.vercel.app/api/v1/transaction/initiate-transaction"
    token = "ak_f33897e77ee6499dbf6cbfd582b224e0ad2591150c93f304"
    
    base_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    base_data = {
        "amount": 100,
        "mobile": "9876543210",
        "email": "customer@example.com",
        "billId": "ORDER_101",
        "description": "Test order payment"
    }
    
    test_cases = [
        ("1. Exact payload from docs", {}),
        ("2. Amount as string", {"amount": "100"}),
        ("3. With customerName", {"customerName": "Test User"}),
        ("4. With name", {"name": "Test User"}),
        ("5. With returnUrl", {"returnUrl": "https://google.com"}),
        ("6. With callbackUrl", {"callbackUrl": "https://google.com"}),
        ("7. With currency", {"currency": "INR"}),
        ("8. With type", {"type": "PAYIN"}),
        ("9. bill_id instead of billId", {"bill_id": "ORDER_101"}),
        ("10. orderId instead of billId", {"orderId": "ORDER_101"})
    ]
    
    print("="*50)
    print("Acceptpay API Bruteforce Debugger")
    print("="*50)
    
    for desc, extra in test_cases:
        payload = base_data.copy()
        for k, v in extra.items():
            payload[k] = v
        if "bill_id" in extra or "orderId" in extra:
            if "billId" in payload:
                del payload["billId"]
                
        print(f"Testing {desc}...")
        try:
            res = requests.post(url, headers=base_headers, json=payload, timeout=10)
            print(f"Status: {res.status_code}")
            print(f"Response: {res.text}")
            if res.status_code == 200 or 'success' in res.text.lower():
                print("✅ THIS WORKED!")
                print("Payload:", json.dumps(payload, indent=2))
        except Exception as e:
            print(f"Error: {e}")
        print("-" * 50)
        
    # Also test header variations just in case
    print("\nTesting Header Variations (with base payload)...")
    header_variations = [
        ("No Bearer prefix", {"Content-Type": "application/json", "Authorization": token}),
        ("X-API-Key instead", {"Content-Type": "application/json", "X-API-Key": token}),
        ("token instead", {"Content-Type": "application/json", "token": token}),
        ("apikey instead", {"Content-Type": "application/json", "apikey": token})
    ]
    
    for desc, h_extra in header_variations:
        print(f"Testing {desc}...")
        try:
            res = requests.post(url, headers=h_extra, json=base_data, timeout=10)
            print(f"Status: {res.status_code}")
            print(f"Response: {res.text}")
            if res.status_code == 200 or 'success' in res.text.lower():
                print("✅ THIS WORKED!")
                print("Headers:", h_extra)
        except Exception as e:
            print(f"Error: {e}")
        print("-" * 50)

if __name__ == "__main__":
    test_api()
