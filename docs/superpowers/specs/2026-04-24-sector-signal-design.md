# 板块信号榜（强势 + 低位启动）设计

**日期**：2026-04-24
**状态**：设计已确认，待用户 review

## 背景

当前"板块涨幅分析 Tab"仅基于**当日涨跌幅**做板块研判，噪声大、信号不稳。实际数据源 `涨幅排名/{date}/public/8涨幅排名*.xlsx` 里已累积了：

- 年初至今涨跌幅 + 升序排名（B 列）
- 月初至今涨跌幅 + 升序排名（D 列）
- 每个历史交易日的当日涨跌幅降序排名（1 = 最强，约 50+ 个日期列）
- "迄今为止排进前 5 次数"

本方案从这份数据挖掘**持续变强板块**（A 信号）和**低位启动板块**（D 信号），作为独立的"强势板块榜"分析视图呈现。

## 目标

1. 在板块涨幅分析 Tab 新增两个榜单：**持续强势榜（A）** 和 **低位启动榜（D）**
2. 每榜可切换 Top 10 / 20 / 30
3. 榜单结果持久化到 MySQL，支持跨日历史回溯
4. 不下沉到个股层面、不侵入现有工作流

## 非目标

- 不做"板块信号"→"个股选股"的回填（未来可扩展）
- 不做信号有效性回测视图（仅数据层为此保留接口）
- 不做图表可视化（本次只做表格；端点 3 历史 API 为未来图表预留）

## 架构

```
前端 Tab「板块涨幅分析」
  └── 新增子面板：板块信号榜（现有涨幅排名大表之上）
        ├── 持续强势榜 (A) [Top 10/20/30 切换]
        └── 低位启动榜 (D) [Top 10/20/30 切换]
            ↓ HTTP
FastAPI: GET /api/statistics/sector-signal?date=&top_n=
  ├── 1. 查 MySQL sector_signal 表（by date_str）
  ├── 2a. 命中 → 反序列化 JSON 返回
  └── 2b. 未命中 →
        ├── 读 data/excel/涨幅排名/{date}/public/8涨幅排名*.xlsx
        ├── SectorSignalService.compute()
        │     ├─ 解析历史日期列（最近 20 个交易日）
        │     ├─ 算 A 榜 / D 榜 全量分数
        │     └─ 排序
        ├── 整批写入 sector_signal（全量板块分 + 两榜 Top 30 + 权重快照）
        └── 返回前 top_n
```

### 模块边界

| 文件 | 职责 |
|---|---|
| `backend/services/sector_signal_service.py` (新) | 纯算法 + 持久化，不依赖 FastAPI 上下文，便于单测 |
| `backend/config/sector_signal_config.py` (新) | 权重、窗口、阈值常量，支持 `.env` 覆盖 |
| `backend/api/statistics_api.py` (扩展) | 新增 3 个端点（查询 / 重算 / 历史） |
| `backend/models/models.py` (扩展) | 新增 `SectorSignal` 模型，随 `Base.metadata.create_all` 启动时自动建表（项目无 alembic） |
| `frontend/src/components/SectorSignalPanel.vue` (新) | 两张榜单表 + Top N 切换 + 刷新按钮 |

## 评分算法

### 输入预处理

来源：`data/excel/涨幅排名/{date}/public/8涨幅排名{首日}-{当日}.xlsx`（单 sheet）

结构：`板块名称 | 年初涨跌幅 | B列升序 | 月初涨跌幅 | D列升序 | 今日涨跌幅 | 迄今前5次数 | <date1> | <date2> | ...`

步骤：
1. 过滤板块名为空 / 含 "妙想Choice" / 全列 NaN 的行（与 `workflow_executor.py:2604` 一致）
2. 识别日期列：列头为 `datetime` 类型，按时间降序排序
3. 切窗口：
   - `window_recent = 最近 5 个日期列`
   - `window_long = 最近 20 个日期列`
   - `window_early = 第 11~20 个日期列`（20 日前半段，用于反转分）
4. `N = 有效板块总数`（实测约 131–140）

