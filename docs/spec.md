# 金融数据平台 - 详细规格文档

## 1. 项目概述

### 1.1 目标
构建一个本地金融数据平台，基于 AkShare 数据源，支持复杂条件查询和 AI 智能查询，最多保存近2年数据。

### 1.2 数据源
| 数据源 | 接口数量 | 主要数据类型 | 认证方式 |
|--------|---------|-------------|---------|
| AkShare | 200+ | 股票行情、财务数据、基金、期货、债券、宏观、均线数据 | 无需认证 |

### 1.3 技术选型
- **关系数据库**: MySQL 8.0 - 存储结构化事实表和维度表
- **时序数据库**: TimescaleDB - 存储股票行情等时序数据
- **Python版本**: 3.11+

---

## 2. 数据库设计

### 2.1 MySQL 表结构

#### 维度表 (Dimension Tables)

```sql
-- 股票维度表
CREATE TABLE dim_stock (
    stock_code VARCHAR(10) PRIMARY KEY COMMENT '股票代码',
    stock_name VARCHAR(100) COMMENT '股票名称',
    listing_date DATE COMMENT '上市日期',
    delist_date DATE COMMENT '退市日期',
    exchange_code VARCHAR(10) COMMENT '交易所代码(SH/SZ/BJ)',
    industry_code VARCHAR(20) COMMENT '行业代码',
    industry_name VARCHAR(100) COMMENT '行业名称',
    concept_codes JSON COMMENT '概念板块代码列表',
    is_active TINYINT DEFAULT 1 COMMENT '是否活跃',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_exchange (exchange_code),
    INDEX idx_industry (industry_code),
    INDEX idx_listing_date (listing_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票基础信息表';

-- 行业维度表
CREATE TABLE dim_industry (
    industry_code VARCHAR(20) PRIMARY KEY COMMENT '行业代码',
    industry_name VARCHAR(100) COMMENT '行业名称',
    level INT COMMENT '层级(1/2/3)',
    parent_code VARCHAR(20) COMMENT '父级代码',
    source VARCHAR(20) DEFAULT 'akshare' COMMENT '数据来源'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='行业分类表';

-- 概念板块维度表
CREATE TABLE dim_concept (
    concept_code VARCHAR(20) PRIMARY KEY COMMENT '概念板块代码',
    concept_name VARCHAR(100) COMMENT '概念板块名称',
    source VARCHAR(20) DEFAULT 'akshare' COMMENT '数据来源',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='概念板块表';

-- 交易日历表
CREATE TABLE dim_calendar (
    trade_date DATE PRIMARY KEY COMMENT '交易日期',
    is_trading_day TINYINT DEFAULT 1 COMMENT '是否交易日',
    year INT COMMENT '年份',
    quarter INT COMMENT '季度',
    month INT COMMENT '月份',
    INDEX idx_year (year),
    INDEX idx_quarter (quarter)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易日历表';

-- 指数/ETF基础信息表
CREATE TABLE dim_index (
    index_code VARCHAR(20) PRIMARY KEY COMMENT '指数代码',
    index_name VARCHAR(100) COMMENT '指数名称',
    category VARCHAR(50) COMMENT '分类(股票指数/债券指数/商品指数)',
    base_date DATE COMMENT '基期',
    base_point DECIMAL(10,4) COMMENT '基点',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='指数基础信息表';
```

#### 事实表 (Fact Tables - MySQL)

