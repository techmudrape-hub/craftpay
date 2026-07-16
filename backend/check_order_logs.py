#!/usr/bin/env python3
"""
Check callback data and logs for a specific order ID or transaction ID.
Usage: python check_order_logs.py <order_id_or_txn_id>
"""

import sys
import json
import os
import re
import subprocess
from database_pooled import get_db_connection

def dict_to_string(d):
    """Safely convert dict values to strings for printing"""
    out = {}
    for k, v in d.items():
        if isinstance(v, bytes):
            out[k] = "<binary data>"
        else:
            out[k] = str(v)
    return out

def main(search_id):
    # Setup database connection
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
        
    print("="*80)
    print(f"  SEARCHING DATABASE FOR: {search_id}")
    print("="*80)
    
    txn_ids = set()
    
    try:
        with conn.cursor() as cursor:
            # 1. Check payin_transactions
            cursor.execute("""
                SELECT * FROM payin_transactions
                WHERE order_id = %s OR txn_id = %s OR pg_txn_id = %s OR bank_ref_no = %s
            """, (search_id, search_id, search_id, search_id))
            payins = cursor.fetchall()
            
            if payins:
                print("\n[+] PAYIN TRANSACTIONS FOUND:")
                for i, row in enumerate(payins, 1):
                    print(f"\n--- Payin Record #{i} ---")
                    safe_row = dict_to_string(row)
                    for k, v in safe_row.items():
                        print(f"  {k:20s}: {v}")
                    if row.get('txn_id'):
                        txn_ids.add(row.get('txn_id'))
            
            # 2. Check payout_transactions
            cursor.execute("""
                SELECT * FROM payout_transactions
                WHERE order_id = %s OR txn_id = %s OR reference_id = %s OR pg_txn_id = %s OR utr = %s OR bank_ref_no = %s
            """, (search_id, search_id, search_id, search_id, search_id, search_id))
            payouts = cursor.fetchall()
            
            if payouts:
                print("\n[+] PAYOUT TRANSACTIONS FOUND:")
                for i, row in enumerate(payouts, 1):
                    print(f"\n--- Payout Record #{i} ---")
                    safe_row = dict_to_string(row)
                    for k, v in safe_row.items():
                        print(f"  {k:20s}: {v}")
                    if row.get('txn_id'):
                        txn_ids.add(row.get('txn_id'))
            
            # 3. Check callback_logs
            print("\n[+] CALLBACK LOGS:")
            txn_id_list = list(txn_ids)
            query_parts = ["request_data LIKE %s", "response_data LIKE %s", "callback_url LIKE %s", "txn_id = %s"]
            params = [f"%{search_id}%", f"%{search_id}%", f"%{search_id}%", search_id]
            
            if txn_id_list:
                placeholders = ', '.join(['%s'] * len(txn_id_list))
                query_parts.append(f"txn_id IN ({placeholders})")
                params.extend(txn_id_list)
                
            query = f"SELECT * FROM callback_logs WHERE {' OR '.join(query_parts)} ORDER BY created_at DESC"
            cursor.execute(query, tuple(params))
            callbacks = cursor.fetchall()
            
            if callbacks:
                print(f"Found {len(callbacks)} callback log entries.\n")
                for i, row in enumerate(callbacks, 1):
                    print(f"--- Callback Log #{i} (ID: {row['id']}) ---")
                    print(f"Time: {row['created_at']}")
                    print(f"Merchant ID: {row['merchant_id']} | TXN ID: {row['txn_id']}")
                    print(f"Callback URL: {row['callback_url']}")
                    print(f"Response Code: {row['response_code']}")
                    
                    print(f"\nRequest Data:")
                    try:
                        req = json.loads(row['request_data'])
                        print(json.dumps(req, indent=2))
                    except:
                        print(row['request_data'])
                        
                    print(f"\nResponse Data:")
                    try:
                        if row['response_data']:
                            res = json.loads(row['response_data'])
                            print(json.dumps(res, indent=2))
                        else:
                            print("None")
                    except:
                        print(row['response_data'])
                    print("-" * 60)
            else:
                print("No matching callback logs found in database.")
                
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        conn.close()
        
    print("\n" + "="*80)
    print("  SEARCHING LOG FILES (app logs)")
    print("="*80)
    
    # Try searching log files
    log_files = [
        '/var/log/flask.log', 
        '/var/log/app.log', 
        os.path.join(os.path.dirname(__file__), 'app.log'), 
        os.path.join(os.path.dirname(__file__), 'flask.log'),
        'gunicorn.log'
    ]
    found_any_file = False
    
    for lf in log_files:
        if os.path.exists(lf):
            found_any_file = True
            print(f"\nSearching in {lf}...")
            try:
                with open(lf, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    
                relevant = []
                for i, line in enumerate(lines):
                    if search_id in line:
                        # Get some context around the match
                        start = max(0, i - 3)
                        end = min(len(lines), i + 4)
                        
                        # Avoid adding duplicates if matches are close together
                        if relevant and relevant[-1] == "---\n":
                            # Last block just finished, we can just append
                            pass
                        
                        block = lines[start:end]
                        relevant.extend(block)
                        relevant.append("---\n")
                
                if relevant:
                    print(f"Found {len([l for l in relevant if l == '---\\n'])} match blocks in {lf}:")
                    print("".join(relevant))
                else:
                    print("No matches in this file.")
            except Exception as e:
                print(f"Error reading {lf}: {e}")
                
    if not found_any_file:
        print("No local log files found to search.")

    print("\n" + "="*80)
    print("  SEARCHING SYSTEMD JOURNAL (orchpay-api)")
    print("="*80)
    
    try:
        # Check if journalctl is available and we're on linux
        if sys.platform.startswith('linux'):
            cmd = f"sudo journalctl -u orchpay-api --no-pager | grep '{search_id}' -B 3 -A 4"
            print(f"Running: {cmd}\n")
            
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()
            
            if stdout.strip():
                print(f"Found matches in journalctl:")
                print(stdout)
            else:
                if stderr and "sudo: " in stderr:
                    print("Sudo privileges might be required without password, or command failed.")
                    print(f"Error: {stderr.strip()}")
                else:
                    print("No matches found in journalctl.")
        else:
            print(f"System is {sys.platform}. Skipping journalctl search (Linux only).")
            print(f"Command to run manually on the server:")
            print(f"  sudo journalctl -u orchpay-api --no-pager | grep '{search_id}' -B 3 -A 4")
            
    except Exception as e:
        print(f"Failed to query journalctl: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_order_logs.py <order_id_or_txn_id>")
        sys.exit(1)
        
    main(sys.argv[1])
