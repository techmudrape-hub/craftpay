#!/usr/bin/env python3
"""
ViyonaPay Webhook Simulator
Simulates ViyonaPay sending an encrypted webhook callback to OrchPay

This script:
1. Takes order_id, amount, and status as input
2. Encrypts the payload using AES-GCM (like ViyonaPay does)
3. Signs the payload using your private key
4. Sends it to your OrchPay callback endpoint
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
import json
import base64
import uuid
from datetime import datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from config import Config


def load_client_private_key():
    """Load client's private key for signing"""
    try:
        key_path = Config.VIYONAPAY_CLIENT_PRIVATE_KEY_PATH
        with open(key_path, 'rb') as f:
            key_data = f.read()
        return RSA.import_key(key_data)
    except Exception as e:
        print(f"❌ Failed to load private key: {e}")
        return None


def load_webhook_secret_key():
    """Load webhook secret key for encryption"""
    try:
        secret_key_hex = Config.VIYONAPAY_WEBHOOK_SECRET_KEY
        if not secret_key_hex:
            print(f"❌ VIYONAPAY_WEBHOOK_SECRET_KEY not configured")
            return None
        
        key_bytes = bytes.fromhex(secret_key_hex)
        if len(key_bytes) != 16:
            print(f"❌ Invalid key length: {len(key_bytes)} bytes (expected 16)")
            return None
        
        return key_bytes
    except Exception as e:
        print(f"❌ Failed to load webhook secret key: {e}")
        return None


def encrypt_webhook_payload(data_dict, secret_key, aad_dict):
    """
    Encrypt webhook payload using AES-128-GCM
    
    Args:
        data_dict: Dictionary to encrypt
        secret_key: 16-byte secret key
        aad_dict: Additional Authenticated Data
    
    Returns:
        Base64-encoded encrypted data
    """
    try:
        import os
        
        # Convert data to JSON
        plaintext = json.dumps(data_dict, separators=(',', ':')).encode('utf-8')
        
        # Convert AAD to canonical JSON
        aad_json = json.dumps(aad_dict, separators=(',', ':'), sort_keys=True)
        aad_bytes = aad_json.encode('utf-8')
        
        # Generate random 12-byte nonce
        nonce = os.urandom(12)
        
        # Encrypt using AES-GCM
        aesgcm = AESGCM(secret_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, aad_bytes)
        
        # Combine: nonce + ciphertext (ciphertext includes tag)
        encrypted_data = nonce + ciphertext
        
        return base64.b64encode(encrypted_data).decode('utf-8')
    except Exception as e:
        print(f"❌ Encryption error: {e}")
        import traceback
        traceback.print_exc()
        return None


def sign_payload(payload_dict, private_key):
    """
    Sign payload using RSA private key
    
    Args:
        payload_dict: Dictionary to sign
        private_key: RSA private key
    
    Returns:
        Base64-encoded signature
    """
    try:
        # Convert to canonical JSON
        json_data = json.dumps(payload_dict, separators=(',', ':'), sort_keys=True)
        
        # Create SHA-256 hash
        hash_obj = SHA256.new(json_data.encode('utf-8'))
        
        # Sign
        signature = pkcs1_15.new(private_key).sign(hash_obj)
        
        return base64.b64encode(signature).decode('utf-8')
    except Exception as e:
        print(f"❌ Signing error: {e}")
        return None


