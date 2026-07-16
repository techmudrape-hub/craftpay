"""
Diagnose Singapore Timezone Issue
Check actual timestamps and timezone handling
"""

from database import get_db_connection
from datetime import datetime, timedelta
import pytz

def diagnose_timezone_issue():
    """Check timezone configuration and recent transactions"""
    
    print("=" * 70)
    print("TIMEZONE DIAGNOSTIC TOOL")
    print("=" * 70)
    print()
    
    # 1. Check Python timezone
    print("1. PYTHON TIMEZONE INFO:")
    print("-" * 70)
    now_naive = datetime.now()
    now_utc = datetime.now(pytz.UTC)
    now_ist = datetime.now(pytz.timezone('Asia/Kolkata'))
    now_sgt = datetime.now(pytz.timezone('Asia/Singapore'))
    
    print(f"Server time (naive):     {now_naive}")
    print(f"UTC time:                {now_utc}")
    print(f"IST time:                {now_ist}")
    print(f"SGT time:                {now_sgt}")
    print()
    
    # 2. Check MySQL timezone
    print("2. MYSQL TIMEZONE INFO:")
    print("-" * 70)
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return
    
    try:
        with conn.cursor() as cursor:
            # Check MySQL timezone settings
            cursor.execute("SELECT @@global.time_zone, @@session.time_zone")
            tz_info = cursor.fetchone()
            print(f"Global timezone:         {tz_info['@@global.time_zone']}")
            print(f"Session timezone:        {tz_info['@@session.time_zone']}")
            
            # Check current MySQL times
            cursor.execute("SELECT NOW() as now_server, UTC_TIMESTAMP() as now_utc")
            time_info = cursor.fetchone()
            print(f"MySQL NOW():             {time_info['now_server']}")
            print(f"MySQL UTC_TIMESTAMP():   {time_info['now_utc']}")
            print()
            
            # 3. Check recent MaxPe transactions
            print("3. RECENT MAXPE TRANSACTIONS:")
            print("-" * 70)
            cursor.execute("""
                SELECT 
                    order_id,
                    created_at,
                    status,
                    checkout_expired_at,
                    TIMESTAMPDIFF(SECOND, created_at, NOW()) as seconds_since_creation,
                    TIMESTAMPDIFF(SECOND, created_at, UTC_TIMESTAMP()) as seconds_since_creation_utc
                FROM payin_transactions
                WHERE pg_partner = 'MAXPE'
                ORDER BY created_at DESC
                LIMIT 5
            """)
            
            transactions = cursor.fetchall()
            
            if not transactions:
                print("No MaxPe transactions found")
            else:
                for txn in transactions:
                    print(f"\nOrder ID: {txn['order_id']}")
                    print(f"  Created at:              {txn['created_at']}")
                    print(f"  Status:                  {txn['status']}")
                    print(f"  Expired at:              {txn['checkout_expired_at']}")
                    print(f"  Seconds since (NOW):     {txn['seconds_since_creation']}")
                    print(f"  Seconds since (UTC):     {txn['seconds_since_creation_utc']}")
                    
                    # Check if would be expired
                    if txn['seconds_since_creation'] and txn['seconds_since_creation'] > 360:
                        print(f"  ⚠️  WOULD BE EXPIRED (> 6 minutes using NOW)")
                    if txn['seconds_since_creation_utc'] and txn['seconds_since_creation_utc'] > 360:
                        print(f"  ⚠️  WOULD BE EXPIRED (> 6 minutes using UTC)")
            
            print()
            
            # 4. Test timezone conversion
            print("4. TIMEZONE CONVERSION TEST:")
            print("-" * 70)
            
            # Get a recent transaction
            cursor.execute("""
                SELECT created_at, order_id
                FROM payin_transactions
                WHERE pg_partner = 'MAXPE'
                ORDER BY created_at DESC
                LIMIT 1
            """)
            
            recent = cursor.fetchone()
            if recent:
                created_at = recent['created_at']
                print(f"Sample transaction: {recent['order_id']}")
                print(f"  DB created_at (raw):     {created_at}")
                print(f"  Type:                    {type(created_at)}")
                print(f"  Has timezone:            {created_at.tzinfo is not None}")
                
                # Try to localize
                if created_at.tzinfo is None:
                    created_at_utc = pytz.UTC.localize(created_at)
                    print(f"  Localized to UTC:        {created_at_utc}")
                else:
                    created_at_utc = created_at
                    print(f"  Already has timezone:    {created_at_utc}")
                
                # Calculate elapsed time
                now_utc = datetime.now(pytz.UTC)
                elapsed = now_utc - created_at_utc
                print(f"  Current UTC:             {now_utc}")
                print(f"  Elapsed time:            {elapsed.total_seconds()} seconds")
                print(f"  Would expire:            {elapsed.total_seconds() > 360}")
            
            print()
            
            # 5. Simulate Singapore user scenario
            print("5. SINGAPORE USER SIMULATION:")
            print("-" * 70)
            
            # Create a test timestamp as if created now
            test_created_ist = datetime.now()  # Server time (IST)
            test_created_utc = datetime.now(pytz.UTC)
            
            print(f"If transaction created NOW:")
            print(f"  Server time (IST):       {test_created_ist}")
            print(f"  UTC time:                {test_created_utc}")
            
            # Simulate Singapore user opening link immediately
            sgt_tz = pytz.timezone('Asia/Singapore')
            sgt_now = datetime.now(sgt_tz)
            print(f"  Singapore time now:      {sgt_now}")
            
            # What would backend calculate?
            if test_created_ist.tzinfo is None:
                test_created_utc_localized = pytz.UTC.localize(test_created_ist)
            else:
                test_created_utc_localized = test_created_ist
            
            backend_now_utc = datetime.now(pytz.UTC)
            backend_elapsed = backend_now_utc - test_created_utc_localized
            
            print(f"  Backend would calculate: {backend_elapsed.total_seconds()} seconds elapsed")
            print(f"  Would show as expired:   {backend_elapsed.total_seconds() > 360}")
            
    finally:
        conn.close()
    
    print()
    print("=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)
    print()
    print("RECOMMENDATIONS:")
    print("1. If MySQL timezone is SYSTEM, consider setting to UTC")
    print("2. If created_at has no timezone info, we're assuming UTC")
    print("3. Check if recent transactions show correct elapsed time")
    print("4. For Singapore users, elapsed time should be same as India users")
    print()

if __name__ == '__main__':
    diagnose_timezone_issue()
