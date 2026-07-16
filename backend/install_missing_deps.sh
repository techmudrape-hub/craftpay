#!/bin/bash

# Install missing Python dependencies

echo "=========================================="
echo "Installing Missing Dependencies"
echo "=========================================="
echo ""

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "❌ Virtual environment not found!"
    echo "   Run: python3 -m venv venv"
    exit 1
fi

echo ""
echo "Installing dependencies..."
echo ""

# Install PyMySQL (for database connection)
pip install PyMySQL

# Install python-dotenv (for .env file)
pip install python-dotenv

# Install Werkzeug (for password hashing)
pip install Werkzeug

echo ""
echo "✅ Dependencies installed successfully!"
echo ""
echo "You can now run:"
echo "  python3 test_db_connection.py"
echo "  python3 migrate_database.py"
echo "  python3 create_orchpay_admin_user.py"
echo ""
