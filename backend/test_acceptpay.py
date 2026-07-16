from acceptpay_service import acceptpay_service
from acceptpay_callback_routes import verify_webhook_signature
from config import Config
import json

def test_imports():
    print("AcceptpayService initialized successfully.")
    print(f"Base URL: {Config.ACCEPTPAY_BASE_URL}")

def test_signature():
    secret = "my_secret"
    payload = {"event": "payment.completed", "data": {"status": "success"}}
    payload_bytes = json.dumps(payload).encode('utf-8')
    
    import hmac
    import hashlib
    signature = hmac.new(secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()
    
    print(f"Generated Signature: {signature}")
    is_valid = verify_webhook_signature(payload_bytes, signature, secret)
    print(f"Signature Valid: {is_valid}")
    assert is_valid == True, "Signature verification failed"

if __name__ == "__main__":
    test_imports()
    test_signature()
    print("Tests passed!")
