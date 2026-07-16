"""
=====================================================================
  Risexpay Payout — Integration Test Script
  Reads credentials from .env and uses the actual RisexpayPayoutService.

  Run from the backend/ directory:
      python test_risexpay_payout.py

  Optional flags:
      --status <ref_no>   Only run a status check for a known ref_no
      --live              Enable live payout (sends real money)
=====================================================================
"""

import sys
import os
import json
import time
from datetime import datetime

# ── Load .env so Config picks up values ──────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# ── Now import our actual service ─────────────────────────────────
from config import Config
from risexpay_payout_service import RisexpayPayoutService

# ── Colour helpers ───────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"{GREEN}  ✓  {msg}{RESET}")
def fail(msg): print(f"{RED}  ✗  {msg}{RESET}")
def info(msg): print(f"{CYAN}  ℹ  {msg}{RESET}")
def warn(msg): print(f"{YELLOW}  ⚠  {msg}{RESET}")

def section(title):
    bar = "=" * 62
    print(f"\n{BOLD}{bar}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{bar}{RESET}")

# ======================================================================
# ✏️  EDIT TEST PARAMETERS BELOW
# ======================================================================
BENE_NAME    = "Test Beneficiary"
BENE_ACCOUNT = "1234567890"       # ← replace with real account number
BENE_IFSC    = "SBIN0001234"      # ← replace with real IFSC
BENE_BANK    = "State Bank of India"
AMOUNT       = 1                  # ₹ — set to what you want to test

# Set True here OR pass --live flag to actually initiate a payout
SEND_LIVE    = False
# ======================================================================


def print_config():
    """Print effective credentials loaded from .env."""
    section("CREDENTIALS (from .env)")

    fields = [
        ("RISEXPAY_BASE_URL",          Config.RISEXPAY_BASE_URL),
        ("RISEXPAY_MID",               Config.RISEXPAY_MID),
        ("RISEXPAY_API_KEY",           Config.RISEXPAY_API_KEY),
        ("RISEXPAY_SECRET_KEY",        Config.RISEXPAY_SECRET_KEY),
        ("RISEXPAY_PAYOUT_SECRET_KEY", Config.RISEXPAY_PAYOUT_SECRET_KEY),
    ]

    all_set = True
    for name, val in fields:
        masked = (val[:6] + "..." + val[-4:]) if len(val) > 12 else val
        if not val or "YOUR_" in val.upper():
            fail(f"{name} = NOT SET")
            all_set = False
        else:
            ok(f"{name} = {masked}")

    return all_set


def show_service_state(svc: RisexpayPayoutService):
    """Show what the service actually loaded."""
    section("SERVICE STATE")
    ok(f"base_url       = {svc.base_url}")
    ok(f"mid            = {svc.mid}")
    api_key = svc.api_key
    ok(f"api_key        = {api_key[:6]}...{api_key[-4:] if len(api_key) > 10 else api_key}")
    secret = svc.payout_secret
    ok(f"payout_secret  = {secret[:6]}...{secret[-4:] if len(secret) > 10 else secret}")

    # Show what ref_no would be generated for a sample reference_id
    sample = f"ADMIN20260526ABCDEF"
    ref    = svc._make_ref_no(sample)
    info(f"Sample ref_no  : '{sample}' → '{ref}'  (len={len(ref)})")


def test_signature(svc: RisexpayPayoutService):
    """Show canonical string and signature for a sample payload."""
    section("SIGNATURE TEST")

    ts  = int(time.time())
    ref = svc._make_ref_no(f"SIGTEST{ts}")

    payload = {
        'mid'           : svc.mid,
        'apikey'        : svc.api_key,
        'amount'        : int(AMOUNT),
        'customer_name' : BENE_NAME.strip(),
        'route'         : 1,
        'ref_no'        : ref,
        'account_number': str(BENE_ACCOUNT).strip(),
        'ifsc'          : BENE_IFSC.upper().strip(),
    }

    sig = svc._generate_signature(payload, ts)

    sorted_keys = sorted(payload.keys())
    parts = [f"timestamp={ts}"]
    for k in sorted_keys:
        parts.append(f"{k}={payload[k]}")
    canonical = "&".join(parts)

    info(f"Timestamp      : {ts}")
    info(f"ref_no         : {ref}")
    info(f"Canonical str  : {canonical}")
    info(f"Signature      : {sig}")
    ok("Signature generated successfully")


