"""
Scheduler for auto-settlement - runs every 5 minutes
"""
import schedule
import time
from auto_settlement_service import AutoSettlementService
from datetime import datetime

def run_auto_settlements():
    """Run auto-settlements for all enabled merchants"""
    print(f"\n{'='*60}")
    print(f"Auto-Settlement Scheduler - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    service = AutoSettlementService()
    service.run_scheduled_settlements()

def start_scheduler():
    """Start the auto-settlement scheduler"""
    print("🚀 Starting Auto-Settlement Scheduler...")
    print("⏰ Running every 5 minutes")
    
    # Schedule to run every 5 minutes
    schedule.every(5).minutes.do(run_auto_settlements)
    
    # Run immediately on start
    run_auto_settlements()
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(30)  # Check every 30 seconds

if __name__ == '__main__':
    start_scheduler()
