"""
Add or update merchant callback URL
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def add_merchant_callback(merchant_id, payin_callback_url, payout_callback_url=None):
    """Add or update merchant callback URLs"""
    
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return False
    
    try:
        with conn.cursor() as cursor:
            # Check if merchant exists
            cursor.execute("""
                SELECT merchant_id, full_name FROM merchants WHERE merchant_id = %s
            """, (merchant_id,))
            
            merchant = cursor.fetchone()
            if not merchant:
                print(f"❌ Merchant not found: {merchant_id}")
                return False
            
            print(f"✅ Found merchant: {merchant['full_name']} ({merchant_id})")
            
            # Check if callback entry exists
            cursor.execute("""
                SELECT merchant_id FROM merchant_callbacks WHERE merchant_id = %s
            """, (merchant_id,))
            
            exists = cursor.fetchone()
            
            if exists:
                # Update existing entry
                if payout_callback_url:
                    cursor.execute("""
                        UPDATE merchant_callbacks
                        SET payin_callback_url = %s,
                            payout_callback_url = %s,
                            updated_at = NOW()
                        WHERE merchant_id = %s
                    """, (payin_callback_url, payout_callback_url, merchant_id))
                else:
                    cursor.execute("""
                        UPDATE merchant_callbacks
                        SET payin_callback_url = %s,
                            updated_at = NOW()
                        WHERE merchant_id = %s
                    """, (payin_callback_url, merchant_id))
                
                print(f"✅ Updated callback URLs for merchant {merchant_id}")
            else:
                # Insert new entry
                cursor.execute("""
                    INSERT INTO merchant_callbacks (merchant_id, payin_callback_url, payout_callback_url, created_at, updated_at)
                    VALUES (%s, %s, %s, NOW(), NOW())
                """, (merchant_id, payin_callback_url, payout_callback_url))
                
                print(f"✅ Added callback URLs for merchant {merchant_id}")
            
            conn.commit()
            
            # Verify
            cursor.execute("""
                SELECT payin_callback_url, payout_callback_url
                FROM merchant_callbacks
                WHERE merchant_id = %s
            """, (merchant_id,))
            
            result = cursor.fetchone()
            print(f"\n📋 Current Configuration:")
            print(f"  Payin Callback URL: {result['payin_callback_url']}")
            print(f"  Payout Callback URL: {result['payout_callback_url'] if result['payout_callback_url'] else 'NOT SET'}")
            
            return True
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 80)
    print("ADD/UPDATE MERCHANT CALLBACK URL")
    print("=" * 80)
    
    # Get merchant ID
    print("\nEnter Merchant ID: ", end='')
    merchant_id = input().strip()
    
    if not merchant_id:
        print("❌ Merchant ID is required")
        sys.exit(1)
    
    # Get payin callback URL
    print("Enter Payin Callback URL: ", end='')
    payin_callback_url = input().strip()
    
    if not payin_callback_url:
        print("❌ Payin Callback URL is required")
        sys.exit(1)
    
    # Get payout callback URL (optional)
    print("Enter Payout Callback URL (optional, press Enter to skip): ", end='')
    payout_callback_url = input().strip()
    
    if not payout_callback_url:
        payout_callback_url = None
    
    print()
    
    # Add/update callback
    success = add_merchant_callback(merchant_id, payin_callback_url, payout_callback_url)
    
    if success:
        print("\n✅ SUCCESS - Merchant callback URL configured")
        print("\n💡 Next Steps:")
        print("   1. Test with a new transaction")
        print("   2. Check callback logs after transaction completes")
        print("   3. Run: python diagnose_clockspay_callback.py")
    else:
        print("\n❌ FAILED - Could not configure callback URL")
    
    print("=" * 80)
