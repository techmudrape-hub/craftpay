#!/usr/bin/env python3
"""
Diagnose ViyonaPay Real Callback Issue
Decrypt the callback and check what order_id ViyonaPay is sending
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64
import json
from config import Config
from database import get_db_connection

# The encrypted data from your real callback
ENCRYPTED_DATA = "DgwgEbfPNU+DYGSDjL5AVZBYXEMe0U6Tq8NL2ANow+1OkYteru1QnjiIL3nDb0j+I4e5yDun4F5aZV45Coyw8BBJHxopVqzCfqPVNGVQ6QO/TEwLt6nmxgu8EnWywIjRzFk9xq67/DJnXmarY09hvaBqSwWGg5j5FMwx8yfBGhc9TZ9EZBoGsobXHX/VKMktWM2xjQZ6LLLNo6e2e6MAQ9Qv/aKrbdSF/0hL1VW3LacrJw2judq9NLwwOaknUQzTjcqvcnfbgIAW5RSF7XC2Bd5/Q5rIPLUmyiTXxWBQ3WiDG0x4RBIsAL+zHp1F0BUGVbmBC7jUfhoKaitGvUXsqQc3p2Vl0+llh9aJtMeBJHH+hB/9j5+U/Av184tIcl3Mm6N2X3ZRIRC1fxzjLpLyYM06s5ibXw4kukzKLxsAF+MR0Kz1UyseypJ62XEiKiZT0mdYM7qbr7m4fptdO7YwVdrYY4KGNNl/RDzuowPy4LoCgCmFwOSlu0U8Un8lNuxK1g8R55KhhNnbfvItiXE1XDtsn3ozxvJpjv14y2MtEYDmH3S8Lsfq"

def decrypt_callback(encrypted_b64, secret_key_hex, timestamp, request_id):
    """Decrypt ViyonaPay callback"""
    try:
        print(f"\n🔓 Decrypting callback...")
        print(f"  Timestamp: {timestamp}")
        print(f"  Request ID: {request_id}")
        
        # Decode base64
        raw = base64.b64decode(encrypted_b64)
        
        # Extract components
        nonce = raw[:12]
        ciphertext = raw[12:]
        
        print(f"  Nonce length: {len(nonce)}")
        print(f"  Ciphertext length: {len(ciphertext)}")
        
        # Convert key
        key16 = bytes.fromhex(secret_key_hex)
        print(f"  Key length: {len(key16)} bytes")
        
        # Prepare AAD
        aad_dict = {
            'timestamp': int(timestamp),
            'request_id': request_id
        }
        aad_json = json.dumps(aad_dict, separators=(',', ':'), sort_keys=True)
        aad_bytes = aad_json.encode('utf-8')
        
        print(f"  AAD: {aad_json}")
        
        # Decrypt
        aesgcm = AESGCM(key16)
        plaintext = aesgcm.decrypt(nonce, ciphertext, aad_bytes)
        
        print(f"✅ Decryption successful!")
        
        return json.loads(plaintext.decode('utf-8'))
        
    except Exception as e:
        print(f"❌ Decryption failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def check_database_for_order(order_id):
    """Check if order exists in database"""
    print(f"\n🔍 Checking database for order_id: {order_id}")
    
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        with conn.cursor() as cursor:
            # Check all payin transactions
            cursor.execute("""
                SELECT txn_id, order_id, pg_partner, status, amount, created_at
                FROM payin_transactions
                WHERE order_id = %s
            """, (order_id,))
            
            txn = cursor.fetchone()
            
            if txn:
                print(f"✅ Transaction FOUND!")
                print(f"  Transaction ID: {txn['txn_id']}")
                print(f"  Order ID: {txn['order_id']}")
                print(f"  PG Partner: {txn['pg_partner']}")
                print(f"  Status: {txn['status']}")
                print(f"  Amount: ₹{txn['amount']}")
                print(f"  Created: {txn['created_at']}")
            else:
                print(f"❌ Transaction NOT FOUND in database")
                print(f"\n📋 Showing recent ViyonaPay transactions:")
                
                cursor.execute("""
                    SELECT txn_id, order_id, pg_partner, status, amount, created_at
                    FROM payin_transactions
                    WHERE pg_partner LIKE '%VIYO%'
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                
                recent = cursor.fetchall()
                if recent:
                    for r in recent:
                        print(f"  - {r['order_id']} | {r['pg_partner']} | {r['status']} | ₹{r['amount']} | {r['created_at']}")
                else:
                    print(f"  No ViyonaPay transactions found")
                    
                print(f"\n📋 Showing ALL recent transactions:")
                cursor.execute("""
                    SELECT txn_id, order_id, pg_partner, status, amount, created_at
                    FROM payin_transactions
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                
                all_recent = cursor.fetchall()
                if all_recent:
                    for r in all_recent:
                        print(f"  - {r['order_id']} | {r['pg_partner']} | {r['status']} | ₹{r['amount']} | {r['created_at']}")
                        
    finally:
        conn.close()


def main():
    print("="*80)
    print("🔍 VIYONAPAY REAL CALLBACK DIAGNOSTIC")
    print("="*80)
    
    print("\n⚠️  You need to provide the X-TIMESTAMP and X-Request-Id from the callback")
    print("    These are in the HTTP headers sent by ViyonaPay")
    print()
    
    # Get input
    timestamp = input("Enter X-TIMESTAMP: ").strip()
    if not timestamp:
        print("❌ Timestamp is required")
        return
    
    request_id = input("Enter X-Request-Id: ").strip()
    if not request_id:
        print("❌ Request ID is required")
        return
    
    # Get webhook secret key
    secret_key = Config.VIYONAPAY_WEBHOOK_SECRET_KEY
    if not secret_key:
        print("❌ VIYONAPAY_WEBHOOK_SECRET_KEY not configured in .env")
        return
    
    print(f"\n📋 Using webhook secret key from .env: {secret_key[:8]}...")
    
    # Decrypt
    decrypted = decrypt_callback(ENCRYPTED_DATA, secret_key, timestamp, request_id)
    
    if not decrypted:
        print("\n❌ Failed to decrypt callback")
        print("\n💡 Possible issues:")
        print("   1. Wrong timestamp or request_id")
        print("   2. Wrong webhook secret key in .env")
        print("   3. Encrypted data is corrupted")
        return
    
    print(f"\n📦 Decrypted Payload:")
    print(json.dumps(decrypted, indent=2))
    
    # Extract responseBody
    response_body = decrypted.get('responseBody', {})
    if not response_body:
        print("\n❌ No responseBody in decrypted data")
        return
    
    print(f"\n📋 Payment Data:")
    print(json.dumps(response_body, indent=2))
    
    # Get order_id
    order_id = response_body.get('orderId')
    if not order_id:
        print("\n❌ No orderId in payment data")
        return
    
    print(f"\n🔑 Order ID from ViyonaPay: {order_id}")
    
    # Check database
    check_database_for_order(order_id)
    
    print(f"\n{'='*80}")
    print("💡 SOLUTION:")
    print(f"{'='*80}")
    print("If the order_id doesn't match what's in your database:")
    print("  1. Check how you're creating the order_id when initiating payment")
    print("  2. Make sure you're storing the EXACT same order_id in payin_transactions")
    print("  3. Check for extra spaces, different formats, etc.")
    print()
    print("If the pg_partner is wrong:")
    print("  1. Make sure you're setting pg_partner = 'VIYONAPAY' when creating transaction")
    print("  2. Not 'VIYONAPAY_BARRINGER' or any other variant")


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