```sql
-- 财务数据事实表
CREATE TABLE fact_financial (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL COMMENT '股票代码',
    report_date DATE NOT NULL COMMENT '报告期',
    report_type VARCHAR(20) NOT NULL COMMENT '报告类型(Q1/Q2/Q3/FY)',
    revenue DECIMAL(20,4) COMMENT '营业收入(元)',
    revenue_yoy DECIMAL(10,4) COMMENT '营收同比(%)',
    net_profit DECIMAL(20,4) COMMENT '净利润(元)',
    net_profit_yoy DECIMAL(10,4) COMMENT '净利润同比(%)',
    total_assets DECIMAL(20,4) COMMENT '总资产',
    total_liabilities DECIMAL(20,4) COMMENT '总负债',
    equity DECIMAL(20,4) COMMENT '所有者权益',
    roe DECIMAL(10,4) COMMENT '净资产收益率(%)',
    gross_margin DECIMAL(10,4) COMMENT '毛利率(%)',
    net_margin DECIMAL(10,4) COMMENT '净利率(%)',
    eps DECIMAL(10,4) COMMENT '每股收益(元)',
    bps DECIMAL(10,4) COMMENT '每股净资产(元)',
    pe_ratio DECIMAL(10,4) COMMENT '市盈率',
    pb_ratio DECIMAL(10,4) COMMENT '市净率',
    ps_ratio DECIMAL(10,4) COMMENT '市销率',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_stock_report (stock_code, report_date, report_type),
    INDEX idx_report_date (report_date),
    INDEX idx_roe (roe),
    INDEX idx_pe (pe_ratio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='财务数据事实表';

-- 基金基础信息表
CREATE TABLE dim_fund (
    fund_code VARCHAR(20) PRIMARY KEY COMMENT '基金代码',
    fund_name VARCHAR(100) COMMENT '基金名称',
    fund_type VARCHAR(50) COMMENT '基金类型(股票型/债券型/混合型/指数型)',
    manager VARCHAR(100) COMMENT '基金经理',
    listing_date DATE COMMENT '成立日期',
    is_active TINYINT DEFAULT 1 COMMENT '是否运作中',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基金基础信息表';

-- 基金持仓表
CREATE TABLE fact_fund_holding (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    fund_code VARCHAR(20) NOT NULL COMMENT '基金代码',
    fund_name VARCHAR(100) COMMENT '基金名称',
    stock_code VARCHAR(10) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(100) COMMENT '股票名称',
    report_date DATE NOT NULL COMMENT '报告期',
    holding_ratio DECIMAL(10,4) COMMENT '持仓比例(%)',
    holding_shares BIGINT COMMENT '持仓股数',
    market_value DECIMAL(20,4) COMMENT '持仓市值(元)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_fund_stock (fund_code, stock_code, report_date),
    INDEX idx_report_date (report_date),
    INDEX idx_stock_code (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基金持仓表';

-- 宏观数据表
CREATE TABLE fact_macro (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    indicator_code VARCHAR(50) NOT NULL COMMENT '指标代码',
    indicator_name VARCHAR(100) COMMENT '指标名称',
    period VARCHAR(20) NOT NULL COMMENT '周期(D/M/Q/Y)',
    period_value VARCHAR(20) NOT NULL COMMENT '周期值(2026Q1/202601等)',
    value DECIMAL(20,4) COMMENT '数值',
    value_yoy DECIMAL(10,4) COMMENT '同比(%)',
    value_mom DECIMAL(10,4) COMMENT '环比(%)',
    source VARCHAR(50) DEFAULT 'akshare' COMMENT '数据来源',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_indicator_period (indicator_code, period, period_value),
    INDEX idx_period (period_value)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='宏观数据表';
```

### 2.2 TimescaleDB 表结构 (时序数据)

```sql
-- 启用 TimescaleDB 扩展
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- A股/期货每日行情表 (时序数据)
CREATE TABLE fact_daily_bar (
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

-- 创建连续聚合策略 (用于计算均线等指标)
CREATE MATERIALIZED VIEW fact_daily_bar_ma
WITH (timescaledb.continuous) AS
SELECT
    stock_code,
    time_bucket('1 day', trade_date) AS bucket,
    AVG(close) OVER (
        PARTITION BY stock_code
        ORDER BY trade_date
        ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
    ) AS ma5,
    AVG(close) OVER (
        PARTITION BY stock_code
        ORDER BY trade_date
        ROWS BETWEEN 9 PRECEDING AND CURRENT ROW
    ) AS ma10,
    AVG(close) OVER (
        PARTITION BY stock_code
        ORDER BY trade_date
        ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS ma20
FROM fact_daily_bar;

-- 指数/ETF行情表
CREATE TABLE fact_index_bar (
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
CREATE TABLE fact_fund_nav (
    fund_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    unit_nav DECIMAL(10,4) COMMENT '单位净值',
    accum_nav DECIMAL(10,4) COMMENT '累计净值',
    change_pct DECIMAL(10,4) COMMENT '涨跌幅',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (fund_code, trade_date)
);

SELECT create_hypertable('fact_fund_nav', 'trade_date', if_not_exists => TRUE);
```

