-- 数据库迁移脚本：添加 workflow_type 字段
-- 执行时间：2026-04-12
-- 说明：支持工作流类型系统，允许不同类型的工作流使用不同的目录和命名规则

USE stock_pool;

-- 检查字段是否已存在
SET @column_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'stock_pool'
    AND TABLE_NAME = 'workflows'
    AND COLUMN_NAME = 'workflow_type'
);

-- 如果字段不存在，则添加
SET @sql = IF(@column_exists = 0,
    'ALTER TABLE workflows ADD COLUMN workflow_type VARCHAR(50) DEFAULT '''' COMMENT ''工作流类型: 空/并购重组/股权转让/...'' AFTER description',
    'SELECT ''workflow_type字段已存在，跳过迁移'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 验证迁移结果
SELECT
    COLUMN_NAME,
    COLUMN_TYPE,
    IS_NULLABLE,
    COLUMN_DEFAULT,
    COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'stock_pool'
AND TABLE_NAME = 'workflows'
AND COLUMN_NAME = 'workflow_type';
