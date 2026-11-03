-- ==============================================================================
-- SnapBase: Official Database Schema Definition (MySQL 8.0+)
-- Database: photo_automation
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS `photo_automation` 
DEFAULT CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE `photo_automation`;

-- 1. Users Table
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(50) NOT NULL UNIQUE,
    `email` VARCHAR(100) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Documents Master Table
-- Stores raw extraction results, OCR text, and processing status.
-- Statuses: 'uploaded', 'processed', 'verified', 'rejected', 'failed'
CREATE TABLE IF NOT EXISTS `documents` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NULL,
    `filename` VARCHAR(255) NOT NULL,
    `image_path` VARCHAR(500) NOT NULL,
    `image_hash` VARCHAR(64) NOT NULL UNIQUE,
    `category` VARCHAR(50) NOT NULL DEFAULT 'receipts',
    `ocr_text` MEDIUMTEXT NULL,
    `ocr_confidence` DECIMAL(5, 4) NOT NULL DEFAULT 0.0000,
    `status` ENUM('uploaded', 'processed', 'verified', 'rejected', 'failed') NOT NULL DEFAULT 'uploaded',
    `raw_fields_json` JSON NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_docs_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
    INDEX `idx_doc_hash` (`image_hash`),
    INDEX `idx_doc_status` (`status`),
    INDEX `idx_doc_category` (`category`),
    INDEX `idx_doc_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Confirmed Receipts Table
-- Populated ONLY when a document is verified/approved by human or high confidence.
CREATE TABLE IF NOT EXISTS `receipts` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `document_id` INT NOT NULL UNIQUE,
    `shop_name` VARCHAR(150) NOT NULL,
    `receipt_number` VARCHAR(80) NULL,
    `date` DATE NULL,
    `phone` VARCHAR(30) NULL,
    `subtotal` DECIMAL(10, 2) DEFAULT 0.00,
    `tax_amount` DECIMAL(10, 2) DEFAULT 0.00,
    `total_amount` DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_receipt_doc` FOREIGN KEY (`document_id`) REFERENCES `documents` (`id`) ON DELETE CASCADE,
    INDEX `idx_receipt_date` (`date`),
    INDEX `idx_receipt_shop` (`shop_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Receipt Line Items Table
CREATE TABLE IF NOT EXISTS `receipt_items` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `receipt_id` INT NOT NULL,
    `item_name` VARCHAR(200) NOT NULL,
    `quantity` DECIMAL(8, 2) DEFAULT 1.00,
    `unit_price` DECIMAL(10, 2) DEFAULT 0.00,
    `total_price` DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    CONSTRAINT `fk_item_receipt` FOREIGN KEY (`receipt_id`) REFERENCES `receipts` (`id`) ON DELETE CASCADE,
    INDEX `idx_item_receipt` (`receipt_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Confirmed Students & Marksheets Table
CREATE TABLE IF NOT EXISTS `students` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `document_id` INT NOT NULL UNIQUE,
    `name` VARCHAR(150) NOT NULL,
    `usn` VARCHAR(50) NOT NULL,
    `college` VARCHAR(200) NULL,
    `semester` VARCHAR(20) NULL,
    `total_marks` DECIMAL(8, 2) DEFAULT 0.00,
    `percentage` DECIMAL(5, 2) DEFAULT 0.00,
    `result` VARCHAR(30) DEFAULT 'PASS',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_student_doc` FOREIGN KEY (`document_id`) REFERENCES `documents` (`id`) ON DELETE CASCADE,
    INDEX `idx_student_usn` (`usn`),
    INDEX `idx_student_college` (`college`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Student Marks Breakdown Table
CREATE TABLE IF NOT EXISTS `marks` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `subject_name` VARCHAR(150) NOT NULL,
    `subject_code` VARCHAR(30) NULL,
    `marks_obtained` DECIMAL(6, 2) NOT NULL DEFAULT 0.00,
    `max_marks` DECIMAL(6, 2) NOT NULL DEFAULT 100.00,
    CONSTRAINT `fk_marks_student` FOREIGN KEY (`student_id`) REFERENCES `students` (`id`) ON DELETE CASCADE,
    INDEX `idx_marks_student` (`student_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Confirmed Business Cards Table
CREATE TABLE IF NOT EXISTS `business_cards` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `document_id` INT NOT NULL UNIQUE,
    `person_name` VARCHAR(120) NOT NULL,
    `designation` VARCHAR(100) NULL,
    `company_name` VARCHAR(150) NULL,
    `phone` VARCHAR(30) NULL,
    `email` VARCHAR(120) NULL,
    `website` VARCHAR(150) NULL,
    `address` TEXT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_card_doc` FOREIGN KEY (`document_id`) REFERENCES `documents` (`id`) ON DELETE CASCADE,
    INDEX `idx_card_company` (`company_name`),
    INDEX `idx_card_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. Processing History Table
-- Logs execution timing, stages, OCR scores, and errors for observability.
CREATE TABLE IF NOT EXISTS `processing_history` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `document_id` INT NOT NULL,
    `step_name` VARCHAR(80) NOT NULL,
    `status` VARCHAR(30) NOT NULL DEFAULT 'success',
    `details` TEXT NULL,
    `execution_time_ms` INT DEFAULT 0,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_history_doc` FOREIGN KEY (`document_id`) REFERENCES `documents` (`id`) ON DELETE CASCADE,
    INDEX `idx_history_doc` (`document_id`),
    INDEX `idx_history_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
