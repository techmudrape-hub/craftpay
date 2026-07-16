import hmac
import hashlib
import json

secret = 'wt_live_a80e5f702b8f7e3440317773790ba1e4'
payload = '{"event":"payment.completed","timestamp":"2026-06-22T14:58:22.597Z","data":{"transactionId":"6a394bee1dc1","status":"COMPLETED","amount":100,"currency":"INR","paymentMethod":"Upi","customerEmail":"john@example.com","customerPhone":"9876543210","billId":"BILL_...","completedAt":"2026-06-22T14:58:22.597Z"}}'

print("Raw signature:")
print(hmac.new(secret.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest())

data = json.loads(payload)
node_json = json.dumps(data, separators=(',', ':'))
print("Node json.stringify signature:")
print(hmac.new(secret.encode('utf-8'), node_json.encode('utf-8'), hashlib.sha256).hexdigest())
