import re

file_path = "c:/Users/USER/Desktop/JAHARVIR INFINET/Orchpay/backend/payout_routes.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# For client_check_payout_status
tpipay_status_logic = """            elif txn['pg_partner'] == 'Tpipay':
                status_result = tpipay_payout_service.check_payout_status(txn['reference_id'])"""

makemypayment_status_logic = tpipay_status_logic + """
            elif txn['pg_partner'] == 'MAKEMYPAYMENT':
                status_result = makemypayment_payout_service.check_payout_status(merchant_reference_id=txn['reference_id'])"""

content = content.replace(tpipay_status_logic, makemypayment_status_logic)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated payout_routes.py successfully for status checks!")
