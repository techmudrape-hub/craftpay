import re

path = r"c:\Users\USER\Desktop\JAHARVIR INFINET\Orchpay\backend\payout_routes.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Fix admin_bulk_payout (around line 1176)
target1 = """                    if result['success']:
                        status = result.get('status', 'QUEUED')
                        pg_txn_id_resp = result.get('pg_txn_id', '')
                        utr = result.get('utr', '')
                        print(f"Risexpay payout initiated - Status: {status}, PG Txn ID: {pg_txn_id_resp}, Merchant Order ID: {reference_id}")
                    else:"""
replacement1 = """                    if result['success']:
                        status = result.get('status', 'QUEUED')
                        pg_txn_id_resp = result.get('pg_txn_id', '')
                        utr = result.get('utr', '')
                        print(f"Risexpay payout initiated - Status: {status}, PG Txn ID: {pg_txn_id_resp}, Merchant Order ID: {reference_id}")
                        
                        cursor.execute(\"\"\"
                            UPDATE payout_transactions 
                            SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                            WHERE reference_id = %s
                        \"\"\", (status, pg_txn_id_resp, utr, reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'reference_id': reference_id,
                            'status': status
                        }), 200
                    else:"""
content = content.replace(target1, replacement1)

# 2. Fix settle_fund (around line 2558)
target2 = """                    if result['success']:
                        status = result.get('status', 'QUEUED')
                        pg_txn_id_resp = result.get('pg_txn_id', '')
                        utr = result.get('utr', '')
                    else:"""
replacement2 = """                    if result['success']:
                        status = result.get('status', 'QUEUED')
                        pg_txn_id_resp = result.get('pg_txn_id', '')
                        utr = result.get('utr', '')
                        
                        cursor.execute(\"\"\"
                            UPDATE payout_transactions 
                            SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        \"\"\", (status, pg_txn_id_resp, utr, txn_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': True,
                            'message': 'Settlement initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'requested_amount': amount_to_bank,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_wallet_deduction,
                            'status': status
                        }), 200
                    else:"""
content = content.replace(target2, replacement2)

# 3. Fix client_direct_payout (around line 4740)
target3 = """                    if result['success']:
                        status = result.get('status', 'QUEUED')
                        pg_txn_id_resp = result.get('pg_txn_id', '')
                        utr = result.get('utr', '')
                        print(f"Risexpay payout initiated - Status: {status}, PG Txn ID: {pg_txn_id_resp}, Merchant Order ID: {reference_id}")
                    else:"""
replacement3 = """                    if result['success']:
                        status = result.get('status', 'QUEUED')
                        pg_txn_id_resp = result.get('pg_txn_id', '')
                        utr = result.get('utr', '')
                        print(f"Risexpay payout initiated - Status: {status}, PG Txn ID: {pg_txn_id_resp}, Merchant Order ID: {reference_id}")
                        
                        cursor.execute(\"\"\"
                            UPDATE payout_transactions 
                            SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        \"\"\", (status, pg_txn_id_resp, utr, txn_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'requested_amount': net_amount_to_bank,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_wallet_deduction,
                            'status': status
                        }), 200
                    else:"""
# Using string replace with count=1 in case of duplicates (though there shouldn't be for target3 as it was injected once)
parts = content.split(target3)
if len(parts) > 1:
    content = parts[0] + replacement3 + target3.join(parts[1:])

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied.")