### A 榜：持续强势分（0–100）

| 子指标 | 口径 | 权重 |
|---|---|---|
| `score_long_rank` | 近 20 日平均排名 → 降序分位：`100 × (N − avg_rank + 1) / N` | **0.35** |
| `score_recent_rank` | 近 5 日平均排名 → 同上 | **0.25** |
| `score_mtd_pct` | 月初涨跌幅降序分位：`100 × (N − D列升序 + 1) / N` | **0.20** |
| `score_ytd_pct` | 年初涨跌幅降序分位：`100 × (N − B列升序 + 1) / N` | **0.10** |
| `score_stability` | 近 20 日进入前 20 的次数 / 20 × 100 | **0.10** |

**总分** = 子项加权求和，保留 2 位小数。

**硬门槛**（不满足直接不入榜）：
- 近 5 日有效排名数据 ≥ 3
- 近 20 日有效排名数据 ≥ 10

### D 榜：低位启动分（0–100）

| 子指标 | 口径 | 权重 |
|---|---|---|
| `score_reversal` | `(avg_rank_early − avg_rank_recent)` → min-max 归一化到 0–100 | **0.40** |
| `score_recent_rank` | 近 5 日平均排名降序分位 | **0.30** |
| `score_ytd_low` | `100 − 年初涨跌幅降序分位`（低位加分） | **0.20** |
| `score_mtd_pct` | 月初涨跌幅降序分位 | **0.10** |

**总分** = 子项加权求和，保留 2 位小数。

**硬门槛**：
- 近 5 日平均排名 ≤ N × 0.5（真的冲到前半区）
- 第 11–20 日平均排名 ≥ N × 0.5（之前真的在后半区）
- 年初至今涨跌幅 < 全市场中位数（低位硬性要求）

> 说明：反转分用 min-max 批次内归一化 → 每天都能产出榜单，但**不同日期的反转分不可直接比较**。若未来需跨日可比，改 z-score 或固定基准。已确认本次接受此限制。

### 返回字段

**A 榜每行字段**：`sector | today_pct | today_rank | mtd_pct | mtd_rank | ytd_pct | ytd_rank | recent_avg_rank | long_avg_rank | top20_count | strong_score | sub_scores`

**D 榜每行字段**：`sector | today_pct | today_rank | ytd_pct | recent_avg_rank | early_avg_rank | reversal_gap | first_enter_top20_date | reversal_score | sub_scores`

`sub_scores` 为子分数对象，前端用 tooltip 展示、后端原样返回。

格式：涨跌幅保留 2 位小数（数值，前端加 `%`）；排名整数；均排名 1 位小数。"进前 N" / "首次冲入前 N" 中的 N 统一使用 `TOP_THRESHOLD` 常量（默认 20）。

### 权重配置

`backend/config/sector_signal_config.py`：

```python
WEIGHTS_STRONG = {"long_rank": 0.35, "recent_rank": 0.25, "mtd": 0.20, "ytd": 0.10, "stability": 0.10}
WEIGHTS_REVERSAL = {"reversal": 0.40, "recent_rank": 0.30, "ytd_low": 0.20, "mtd": 0.10}
WINDOW_RECENT = 5
WINDOW_LONG = 20
TOP_THRESHOLD = 20   # "进前N"的N
MIN_RECENT_VALID = 3
MIN_LONG_VALID = 10
```

支持 `.env` 覆盖。每次计算时把生效快照写入 DB 的 `config_snapshot`，确保回测可复现。

## 数据库

### `sector_signal` 表

```python
class SectorSignal(Base):
    __tablename__ = "sector_signal"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date_str = Column(String(10), nullable=False, unique=True, index=True)

    source_file = Column(String(500), nullable=False)
    source_mtime = Column(DateTime, nullable=True)  # 为 mtime 失效策略预留

    sector_count = Column(Integer, nullable=False)
    window_long_days = Column(Integer, nullable=False)
    window_recent_days = Column(Integer, nullable=False)

    all_sectors = Column(JSON, nullable=False)    # 全量板块分（~140 行，单条 <100KB）
    top_strong = Column(JSON, nullable=False)     # Top 30 预排序
    top_reversal = Column(JSON, nullable=False)

    config_snapshot = Column(JSON, nullable=False)

    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    __table_args__ = (Index("idx_sector_signal_date", "date_str"),)
```

