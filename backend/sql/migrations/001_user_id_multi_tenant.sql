-- Add per-user isolation: rename users.id -> user_id, add user_id FK columns.
-- Idempotent: safe to re-run.

USE yingshi_database;

-- 1. Drop FKs that reference users(id)
SET @fk_exists := (
  SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = 'yingshi_database' AND CONSTRAINT_NAME = 'fk_alerts_handler'
);
SET @sql := IF(@fk_exists > 0, 'ALTER TABLE alerts DROP FOREIGN KEY fk_alerts_handler', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @fk_exists := (
  SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = 'yingshi_database' AND CONSTRAINT_NAME = 'fk_messages_user'
);
SET @sql := IF(@fk_exists > 0, 'ALTER TABLE messages DROP FOREIGN KEY fk_messages_user', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @fk_exists := (
  SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = 'yingshi_database' AND CONSTRAINT_NAME = 'fk_usercameras_user'
);
SET @sql := IF(@fk_exists > 0, 'ALTER TABLE user_cameras DROP FOREIGN KEY fk_usercameras_user', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2. Rename users.id -> user_id
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'yingshi_database' AND TABLE_NAME = 'users' AND COLUMN_NAME = 'id'
);
SET @sql := IF(@col_exists > 0,
  'ALTER TABLE users CHANGE COLUMN id user_id INT NOT NULL AUTO_INCREMENT COMMENT ''Primary key''',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3. Add user_id columns
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'yingshi_database' AND TABLE_NAME = 'hamsters' AND COLUMN_NAME = 'user_id'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE hamsters ADD COLUMN user_id INT DEFAULT NULL AFTER id',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'yingshi_database' AND TABLE_NAME = 'cameras' AND COLUMN_NAME = 'user_id'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE cameras ADD COLUMN user_id INT DEFAULT NULL AFTER id',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'yingshi_database' AND TABLE_NAME = 'alerts' AND COLUMN_NAME = 'user_id'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE alerts ADD COLUMN user_id INT DEFAULT NULL AFTER id',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'yingshi_database' AND TABLE_NAME = 'activity_history' AND COLUMN_NAME = 'user_id'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE activity_history ADD COLUMN user_id INT DEFAULT NULL AFTER id',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'yingshi_database' AND TABLE_NAME = 'settings' AND COLUMN_NAME = 'user_id'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE settings ADD COLUMN user_id INT DEFAULT NULL AFTER id',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 4. Backfill existing rows to admin user (user_id = 1)
UPDATE hamsters SET user_id = 1 WHERE user_id IS NULL;
UPDATE cameras SET user_id = 1 WHERE user_id IS NULL;
UPDATE alerts SET user_id = 1 WHERE user_id IS NULL;
UPDATE activity_history SET user_id = 1 WHERE user_id IS NULL;
UPDATE settings SET user_id = 1 WHERE user_id IS NULL;

-- 5. settings: per-user unique key
SET @idx_exists := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = 'yingshi_database' AND TABLE_NAME = 'settings' AND INDEX_NAME = 'uk_key_name'
);
SET @sql := IF(@idx_exists > 0, 'ALTER TABLE settings DROP INDEX uk_key_name', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = 'yingshi_database' AND TABLE_NAME = 'settings' AND INDEX_NAME = 'uk_user_key_name'
);
SET @sql := IF(@idx_exists = 0,
  'ALTER TABLE settings ADD UNIQUE KEY uk_user_key_name (user_id, key_name)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 6. Re-create / add foreign keys referencing users(user_id)
SET @fk_exists := (
  SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = 'yingshi_database' AND CONSTRAINT_NAME = 'fk_alerts_handler'
);
SET @sql := IF(@fk_exists = 0,
  'ALTER TABLE alerts ADD CONSTRAINT fk_alerts_handler FOREIGN KEY (handler_id) REFERENCES users(user_id) ON DELETE SET NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @fk_exists := (
  SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = 'yingshi_database' AND CONSTRAINT_NAME = 'fk_messages_user'
);
SET @sql := IF(@fk_exists = 0,
  'ALTER TABLE messages ADD CONSTRAINT fk_messages_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @fk_exists := (
  SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = 'yingshi_database' AND CONSTRAINT_NAME = 'fk_usercameras_user'
);
SET @sql := IF(@fk_exists = 0,
  'ALTER TABLE user_cameras ADD CONSTRAINT fk_usercameras_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @fk_exists := (
  SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = 'yingshi_database' AND CONSTRAINT_NAME = 'fk_hamsters_user'
);
SET @sql := IF(@fk_exists = 0,
  'ALTER TABLE hamsters ADD CONSTRAINT fk_hamsters_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @fk_exists := (
  SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = 'yingshi_database' AND CONSTRAINT_NAME = 'fk_cameras_user'
);
SET @sql := IF(@fk_exists = 0,
  'ALTER TABLE cameras ADD CONSTRAINT fk_cameras_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @fk_exists := (
  SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = 'yingshi_database' AND CONSTRAINT_NAME = 'fk_alerts_user'
);
SET @sql := IF(@fk_exists = 0,
  'ALTER TABLE alerts ADD CONSTRAINT fk_alerts_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @fk_exists := (
  SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = 'yingshi_database' AND CONSTRAINT_NAME = 'fk_activity_history_user'
);
SET @sql := IF(@fk_exists = 0,
  'ALTER TABLE activity_history ADD CONSTRAINT fk_activity_history_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @fk_exists := (
  SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = 'yingshi_database' AND CONSTRAINT_NAME = 'fk_settings_user'
);
SET @sql := IF(@fk_exists = 0,
  'ALTER TABLE settings ADD CONSTRAINT fk_settings_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
