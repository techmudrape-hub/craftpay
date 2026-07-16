import requests
import hmac
import hashlib
import json
import time

# Configuration
URL = "http://127.0.0.1:5000/webhook" # or http://127.0.0.1:5000/api/callback/acceptpay/webhook
SECRET = "0f66a07a02098e1f20887747feb6a1db"

def test_webhook(order_id="TEST_ORD_123", txn_id="6a394bee1dc1"):
    # Simulated AcceptPay Payload
    payload_data = {
        "event": "payment.completed",
        "timestamp": "2026-06-22T14:58:22.597Z",
        "data": {
            "transactionId": txn_id,
            "status": "COMPLETED",
            "amount": 100,
            "currency": "INR",
            "paymentMethod": "Upi",
            "customerEmail": "test@example.com",
            "customerPhone": "9876543210",
            "billId": order_id,
            "completedAt": "2026-06-22T14:58:22.597Z"
        }
    }

    # AcceptPay stringifies the payload before calculating HMAC
    # This exactly mimics Node.js JSON.stringify(req.body)
    payload_string = json.dumps(payload_data, separators=(',', ':'))

    # Calculate HMAC-SHA256 signature
    signature = hmac.new(
        SECRET.encode('utf-8'),
        payload_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-AcceptPay-Signature": signature
    }

    print(f"Sending webhook to {URL}")
    print(f"Payload: {payload_string}")
    print(f"Calculated Signature: {signature}")

    try:
        # We send the exact same payload string to guarantee no framework stringification differences
        response = requests.post(URL, data=payload_string, headers=headers)
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body: {response.text}")
    except Exception as e:
        print(f"Error sending request: {e}")

if __name__ == "__main__":
    test_webhook()
