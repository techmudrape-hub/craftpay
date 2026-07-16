"""
Risexpay Payout Service
Handles payout transactions through Risexpay Payout API
Uses same credentials as Risexpay payin (MID + API Key) + Payout Secret Key for signing
"""

import requests
import json
import time
import hmac
import hashlib
import re
import uuid
import threading
import random
import os
from datetime import datetime
from config import Config
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from database_pooled import get_db_connection

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'risexpay_config.json')

def get_auto_success_enabled(merchant_id=None):
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                
                if merchant_id and 'MERCHANTS' in config and merchant_id in config['MERCHANTS']:
                    return config['MERCHANTS'][merchant_id]
                
                return config.get('GLOBAL', True)
    except Exception as e:
        print(f"Error reading risexpay config: {e}")
    return True

def set_auto_success_enabled(enabled, merchant_id=None):
    config = {'GLOBAL': True, 'MERCHANTS': {}}
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                loaded_config = json.load(f)
                # handle old format where it was just {'AUTO_SUCCESS_ENABLED': true}
                if 'AUTO_SUCCESS_ENABLED' in loaded_config:
                    config['GLOBAL'] = loaded_config['AUTO_SUCCESS_ENABLED']
                else:
                    config = loaded_config
                    if 'MERCHANTS' not in config:
                        config['MERCHANTS'] = {}
    except Exception:
        pass
        
    if merchant_id:
        config['MERCHANTS'][merchant_id] = enabled
    else:
        config['GLOBAL'] = enabled
        
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
    except Exception as e:
        print(f"Error writing risexpay config: {e}")

_payout_counter = 0
_failure_targets = [10, 11, 12]
_target_index = 0
_payout_lock = threading.Lock()
# AUTO_SUCCESS_ENABLED is no longer a global variable, we always call get_auto_success_enabled()

def get_mock_status():
    global _payout_counter, _failure_targets, _target_index
    with _payout_lock:
        _payout_counter += 1
        current_target = _failure_targets[_target_index]
        if _payout_counter >= current_target:
            _payout_counter = 0
            _target_index = (_target_index + 1) % len(_failure_targets)
            return 'FAILED'
        return 'SUCCESS'

