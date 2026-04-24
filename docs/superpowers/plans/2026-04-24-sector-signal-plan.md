# 板块信号榜（持续强势 + 低位启动）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在「板块涨幅分析 Tab」新增「持续强势榜（A）」和「低位启动榜（D）」两张榜单，基于涨幅排名 public Excel 存档的历史日排名+年初/月初涨跌幅挖掘板块动量信号，结果持久化 MySQL 支持跨日回溯。

**Architecture:** API 请求时实时计算 + DB 缓存命中（按 `date_str` 唯一约束）。**独立实现：模型、路由、service、前端组件全部新建独立模块，不修改任何现有文件的业务逻辑。** 唯一的外部挂载点：`main.py` 新增一行 `include_router`（独立路由前缀），`Statistics.vue` 三行最小插入（import + computed + 组件使用），均不改动既有代码路径。

**复用不侵入：** 复用 `core.database.Base` / `AsyncSessionLocal`、`api.auth.get_current_user`、`utils.beijing_time.beijing_today_str` 等现成模块，但不修改它们；不触碰 `workflow_executor.py` / `statistics_api.py` / `models.py` 的任何现有代码。

**Tech Stack:** FastAPI + SQLAlchemy (async) + MySQL + pandas + openpyxl + Vue 3 + Element Plus + axios。

**Spec:** `docs/superpowers/specs/2026-04-24-sector-signal-design.md`

**关键常量**（权重 / 窗口 / 阈值）：
```python
WEIGHTS_STRONG = {"long_rank": 0.35, "recent_rank": 0.25, "mtd": 0.20, "ytd": 0.10, "stability": 0.10}
WEIGHTS_REVERSAL = {"reversal": 0.40, "recent_rank": 0.30, "ytd_low": 0.20, "mtd": 0.10}
WINDOW_RECENT = 5
WINDOW_LONG = 20
TOP_THRESHOLD = 20
MIN_RECENT_VALID = 3
MIN_LONG_VALID = 10
```

---

## 文件结构

**新增文件（全部独立，零侵入）：**
- `backend/config/sector_signal_config.py` — 权重/窗口/阈值常量 + `.env` 覆盖
- `backend/models/sector_signal_model.py` — `SectorSignal` 模型（独立文件，不动 `models.py`）
- `backend/services/sector_signal_service.py` — 算分+持久化纯逻辑
- `backend/api/sector_signal_api.py` — 3 个端点（独立路由模块）
- `backend/tests/test_sector_signal.py` — 后端单测
- `backend/tests/fixtures/sector_signal_sample.xlsx` — mini fixture（解析层测试用）
- `frontend/src/components/SectorSignalPanel.vue` — 前端面板

**最小挂载点（非侵入，只添加不修改）：**
- `backend/main.py` — 新增 2 行 import + 1 行 `app.include_router`（前缀 `/api/sector-signal`，独立路由，不挤占现有 `/api/statistics` 命名空间）
- `backend/models/__init__.py` 或模型发现机制 — 确保新模型被 `Base.metadata` 注册（需要确认项目机制，见 Task 2）
- `frontend/src/views/Statistics.vue` — 新增 1 行 import + 1 行 computed + 1 行 `<SectorSignalPanel>`（在 ranking Tab 顶部），不修改任何现有元素

**数据流：** 前端请求 → `/api/sector-signal/` → `SectorSignalService.get_or_compute(date)` → 命中返回 / 未命中读 Excel + 算分 + 写 DB → 返回。

---

## Task 1: 创建配置模块

**Files:**
- Create: `backend/config/sector_signal_config.py`

- [ ] **Step 1: 写配置文件**

```python
# backend/config/sector_signal_config.py
"""板块信号榜配置（权重/窗口/阈值）。

支持通过环境变量覆盖，便于调参：
- SECTOR_SIGNAL_WINDOW_RECENT, SECTOR_SIGNAL_WINDOW_LONG
- SECTOR_SIGNAL_TOP_THRESHOLD, SECTOR_SIGNAL_MIN_RECENT_VALID, SECTOR_SIGNAL_MIN_LONG_VALID
"""
import os

WEIGHTS_STRONG = {
    "long_rank": 0.35,
    "recent_rank": 0.25,
    "mtd": 0.20,
    "ytd": 0.10,
    "stability": 0.10,
}

WEIGHTS_REVERSAL = {
    "reversal": 0.40,
    "recent_rank": 0.30,
    "ytd_low": 0.20,
    "mtd": 0.10,
}

WINDOW_RECENT = int(os.getenv("SECTOR_SIGNAL_WINDOW_RECENT", "5"))
WINDOW_LONG = int(os.getenv("SECTOR_SIGNAL_WINDOW_LONG", "20"))
TOP_THRESHOLD = int(os.getenv("SECTOR_SIGNAL_TOP_THRESHOLD", "20"))
MIN_RECENT_VALID = int(os.getenv("SECTOR_SIGNAL_MIN_RECENT_VALID", "3"))
MIN_LONG_VALID = int(os.getenv("SECTOR_SIGNAL_MIN_LONG_VALID", "10"))

TOP_N_CHOICES = {10, 20, 30}
TOP_N_DEFAULT = 20
TOP_N_STORE = 30  # DB 预存 Top 30，前端本地切片


def snapshot() -> dict:
    """返回当前生效的配置快照，写入 DB 的 config_snapshot 字段。"""
    return {
        "weights_strong": dict(WEIGHTS_STRONG),
        "weights_reversal": dict(WEIGHTS_REVERSAL),
        "window_recent": WINDOW_RECENT,
        "window_long": WINDOW_LONG,
        "top_threshold": TOP_THRESHOLD,
        "min_recent_valid": MIN_RECENT_VALID,
        "min_long_valid": MIN_LONG_VALID,
    }
```

- [ ] **Step 2: 校验权重和为 1**

运行：
```bash
cd /Users/xiayanji/qbox/aistock/backend && python -c "
from config.sector_signal_config import WEIGHTS_STRONG, WEIGHTS_REVERSAL, snapshot
assert abs(sum(WEIGHTS_STRONG.values()) - 1.0) < 1e-9, WEIGHTS_STRONG
assert abs(sum(WEIGHTS_REVERSAL.values()) - 1.0) < 1e-9, WEIGHTS_REVERSAL
print(snapshot())
"
```
Expected: 打印快照 dict，无 AssertionError。

- [ ] **Step 3: Commit**

```bash
git add backend/config/sector_signal_config.py
git commit -m "feat(sector-signal): 新增板块信号榜配置模块"
```

---

## Task 2: 新增 SectorSignal 数据模型（独立文件）

**Files:**
- Create: `backend/models/sector_signal_model.py`

**零侵入说明**：不修改 `backend/models/models.py`。新模型通过 `sector_signal_api.py` 的 import 链被加载，自动注册到 `Base.metadata`，`create_all` 会在启动时建表。

- [ ] **Step 1: 新建模型文件**

```python
# backend/models/sector_signal_model.py
"""板块信号榜持久化模型（独立文件，不影响 models.py）。"""
from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from core.database import Base


class SectorSignal(Base):
    """一天一行：全量板块分 + 两榜 Top N + 权重快照。"""
    __tablename__ = "sector_signal"

    id = Column(Integer, primary_key=True, index=True)
    date_str = Column(String(10), nullable=False, unique=True, index=True, comment="YYYY-MM-DD")

    source_file = Column(String(500), nullable=False, comment="源 public Excel 路径")
    source_mtime = Column(DateTime, nullable=True, comment="源文件 mtime，mtime 失效策略预留")

    sector_count = Column(Integer, nullable=False, comment="有效板块总数 N")
    window_long_days = Column(Integer, nullable=False, comment="实际长窗口天数")
    window_recent_days = Column(Integer, nullable=False, comment="实际短窗口天数")

    all_sectors = Column(JSON, nullable=False, comment="全量板块分")
    top_strong = Column(JSON, nullable=False, comment="持续强势榜 Top 30")
    top_reversal = Column(JSON, nullable=False, comment="低位启动榜 Top 30")

    config_snapshot = Column(JSON, nullable=False, comment="当时生效的权重/窗口/阈值")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 2: 校验模型语法**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -c "
from models.sector_signal_model import SectorSignal
from core.database import Base
assert 'sector_signal' in Base.metadata.tables
print('OK:', Base.metadata.tables['sector_signal'].columns.keys())
"
```
Expected: 打印 `OK: [...列名列表...]`。

- [ ] **Step 3: 重启后端让 create_all 自动建表**

> **注意**：建表需要在 `main.py` lifespan 运行前，`SectorSignal` 模型已被 import。这会在 Task 10 新增 `sector_signal_api.py` 并 include_router 后自动满足（`main.py` import 路由模块时连带 import 模型）。本 Task 暂不建表，Task 10 完成后重启即可建出。

如需在本 Task 提前手工建表验证，运行：
```bash
cd /Users/xiayanji/qbox/aistock/backend && python -c "
import asyncio
from core.database import async_engine, Base
from models.sector_signal_model import SectorSignal
async def go():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
asyncio.run(go())
print('建表完成')
"
```

- [ ] **Step 4: Commit**

```bash
git add backend/models/sector_signal_model.py
git commit -m "feat(sector-signal): 新增 SectorSignal 模型（独立文件）"
```

---

## Task 3: Service 层骨架 + 纯函数（TDD · RED）

**Files:**
- Create: `backend/services/sector_signal_service.py`
- Create: `backend/tests/test_sector_signal.py`

- [ ] **Step 1: 写 service 模块骨架（所有函数先 NotImplementedError）**

