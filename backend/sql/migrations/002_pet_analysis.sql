-- Create pet_analysis table for scheduled AI capture results.
-- Idempotent: safe to re-run.

USE yingshi_database;

SET @table_exists := (
  SELECT COUNT(*) FROM information_schema.TABLES
  WHERE TABLE_SCHEMA = 'yingshi_database' AND TABLE_NAME = 'pet_analysis'
);
SET @sql := IF(
  @table_exists = 0,
  'CREATE TABLE `pet_analysis` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `user_id` INT DEFAULT NULL,
    `camera_id` VARCHAR(64) NOT NULL,
    `timestamp` DATETIME NOT NULL,
    `has_pet` TINYINT NOT NULL DEFAULT 0,
    `movement_state` VARCHAR(20) DEFAULT ''stationary'',
    `food_state` VARCHAR(20) DEFAULT ''unknown'',
    `position_x` INT DEFAULT NULL,
    `position_y` INT DEFAULT NULL,
    `position_width` INT DEFAULT NULL,
    `position_height` INT DEFAULT NULL,
    `confidence` DOUBLE DEFAULT 0,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_camera_timestamp` (`camera_id`, `timestamp`),
    KEY `idx_pet_analysis_user_id` (`user_id`),
    CONSTRAINT `fk_pet_analysis_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT=''Pet analysis records''',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
