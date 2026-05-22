-- 仓鼠健康预警 AIoT 系统 - 数据库初始化脚本

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS yingshi_database DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE yingshi_database;

-- 一、用户表 users
CREATE TABLE IF NOT EXISTS `users` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `username` VARCHAR(50) NOT NULL COMMENT '用户名',
  `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希（BCrypt）',
  `email` VARCHAR(100) DEFAULT NULL COMMENT '邮箱',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  `updated_at` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- 二、仓鼠信息表 hamsters
CREATE TABLE IF NOT EXISTS `hamsters` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `name` VARCHAR(50) NOT NULL COMMENT '名字',
  `breed` VARCHAR(50) DEFAULT NULL COMMENT '品种',
  `birth_date` DATE DEFAULT NULL COMMENT '出生日期',
  `gender` TINYINT DEFAULT 0 COMMENT '性别：0未知/1公/2母',
  `weight` DECIMAL(5,2) DEFAULT NULL COMMENT '当前体重(g)',
  `avatar` VARCHAR(255) DEFAULT NULL COMMENT '头像URL',
  `remark` VARCHAR(500) DEFAULT NULL COMMENT '备注',
  `health_status` TINYINT DEFAULT 0 COMMENT '健康状态：0正常/1异常/2治疗中',
  `is_deleted` TINYINT DEFAULT 0 COMMENT '软删除标记：0否/1是',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  `updated_at` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  `deleted_at` DATETIME DEFAULT NULL COMMENT '删除时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `idx_hamsters_name_deleted` (`name`, `is_deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='仓鼠信息表';

-- 三、摄像头表 cameras
CREATE TABLE IF NOT EXISTS `cameras` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `hamster_id` INT DEFAULT NULL COMMENT '关联仓鼠ID',
  `name` VARCHAR(50) NOT NULL COMMENT '摄像头名称',
  `device_key` VARCHAR(100) NOT NULL COMMENT '萤石设备序列号',
  `channel_no` INT DEFAULT 1 COMMENT '通道号',
  `access_token` TEXT DEFAULT NULL COMMENT '摄像头访问令牌（加密存储）',
  `token_expires` DATETIME DEFAULT NULL COMMENT '令牌过期时间（UTC）',
  `last_online_time` DATETIME DEFAULT NULL COMMENT '最后在线时间（UTC）',
  `online_status` TINYINT DEFAULT 0 COMMENT '在线状态：0离线/1在线',
  `recording_enabled` TINYINT DEFAULT 0 COMMENT '录像开关：0关闭/1开启',
  `is_deleted` TINYINT DEFAULT 0 COMMENT '软删除标记：0否/1是',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  `updated_at` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  `deleted_at` DATETIME DEFAULT NULL COMMENT '删除时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `idx_cameras_hamster_deleted` (`hamster_id`, `is_deleted`),
  CONSTRAINT `fk_cameras_hamster` FOREIGN KEY (`hamster_id`) REFERENCES `hamsters` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='摄像头表';

-- 四、用户摄像头映射表 user_cameras
CREATE TABLE IF NOT EXISTS `user_cameras` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `user_id` INT NOT NULL COMMENT '用户ID',
  `camera_id` INT NOT NULL COMMENT '摄像头ID',
  `is_deleted` TINYINT DEFAULT 0 COMMENT '软删除标记：0否/1是',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  `updated_at` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  `deleted_at` DATETIME DEFAULT NULL COMMENT '删除时间（UTC）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_camera` (`user_id`, `camera_id`, `is_deleted`),
  KEY `idx_user_cameras_user_camera` (`user_id`, `camera_id`, `is_deleted`),
  CONSTRAINT `fk_usercameras_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_usercameras_camera` FOREIGN KEY (`camera_id`) REFERENCES `cameras` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户摄像头映射表';