**设计决策**：
- 单行 JSON 结构：一天一批原子写入，无需跨日 JOIN；前端一次请求拿全；`all_sectors` 留全量是为未来回测。
- `top_strong` / `top_reversal` 预排序冗余：避免每次解 `all_sectors`，读极快。
- `config_snapshot`：权重改过之后，旧记录仍带当时权重，回测不失真。
- 若将来要做"单板块信号时序图"再加明细表（目前 YAGNI）。

## API

### 端点 1：查询板块信号榜（主力）

```
GET /api/statistics/sector-signal
```

**Query**：`date` (YYYY-MM-DD，可选，缺省取最新有 public 的日期) / `top_n` ∈ {10, 20, 30}，缺省 20。

**流程**：参数校验 → 缺省 date 扫目录取最新 → 查 DB → 命中即返回 → 未命中触发计算+持久化 → 返回。

**成功响应**：
```json
{
  "date": "2026-04-23",
  "source_file": "data/excel/涨幅排名/2026-04-23/public/8涨幅排名0202-20260423.xlsx",
  "sector_count": 134,
  "window_long_days": 20,
  "window_recent_days": 5,
  "config_snapshot": { "weights_strong": {...}, "weights_reversal": {...}, "window_recent": 5, "window_long": 20 },
  "top_strong":   [ { "rank": 1, "sector": "...", "strong_score": ..., "today_pct": ..., "today_rank": ..., "mtd_pct": ..., "mtd_rank": ..., "ytd_pct": ..., "ytd_rank": ..., "recent_avg_rank": ..., "long_avg_rank": ..., "top20_count": ..., "sub_scores": { "long_rank": ..., "recent_rank": ..., "mtd": ..., "ytd": ..., "stability": ... } }, ... ],
  "top_reversal": [ { "rank": 1, "sector": "...", "reversal_score": ..., "today_pct": ..., "today_rank": ..., "ytd_pct": ..., "recent_avg_rank": ..., "early_avg_rank": ..., "reversal_gap": ..., "first_enter_top20_date": "2026-04-18", "sub_scores": { "reversal": ..., "recent_rank": ..., "ytd_low": ..., "mtd": ... } }, ... ]
}
```

**错误码**：
| HTTP | code | 场景 |
|---|---|---|
| 400 | `INVALID_TOP_N` | top_n 不在 {10,20,30} |
| 400 | `INVALID_DATE` | 日期格式错误或未来日期 |
| 404 | `SOURCE_FILE_MISSING` | 当日 public 文件不存在 |
| 422 | `INSUFFICIENT_HISTORY` | 历史日期列 < 5 |
| 500 | `COMPUTE_FAILED` | 计算异常 |

### 端点 2：强制重算

```
POST /api/statistics/sector-signal/recompute
Body: { "date": "2026-04-23" }
```

绕过缓存命中，读 Excel 重算覆盖写入，返回同端点 1 结构。用于手工更新了 Excel 后刷新数据。权限复用现有 JWT。

### 端点 3：历史查询

```
GET /api/statistics/sector-signal/history
```

**Query**：
- `sector` (可选)：板块名，精确匹配
- `days` (可选, 默认 30, 范围 1–180)
- `board` (可选, 默认 `strong`)：`strong` 或 `reversal`，仅模式 B 生效

**模式 A — 单板块时序**（传 `sector`）：返回该板块近 N 天分数/排名点列，用于未来画时序图。

```json
{
  "sector": "航海装备Ⅱ",
  "days": 30,
  "points": [
    { "date": "2026-04-23", "strong_score": 82.45, "strong_rank": 1, "reversal_score": 45.2, "reversal_rank": null,
      "today_rank": 2, "recent_avg_rank": 6.2, "long_avg_rank": 18.5,
      "in_top_strong": true, "in_top_reversal": false },
    ...
  ]
}
```