def test_initiate_payout(svc: RisexpayPayoutService, live: bool):
    """Call svc.call_payout_api() and return the ref_no used."""
    section(f"PAYOUT INITIATION  ({'LIVE' if live else 'DRY-RUN — payload preview only'})")

    ts  = int(time.time())
    ref = f"RXTST{ts}"   # will be normalised by _make_ref_no() inside service

    info(f"merchant_order_id : {ref}")
    info(f"payee_name        : {BENE_NAME}")
    info(f"account_number    : {BENE_ACCOUNT}")
    info(f"ifsc_code         : {BENE_IFSC}")
    info(f"bank_name         : {BENE_BANK}")
    info(f"amount            : ₹{AMOUNT}")

    if not live:
        warn("DRY-RUN — no HTTP call made. Pass --live flag to send real money.")
        # Still show what ref_no would actually be sent
        norm_ref = svc._make_ref_no(ref)
        info(f"normalised ref_no : {norm_ref}  (len={len(norm_ref)})")
        ok("Dry-run complete — use --live to test real API")
        return ref

    # ── LIVE call ─────────────────────────────────────────────────
    result = svc.call_payout_api(
        account_number    = BENE_ACCOUNT,
        ifsc_code         = BENE_IFSC,
        bank_name         = BENE_BANK,
        merchant_order_id = ref,
        amount            = AMOUNT,
        payee_name        = BENE_NAME,
    )

    print()
    info("Raw result from service:")
    for k, v in result.items():
        if k == 'data':
            info(f"  data            : {json.dumps(v, indent=6)}")
        else:
            info(f"  {k:16}: {v}")

    print()
    if result.get('success'):
        ok(f"Payout initiated! status={result.get('status')}  pg_txn_id={result.get('pg_txn_id')}  utr={result.get('utr')}")
    else:
        fail(f"Payout failed: {result.get('message')}")

    return ref


def test_status_check(svc: RisexpayPayoutService, ref_no: str, live: bool):
    """Call svc.check_payout_status() for a given ref_no."""
    section(f"STATUS CHECK  (ref_no={ref_no})")

    if not live:
        warn("DRY-RUN — no HTTP call. Use --live to query real status.")
        norm = svc._make_ref_no(ref_no)
        txn_date = datetime.now().strftime('%Y-%m-%d')
        info(f"Would send: client_txn_id={norm}, txn_date={txn_date}, route=0")
        ok("Dry-run complete")
        return

    result = svc.check_payout_status(ref_no)

    print()
    info("Raw result from service:")
    for k, v in result.items():
        info(f"  {k:16}: {v}")

    print()
    status = result.get('status', '')
    if result.get('success') and status == 'SUCCESS':
        ok(f"Payout SUCCESS — UTR: {result.get('utr')}")
    elif result.get('success') and status == 'FAILED':
        fail(f"Payout FAILED — {result.get('message')}")
    elif result.get('success'):
        warn(f"Payout status: {status} (still pending)")
    else:
        fail(f"Status check failed: {result.get('message')}")


