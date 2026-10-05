"""
=============================================================================
 MaxPe PayIn - COMPLETE TEST SCRIPT
 Full Request / Response Logging for Every API Call
=============================================================================

 Tests Covered:
   1. Create Payment Order  (POST /api/prod/payin/create-payment)
   2. Check Payment Status  (POST /api/prod/payin1/status)
   3. Simulate Callback     (POST /api/callback/maxpe/payin)
   4. Signature Validation  (verify HMAC-SHA256 generation)
   5. Error / Edge Cases    (invalid signature, bad order ID)

 Prerequisites:
   pip install requests python-dotenv
   Ensure backend/.env has MAXPE_BASE_URL, MAXPE_API_KEY, MAXPE_API_SECRET

 Usage:
   cd backend
   python test_maxpe_payin_complete.py
=============================================================================
"""

import requests
import json
import time
import hmac
import hashlib
import uuid
import traceback
from datetime import datetime
import os
from dotenv import load_dotenv

# Load env
load_dotenv()

# ─────────────────────────────────────────────
#  ANSI colours
# ─────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    GREEN   = "\033[92m"
    RED     = "\033[91m"
    YELLOW  = "\033[93m"
    CYAN    = "\033[96m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    WHITE   = "\033[97m"

def ok(msg):   print(f"{C.GREEN}[PASS] {msg}{C.RESET}")
def fail(msg): print(f"{C.RED}[FAIL] {msg}{C.RESET}")
def warn(msg): print(f"{C.YELLOW}[WARN] {msg}{C.RESET}")
def info(msg): print(f"{C.CYAN}[INFO] {msg}{C.RESET}")

def header(msg):
    border = "=" * 80
    print(f"\n{C.BLUE}{C.BOLD}{border}{C.RESET}")
    print(f"{C.BLUE}{C.BOLD}  {msg}{C.RESET}")
    print(f"{C.BLUE}{C.BOLD}{border}{C.RESET}")

def section(msg):
    print(f"\n{C.MAGENTA}{'─' * 60}{C.RESET}")
    print(f"{C.MAGENTA}{C.BOLD}  {msg}{C.RESET}")
    print(f"{C.MAGENTA}{'─' * 60}{C.RESET}")

def print_request(method, url, headers, payload, payload_type="JSON"):
    section(f"REQUEST  {method}  {url}")
    print(f"{C.WHITE}{C.BOLD}Headers:{C.RESET}")
    for k, v in headers.items():
        if k in ("X-API-KEY", "X-SIGNATURE"):
            display_val = v[:10] + "..." + v[-6:] if len(v) > 20 else v
        else:
            display_val = v
        print(f"  {C.CYAN}{k}{C.RESET}: {display_val}")
    print(f"\n{C.WHITE}{C.BOLD}Payload ({payload_type}):{C.RESET}")
    if isinstance(payload, dict):
        print(json.dumps(payload, indent=4, default=str))
    else:
        print(payload)

def print_response(status_code, elapsed, headers, body):
    section(f"RESPONSE  HTTP {status_code}  ({elapsed:.3f}s)")
    color = C.GREEN if 200 <= status_code < 300 else C.RED
    print(f"{color}{C.BOLD}Status Code: {status_code}{C.RESET}")
    print(f"{C.WHITE}{C.BOLD}Response Headers:{C.RESET}")
    for k, v in dict(headers).items():
        print(f"  {C.CYAN}{k}{C.RESET}: {v}")
    print(f"\n{C.WHITE}{C.BOLD}Response Body:{C.RESET}")
    try:
        parsed = json.loads(body)
        print(json.dumps(parsed, indent=4, default=str))
    except Exception:
        print(body[:2000] if len(body) > 2000 else body)

# ─────────────────────────────────────────────
#  Config / Credentials
# ─────────────────────────────────────────────
BASE_URL   = os.getenv("MAXPE_BASE_URL",   "https://merchant.maxpe.tech")
API_KEY    = os.getenv("MAXPE_API_KEY",    "")
API_SECRET = os.getenv("MAXPE_API_SECRET", "")
BACKEND_URL= os.getenv("BACKEND_URL",      "http://localhost:5000")

if not API_KEY or not API_SECRET:
    print(f"{C.RED}ERROR: MAXPE_API_KEY and MAXPE_API_SECRET must be set in .env{C.RESET}")
    exit(1)

# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────
def generate_nonce():
    return uuid.uuid4().hex[:16]

def generate_signature(data_to_sign):
    sorted_keys    = sorted(data_to_sign.keys())
    canonical_parts= [f"{k}={data_to_sign[k]}" for k in sorted_keys]
    canonical_str  = "&".join(canonical_parts)
    print(f"\n{C.YELLOW}[Signature]{C.RESET}")
    print(f"  Canonical String : {canonical_str}")
    sig = hmac.new(
        API_SECRET.encode("utf-8"),
        canonical_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    print(f"  Generated Sig    : {sig[:24]}...{sig[-8:]}")
    return sig

def payin_headers(timestamp, nonce, signature):
    return {
        "Content-Type": "application/json",
        "Accept":       "application/json",
        "X-API-KEY":    API_KEY,
        "X-TIMESTAMP":  str(timestamp),
        "X-NONCE":      nonce,
        "X-SIGNATURE":  signature,
    }

def status_headers():
    return {"X-API-KEY": API_KEY}

# ─────────────────────────────────────────────
#  Test Results tracker
# ─────────────────────────────────────────────
results = []

def record(name, passed, note=""):
    results.append({"name": name, "passed": passed, "note": note})
    if passed:
        ok(f"{name}  [{note}]")
    else:
        fail(f"{name}  [{note}]")

# ═══════════════════════════════════════════
#  TEST 1: Signature Generation
# ═══════════════════════════════════════════
def test_signature_generation():
    header("TEST 1: Signature Generation (Unit Test)")
    sample = {
        "amount":            "100.00",
        "email":             "test@example.com",
        "merchant_order_id": "ORDER_001",
        "mobile":            "9876543210",
        "name":              "Test User",
        "nonce":             "abcdef1234567890",
        "timestamp":         "1700000000",
    }
    sig    = generate_signature(sample)
    passed = len(sig) == 64 and all(c in "0123456789abcdef" for c in sig)
    record("Signature Generation", passed, f"64-char hex={'YES' if passed else 'NO'}")
    return passed

# ═══════════════════════════════════════════
#  TEST 2: Create Payment Order
# ═══════════════════════════════════════════
def test_create_payment_order(amount=100.00):
    header(f"TEST 2: Create Payment Order  (Rs {amount})")

    merchant_order_id = f"TEST_MAXPE_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    timestamp = int(time.time())
    nonce     = generate_nonce()

    customer = {
        "name":   "Craftpay Test User",
        "mobile": "9876543210",
        "email":  "testuser@craftpay.in",
    }

    # MaxPe requires amount as a whole number in rupees (no decimals)
    amount_str = str(int(amount))

    data_to_sign = {
        "amount":            amount_str,
        "email":             customer["email"],
        "merchant_order_id": merchant_order_id,
        "mobile":            customer["mobile"],
        "name":              customer["name"],
        "nonce":             nonce,
        "payer_vpa":         "testuser@okaxis",
        "timestamp":         str(timestamp),
    }
    signature = generate_signature(data_to_sign)

    payload = {
        "name":             customer["name"],
        "mobile":           customer["mobile"],
        "email":            customer["email"],
        "amount":           amount_str,
        "payer_vpa":        "testuser@okaxis",
        "merchant_order_id": merchant_order_id,
    }

    url     = f"{BASE_URL}/api/prod/payin/v1/create-payment"
    headers = payin_headers(timestamp, nonce, signature)

    print_request("POST", url, headers, payload)

    start = time.time()
    try:
        resp    = requests.post(url, headers=headers, json=payload, timeout=(15, 120))
        elapsed = time.time() - start
        print_response(resp.status_code, elapsed, resp.headers, resp.text)

        if resp.status_code in (200, 201):
            body = resp.json()
            if body.get("status"):
                upi = body.get("upi_deeplink", body.get("payment_url", ""))
                print(f"\n{C.GREEN}  UPI DeepLink: {upi}{C.RESET}")
                record("Create Payment Order", True, f"order={merchant_order_id} time={elapsed:.2f}s")
                return {"success": True, "merchant_order_id": merchant_order_id, "upi_deeplink": upi, "elapsed": elapsed, "response": body}
            else:
                record("Create Payment Order", False, body.get("message", "status=false"))
        else:
            record("Create Payment Order", False, f"HTTP {resp.status_code}")
    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        warn(f"TIMEOUT after {elapsed:.2f}s - transaction may still be created on MaxPe side")
        record("Create Payment Order", False, f"TIMEOUT {elapsed:.2f}s")
        return {"success": False, "error": "TIMEOUT", "merchant_order_id": merchant_order_id, "elapsed": elapsed}
    except Exception as exc:
        fail(str(exc))
        traceback.print_exc()
        record("Create Payment Order", False, str(exc))

    return {"success": False, "merchant_order_id": merchant_order_id}

# ═══════════════════════════════════════════
#  TEST 3: Check Payment Status
# ═══════════════════════════════════════════
def test_check_status(merchant_order_id):
    header(f"TEST 3: Check Payment Status  ({merchant_order_id})")

    url     = f"{BASE_URL}/api/prod/payin/v1/status"
    headers = status_headers()
    payload = {"merchant_order_id": merchant_order_id}

    print_request("POST", url, headers, payload, payload_type="FORM-DATA")
    info("Status endpoint uses form-data (not JSON) with only X-API-KEY header")

    start = time.time()
    try:
        resp    = requests.post(url, headers=headers, data=payload, timeout=(10, 60))
        elapsed = time.time() - start
        print_response(resp.status_code, elapsed, resp.headers, resp.text)

        if resp.status_code in (200, 201):
            body = resp.json()
            if body.get("status"):
                data   = body.get("data", {})
                txn_st = data.get("transaction_status", "PENDING").upper()
                print(f"\n  Transaction Status : {C.BOLD}{txn_st}{C.RESET}")
                print(f"  Merchant Order ID  : {data.get('merchant_order_id', merchant_order_id)}")
                print(f"  Amount             : Rs {data.get('amount', 'N/A')}")
                print(f"  UTR                : {data.get('utr', 'N/A')}")
                print(f"  Created At         : {data.get('created_at', 'N/A')}")
                record("Check Payment Status", True, f"status={txn_st} order={merchant_order_id}")
                return {"success": True, "status": txn_st, "data": data}
            else:
                record("Check Payment Status", False, body.get("message", "status=false"))
        else:
            record("Check Payment Status", False, f"HTTP {resp.status_code}")
    except Exception as exc:
        fail(str(exc))
        traceback.print_exc()
        record("Check Payment Status", False, str(exc))

    return {"success": False}

# ═══════════════════════════════════════════
#  TEST 4: Invalid Order ID Error Handling
# ═══════════════════════════════════════════
def test_invalid_order_status():
    header("TEST 4: Status Check with Invalid Order ID")

    fake_id = f"INVALID_ORDER_{uuid.uuid4().hex[:8].upper()}"
    url     = f"{BASE_URL}/api/prod/payin/v1/status"
    headers = status_headers()
    payload = {"merchant_order_id": fake_id}

    print_request("POST", url, headers, payload, payload_type="FORM-DATA")
    info(f"Sending invalid order id: {fake_id}")

    start = time.time()
    try:
        resp    = requests.post(url, headers=headers, data=payload, timeout=(10, 60))
        elapsed = time.time() - start
        print_response(resp.status_code, elapsed, resp.headers, resp.text)

        if resp.status_code in (200, 201):
            body = resp.json()
            if not body.get("status"):
                record("Invalid Order Error Handling", True, f"Correctly returned status=false in {elapsed:.2f}s")
            else:
                record("Invalid Order Error Handling", False, "status=true for fake order (unexpected)")
        elif resp.status_code in (400, 404, 422):
            record("Invalid Order Error Handling", True, f"HTTP {resp.status_code} for fake order")
        else:
            record("Invalid Order Error Handling", True, f"HTTP {resp.status_code} (non-2xx = rejected)")
    except Exception as exc:
        fail(str(exc))
        traceback.print_exc()
        record("Invalid Order Error Handling", False, str(exc))

# ═══════════════════════════════════════════
#  TEST 5: Invalid Signature Rejection
# ═══════════════════════════════════════════
def test_invalid_signature():
    header("TEST 5: Create Order with Invalid Signature")

    merchant_order_id = f"BAD_SIG_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    timestamp         = int(time.time())
    nonce             = generate_nonce()

    payload = {
        "name":              "Bad Sig User",
        "mobile":            "9876543210",
        "email":             "badsig@craftpay.in",
        "amount":            "50.00",
        "payer_vpa":         "badsig@okaxis",
        "merchant_order_id": merchant_order_id,
    }

    bad_signature = "0" * 64
    headers       = payin_headers(timestamp, nonce, bad_signature)
    url           = f"{BASE_URL}/api/prod/payin/create-payment"

    print_request("POST", url, headers, payload)
    warn("Using a deliberately invalid signature - expecting API to reject it")

    start = time.time()
    try:
        resp    = requests.post(url, headers=headers, json=payload, timeout=(15, 60))
        elapsed = time.time() - start
        print_response(resp.status_code, elapsed, resp.headers, resp.text)

        if resp.status_code in (401, 403):
            record("Invalid Signature Rejection", True, f"HTTP {resp.status_code} - correctly rejected")
        elif resp.status_code in (200, 201):
            body = resp.json()
            if not body.get("status"):
                record("Invalid Signature Rejection", True, "status=false for bad sig (acceptable)")
            else:
                record("Invalid Signature Rejection", False, "API accepted invalid signature (security issue)")
        else:
            record("Invalid Signature Rejection", True, f"HTTP {resp.status_code} (non-2xx = rejected)")
    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        record("Invalid Signature Rejection", False, f"Timeout {elapsed:.2f}s")
    except Exception as exc:
        fail(str(exc))
        traceback.print_exc()
        record("Invalid Signature Rejection", False, str(exc))

# ═══════════════════════════════════════════
#  TEST 6: Simulate Callback to Your Backend
# ═══════════════════════════════════════════
def test_simulate_callback(merchant_order_id="DEMO_ORDER_001"):
    header(f"TEST 6: Simulate MaxPe Callback to Your Backend")

    callback_url = f"{BACKEND_URL}/api/callback/maxpe/payin"
    callback_payload = {
        "status": "SUCCESS",
        "transaction_details": {
            "amount":             "100.00",
            "merchant_order_id":  merchant_order_id,
            "utr":                "608919646598",
            "created_at":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "transaction_status": "SUCCESS",
        }
    }
    headers = {"Content-Type": "application/json"}

    print_request("POST", callback_url, headers, callback_payload)
    info(f"Simulating MaxPe -> your backend callback for order: {merchant_order_id}")

    start = time.time()
    try:
        resp    = requests.post(callback_url, headers=headers, json=callback_payload, timeout=(5, 30))
        elapsed = time.time() - start
        print_response(resp.status_code, elapsed, resp.headers, resp.text)

        if resp.status_code in (200, 201):
            record("Callback Simulation (Your Backend)", True, f"HTTP {resp.status_code} in {elapsed:.2f}s")
        else:
            record("Callback Simulation (Your Backend)", False, f"HTTP {resp.status_code}")
    except requests.exceptions.ConnectionError:
        warn(f"Could not reach backend at {BACKEND_URL} - is the server running?")
        record("Callback Simulation (Your Backend)", False, f"Connection refused to {BACKEND_URL}")
    except Exception as exc:
        fail(str(exc))
        traceback.print_exc()
        record("Callback Simulation (Your Backend)", False, str(exc))

# ═══════════════════════════════════════════
#  TEST 7: Full Flow
# ═══════════════════════════════════════════
def test_full_flow(amount=100.00, wait_seconds=30):
    header(f"TEST 7: Full Flow (Create -> Wait {wait_seconds}s -> Status)")

    create_result     = test_create_payment_order(amount=amount)
    merchant_order_id = create_result.get("merchant_order_id")

    if create_result.get("success"):
        upi = create_result.get("upi_deeplink", "")
        print(f"\n{C.GREEN}  UPI DeepLink: {upi}{C.RESET}")
        print(f"  Open this on your phone to complete payment")
    else:
        if create_result.get("error") == "TIMEOUT":
            warn("Order may have been created despite timeout")
        else:
            fail("Order creation failed - aborting full flow")
            return

    print(f"\n{C.CYAN}Waiting {wait_seconds}s before status check ...{C.RESET}")
    try:
        for i in range(wait_seconds, 0, -1):
            print(f"\r  {i:3d}s remaining ...", end="", flush=True)
            time.sleep(1)
        print()
    except KeyboardInterrupt:
        print("\n  (wait skipped)")

    if merchant_order_id:
        test_check_status(merchant_order_id)

# ═══════════════════════════════════════════
#  SUMMARY TABLE
# ═══════════════════════════════════════════
def print_summary():
    header("TEST SUMMARY")
    total  = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    rate   = (passed / total * 100) if total else 0

    print(f"\n{'Test Name':<45} {'Result':<8} {'Notes'}")
    print("─" * 90)
    for r in results:
        status_str = "PASS" if r["passed"] else "FAIL"
        color      = C.GREEN if r["passed"] else C.RED
        print(f"{r['name']:<45} {color}{C.BOLD}{status_str}{C.RESET:<8}  {r['note'][:40]}")
    print("─" * 90)
    print(f"\nTotal  : {total}")
    print(f"{C.GREEN}Passed : {passed}{C.RESET}")
    print(f"{C.RED}Failed : {failed}{C.RESET}")
    print(f"Rate   : {C.BOLD}{rate:.1f}%{C.RESET}")
    if rate == 100:
        print(f"\n{C.GREEN}{C.BOLD}ALL TESTS PASSED!{C.RESET}")
    elif rate >= 75:
        print(f"\n{C.YELLOW}{C.BOLD}MOSTLY PASSING - review failed tests{C.RESET}")
    else:
        print(f"\n{C.RED}{C.BOLD}MULTIPLE FAILURES - check credentials and API{C.RESET}")

# ═══════════════════════════════════════════
#  RUN ALL (automated)
# ═══════════════════════════════════════════
def run_all():
    print(f"\n{C.BLUE}{C.BOLD}== MaxPe PayIn Complete Test Suite =={C.RESET}")
    print(f"  Base URL   : {BASE_URL}")
    print(f"  API Key    : {API_KEY[:12]}...{API_KEY[-6:]}")
    print(f"  Time       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    test_signature_generation()
    test_invalid_signature()

    create_result = test_create_payment_order(amount=10.00)
    mid = create_result.get("merchant_order_id", "UNKNOWN")

    test_invalid_order_status()

    print(f"\n{C.CYAN}Waiting 10s before status check ...{C.RESET}")
    for i in range(10, 0, -1):
        print(f"\r  {i:2d}s", end="", flush=True)
        time.sleep(1)
    print()

    test_check_status(mid)
    test_simulate_callback(merchant_order_id=mid)
    print_summary()

# ═══════════════════════════════════════════
#  MAIN MENU
# ═══════════════════════════════════════════
def main():
    print(f"\n{C.BLUE}{C.BOLD}{'='*80}{C.RESET}")
    print(f"{C.BLUE}{C.BOLD}  MaxPe PayIn - Complete Test Script{C.RESET}")
    print(f"{C.BLUE}{C.BOLD}{'='*80}{C.RESET}")
    print(f"  Base URL   : {BASE_URL}")
    print(f"  API Key    : {API_KEY[:12]}...{API_KEY[-6:]}")
    print(f"  Backend URL: {BACKEND_URL}")
    print(f"  Test Time  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print("""
Select a test:
  1  - Signature Generation    (unit test, no network)
  2  - Create Payment Order    (live call to MaxPe)
  3  - Check Payment Status    (requires merchant_order_id)
  4  - Invalid Order Error     (error edge case)
  5  - Invalid Signature       (security check)
  6  - Simulate Callback       (tests your /api/callback/maxpe/payin)
  7  - Full Flow               (Create -> Wait -> Status)
  A  - Run ALL tests
""")
    choice = input("Enter choice (1-7 / A): ").strip().upper()

    if choice == "1":
        test_signature_generation()
        print_summary()
    elif choice == "2":
        try:
            amt = float(input("Amount (default 100.00): ").strip() or "100.00")
        except ValueError:
            amt = 100.00
        test_create_payment_order(amount=amt)
        print_summary()
    elif choice == "3":
        oid = input("Merchant Order ID: ").strip()
        if not oid:
            fail("merchant_order_id is required")
            return
        test_check_status(oid)
        print_summary()
    elif choice == "4":
        test_invalid_order_status()
        print_summary()
    elif choice == "5":
        test_invalid_signature()
        print_summary()
    elif choice == "6":
        default_oid = f"TEST_MAXPE_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        oid = input(f"Merchant Order ID (default: {default_oid}): ").strip() or default_oid
        test_simulate_callback(merchant_order_id=oid)
        print_summary()
    elif choice == "7":
        try:
            amt  = float(input("Amount (default 100.00): ").strip() or "100.00")
        except ValueError:
            amt  = 100.00
        try:
            wait = int(input("Wait seconds (default 30): ").strip() or "30")
        except ValueError:
            wait = 30
        test_full_flow(amount=amt, wait_seconds=wait)
        print_summary()
    elif choice == "A":
        run_all()
    else:
        fail(f"Invalid choice: {choice}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}Test interrupted by user{C.RESET}")
        print_summary()
    except Exception as e:
        fail(f"Fatal error: {e}")
        traceback.print_exc()
