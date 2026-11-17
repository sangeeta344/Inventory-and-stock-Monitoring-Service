-- =========================================================
-- Smart Supermarket Management System - MySQL Database DDL
-- Database: smart_supermarket
-- Character Set: utf8mb4 / utf8mb4_unicode_ci
-- =========================================================

CREATE DATABASE IF NOT EXISTS `smart_supermarket` 
CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `smart_supermarket`;

SET FOREIGN_KEY_CHECKS = 0;

-- 1. Users Table
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(50) NOT NULL UNIQUE,
    `email` VARCHAR(100) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `role` ENUM('OWNER', 'CASHIER') NOT NULL DEFAULT 'CASHIER',
    `full_name` VARCHAR(100) NOT NULL,
    `phone` VARCHAR(20) NULL,
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_users_role` (`role`),
    INDEX `idx_users_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Employees Table
DROP TABLE IF EXISTS `employees`;
CREATE TABLE `employees` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL UNIQUE,
    `employee_code` VARCHAR(20) NOT NULL UNIQUE,
    `designation` VARCHAR(50) DEFAULT 'Store Cashier',
    `salary` DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    `hire_date` DATE NULL,
    `emergency_contact` VARCHAR(50) NULL,
    `notes` TEXT NULL,
    CONSTRAINT `fk_employee_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Categories Table
DROP TABLE IF EXISTS `categories`;
CREATE TABLE `categories` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL UNIQUE,
    `description` VARCHAR(255) NULL,
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_cat_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Products Table
DROP TABLE IF EXISTS `products`;
CREATE TABLE `products` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(150) NOT NULL,
    `category_id` INT NOT NULL,
    `barcode` VARCHAR(50) NOT NULL UNIQUE,
    `purchase_price` DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    `selling_price` DECIMAL(10, 2) NOT NULL,
    `current_stock` INT NOT NULL DEFAULT 0,
    `min_stock_level` INT NOT NULL DEFAULT 5,
    `unit_of_measure` VARCHAR(20) NOT NULL DEFAULT 'pcs',
    `description` TEXT NULL,
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_product_category` FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`),
    INDEX `idx_prod_barcode` (`barcode`),
    INDEX `idx_prod_stock` (`current_stock`),
    INDEX `idx_prod_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Suppliers Table
DROP TABLE IF EXISTS `suppliers`;
CREATE TABLE `suppliers` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL,
    `company_name` VARCHAR(100) NOT NULL,
    `phone` VARCHAR(20) NOT NULL,
    `email` VARCHAR(100) NULL,
    `address` TEXT NULL,
    `payment_details` TEXT NULL,
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_sup_company` (`company_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Inventory Batches Table (FEFO Batch Tracking)
DROP TABLE IF EXISTS `inventory_batches`;
CREATE TABLE `inventory_batches` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `product_id` INT NOT NULL,
    `supplier_id` INT NULL,
    `purchase_item_id` INT NULL,
    `batch_number` VARCHAR(50) NOT NULL,
    `purchase_date` DATE NOT NULL,
    `expiry_date` DATE NULL,
    `unit_cost` DECIMAL(10, 2) NOT NULL,
    `quantity_received` INT NOT NULL,
    `quantity_remaining` INT NOT NULL,
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_batch_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_batch_supplier` FOREIGN KEY (`supplier_id`) REFERENCES `suppliers` (`id`) ON DELETE SET NULL,
    INDEX `idx_batch_expiry` (`expiry_date`),
    INDEX `idx_batch_remaining` (`quantity_remaining`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Purchases Table
DROP TABLE IF EXISTS `purchases`;
CREATE TABLE `purchases` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `supplier_id` INT NOT NULL,
    `invoice_number` VARCHAR(50) NOT NULL,
    `purchase_date` DATE NOT NULL,
    `total_amount` DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    `payment_status` ENUM('PAID', 'PENDING', 'PARTIAL') NOT NULL DEFAULT 'PAID',
    `status` ENUM('RECEIVED', 'ORDERED', 'CANCELLED') NOT NULL DEFAULT 'RECEIVED',
    `notes` TEXT NULL,
    `created_by` INT NOT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_purchase_supplier` FOREIGN KEY (`supplier_id`) REFERENCES `suppliers` (`id`),
    CONSTRAINT `fk_purchase_user` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`),
    INDEX `idx_pur_invoice` (`invoice_number`),
    INDEX `idx_pur_date` (`purchase_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. Purchase Items Table
DROP TABLE IF EXISTS `purchase_items`;
CREATE TABLE `purchase_items` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `purchase_id` INT NOT NULL,
    `product_id` INT NOT NULL,
    `batch_number` VARCHAR(50) NOT NULL,
    `expiry_date` DATE NULL,
    `quantity` INT NOT NULL,
    `unit_price` DECIMAL(10, 2) NOT NULL,
    `subtotal` DECIMAL(10, 2) NOT NULL,
    CONSTRAINT `fk_pitem_purchase` FOREIGN KEY (`purchase_id`) REFERENCES `purchases` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_pitem_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. Sales Table
