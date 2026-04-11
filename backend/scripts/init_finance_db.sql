-- 金融数据平台数据库初始化脚本
-- 数据库: finance_data

-- 创建数据库
CREATE DATABASE IF NOT EXISTS `finance_data` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `finance_data`;

-- ==================== 维度表 ====================

-- 股票维度表
CREATE TABLE IF NOT EXISTS `dim_stock` (
    `stock_code` VARCHAR(10) PRIMARY KEY COMMENT '股票代码',
    `stock_name` VARCHAR(100) COMMENT '股票名称',
    `listing_date` DATE COMMENT '上市日期',
    `delist_date` DATE COMMENT '退市日期',
    `exchange_code` VARCHAR(10) COMMENT '交易所代码(SH/SZ/BJ)',
    `industry_code` VARCHAR(20) COMMENT '行业代码',
    `industry_name` VARCHAR(100) COMMENT '行业名称',
    `concept_codes` JSON COMMENT '概念板块代码列表',
    `is_active` TINYINT DEFAULT 1 COMMENT '是否活跃',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_exchange` (`exchange_code`),
    INDEX `idx_industry` (`industry_code`),
    INDEX `idx_listing_date` (`listing_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票基础信息表';

-- 行业维度表
CREATE TABLE IF NOT EXISTS `dim_industry` (
    `industry_code` VARCHAR(20) PRIMARY KEY COMMENT '行业代码',
    `industry_name` VARCHAR(100) COMMENT '行业名称',
    `level` INT COMMENT '层级(1/2/3)',
    `parent_code` VARCHAR(20) COMMENT '父级代码',
    `source` VARCHAR(20) DEFAULT 'akshare' COMMENT '数据来源'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='行业分类表';

-- 概念板块维度表
CREATE TABLE IF NOT EXISTS `dim_concept` (
    `concept_code` VARCHAR(20) PRIMARY KEY COMMENT '概念板块代码',
    `concept_name` VARCHAR(100) COMMENT '概念板块名称',
    `source` VARCHAR(20) DEFAULT 'akshare' COMMENT '数据来源',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='概念板块表';

-- 交易日历表
CREATE TABLE IF NOT EXISTS `dim_calendar` (
    `trade_date` DATE PRIMARY KEY COMMENT '交易日期',
    `is_trading_day` TINYINT DEFAULT 1 COMMENT '是否交易日',
    `year` INT COMMENT '年份',
    `quarter` INT COMMENT '季度',
    `month` INT COMMENT '月份',
    INDEX `idx_year` (`year`),
    INDEX `idx_quarter` (`quarter`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易日历表';

-- 指数/ETF基础信息表
CREATE TABLE IF NOT EXISTS `dim_index` (
    `index_code` VARCHAR(20) PRIMARY KEY COMMENT '指数代码',
    `index_name` VARCHAR(100) COMMENT '指数名称',
    `category` VARCHAR(50) COMMENT '分类(股票指数/债券指数/商品指数)',
    `base_date` DATE COMMENT '基期',
    `base_point` DECIMAL(10,4) COMMENT '基点',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='指数基础信息表';

-- ==================== 事实表 (MySQL) ====================

-- 财务数据事实表
CREATE TABLE IF NOT EXISTS `fact_financial` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `stock_code` VARCHAR(10) NOT NULL COMMENT '股票代码',
    `report_date` DATE NOT NULL COMMENT '报告期',
    `report_type` VARCHAR(20) NOT NULL COMMENT '报告类型(Q1/Q2/Q3/FY)',
    `revenue` DECIMAL(20,4) COMMENT '营业收入(元)',
    `revenue_yoy` DECIMAL(10,4) COMMENT '营收同比(%)',
    `net_profit` DECIMAL(20,4) COMMENT '净利润(元)',
    `net_profit_yoy` DECIMAL(10,4) COMMENT '净利润同比(%)',
    `total_assets` DECIMAL(20,4) COMMENT '总资产',
    `total_liabilities` DECIMAL(20,4) COMMENT '总负债',
    `equity` DECIMAL(20,4) COMMENT '所有者权益',
    `roe` DECIMAL(10,4) COMMENT '净资产收益率(%)',
    `gross_margin` DECIMAL(10,4) COMMENT '毛利率(%)',
    `net_margin` DECIMAL(10,4) COMMENT '净利率(%)',
    `eps` DECIMAL(10,4) COMMENT '每股收益(元)',
    `bps` DECIMAL(10,4) COMMENT '每股净资产(元)',
    `pe_ratio` DECIMAL(10,4) COMMENT '市盈率',
    `pb_ratio` DECIMAL(10,4) COMMENT '市净率',
    `ps_ratio` DECIMAL(10,4) COMMENT '市销率',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_stock_report` (`stock_code`, `report_date`, `report_type`),
    INDEX `idx_report_date` (`report_date`),
    INDEX `idx_roe` (`roe`),
    INDEX `idx_pe` (`pe_ratio`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='财务数据事实表';

-- 基金基础信息表
CREATE TABLE IF NOT EXISTS `dim_fund` (
    `fund_code` VARCHAR(20) PRIMARY KEY COMMENT '基金代码',
    `fund_name` VARCHAR(100) COMMENT '基金名称',
    `fund_type` VARCHAR(50) COMMENT '基金类型(股票型/债券型/混合型/指数型)',
    `manager` VARCHAR(100) COMMENT '基金经理',
    `listing_date` DATE COMMENT '成立日期',
    `is_active` TINYINT DEFAULT 1 COMMENT '是否运作中',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基金基础信息表';

-- 基金持仓表
CREATE TABLE IF NOT EXISTS `fact_fund_holding` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `fund_code` VARCHAR(20) NOT NULL COMMENT '基金代码',
    `fund_name` VARCHAR(100) COMMENT '基金名称',
    `stock_code` VARCHAR(10) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(100) COMMENT '股票名称',
    `report_date` DATE NOT NULL COMMENT '报告期',
    `holding_ratio` DECIMAL(10,4) COMMENT '持仓比例(%)',
    `holding_shares` BIGINT COMMENT '持仓股数',
    `market_value` DECIMAL(20,4) COMMENT '持仓市值(元)',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_fund_stock` (`fund_code`, `stock_code`, `report_date`),
    INDEX `idx_report_date` (`report_date`),
    INDEX `idx_stock_code` (`stock_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基金持仓表';

-- 宏观数据表
CREATE TABLE IF NOT EXISTS `fact_macro` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `indicator_code` VARCHAR(50) NOT NULL COMMENT '指标代码',
    `indicator_name` VARCHAR(100) COMMENT '指标名称',
    `period` VARCHAR(20) NOT NULL COMMENT '周期(D/M/Q/Y)',
    `period_value` VARCHAR(20) NOT NULL COMMENT '周期值(2026Q1/202601等)',
    `value` DECIMAL(20,4) COMMENT '数值',
    `value_yoy` DECIMAL(10,4) COMMENT '同比(%)',
    `value_mom` DECIMAL(10,4) COMMENT '环比(%)',
    `source` VARCHAR(50) DEFAULT 'akshare' COMMENT '数据来源',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_indicator_period` (`indicator_code`, `period`, `period_value`),
    INDEX `idx_period` (`period_value`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='宏观数据表';

-- ==================== 配置与日志表 ====================

-- 数据获取配置表
CREATE TABLE IF NOT EXISTS `config_data_fetch` (
    `id` INT PRIMARY KEY AUTO_INCREMENT,
    `data_type` VARCHAR(50) NOT NULL COMMENT '数据类型(stock_daily/financial/fund_nav等)',
    `source` VARCHAR(20) NOT NULL COMMENT '数据源(akshare)',
    `api_name` VARCHAR(100) COMMENT 'API名称',
    `fetch_frequency` VARCHAR(20) NOT NULL COMMENT '更新频率(hourly/daily/weekly)',
    `time_range_start` VARCHAR(20) COMMENT '时间范围起点',
    `time_range_end` VARCHAR(20) COMMENT '时间范围终点',
    `update_config` JSON COMMENT '更新配置(参数、过滤条件等)',
    `is_enabled` TINYINT DEFAULT 1,
    `last_fetch_time` DATETIME,
    `last_fetch_status` VARCHAR(20),
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_data_type_source` (`data_type`, `source`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据获取配置表';

-- 数据保留策略表
CREATE TABLE IF NOT EXISTS `config_retention_policy` (
    `id` INT PRIMARY KEY AUTO_INCREMENT,
    `data_type` VARCHAR(50) NOT NULL,
    `retention_days` INT NOT NULL COMMENT '保留天数',
    `archive_before_delete` TINYINT DEFAULT 0 COMMENT '删除前是否归档',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_data_type` (`data_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据保留策略表';

-- 数据获取日志表
CREATE TABLE IF NOT EXISTS `log_data_fetch` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `data_type` VARCHAR(50) NOT NULL,
    `source` VARCHAR(20) NOT NULL,
    `start_time` DATETIME NOT NULL,
    `end_time` DATETIME,
    `records_fetched` INT DEFAULT 0,
    `status` VARCHAR(20) NOT NULL,
    `error_message` TEXT,
    `details` JSON,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_data_type` (`data_type`),
    INDEX `idx_status` (`status`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据获取日志表';

-- ==================== 初始化配置数据 ====================

-- 插入默认数据获取配置
INSERT INTO `config_data_fetch` (`data_type`, `source`, `api_name`, `fetch_frequency`, `time_range_start`, `time_range_end`, `update_config`, `is_enabled`)
VALUES
    ('stock_daily', 'akshare', 'stock_zh_a_hist', 'hourly', '2025-01-01', NULL, '{"last_year_frequency": "every_5_days"}', 1),
    ('stock_spot', 'akshare', 'stock_zh_a_spot_em', 'hourly', NULL, NULL, NULL, 1),
    ('financial', 'akshare', 'stock_financial_analysis_indicator_em', 'quarterly', '2024-01-01', NULL, NULL, 1),
    ('fund_nav', 'akshare', 'fund_open_fund_info_em', 'daily', '2025-01-01', NULL, NULL, 1),
    ('index_bar', 'akshare', 'index_zh_a_hist', 'hourly', '2025-01-01', NULL, NULL, 1),
    ('macro', 'akshare', 'macro_china_money_supply', 'daily', '2024-01-01', NULL, NULL, 1)
ON DUPLICATE KEY UPDATE `fetch_frequency` = VALUES(`fetch_frequency`);

-- 插入默认保留策略 (2年 = 730天)
INSERT INTO `config_retention_policy` (`data_type`, `retention_days`, `archive_before_delete`)
VALUES
    ('stock_daily', 730, 0),
    ('stock_spot', 30, 0),
    ('financial', 730, 0),
    ('fund_nav', 730, 0),
    ('index_bar', 730, 0),
    ('macro', 730, 0)
ON DUPLICATE KEY UPDATE `retention_days` = VALUES(`retention_days`);