### 2.3 配置与日志表

```sql
-- 数据获取配置表
CREATE TABLE config_data_fetch (
    id INT PRIMARY KEY AUTO_INCREMENT,
    data_type VARCHAR(50) NOT NULL COMMENT '数据类型(stock_daily/financial/fund_nav等)',
    source VARCHAR(20) NOT NULL COMMENT '数据源(akshare)',
    api_name VARCHAR(100) COMMENT 'API名称',
    fetch_frequency VARCHAR(20) NOT NULL COMMENT '更新频率(hourly/daily/weekly)',
    time_range_start VARCHAR(20) COMMENT '时间范围起点',
    time_range_end VARCHAR(20) COMMENT '时间范围终点',
    update_config JSON COMMENT '更新配置(参数、过滤条件等)',
    is_enabled TINYINT DEFAULT 1,
    last_fetch_time DATETIME,
    last_fetch_status VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_data_type_source (data_type, source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据获取配置表';

-- 数据保留策略表
CREATE TABLE config_retention_policy (
    id INT PRIMARY KEY AUTO_INCREMENT,
    data_type VARCHAR(50) NOT NULL,
    retention_days INT NOT NULL COMMENT '保留天数',
    archive_before_delete TINYINT DEFAULT 0 COMMENT '删除前是否归档',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_data_type (data_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据保留策略表';

-- 数据获取日志表
CREATE TABLE log_data_fetch (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    data_type VARCHAR(50) NOT NULL,
    source VARCHAR(20) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    records_fetched INT DEFAULT 0,
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    details JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_data_type (data_type),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据获取日志表';
```

---

## 3. 数据更新策略

### 3.1 分级更新规则

| 数据类型 | 去年 (2025-01-01 ~ 2025-12-31) | 今年 (2026-01-01 ~ 今天) |
|---------|------------------------------|------------------------|
| A股/期货每日行情 | 每5天更新一次 | 每1小时更新一次 |
| 财务数据 | 每季度更新一次(财报发布后) | 每季度更新一次 |
| 基金净值 | 每5天更新一次 | 每天更新一次 |
| 指数行情 | 每5天更新一次 | 每1小时更新一次 |
| 宏观数据 | 每5天更新一次 | 每天更新一次 |
| 基金持仓(季报) | 季报发布后更新 | 季报发布后更新 |

### 3.2 数据淘汰规则
- 保留最近2年数据
- 超过2年的数据自动 DELETE
- 每周日凌晨2点执行清理任务

### 3.3 初始数据加载
- 首次运行时，一次性加载近2年历史数据
- 之后按分级更新策略增量更新

---

## 4. 查询接口设计

### 4.1 SQL 查询接口

```python
# 通用查询接口
POST /api/v1/data/query
{
    "sql": "SELECT stock_code, trade_date, close, ma5, ma10, ma20 FROM fact_daily_bar WHERE trade_date BETWEEN '2026-01-01' AND '2026-04-09' LIMIT 100",
    "params": {}
}

# 返回
{
    "success": true,
    "data": [...],
    "columns": ["stock_code", "trade_date", "close", "ma5", "ma10", "ma20"],
    "row_count": 100
}
```

### 4.2 预设查询模板

