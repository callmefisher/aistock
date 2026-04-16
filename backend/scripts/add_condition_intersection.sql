-- 条件交集功能: Schema 变更
-- 执行时间: 2026-04-16

USE stock_pool;

-- 1. workflows 表增加 date_str 字段
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS date_str VARCHAR(20) DEFAULT '' COMMENT '数据日期' AFTER workflow_type;

-- 2. stock_pools 表增加新字段
ALTER TABLE stock_pools ADD COLUMN IF NOT EXISTS workflow_id INT COMMENT '生成工作流ID' AFTER task_id;
ALTER TABLE stock_pools ADD COLUMN IF NOT EXISTS date_str VARCHAR(20) DEFAULT '' COMMENT '数据日期' AFTER workflow_id;
ALTER TABLE stock_pools ADD COLUMN IF NOT EXISTS filter_conditions JSON COMMENT '过滤条件' AFTER `data`;
ALTER TABLE stock_pools ADD COLUMN IF NOT EXISTS source_types JSON COMMENT '来源工作流类型列表' AFTER filter_conditions;

-- 3. 添加索引
ALTER TABLE stock_pools ADD INDEX IF NOT EXISTS idx_workflow_id (workflow_id);
ALTER TABLE stock_pools ADD INDEX IF NOT EXISTS idx_date_str (date_str);
