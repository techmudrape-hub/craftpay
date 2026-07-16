"""
Auto-settlement service for scheduled wallet settlements
"""
from database_pooled import get_db_connection
from wallet_service import WalletService
from datetime import datetime, timedelta
import traceback

class AutoSettlementService:
    def __init__(self):
        self.wallet_svc = WalletService()
    
    def get_merchant_auto_settlement_config(self, merchant_id):
        """Get auto-settlement configuration for a merchant"""
        try:
            conn = get_db_connection()
            if not conn:
                return None
            
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM auto_settlement_config
                    WHERE merchant_id = %s
                """, (merchant_id,))
                config = cursor.fetchone()
            
            conn.close()
            return config
            
        except Exception as e:
            print(f"Get config error: {e}")
            return None
    
    def update_auto_settlement_config(self, merchant_id, config_data):
        """Update or create auto-settlement configuration"""
        try:
            conn = get_db_connection()
            if not conn:
                return {'success': False, 'message': 'Database connection failed'}
            
            with conn.cursor() as cursor:
                # Check if config exists
                cursor.execute("""
                    SELECT id FROM auto_settlement_config
                    WHERE merchant_id = %s
                """, (merchant_id,))
                existing = cursor.fetchone()
                
                is_enabled = config_data.get('is_enabled', False)
                settlement_mode = config_data.get('settlement_mode', 'SCHEDULED')
                settlement_frequency = config_data.get('settlement_frequency', 'DAILY')
                settlement_hour = config_data.get('settlement_hour', 0)
                settlement_minute = config_data.get('settlement_minute', 0)
                settlement_day = config_data.get('settlement_day', 1)
                settlement_interval_minutes = config_data.get('settlement_interval_minutes', None)
                hold_percentage = config_data.get('hold_percentage', 0.00)
                minimum_settlement_amount = config_data.get('minimum_settlement_amount', 0.00)
                
                # Validate hold_percentage
                if hold_percentage < 0 or hold_percentage > 100:
                    return {'success': False, 'message': 'Hold percentage must be between 0 and 100'}
                
                # Validate based on mode
                if settlement_mode == 'INTERVAL':
                    if not settlement_interval_minutes or settlement_interval_minutes <= 0:
                        return {'success': False, 'message': 'Settlement interval must be greater than 0'}
                else:
                    # Validate settlement_hour
                    if settlement_hour < 0 or settlement_hour > 23:
                        return {'success': False, 'message': 'Settlement hour must be between 0 and 23'}
                    
                    # Validate settlement_minute
                    if settlement_minute < 0 or settlement_minute > 59:
                        return {'success': False, 'message': 'Settlement minute must be between 0 and 59'}
                
                if existing:
                    # Update existing config
                    cursor.execute("""
                        UPDATE auto_settlement_config
                        SET is_enabled = %s,
                            settlement_mode = %s,
                            settlement_frequency = %s,
                            settlement_hour = %s,
                            settlement_minute = %s,
                            settlement_day = %s,
                            settlement_interval_minutes = %s,
                            hold_percentage = %s,
                            minimum_settlement_amount = %s,
                            updated_at = NOW()
                        WHERE merchant_id = %s
                    """, (is_enabled, settlement_mode, settlement_frequency, settlement_hour, settlement_minute,
                          settlement_day, settlement_interval_minutes, hold_percentage, minimum_settlement_amount, merchant_id))
                else:
                    # Insert new config
                    cursor.execute("""
                        INSERT INTO auto_settlement_config
                        (merchant_id, is_enabled, settlement_mode, settlement_frequency, settlement_hour,
                         settlement_minute, settlement_day, settlement_interval_minutes, hold_percentage, minimum_settlement_amount)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (merchant_id, is_enabled, settlement_mode, settlement_frequency, settlement_hour,
                          settlement_minute, settlement_day, settlement_interval_minutes, hold_percentage, minimum_settlement_amount))
                
                conn.commit()
            
            conn.close()
            return {'success': True, 'message': 'Auto-settlement configuration updated'}
            
        except Exception as e:
            print(f"Update config error: {e}")
            traceback.print_exc()
            if conn:
                conn.rollback()
                conn.close()
            return {'success': False, 'message': str(e)}
    
    def should_settle_now(self, config):
        """Check if settlement should happen now based on config"""
        if not config or not config['is_enabled']:
            return False
        
        now = datetime.now()
        last_settlement = config.get('last_settlement_at')
        settlement_mode = config.get('settlement_mode', 'SCHEDULED')
        
        # INTERVAL MODE: Settle after X minutes from last settlement
        if settlement_mode == 'INTERVAL':
            interval_minutes = config.get('settlement_interval_minutes')
            
            if not interval_minutes or interval_minutes <= 0:
                return False
            
            # If never settled before, settle now
            if not last_settlement:
                return True
            
            # Check if enough time has passed since last settlement
            time_since_last = now - last_settlement
            minutes_since_last = time_since_last.total_seconds() / 60
            
            return minutes_since_last >= interval_minutes
        
        # SCHEDULED MODE: Settle at specific time
        frequency = config['settlement_frequency']
        settlement_hour = config['settlement_hour']
        settlement_minute = config['settlement_minute']
        
        # Check if we're in the settlement time window (within 5 minutes)
        current_time = now.hour * 60 + now.minute
        target_time = settlement_hour * 60 + settlement_minute
        time_diff = abs(current_time - target_time)
        
        if time_diff > 5:  # Not within 5-minute window
            return False
        
        # Check if already settled recently
        if last_settlement:
            time_since_last = now - last_settlement
            
            if frequency == 'HOURLY':
                # Don't settle if settled in last 55 minutes
                if time_since_last < timedelta(minutes=55):
                    return False
            elif frequency == 'DAILY':
                # Don't settle if settled in last 23 hours
                if time_since_last < timedelta(hours=23):
                    return False
            elif frequency == 'WEEKLY':
                settlement_day = config['settlement_day']
                # Check if today is the settlement day (1=Monday, 7=Sunday)
                if now.isoweekday() != settlement_day:
                    return False
                # Don't settle if settled in last 6 days
                if time_since_last < timedelta(days=6):
                    return False
        
        return True
    
    def calculate_settlement_amount(self, unsettled_balance, hold_percentage):
        """Calculate amount to settle after holding percentage"""
        if unsettled_balance <= 0:
            return 0, 0
        
        held_amount = (unsettled_balance * hold_percentage) / 100
        settlement_amount = unsettled_balance - held_amount
        
        return round(settlement_amount, 2), round(held_amount, 2)
    
    def perform_auto_settlement(self, merchant_id, admin_id='SYSTEM', force=False):
        """Perform auto-settlement for a merchant
        
        Args:
            merchant_id: Merchant ID to settle
            admin_id: Admin performing the settlement
            force: If True, bypass schedule checks (for manual triggers)
        """
        try:
            # Validate admin_id exists
            conn_check = get_db_connection()
            if conn_check:
                try:
                    with conn_check.cursor() as cursor:
                        cursor.execute("SELECT admin_id FROM admin_users WHERE admin_id = %s", (admin_id,))
                        if not cursor.fetchone():
                            # Use first available admin if provided admin doesn't exist
                            cursor.execute("SELECT admin_id FROM admin_users LIMIT 1")
                            admin_row = cursor.fetchone()
                            if admin_row:
                                admin_id = admin_row['admin_id']
                            else:
                                return {
                                    'success': False,
                                    'message': 'No admin user found in system'
                                }
                finally:
                    conn_check.close()
            
            # Get merchant config
            config = self.get_merchant_auto_settlement_config(merchant_id)
            
            if not config or not config['is_enabled']:
                return {
                    'success': False,
                    'message': 'Auto-settlement not enabled for this merchant'
                }
            
            # Get merchant wallet
            conn = get_db_connection()
            if not conn:
                return {'success': False, 'message': 'Database connection failed'}
            
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT unsettled_balance FROM merchant_wallet
                    WHERE merchant_id = %s FOR UPDATE
                """, (merchant_id,))
                wallet = cursor.fetchone()
            
            conn.close()
            
            if not wallet:
                return {'success': False, 'message': 'Merchant wallet not found'}
            
            unsettled_balance = float(wallet['unsettled_balance'])
            
            # Check minimum settlement amount
            if unsettled_balance < float(config['minimum_settlement_amount']):
                self.log_auto_settlement(
                    merchant_id, None, unsettled_balance, 0, 0,
                    'SKIPPED', f'Unsettled balance below minimum ({config["minimum_settlement_amount"]})'
                )
                return {
                    'success': False,
                    'message': f'Unsettled balance below minimum settlement amount'
                }
            
            # Calculate settlement amount with hold percentage
            settlement_amount, held_amount = self.calculate_settlement_amount(
                unsettled_balance, float(config['hold_percentage'])
            )
            
            if settlement_amount <= 0:
                self.log_auto_settlement(
                    merchant_id, None, unsettled_balance, 0, held_amount,
                    'SKIPPED', 'No amount to settle after hold percentage'
                )
                return {
                    'success': False,
                    'message': 'No amount to settle after applying hold percentage'
                }
            
            # Perform settlement
            remarks = f"Auto-settlement (Hold: {config['hold_percentage']}%)"
            if force:
                remarks = f"Manual trigger - {remarks}"
            
            result = self.wallet_svc.settle_wallet(
                merchant_id, settlement_amount, admin_id, remarks
            )
            
            if result['success']:
                # Update last settlement time
                conn = get_db_connection()
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            UPDATE auto_settlement_config
                            SET last_settlement_at = NOW()
                            WHERE merchant_id = %s
                        """, (merchant_id,))
                        conn.commit()
                    conn.close()
                
                # Log success
                self.log_auto_settlement(
                    merchant_id, result['settlement_id'], unsettled_balance,
                    settlement_amount, held_amount, 'SUCCESS', 'Auto-settlement completed'
                )
                
                return {
                    'success': True,
                    'settlement_id': result['settlement_id'],
                    'settled_amount': settlement_amount,
                    'held_amount': held_amount,
                    'message': 'Auto-settlement completed successfully'
                }
            else:
                # Log failure
                self.log_auto_settlement(
                    merchant_id, None, unsettled_balance, 0, 0,
                    'FAILED', result.get('message', 'Settlement failed')
                )
                return result
            
        except Exception as e:
            print(f"Auto-settlement error: {e}")
            traceback.print_exc()
            self.log_auto_settlement(
                merchant_id, None, 0, 0, 0, 'FAILED', str(e)
            )
            return {'success': False, 'message': str(e)}
    
    def log_auto_settlement(self, merchant_id, settlement_id, attempted_amount,
                           settled_amount, held_amount, status, reason):
        """Log auto-settlement attempt"""
        try:
            conn = get_db_connection()
            if not conn:
                return
            
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO auto_settlement_logs
                    (merchant_id, settlement_id, attempted_amount, settled_amount,
                     held_amount, status, reason)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (merchant_id, settlement_id, attempted_amount, settled_amount,
                      held_amount, status, reason))
                conn.commit()
            
            conn.close()
            
        except Exception as e:
            print(f"Log auto-settlement error: {e}")
    
    def run_scheduled_settlements(self):
        """Run scheduled settlements for all enabled merchants"""
        try:
            conn = get_db_connection()
            if not conn:
                print("Database connection failed")
                return
            
            with conn.cursor() as cursor:
                # Get all enabled auto-settlement configs
                cursor.execute("""
                    SELECT merchant_id FROM auto_settlement_config
                    WHERE is_enabled = TRUE
                """)
                configs = cursor.fetchall()
            
            conn.close()
            
            print(f"\n🔄 Running auto-settlements for {len(configs)} merchants...")
            
            for config in configs:
                merchant_id = config['merchant_id']
                
                # Get full config
                full_config = self.get_merchant_auto_settlement_config(merchant_id)
                
                # Check if should settle now
                if self.should_settle_now(full_config):
                    print(f"\n💰 Processing auto-settlement for {merchant_id}...")
                    result = self.perform_auto_settlement(merchant_id)
                    
                    if result['success']:
                        print(f"   ✅ Settled: ₹{result['settled_amount']}, Held: ₹{result['held_amount']}")
                    else:
                        print(f"   ⚠️  {result['message']}")
                else:
                    print(f"   ⏭️  Skipping {merchant_id} (not scheduled now)")
            
            print("\n✅ Auto-settlement run completed")
            
        except Exception as e:
            print(f"Run scheduled settlements error: {e}")
            traceback.print_exc()
    
    def get_auto_settlement_logs(self, merchant_id=None, limit=100):
        """Get auto-settlement logs"""
        try:
            conn = get_db_connection()
            if not conn:
                return []
            
            with conn.cursor() as cursor:
                if merchant_id:
                    cursor.execute("""
                        SELECT * FROM auto_settlement_logs
                        WHERE merchant_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    """, (merchant_id, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM auto_settlement_logs
                        ORDER BY created_at DESC
                        LIMIT %s
                    """, (limit,))
                
                logs = cursor.fetchall()
            
            conn.close()
            return logs
            
        except Exception as e:
            print(f"Get logs error: {e}")
            return []
