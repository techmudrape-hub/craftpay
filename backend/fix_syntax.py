file_path = 'c:/Users/USER/Desktop/JAHARVIR INFINET/Orchpay/backend/payout_routes.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('f\\"SECTORPE_TXN_', 'f"SECTORPE_TXN_')
content = content.replace('upper()}\\"', 'upper()}"')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Syntax fixed.')