```python
# backend/services/sector_signal_service.py
"""板块信号榜算分服务。

所有算分函数都是纯函数，便于单测：
- 输入：pandas DataFrame（已读好的 public Excel 内容）
- 输出：dict / list[dict]

持久化方法：
- get_or_compute(date_str) -> dict          # 缓存命中返回，未命中算完写 DB
- recompute(date_str) -> dict               # 强制重算覆盖
- load_sector_history(sector, days) -> dict
- load_board_history(board, days, top_n) -> dict
"""
from __future__ import annotations

import glob
import logging
import os
from datetime import datetime
from typing import Any, Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.sector_signal_config import (
    WEIGHTS_STRONG, WEIGHTS_REVERSAL,
    WINDOW_RECENT, WINDOW_LONG, TOP_THRESHOLD,
    MIN_RECENT_VALID, MIN_LONG_VALID,
    TOP_N_STORE, snapshot,
)
from core.database import AsyncSessionLocal
from models.sector_signal_model import SectorSignal

logger = logging.getLogger(__name__)

BASE_EXCEL_DIR = "data/excel/涨幅排名"
INVALID_SECTOR_MARKER = "妙想Choice"


# ---------- 纯函数：解析 + 算分 ----------

def parse_date_columns(df: pd.DataFrame) -> list:
    """识别日期列（列头为 datetime），按时间降序返回列名列表。"""
    raise NotImplementedError


def filter_invalid_rows(df: pd.DataFrame, sector_col: str = "板块名称") -> pd.DataFrame:
    """过滤板块名为空 / 含 '妙想Choice' / 全列 NaN 的行。"""
    raise NotImplementedError


def _rank_to_pct_score(rank: float, n: int) -> float:
    """升序排名 → 降序分位分（越小越靠前越高分）。"""
    raise NotImplementedError


def compute_strong_score(row: dict, n: int) -> Optional[dict]:
    """单板块持续强势分。不满足硬门槛返回 None。

    row 需含:
      long_avg_rank, recent_avg_rank, ytd_asc_rank, mtd_asc_rank,
      top20_count, long_valid_days, recent_valid_days
    返回: {"strong_score": 82.45, "sub_scores": {...}}
    """
    raise NotImplementedError


def compute_reversal_score(row: dict, n: int, ytd_median_pct: float) -> Optional[dict]:
    """单板块低位启动分。不满足硬门槛返回 None。

    reversal 子分需要在批次级别做 min-max，所以本函数只算 reversal_gap
    原始值，不做归一化；批次归一化在 compute_all() 里做。

    row 需含: recent_avg_rank, early_avg_rank, ytd_pct, ytd_asc_rank, mtd_asc_rank
    返回: {"reversal_gap_raw": 80.5, "sub_raw": {...}}  批次归一化前的中间结果
    """
    raise NotImplementedError


def compute_all(df: pd.DataFrame) -> dict:
    """给定已读好的 public Excel DataFrame，返回两榜 + 全量分。

    返回:
    {
      "sector_count": N, "window_long_days": ..., "window_recent_days": ...,
      "all_sectors": [...], "top_strong": [...], "top_reversal": [...],
    }
    """
    raise NotImplementedError


# ---------- Excel 读取 ----------

def find_source_excel(date_str: str, base_dir: str = BASE_EXCEL_DIR) -> Optional[str]:
    """按 date_str 查 public 目录下最新的 8涨幅排名*.xlsx；不存在返回 None。"""
    raise NotImplementedError


def find_latest_date_with_source(base_dir: str = BASE_EXCEL_DIR) -> Optional[str]:
    """扫所有子目录，返回最新有 public 文件的日期（YYYY-MM-DD）。"""
    raise NotImplementedError


def read_public_excel(path: str) -> pd.DataFrame:
    """读 public Excel 单 sheet，返回 DataFrame（保留原列头含 datetime 对象）。"""
    raise NotImplementedError


# ---------- 持久化（async） ----------

async def get_or_compute(date_str: str, session: Optional[AsyncSession] = None) -> dict:
    """查 DB 命中即返回，否则读 Excel 算完写库再返回。"""
    raise NotImplementedError


async def recompute(date_str: str, session: Optional[AsyncSession] = None) -> dict:
    """绕过缓存，强制重算覆盖写入。"""
    raise NotImplementedError


async def load_sector_history(sector: str, days: int) -> dict:
    """端点 3 模式 A：单板块 N 天时序点列。"""
    raise NotImplementedError


async def load_board_history(board: str, days: int, top_n: int = 10) -> dict:
    """端点 3 模式 B：每日榜单 Top N 板块名列表。board in {strong, reversal}"""
    raise NotImplementedError


# ---------- 自定义异常 ----------

class SourceFileMissing(Exception):
    pass


class InsufficientHistory(Exception):
    pass


class SectorNotFound(Exception):
    pass
```

- [ ] **Step 2: 写完整测试用例（全部期望失败）**

