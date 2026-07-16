"""
Check for syntax errors in Python files
"""

import py_compile
import sys

files_to_check = [
    'razorpay_service.py',
    'razorpay_callback_routes.py',
    'app.py'
]

print("Checking Python syntax...")
print("=" * 80)

errors_found = False

for filename in files_to_check:
    try:
        py_compile.compile(filename, doraise=True)
        print(f"✅ {filename} - OK")
    except py_compile.PyCompileError as e:
        print(f"❌ {filename} - SYNTAX ERROR:")
        print(f"   {e}")
        errors_found = True

print("=" * 80)

if errors_found:
    print("❌ Syntax errors found! Fix them before restarting.")
    sys.exit(1)
else:
    print("✅ All files OK!")
    sys.exit(0)
