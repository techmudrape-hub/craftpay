import os
import pymysql
import bcrypt
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'orchpay_db')

SQL_SCHEMA = """
SET FOREIGN_KEY_CHECKS=0;

-- Table structure for `admin_activity_logs`
DROP TABLE IF EXISTS `admin_activity_logs`;
CREATE TABLE `admin_activity_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `admin_id` varchar(50) NOT NULL,
  `action` varchar(100) NOT NULL,
  `details` text,
  `ip_address` varchar(45) DEFAULT NULL,
  `user_agent` text,
  `status` varchar(20) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_admin_id` (`admin_id`),
  CONSTRAINT `admin_activity_logs_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin_users` (`admin_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `admin_banks`
DROP TABLE IF EXISTS `admin_banks`;
CREATE TABLE `admin_banks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `admin_id` varchar(50) NOT NULL,
  `bank_name` varchar(255) NOT NULL,
  `account_number` varchar(50) NOT NULL,
  `ifsc_code` varchar(20) NOT NULL,
  `branch_name` varchar(255) DEFAULT NULL,
  `account_holder_name` varchar(255) NOT NULL,
  `tpin_hash` varchar(255) NOT NULL,
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_admin_id` (`admin_id`),
  CONSTRAINT `admin_banks_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin_users` (`admin_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `admin_users`
DROP TABLE IF EXISTS `admin_users`;
CREATE TABLE `admin_users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `admin_id` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `pin_hash` varchar(255) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `last_login` timestamp NULL DEFAULT NULL,
  `login_attempts` int DEFAULT '0',
  `locked_until` timestamp NULL DEFAULT NULL,
  `password_changed_at` timestamp NULL DEFAULT NULL,
  `pin_changed_at` timestamp NULL DEFAULT NULL,
  `must_change_password` tinyint(1) DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `admin_id` (`admin_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `admin_wallet`
DROP TABLE IF EXISTS `admin_wallet`;
CREATE TABLE `admin_wallet` (
  `id` int NOT NULL AUTO_INCREMENT,
  `admin_id` varchar(50) NOT NULL,
  `main_balance` decimal(15,2) NOT NULL DEFAULT '0.00',
  `unsettled_balance` decimal(15,2) NOT NULL DEFAULT '0.00',
  `last_updated` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `settled_balance` decimal(15,2) DEFAULT '0.00',
  PRIMARY KEY (`id`),
  UNIQUE KEY `admin_id` (`admin_id`),
  CONSTRAINT `admin_wallet_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin_users` (`admin_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `admin_wallet_transactions`
DROP TABLE IF EXISTS `admin_wallet_transactions`;
CREATE TABLE `admin_wallet_transactions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `admin_id` varchar(50) NOT NULL,
  `txn_id` varchar(100) NOT NULL,
  `wallet_type` enum('MAIN','UNSETTLED') NOT NULL,
  `txn_type` enum('CREDIT','DEBIT') NOT NULL,
  `amount` decimal(15,2) NOT NULL,
  `balance_before` decimal(15,2) NOT NULL,
  `balance_after` decimal(15,2) NOT NULL,
  `description` varchar(500) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `reference_id` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_admin_id` (`admin_id`),
  KEY `idx_wallet_type` (`wallet_type`),
  KEY `idx_created_at` (`created_at`),
  CONSTRAINT `admin_wallet_transactions_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin_users` (`admin_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `auto_settlement_config`
DROP TABLE IF EXISTS `auto_settlement_config`;
CREATE TABLE `auto_settlement_config` (
  `id` int NOT NULL AUTO_INCREMENT,
  `merchant_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `is_enabled` tinyint(1) DEFAULT '0',
  `settlement_frequency` enum('HOURLY','DAILY','WEEKLY') DEFAULT 'DAILY',
  `settlement_hour` int DEFAULT '0' COMMENT 'Hour of day (0-23) for DAILY/WEEKLY',
  `settlement_minute` int DEFAULT '0' COMMENT 'Minute of hour (0-59)',
  `settlement_day` int DEFAULT '1' COMMENT 'Day of week (1-7) for WEEKLY, 1=Monday',
  `hold_percentage` decimal(5,2) DEFAULT '0.00' COMMENT 'Percentage to hold in unsettled (0-100)',
  `minimum_settlement_amount` decimal(15,2) DEFAULT '0.00' COMMENT 'Minimum amount to trigger settlement',
  `last_settlement_at` timestamp NULL DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `settlement_interval_minutes` int DEFAULT NULL COMMENT 'Settle after X minutes (NULL = use hour/minute)',
  `settlement_mode` enum('SCHEDULED','INTERVAL') DEFAULT 'SCHEDULED' COMMENT 'SCHEDULED=specific time, INTERVAL=after X minutes',
  PRIMARY KEY (`id`),
  UNIQUE KEY `merchant_id` (`merchant_id`),
  KEY `idx_enabled` (`is_enabled`),
  KEY `idx_last_settlement` (`last_settlement_at`),
  CONSTRAINT `fk_auto_settlement_merchant` FOREIGN KEY (`merchant_id`) REFERENCES `merchants` (`merchant_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `auto_settlement_logs`
DROP TABLE IF EXISTS `auto_settlement_logs`;
CREATE TABLE `auto_settlement_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `merchant_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `settlement_id` varchar(100) DEFAULT NULL,
  `attempted_amount` decimal(15,2) NOT NULL,
  `settled_amount` decimal(15,2) DEFAULT '0.00',
  `held_amount` decimal(15,2) DEFAULT '0.00',
  `status` enum('SUCCESS','FAILED','SKIPPED') NOT NULL,
  `reason` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_merchant_id` (`merchant_id`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`),
  CONSTRAINT `fk_auto_settlement_logs_merchant` FOREIGN KEY (`merchant_id`) REFERENCES `merchants` (`merchant_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `callback_logs`
DROP TABLE IF EXISTS `callback_logs`;
CREATE TABLE `callback_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `merchant_id` varchar(50) NOT NULL,
  `txn_id` varchar(100) NOT NULL,
  `callback_url` varchar(500) DEFAULT NULL,
  `request_data` text,
  `response_code` int DEFAULT NULL,
  `response_data` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `merchant_id` (`merchant_id`),
  KEY `idx_txn_id` (`txn_id`),
  CONSTRAINT `callback_logs_ibfk_1` FOREIGN KEY (`merchant_id`) REFERENCES `merchants` (`merchant_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `chargeback_deductions`
DROP TABLE IF EXISTS `chargeback_deductions`;
CREATE TABLE `chargeback_deductions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `deduction_id` varchar(100) NOT NULL,
  `chargeback_id` int NOT NULL,
  `merchant_id` varchar(50) NOT NULL,
  `transaction_id` varchar(100) NOT NULL,
  `order_id` varchar(100) NOT NULL,
  `deduction_amount` decimal(15,2) NOT NULL,
  `previous_unsettled_balance` decimal(15,2) NOT NULL,
  `new_unsettled_balance` decimal(15,2) NOT NULL,
  `deduction_status` enum('SUCCESS','FAILED','INSUFFICIENT_BALANCE') NOT NULL DEFAULT 'SUCCESS',
  `deduction_date` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `remarks` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `deduction_id` (`deduction_id`),
  KEY `idx_merchant_id` (`merchant_id`),
  KEY `idx_chargeback_id` (`chargeback_id`),
  KEY `idx_transaction_id` (`transaction_id`),
  KEY `idx_deduction_date` (`deduction_date`),
  KEY `idx_deduction_status` (`deduction_status`),
  CONSTRAINT `chargeback_deductions_ibfk_1` FOREIGN KEY (`chargeback_id`) REFERENCES `chargebacks` (`id`) ON DELETE CASCADE,
  CONSTRAINT `chargeback_deductions_ibfk_2` FOREIGN KEY (`merchant_id`) REFERENCES `merchants` (`merchant_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `chargeback_uploads`
DROP TABLE IF EXISTS `chargeback_uploads`;
CREATE TABLE `chargeback_uploads` (
  `id` int NOT NULL AUTO_INCREMENT,
  `upload_id` varchar(100) NOT NULL,
  `merchant_id` varchar(50) NOT NULL,
  `filename` varchar(255) NOT NULL,
  `total_records` int NOT NULL DEFAULT '0',
  `successful_records` int NOT NULL DEFAULT '0',
  `failed_records` int NOT NULL DEFAULT '0',
  `uploaded_by` varchar(50) NOT NULL,
  `upload_status` enum('PROCESSING','COMPLETED','FAILED') NOT NULL DEFAULT 'PROCESSING',
  `error_message` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `upload_id` (`upload_id`),
  KEY `uploaded_by` (`uploaded_by`),
  KEY `idx_merchant_id` (`merchant_id`),
  KEY `idx_upload_status` (`upload_status`),
  KEY `idx_created_at` (`created_at`),
  CONSTRAINT `chargeback_uploads_ibfk_1` FOREIGN KEY (`merchant_id`) REFERENCES `merchants` (`merchant_id`) ON DELETE CASCADE,
  CONSTRAINT `chargeback_uploads_ibfk_2` FOREIGN KEY (`uploaded_by`) REFERENCES `admin_users` (`admin_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `chargebacks`
DROP TABLE IF EXISTS `chargebacks`;
CREATE TABLE `chargebacks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `merchant_id` varchar(50) NOT NULL,
  `transaction_id` varchar(100) NOT NULL,
  `order_id` varchar(100) NOT NULL,
  `chargeback_amount` decimal(15,2) NOT NULL,
  `status` varchar(50) NOT NULL,
  `acceptance_status` enum('PENDING','ACCEPTED','REJECTED') DEFAULT 'PENDING',
  `accepted_at` timestamp NULL DEFAULT NULL,
  `accepted_by` varchar(50) DEFAULT NULL,
  `rejection_reason` text,
  `payment_mode` varchar(50) DEFAULT NULL,
  `customer_name` varchar(255) DEFAULT NULL,
  `customer_mobile` varchar(20) DEFAULT NULL,
  `utr` varchar(100) DEFAULT NULL,
  `chargeback_date` date NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `uploaded_by` varchar(50) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `uploaded_by` (`uploaded_by`),
  KEY `idx_merchant_id` (`merchant_id`),
  KEY `idx_transaction_id` (`transaction_id`),
  KEY `idx_order_id` (`order_id`),
  KEY `idx_chargeback_date` (`chargeback_date`),
  KEY `idx_created_at` (`created_at`),
  CONSTRAINT `chargebacks_ibfk_1` FOREIGN KEY (`merchant_id`) REFERENCES `merchants` (`merchant_id`) ON DELETE CASCADE,
  CONSTRAINT `chargebacks_ibfk_2` FOREIGN KEY (`uploaded_by`) REFERENCES `admin_users` (`admin_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `commercial_charges`
DROP TABLE IF EXISTS `commercial_charges`;
CREATE TABLE `commercial_charges` (
  `id` int NOT NULL AUTO_INCREMENT,
  `scheme_id` int NOT NULL,
  `service_type` enum('PAYOUT','PAYIN') NOT NULL,
  `product_name` varchar(100) NOT NULL,
  `min_amount` decimal(10,2) NOT NULL,
  `max_amount` decimal(10,2) NOT NULL,
  `charge_value` decimal(10,4) NOT NULL,
  `charge_type` enum('PERCENTAGE','FIXED') NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_scheme_product` (`scheme_id`,`service_type`,`product_name`),
  CONSTRAINT `commercial_charges_ibfk_1` FOREIGN KEY (`scheme_id`) REFERENCES `commercial_schemes` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `commercial_schemes`
DROP TABLE IF EXISTS `commercial_schemes`;
CREATE TABLE `commercial_schemes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `scheme_name` varchar(100) NOT NULL,
  `is_active` tinyint(1) DEFAULT '1',
  `created_by` varchar(50) NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `scheme_name` (`scheme_name`),
  KEY `created_by` (`created_by`),
  CONSTRAINT `commercial_schemes_ibfk_1` FOREIGN KEY (`created_by`) REFERENCES `admin_users` (`admin_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `fund_requests`
DROP TABLE IF EXISTS `fund_requests`;
CREATE TABLE `fund_requests` (
  `id` int NOT NULL AUTO_INCREMENT,
  `request_id` varchar(100) NOT NULL,
  `merchant_id` varchar(50) NOT NULL,
  `amount` decimal(15,2) NOT NULL,
  `request_type` enum('TOPUP','SETTLEMENT') NOT NULL,
  `status` enum('PENDING','APPROVED','REJECTED') NOT NULL DEFAULT 'PENDING',
  `remarks` text,
  `requested_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `processed_at` timestamp NULL DEFAULT NULL,
  `processed_by` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `request_id` (`request_id`),
  KEY `processed_by` (`processed_by`),
  KEY `idx_merchant_id` (`merchant_id`),
  KEY `idx_status` (`status`),
  CONSTRAINT `fund_requests_ibfk_1` FOREIGN KEY (`merchant_id`) REFERENCES `merchants` (`merchant_id`) ON DELETE CASCADE,
  CONSTRAINT `fund_requests_ibfk_2` FOREIGN KEY (`processed_by`) REFERENCES `admin_users` (`admin_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `ip_security_logs`
DROP TABLE IF EXISTS `ip_security_logs`;
CREATE TABLE `ip_security_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `merchant_id` varchar(50) NOT NULL,
  `ip_address` varchar(45) NOT NULL,
  `endpoint` varchar(255) NOT NULL,
  `action` varchar(100) NOT NULL,
  `status` enum('ALLOWED','BLOCKED') NOT NULL,
  `user_agent` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_ip_logs_merchant` (`merchant_id`,`created_at`),
  KEY `idx_ip_logs_status` (`status`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `merchant_banks`
DROP TABLE IF EXISTS `merchant_banks`;
CREATE TABLE `merchant_banks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `merchant_id` varchar(50) NOT NULL,
  `bank_name` varchar(255) NOT NULL,
  `account_number` varchar(50) NOT NULL,
  `ifsc_code` varchar(20) NOT NULL,
  `branch_name` varchar(255) DEFAULT NULL,
  `account_holder_name` varchar(255) NOT NULL,
  `tpin_hash` varchar(255) NOT NULL,
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `merchant_id` (`merchant_id`),
  CONSTRAINT `merchant_banks_ibfk_1` FOREIGN KEY (`merchant_id`) REFERENCES `merchants` (`merchant_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `merchant_callbacks`
DROP TABLE IF EXISTS `merchant_callbacks`;
CREATE TABLE `merchant_callbacks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `merchant_id` varchar(50) NOT NULL,
  `payin_callback_url` varchar(500) DEFAULT NULL,
  `payout_callback_url` varchar(500) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `merchant_id` (`merchant_id`),
  CONSTRAINT `merchant_callbacks_ibfk_1` FOREIGN KEY (`merchant_id`) REFERENCES `merchants` (`merchant_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `merchant_documents`
DROP TABLE IF EXISTS `merchant_documents`;
CREATE TABLE `merchant_documents` (
  `id` int NOT NULL AUTO_INCREMENT,
  `merchant_id` varchar(50) NOT NULL,
  `aadhar_front_path` varchar(500) DEFAULT NULL,
  `aadhar_back_path` varchar(500) DEFAULT NULL,
  `pan_card_path` varchar(500) DEFAULT NULL,
  `gst_certificate_path` varchar(500) DEFAULT NULL,
  `cancelled_cheque_path` varchar(500) DEFAULT NULL,
  `shop_photo_path` varchar(500) DEFAULT NULL,
  `profile_photo_path` varchar(500) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `merchant_id` (`merchant_id`),
  CONSTRAINT `merchant_documents_ibfk_1` FOREIGN KEY (`merchant_id`) REFERENCES `merchants` (`merchant_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `merchant_ip_security`
DROP TABLE IF EXISTS `merchant_ip_security`;
CREATE TABLE `merchant_ip_security` (
  `id` int NOT NULL AUTO_INCREMENT,
  `merchant_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `ip_address` varchar(45) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT '1',
  `created_by` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_merchant_ip` (`merchant_id`,`ip_address`),
  KEY `idx_merchant_ip_active` (`merchant_id`,`ip_address`,`is_active`),
  KEY `idx_created_by` (`created_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `merchant_ip_whitelist`
DROP TABLE IF EXISTS `merchant_ip_whitelist`;
CREATE TABLE `merchant_ip_whitelist` (
  `id` int NOT NULL AUTO_INCREMENT,
  `merchant_id` varchar(50) NOT NULL,
  `ip_address` varchar(45) NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_merchant_ip` (`merchant_id`,`ip_address`),
  CONSTRAINT `merchant_ip_whitelist_ibfk_1` FOREIGN KEY (`merchant_id`) REFERENCES `merchants` (`merchant_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `merchant_unsettled_wallet`
DROP TABLE IF EXISTS `merchant_unsettled_wallet`;
CREATE TABLE `merchant_unsettled_wallet` (
  `id` int NOT NULL AUTO_INCREMENT,
  `merchant_id` varchar(50) NOT NULL,
  `balance` decimal(15,2) NOT NULL DEFAULT '0.00',
  `last_updated` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `merchant_id` (`merchant_id`),
  KEY `idx_merchant_id` (`merchant_id`),
  CONSTRAINT `merchant_unsettled_wallet_ibfk_1` FOREIGN KEY (`merchant_id`) REFERENCES `merchants` (`merchant_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `merchant_wallet`
DROP TABLE IF EXISTS `merchant_wallet`;
CREATE TABLE `merchant_wallet` (
  `id` int NOT NULL AUTO_INCREMENT,
  `merchant_id` varchar(50) NOT NULL,
  `balance` decimal(15,2) NOT NULL DEFAULT '0.00',
  `main_balance` decimal(15,2) DEFAULT '0.00',
  `unsettled_balance` decimal(15,2) DEFAULT '0.00',
  `settled_balance` decimal(15,2) DEFAULT '0.00',
  `last_updated` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `cyber_hold_amount` decimal(15,2) DEFAULT '0.00',
  `total_hold_amount` decimal(15,2) DEFAULT '0.00',
  PRIMARY KEY (`id`),
  UNIQUE KEY `merchant_id` (`merchant_id`),
  KEY `idx_wallet_merchant` (`merchant_id`),
  CONSTRAINT `merchant_wallet_ibfk_1` FOREIGN KEY (`merchant_id`) REFERENCES `merchants` (`merchant_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `merchant_wallet_transactions`
DROP TABLE IF EXISTS `merchant_wallet_transactions`;
CREATE TABLE `merchant_wallet_transactions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `merchant_id` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `transaction_type` enum('CREDIT','DEBIT','SETTLEMENT','REFUND','CHARGE','TOPUP','FETCH') COLLATE utf8mb4_unicode_ci NOT NULL,
  `amount` decimal(15,2) NOT NULL,
  `balance_before` decimal(15,2) NOT NULL,
  `balance_after` decimal(15,2) NOT NULL,
  `reference_id` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txn_id` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `txn_type` enum('CREDIT','DEBIT','HOLD','RELEASE','UNSETTLED_CREDIT','SETTLEMENT') COLLATE utf8mb4_unicode_ci NOT NULL,
  `on_hold_before` decimal(15,2) DEFAULT '0.00',
  `on_hold_after` decimal(15,2) DEFAULT '0.00',
  PRIMARY KEY (`id`),
  KEY `idx_merchant_id` (`merchant_id`),
  KEY `idx_transaction_type` (`transaction_type`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_reference_id` (`reference_id`),
  KEY `idx_merchant_created` (`merchant_id`,`created_at`),
  KEY `idx_txn_type` (`txn_type`),
  KEY `idx_reference` (`reference_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table structure for `merchants`
DROP TABLE IF EXISTS `merchants`;
CREATE TABLE `merchants` (
  `id` int NOT NULL AUTO_INCREMENT,
  `merchant_id` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `pin_hash` varchar(255) DEFAULT NULL,
  `full_name` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `mobile` varchar(20) NOT NULL,
  `dob` date DEFAULT NULL,
  `aadhar_card` varchar(20) NOT NULL,
  `pan_no` varchar(20) NOT NULL,
  `pincode` varchar(10) NOT NULL,
  `state` varchar(100) NOT NULL,
  `city` varchar(100) NOT NULL,
  `house_number` varchar(100) DEFAULT NULL,
  `address` text NOT NULL,
  `landmark` varchar(255) DEFAULT NULL,
  `merchant_type` enum('PAYIN','PAYOUT','BOTH') NOT NULL,
  `account_number` varchar(50) NOT NULL,
  `ifsc_code` varchar(20) NOT NULL,
  `gst_no` varchar(50) NOT NULL,
  `scheme_id` int DEFAULT NULL,
  `authorization_key` varchar(255) NOT NULL,
  `module_secret` varchar(255) NOT NULL,
  `aes_iv` varchar(255) NOT NULL,
  `aes_key` varchar(255) NOT NULL,
  `is_active` tinyint(1) DEFAULT '1',
  `created_by` varchar(50) NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `password_changed_at` timestamp NULL DEFAULT NULL,
  `pin_changed_at` timestamp NULL DEFAULT NULL,
  `qr_enabled` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `merchant_id` (`merchant_id`),
  UNIQUE KEY `authorization_key` (`authorization_key`),
  UNIQUE KEY `module_secret` (`module_secret`),
  KEY `scheme_id` (`scheme_id`),
  KEY `created_by` (`created_by`),
  KEY `idx_merchant_email` (`email`),
  CONSTRAINT `merchants_ibfk_1` FOREIGN KEY (`scheme_id`) REFERENCES `commercial_schemes` (`id`),
  CONSTRAINT `merchants_ibfk_2` FOREIGN KEY (`created_by`) REFERENCES `admin_users` (`admin_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `payin_transactions`
DROP TABLE IF EXISTS `payin_transactions`;
CREATE TABLE `payin_transactions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `txn_id` varchar(100) NOT NULL,
  `txn_type` varchar(50) DEFAULT 'PAYIN',
  `merchant_id` varchar(50) NOT NULL,
  `order_id` varchar(100) NOT NULL,
  `amount` decimal(15,2) NOT NULL,
  `charge_amount` decimal(15,2) NOT NULL DEFAULT '0.00',
  `charge_type` enum('PERCENTAGE','FIXED') NOT NULL DEFAULT 'FIXED',
  `net_amount` decimal(15,2) NOT NULL,
  `payee_name` varchar(255) DEFAULT NULL,
  `payee_email` varchar(255) DEFAULT NULL,
  `payee_mobile` varchar(20) DEFAULT NULL,
  `product_info` varchar(500) DEFAULT NULL,
  `status` enum('INITIATED','PENDING','SUCCESS','FAILED','CANCELLED') NOT NULL DEFAULT 'INITIATED',
  `pg_partner` varchar(50) DEFAULT 'PayU',
  `pg_txn_id` varchar(100) DEFAULT NULL,
  `bank_ref_no` varchar(100) DEFAULT NULL,
  `payment_mode` varchar(50) DEFAULT NULL,
  `error_message` text,
  `remarks` text,
  `callback_url` varchar(500) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `completed_at` timestamp NULL DEFAULT NULL,
  `checkout_expired_at` timestamp NULL DEFAULT NULL,
  `payment_url` text,
  PRIMARY KEY (`id`),
  UNIQUE KEY `txn_id` (`txn_id`),
  KEY `idx_merchant_id` (`merchant_id`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_order_merchant` (`order_id`,`merchant_id`),
  KEY `idx_merchant_created` (`merchant_id`,`created_at`),
  KEY `idx_status_created` (`status`,`created_at`),
  KEY `idx_order_id` (`order_id`),
  KEY `idx_txn_id` (`txn_id`),
  CONSTRAINT `payin_transactions_ibfk_1` FOREIGN KEY (`merchant_id`) REFERENCES `merchants` (`merchant_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `payout_transactions`
DROP TABLE IF EXISTS `payout_transactions`;
CREATE TABLE `payout_transactions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `txn_id` varchar(100) NOT NULL,
  `txn_type` varchar(50) DEFAULT 'PAYOUT',
  `merchant_id` varchar(50) DEFAULT NULL,
  `reference_id` varchar(100) NOT NULL,
  `order_id` varchar(100) DEFAULT NULL,
  `batch_id` varchar(100) DEFAULT NULL,
  `amount` decimal(15,2) NOT NULL,
  `charge_amount` decimal(15,2) NOT NULL DEFAULT '0.00',
  `charge_type` enum('PERCENTAGE','FIXED') NOT NULL DEFAULT 'FIXED',
  `net_amount` decimal(15,2) NOT NULL,
  `bene_name` varchar(255) NOT NULL,
  `bene_email` varchar(255) DEFAULT NULL,
  `bene_mobile` varchar(20) DEFAULT NULL,
  `bene_bank` varchar(255) DEFAULT NULL,
  `ifsc_code` varchar(20) DEFAULT NULL,
  `account_no` varchar(50) DEFAULT NULL,
  `vpa` varchar(100) DEFAULT NULL,
  `payment_type` enum('IMPS','NEFT','RTGS','UPI') NOT NULL DEFAULT 'IMPS',
  `purpose` varchar(500) DEFAULT NULL,
  `status` enum('INITIATED','QUEUED','INPROCESS','SUCCESS','FAILED','REVERSED') NOT NULL DEFAULT 'INITIATED',
  `pg_partner` varchar(50) DEFAULT 'PayU',
  `pg_txn_id` varchar(100) DEFAULT NULL,
  `bank_ref_no` varchar(100) DEFAULT NULL,
  `utr` varchar(100) DEFAULT NULL,
  `name_with_bank` varchar(255) DEFAULT NULL,
  `name_match_score` int DEFAULT NULL,
  `error_message` text,
  `remarks` text,
  `callback_url` varchar(500) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `completed_at` timestamp NULL DEFAULT NULL,
  `admin_id` varchar(50) DEFAULT NULL,
  `mobile` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `txn_id` (`txn_id`),
  KEY `idx_merchant_id` (`merchant_id`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_reference_id` (`reference_id`),
  KEY `idx_order_id` (`order_id`),
  KEY `idx_admin_id` (`admin_id`),
  KEY `idx_payout_merchant_created` (`merchant_id`,`created_at`),
  KEY `idx_payout_status` (`status`),
  KEY `idx_payout_order_id` (`order_id`),
  KEY `idx_payout_txn_id` (`txn_id`),
  CONSTRAINT `payout_transactions_ibfk_1` FOREIGN KEY (`merchant_id`) REFERENCES `merchants` (`merchant_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `payu_tokens`
DROP TABLE IF EXISTS `payu_tokens`;
CREATE TABLE `payu_tokens` (
  `id` int NOT NULL AUTO_INCREMENT,
  `access_token` text NOT NULL,
  `refresh_token` text,
  `token_type` varchar(50) DEFAULT NULL,
  `expires_at` timestamp NOT NULL,
  `user_uuid` varchar(100) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `payu_webhook_config`
DROP TABLE IF EXISTS `payu_webhook_config`;
CREATE TABLE `payu_webhook_config` (
  `id` int NOT NULL AUTO_INCREMENT,
  `event_type` varchar(100) NOT NULL,
  `webhook_url` varchar(500) NOT NULL,
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_event` (`event_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `payu_webhook_logs`
DROP TABLE IF EXISTS `payu_webhook_logs`;
CREATE TABLE `payu_webhook_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `event_type` varchar(100) NOT NULL,
  `merchant_ref_id` varchar(100) DEFAULT NULL,
  `payu_ref_id` varchar(100) DEFAULT NULL,
  `payload` text,
  `status` enum('RECEIVED','PROCESSED','FAILED') NOT NULL DEFAULT 'RECEIVED',
  `error_message` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `processed_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_event_type` (`event_type`),
  KEY `idx_merchant_ref_id` (`merchant_ref_id`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `qr_codes`
DROP TABLE IF EXISTS `qr_codes`;
CREATE TABLE `qr_codes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `qr_image_path` varchar(512) NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `qr_merchant_routing`
DROP TABLE IF EXISTS `qr_merchant_routing`;
CREATE TABLE `qr_merchant_routing` (
  `id` int NOT NULL AUTO_INCREMENT,
  `merchant_id` varchar(50) NOT NULL,
  `qr_code_id` int NOT NULL,
  `is_enabled` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_merchant_qr` (`merchant_id`),
  KEY `qr_code_id` (`qr_code_id`),
  CONSTRAINT `qr_merchant_routing_ibfk_1` FOREIGN KEY (`qr_code_id`) REFERENCES `qr_codes` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `qr_transactions`
DROP TABLE IF EXISTS `qr_transactions`;
CREATE TABLE `qr_transactions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `txn_id` varchar(100) NOT NULL,
  `order_id` varchar(100) NOT NULL,
  `merchant_id` varchar(50) NOT NULL,
  `qr_code_id` int DEFAULT NULL,
  `amount` decimal(15,2) NOT NULL,
  `charge_amount` decimal(15,2) NOT NULL DEFAULT '0.00',
  `charge_type` enum('PERCENTAGE','FIXED') NOT NULL DEFAULT 'FIXED',
  `net_amount` decimal(15,2) NOT NULL DEFAULT '0.00',
  `customer_name` varchar(255) DEFAULT NULL,
  `mobile` varchar(20) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `status` enum('INITIATED','UTR_SUBMITTED','SUCCESS','FAILED') NOT NULL DEFAULT 'INITIATED',
  `utr` varchar(100) DEFAULT NULL,
  `pg_partner` varchar(50) NOT NULL DEFAULT 'QR',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `completed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `txn_id` (`txn_id`),
  KEY `idx_merchant_id` (`merchant_id`),
  KEY `idx_order_id` (`order_id`),
  KEY `idx_txn_id` (`txn_id`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `service_routing`
DROP TABLE IF EXISTS `service_routing`;
CREATE TABLE `service_routing` (
  `id` int NOT NULL AUTO_INCREMENT,
  `merchant_id` varchar(50) DEFAULT NULL,
  `service_type` enum('PAYIN','PAYOUT') NOT NULL,
  `routing_type` enum('SINGLE_USER','ALL_USERS') NOT NULL,
  `pg_partner` varchar(50) NOT NULL,
  `is_active` tinyint(1) DEFAULT '1',
  `priority` int DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_routing` (`merchant_id`,`service_type`,`routing_type`,`pg_partner`),
  CONSTRAINT `service_routing_ibfk_1` FOREIGN KEY (`merchant_id`) REFERENCES `merchants` (`merchant_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for `settlement_transactions`
DROP TABLE IF EXISTS `settlement_transactions`;
CREATE TABLE `settlement_transactions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `settlement_id` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `merchant_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `amount` decimal(15,2) NOT NULL,
  `settled_by` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `remarks` text COLLATE utf8mb4_unicode_ci,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `settlement_id` (`settlement_id`),
  KEY `idx_merchant_id` (`merchant_id`),
  KEY `idx_created_at` (`created_at`),
  KEY `fk_settlement_admin` (`settled_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table structure for `wallet_transactions`
DROP TABLE IF EXISTS `wallet_transactions`;
CREATE TABLE `wallet_transactions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `merchant_id` varchar(50) NOT NULL,
  `txn_id` varchar(100) NOT NULL,
  `txn_type` enum('CREDIT','DEBIT') NOT NULL,
  `amount` decimal(15,2) NOT NULL,
  `balance_before` decimal(15,2) NOT NULL,
  `balance_after` decimal(15,2) NOT NULL,
  `description` varchar(500) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_merchant_id` (`merchant_id`),
  KEY `idx_created_at` (`created_at`),
  CONSTRAINT `wallet_transactions_ibfk_1` FOREIGN KEY (`merchant_id`) REFERENCES `merchants` (`merchant_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

SET FOREIGN_KEY_CHECKS=1;
"""