```python
# backend/tests/test_sector_signal.py
"""板块信号榜单测（TDD · RED 先行）。

算法层：程序生成 DataFrame 精确断言
解析层：真实 mini fixture（Task 5 创建）
持久化层：conftest.py 提供 async session
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import pandas as pd
import pytest

from services import sector_signal_service as sig_svc
from services.sector_signal_service import (
    SourceFileMissing, InsufficientHistory, SectorNotFound,
)


# ---------- 解析 / 过滤 ----------

def _make_df(date_cols: list, rows: list[dict]) -> pd.DataFrame:
    """辅助：构造含 datetime 列头 + 板块行的 DataFrame。"""
    base_cols = ["板块名称", "年初涨跌幅", "B列升序", "月初涨跌幅", "D列升序", "今日涨跌幅", "迄今前5次数"]
    data = {}
    for c in base_cols:
        data[c] = [r.get(c) for r in rows]
    for d in date_cols:
        data[d] = [r.get(d) for r in rows]
    return pd.DataFrame(data)


def test_parse_date_columns_orders_desc():
    d1, d2, d3 = datetime(2026, 4, 21), datetime(2026, 4, 22), datetime(2026, 4, 23)
    df = _make_df([d1, d3, d2], [{"板块名称": "A"}])
    result = sig_svc.parse_date_columns(df)
    assert result == [d3, d2, d1], f"日期列应按降序返回，实际 {result}"


def test_parse_date_columns_skips_string_headers():
    d1 = datetime(2026, 4, 23)
    df = _make_df([d1], [{"板块名称": "A"}])
    result = sig_svc.parse_date_columns(df)
    assert result == [d1], "字符串列头（板块名称等）必须被跳过"


def test_filter_invalid_rows_removes_blank_placeholder_nan():
    df = _make_df([datetime(2026, 4, 23)], [
        {"板块名称": "正常板块", "今日涨跌幅": 1.0},
        {"板块名称": "", "今日涨跌幅": 2.0},
        {"板块名称": "妙想Choice A", "今日涨跌幅": 3.0},
        {"板块名称": None, "今日涨跌幅": 4.0},
    ])
    result = sig_svc.filter_invalid_rows(df)
    assert len(result) == 1
    assert result.iloc[0]["板块名称"] == "正常板块"


# ---------- 算分 ----------

def test_rank_to_pct_score_boundary():
    # N=100: rank=1 → 100 分, rank=100 → 1 分
    assert sig_svc._rank_to_pct_score(1, 100) == pytest.approx(100.0)
    assert sig_svc._rank_to_pct_score(100, 100) == pytest.approx(1.0)
    assert sig_svc._rank_to_pct_score(50, 100) == pytest.approx(51.0)


def test_compute_strong_score_relative_order():
    n = 100
    strong = sig_svc.compute_strong_score({
        "long_avg_rank": 5.0, "recent_avg_rank": 3.0,
        "ytd_asc_rank": 95, "mtd_asc_rank": 98,
        "top20_count": 20, "long_valid_days": 20, "recent_valid_days": 5,
    }, n)
    weak = sig_svc.compute_strong_score({
        "long_avg_rank": 80.0, "recent_avg_rank": 85.0,
        "ytd_asc_rank": 10, "mtd_asc_rank": 15,
        "top20_count": 0, "long_valid_days": 20, "recent_valid_days": 5,
    }, n)
    mid = sig_svc.compute_strong_score({
        "long_avg_rank": 50.0, "recent_avg_rank": 40.0,
        "ytd_asc_rank": 50, "mtd_asc_rank": 55,
        "top20_count": 3, "long_valid_days": 20, "recent_valid_days": 5,
    }, n)
    assert strong["strong_score"] > mid["strong_score"] > weak["strong_score"]
    assert 0 <= weak["strong_score"] <= 100
    assert 0 <= strong["strong_score"] <= 100


def test_strong_hard_threshold_insufficient_recent():
    n = 100
    result = sig_svc.compute_strong_score({
        "long_avg_rank": 5.0, "recent_avg_rank": 3.0,
        "ytd_asc_rank": 95, "mtd_asc_rank": 98,
        "top20_count": 15, "long_valid_days": 20, "recent_valid_days": 2,
    }, n)
    assert result is None, "近 5 日有效 < 3 必须不入榜"


def test_strong_hard_threshold_insufficient_long():
    n = 100
    result = sig_svc.compute_strong_score({
        "long_avg_rank": 5.0, "recent_avg_rank": 3.0,
        "ytd_asc_rank": 95, "mtd_asc_rank": 98,
        "top20_count": 5, "long_valid_days": 9, "recent_valid_days": 5,
    }, n)
    assert result is None, "近 20 日有效 < 10 必须不入榜"


def test_compute_reversal_gap_raw_positive_when_reversal():
    n = 100
    result = sig_svc.compute_reversal_score({
        "recent_avg_rank": 8.0, "early_avg_rank": 85.0,
        "ytd_pct": -15.0, "ytd_asc_rank": 5, "mtd_asc_rank": 40,
    }, n, ytd_median_pct=2.0)
    assert result is not None
    assert result["reversal_gap_raw"] > 0


def test_reversal_hard_threshold_ytd_above_median():
    n = 100
    result = sig_svc.compute_reversal_score({
        "recent_avg_rank": 8.0, "early_avg_rank": 85.0,
        "ytd_pct": 30.0, "ytd_asc_rank": 95, "mtd_asc_rank": 40,
    }, n, ytd_median_pct=2.0)
    assert result is None, "年初至今涨幅高于中位数必须不入 D 榜"


def test_reversal_hard_threshold_recent_not_top_half():
    n = 100
    result = sig_svc.compute_reversal_score({
        "recent_avg_rank": 60.0, "early_avg_rank": 85.0,
        "ytd_pct": -15.0, "ytd_asc_rank": 5, "mtd_asc_rank": 40,
    }, n, ytd_median_pct=2.0)
    assert result is None, "近 5 日均排名 > N/2 必须不入 D 榜"


def test_reversal_hard_threshold_early_must_be_back_half():
    n = 100
    result = sig_svc.compute_reversal_score({
        "recent_avg_rank": 8.0, "early_avg_rank": 30.0,
        "ytd_pct": -15.0, "ytd_asc_rank": 5, "mtd_asc_rank": 40,
    }, n, ytd_median_pct=2.0)
    assert result is None, "20日前半段均排名 < N/2（本来就靠前）必须不入 D 榜"


# ---------- 整合：compute_all ----------

def _build_synthetic_df(n_sectors: int = 20, n_days: int = 25) -> pd.DataFrame:
    """构造 n 个板块 × n_days 个日期列的合成 DataFrame，每行可预测。"""
    from datetime import datetime, timedelta
    date_cols = [datetime(2026, 4, 23) - timedelta(days=i) for i in range(n_days)]
    rows = []
    for i in range(n_sectors):
        r = {
            "板块名称": f"板块{i:02d}",
            "年初涨跌幅": round(30 - i * 2.5, 2),
            "B列升序": n_sectors - i,   # i=0 升序最大 → 年初涨幅最大
            "月初涨跌幅": round(10 - i * 0.8, 2),
            "D列升序": n_sectors - i,
            "今日涨跌幅": round(3 - i * 0.2, 2),
            "迄今前5次数": max(0, 10 - i),
        }
        # 日期列：i=0 每天排名 ≈ 1，i=N 每天排名 ≈ N
        for j, d in enumerate(date_cols):
            r[d] = i + 1
        rows.append(r)
    return _make_df(date_cols, rows)


def test_compute_all_returns_two_boards_and_all():
    df = _build_synthetic_df(n_sectors=30, n_days=25)
    result = sig_svc.compute_all(df)
    assert result["sector_count"] == 30
    assert result["window_long_days"] == 20
    assert result["window_recent_days"] == 5
    assert len(result["all_sectors"]) == 30
    assert len(result["top_strong"]) <= 30
    # 第 0 号板块排名最高，应在 top_strong 第 1 位
    assert result["top_strong"][0]["sector"] == "板块00"
    # 每行有必要字段
    row = result["top_strong"][0]
    for k in ["sector", "strong_score", "today_pct", "today_rank", "recent_avg_rank", "long_avg_rank", "top20_count", "sub_scores"]:
        assert k in row, f"top_strong 行缺少字段: {k}"


def test_compute_all_reversal_top_is_reversal_sector():
    """构造：板块00 前 10 天排名 ~100，后 5 天 ~5，年初跌幅大 → 反转分最高。"""
    from datetime import datetime, timedelta
    n_sectors, n_days = 30, 25
    date_cols = [datetime(2026, 4, 23) - timedelta(days=i) for i in range(n_days)]
    rows = []
    for i in range(n_sectors):
        r = {
            "板块名称": f"板块{i:02d}",
            "年初涨跌幅": -20.0 if i == 0 else 10.0 + i,  # 板块00 年初大跌
            "B列升序": 1 if i == 0 else n_sectors - i + 1,
            "月初涨跌幅": 5.0 if i == 0 else round(10 - i * 0.5, 2),
            "D列升序": 10 if i == 0 else n_sectors - i,
            "今日涨跌幅": 2.0 if i == 0 else round(1 - i * 0.1, 2),
            "迄今前5次数": 1 if i == 0 else 0,
        }
        for j, d in enumerate(date_cols):
            if i == 0:
                r[d] = 3 if j < 5 else 28  # 最近 5 天排名 3，之前排名 28
            else:
                r[d] = i + 1
        rows.append(r)
    df = _make_df(date_cols, rows)
    result = sig_svc.compute_all(df)
    assert result["top_reversal"], "应有 D 榜成员"
    assert result["top_reversal"][0]["sector"] == "板块00"


def test_compute_all_insufficient_history_raises():
    df = _build_synthetic_df(n_sectors=5, n_days=4)
    with pytest.raises(InsufficientHistory):
        sig_svc.compute_all(df)


# ---------- Excel I/O ----------

def test_find_source_excel_missing_returns_none(tmp_path):
    assert sig_svc.find_source_excel("2026-04-23", base_dir=str(tmp_path)) is None


def test_find_source_excel_picks_matching(tmp_path):
    d = tmp_path / "2026-04-23" / "public"
    d.mkdir(parents=True)
    f = d / "8涨幅排名0202-20260423.xlsx"
    f.write_bytes(b"")
    assert sig_svc.find_source_excel("2026-04-23", base_dir=str(tmp_path)) == str(f)


def test_find_latest_date_with_source(tmp_path):
    for date in ["2026-04-20", "2026-04-22", "2026-04-23"]:
        d = tmp_path / date / "public"
        d.mkdir(parents=True)
        (d / f"8涨幅排名-{date}.xlsx").write_bytes(b"")
    (tmp_path / "2026-04-21").mkdir()  # 无 public 子目录
    assert sig_svc.find_latest_date_with_source(base_dir=str(tmp_path)) == "2026-04-23"


def test_read_public_excel_keeps_datetime_headers():
    """解析层测试：从 fixture 读 Excel 验证日期列头保留为 datetime。"""
    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "sector_signal_sample.xlsx")
    df = sig_svc.read_public_excel(fixture)
    date_cols = [c for c in df.columns if isinstance(c, datetime)]
    assert len(date_cols) >= 20, f"fixture 应至少 20 个日期列，实际 {len(date_cols)}"


# ---------- 持久化（async） ----------

@pytest.mark.asyncio
async def test_get_or_compute_caches(tmp_path, monkeypatch):
    """二次调用命中缓存，不再读 Excel。"""
    monkeypatch.setattr(sig_svc, "BASE_EXCEL_DIR", str(tmp_path))
    # 准备 fixture
    fixture_src = os.path.join(os.path.dirname(__file__), "fixtures", "sector_signal_sample.xlsx")
    import shutil
    d = tmp_path / "2026-04-23" / "public"
    d.mkdir(parents=True)
    shutil.copy(fixture_src, d / "8涨幅排名-20260423.xlsx")

    read_count = {"n": 0}
    orig_read = sig_svc.read_public_excel

    def counting_read(path):
        read_count["n"] += 1
        return orig_read(path)

    monkeypatch.setattr(sig_svc, "read_public_excel", counting_read)

    r1 = await sig_svc.get_or_compute("2026-04-23")
    r2 = await sig_svc.get_or_compute("2026-04-23")
    assert read_count["n"] == 1, f"命中缓存后不应再读 Excel，实际读了 {read_count['n']} 次"
    assert r1["date"] == r2["date"] == "2026-04-23"


@pytest.mark.asyncio
async def test_get_or_compute_source_missing_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(sig_svc, "BASE_EXCEL_DIR", str(tmp_path))
    with pytest.raises(SourceFileMissing):
        await sig_svc.get_or_compute("2026-04-23")


@pytest.mark.asyncio
async def test_recompute_overwrites(tmp_path, monkeypatch):
    """recompute 应覆盖 DB 中已有的记录（updated_at 前进）。"""
    import asyncio
    monkeypatch.setattr(sig_svc, "BASE_EXCEL_DIR", str(tmp_path))
    fixture_src = os.path.join(os.path.dirname(__file__), "fixtures", "sector_signal_sample.xlsx")
    import shutil
    d = tmp_path / "2026-04-23" / "public"
    d.mkdir(parents=True)
    shutil.copy(fixture_src, d / "8涨幅排名-20260423.xlsx")

    r1 = await sig_svc.get_or_compute("2026-04-23")
    await asyncio.sleep(1.1)  # 确保 updated_at 至少前进 1 秒
    r2 = await sig_svc.recompute("2026-04-23")
    assert r2["date"] == "2026-04-23"
    # 读 DB 验证 updated_at > created_at
    from core.database import AsyncSessionLocal
    from sqlalchemy import select
    from models.sector_signal_model import SectorSignal
    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(SectorSignal).where(SectorSignal.date_str == "2026-04-23"))).scalar_one()
        assert row.updated_at >= row.created_at


@pytest.mark.asyncio
async def test_load_sector_history(tmp_path, monkeypatch):
    monkeypatch.setattr(sig_svc, "BASE_EXCEL_DIR", str(tmp_path))
    fixture_src = os.path.join(os.path.dirname(__file__), "fixtures", "sector_signal_sample.xlsx")
    import shutil
    d = tmp_path / "2026-04-23" / "public"
    d.mkdir(parents=True)
    shutil.copy(fixture_src, d / "8涨幅排名-20260423.xlsx")

    await sig_svc.get_or_compute("2026-04-23")
    # fixture 里第一行板块名（Task 5 约定为 "板块00"）
    result = await sig_svc.load_sector_history("板块00", days=30)
    assert result["sector"] == "板块00"
    assert len(result["points"]) == 1
    p = result["points"][0]
    assert p["date"] == "2026-04-23"
    for k in ["strong_score", "strong_rank", "reversal_score", "reversal_rank", "today_rank", "in_top_strong", "in_top_reversal"]:
        assert k in p


@pytest.mark.asyncio
async def test_load_sector_history_not_found():
    with pytest.raises(SectorNotFound):
        await sig_svc.load_sector_history("不存在的板块XYZ", days=30)


@pytest.mark.asyncio
async def test_load_board_history(tmp_path, monkeypatch):
    monkeypatch.setattr(sig_svc, "BASE_EXCEL_DIR", str(tmp_path))
    fixture_src = os.path.join(os.path.dirname(__file__), "fixtures", "sector_signal_sample.xlsx")
    import shutil
    d = tmp_path / "2026-04-23" / "public"
    d.mkdir(parents=True)
    shutil.copy(fixture_src, d / "8涨幅排名-20260423.xlsx")
    await sig_svc.get_or_compute("2026-04-23")

    result = await sig_svc.load_board_history("strong", days=30, top_n=5)
    assert result["board"] == "strong"
    assert isinstance(result["daily_top10"], list)
    assert result["daily_top10"][0]["date"] == "2026-04-23"
    assert len(result["daily_top10"][0]["sectors"]) <= 5


@pytest.mark.asyncio
async def test_config_snapshot_preserved(tmp_path, monkeypatch):
    """旧记录的 config_snapshot 不受后续权重变更影响。"""
    monkeypatch.setattr(sig_svc, "BASE_EXCEL_DIR", str(tmp_path))
    fixture_src = os.path.join(os.path.dirname(__file__), "fixtures", "sector_signal_sample.xlsx")
    import shutil
    d = tmp_path / "2026-04-23" / "public"
    d.mkdir(parents=True)
    shutil.copy(fixture_src, d / "8涨幅排名-20260423.xlsx")

    r1 = await sig_svc.get_or_compute("2026-04-23")
    snap_before = r1["config_snapshot"]

    # 修改运行时配置（模拟"权重改了"），旧记录查回来还是原快照
    monkeypatch.setattr(sig_svc, "WEIGHTS_STRONG", {"long_rank": 0.5, "recent_rank": 0.5, "mtd": 0, "ytd": 0, "stability": 0})
    r2 = await sig_svc.get_or_compute("2026-04-23")  # 命中缓存
    assert r2["config_snapshot"] == snap_before
```

