import sys
import os
import json
import uuid
from datetime import datetime

# Add the current directory to the sys path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from payu_legalhalt_service import payu_legalhalt_service
from config import Config

def test_payu_legalhalt_payin():
    print("=" * 60)
    print("Testing PayU Legal Halt Payin (UPI Intent S2S)")
    print("=" * 60)
    
    # Ensure config variables are set. If not, mock them for testing purposes.
    # Note: If your .env has the real keys, it will use them automatically.
    print(f"Merchant Key: {Config.PAYU_LEGALHALT_MERCHANT_KEY}")
    print(f"Merchant Salt: {Config.PAYU_LEGALHALT_MERCHANT_SALT}")
    print(f"Base URL: {Config.PAYU_LEGALHALT_BASE_URL}")
    print(f"Test Mode: {Config.PAYU_LEGALHALT_TEST_MODE}")
    print("-" * 60)

    # 1. Fetch a valid active merchant ID from the database
    merchant_id = None
    try:
        from database import get_db_connection
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT merchant_id FROM merchants WHERE is_active = TRUE LIMIT 1")
                row = cursor.fetchone()
                if row:
                    merchant_id = row['merchant_id']
            conn.close()
    except Exception as e:
        print(f"Failed to fetch merchant: {e}")
        
    if not merchant_id:
        print("❌ FAILED: No active merchants found in the database to test with.")
        return
        
    print(f"Using Merchant ID: {merchant_id}")
    # 2. Define Order Data
    unique_order_id = f"test_order_{uuid.uuid4().hex[:8]}"
    order_data = {
        'orderid': unique_order_id,
        'amount': '10.00',  # Test amount in INR
        'productinfo': 'Test UPI Payin',
        'payee_fname': 'John',
        'payee_lname': 'Doe',
        'payee_email': 'johndoe@example.com',
        'payee_mobile': '9999999999',
        'callbackurl': 'https://api.orchpay.com/test-callback'
    }
    
    client_ip = '127.0.0.1'
    device_info = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Test'

    print(f"Initiating Payin Request for Order: {unique_order_id}...")
    
    # 3. Call the Service
    try:
        response = payu_legalhalt_service.create_payin_order(
            merchant_id=merchant_id,
            order_data=order_data,
            client_ip=client_ip,
            device_info=device_info
        )
        
        print("\nResponse from PayU Legal Halt Service:")
        print(json.dumps(response, indent=4))
        
        if response.get('success'):
            print("\n✅ SUCCESS: Intent UPI Link generated.")
            print(f"🔗 UPI Link: {response.get('payment_url')}")
            print("\nYou can convert this link into a QR code or use an anchor tag <a href='...'> to trigger the UPI app on mobile.")
        else:
            print(f"\n❌ FAILED: {response.get('message')}")
            
    except Exception as e:
        print(f"\n❌ Error encountered during execution: {e}")

if __name__ == '__main__':
    test_payu_legalhalt_payin()