**模式 B — 榜单成分历史**（未传 `sector`）：每天 Top 10 板块名列表，观察"谁进谁出"。

```json
{
  "days": 30,
  "board": "strong",
  "daily_top10": [ { "date": "2026-04-23", "sectors": ["航海装备Ⅱ", "油服工程", ...] }, ... ]
}
```

**错误码**：400 `INVALID_DAYS` / 400 `INVALID_BOARD` / 404 `SECTOR_NOT_FOUND`。

纯 DB 查询，不触发重算。

## 前端

**位置**：板块涨幅分析 Tab 内，现有涨幅排名大表**之上**新增面板。

**组件**：新建 `SectorSignalPanel.vue`，含两张 `el-table`、Top N `el-select`、刷新按钮。

**API 调用**：
- 初始 / 切换日期：`GET /api/statistics/sector-signal?date=...&top_n=30`（一次拿 30 条，本地切片）
- Top N 切换：本地截取，不发请求
- 刷新按钮：`POST /recompute` → 成功后重发 GET

**日期联动**：复用 Tab 现有日期选择器。

**端点 3 的 UI 不在本次范围**（仅后端实现 + 预留接口）。

## 测试策略

遵循 `testing.md` TDD 流程。

### 后端单测（`backend/tests/test_sector_signal.py` 新建）

| 测试点 | 场景 |
|---|---|
| `test_parse_date_columns` | 识别 datetime 列 + 按时间降序；字符串列正确跳过 |
| `test_filter_invalid_rows` | 空板块名 / "妙想Choice" / 全 NaN 被过滤 |
| `test_compute_strong_score` | 3 个模拟板块（强/中/弱），分数落在合理区间 + 相对顺序正确 |
| `test_compute_reversal_score` | 前 10 日垫底 + 后 5 日冲前的板块，反转分最高 |
| `test_hard_thresholds_strong` | 有效日 < 3 的板块不入 A 榜 |
| `test_hard_thresholds_reversal` | 年初高于中位数 / 5 日均排名 > N/2 / 前半段 < N/2 → 不入 D 榜 |
| `test_insufficient_history_422` | 日期列 < 5 时返回 422 |
| `test_source_file_missing_404` | public 目录不存在 404 |
| `test_cache_hit` | 二次请求不触发 Excel 读（mock 验证 open 仅 1 次） |
| `test_recompute_overwrites` | recompute 覆盖写入（updated_at 更新） |
| `test_history_by_sector` | 端点 3 模式 A：30 天数据查单板块返回 30 条 |
| `test_history_by_board` | 端点 3 模式 B：每日 Top 10 sector 列表 |
| `test_config_snapshot_preserved` | 修改权重后回查旧记录，快照仍是当时值 |

**测试数据**：
- 算法层测试：程序生成 `DataFrame`（轻量、精确可断言）
- 解析层测试：真实 mini Excel fixture `backend/tests/fixtures/sector_signal_sample.xlsx`（5 板块 × 25 日期列）

### 前端测试

- `SectorSignalPanel.spec.ts`：渲染两张表、Top N 切换不发 API、刷新按钮触发 recompute、空数据（404）显示占位

### 验收

1. 所有测试通过
2. `./deploy.sh build && ./deploy.sh restart`
3. 浏览器打开板块涨幅分析 Tab，肉眼校验榜单数据合理（与 public Excel 对账）
4. `/verify` 全部通过

## 经验教训预期

实施中若遇到以下场景，按 CLAUDE.md 约定追加规则：
- 若 public Excel 某天的日期列顺序不稳定 → `_parse_date_columns` 必须按 datetime 类型 + 排序再取，禁止按位置
- 若历史日期里混入非数字值（`--`、空）→ 算均排名前必须 `pd.to_numeric(errors='coerce')` + `dropna` 按样本数兜底
- 时区：date_str 一律 `utils.beijing_time.beijing_today_str()`，禁用 `datetime.now().strftime('%Y-%m-%d')`