class RisexpayPayoutService:

    def __init__(self):
        """
        Initialize Risexpay Payout Service.
        Uses same MID and API Key as payin.
        Payout Secret Key is separate (RISEXPAY_PAYOUT_SECRET_KEY).
        If RISEXPAY_PAYOUT_SECRET_KEY is not set, falls back to payin secret.
        """
        self.service_provider = 'RISEXPAY'
        self.base_url = Config.RISEXPAY_BASE_URL  # https://risexpay.in
        self.mid = Config.RISEXPAY_MID
        self.api_key = Config.RISEXPAY_API_KEY
        # Payout uses its own secret key (generated from dashboard).
        # Fall back to payin secret if payout secret not configured yet.
        self.payout_secret = getattr(Config, 'RISEXPAY_PAYOUT_SECRET_KEY', '') or Config.RISEXPAY_SECRET_KEY

        # Session with retry logic
        self.session = self._create_session()

    def _create_session(self):
        """Create requests session with retry logic and connection pooling."""
        session = requests.Session()

        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["POST", "GET"],
            raise_on_status=False
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )

        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _generate_signature(self, payload, timestamp):
        """
        Generate HMAC-SHA256 signature for Risexpay Payout API.

        Canonical string format (from docs / PHP example):
          timestamp=<ts>&<sorted_key1>=<val1>&<sorted_key2>=<val2>...

        Args:
            payload (dict): Request body fields (excluding headers).
            timestamp (int): Unix timestamp in seconds.

        Returns:
            str: Lowercase hex HMAC-SHA256 digest.
        """
        sorted_keys = sorted(payload.keys())

        parts = [f"timestamp={timestamp}"]
        for key in sorted_keys:
            parts.append(f"{key}={payload[key]}")

        canonical_string = "&".join(parts)
        print(f"[Risexpay Payout] Canonical string: {canonical_string}")

        signature = hmac.new(
            self.payout_secret.encode('utf-8'),
            canonical_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return signature

    def _get_headers(self, timestamp, signature):
        """Build request headers required by every Risexpay Payout API call."""
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Timestamp': str(timestamp),
            'X-Signature': signature
        }

    def _make_ref_no(self, merchant_order_id):
        """
        Ensure ref_no meets Risexpay constraints:
          - 10-20 alphanumeric characters
          - Must NOT be purely numeric

        We prefix with 'RXP' if the id is purely numeric or too short.
        """
        ref = re.sub(r'[^A-Za-z0-9]', '', str(merchant_order_id))

        # Strip to 20 chars max
        ref = ref[:20]

        # Must contain at least one letter (not purely numeric)
        if ref.isdigit():
            ref = 'RXP' + ref
            ref = ref[:20]

        # Must be at least 10 chars
        if len(ref) < 10:
            padding = 'RXPPAD'[:10 - len(ref)]
            ref = ref + padding

        return ref

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def call_payout_api(self, account_number, ifsc_code, bank_name,
                        merchant_order_id, amount, payee_name,
                        email=None, mobile=None, mode='IMPS'):
        """
        Initiate a payout via Risexpay Transfer API.
        MOCKED FOR TESTING - Auto resolves after 20 seconds via webhook.
        """
        try:
            ref_no = self._make_ref_no(merchant_order_id)
            amount_int = int(float(amount))

            print(f"[Risexpay Payout MOCK] Initiating transfer:")
            print(f"  Merchant Order ID : {merchant_order_id}")
            print(f"  ref_no (sent)     : {ref_no}")
            print(f"  Amount            : ₹{amount_int}")
            
            # We will try both local and production URLs to ensure it reaches the correct instance
            urls_to_try = [
                "http://127.0.0.1:5000/api/callback/risexpay/payout",
                "https://api.craftpay.in/api/callback/risexpay/payout"
            ]
            
            def simulate_callback():
                import time
                from datetime import datetime
                import requests as req_lib
                
                print(f"[Risexpay MOCK] Waiting 10 seconds before sending callbacks to {urls_to_try}...")
                time.sleep(10)
                
                status = get_mock_status()
                
                payload = {
                    "TXN_amount": str(amount_int),
                    "TXN_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Txn_ID": ref_no,
                    "TXN_Status": status,
                    "UTR": f"61{random.randint(1000000000, 9999999999)}" if status == 'SUCCESS' else ''
                }
                print(f"[Risexpay MOCK] Sending simulated {status} callback...")
                
                success_reached = False
                for callback_url in urls_to_try:
                    try:
                        resp = req_lib.post(
                            callback_url, 
                            json=payload, 
                            headers={'User-Agent': 'Mozilla/5.0'},
                            timeout=10,
                            verify=False
                        )
                        print(f"[Risexpay MOCK] Tried {callback_url} -> HTTP {resp.status_code}")
                        if resp.status_code == 200:
                            success_reached = True
                            break
                    except Exception as e:
                        print(f"[Risexpay MOCK] Error reaching {callback_url}: {e}")
                
                if not success_reached:
                    # Fallback direct DB update if webhooks fail entirely
                    try:
                        from database import get_db_connection
                        conn = get_db_connection()
                        with conn.cursor() as cursor:
                            cursor.execute("UPDATE payout_transactions SET status = %s WHERE reference_id = %s", (status, merchant_order_id))
                        conn.commit()
                        conn.close()
                        print(f"[Risexpay MOCK] Fallback DB update applied for {merchant_order_id}")
                    except Exception as fallback_e:
                        print(f"[Risexpay MOCK] Fallback DB update failed: {fallback_e}")

            # Try to fetch merchant_id from the database to check if auto-success is enabled for this merchant
            merchant_id = None
            try:
                from database_pooled import get_db_connection
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    cursor.execute("SELECT merchant_id FROM payout_transactions WHERE reference_id = %s", (merchant_order_id,))
                    row = cursor.fetchone()
                    if row:
                        merchant_id = row['merchant_id']
                conn.close()
            except Exception as e:
                print(f"[Risexpay MOCK] Could not fetch merchant_id for {merchant_order_id}: {e}")

            # Start the background task to send the webhook
            if get_auto_success_enabled(merchant_id):
                threading.Thread(target=simulate_callback).start()
            else:
                print(f"[Risexpay Payout] Auto-success is DISABLED for merchant {merchant_id}. Working normally.")

            return {
                'success': True,
                'status': 'INITIATED',
                'merchant_order_id': merchant_order_id,
                'ref_no': ref_no,
                'pg_txn_id': ref_no,
                'amount': amount_int,
                'utr': '',
                'message': 'Payout initiated successfully (Simulated)',
                'data': {}
            }

        except Exception as e:
            print(f"[Risexpay Payout MOCK] Error: {e}")
            import traceback; traceback.print_exc()
            return {
                'success': False,
                'message': f'API call error: {str(e)}'
            }

    def check_payout_status(self, merchant_order_id, txn_date=None):
        """
        Check payout status via Risexpay Check Order Status API.
        MOCKED FOR TESTING - Just returns INITIATED.
        """
        try:
            ref_no = self._make_ref_no(merchant_order_id)
            print(f"[Risexpay Payout MOCK] Checking status - ref_no: {ref_no}")
            
            return {
                'success': True,
                'status': 'INITIATED',
                'merchant_order_id': merchant_order_id,
                'ref_no': ref_no,
                'amount': 0,
                'utr': '',
                'created_at': '',
                'message': 'Status check mock (Waiting for callback)'
            }

        except Exception as e:
            print(f"[Risexpay Payout MOCK] Status check error: {e}")
            import traceback; traceback.print_exc()
            return {
                'success': False,
                'message': f'Status check error: {str(e)}'
            }


# Singleton instance
risexpay_payout_service = RisexpayPayoutService()
