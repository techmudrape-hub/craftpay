#!/usr/bin/env python3
"""
Decrypt the ViyonaPay callback from the screenshot
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import base64
import json

# The encrypted data from the screenshot
ENCRYPTED_DATA = "EyFUI8cJoH7df7UjoXyhWngba+slecgtSnWgRHapxvOxajKN1qFBlbdGSqWnL9QnIGzALvshSRvsyJquOfmItZGjIIxouLHe0dApHa08Ce1Bfs5DpxbQb2TZxVaZ2RkrrLKu/P+rAWzT3acRxXR06VFIpkpAd5R7ED9eC7kCT3Ge3OQvyH+mLgRBrg1njuayKtMytjODcSbziP2wEUHYRiwnuch8Cx9ysQy4RXYddBWBExSjq8xc7+yaVHCEz0rXbpdFMcr2XxMw82dj8AaReXbCY9twQdr2JrftFsAMJoeiK5GMrD+RyuITQH1yAyZNqfewb7CE6W/aSZWdflQ+tRfWYb89m2ZreIILOQ671Xdc+yO/OGpOTasU9tQHj+M/OR0L6IWaUYtHeWONmIOfHcC6CFZ4t0amxoo7HB6PpSDotMeJOxA1IhtFR8qmU1b68ldN8mEadEmmeC6Wk5n6SsS4nb5/U4zZH4vKp54lgMbPuncg0e2CX9GRVU66INUA4BkNqpb/3a97TCCe8jEt+jPR8vqnLdvdA8F9l4a4BYfQLpYRA+gQxYVIjA=="

# Your webhook secret key from .env
WEBHOOK_SECRET_KEY = "YOUR_WEBHOOK_SECRET_KEY_HERE"  # 16-byte hex key

def decrypt_webhook_response(encrypted_b64, secret_key_hex, aad_dict):
    """
    Decrypt ViyonaPay webhook response using AES-128-GCM
    
    Args:
        encrypted_b64: Base64 encoded encrypted data (format: nonce + ciphertext + tag)
        secret_key_hex: 16-byte hex string (32 hex characters)
        aad_dict: Additional authenticated data dict with timestamp and request_id
    
    Returns:
        Decrypted data as dict, or None if decryption fails
    """
    try:
        print(f"\n🔓 Decrypting ViyonaPay webhook...")
        print(f"  Encrypted data (base64): {encrypted_b64[:50]}...")
        print(f"  Secret key (hex): {secret_key_hex}")
        print(f"  AAD: {aad_dict}")
        
        # Decode base64
        encrypted_bytes = base64.b64decode(encrypted_b64)
        print(f"  Encrypted bytes length: {len(encrypted_bytes)}")
        
        # Extract components (nonce: 12 bytes, ciphertext: variable, tag: 16 bytes)
        nonce = encrypted_bytes[:12]
        tag = encrypted_bytes[-16:]
        ciphertext = encrypted_bytes[12:-16]
        
        print(f"  Nonce length: {len(nonce)}")
        print(f"  Ciphertext length: {len(ciphertext)}")
        print(f"  Tag length: {len(tag)}")
        
        # Convert hex key to bytes
        secret_key = bytes.fromhex(secret_key_hex)
        print(f"  Secret key length: {len(secret_key)} bytes")
        
        # Prepare AAD (canonical JSON)
        aad_json = json.dumps(aad_dict, separators=(',', ':'), sort_keys=True)
        aad_bytes = aad_json.encode('utf-8')
        print(f"  AAD (canonical JSON): {aad_json}")
        
        # Create cipher
        cipher = AES.new(secret_key, AES.MODE_GCM, nonce=nonce)
        cipher.update(aad_bytes)
        
        # Decrypt and verify
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        
        print(f"✅ Decryption successful!")
        print(f"  Plaintext length: {len(plaintext)}")
        
        # Parse JSON
        decrypted_data = json.loads(plaintext.decode('utf-8'))
        
        return decrypted_data
        
    except Exception as e:
        print(f"❌ Decryption failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("="*80)
    print("🔍 VIYONAPAY CALLBACK DECRYPTION TEST")
    print("="*80)
    
    # You need to provide these from the actual callback
    print("\n⚠️  IMPORTANT: You need to provide the actual values from ViyonaPay callback:")
    print("   1. X-TIMESTAMP header value")
    print("   2. X-Request-Id header value")
    print("   3. Your VIYONAPAY_WEBHOOK_SECRET_KEY from .env")
    print()
    
    # Example AAD (you need to replace with actual values from callback)
    aad = {
        'timestamp': 1234567890,  # Replace with actual X-TIMESTAMP
        'request_id': 'test-request-id'  # Replace with actual X-Request-Id
    }
    
    # Decrypt
    decrypted = decrypt_webhook_response(ENCRYPTED_DATA, WEBHOOK_SECRET_KEY, aad)
    
    if decrypted:
        print("\n📦 Decrypted Payload:")
        print(json.dumps(decrypted, indent=2))
        
        # Extract responseBody
        response_body = decrypted.get('responseBody', {})
        if response_body:
            print("\n📋 Payment Data:")
            print(json.dumps(response_body, indent=2))
            
            order_id = response_body.get('orderId')
            if order_id:
                print(f"\n🔍 Order ID from callback: {order_id}")
                print(f"\n💡 Check if this matches your database:")
                print(f"   - ORDER123456787347238949")
                print(f"   - ORD1776171742669475")
    else:
        print("\n❌ Failed to decrypt callback")
        print("\n💡 Possible issues:")
        print("   1. Wrong webhook secret key")
        print("   2. Wrong timestamp or request_id")
        print("   3. Encrypted data is corrupted")


if __name__ == '__main__':
    main()
