#!/bin/bash
# Script to clean Python cache and restart API

echo "🧹 Cleaning Python cache..."
find /var/www/orchpay/orchpay/backend -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find /var/www/orchpay/orchpay/backend -type f -name "*.pyc" -delete 2>/dev/null || true
find /var/www/orchpay/orchpay/backend -type f -name "*.pyo" -delete 2>/dev/null || true

echo "🔄 Restarting orchpay-api service..."
sudo systemctl restart orchpay-api

echo "⏳ Waiting for service to start..."
sleep 3

echo "✅ Checking service status..."
sudo systemctl status orchpay-api --no-pager

echo ""
echo "✅ Done! API restarted with clean cache."
