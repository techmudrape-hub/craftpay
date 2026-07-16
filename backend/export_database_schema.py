#!/usr/bin/env python3
"""Export complete database schema for analysis"""

from config import Config
import pymysql
import json

print("=" * 70)
print("Exporting Database Schema")
print("=" * 70)

try:
    conn = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME
    )
    print(f"✅ Connected to database: {Config.DB_NAME}\n")
    
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SHOW TABLES")
    tables = [table[0] for table in cursor.fetchall()]
    
    print(f"📊 Found {len(tables)} tables\n")
    
    schema = {}
    
    for table in tables:
        print(f"📋 Analyzing table: {table}")
        
        # Get table structure
        cursor.execute(f"DESCRIBE {table}")
        columns = cursor.fetchall()
        
        # Get table indexes
        cursor.execute(f"SHOW INDEX FROM {table}")
        indexes = cursor.fetchall()
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cursor.fetchone()[0]
        
        schema[table] = {
            'columns': [
                {
                    'name': col[0],
                    'type': col[1],
                    'null': col[2],
                    'key': col[3],
                    'default': col[4],
                    'extra': col[5]
                }
                for col in columns
            ],
            'indexes': [
                {
                    'name': idx[2],
                    'column': idx[4],
                    'unique': idx[1] == 0
                }
                for idx in indexes
            ],
            'row_count': row_count
        }
        
        print(f"   - Columns: {len(columns)}")
        print(f"   - Indexes: {len(set(idx[2] for idx in indexes))}")
        print(f"   - Rows: {row_count}\n")
    
    # Save to JSON file
    with open('database_schema.json', 'w') as f:
        json.dump(schema, f, indent=2, default=str)
    
    print("=" * 70)
    print("✅ Schema exported to: database_schema.json")
    print("=" * 70)
    
    # Also create a readable text report
    with open('database_schema_report.txt', 'w') as f:
        f.write("=" * 70 + "\n")
        f.write(f"Database Schema Report: {Config.DB_NAME}\n")
        f.write("=" * 70 + "\n\n")
        
        for table, info in schema.items():
            f.write(f"\nTable: {table}\n")
            f.write("-" * 70 + "\n")
            f.write(f"Rows: {info['row_count']}\n\n")
            
            f.write("Columns:\n")
            for col in info['columns']:
                null_str = "NULL" if col['null'] == 'YES' else "NOT NULL"
                key_str = f" [{col['key']}]" if col['key'] else ""
                default_str = f" DEFAULT {col['default']}" if col['default'] else ""
                extra_str = f" {col['extra']}" if col['extra'] else ""
                f.write(f"  - {col['name']}: {col['type']} {null_str}{key_str}{default_str}{extra_str}\n")
            
            if info['indexes']:
                f.write("\nIndexes:\n")
                unique_indexes = {}
                for idx in info['indexes']:
                    if idx['name'] not in unique_indexes:
                        unique_indexes[idx['name']] = []
                    unique_indexes[idx['name']].append(idx['column'])
                
                for idx_name, columns in unique_indexes.items():
                    f.write(f"  - {idx_name}: ({', '.join(columns)})\n")
            
            f.write("\n")
    
    print("✅ Readable report saved to: database_schema_report.txt")
    print("\n📤 You can now share these files:")
    print("   - database_schema.json (structured data)")
    print("   - database_schema_report.txt (human readable)")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
