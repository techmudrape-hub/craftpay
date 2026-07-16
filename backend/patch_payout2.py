import os
import uuid

file_path = r'c:\Users\USER\Desktop\JAHARVIR INFINET\Orchpay\backend\payout_routes.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# For lines like:
# elif pg_partner_upper in ['MAXPE', 'NODEPAY']:
# We need to insert NEXTPAY handling. We will do this by finding the MAXPE block and duplicating it for NEXTPAY,
# but replacing `payout_service_instance = get_payout_service(pg_partner_upper)`
# with `payout_service_instance = nextpay_payout_service`

import re

# Block 1: line 631
# Find the exact text to replace
maxpe_block1 = """                elif pg_partner_upper in ['MAXPE', 'NODEPAY']:
                    # Use MaxPe or NodePay for payout (IMPS) - Direct API call, NO wallet deduction
                    # Get the appropriate service based on pg_partner
                    payout_service_instance = get_payout_service(pg_partner_upper)
                    
                    result = payout_service_instance.call_payout_api("""

nextpay_block1 = """                elif pg_partner_upper == 'NEXTPAY':
                    # Use Nextpay for payout (IMPS)
                    result = nextpay_payout_service.call_payout_api("""

if maxpe_block1 in content:
    content = content.replace(maxpe_block1, nextpay_block1 + maxpe_block1[maxpe_block1.find('('):] + "\n\n" + maxpe_block1)
    # wait, this is hard because we need the entire if/elif body which spans many lines.

# Actually, the simplest way is to dynamically add NEXTPAY where MAXPE is.
# Let's replace:
# elif pg_partner_upper in ['MAXPE', 'NODEPAY']:
# with:
# elif pg_partner_upper in ['MAXPE', 'NODEPAY', 'NEXTPAY']:
# And then update `get_payout_service` in maxpe_payout_service.py to also return nextpay_payout_service!
