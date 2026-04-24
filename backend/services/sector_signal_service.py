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
    date_cols = [c for c in df.columns if isinstance(c, datetime)]
    date_cols.sort(reverse=True)  # 最新在前
    return date_cols


def filter_invalid_rows(df: pd.DataFrame, sector_col: str = "板块名称") -> pd.DataFrame:
    """过滤板块名为空 / 含 '妙想Choice' / 全列 NaN 的行。"""
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
    pattern = os.path.join(base_dir, date_str, "public", "8涨幅排名*.xlsx")
    matches = sorted(glob.glob(pattern))
    if not matches:
        # 兼容无 "8" 前缀的旧文件名（如 板块涨跌幅排名0415.xlsx 的 public 版本）
        pattern2 = os.path.join(base_dir, date_str, "public", "*涨幅排名*.xlsx")
        matches = sorted(glob.glob(pattern2))
    return matches[-1] if matches else None


def find_latest_date_with_source(base_dir: str = BASE_EXCEL_DIR) -> Optional[str]:
    """扫所有子目录，返回最新有 public 文件的日期（YYYY-MM-DD）。"""
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
    """读 public Excel 单 sheet，返回 DataFrame（保留原列头含 datetime 对象）。"""
    return pd.read_excel(path, sheet_name=0)


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