- [ ] **Step 3: 运行测试确认全部失败（RED）**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_sector_signal.py -v 2>&1 | tail -40
```
Expected: 所有测试 FAILED 或 ERROR（NotImplementedError / fixture 缺失）。

- [ ] **Step 4: Commit（失败的测试入库作为契约）**

```bash
git add backend/services/sector_signal_service.py backend/tests/test_sector_signal.py
git commit -m "test(sector-signal): RED 阶段 · 失败测试用例入库"
```

---

## Task 4: 实现解析与过滤（GREEN · 解析层）

**Files:**
- Modify: `backend/services/sector_signal_service.py`

- [ ] **Step 1: 实现 parse_date_columns + filter_invalid_rows**

替换 Task 3 中的 NotImplementedError：

```python
def parse_date_columns(df: pd.DataFrame) -> list:
    date_cols = [c for c in df.columns if isinstance(c, datetime)]
    date_cols.sort(reverse=True)  # 最新在前
    return date_cols


def filter_invalid_rows(df: pd.DataFrame, sector_col: str = "板块名称") -> pd.DataFrame:
    if sector_col not in df.columns:
        return df.iloc[0:0].copy()
    s = df[sector_col].astype(str).str.strip()
    mask = (
        df[sector_col].notna()
        & (s != "")
        & (s.str.lower() != "nan")
        & (~s.str.contains(INVALID_SECTOR_MARKER, na=False, regex=False))
    )
    return df[mask].reset_index(drop=True)
```

- [ ] **Step 2: 运行解析层测试**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_sector_signal.py::test_parse_date_columns_orders_desc tests/test_sector_signal.py::test_parse_date_columns_skips_string_headers tests/test_sector_signal.py::test_filter_invalid_rows_removes_blank_placeholder_nan -v
```
Expected: 3 个测试 PASSED。

- [ ] **Step 3: Commit**

```bash
git add backend/services/sector_signal_service.py
git commit -m "feat(sector-signal): 解析 + 过滤函数实现"
```

---

## Task 5: 创建 mini Excel fixture

**Files:**
- Create: `backend/tests/fixtures/sector_signal_sample.xlsx`

- [ ] **Step 1: 写一次性生成脚本 + 执行**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -c "
import os
from datetime import datetime, timedelta
import pandas as pd

os.makedirs('tests/fixtures', exist_ok=True)
n_sectors, n_days = 20, 25
date_cols = [datetime(2026, 4, 23) - timedelta(days=i) for i in range(n_days)]

base_cols = ['板块名称', '年初涨跌幅', 'B列升序', '月初涨跌幅', 'D列升序', '今日涨跌幅', '迄今前5次数']
data = {c: [] for c in base_cols + date_cols}

for i in range(n_sectors):
    data['板块名称'].append(f'板块{i:02d}')
    data['年初涨跌幅'].append(round(30 - i*2.5, 2))
    data['B列升序'].append(n_sectors - i)
    data['月初涨跌幅'].append(round(10 - i*0.8, 2))
    data['D列升序'].append(n_sectors - i)
    data['今日涨跌幅'].append(round(3 - i*0.2, 2))
    data['迄今前5次数'].append(max(0, 10-i))
    for d in date_cols:
        data[d].append(i + 1)

df = pd.DataFrame(data)
df.to_excel('tests/fixtures/sector_signal_sample.xlsx', index=False, sheet_name='0423')
print('fixture 已生成, shape =', df.shape)
"
```
Expected: `fixture 已生成, shape = (20, 32)`

- [ ] **Step 2: 验证读取保留 datetime 列头**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -c "
import pandas as pd
from datetime import datetime
df = pd.read_excel('tests/fixtures/sector_signal_sample.xlsx', sheet_name=0)
date_cols = [c for c in df.columns if isinstance(c, datetime)]
print(f'datetime 列数: {len(date_cols)}')
assert len(date_cols) == 25
"
```
Expected: `datetime 列数: 25`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/fixtures/sector_signal_sample.xlsx
git commit -m "test(sector-signal): 添加 mini Excel fixture（20板块×25日期）"
```

---

## Task 6: 实现 Excel I/O（GREEN · I/O 层）

**Files:**
- Modify: `backend/services/sector_signal_service.py`

- [ ] **Step 1: 实现 find_source_excel / find_latest_date_with_source / read_public_excel**

替换对应 NotImplementedError：

```python
def find_source_excel(date_str: str, base_dir: str = BASE_EXCEL_DIR) -> Optional[str]:
    pattern = os.path.join(base_dir, date_str, "public", "8涨幅排名*.xlsx")
    matches = sorted(glob.glob(pattern))
    if not matches:
        # 兼容无 "8" 前缀的旧文件名（如 板块涨跌幅排名0415.xlsx 的 public 版本）
        pattern2 = os.path.join(base_dir, date_str, "public", "*涨幅排名*.xlsx")
        matches = sorted(glob.glob(pattern2))
    return matches[-1] if matches else None


def find_latest_date_with_source(base_dir: str = BASE_EXCEL_DIR) -> Optional[str]:
    if not os.path.isdir(base_dir):
        return None
    candidates = []
    for name in os.listdir(base_dir):
        if len(name) != 10 or name[4] != "-" or name[7] != "-":
            continue
        pub_dir = os.path.join(base_dir, name, "public")
        if os.path.isdir(pub_dir) and os.listdir(pub_dir):
            candidates.append(name)
    return sorted(candidates)[-1] if candidates else None


def read_public_excel(path: str) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=0)
```

- [ ] **Step 2: 运行 I/O 层测试**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_sector_signal.py::test_find_source_excel_missing_returns_none tests/test_sector_signal.py::test_find_source_excel_picks_matching tests/test_sector_signal.py::test_find_latest_date_with_source tests/test_sector_signal.py::test_read_public_excel_keeps_datetime_headers -v
```
Expected: 4 个测试 PASSED。

- [ ] **Step 3: Commit**

```bash
git add backend/services/sector_signal_service.py
git commit -m "feat(sector-signal): Excel I/O 层实现"
```

---

## Task 7: 实现算分函数（GREEN · 算法层）

**Files:**
- Modify: `backend/services/sector_signal_service.py`

- [ ] **Step 1: 实现 _rank_to_pct_score + compute_strong_score + compute_reversal_score**

替换对应 NotImplementedError：

