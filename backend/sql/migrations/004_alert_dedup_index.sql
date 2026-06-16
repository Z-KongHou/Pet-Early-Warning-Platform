-- 004: dedup index for alert creation queries
-- Supports AlertService.hasDuplicateWithinWindow(hamsterId, status, window)
-- Idempotent: safe to re-run.

USE yingshi_database;

SET @idx_exists := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = 'yingshi_database'
    AND TABLE_NAME = 'alerts'
    AND INDEX_NAME = 'idx_alerts_dedup'
);

SET @sql := IF(@idx_exists = 0,
  'CREATE INDEX idx_alerts_dedup ON alerts (hamster_id, activity_status, created_at, is_deleted)',
  'SELECT "Index idx_alerts_dedup already exists, skipping." AS msg'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
