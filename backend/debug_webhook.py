import requests
import json
import time

payload = {
    "TXN_amount": "100.00",
    "TXN_date": "2026-01-01 12:00:00",
    "Txn_ID": "DUMMY_REF",
    "TXN_Status": "SUCCESS",
    "UTR": "123456789012"
}

print("Testing localhost:5000")
try:
    resp = requests.post("http://127.0.0.1:5000/api/callback/risexpay/payout", json=payload, timeout=5)
    print("Status:", resp.status_code)
    print("Response:", resp.text)
except Exception as e:
    print("Error:", e)

print("Testing 0.0.0.0:5000")
try:
    resp = requests.post("http://0.0.0.0:5000/api/callback/risexpay/payout", json=payload, timeout=5)
    print("Status:", resp.status_code)
    print("Response:", resp.text)
except Exception as e:
    print("Error:", e)
