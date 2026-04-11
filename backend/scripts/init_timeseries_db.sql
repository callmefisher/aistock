-- TimescaleDB 时序数据表初始化
-- 需要在 finance_data 数据库中执行

-- 启用 TimescaleDB 扩展 (如果还没有)
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- A股每日行情表 (时序数据 - 超表)
CREATE TABLE IF NOT EXISTS fact_daily_bar (
    stock_code VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    open DECIMAL(10,4),
    high DECIMAL(10,4),
    low DECIMAL(10,4),
    close DECIMAL(10,4),
    volume BIGINT COMMENT '成交量(手)',
    amount DECIMAL(20,4) COMMENT '成交额(元)',
    turnover_rate DECIMAL(10,4) COMMENT '换手率(%)',
    amplitude DECIMAL(10,4) COMMENT '振幅(%)',
    change_pct DECIMAL(10,4) COMMENT '涨跌幅(%)',
    change_amount DECIMAL(10,4) COMMENT '涨跌额(元)',
    pre_close DECIMAL(10,4) COMMENT '前收',
    ma5 DECIMAL(10,4) COMMENT '5日均线',
    ma10 DECIMAL(10,4) COMMENT '10日均线',
    ma20 DECIMAL(10,4) COMMENT '20日均线',
    ma30 DECIMAL(10,4) COMMENT '30日均线',
    ma60 DECIMAL(10,4) COMMENT '60日均线',
    ma120 DECIMAL(10,4) COMMENT '120日均线',
    ma250 DECIMAL(10,4) COMMENT '250日均线',
    volume_ratio DECIMAL(10,4) COMMENT '量比',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (stock_code, trade_date)
);

-- 转换为超表
SELECT create_hypertable('fact_daily_bar', 'trade_date', if_not_exists => TRUE);

-- 创建连续聚合策略 (用于加速均线查询)
CREATE MATERIALIZED VIEW IF NOT EXISTS fact_daily_bar_ma_agg
WITH (timescaledb.continuous) AS
SELECT
    stock_code,
    time_bucket('1 day', trade_date) AS bucket,
    AVG(close) AS avg_close,
    AVG(volume) AS avg_volume
FROM fact_daily_bar
GROUP BY stock_code, bucket;

-- 指数行情表
CREATE TABLE IF NOT EXISTS fact_index_bar (
    index_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    open DECIMAL(10,4),
    high DECIMAL(10,4),
    low DECIMAL(10,4),
    close DECIMAL(10,4),
    volume BIGINT,
    amount DECIMAL(20,4),
    change_pct DECIMAL(10,4),
    ma5 DECIMAL(10,4),
    ma10 DECIMAL(10,4),
    ma20 DECIMAL(10,4),
    ma60 DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (index_code, trade_date)
);

SELECT create_hypertable('fact_index_bar', 'trade_date', if_not_exists => TRUE);

-- 基金净值表
CREATE TABLE IF NOT EXISTS fact_fund_nav (
    fund_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    unit_nav DECIMAL(10,4) COMMENT '单位净值',
    accum_nav DECIMAL(10,4) COMMENT '累计净值',
    change_pct DECIMAL(10,4) COMMENT '涨跌幅',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (fund_code, trade_date)
);

SELECT create_hypertable('fact_fund_nav', 'trade_date', if_not_exists => TRUE);
