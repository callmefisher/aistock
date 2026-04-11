-- 股票维度表
CREATE TABLE IF NOT EXISTS dim_stock (
    stock_code VARCHAR(10) NOT NULL PRIMARY KEY,
    stock_name VARCHAR(100),
    exchange_code VARCHAR(5),
    industry_name VARCHAR(100),
    market_value DECIMAL(20,4),
    is_active TINYINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 财务数据表
CREATE TABLE IF NOT EXISTS fact_financial (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    report_date DATE NOT NULL,
    revenue DECIMAL(20,4),
    net_profit DECIMAL(20,4),
    net_profit_yoy DECIMAL(10,4),
    pe_ratio DECIMAL(10,4),
    pb_ratio DECIMAL(10,4),
    ps_ratio DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_stock_date (stock_code, report_date)
);

-- 创建索引
CREATE INDEX idx_financial_stock ON fact_financial(stock_code);
CREATE INDEX idx_financial_date ON fact_financial(report_date);
CREATE INDEX idx_daily_stock ON fact_daily_bar(stock_code);
CREATE INDEX idx_daily_date ON fact_daily_bar(trade_date);