def setup_database():
    print(f"Connecting to MySQL database '{DB_NAME}' at '{DB_HOST}'...")
    try:
        connection = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            print("Executing schema...")
            # Split schema by semicolon, but handle cases where semicolon is inside comments or strings
            # Since this is a simple export, we can execute it by executing statements one by one.
            statements = SQL_SCHEMA.split(';')
            for statement in statements:
                if statement.strip():
                    cursor.execute(statement)
            
            print("Schema recreated successfully.")
            
            # Create default admin user
            admin_id = "admin@craftpay.in"
            password = "Admin@123"
            
            # Hash password with bcrypt
            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
            
            print(f"Creating default admin user: {admin_id}")
            
            # Check if admin already exists
            cursor.execute("SELECT id FROM admin_users WHERE admin_id = %s", (admin_id,))
            if cursor.fetchone():
                print(f"Admin user {admin_id} already exists. Updating password...")
                cursor.execute(
                    "UPDATE admin_users SET password_hash = %s WHERE admin_id = %s",
                    (password_hash, admin_id)
                )
            else:
                cursor.execute(
                    "INSERT INTO admin_users (admin_id, password_hash, is_active, must_change_password) VALUES (%s, %s, 1, 0)",
                    (admin_id, password_hash)
                )
                
            connection.commit()
            print("Database setup complete! You can now log in.")
            
    except pymysql.MySQLError as e:
        print(f"Database Error: {e}")
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()

if __name__ == "__main__":
    setup_database()
