#!/usr/bin/env python3
"""
Check wallet table name
"""

import pymysql
from config import Config

def check_wallet_table():
    """Check what wallet-related tables exist"""
    try:
        connection = pymysql.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            # Get all tables
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            print("All tables in database:")
            print("=" * 80)
            wallet_tables = []
            for table in tables:
                table_name = list(table.values())[0]
                print(f"  {table_name}")
                if 'wallet' in table_name.lower():
                    wallet_tables.append(table_name)
            
            print("\n" + "=" * 80)
            print(f"\nWallet-related tables found: {len(wallet_tables)}")
            for wt in wallet_tables:
                print(f"  ✅ {wt}")
                
                # Show structure
                cursor.execute(f"DESCRIBE {wt}")
                columns = cursor.fetchall()
                print(f"\n  Columns in {wt}:")
                for col in columns:
                    print(f"    - {col['Field']} ({col['Type']})")
                print()
            
            if not wallet_tables:
                print("\n❌ No wallet tables found!")
                print("\nSearching for merchant balance columns in other tables...")
                
                # Check merchants table
                cursor.execute("DESCRIBE merchants")
                merchant_cols = cursor.fetchall()
                print("\nMerchants table columns:")
                for col in merchant_cols:
                    if 'balance' in col['Field'].lower() or 'wallet' in col['Field'].lower():
                        print(f"  ✅ {col['Field']} ({col['Type']})")
        
        connection.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    check_wallet_table()