```python
def _rank_to_pct_score(rank: float, n: int) -> float:
    """升序排名 → 降序分位分。rank ∈ [1, N]，返回 ∈ (0, 100]。"""
    if n <= 0:
        return 0.0
    return round(100.0 * (n - rank + 1) / n, 4)


def compute_strong_score(row: dict, n: int) -> Optional[dict]:
    # 硬门槛
    if row.get("recent_valid_days", 0) < MIN_RECENT_VALID:
        return None
    if row.get("long_valid_days", 0) < MIN_LONG_VALID:
        return None

    score_long = _rank_to_pct_score(row["long_avg_rank"], n)
    score_recent = _rank_to_pct_score(row["recent_avg_rank"], n)
    score_mtd = _rank_to_pct_score(row["mtd_asc_rank"], n)  # D列升序 = 月初涨幅升序
    score_ytd = _rank_to_pct_score(row["ytd_asc_rank"], n)  # B列升序 = 年初涨幅升序
    # 注意：B/D 列是升序（小=涨幅小），要转降序分位，直接用 _rank_to_pct_score 传入
    # (n - asc_rank + 1)，即 desc_rank=asc_rank；实际上我们要分位 = 100*(n - desc_rank + 1)/n
    # 但月初/年初涨幅是"值大=强"，在 rank 表示里 desc_rank=1 是最强（涨最多）。
    # 源表给的是 asc_rank=1 是最弱，所以 desc_rank = n - asc_rank + 1。
    # 再套 _rank_to_pct_score(desc_rank, n) = 100*(n - desc_rank + 1)/n = 100*asc_rank/n。
    # 为避免重复踩坑，直接用 asc 换算：
    score_mtd = round(100.0 * row["mtd_asc_rank"] / n, 4)
    score_ytd = round(100.0 * row["ytd_asc_rank"] / n, 4)

    score_stability = round(100.0 * row["top20_count"] / WINDOW_LONG, 4)

    sub = {
        "long_rank": score_long,
        "recent_rank": score_recent,
        "mtd": score_mtd,
        "ytd": score_ytd,
        "stability": min(score_stability, 100.0),
    }
    total = sum(WEIGHTS_STRONG[k] * sub[k] for k in WEIGHTS_STRONG)
    return {"strong_score": round(total, 2), "sub_scores": sub}


def compute_reversal_score(row: dict, n: int, ytd_median_pct: float) -> Optional[dict]:
    # 硬门槛 1: 年初涨幅必须低于全市场中位数
    if row["ytd_pct"] >= ytd_median_pct:
        return None
    # 硬门槛 2: 近 5 日均排名 ≤ N/2（真的冲前）
    if row["recent_avg_rank"] > n * 0.5:
        return None
    # 硬门槛 3: 前半段均排名 ≥ N/2（之前真的在后半区）
    if row["early_avg_rank"] < n * 0.5:
        return None

    gap_raw = row["early_avg_rank"] - row["recent_avg_rank"]  # 正值 = 越左侧越强
    score_recent = _rank_to_pct_score(row["recent_avg_rank"], n)
    ytd_desc_pct = 100.0 * row["ytd_asc_rank"] / n  # 年初降序分位
    score_ytd_low = 100.0 - ytd_desc_pct
    score_mtd = 100.0 * row["mtd_asc_rank"] / n

    return {
        "reversal_gap_raw": round(gap_raw, 4),
        "sub_raw": {
            "recent_rank": score_recent,
            "ytd_low": round(score_ytd_low, 4),
            "mtd": round(score_mtd, 4),
        },
    }
```

- [ ] **Step 2: 运行算分单测**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_sector_signal.py::test_rank_to_pct_score_boundary tests/test_sector_signal.py::test_compute_strong_score_relative_order tests/test_sector_signal.py::test_strong_hard_threshold_insufficient_recent tests/test_sector_signal.py::test_strong_hard_threshold_insufficient_long tests/test_sector_signal.py::test_compute_reversal_gap_raw_positive_when_reversal tests/test_sector_signal.py::test_reversal_hard_threshold_ytd_above_median tests/test_sector_signal.py::test_reversal_hard_threshold_recent_not_top_half tests/test_sector_signal.py::test_reversal_hard_threshold_early_must_be_back_half -v
```
Expected: 8 个测试 PASSED。

- [ ] **Step 3: Commit**

```bash
git add backend/services/sector_signal_service.py
git commit -m "feat(sector-signal): 算分函数（强势分 + 反转分 raw）实现"
```

---

## Task 8: 实现 compute_all 整合逻辑

**Files:**
- Modify: `backend/services/sector_signal_service.py`

- [ ] **Step 1: 实现 compute_all**

替换 NotImplementedError：

```python
def _numeric_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _avg_rank_and_valid(df_ranks: pd.DataFrame) -> pd.DataFrame:
    """给定每日排名矩阵（行=板块，列=日期），返回 DataFrame(avg_rank, valid_days)。"""
    numeric = df_ranks.apply(_numeric_series)
    return pd.DataFrame({
        "avg_rank": numeric.mean(axis=1, skipna=True),
        "valid_days": numeric.notna().sum(axis=1),
    })


def _count_in_top(df_ranks: pd.DataFrame, threshold: int) -> pd.Series:
    numeric = df_ranks.apply(_numeric_series)
    return (numeric <= threshold).sum(axis=1)


def _first_enter_top(df_ranks: pd.DataFrame, threshold: int) -> pd.Series:
    """从最老到最新，第一次 ≤ threshold 的日期列名（返回 pd.Series[str] or None）。"""
    # df_ranks 列按降序排列，这里要从老到新扫 → 反转列顺序
    cols = list(df_ranks.columns)[::-1]  # 从老到新
    numeric = df_ranks[cols].apply(_numeric_series)

    def _first(row):
        for c in cols:
            v = row[c]
            if pd.notna(v) and v <= threshold:
                return c.strftime("%Y-%m-%d") if isinstance(c, datetime) else str(c)
        return None

    return numeric.apply(_first, axis=1)


def compute_all(df: pd.DataFrame) -> dict:
    df = filter_invalid_rows(df)
    date_cols = parse_date_columns(df)
    if len(date_cols) < 5:
        raise InsufficientHistory(f"历史日期列不足 5（实际 {len(date_cols)}）")

    window_long_days = min(len(date_cols), WINDOW_LONG)
    window_recent_days = min(len(date_cols), WINDOW_RECENT)
    window_early_cols = date_cols[window_recent_days:window_long_days]  # 前半段

    recent_cols = date_cols[:window_recent_days]
    long_cols = date_cols[:window_long_days]

    n = len(df)
    ytd_pct = _numeric_series(df["年初涨跌幅"])
    ytd_median = float(ytd_pct.median()) if not ytd_pct.dropna().empty else 0.0

    recent_info = _avg_rank_and_valid(df[recent_cols])
    long_info = _avg_rank_and_valid(df[long_cols])
    early_info = _avg_rank_and_valid(df[window_early_cols]) if window_early_cols else pd.DataFrame({
        "avg_rank": [float("nan")] * n, "valid_days": [0] * n
    })
    top_counts = _count_in_top(df[long_cols], TOP_THRESHOLD)
    first_enter = _first_enter_top(df[long_cols], TOP_THRESHOLD)

    # 当日：第一个（最新）日期列即今日排名
    today_col = date_cols[0]
    today_rank = _numeric_series(df[today_col])
    today_date_str = today_col.strftime("%Y-%m-%d")
    today_pct = _numeric_series(df["今日涨跌幅"])
    mtd_asc = _numeric_series(df["D列升序"])
    ytd_asc = _numeric_series(df["B列升序"])
    mtd_pct = _numeric_series(df["月初涨跌幅"])

    # 逐行算两榜
    strong_list, reversal_raw_list, all_list = [], [], []
    for idx in range(n):
        sector = df["板块名称"].iloc[idx]
        common = {
            "sector": sector,
            "today_pct": None if pd.isna(today_pct.iloc[idx]) else round(float(today_pct.iloc[idx]), 2),
            "today_rank": None if pd.isna(today_rank.iloc[idx]) else int(today_rank.iloc[idx]),
            "mtd_pct": None if pd.isna(mtd_pct.iloc[idx]) else round(float(mtd_pct.iloc[idx]), 2),
            "mtd_rank": None if pd.isna(mtd_asc.iloc[idx]) else int(mtd_asc.iloc[idx]),
            "ytd_pct": None if pd.isna(ytd_pct.iloc[idx]) else round(float(ytd_pct.iloc[idx]), 2),
            "ytd_rank": None if pd.isna(ytd_asc.iloc[idx]) else int(ytd_asc.iloc[idx]),
            "recent_avg_rank": None if pd.isna(recent_info["avg_rank"].iloc[idx]) else round(float(recent_info["avg_rank"].iloc[idx]), 1),
            "long_avg_rank": None if pd.isna(long_info["avg_rank"].iloc[idx]) else round(float(long_info["avg_rank"].iloc[idx]), 1),
            "early_avg_rank": None if pd.isna(early_info["avg_rank"].iloc[idx]) else round(float(early_info["avg_rank"].iloc[idx]), 1),
            "top20_count": int(top_counts.iloc[idx]),
            "first_enter_top20_date": first_enter.iloc[idx],
        }

        strong_row = None
        if common["long_avg_rank"] is not None and common["recent_avg_rank"] is not None:
            s = compute_strong_score({
                "long_avg_rank": common["long_avg_rank"],
                "recent_avg_rank": common["recent_avg_rank"],
                "ytd_asc_rank": common["ytd_rank"] if common["ytd_rank"] is not None else n,
                "mtd_asc_rank": common["mtd_rank"] if common["mtd_rank"] is not None else n,
                "top20_count": common["top20_count"],
                "long_valid_days": int(long_info["valid_days"].iloc[idx]),
                "recent_valid_days": int(recent_info["valid_days"].iloc[idx]),
            }, n)
            if s is not None:
                strong_row = {**common, **s}

        reversal_row = None
        if common["recent_avg_rank"] is not None and common["early_avg_rank"] is not None and common["ytd_pct"] is not None:
            r = compute_reversal_score({
                "recent_avg_rank": common["recent_avg_rank"],
                "early_avg_rank": common["early_avg_rank"],
                "ytd_pct": common["ytd_pct"],
                "ytd_asc_rank": common["ytd_rank"] if common["ytd_rank"] is not None else n,
                "mtd_asc_rank": common["mtd_rank"] if common["mtd_rank"] is not None else n,
            }, n, ytd_median)
            if r is not None:
                reversal_row = {**common, **r}  # 暂存 raw

        all_list.append({
            **common,
            "strong_score": strong_row["strong_score"] if strong_row else None,
            "strong_sub_scores": strong_row["sub_scores"] if strong_row else None,
        })
        if strong_row:
            strong_list.append({**common, "strong_score": strong_row["strong_score"], "sub_scores": strong_row["sub_scores"]})
        if reversal_row:
            reversal_raw_list.append(reversal_row)

    # D 榜：批次内 min-max 归一化 reversal_gap → [0, 100]，再加权
    if reversal_raw_list:
        gaps = [r["reversal_gap_raw"] for r in reversal_raw_list]
        g_min, g_max = min(gaps), max(gaps)
        span = g_max - g_min if g_max > g_min else 1.0
        reversal_list = []
        for r in reversal_raw_list:
            gap_score = 100.0 * (r["reversal_gap_raw"] - g_min) / span
            sub = {"reversal": round(gap_score, 4), **r["sub_raw"]}
            total = sum(WEIGHTS_REVERSAL[k] * sub[k] for k in WEIGHTS_REVERSAL)
            reversal_list.append({
                **{k: r[k] for k in ["sector", "today_pct", "today_rank", "ytd_pct", "recent_avg_rank", "early_avg_rank", "first_enter_top20_date"]},
                "reversal_gap": round(r["reversal_gap_raw"], 2),
                "reversal_score": round(total, 2),
                "sub_scores": sub,
            })
        reversal_list.sort(key=lambda x: x["reversal_score"], reverse=True)
    else:
        reversal_list = []

    strong_list.sort(key=lambda x: x["strong_score"], reverse=True)
    # 加 rank 字段
    for i, r in enumerate(strong_list[:TOP_N_STORE]):
        r["rank"] = i + 1
    for i, r in enumerate(reversal_list[:TOP_N_STORE]):
        r["rank"] = i + 1

    # all_sectors 里标注在两榜中的名次（便于 load_sector_history）
    strong_rank_by_sector = {r["sector"]: r["rank"] for r in strong_list[:TOP_N_STORE]}
    reversal_rank_by_sector = {r["sector"]: r["rank"] for r in reversal_list[:TOP_N_STORE]}
    for a in all_list:
        a["strong_rank"] = strong_rank_by_sector.get(a["sector"])
        a["reversal_rank"] = reversal_rank_by_sector.get(a["sector"])

    return {
        "sector_count": n,
        "window_long_days": window_long_days,
        "window_recent_days": window_recent_days,
        "all_sectors": all_list,
        "top_strong": strong_list[:TOP_N_STORE],
        "top_reversal": reversal_list[:TOP_N_STORE],
    }