```python
# 查询1: 导出某时间段并购重组数据 (需要先确认数据源)
# 接口: POST /api/v1/data/export/merger

# 查询2: 查询满足条件的股票
POST /api/v1/data/query/stocks
{
    "conditions": {
        "exchange": "SZ",          # 交易所(SH/SZ/BJ)
        "industry": "消费",         # 行业
        "pe_min": 0,
        "pe_max": 30,
        "net_profit_growth_min": 20,  # 净利润增长(%)
        "years": 3,                   # 持续年数
        "sort_by": "pe",              # 排序字段
        "order": "asc"
    }
}

# 查询3: 获取股票技术指标
POST /api/v1/data/stock/technical
{
    "stock_code": "600004",
    "start_date": "2026-01-01",
    "end_date": "2026-04-09",
    "indicators": ["ma5", "ma10", "ma20", "ma60", "volume_ratio"]
}

# 查询4: 获取指数成分股
POST /api/v1/data/index/constituents
{
    "index_code": "000300",  # 沪深300
    "date": "2026-04-09"
}
```

### 4.3 AI 查询接口

```python
# 自然语言转SQL查询
POST /api/v1/data/query/ai
{
    "query": "查询近三年净利润增长均超过20%且市盈率低于30倍的消费股",
    "mode": "nl2sql"  # nl2sql / direct_answer
}

# 返回
{
    "success": true,
    "sql": "SELECT s.stock_code, s.stock_name, f.pe_ratio, f.net_profit_yoy FROM dim_stock s JOIN fact_financial f ON s.stock_code = f.stock_code WHERE s.industry_name = '消费' AND f.pe_ratio < 30 AND f.net_profit_yoy > 20 AND f.report_date >= DATE_SUB(CURDATE(), INTERVAL 3 YEAR)",
    "results": [...],
    "explanation": "查询了消费行业中符合条件..."
}
```

### 4.4 AI 实现方案
- **基础版本**: 本地规则解析 + 模板匹配
- **进阶版本**: 接入 ChatGLM / Claude 等 LLM API
- 两种模式可切换

---

## 5. 数据获取模块设计

### 5.1 AkShare 核心接口清单

| 数据类型 | AkShare API | 更新频率 |
|---------|-------------|---------|
| **股票行情** | stock_zh_a_hist | 小时/天 |
| **股票实时行情** | stock_zh_a_spot_em | 实时 |
| **财务指标** | stock_financial_analysis_indicator_em | 季度 |
| **财务报表** | stock_financial_report_sina | 季度 |
| **均线数据** | (本地计算) | 日 |
| **指数行情** | index_zh_a_hist | 小时/天 |
| **指数成分** | index_weight_cons | 日 |
| **ETF行情** | fund_etf_hist_sina | 小时/天 |
| **基金净值** | fund_open_fund_info_em | 天 |
| **基金持仓** | fund_report_stock | 季度 |
| **宏观数据** | macro_china_money_supply | 月 |
| **行业分类** | stock_board_industry_name_em | 日 |

### 5.2 模块架构

```
┌─────────────────────────────────────────────────────────────┐
│                    DataFetcher (统一入口)                     │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ StockFetcher │  │ FundFetcher  │  │ MacroFetcher │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
├─────────────────────────────────────────────────────────────┤
│                    DataNormalizer (数据标准化)                │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────┐  ┌──────────────────────┐         │
│  │ MySQLWriter          │  │ TimescaleDBWriter    │         │
│  └──────────────────────┘  └──────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 核心类设计

```python
# 数据获取基类
class BaseFetcher:
    def fetch(self, **kwargs) -> pd.DataFrame:
        raise NotImplementedError

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError

