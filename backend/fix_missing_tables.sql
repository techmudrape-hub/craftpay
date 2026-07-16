-- Fix missing columns and tables for OrchPay

-- 1. Add settled_balance column to merchant_wallet if it doesn't exist
ALTER TABLE merchant_wallet 
ADD COLUMN IF NOT EXISTS settled_balance DECIMAL(15,2) DEFAULT 0.00 AFTER unsettled_balance;

-- 2. Create merchant_wallet_transactions table if it doesn't exist
CREATE TABLE IF NOT EXISTS merchant_wallet_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    merchant_id VARCHAR(100) NOT NULL,
    transaction_type ENUM('CREDIT', 'DEBIT', 'SETTLEMENT', 'REFUND', 'CHARGE', 'TOPUP', 'FETCH') NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    balance_before DECIMAL(15,2) NOT NULL,
    balance_after DECIMAL(15,2) NOT NULL,
    reference_id VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_transaction_type (transaction_type),
    INDEX idx_created_at (created_at),
    INDEX idx_reference_id (reference_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Verify merchant_wallet structure
ALTER TABLE merchant_wallet 
MODIFY COLUMN main_balance DECIMAL(15,2) DEFAULT 0.00,
MODIFY COLUMN unsettled_balance DECIMAL(15,2) DEFAULT 0.00;

-- 4. Add indexes for better performance
ALTER TABLE merchant_wallet_transactions
ADD INDEX IF NOT EXISTS idx_merchant_created (merchant_id, created_at);

-- Show the structure
DESCRIBE merchant_wallet;
DESCRIBE merchant_wallet_transactions;