-- 五、预警记录表 alerts
CREATE TABLE IF NOT EXISTS `alerts` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `hamster_id` INT DEFAULT NULL COMMENT '关联仓鼠ID',
  `activity_status` VARCHAR(20) NOT NULL COMMENT '活动状态：normal/low/high',
  `activity_score` INT NOT NULL COMMENT '活动评分(0-100)',
  `threshold` INT NOT NULL COMMENT '触发阈值',
  `image_url` VARCHAR(255) DEFAULT NULL COMMENT '截图URL',
  `status` TINYINT DEFAULT 0 COMMENT '处理状态：0未处理/1已读/2已处理',
  `handler_id` INT DEFAULT NULL COMMENT '处理人ID',
  `handle_remark` VARCHAR(500) DEFAULT NULL COMMENT '处理备注',
  `is_deleted` TINYINT DEFAULT 0 COMMENT '软删除标记：0否/1是',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '预警时间（UTC）',
  `handled_at` DATETIME DEFAULT NULL COMMENT '处理时间（UTC）',
  `deleted_at` DATETIME DEFAULT NULL COMMENT '删除时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `idx_alerts_hamster_status_deleted` (`hamster_id`, `status`, `is_deleted`, `created_at`),
  KEY `idx_alerts_created_at` (`created_at`),
  CONSTRAINT `fk_alerts_hamster` FOREIGN KEY (`hamster_id`) REFERENCES `hamsters` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_alerts_handler` FOREIGN KEY (`handler_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='预警记录表';

-- 六、站内信表 messages
CREATE TABLE IF NOT EXISTS `messages` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `hamster_id` INT DEFAULT NULL COMMENT '关联仓鼠ID',
  `alert_id` INT DEFAULT NULL COMMENT '关联预警ID',
  `user_id` INT NOT NULL COMMENT '接收用户ID',
  `title` VARCHAR(100) NOT NULL COMMENT '消息标题',
  `content` TEXT NOT NULL COMMENT '消息内容',
  `is_read` TINYINT DEFAULT 0 COMMENT '已读状态：0未读/1已读',
  `is_deleted` TINYINT DEFAULT 0 COMMENT '软删除标记：0否/1是',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  `updated_at` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  `deleted_at` DATETIME DEFAULT NULL COMMENT '删除时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `idx_messages_user_read_deleted` (`user_id`, `is_read`, `is_deleted`, `created_at`),
  CONSTRAINT `fk_messages_hamster` FOREIGN KEY (`hamster_id`) REFERENCES `hamsters` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_messages_alert` FOREIGN KEY (`alert_id`) REFERENCES `alerts` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_messages_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='站内信表';

-- 七、活动量历史表 activity_history
CREATE TABLE IF NOT EXISTS `activity_history` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `hamster_id` INT DEFAULT NULL COMMENT '关联仓鼠ID',
  `camera_id` INT DEFAULT NULL COMMENT '摄像头ID',
  `activity_score` INT NOT NULL COMMENT '活动评分(0-100)',
  `status` VARCHAR(20) NOT NULL COMMENT '活动状态：normal/low/high',
  `analysis_result` TEXT DEFAULT NULL COMMENT 'AI分析详情',
  `image_url` VARCHAR(255) DEFAULT NULL COMMENT '截图URL',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '采样时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `idx_activity_history_hamster_created` (`hamster_id`, `created_at`),
  CONSTRAINT `fk_activity_hamster` FOREIGN KEY (`hamster_id`) REFERENCES `hamsters` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_activity_camera` FOREIGN KEY (`camera_id`) REFERENCES `cameras` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动量历史表';

-- 八、系统配置表 settings
CREATE TABLE IF NOT EXISTS `settings` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `key_name` VARCHAR(50) NOT NULL COMMENT '配置键',
  `key_value` TEXT DEFAULT NULL COMMENT '配置值',
  `description` VARCHAR(100) DEFAULT NULL COMMENT '说明',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  `updated_at` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_key_name` (`key_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表';

-- 插入初始配置数据
INSERT INTO `settings` (`key_name`, `key_value`, `description`) VALUES
('activity_interval', '300', '采样间隔（秒）'),
('low_activity_threshold', '30', '低活动阈值'),
('high_activity_threshold', '80', '高活动阈值'),
('deepseek_api_key', '', 'API密钥（加密存储）');

-- 插入默认管理员用户（密码: password123，与前端登录页 Demo 一致）
-- BCrypt ($2b$, cost 10) 由 Spring 同算法生成，可用 bcrypt 库校验
INSERT INTO `users` (`username`, `password_hash`, `email`) VALUES
('admin', '$2b$10$o6NHJxGubUj/zbJA73CcPecu04qRpbjtkgpVdirdOJpGYeQ4rIJRe', 'admin@example.com');