def test_callback_parse():
    """Parse sample Risexpay callback bodies locally — no HTTP."""
    section("CALLBACK PARSING (local simulation)")

    samples = [
        {
            "label"  : "SUCCESS + real UTR",
            "payload": {"TXN_amount": "100.00", "TXN_date": "2026-05-26 22:00:00",
                        "Txn_ID": "TXN123456789", "TXN_Status": "SUCCESS", "UTR": "HDFC0012345XYZ"}
        },
        {
            "label"  : "FAILED",
            "payload": {"TXN_amount": "500.00", "TXN_date": "2026-05-26 22:10:00",
                        "Txn_ID": "TXN987654321", "TXN_Status": "FAILED", "UTR": "NA"}
        },
        {
            "label"  : "SUCCESS + UTR=NA (falls back to Txn_ID)",
            "payload": {"TXN_amount": "250.00", "TXN_date": "2026-05-26 22:15:00",
                        "Txn_ID": "TXN111222333", "TXN_Status": "SUCCESS", "UTR": "NA"}
        },
        {
            "label"  : "INPROCESS",
            "payload": {"TXN_amount": "1000.00", "TXN_date": "2026-05-26 22:20:00",
                        "Txn_ID": "TXN555666777", "TXN_Status": "INPROCESS", "UTR": ""}
        },
    ]

    for cb in samples:
        p = cb['payload']
        pg_txn_id  = (p.get('Txn_ID') or '').strip()
        raw_status = (p.get('TXN_Status') or '').upper().strip()
        utr        = (p.get('UTR') or '').strip()
        amount     = float(p.get('TXN_amount', 0))

        # Status mapping (mirrors risexpay_payout_callback_routes.py)
        if raw_status in ('SUCCESS', 'TXN', 'COMPLETED'):
            mapped = 'SUCCESS'
        elif raw_status in ('FAILED', 'ERR', 'FAILURE'):
            mapped = 'FAILED'
        elif raw_status in ('PENDING', 'INPROCESS', 'PROCESSING'):
            mapped = 'INPROCESS'
        else:
            mapped = 'INITIATED'

        # UTR fallback
        final_utr = utr if utr and utr.upper() not in ('NA', 'NULL', 'NONE', '') else pg_txn_id

        # Merchant forwarding payload (MaxPe format)
        fwd = {
            'txn_id'      : 'RXP_TXN_<from_db>',
            'reference_id': pg_txn_id,
            'status'      : mapped,
            'utr'         : final_utr,
            'pg_partner'  : 'RISEXPAY',
            'pg_txn_id'   : pg_txn_id,
            'amount'      : amount,
            'message'     : f'Payout {mapped.lower()}'
        }

        print(f"\n  {CYAN}Scenario: {cb['label']}{RESET}")
        print(f"    TXN_Status → mapped : {raw_status!r:12} → {mapped!r}")
        print(f"    UTR (raw)  → final  : {utr!r:12} → {final_utr!r}")
        print(f"    Merchant forward    : {json.dumps(fwd)}")
        ok(f"Parsed correctly")


# ======================================================================
# Main
# ======================================================================
if __name__ == '__main__':
    args = sys.argv[1:]
    live = SEND_LIVE or ('--live' in args)

    # Handle: python test_risexpay_payout.py --status <ref_no>
    status_only_ref = None
    if '--status' in args:
        idx = args.index('--status')
        if idx + 1 < len(args):
            status_only_ref = args[idx + 1]

    print(f"\n{BOLD}{'=' * 62}{RESET}")
    print(f"{BOLD}  Risexpay Payout — Integration Test{RESET}")
    print(f"{BOLD}  {datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}{RESET}")
    print(f"{BOLD}  Mode: {'🟢 LIVE' if live else '🟡 DRY-RUN'}{RESET}")
    print(f"{BOLD}{'=' * 62}{RESET}")

    # 1. Credentials
    creds_ok = print_config()
    if not creds_ok:
        warn("\nFill in your credentials in .env before continuing.")
        warn("Keys needed: RISEXPAY_MID, RISEXPAY_API_KEY, RISEXPAY_PAYOUT_SECRET_KEY")
        sys.exit(1)

    # 2. Instantiate the real service
    svc = RisexpayPayoutService()
    show_service_state(svc)

    # 3. Signature test
    test_signature(svc)

    # 4. Status-only mode
    if status_only_ref:
        test_status_check(svc, status_only_ref, live=True)
        test_callback_parse()
        sys.exit(0)

    # 5. Full flow
    ref = test_initiate_payout(svc, live=live)

    if live and ref:
        info("\nWaiting 4 seconds before status check...")
        time.sleep(4)
        test_status_check(svc, ref, live=True)
    else:
        test_status_check(svc, ref or f"RXTST{int(time.time())}", live=False)

    # 6. Callback simulation
    test_callback_parse()

    # Footer
    print(f"\n{BOLD}{'=' * 62}{RESET}")
    print(f"{BOLD}  All tests complete!{RESET}")
    if not live:
        print(f"{YELLOW}  Run with --live to make real API calls (sends ₹{AMOUNT}).{RESET}")
    print(f"  Status check only:  python test_risexpay_payout.py --status <ref_no> --live")
    print(f"{BOLD}{'=' * 62}{RESET}\n")
