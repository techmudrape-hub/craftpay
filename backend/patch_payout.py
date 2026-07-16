import sys
import os
import uuid

file_path = r'c:\Users\USER\Desktop\JAHARVIR INFINET\Orchpay\backend\payout_routes.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Change 1: Import
if 'from nextpay_payout_service import nextpay_payout_service' not in content:
    content = content.replace(
        'from risexpay_payout_service import risexpay_payout_service',
        'from risexpay_payout_service import risexpay_payout_service\nfrom nextpay_payout_service import nextpay_payout_service'
    )

# Replace txn_id generators for NEXTPAY wherever RISEXPAY is present
content = content.replace(
    'elif pg_partner_upper == \'RISEXPAY\':\n                    txn_id = f"RXP_TXN_{uuid.uuid4().hex[:12].upper()}"',
    'elif pg_partner_upper == \'RISEXPAY\':\n                    txn_id = f"RXP_TXN_{uuid.uuid4().hex[:12].upper()}"\n                elif pg_partner_upper == \'NEXTPAY\':\n                    txn_id = f"NEXTPAY_TXN_{uuid.uuid4().hex[:12].upper()}"'
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patch 1 done")
