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
    """升序排名 → 降序分位分。rank ∈ [1, N]，返回 ∈ (0, 100]。"""
    if n <= 0:
        return 0.0
    return round(100.0 * (n - rank + 1) / n, 4)


def compute_strong_score(row: dict, n: int) -> Optional[dict]:
    """单板块持续强势分。不满足硬门槛返回 None。

    row 需含:
      long_avg_rank, recent_avg_rank, ytd_asc_rank, mtd_asc_rank,
      top20_count, long_valid_days, recent_valid_days
    返回: {"strong_score": 82.45, "sub_scores": {...}}
    """
    # 硬门槛
    if row.get("recent_valid_days", 0) < MIN_RECENT_VALID:
        return None
    if row.get("long_valid_days", 0) < MIN_LONG_VALID:
        return None

    score_long = _rank_to_pct_score(row["long_avg_rank"], n)
    score_recent = _rank_to_pct_score(row["recent_avg_rank"], n)
    # 月初/年初：源表给的是 asc_rank（1=涨幅最小），"值大=强"的降序分位 = 100*asc_rank/n
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
    """单板块低位启动分。不满足硬门槛返回 None。

    reversal 子分需要在批次级别做 min-max，所以本函数只算 reversal_gap
    原始值，不做归一化；批次归一化在 compute_all() 里做。

    row 需含: recent_avg_rank, early_avg_rank, ytd_pct, ytd_asc_rank, mtd_asc_rank
    返回: {"reversal_gap_raw": 80.5, "sub_raw": {...}}  批次归一化前的中间结果
    """
    # 硬门槛 1: 年初涨幅必须低于全市场中位数
    if row["ytd_pct"] >= ytd_median_pct:
        return None
    # 硬门槛 2: 近 5 日均排名 ≤ N/2
    if row["recent_avg_rank"] > n * 0.5:
        return None
    # 硬门槛 3: 前半段均排名 ≥ N/2
    if row["early_avg_rank"] < n * 0.5:
        return None

    gap_raw = row["early_avg_rank"] - row["recent_avg_rank"]
    score_recent = _rank_to_pct_score(row["recent_avg_rank"], n)
    ytd_desc_pct = 100.0 * row["ytd_asc_rank"] / n
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
    """给定已读好的 public Excel DataFrame，返回两榜 + 全量分。

    返回:
    {
      "sector_count": N, "window_long_days": ..., "window_recent_days": ...,
      "all_sectors": [...], "top_strong": [...], "top_reversal": [...],
    }
    """
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
    source_file = find_source_excel(date_str, base_dir=BASE_EXCEL_DIR)
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
    """查 DB 命中即返回，否则读 Excel 算完写库再返回。"""
    if session is None:
        async with AsyncSessionLocal() as s:
            return await get_or_compute(date_str, s)
    existing = await _load_row(session, date_str)
    if existing:
        return _row_to_response(existing, date_str, existing.source_file)
    return await _compute_and_persist(date_str, session, overwrite=False)


async def recompute(date_str: str, session: Optional[AsyncSession] = None) -> dict:
    """绕过缓存，强制重算覆盖写入。"""
    if session is None:
        async with AsyncSessionLocal() as s:
            return await recompute(date_str, s)
    return await _compute_and_persist(date_str, session, overwrite=True)


async def load_sector_history(sector: str, days: int) -> dict:
    """端点 3 模式 A：单板块 N 天时序点列。"""
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
    """端点 3 模式 B：每日榜单 Top N 板块名列表。board in {strong, reversal}"""
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


# ---------- 自定义异常 ----------

class SourceFileMissing(Exception):
    pass


class InsufficientHistory(Exception):
    pass


class SectorNotFound(Exception):
    pass
