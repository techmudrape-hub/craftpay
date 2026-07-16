"""
MaxPe Performance Monitoring Script
Monitors MaxPe payin transactions and provides insights
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
from datetime import datetime, timedelta
import json

def monitor_maxpe_performance():
    """Monitor MaxPe payin performance metrics"""
    
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        with conn.cursor() as cursor:
            print("=" * 80)
            print("MAXPE PAYIN PERFORMANCE MONITORING")
            print("=" * 80)
            print(f"Report Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            
            # 1. Overall Statistics (Last 24 hours)
            print("📊 LAST 24 HOURS STATISTICS")
            print("-" * 80)
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_transactions,
                    COUNT(CASE WHEN status = 'SUCCESS' THEN 1 END) as success_count,
                    COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as failed_count,
                    COUNT(CASE WHEN status IN ('INITIATED', 'PENDING') THEN 1 END) as pending_count,
                    SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END) as success_amount,
                    AVG(CASE WHEN status = 'SUCCESS' AND completed_at IS NOT NULL 
                        THEN TIMESTAMPDIFF(SECOND, created_at, completed_at) END) as avg_completion_time
                FROM payin_transactions
                WHERE pg_partner = 'MAXPE'
                AND created_at >= NOW() - INTERVAL 24 HOUR
            """)
            
            stats = cursor.fetchone()
            
            if stats and stats['total_transactions'] > 0:
                success_rate = (stats['success_count'] / stats['total_transactions']) * 100
                print(f"Total Transactions: {stats['total_transactions']}")
                print(f"✅ Success: {stats['success_count']} ({success_rate:.1f}%)")
                print(f"❌ Failed: {stats['failed_count']}")
                print(f"⏳ Pending: {stats['pending_count']}")
                print(f"💰 Success Amount: ₹{stats['success_amount']:.2f}")
                if stats['avg_completion_time']:
                    print(f"⏱️  Avg Completion Time: {stats['avg_completion_time']:.1f} seconds")
            else:
                print("No transactions in last 24 hours")
            
            print()
            
            # 2. Recent Transactions (Last 10)
            print("📋 RECENT TRANSACTIONS (Last 10)")
            print("-" * 80)
            
            cursor.execute("""
                SELECT 
                    txn_id,
                    order_id,
                    merchant_id,
                    amount,
                    status,
                    created_at,
                    completed_at,
                    TIMESTAMPDIFF(SECOND, created_at, COALESCE(completed_at, NOW())) as duration_seconds
                FROM payin_transactions
                WHERE pg_partner = 'MAXPE'
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            recent_txns = cursor.fetchall()
            
            if recent_txns:
                for txn in recent_txns:
                    status_icon = "✅" if txn['status'] == 'SUCCESS' else "❌" if txn['status'] == 'FAILED' else "⏳"
                    print(f"{status_icon} {txn['order_id'][:30]:<30} | ₹{txn['amount']:>8.2f} | {txn['status']:<10} | {txn['duration_seconds']:>4}s | {txn['created_at']}")
            else:
                print("No recent transactions")
            
            print()
            
            # 3. Stuck Transactions (Pending > 5 minutes)
            print("⚠️  STUCK TRANSACTIONS (Pending > 5 minutes)")
            print("-" * 80)
            
            cursor.execute("""
                SELECT 
                    txn_id,
                    order_id,
                    merchant_id,
                    amount,
                    status,
                    created_at,
                    TIMESTAMPDIFF(MINUTE, created_at, NOW()) as minutes_pending
                FROM payin_transactions
                WHERE pg_partner = 'MAXPE'
                AND status IN ('INITIATED', 'PENDING')
                AND created_at < NOW() - INTERVAL 5 MINUTE
                ORDER BY created_at ASC
                LIMIT 20
            """)
            
            stuck_txns = cursor.fetchall()
            
            if stuck_txns:
                print(f"Found {len(stuck_txns)} stuck transactions:")
                for txn in stuck_txns:
                    print(f"  ⚠️  {txn['order_id'][:40]:<40} | ₹{txn['amount']:>8.2f} | {txn['minutes_pending']:>4} min | {txn['created_at']}")
                print()
                print("💡 Recommendation: Run status check for these transactions")
                print("   python backend/check_maxpe_stuck_transactions.py")
            else:
                print("✅ No stuck transactions found")
            
            print()
            
            # 4. Callback Performance
            print("📞 CALLBACK PERFORMANCE")
            print("-" * 80)
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_callbacks,
                    COUNT(CASE WHEN response_code BETWEEN 200 AND 299 THEN 1 END) as success_callbacks,
                    COUNT(CASE WHEN response_code NOT BETWEEN 200 AND 299 OR response_code = 0 THEN 1 END) as failed_callbacks,
                    AVG(CASE WHEN response_code BETWEEN 200 AND 299 THEN 1 ELSE 0 END) * 100 as success_rate
                FROM callback_logs
                WHERE txn_id IN (
                    SELECT txn_id FROM payin_transactions 
                    WHERE pg_partner = 'MAXPE' 
                    AND created_at >= NOW() - INTERVAL 24 HOUR
                )
                AND created_at >= NOW() - INTERVAL 24 HOUR
            """)
            
            callback_stats = cursor.fetchone()
            
            if callback_stats and callback_stats['total_callbacks'] > 0:
                print(f"Total Callbacks: {callback_stats['total_callbacks']}")
                print(f"✅ Success: {callback_stats['success_callbacks']}")
                print(f"❌ Failed: {callback_stats['failed_callbacks']}")
                print(f"📈 Success Rate: {callback_stats['success_rate']:.1f}%")
            else:
                print("No callback data available")
            
            print()
            
            # 5. Hourly Transaction Volume (Last 24 hours)
            print("📈 HOURLY TRANSACTION VOLUME (Last 24 hours)")
            print("-" * 80)
            
            cursor.execute("""
                SELECT 
                    DATE_FORMAT(created_at, '%Y-%m-%d %H:00') as hour,
                    COUNT(*) as txn_count,
                    COUNT(CASE WHEN status = 'SUCCESS' THEN 1 END) as success_count,
                    SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END) as success_amount
                FROM payin_transactions
                WHERE pg_partner = 'MAXPE'
                AND created_at >= NOW() - INTERVAL 24 HOUR
                GROUP BY DATE_FORMAT(created_at, '%Y-%m-%d %H:00')
                ORDER BY hour DESC
                LIMIT 24
            """)
            
            hourly_stats = cursor.fetchall()
            
            if hourly_stats:
                for stat in hourly_stats:
                    bar = "█" * min(int(stat['txn_count'] / 2), 50)
                    print(f"{stat['hour']} | {stat['txn_count']:>3} txns | {stat['success_count']:>3} success | ₹{stat['success_amount']:>10.2f} | {bar}")
            else:
                print("No hourly data available")
            
            print()
            
            # 6. Error Analysis
            print("🔍 ERROR ANALYSIS")
            print("-" * 80)
            
            cursor.execute("""
                SELECT 
                    status,
                    COUNT(*) as count,
                    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() as percentage
                FROM payin_transactions
                WHERE pg_partner = 'MAXPE'
                AND created_at >= NOW() - INTERVAL 24 HOUR
                GROUP BY status
                ORDER BY count DESC
            """)
            
            status_breakdown = cursor.fetchall()
            
            if status_breakdown:
                for stat in status_breakdown:
                    icon = "✅" if stat['status'] == 'SUCCESS' else "❌" if stat['status'] == 'FAILED' else "⏳"
                    print(f"{icon} {stat['status']:<15} | {stat['count']:>5} transactions | {stat['percentage']:>5.1f}%")
            else:
                print("No status data available")
            
            print()
            print("=" * 80)
            
    finally:
        conn.close()

if __name__ == '__main__':
    monitor_maxpe_performance()
