#!/bin/bash
# Check for multiple copies of mudrape_callback_routes.py

echo "🔍 Searching for mudrape_callback_routes.py files..."
find /var/www/orchpay -name "mudrape_callback_routes.py" -type f

echo ""
echo "🔍 Checking which file is being used by the running process..."
ps aux | grep gunicorn | grep orchpay | head -1

echo ""
echo "🔍 Checking the content of the callback error message..."
grep -n "Missing.*clientTxnId\|Missing.*referenceId" /var/www/orchpay/orchpay/backend/mudrape_callback_routes.py

echo ""
echo "🔍 Checking for __pycache__ directories..."
find /var/www/orchpay/orchpay/backend -type d -name "__pycache__" | head -5
