#!/bin/bash

# Fix .env file with correct RDS credentials

echo "=========================================="
echo "Fixing .env File Credentials"
echo "=========================================="
echo ""

# Backup existing .env
if [ -f ".env" ]; then
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ Backed up existing .env file"
fi

# Get RDS endpoint
echo "Enter your RDS endpoint (e.g., orchpay-db.xxxxx.region.rds.amazonaws.com):"
read -r RDS_ENDPOINT

# Get RDS password
echo "Enter your RDS admin password:"
read -s RDS_PASSWORD
echo ""

# Update .env file
echo "Updating .env file..."

# Update DB_HOST
sed -i "s|^DB_HOST=.*|DB_HOST=$RDS_ENDPOINT|g" .env

# Update DB_USER to admin
sed -i "s|^DB_USER=.*|DB_USER=admin|g" .env

# Update DB_PASSWORD
sed -i "s|^DB_PASSWORD=.*|DB_PASSWORD=$RDS_PASSWORD|g" .env

# Update DB_NAME to orchpay_db
sed -i "s|^DB_NAME=.*|DB_NAME=orchpay_db|g" .env

echo ""
echo "✅ .env file updated successfully!"
echo ""
echo "Updated values:"
echo "  DB_HOST=$RDS_ENDPOINT"
echo "  DB_USER=admin"
echo "  DB_PASSWORD=********"
echo "  DB_NAME=orchpay_db"
echo ""
echo "Testing connection..."
python3 test_db_connection.py