```

- [ ] **Step 2: 运行 compute_all 相关测试**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_sector_signal.py::test_compute_all_returns_two_boards_and_all tests/test_sector_signal.py::test_compute_all_reversal_top_is_reversal_sector tests/test_sector_signal.py::test_compute_all_insufficient_history_raises -v
```
Expected: 3 个测试 PASSED。

- [ ] **Step 3: 全量算法层回归**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_sector_signal.py -v -k "not async" 2>&1 | tail -30
```
Expected: 所有非 async 测试 PASSED（async 测试下一 Task 实现）。

- [ ] **Step 4: Commit**

```bash
git add backend/services/sector_signal_service.py
git commit -m "feat(sector-signal): compute_all 整合两榜算分 + 批次 min-max"
```

---

## Task 9: 实现持久化层（async）

**Files:**
- Modify: `backend/services/sector_signal_service.py`

- [ ] **Step 1: 实现 get_or_compute / recompute**

替换对应 NotImplementedError：

```python
async def _load_row(session: AsyncSession, date_str: str) -> Optional[SectorSignal]:
    q = select(SectorSignal).where(SectorSignal.date_str == date_str)
    res = await session.execute(q)
    return res.scalar_one_or_none()


def _row_to_response(row: SectorSignal, date_str: str, source_file: str) -> dict:
    return {
        "date": date_str,
        "source_file": source_file,
        "sector_count": row.sector_count,
        "window_long_days": row.window_long_days,
        "window_recent_days": row.window_recent_days,
        "config_snapshot": row.config_snapshot,
        "top_strong": row.top_strong,
        "top_reversal": row.top_reversal,
    }


async def _compute_and_persist(date_str: str, session: AsyncSession, overwrite: bool) -> dict:
    source_file = find_source_excel(date_str)
    if source_file is None:
        raise SourceFileMissing(f"date={date_str} 的 public 文件不存在")
    df = read_public_excel(source_file)
    result = compute_all(df)

    source_mtime = datetime.fromtimestamp(os.path.getmtime(source_file))
    config_snap = snapshot()

    existing = await _load_row(session, date_str)
    if existing and not overwrite:
        return _row_to_response(existing, date_str, existing.source_file)

    if existing:
        existing.source_file = source_file
        existing.source_mtime = source_mtime
        existing.sector_count = result["sector_count"]
        existing.window_long_days = result["window_long_days"]
        existing.window_recent_days = result["window_recent_days"]
        existing.all_sectors = result["all_sectors"]
        existing.top_strong = result["top_strong"]
        existing.top_reversal = result["top_reversal"]
        existing.config_snapshot = config_snap
        row = existing
    else:
        row = SectorSignal(
            date_str=date_str,
            source_file=source_file,
            source_mtime=source_mtime,
            sector_count=result["sector_count"],
            window_long_days=result["window_long_days"],
            window_recent_days=result["window_recent_days"],
            all_sectors=result["all_sectors"],
            top_strong=result["top_strong"],
            top_reversal=result["top_reversal"],
            config_snapshot=config_snap,
        )
        session.add(row)
    await session.commit()
    await session.refresh(row)
    return _row_to_response(row, date_str, source_file)


async def get_or_compute(date_str: str, session: Optional[AsyncSession] = None) -> dict:
    if session is None:
        async with AsyncSessionLocal() as s:
            return await get_or_compute(date_str, s)
    existing = await _load_row(session, date_str)
    if existing:
        return _row_to_response(existing, date_str, existing.source_file)
    return await _compute_and_persist(date_str, session, overwrite=False)


async def recompute(date_str: str, session: Optional[AsyncSession] = None) -> dict:
    if session is None:
        async with AsyncSessionLocal() as s:
            return await recompute(date_str, s)
    return await _compute_and_persist(date_str, session, overwrite=True)


async def load_sector_history(sector: str, days: int) -> dict:
    async with AsyncSessionLocal() as s:
        q = (select(SectorSignal)
             .order_by(SectorSignal.date_str.desc())
             .limit(days))
        rows = (await s.execute(q)).scalars().all()

    points = []
    for row in rows:
        hit = next((a for a in row.all_sectors if a["sector"] == sector), None)
        if hit is None:
            continue
        top_strong_row = next((t for t in row.top_strong if t["sector"] == sector), None)
        top_rev_row = next((t for t in row.top_reversal if t["sector"] == sector), None)
        points.append({
            "date": row.date_str,
            "strong_score": hit.get("strong_score"),
            "strong_rank": hit.get("strong_rank"),
            "reversal_score": top_rev_row["reversal_score"] if top_rev_row else None,
            "reversal_rank": hit.get("reversal_rank"),
            "today_rank": hit.get("today_rank"),
            "recent_avg_rank": hit.get("recent_avg_rank"),
            "long_avg_rank": hit.get("long_avg_rank"),
            "in_top_strong": top_strong_row is not None,
            "in_top_reversal": top_rev_row is not None,
        })
    if not points:
        raise SectorNotFound(f"板块 '{sector}' 在最近 {days} 天无记录")
    return {"sector": sector, "days": days, "points": points}


async def load_board_history(board: str, days: int, top_n: int = 10) -> dict:
    if board not in {"strong", "reversal"}:
        raise ValueError(f"board 必须是 strong 或 reversal，实际 {board}")
    async with AsyncSessionLocal() as s:
        q = (select(SectorSignal)
             .order_by(SectorSignal.date_str.desc())
             .limit(days))
        rows = (await s.execute(q)).scalars().all()
    key = "top_strong" if board == "strong" else "top_reversal"
    daily = [{"date": r.date_str, "sectors": [x["sector"] for x in getattr(r, key)[:top_n]]} for r in rows]
    return {"days": days, "board": board, "daily_top10": daily}
```

- [ ] **Step 2: 运行 async 测试**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_sector_signal.py -v 2>&1 | tail -40
```
Expected: 全部测试 PASSED。

- [ ] **Step 3: Commit**

```bash
git add backend/services/sector_signal_service.py
git commit -m "feat(sector-signal): 持久化层（async）+ 历史查询"
```

---

## Task 10: 独立路由模块（端点 1 + 2 + 3）+ main.py 挂载

**Files:**
- Create: `backend/api/sector_signal_api.py`
- Modify: `backend/main.py`（只新增 import + include_router，不动现有代码）

**零侵入说明**：不修改 `statistics_api.py`。新路由走独立前缀 `/api/sector-signal`，`main.py` 只增不改。

- [ ] **Step 1: 新建 `backend/api/sector_signal_api.py`**

