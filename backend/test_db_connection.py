#!/usr/bin/env python3
"""
Database Connection Test Script
Tests connection to RDS MySQL database
"""

import pymysql
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database configuration
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')

print("="*60)
print("Database Connection Test")
print("="*60)
print(f"\nConnection Details:")
print(f"Host: {DB_HOST}")
print(f"User: {DB_USER}")
print(f"Database: {DB_NAME}")
print(f"Password: {'*' * len(DB_PASSWORD) if DB_PASSWORD else 'NOT SET'}")
print("\nTesting connection...")
print("-"*60)

try:
    # Attempt connection
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connect_timeout=10
    )
    
    print("\n✅ SUCCESS: Database connection established!")
    print("-"*60)
    
    # Get MySQL version
    cursor = connection.cursor()
    cursor.execute("SELECT VERSION()")
    version = cursor.fetchone()
    print(f"MySQL Version: {version[0]}")
    
    # Get current database
    cursor.execute("SELECT DATABASE()")
    current_db = cursor.fetchone()
    print(f"Current Database: {current_db[0]}")
    
    # List tables
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    print(f"\nTotal Tables: {len(tables)}")
    
    if tables:
        print("\nTables in database:")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"  - {table[0]}: {count} rows")
    else:
        print("\n⚠️  No tables found. Run migration script to create tables.")
    
    cursor.close()
    connection.close()
    
    print("\n" + "="*60)
    print("✅ Connection test completed successfully!")
    print("="*60)
    sys.exit(0)
    
except pymysql.err.OperationalError as e:
    print("\n❌ FAILED: Cannot connect to database")
    print("-"*60)
    print(f"Error Code: {e.args[0]}")
    print(f"Error Message: {e.args[1]}")
    print("\n🔍 Troubleshooting Steps:")
    print("1. Check if RDS instance is running (Status: Available)")
    print("2. Verify RDS endpoint in .env file")
    print("3. Check security group allows port 3306")
    print("4. Ensure EC2 and RDS are in same VPC")
    print("5. Test port connectivity: telnet <RDS_ENDPOINT> 3306")
    print("\n📖 See AWS_EC2_RDS_COMPLETE_DEPLOYMENT_GUIDE.md")
    print("   Section: 'Issue: Cannot Connect to Database'")
    print("="*60)
    sys.exit(1)
    
except pymysql.err.InternalError as e:
    print("\n❌ FAILED: Database error")
    print("-"*60)
    print(f"Error: {e}")
    print("\n🔍 Possible Issues:")
    print("1. Database name is incorrect")
    print("2. Database doesn't exist")
    print("3. User doesn't have permissions")
    print("="*60)
    sys.exit(1)
    
except Exception as e:
    print("\n❌ FAILED: Unexpected error")
    print("-"*60)
    print(f"Error Type: {type(e).__name__}")
    print(f"Error: {e}")
    print("\n🔍 Check:")
    print("1. All environment variables are set correctly")
    print("2. PyMySQL is installed: pip install PyMySQL")
    print("3. .env file exists and is readable")
    print("="*60)
    sys.exit(1)
