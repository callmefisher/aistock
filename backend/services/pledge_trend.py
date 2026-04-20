"""质押异动和趋势算法（纯函数，无 I/O）。

三种趋势算法：
- mann_kendall（默认）：非参数趋势检验，对非均匀时间采样稳健
- monthly_downsample：月末值单调性（≤ 反转阈值）
- linear_regression：一次多项式拟合 + R² 阈值

异动分类（当日 Δ = max(累计质押比例) - min(前次累计质押比例)）：
  |Δ| < no_change_threshold  → "本次质押趋势无变化"
  Δ > 0，|Δ| ≥ large          → "大幅激增"
  Δ > 0，|Δ| < large          → "小幅转增"
  Δ < 0，|Δ| ≥ large          → "大幅骤减"
  Δ < 0，|Δ| < large          → "小幅转减"
"""
from __future__ import annotations

import math
from collections import OrderedDict
from typing import Iterable, Optional

import numpy as np


# ---------------- 趋势算法 ----------------

def mann_kendall(values: list[float]) -> tuple[float, float]:
    """返回 (Z, p_value)。Z > 0 且 p 低 → 递增；Z < 0 且 p 低 → 递减。"""
    n = len(values)
    if n < 4:
        return 0.0, 1.0
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            d = values[j] - values[i]
            s += 1 if d > 0 else (-1 if d < 0 else 0)
    var_s = n * (n - 1) * (2 * n + 5) / 18.0
    if var_s <= 0:
        return 0.0, 1.0
    if s > 0:
        z = (s - 1) / math.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / math.sqrt(var_s)
    else:
        z = 0.0
    # 双尾 p 值，使用标准正态 CDF
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return z, p


def _detect_trend_mk(series: list[tuple[str, float]], p_threshold: float) -> str:
    """返回 'up' / 'down' / 'none'。

    小样本兜底：若 3 ≤ n < 10 且序列严格单调（所有点都同向），
    直接判 up/down（金融意义上的明显趋势，但 MK 统计检验在小样本
    下 p 值必然偏高，会漏判）。
    """
    n = len(series)
    if n < 3:
        return "none"
    vals = [v for _, v in series]

    # 小样本严格单调兜底（包括 n≥4 的情况）
    diffs = [vals[i + 1] - vals[i] for i in range(n - 1)]
    if all(d > 0 for d in diffs):
        return "up"
    if all(d < 0 for d in diffs):
        return "down"

    if n < 4:
        return "none"
    z, p = mann_kendall(vals)
    if p < p_threshold:
        if z > 0:
            return "up"
        if z < 0:
            return "down"
    return "none"


def _detect_trend_monthly(series: list[tuple[str, float]], max_reversals: int,
                          min_delta: float = 0.01) -> str:
    """按月末值取最后一条，数相邻点方向反转数；≤ 阈值 且 首末差显著 → up/down。"""
    if len(series) < 2:
        return "none"
    # 月末聚合：同月多条取最后一条（输入已升序）
    by_month: "OrderedDict[str, float]" = OrderedDict()
    for d, v in series:
        month = d[:7]  # YYYY-MM
        by_month[month] = v
    months = list(by_month.items())
    if len(months) < 2:
        return "none"
    vals = [v for _, v in months]
    diffs = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
    # 数方向反转
    prev_sign = 0
    reversals = 0
    for d in diffs:
        if abs(d) < min_delta:
            continue
        cur_sign = 1 if d > 0 else -1
        if prev_sign != 0 and cur_sign != prev_sign:
            reversals += 1
        prev_sign = cur_sign
    total_delta = vals[-1] - vals[0]
    if abs(total_delta) < min_delta:
        return "none"
    if reversals <= max_reversals:
        return "up" if total_delta > 0 else "down"
    return "none"


def _detect_trend_linear(series: list[tuple[str, float]], min_r2: float) -> str:
    """线性回归 slope & R²。R² ≥ 阈值 且 斜率显著 → up/down。"""
    if len(series) < 4:
        return "none"
    x = np.arange(len(series), dtype=float)
    y = np.array([v for _, v in series], dtype=float)
    # polyfit degree=1
    slope, intercept = np.polyfit(x, y, 1)
    y_pred = slope * x + intercept
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    if ss_tot <= 0:
        return "none"
    r2 = 1.0 - ss_res / ss_tot
    if r2 >= min_r2 and abs(slope) > 1e-6:
        return "up" if slope > 0 else "down"
    return "none"


# ---------------- 异动分类 ----------------

def _detect_event(records: list[dict], anchor_date: str,
                  no_change_th: float, large_th: float) -> str:
    """返回 5 种分类或空字符串。"""
    today_rows = [r for r in records if str(r.get("公告日期", "")).strip() == anchor_date]
    if not today_rows:
        return ""
    try:
        accum_after_vals = [float(r["累计质押比例"]) for r in today_rows
                            if r.get("累计质押比例") not in (None, "")]
        accum_before_vals = [float(r["前次累计质押比例"]) for r in today_rows
                             if r.get("前次累计质押比例") not in (None, "")]
    except (TypeError, ValueError):
        return ""
    if not accum_after_vals or not accum_before_vals:
        return ""
    delta = max(accum_after_vals) - min(accum_before_vals)
    if abs(delta) < no_change_th:
        return "本次质押趋势无变化"
    if delta > 0:
        return "大幅激增" if delta >= large_th else "小幅转增"
    return "大幅骤减" if abs(delta) >= large_th else "小幅转减"


# ---------------- 对外入口 ----------------

def _aggregate_by_date(records: list[dict], value_col: str = "累计质押比例"
                       ) -> list[tuple[str, float]]:
    """按公告日期聚合 records → 升序的 (date, value) 列表；同日取最后一条的 value。"""
    by_date: "OrderedDict[str, float]" = OrderedDict()
    # records 假设已按公告日期升序
    for r in records:
        d = str(r.get("公告日期", "")).strip()
        v = r.get(value_col)
        if not d or v in (None, ""):
            continue
        try:
            by_date[d] = float(v)
        except (TypeError, ValueError):
            continue
    # 返回时排序确保升序
    return sorted(by_date.items(), key=lambda kv: kv[0])


def compute_trend(
    records: list[dict],
    anchor_date: str,
    trend_algo: str = "mann_kendall",
    mk_pvalue: float = 0.05,
    b_max_reversals: int = 2,
    c_min_r2: float = 0.7,
    event_no_change: float = 0.5,
    event_large: float = 3.0,
) -> dict[str, str]:
    """主入口。records 应为升序 (按公告日期) 的标准化字典列表。"""
    if not records:
        return {"持续递增（一年内）": "", "持续递减（一年内）": "", "质押异动": ""}

    series = _aggregate_by_date(records, value_col="累计质押比例")
    if trend_algo == "monthly_downsample":
        trend = _detect_trend_monthly(series, b_max_reversals)
    elif trend_algo == "linear_regression":
        trend = _detect_trend_linear(series, c_min_r2)
    else:  # default mann_kendall
        trend = _detect_trend_mk(series, mk_pvalue)

    event = _detect_event(records, anchor_date, event_no_change, event_large)

    return {
        "持续递增（一年内）": "Y" if trend == "up" else "",
        "持续递减（一年内）": "Y" if trend == "down" else "",
        "质押异动": event,
    }
