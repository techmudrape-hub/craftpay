import os
import re

file_path = r'c:\Users\USER\Desktop\JAHARVIR INFINET\Orchpay\backend\payout_routes.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Step 1: Revert my previous mistake
content = content.replace(
    "elif pg_partner_upper in ['MAXPE', 'NODEPAY', 'NEXTPAY']:",
    "elif pg_partner_upper in ['MAXPE', 'NODEPAY']:"
)

# Step 2: Inject NEXTPAY blocks after MAXPE blocks
# There are 5 blocks of MAXPE.
# 3 of them are txn_id generation:
#                 elif pg_partner_upper in ['MAXPE', 'NODEPAY']:
#                     txn_id = f"MAXPE_TXN_{uuid.uuid4().hex[:12].upper()}"
txn_id_maxpe = """                elif pg_partner_upper in ['MAXPE', 'NODEPAY']:
                    txn_id = f"MAXPE_TXN_{uuid.uuid4().hex[:12].upper()}\""""

txn_id_nextpay = """                elif pg_partner_upper in ['MAXPE', 'NODEPAY']:
                    txn_id = f"MAXPE_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'NEXTPAY':
                    txn_id = f"NEXTPAY_TXN_{uuid.uuid4().hex[:12].upper()}\""""

content = content.replace(txn_id_maxpe, txn_id_nextpay)


# Step 3: Find the full processing blocks for MAXPE and duplicate for NEXTPAY
# Block 1 (admin_personal_payout) starts with:
#                 elif pg_partner_upper in ['MAXPE', 'NODEPAY']:
#                     # Use MaxPe or NodePay for payout (IMPS) - Direct API call, NO wallet deduction
#                     # Get the appropriate service based on pg_partner
#                     payout_service_instance = get_payout_service(pg_partner_upper)
# And ends before:
#                 elif pg_partner_upper == 'CLOCKSPAY':
# We'll use regex to capture the block.
import re
pattern1 = re.compile(
    r"(                elif pg_partner_upper in \['MAXPE', 'NODEPAY'\]:\n.*?)"
    r"(?=                elif pg_partner_upper == 'CLOCKSPAY':)",
    re.DOTALL
)

def replace_block(match):
    maxpe_block = match.group(1)
    nextpay_block = maxpe_block.replace(
        "elif pg_partner_upper in ['MAXPE', 'NODEPAY']:",
        "elif pg_partner_upper == 'NEXTPAY':"
    )
    nextpay_block = nextpay_block.replace(
        "payout_service_instance = get_payout_service(pg_partner_upper)",
        "payout_service_instance = nextpay_payout_service"
    )
    nextpay_block = nextpay_block.replace(
        "MaxPe or NodePay",
        "Nextpay"
    )
    return maxpe_block + nextpay_block

content = pattern1.sub(replace_block, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Success')