```python
# backend/api/sector_signal_api.py
"""板块信号榜 API（独立路由模块）。

路由前缀：/api/sector-signal
端点：
  GET  /                    查询榜单（缓存命中 / 未命中实时计算）
  POST /recompute           强制重算
  GET  /history             历史查询（单板块时序 / 榜单成分）
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user
from config.sector_signal_config import TOP_N_CHOICES, TOP_N_DEFAULT
from models.models import User
from models.sector_signal_model import SectorSignal  # noqa: F401  强制注册到 Base
from services import sector_signal_service as sig_svc
from services.sector_signal_service import (
    InsufficientHistory, SectorNotFound, SourceFileMissing,
)
from utils.beijing_time import beijing_today_str

router = APIRouter()


class RecomputeBody(BaseModel):
    date: str


@router.get("/")
async def get_sector_signal(
    date: Optional[str] = None,
    top_n: int = TOP_N_DEFAULT,
    current_user: User = Depends(get_current_user),
):
    if top_n not in TOP_N_CHOICES:
        raise HTTPException(status_code=400, detail={"code": "INVALID_TOP_N", "message": f"top_n 必须是 {sorted(TOP_N_CHOICES)} 之一"})

    if date is None:
        date = sig_svc.find_latest_date_with_source()
        if date is None:
            raise HTTPException(status_code=404, detail={"code": "SOURCE_FILE_MISSING", "message": "无可用的 public 文件"})
    else:
        try:
            parsed = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail={"code": "INVALID_DATE", "message": "日期格式错误（YYYY-MM-DD）"})
        if parsed.isoformat() > beijing_today_str():
            raise HTTPException(status_code=400, detail={"code": "INVALID_DATE", "message": "不能查询未来日期"})

    try:
        result = await sig_svc.get_or_compute(date)
    except SourceFileMissing as e:
        raise HTTPException(status_code=404, detail={"code": "SOURCE_FILE_MISSING", "message": str(e)})
    except InsufficientHistory as e:
        raise HTTPException(status_code=422, detail={"code": "INSUFFICIENT_HISTORY", "message": str(e)})
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("compute_failed")
        raise HTTPException(status_code=500, detail={"code": "COMPUTE_FAILED", "message": str(e)})

    return {
        **result,
        "top_strong": result["top_strong"][:top_n],
        "top_reversal": result["top_reversal"][:top_n],
    }


@router.post("/recompute")
async def recompute_sector_signal(
    body: RecomputeBody,
    current_user: User = Depends(get_current_user),
):
    try:
        datetime.strptime(body.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "INVALID_DATE", "message": "日期格式错误"})
    try:
        return await sig_svc.recompute(body.date)
    except SourceFileMissing as e:
        raise HTTPException(status_code=404, detail={"code": "SOURCE_FILE_MISSING", "message": str(e)})
    except InsufficientHistory as e:
        raise HTTPException(status_code=422, detail={"code": "INSUFFICIENT_HISTORY", "message": str(e)})


@router.get("/history")
async def get_sector_signal_history(
    sector: Optional[str] = None,
    days: int = 30,
    board: str = "strong",
    current_user: User = Depends(get_current_user),
):
    if not (1 <= days <= 180):
        raise HTTPException(status_code=400, detail={"code": "INVALID_DAYS", "message": "days 必须在 1-180"})
    if board not in {"strong", "reversal"}:
        raise HTTPException(status_code=400, detail={"code": "INVALID_BOARD", "message": "board 必须是 strong 或 reversal"})
    if sector:
        try:
            return await sig_svc.load_sector_history(sector, days)
        except SectorNotFound as e:
            raise HTTPException(status_code=404, detail={"code": "SECTOR_NOT_FOUND", "message": str(e)})
    return await sig_svc.load_board_history(board, days, top_n=10)
```

> **注意路由顺序（CLAUDE.md 经验教训 10）**：`/recompute` 和 `/history` 是 literal path，`/` 是根路径，FastAPI 路由匹配无冲突。

- [ ] **Step 2: `main.py` 最小挂载（新增 1 行 import + 1 行 include_router）**

定位 `main.py:8` 的 `from api import ...` 行，**另起一行** 追加（不要并入原行，便于 diff 清晰）：

```python
from api import sector_signal_api
```

定位 `main.py:161` 附近的最后一个 `app.include_router(...)` 行之后，新增一行：

```python
app.include_router(sector_signal_api.router, prefix=f"{settings.API_PREFIX}/sector-signal", tags=["板块信号"])
```

- [ ] **Step 3: 重启后端，建表 + 挂载生效**

```bash
cd /Users/xiayanji/qbox/aistock && ./deploy.sh restart
docker exec -i $(docker ps --filter name=mysql -q) mysql -uroot -proot aistock -e "SHOW TABLES LIKE 'sector_signal';"
```
Expected: `sector_signal` 表存在。后端日志无错误。

- [ ] **Step 4: 写 API 黑盒测试（追加到 test_sector_signal.py 末尾）**

```python
# ---------- API 端点测试 ----------

from httpx import AsyncClient, ASGITransport


async def _mock_user_override():
    from main import app
    from api import auth as auth_mod
    from models.models import User

    async def _fake_user():
        return User(id=1, username="test", email="t@t", password_hash="x")

    app.dependency_overrides[auth_mod.get_current_user] = _fake_user
    return app


@pytest.mark.asyncio
async def test_api_sector_signal_happy(tmp_path, monkeypatch):
    monkeypatch.setattr(sig_svc, "BASE_EXCEL_DIR", str(tmp_path))
    fixture_src = os.path.join(os.path.dirname(__file__), "fixtures", "sector_signal_sample.xlsx")
    import shutil
    d = tmp_path / "2026-04-23" / "public"
    d.mkdir(parents=True)
    shutil.copy(fixture_src, d / "8涨幅排名-20260423.xlsx")

    app = await _mock_user_override()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/sector-signal/?date=2026-04-23&top_n=10")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["date"] == "2026-04-23"
            assert len(data["top_strong"]) <= 10
            assert len(data["top_reversal"]) <= 10
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_sector_signal_invalid_top_n():
    app = await _mock_user_override()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/sector-signal/?top_n=15")
            assert r.status_code == 400
            assert r.json()["detail"]["code"] == "INVALID_TOP_N"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_sector_signal_source_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(sig_svc, "BASE_EXCEL_DIR", str(tmp_path))
    app = await _mock_user_override()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/sector-signal/?date=2026-04-23")
            assert r.status_code == 404
            assert r.json()["detail"]["code"] == "SOURCE_FILE_MISSING"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_recompute_overwrites(tmp_path, monkeypatch):
    monkeypatch.setattr(sig_svc, "BASE_EXCEL_DIR", str(tmp_path))
    fixture_src = os.path.join(os.path.dirname(__file__), "fixtures", "sector_signal_sample.xlsx")
    import shutil
    d = tmp_path / "2026-04-23" / "public"
    d.mkdir(parents=True)
    shutil.copy(fixture_src, d / "8涨幅排名-20260423.xlsx")

    app = await _mock_user_override()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/api/sector-signal/?date=2026-04-23")
            r = await client.post("/api/sector-signal/recompute", json={"date": "2026-04-23"})
            assert r.status_code == 200
            assert r.json()["date"] == "2026-04-23"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_history_board(tmp_path, monkeypatch):
    monkeypatch.setattr(sig_svc, "BASE_EXCEL_DIR", str(tmp_path))
    fixture_src = os.path.join(os.path.dirname(__file__), "fixtures", "sector_signal_sample.xlsx")
    import shutil
    d = tmp_path / "2026-04-23" / "public"
    d.mkdir(parents=True)
    shutil.copy(fixture_src, d / "8涨幅排名-20260423.xlsx")

    app = await _mock_user_override()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/api/sector-signal/?date=2026-04-23")
            r = await client.get("/api/sector-signal/history?days=10&board=strong")
            assert r.status_code == 200
            data = r.json()
            assert data["board"] == "strong"
            assert isinstance(data["daily_top10"], list)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_history_invalid_days():
    app = await _mock_user_override()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/sector-signal/history?days=500")
            assert r.status_code == 400
            assert r.json()["detail"]["code"] == "INVALID_DAYS"
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 5: 运行全部测试**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_sector_signal.py -v 2>&1 | tail -40
```
Expected: 全部 PASSED。

- [ ] **Step 6: Commit**

```bash
git add backend/api/sector_signal_api.py backend/main.py backend/tests/test_sector_signal.py
git commit -m "feat(sector-signal): 独立路由模块 + main.py 最小挂载"
```

---

## Task 11: (已合并到 Task 10)

Task 11 的端点 2 + 3 已在 Task 10 一并实现（同一独立路由模块内）。跳过。

---

## Task 12: 前端组件 SectorSignalPanel

**Files:**
- Create: `frontend/src/components/SectorSignalPanel.vue`

- [ ] **Step 1: 写前端组件**