# 股票数据获取器
class StockFetcher(BaseFetcher):
    def fetch_daily_bar(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        # stock_zh_a_hist
        pass

    def calculate_ma(self, df: pd.DataFrame, periods: List[int]) -> pd.DataFrame:
        # 计算均线
        for period in periods:
            df[f'ma{period}'] = df['close'].rolling(window=period).mean()
        return df

    def fetch_financial(self, stock_code: str) -> pd.DataFrame:
        # stock_financial_analysis_indicator_em
        pass

    def fetch_spot(self) -> pd.DataFrame:
        # stock_zh_a_spot_em 实时行情
        pass

# 基金数据获取器
class FundFetcher(BaseFetcher):
    def fetch_nav(self, fund_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        # fund_open_fund_info_em
        pass

    def fetch_holding(self, fund_code: str, year: int) -> pd.DataFrame:
        # fund_report_stock 基金持仓
        pass
```

---

## 6. 前端界面设计

### 6.1 页面结构

```
金融数据平台
├── 数据概览 (Dashboard)
│   ├── 今日行情摘要
│   ├── 数据更新状态
│   └── 存储使用情况
├── 数据查询
│   ├── SQL 查询
│   ├── AI 智能查询
│   └── 预设模板查询
├── 数据管理
│   ├── 数据源配置
│   ├── 更新策略配置
│   └── 手动更新触发
├── 数据导出
│   ├── 导出历史数据
│   └── 定时导出任务
└── 系统设置
    ├── 更新频率设置
    ├── 保留策略设置
    └── AI 配置
```

---

## 7. 项目文件结构

```
backend/
├── main.py                      # FastAPI 入口
├── requirements.txt             # 依赖
├── config/
│   ├── database.py             # 数据库配置
│   └── akshare.py              # AkShare 配置
├── models/
│   ├── dimension.py            # 维度表模型
│   ├── fact.py                 # 事实表模型
│   └── config.py               # 配置表模型
├── fetcher/
│   ├── __init__.py
│   ├── base.py                 # 基类
│   ├── stock_fetcher.py        # 股票获取器
│   ├── fund_fetcher.py         # 基金获取器
│   ├── index_fetcher.py        # 指数获取器
│   ├── macro_fetcher.py        # 宏观获取器
│   └── normalizer.py           # 数据标准化
├── service/
│   ├── data_service.py         # 数据服务
│   ├── query_service.py        # 查询服务
│   ├── ai_query_service.py     # AI 查询服务
│   ├── ma_calculator.py        # 均线计算服务
│   └── scheduler_service.py    # 调度服务
├── api/
│   ├── data.py                 # 数据接口
│   ├── query.py                # 查询接口
│   └── config.py               # 配置接口
└── scripts/
    ├── init_db.sql             # 数据库初始化
    ├── init_data.py            # 初始数据加载
    └── retention_cleanup.py     # 数据清理脚本

frontend/src/
├── views/
│   ├── DataDashboard.vue       # 数据概览
│   ├── DataQuery.vue           # 数据查询
│   ├── AIQuery.vue             # AI 查询
│   ├── DataExport.vue          # 数据导出
│   └── SystemConfig.vue        # 系统配置
└── ...
```

---

## 8. 实现优先级

### Phase 1: 基础数据获取 (2周)
1. [ ] 数据库表创建 (MySQL + TimescaleDB)
2. [ ] AkShare 行情数据接口对接 (日线、实时)
3. [ ] 均线数据计算
4. [ ] 基础查询 API

### Phase 2: 财务和基金数据 (1周)
5. [ ] 财务数据接口对接
6. [ ] 基金净值、持仓接口对接
7. [ ] 指数数据接口对接

### Phase 3: 高级功能 (2周)
8. [ ] 数据更新调度
9. [ ] AI 查询 (NL2SQL)
10. [ ] 数据保留策略实现

### Phase 4: 前端界面 (1周)
11. [ ] 前端界面开发
12. [ ] 系统监控 Dashboard

---

## 9. 待确认问题

| 序号 | 问题 | 选项 |
|------|------|------|
| 1 | **是否需要支持港股和美股数据？** | A. 只要A股 / B. A股+港股 / C. 全部 |
| 2 | **是否需要实时行情 (分时/分钟级)？** | A. 只要日线 / B. 加上分钟线 |
| 3 | **AI 查询使用什么实现？** | A. 本地规则模板 / B. ChatGLM API / C. 两者都要 |
| 4 | **是否需要数据订阅/推送功能？** | A. 不需要 / B. 需要 |

---

*文档版本: v2.0*
*创建日期: 2026-04-09*
*最后更新: 2026-04-09*
