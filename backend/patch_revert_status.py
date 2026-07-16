import re

path = r"c:\Users\USER\Desktop\JAHARVIR INFINET\Orchpay\backend\payout_routes.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace all occurrences in the newly injected blocks
content = content.replace(
    "status = result.get('status', 'QUEUED')",
    "status = result.get('status', 'INITIATED')"
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Status reverted to INITIATED.")
