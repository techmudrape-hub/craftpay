"""
MaxPe Checkout Expiry Service
Background service that marks checkout links as expired after 6 minutes if no callback received
"""

import time
from datetime import datetime, timedelta
from database import get_db_connection
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('MaxPeCheckoutExpiry')

# Expiry timeout in minutes
CHECKOUT_EXPIRY_MINUTES = 6

def check_and_expire_checkout_links():
    """
    Check for checkout links that have been pending for more than 6 minutes
    and mark them as expired
    Uses MySQL TIMESTAMPDIFF to avoid timezone issues
    """
    conn = get_db_connection()
    if not conn:
        logger.error("Failed to connect to database")
        return
    
    try:
        with conn.cursor() as cursor:
            # Use MySQL's TIMESTAMPDIFF to find transactions older than 6 minutes (360 seconds)
            # This avoids all Python timezone issues - MySQL handles it internally
            logger.info(f"Checking for transactions older than {CHECKOUT_EXPIRY_MINUTES} minutes")
            
            cursor.execute("""
                SELECT txn_id, order_id, merchant_id, amount, created_at,
                       TIMESTAMPDIFF(SECOND, created_at, NOW()) as seconds_elapsed
                FROM payin_transactions
                WHERE pg_partner = 'MAXPE'
                AND status IN ('INITIATED', 'PENDING')
                AND checkout_expired_at IS NULL
                AND TIMESTAMPDIFF(SECOND, created_at, NOW()) > %s
            """, (CHECKOUT_EXPIRY_MINUTES * 60,))
            
            expired_transactions = cursor.fetchall()
            
            if not expired_transactions:
                logger.debug("No transactions to expire")
                return
            
            logger.info(f"Found {len(expired_transactions)} transactions to expire")
            
            # Mark each transaction as expired
            for txn in expired_transactions:
                try:
                    seconds_elapsed = txn['seconds_elapsed']
                    logger.info(f"Expiring: {txn['order_id']} (elapsed: {seconds_elapsed}s = {seconds_elapsed/60:.1f}min)")
                    
                    # Update the transaction to mark it as expired (but keep original status)
                    cursor.execute("""
                        UPDATE payin_transactions
                        SET checkout_expired_at = NOW(),
                            error_message = 'Checkout link expired - No callback received within 6 minutes',
                            updated_at = NOW()
                        WHERE txn_id = %s
                        AND status IN ('INITIATED', 'PENDING')
                    """, (txn['txn_id'],))
                    
                    if cursor.rowcount > 0:
                        logger.info(f"✅ Expired: {txn['order_id']} (created: {txn['created_at']})")
                    
                except Exception as e:
                    logger.error(f"Error expiring transaction {txn['txn_id']}: {e}")
                    continue
            
            conn.commit()
            logger.info(f"Successfully expired {len(expired_transactions)} checkout links")
            
    except Exception as e:
        logger.error(f"Error in check_and_expire_checkout_links: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

def run_expiry_service():
    """
    Main service loop - checks for expired links every 30 seconds
    """
    logger.info("=" * 60)
    logger.info("MaxPe Checkout Expiry Service Started")
    logger.info(f"Expiry timeout: {CHECKOUT_EXPIRY_MINUTES} minutes")
    logger.info(f"Check interval: 30 seconds")
    logger.info("=" * 60)
    
    while True:
        try:
            check_and_expire_checkout_links()
            time.sleep(30)  # Check every 30 seconds
        except KeyboardInterrupt:
            logger.info("Service stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error in service loop: {e}")
            time.sleep(30)  # Wait before retrying

if __name__ == '__main__':
    run_expiry_service()
