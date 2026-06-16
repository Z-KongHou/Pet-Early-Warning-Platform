-- Hamster Health Early Warning AIoT System - Database initialization script

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS yingshi_database DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE yingshi_database;

-- 1. users table
CREATE TABLE IF NOT EXISTS `users` (
  `user_id` INT NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
  `username` VARCHAR(50) NOT NULL COMMENT 'Username',
  `password_hash` VARCHAR(255) NOT NULL COMMENT 'Password hash (BCrypt)',
  `email` VARCHAR(100) DEFAULT NULL COMMENT 'Email',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at (UTC)',
  `updated_at` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated at (UTC)',
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `uk_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Users table';

-- 2. hamsters table
CREATE TABLE IF NOT EXISTS `hamsters` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
  `user_id` INT DEFAULT NULL COMMENT 'Owner user ID',
  `name` VARCHAR(50) NOT NULL COMMENT 'Name',
  `breed` VARCHAR(50) DEFAULT NULL COMMENT 'Breed',
  `birth_date` DATE DEFAULT NULL COMMENT 'Birth date',
  `gender` TINYINT DEFAULT 0 COMMENT 'Gender: 0 unknown / 1 male / 2 female',
  `weight` DECIMAL(5,2) DEFAULT NULL COMMENT 'Current weight (g)',
  `avatar` VARCHAR(255) DEFAULT NULL COMMENT 'Avatar URL',
  `remark` VARCHAR(500) DEFAULT NULL COMMENT 'Remark',
  `health_status` TINYINT DEFAULT 0 COMMENT 'Health status: 0 normal / 1 abnormal / 2 under treatment',
  `is_deleted` TINYINT DEFAULT 0 COMMENT 'Soft delete flag: 0 no / 1 yes',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at (UTC)',
  `updated_at` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated at (UTC)',
  `deleted_at` DATETIME DEFAULT NULL COMMENT 'Deleted at (UTC)',
  PRIMARY KEY (`id`),
  KEY `idx_hamsters_name_deleted` (`name`, `is_deleted`),
  KEY `idx_hamsters_user_id` (`user_id`),
  CONSTRAINT `fk_hamsters_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Hamsters table';

-- 3. cameras table
CREATE TABLE IF NOT EXISTS `cameras` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
  `user_id` INT DEFAULT NULL COMMENT 'Owner user ID',
  `hamster_id` INT DEFAULT NULL COMMENT 'Linked hamster ID',
  `name` VARCHAR(50) NOT NULL COMMENT 'Camera name',
  `device_key` VARCHAR(100) NOT NULL COMMENT 'Ezviz device serial number',
  `channel_no` INT DEFAULT 1 COMMENT 'Channel number',
  `access_token` TEXT DEFAULT NULL COMMENT 'Camera access token (encrypted storage)',
  `token_expires` DATETIME DEFAULT NULL COMMENT 'Token expiry time (UTC)',
  `last_online_time` DATETIME DEFAULT NULL COMMENT 'Last online time (UTC)',
  `online_status` TINYINT DEFAULT 0 COMMENT 'Online status: 0 offline / 1 online',
  `recording_enabled` TINYINT DEFAULT 0 COMMENT 'Recording switch: 0 off / 1 on',
  `is_deleted` TINYINT DEFAULT 0 COMMENT 'Soft delete flag: 0 no / 1 yes',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at (UTC)',
  `updated_at` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated at (UTC)',
  `deleted_at` DATETIME DEFAULT NULL COMMENT 'Deleted at (UTC)',
  PRIMARY KEY (`id`),
  KEY `idx_cameras_hamster_deleted` (`hamster_id`, `is_deleted`),
  KEY `idx_cameras_user_id` (`user_id`),
  CONSTRAINT `fk_cameras_hamster` FOREIGN KEY (`hamster_id`) REFERENCES `hamsters` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_cameras_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Cameras table';

-- 4. user_cameras mapping table
CREATE TABLE IF NOT EXISTS `user_cameras` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
  `user_id` INT NOT NULL COMMENT 'User ID',
  `camera_id` INT NOT NULL COMMENT 'Camera ID',
  `is_deleted` TINYINT DEFAULT 0 COMMENT 'Soft delete flag: 0 no / 1 yes',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at (UTC)',
  `updated_at` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated at (UTC)',
  `deleted_at` DATETIME DEFAULT NULL COMMENT 'Deleted at (UTC)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_camera` (`user_id`, `camera_id`, `is_deleted`),
  KEY `idx_user_cameras_user_camera` (`user_id`, `camera_id`, `is_deleted`),
  CONSTRAINT `fk_usercameras_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_usercameras_camera` FOREIGN KEY (`camera_id`) REFERENCES `cameras` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='User-camera mapping table';

-- 5. alerts table
CREATE TABLE IF NOT EXISTS `alerts` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
  `user_id` INT DEFAULT NULL COMMENT 'Owner user ID',
  `hamster_id` INT DEFAULT NULL COMMENT 'Linked hamster ID',
  `activity_status` VARCHAR(20) NOT NULL COMMENT 'Activity status: normal/low/high',
  `activity_score` INT NOT NULL COMMENT 'Activity score (0-100)',
  `threshold` INT NOT NULL COMMENT 'Trigger threshold',
  `image_url` VARCHAR(255) DEFAULT NULL COMMENT 'Screenshot URL',
  `status` TINYINT DEFAULT 0 COMMENT 'Handle status: 0 pending / 1 read / 2 handled',
  `handler_id` INT DEFAULT NULL COMMENT 'Handler user ID',
  `handle_remark` VARCHAR(500) DEFAULT NULL COMMENT 'Handle remark',
  `is_deleted` TINYINT DEFAULT 0 COMMENT 'Soft delete flag: 0 no / 1 yes',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Alert time (UTC)',
  `handled_at` DATETIME DEFAULT NULL COMMENT 'Handled at (UTC)',
  `deleted_at` DATETIME DEFAULT NULL COMMENT 'Deleted at (UTC)',
  PRIMARY KEY (`id`),
  KEY `idx_alerts_hamster_status_deleted` (`hamster_id`, `status`, `is_deleted`, `created_at`),
  KEY `idx_alerts_created_at` (`created_at`),
  KEY `idx_alerts_user_id` (`user_id`),
  CONSTRAINT `fk_alerts_hamster` FOREIGN KEY (`hamster_id`) REFERENCES `hamsters` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_alerts_handler` FOREIGN KEY (`handler_id`) REFERENCES `users` (`user_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_alerts_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Alerts table';

-- 6. messages table
CREATE TABLE IF NOT EXISTS `messages` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
  `hamster_id` INT DEFAULT NULL COMMENT 'Linked hamster ID',
  `alert_id` INT DEFAULT NULL COMMENT 'Linked alert ID',
  `user_id` INT NOT NULL COMMENT 'Recipient user ID',
  `title` VARCHAR(100) NOT NULL COMMENT 'Message title',
  `content` TEXT NOT NULL COMMENT 'Message content',
  `is_read` TINYINT DEFAULT 0 COMMENT 'Read status: 0 unread / 1 read',
  `is_deleted` TINYINT DEFAULT 0 COMMENT 'Soft delete flag: 0 no / 1 yes',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at (UTC)',
  `updated_at` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated at (UTC)',
  `deleted_at` DATETIME DEFAULT NULL COMMENT 'Deleted at (UTC)',
  PRIMARY KEY (`id`),
  KEY `idx_messages_user_read_deleted` (`user_id`, `is_read`, `is_deleted`, `created_at`),
  CONSTRAINT `fk_messages_hamster` FOREIGN KEY (`hamster_id`) REFERENCES `hamsters` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_messages_alert` FOREIGN KEY (`alert_id`) REFERENCES `alerts` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_messages_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Messages table';

-- 7. activity_history table
CREATE TABLE IF NOT EXISTS `activity_history` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
  `user_id` INT DEFAULT NULL COMMENT 'Owner user ID',
  `hamster_id` INT DEFAULT NULL COMMENT 'Linked hamster ID',
  `camera_id` INT DEFAULT NULL COMMENT 'Camera ID',
  `activity_score` INT NOT NULL COMMENT 'Activity score (0-100)',
  `status` VARCHAR(20) NOT NULL COMMENT 'Activity status: normal/low/high',
  `analysis_result` TEXT DEFAULT NULL COMMENT 'AI analysis details',
  `image_url` VARCHAR(255) DEFAULT NULL COMMENT 'Screenshot URL',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Sample time (UTC)',
  PRIMARY KEY (`id`),
  KEY `idx_activity_history_hamster_created` (`hamster_id`, `created_at`),
  KEY `idx_activity_history_user_id` (`user_id`),
  CONSTRAINT `fk_activity_hamster` FOREIGN KEY (`hamster_id`) REFERENCES `hamsters` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_activity_camera` FOREIGN KEY (`camera_id`) REFERENCES `cameras` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_activity_history_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Activity history table';

-- 8. settings table
CREATE TABLE IF NOT EXISTS `settings` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
  `user_id` INT DEFAULT NULL COMMENT 'Owner user ID',
  `key_name` VARCHAR(50) NOT NULL COMMENT 'Setting key',
  `key_value` TEXT DEFAULT NULL COMMENT 'Setting value',
  `description` VARCHAR(100) DEFAULT NULL COMMENT 'Description',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at (UTC)',
  `updated_at` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated at (UTC)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_key_name` (`user_id`, `key_name`),
  KEY `idx_settings_user_id` (`user_id`),
  CONSTRAINT `fk_settings_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='System settings table';

-- Insert initial settings for admin (user_id = 1)
INSERT INTO `settings` (`user_id`, `key_name`, `key_value`, `description`) VALUES
(1, 'activity_interval', '300', 'Sampling interval (seconds)'),
(1, 'low_activity_threshold', '30', 'Low activity threshold'),
(1, 'high_activity_threshold', '80', 'High activity threshold'),
(1, 'deepseek_api_key', '', 'API key (encrypted storage)');

-- 9. pet_analysis table (scheduled AI capture results)
CREATE TABLE IF NOT EXISTS `pet_analysis` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` INT DEFAULT NULL COMMENT 'Owner user ID',
  `camera_id` VARCHAR(64) NOT NULL COMMENT 'Camera ID',
  `timestamp` DATETIME NOT NULL COMMENT 'Analysis time (UTC)',
  `has_pet` TINYINT NOT NULL DEFAULT 0 COMMENT 'Pet detected: 0 no / 1 yes',
  `movement_state` VARCHAR(20) DEFAULT 'stationary' COMMENT 'Movement: moving/stationary',
  `food_state` VARCHAR(20) DEFAULT 'unknown' COMMENT 'Food bowl state',
  `position_x` INT DEFAULT NULL,
  `position_y` INT DEFAULT NULL,
  `position_width` INT DEFAULT NULL,
  `position_height` INT DEFAULT NULL,
  `confidence` DOUBLE DEFAULT 0,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at (UTC)',
  PRIMARY KEY (`id`),
  KEY `idx_camera_timestamp` (`camera_id`, `timestamp`),
  KEY `idx_pet_analysis_user_id` (`user_id`),
  CONSTRAINT `fk_pet_analysis_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Pet analysis records';

-- 10. frame_images table (AI service frame storage)
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

-- 11. pet_state table (per-camera pet state tracking)
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

-- Insert default admin user (password: password123, matches frontend login demo)
-- BCrypt ($2b$, cost 10) generated with the same algorithm as Spring; verify with any bcrypt library
INSERT INTO `users` (`username`, `password_hash`, `email`) VALUES
('admin', '$2b$10$o6NHJxGubUj/zbJA73CcPecu04qRpbjtkgpVdirdOJpGYeQ4rIJRe', 'admin@example.com');