DROP TABLE IF EXISTS `sales`;
CREATE TABLE `sales` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `invoice_number` VARCHAR(50) NOT NULL UNIQUE,
    `transaction_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `cashier_id` INT NOT NULL,
    `customer_name` VARCHAR(100) NULL DEFAULT 'Walk-in Customer',
    `customer_phone` VARCHAR(20) NULL,
    `subtotal` DECIMAL(10, 2) NOT NULL,
    `discount_amount` DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    `tax_amount` DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    `final_amount` DECIMAL(10, 2) NOT NULL,
    `payment_method` ENUM('CASH', 'CARD', 'UPI', 'DIGITAL') NOT NULL DEFAULT 'CASH',
    `payment_status` ENUM('COMPLETED', 'CANCELLED', 'REFUNDED') NOT NULL DEFAULT 'COMPLETED',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_sale_cashier` FOREIGN KEY (`cashier_id`) REFERENCES `users` (`id`),
    INDEX `idx_sale_invoice` (`invoice_number`),
    INDEX `idx_sale_date` (`transaction_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. Sale Items Table
DROP TABLE IF EXISTS `sale_items`;
CREATE TABLE `sale_items` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `sale_id` INT NOT NULL,
    `product_id` INT NOT NULL,
    `batch_id` INT NULL,
    `quantity` INT NOT NULL,
    `unit_price` DECIMAL(10, 2) NOT NULL,
    `unit_cost` DECIMAL(10, 2) NOT NULL,
    `subtotal` DECIMAL(10, 2) NOT NULL,
    CONSTRAINT `fk_sitem_sale` FOREIGN KEY (`sale_id`) REFERENCES `sales` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_sitem_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`),
    CONSTRAINT `fk_sitem_batch` FOREIGN KEY (`batch_id`) REFERENCES `inventory_batches` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 11. Returns Table
DROP TABLE IF EXISTS `returns`;
CREATE TABLE `returns` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `return_number` VARCHAR(50) NOT NULL UNIQUE,
    `sale_id` INT NOT NULL,
    `cashier_id` INT NOT NULL,
    `return_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `total_refund_amount` DECIMAL(10, 2) NOT NULL,
    `notes` TEXT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_return_sale` FOREIGN KEY (`sale_id`) REFERENCES `sales` (`id`),
    CONSTRAINT `fk_return_cashier` FOREIGN KEY (`cashier_id`) REFERENCES `users` (`id`),
    INDEX `idx_return_num` (`return_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 12. Return Items Table
DROP TABLE IF EXISTS `return_items`;
CREATE TABLE `return_items` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `return_id` INT NOT NULL,
    `sale_item_id` INT NOT NULL,
    `product_id` INT NOT NULL,
    `quantity` INT NOT NULL,
    `refund_amount` DECIMAL(10, 2) NOT NULL,
    `condition` ENUM('RESELLABLE', 'DAMAGED', 'EXPIRED') NOT NULL DEFAULT 'RESELLABLE',
    `reason` VARCHAR(255) NULL,
    CONSTRAINT `fk_ritem_return` FOREIGN KEY (`return_id`) REFERENCES `returns` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_ritem_saleitem` FOREIGN KEY (`sale_item_id`) REFERENCES `sale_items` (`id`),
    CONSTRAINT `fk_ritem_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 13. Stock Movements Audit Table
DROP TABLE IF EXISTS `stock_movements`;
CREATE TABLE `stock_movements` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `product_id` INT NOT NULL,
    `batch_id` INT NULL,
    `movement_type` ENUM('SALE', 'PURCHASE_RECEIPT', 'CUSTOMER_RETURN', 'DAMAGE_WASTAGE', 'EXPIRED_WASTAGE', 'MANUAL_ADJUSTMENT') NOT NULL,
    `reference_id` VARCHAR(50) NULL,
    `quantity_change` INT NOT NULL,
    `quantity_after` INT NOT NULL,
    `notes` TEXT NULL,
    `created_by` INT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_move_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_move_batch` FOREIGN KEY (`batch_id`) REFERENCES `inventory_batches` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_move_user` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
    INDEX `idx_move_type` (`movement_type`),
    INDEX `idx_move_date` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 14. Expenses Table
DROP TABLE IF EXISTS `expenses`;
CREATE TABLE `expenses` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `title` VARCHAR(100) NOT NULL,
    `category` ENUM('RENT', 'ELECTRICITY', 'SALARY', 'MAINTENANCE', 'SUPPLIES', 'OTHER') NOT NULL,
    `amount` DECIMAL(10, 2) NOT NULL,
    `expense_date` DATE NOT NULL,
    `notes` TEXT NULL,
    `created_by` INT NOT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_expense_user` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`),
    INDEX `idx_exp_date` (`expense_date`),
    INDEX `idx_exp_cat` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 15. Notifications Table
DROP TABLE IF EXISTS `notifications`;
CREATE TABLE `notifications` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `type` ENUM('LOW_STOCK', 'OUT_OF_STOCK', 'EXPIRY_NEAR', 'EXPIRED', 'SYSTEM') NOT NULL,
    `title` VARCHAR(100) NOT NULL DEFAULT 'Inventory Alert',
    `message` TEXT NOT NULL,
    `product_id` INT NULL,
    `is_read` BOOLEAN NOT NULL DEFAULT FALSE,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_notif_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE,
    INDEX `idx_notif_read` (`is_read`),
    INDEX `idx_notif_type` (`type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 16. Audit Logs Table
DROP TABLE IF EXISTS `audit_logs`;
CREATE TABLE `audit_logs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL,
    `action` VARCHAR(100) NOT NULL,
    `module` VARCHAR(50) NOT NULL,
    `details` TEXT NULL,
    `ip_address` VARCHAR(50) NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_audit_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    INDEX `idx_audit_module` (`module`),
    INDEX `idx_audit_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
