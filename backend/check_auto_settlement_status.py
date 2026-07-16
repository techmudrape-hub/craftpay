"""
Check auto-settlement status and configuration
"""
from database_pooled import get_db_connection
from datetime import datetime

def check_status():
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        with conn.cursor() as cursor:
            # Get all enabled configs
            cursor.execute("""
                SELECT 
                    c.*,
                    m.full_name,
                    w.unsettled_balance
                FROM auto_settlement_config c
                LEFT JOIN merchants m ON c.merchant_id = m.merchant_id
                LEFT JOIN merchant_wallet w ON c.merchant_id = w.merchant_id
                WHERE c.is_enabled = 1
            """)
            configs = cursor.fetchall()
            
            print("=" * 80)
            print("AUTO-SETTLEMENT STATUS")
            print("=" * 80)
            print(f"\n✅ Found {len(configs)} enabled auto-settlement configurations\n")
            
            for config in configs:
                print(f"{'─' * 80}")
                print(f"👤 Merchant: {config['full_name']} ({config['merchant_id']})")
                print(f"💰 Unsettled Balance: ₹{float(config['unsettled_balance']):.2f}")
                print(f"\n📋 Configuration:")
                print(f"   Mode: {config['settlement_mode']}")
                
                if config['settlement_mode'] == 'INTERVAL':
                    interval = config['settlement_interval_minutes']
                    if interval:
                        if interval >= 60:
                            hours = interval // 60
                            mins = interval % 60
                            print(f"   Interval: {hours}h {mins}m ({interval} minutes)")
                        else:
                            print(f"   Interval: {interval} minutes")
                    else:
                        print(f"   ⚠️  Interval: NOT SET")
                else:
                    print(f"   Frequency: {config['settlement_frequency']}")
                    print(f"   Time: {config['settlement_hour']:02d}:{config['settlement_minute']:02d}")
                    if config['settlement_frequency'] == 'WEEKLY':
                        days = ['', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                        print(f"   Day: {days[config['settlement_day']]}")
                
                print(f"   Hold %: {float(config['hold_percentage']):.2f}%")
                print(f"   Min Amount: ₹{float(config['minimum_settlement_amount']):.2f}")
                
                if config['last_settlement_at']:
                    last = config['last_settlement_at']
                    now = datetime.now()
                    diff = now - last
                    mins_ago = int(diff.total_seconds() / 60)
                    
                    print(f"\n⏱️  Last Settlement: {last.strftime('%Y-%m-%d %H:%M:%S')} ({mins_ago} minutes ago)")
                    
                    if config['settlement_mode'] == 'INTERVAL' and config['settlement_interval_minutes']:
                        next_settlement = last.timestamp() + (config['settlement_interval_minutes'] * 60)
                        next_dt = datetime.fromtimestamp(next_settlement)
                        
                        if next_dt <= now:
                            print(f"   ⚡ Next Settlement: DUE NOW!")
                        else:
                            diff_next = next_dt - now
                            mins_until = int(diff_next.total_seconds() / 60)
                            print(f"   ⏰ Next Settlement: {next_dt.strftime('%Y-%m-%d %H:%M:%S')} (in {mins_until} minutes)")
                else:
                    print(f"\n⏱️  Last Settlement: Never")
                    if config['settlement_mode'] == 'INTERVAL':
                        print(f"   ⚡ Next Settlement: Will settle on next scheduler run")
                
                # Calculate what will be settled
                unsettled = float(config['unsettled_balance'])
                hold_pct = float(config['hold_percentage'])
                held = (unsettled * hold_pct) / 100
                to_settle = unsettled - held
                
                print(f"\n💵 Settlement Preview:")
                print(f"   Unsettled: ₹{unsettled:.2f}")
                print(f"   Will Hold: ₹{held:.2f} ({hold_pct}%)")
                print(f"   Will Settle: ₹{to_settle:.2f}")
                
                if unsettled < float(config['minimum_settlement_amount']):
                    print(f"   ⚠️  Below minimum settlement amount!")
                
                print()
            
            print("=" * 80)
            print("\n📌 SCHEDULER INFO:")
            print("   The auto-settlement scheduler runs every 5 minutes")
            print("   Check if scheduler is running: ps aux | grep auto_settlement_scheduler")
            print("\n💡 TIP: For INTERVAL mode, settlements happen X minutes after the last settlement")
            print("   Example: If interval is 2 minutes and last settlement was at 10:00,")
            print("   next settlement will be at 10:02")
            print("=" * 80)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    check_status()