```vue
<!-- frontend/src/components/SectorSignalPanel.vue -->
<template>
  <el-card shadow="hover" class="sector-signal-panel" v-loading="loading">
    <template #header>
      <div class="panel-header">
        <span class="panel-title">板块信号榜</span>
        <div class="panel-controls">
          <el-select v-model="topN" size="small" style="width: 100px">
            <el-option :value="10" label="Top 10" />
            <el-option :value="20" label="Top 20" />
            <el-option :value="30" label="Top 30" />
          </el-select>
          <el-button size="small" :icon="Refresh" @click="refresh" :loading="refreshing">强制重算</el-button>
          <span v-if="meta" class="panel-meta">
            {{ meta.date }} · {{ meta.sector_count }} 板块 · 长窗 {{ meta.window_long_days }} 日
          </span>
        </div>
      </div>
    </template>

    <el-alert v-if="errorMsg" type="error" :closable="false" show-icon>
      {{ errorMsg }}
    </el-alert>

    <el-row :gutter="16" v-if="!errorMsg">
      <el-col :span="12">
        <div class="board-title">持续强势榜</div>
        <el-table :data="strongSlice" size="small" border stripe empty-text="暂无数据">
          <el-table-column label="#" type="index" width="40" />
          <el-table-column prop="sector" label="板块" min-width="100" />
          <el-table-column prop="strong_score" label="强势分" width="80" sortable>
            <template #default="{ row }">
              <el-tooltip placement="top">
                <template #content>
                  <div>子分：</div>
                  <div v-for="(v, k) in row.sub_scores" :key="k">{{ k }}: {{ v }}</div>
                </template>
                <strong>{{ row.strong_score }}</strong>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column prop="today_pct" label="当日%" width="70">
            <template #default="{ row }">{{ fmtPct(row.today_pct) }}</template>
          </el-table-column>
          <el-table-column prop="recent_avg_rank" label="5日均排名" width="90" />
          <el-table-column prop="long_avg_rank" label="20日均排名" width="90" />
          <el-table-column prop="top20_count" label="进前20(次)" width="100" />
        </el-table>
      </el-col>

      <el-col :span="12">
        <div class="board-title">低位启动榜</div>
        <el-table :data="reversalSlice" size="small" border stripe empty-text="暂无数据">
          <el-table-column label="#" type="index" width="40" />
          <el-table-column prop="sector" label="板块" min-width="100" />
          <el-table-column prop="reversal_score" label="反转分" width="80" sortable>
            <template #default="{ row }">
              <el-tooltip placement="top">
                <template #content>
                  <div>子分：</div>
                  <div v-for="(v, k) in row.sub_scores" :key="k">{{ k }}: {{ v }}</div>
                </template>
                <strong>{{ row.reversal_score }}</strong>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column prop="today_pct" label="当日%" width="70">
            <template #default="{ row }">{{ fmtPct(row.today_pct) }}</template>
          </el-table-column>
          <el-table-column prop="ytd_pct" label="年初%" width="80">
            <template #default="{ row }">{{ fmtPct(row.ytd_pct) }}</template>
          </el-table-column>
          <el-table-column prop="recent_avg_rank" label="5日均排名" width="90" />
          <el-table-column prop="early_avg_rank" label="前半段均排名" width="110" />
          <el-table-column prop="first_enter_top20_date" label="首入前20" width="100" />
        </el-table>
      </el-col>
    </el-row>
  </el-card>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import axios from 'axios'

const props = defineProps({
  date: { type: String, default: null },
})

const topN = ref(10)
const loading = ref(false)
const refreshing = ref(false)
const errorMsg = ref('')
const payload = ref(null)

const meta = computed(() => payload.value && {
  date: payload.value.date,
  sector_count: payload.value.sector_count,
  window_long_days: payload.value.window_long_days,
})

const strongSlice = computed(() => (payload.value?.top_strong || []).slice(0, topN.value))
const reversalSlice = computed(() => (payload.value?.top_reversal || []).slice(0, topN.value))

function fmtPct(v) {
  if (v === null || v === undefined) return '--'
  return `${v > 0 ? '+' : ''}${v.toFixed(2)}%`
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const params = { top_n: 30 }
    if (props.date) params.date = props.date
    const r = await axios.get('/api/sector-signal/', { params })
    payload.value = r.data
  } catch (e) {
    const detail = e.response?.data?.detail
    errorMsg.value = detail?.message || '加载失败'
    payload.value = null
  } finally {
    loading.value = false
  }
}

async function refresh() {
  if (!payload.value?.date && !props.date) return
  refreshing.value = true
  try {
    await axios.post('/api/sector-signal/recompute', {
      date: props.date || payload.value.date,
    })
    await load()
  } catch (e) {
    errorMsg.value = e.response?.data?.detail?.message || '重算失败'
  } finally {
    refreshing.value = false
  }
}

watch(() => props.date, load)
onMounted(load)

defineExpose({ reload: load })
</script>

<style scoped>
.sector-signal-panel { margin-bottom: 16px; }
.panel-header { display: flex; justify-content: space-between; align-items: center; }
.panel-title { font-weight: 600; font-size: 15px; }
.panel-controls { display: flex; gap: 8px; align-items: center; }
.panel-meta { color: #909399; font-size: 12px; margin-left: 8px; }
.board-title { font-weight: 600; margin-bottom: 8px; color: #303133; }
</style>
```

- [ ] **Step 2: 本地语法检查**

```bash
cd /Users/xiayanji/qbox/aistock/frontend && npx vue-tsc --noEmit 2>&1 | tail -10 || true
```
Expected: 无针对 `SectorSignalPanel.vue` 的新错误（原有错误可忽略）。若项目无 vue-tsc 则跳过此步。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SectorSignalPanel.vue
git commit -m "feat(sector-signal): 前端 SectorSignalPanel 组件"
```

---

## Task 13: 挂载到板块涨幅分析 Tab（前端最小插入）

**Files:**
- Modify: `frontend/src/views/Statistics.vue`（只新增 3 处，不修改任何现有元素）

**零侵入原则**：只新增 import / computed / 组件标签，不改动现有模板、脚本、样式中的任何一行。如果你在修改时发现必须改动现有代码才能让组件工作，停下来先问用户。

- [ ] **Step 1: 定位插入点**

```bash
cd /Users/xiayanji/qbox/aistock && grep -n "板块涨幅分析\|name=\"ranking\"" frontend/src/views/Statistics.vue
```
Expected：看到 `<el-tab-pane label="板块涨幅分析" name="ranking">` 所在行号（spec 调研为 311 行）。

- [ ] **Step 2: 在 `<script setup>` import 区域追加**

```javascript
import SectorSignalPanel from '@/components/SectorSignalPanel.vue'
```

- [ ] **Step 3: 在 `<el-tab-pane label="板块涨幅分析" name="ranking">` 开头、`<div v-loading="rankingLoading">` 之后、`<div class="ranking-toolbar">` 之前，插入组件**

找到类似这样的片段：
```html
<el-tab-pane label="板块涨幅分析" name="ranking">
  <div v-loading="rankingLoading">
    <!-- 顶部工具栏 -->
    <div class="ranking-toolbar">
```

改为：
```html
<el-tab-pane label="板块涨幅分析" name="ranking">
  <div v-loading="rankingLoading">
    <!-- 板块信号榜（新增） -->
    <SectorSignalPanel :date="rankingSelectedDate" />

    <!-- 顶部工具栏 -->
    <div class="ranking-toolbar">
```

其中 `rankingSelectedDate` 是从现有 ranking 数据里派生的日期。检查 `rankingParsed` 或 `rankingAvailable` 里有没有 `date_str` 字段，`<script setup>` 里加一个 computed：

```javascript
const rankingSelectedDate = computed(() => {
  const hit = rankingAvailable.value?.find(x => x.id === rankingResultId.value)
  return hit?.date_str || null
})
```

如该变量已存在则复用。`computed` 需从 `vue` import（如未 import 则加）。

- [ ] **Step 4: 前端构建并启动查看效果**

```bash
cd /Users/xiayanji/qbox/aistock && ./deploy.sh build && ./deploy.sh restart
```
Expected: 无构建错误，前端启动。

- [ ] **Step 5: 浏览器验证**

打开 http://localhost:7654 → 登录 → 统计分析 → 「板块涨幅分析」Tab，顶部应出现两张榜单。
核对榜单首行与 `data/excel/涨幅排名/{最新date}/public/8涨幅排名*.xlsx` 对账：
- Top 1 持续强势：排名靠前、年初 B 列数值大、20 日均排名小
- Top 1 低位启动：年初涨幅负 / 小、近 5 日均排名 < N/2、前半段均排名 ≥ N/2

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/Statistics.vue
git commit -m "feat(sector-signal): Statistics.vue 挂载 SectorSignalPanel"
```

---

## Task 14: 端到端回归

- [ ] **Step 1: 全量后端测试**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/ -v 2>&1 | tail -40
```
Expected: 所有测试 PASSED（包括 `test_sector_signal.py` 和之前的存量测试）。

- [ ] **Step 2: 调用 /verify**

让用户手动执行 `/verify`，确认构建/类型/测试/安全扫描全过。

- [ ] **Step 3: 最终验收清单（人工）**

- [ ] 浏览器页面渲染正常、无控制台报错
- [ ] 切换 Top N（10/20/30）两榜表格行数正确变化
- [ ] 点"强制重算"按钮，后端日志显示重算、前端刷新成功
- [ ] 打开 MySQL 看 `sector_signal` 表有一条 / 多条记录，`config_snapshot` 字段含权重
- [ ] **Step 3: 手动请求 `/api/sector-signal/history?sector=XX&days=1` 和 `?days=10&board=strong` 各一次，均返回 200**

- [ ] **Step 4: 打 tag**

```bash
cd /Users/xiayanji/qbox/aistock && git log --oneline -20 | head
git tag feat-sector-signal
```

---

## 自审记录

**Spec 覆盖检查**（对照 `docs/superpowers/specs/2026-04-24-sector-signal-design.md`）：
- 架构与模块边界 → Task 1-3, 10, 12-13 ✓
- 评分算法（A 榜 5 子分 + 硬门槛 / D 榜 4 子分 + 硬门槛） → Task 7-8 ✓
- 权重配置 + 环境变量覆盖 → Task 1 ✓
- DB 模型（date_str 唯一 + JSON 列 + config_snapshot） → Task 2 ✓
- API 端点 1 / 2 / 3（查询 + 重算 + 历史，独立路由模块） → Task 10 ✓
- 前端组件（两榜 + Top N 切换 + 刷新按钮） → Task 12 ✓
- 日期联动 → Task 13 ✓
- 测试矩阵（14+ 个用例 + 解析层 fixture） → Task 3-11 ✓
- 经验教训预期（datetime 列排序 / to_numeric 兜底 / 北京时区） → Task 4 / Task 8 / Task 10 ✓
- **零侵入要求** → 新建独立模型文件 / 独立路由模块；main.py 只加 include_router；Statistics.vue 只加 3 行 ✓

**类型一致性**：
- `SectorSignal` 字段名在 Task 2 定义，Task 9/10 使用一致
- `compute_all` 返回结构在 Task 3 注释声明，Task 8 实现、Task 9 消费一致
- 异常类 `SourceFileMissing` / `InsufficientHistory` / `SectorNotFound` Task 3 声明，后续统一使用

**Placeholder 扫描**：已确认每个代码 step 都是完整可运行的代码，命令有明确 Expected。

---

## 执行方式

**Plan 完成，文件保存至 `docs/superpowers/plans/2026-04-24-sector-signal-plan.md`。**

两种执行方式：

1. **Subagent 驱动（推荐）** — 每任务派遣独立 subagent，两阶段审查，快速迭代
2. **内联执行** — 本会话执行，checkpoint 批量审查

请选择。
