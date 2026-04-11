SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE DATABASE IF NOT EXISTS `stock_pool` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `stock_pool`;

CREATE TABLE IF NOT EXISTS `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `email` varchar(100) NOT NULL,
  `hashed_password` varchar(255) NOT NULL,
  `is_active` tinyint(1) DEFAULT '1',
  `is_superuser` tinyint(1) DEFAULT '0',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `data_sources` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL COMMENT '数据源名称',
  `website_url` varchar(500) NOT NULL COMMENT '网站URL',
  `login_type` varchar(50) NOT NULL COMMENT '登录类型',
  `login_config` json COMMENT '登录配置',
  `data_format` varchar(50) COMMENT '数据格式',
  `extraction_config` json COMMENT '数据提取配置',
  `cookies` text COMMENT 'Cookie数据',
  `is_active` tinyint(1) DEFAULT '1' COMMENT '是否启用',
  `last_login_time` datetime COMMENT '最后登录时间',
  `last_fetch_time` datetime COMMENT '最后抓取时间',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `rules` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL COMMENT '规则名称',
  `description` text COMMENT '规则描述',
  `natural_language` text NOT NULL COMMENT '自然语言规则',
  `excel_formula` text COMMENT 'Excel公式',
  `filter_conditions` json COMMENT '筛选条件',
  `priority` int DEFAULT '0' COMMENT '优先级',
  `is_active` tinyint(1) DEFAULT '1' COMMENT '是否启用',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tasks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL COMMENT '任务名称',
  `data_source_ids` json COMMENT '数据源ID列表',
  `rule_ids` json COMMENT '规则ID列表',
  `schedule_type` varchar(50) DEFAULT 'manual' COMMENT '调度类型',
  `schedule_config` json COMMENT '调度配置',
  `status` varchar(50) DEFAULT 'pending' COMMENT '任务状态',
  `last_run_time` datetime COMMENT '最后运行时间',
  `next_run_time` datetime COMMENT '下次运行时间',
  `is_active` tinyint(1) DEFAULT '1' COMMENT '是否启用',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `execution_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `task_id` int NOT NULL COMMENT '任务ID',
  `status` varchar(50) NOT NULL COMMENT '执行状态',
  `start_time` datetime COMMENT '开始时间',
  `end_time` datetime COMMENT '结束时间',
  `duration` float COMMENT '执行时长(秒)',
  `records_processed` int COMMENT '处理记录数',
  `error_message` text COMMENT '错误信息',
  `output_file` varchar(500) COMMENT '输出文件路径',
  `details` json COMMENT '执行详情',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_task_id` (`task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `stock_pools` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL COMMENT '选股池名称',
  `task_id` int COMMENT '生成任务ID',
  `file_path` varchar(500) COMMENT 'Excel文件路径',
  `total_stocks` int COMMENT '股票总数',
  `data` json COMMENT '股票数据',
  `is_active` tinyint(1) DEFAULT '1' COMMENT '是否启用',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_task_id` (`task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workflows` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL COMMENT '工作流名称',
  `description` text COMMENT '工作流描述',
  `steps` json COMMENT '工作流步骤配置',
  `status` varchar(50) DEFAULT 'active' COMMENT '状态',
  `last_run_time` datetime COMMENT '最后运行时间',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
