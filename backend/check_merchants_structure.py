#!/usr/bin/env python3
"""Check merchants table structure"""

import pymysql
from config import Config

try:
    connection = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )
    
    with connection.cursor() as cursor:
        cursor.execute("DESCRIBE merchants")
        columns = cursor.fetchall()
        
        print("\n" + "=" * 60)
        print("Merchants Table Structure")
        print("=" * 60)
        for col in columns:
            print(f"{col['Field']:30} {col['Type']:20} {col['Null']:5} {col['Key']:5}")
        print("=" * 60)
        
        cursor.execute("DESCRIBE merchant_banks")
        columns = cursor.fetchall()
        
        print("\n" + "=" * 60)
        print("Merchant Banks Table Structure")
        print("=" * 60)
        for col in columns:
            print(f"{col['Field']:30} {col['Type']:20} {col['Null']:5} {col['Key']:5}")
        print("=" * 60)
        
    connection.close()
except Exception as e:
    print(f"Error: {e}")