def send_webhook(order_id, amount, status='SUCCESS', transaction_id=None, bank_ref_id=None):
    """
    Send encrypted webhook to OrchPay
    
    Args:
        order_id: Order ID (must exist in your database)
        amount: Payment amount
        status: Payment status (SUCCESS, FAILED, PENDING)
        transaction_id: ViyonaPay transaction ID (optional)
        bank_ref_id: Bank reference ID / UTR (optional)
    """
    print("="*80)
    print("🚀 VIYONAPAY WEBHOOK SIMULATOR")
    print("="*80)
    
    # Load keys
    print("\n📋 Loading encryption keys...")
    private_key = load_client_private_key()
    if not private_key:
        return False
    
    secret_key = load_webhook_secret_key()
    if not secret_key:
        return False
    
    print("✅ Keys loaded successfully")
    
    # Generate request metadata
    request_id = str(uuid.uuid4())
    timestamp = int(datetime.now().timestamp())
    
    print(f"\n📦 Preparing webhook payload...")
    print(f"  Order ID: {order_id}")
    print(f"  Amount: ₹{amount}")
    print(f"  Status: {status}")
    print(f"  Transaction ID: {transaction_id or 'Auto-generated'}")
    print(f"  Bank Ref ID: {bank_ref_id or 'None'}")
    
    # Prepare payment data (responseBody)
    payment_data = {
        'paymentStatus': status,
        'transactionId': transaction_id or f"VIYO_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        'orderId': order_id,
        'amount': float(amount),
        'paymentMode': 'UPI',
        'bankRefId': bank_ref_id or '',
        'customerName': 'Test Customer',
        'customerEmail': 'test@example.com',
        'customerPhoneNumber': '9999999999',
        'cardType': '',
        'cardMasked': ''
    }
    
    # Wrap in responseBody
    response_body_wrapper = {
        'responseBody': payment_data
    }
    
    # Prepare AAD
    aad = {
        'timestamp': timestamp,
        'request_id': request_id
    }
    
    print(f"\n🔐 Encrypting payload...")
    # Encrypt the response body
    encrypted_data = encrypt_webhook_payload(response_body_wrapper, secret_key, aad)
    if not encrypted_data:
        return False
    
    print(f"✅ Payload encrypted")
    print(f"  Encrypted data length: {len(encrypted_data)} chars")
    
    # Prepare webhook payload
    webhook_payload = {
        'encrypted_data': encrypted_data,
        'response_status': 1
    }
    
    print(f"\n✍️  Signing payload...")
    # Sign the webhook payload
    signature = sign_payload(webhook_payload, private_key)
    if not signature:
        return False
    
    print(f"✅ Payload signed")
    print(f"  Signature length: {len(signature)} chars")
    
    # Prepare headers
    headers = {
        'Content-Type': 'application/json',
        'X-SIGNATURE': signature,
        'X-TIMESTAMP': str(timestamp),
        'X-Request-Id': request_id,
        'X-API-KEY': Config.VIYONAPAY_API_KEY
    }
    
    # Determine callback URL
    callback_url = "https://api.craftpay.in/api/callback/viyonapay/payin"
    
    print(f"\n📤 Sending webhook to OrchPay...")
    print(f"  URL: {callback_url}")
    print(f"  Request ID: {request_id}")
    print(f"  Timestamp: {timestamp}")
    
    try:
        response = requests.post(
            callback_url,
            json=webhook_payload,
            headers=headers,
            timeout=30
        )
        
        print(f"\n📥 Response received:")
        print(f"  Status Code: {response.status_code}")
        print(f"  Headers: {dict(response.headers)}")
        
        try:
            response_data = response.json()
            print(f"  Response Body:")
            print(json.dumps(response_data, indent=4))
        except:
            print(f"  Response Body (raw): {response.text}")
        
        if response.status_code == 200:
            print(f"\n✅ SUCCESS - Webhook processed successfully!")
            return True
        else:
            print(f"\n❌ FAILED - Webhook returned error")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR sending webhook: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function"""
    print("\n" + "="*80)
    print("VIYONAPAY WEBHOOK SIMULATOR FOR ORCHPAY")
    print("="*80)
    print("\nThis script simulates ViyonaPay sending an encrypted webhook to your system.")
    print("You need to provide:")
    print("  1. Order ID (must exist in your database)")
    print("  2. Amount")
    print("  3. Status (SUCCESS, FAILED, or PENDING)")
    print("="*80)
    
    # Get input
    print("\n📝 Enter webhook details:")
    order_id = input("  Order ID: ").strip()
    if not order_id:
        print("❌ Order ID is required")
        return
    
    amount_str = input("  Amount (₹): ").strip()
    try:
        amount = float(amount_str)
    except:
        print("❌ Invalid amount")
        return
    
    status = input("  Status (SUCCESS/FAILED/PENDING) [SUCCESS]: ").strip().upper() or 'SUCCESS'
    if status not in ['SUCCESS', 'FAILED', 'PENDING']:
        print("❌ Invalid status. Must be SUCCESS, FAILED, or PENDING")
        return
    
    transaction_id = input("  Transaction ID (optional): ").strip() or None
    bank_ref_id = input("  Bank Ref ID/UTR (optional): ").strip() or None
    
    # Confirm
    print(f"\n{'='*80}")
    print("CONFIRMATION")
    print(f"{'='*80}")
    print(f"  Order ID: {order_id}")
    print(f"  Amount: ₹{amount}")
    print(f"  Status: {status}")
    print(f"  Transaction ID: {transaction_id or 'Auto-generated'}")
    print(f"  Bank Ref ID: {bank_ref_id or 'None'}")
    print(f"{'='*80}")
    
    confirm = input("\nSend webhook? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Cancelled")
        return
    
    # Send webhook
    success = send_webhook(order_id, amount, status, transaction_id, bank_ref_id)
    
    if success:
        print(f"\n{'='*80}")
        print("✅ WEBHOOK SENT SUCCESSFULLY")
        print(f"{'='*80}")
        print("\nCheck your database to verify:")
        print(f"  1. Transaction status updated to {status}")
        print(f"  2. Wallet credited (if SUCCESS)")
        print(f"  3. Callback logs created")
    else:
        print(f"\n{'='*80}")
        print("❌ WEBHOOK FAILED")
        print(f"{'='*80}")
        print("\nPossible issues:")
        print("  1. Order ID doesn't exist in database")
        print("  2. Encryption/signature error")
        print("  3. Network/server error")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
