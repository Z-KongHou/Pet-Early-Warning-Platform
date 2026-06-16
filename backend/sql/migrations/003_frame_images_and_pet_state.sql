-- Create frame_images and pet_state tables.
-- Idempotent: safe to re-run.

USE yingshi_database;

-- 1. frame_images table
CREATE TABLE IF NOT EXISTS `frame_images` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL COMMENT 'Owner user ID',
  `camera_id` VARCHAR(64) NOT NULL COMMENT 'Camera ID',
  `request_id` VARCHAR(128) NOT NULL COMMENT 'Request ID',
  `original_filename` VARCHAR(255) DEFAULT NULL COMMENT 'Original filename',
  `file_path` VARCHAR(512) NOT NULL COMMENT 'File storage path',
  `file_size` INT DEFAULT NULL COMMENT 'File size (bytes)',
  `image_timestamp` DATETIME NOT NULL COMMENT 'Image capture timestamp',
  `source` VARCHAR(32) DEFAULT 'upload' COMMENT 'Source: upload/capture',
  `status` VARCHAR(32) DEFAULT 'stored' COMMENT 'Status: stored/sampled/skipped/analyzed',
  `last_accessed_at` DATETIME NOT NULL COMMENT 'Last accessed time for LRU eviction',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at',
  `has_pet` TINYINT DEFAULT NULL COMMENT 'Pet detected: 0 no / 1 yes',
  `position_x` INT DEFAULT NULL,
  `position_y` INT DEFAULT NULL,
  `position_width` INT DEFAULT NULL,
  `position_height` INT DEFAULT NULL,
  `confidence` DOUBLE DEFAULT NULL COMMENT 'Detection confidence',
  `food_status` VARCHAR(32) DEFAULT NULL COMMENT 'Food bowl status',
  `analyzed_at` DATETIME DEFAULT NULL COMMENT 'Analysis completion time',
  PRIMARY KEY (`id`),
  KEY `idx_frame_camera_ts` (`camera_id`, `image_timestamp`),
  KEY `idx_frame_camera_lru` (`camera_id`, `last_accessed_at`),
  KEY `idx_frame_user_id` (`user_id`),
  CONSTRAINT `fk_frame_images_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Frame images for AI analysis';

-- 2. pet_state table
CREATE TABLE IF NOT EXISTS `pet_state` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL COMMENT 'Owner user ID',
  `camera_id` VARCHAR(64) NOT NULL COMMENT 'Camera ID (unique)',
  `last_position_x` INT DEFAULT NULL,
  `last_position_y` INT DEFAULT NULL,
  `last_position_width` INT DEFAULT NULL,
  `last_position_height` INT DEFAULT NULL,
  `last_eating_time` DATETIME DEFAULT NULL COMMENT 'Last detected eating time',
  `stationary_start_time` DATETIME NOT NULL COMMENT 'When stationary period started',
  `food_bowl_position_x` INT DEFAULT NULL,
  `food_bowl_position_y` INT DEFAULT NULL,
  `food_bowl_position_width` INT DEFAULT NULL,
  `food_bowl_position_height` INT DEFAULT NULL,
  `total_analyses` INT DEFAULT 0 COMMENT 'Total analysis count for this camera',
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_pet_state_camera` (`camera_id`),
  KEY `idx_pet_state_user_id` (`user_id`),
  CONSTRAINT `fk_pet_state_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Per-camera pet state tracking';
