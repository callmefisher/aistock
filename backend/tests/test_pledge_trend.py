"""阶段3 - 质押趋势算法纯函数测试。"""
from services.pledge_trend import compute_trend, mann_kendall


def _mk_rec(date, accum, pre_accum):
    return {"公告日期": date, "累计质押比例": accum, "前次累计质押比例": pre_accum}


# ---------- Mann-Kendall 基础检验 ----------

def test_mk_monotonic_decreasing():
    """完全单调递减 → Z < 0 p < 0.05。"""
    z, p = mann_kendall([17.74, 13.73, 11.99, 9.78, 8.14])
    assert z < 0
    assert p < 0.05


def test_mk_monotonic_increasing():
    z, p = mann_kendall([1.0, 2.0, 3.0, 4.0, 5.0])
    assert z > 0
    assert p < 0.05


def test_mk_no_trend():
    """随机振荡 → p > 0.05。"""
    z, p = mann_kendall([3.0, 5.0, 3.0, 5.0, 3.0, 5.0])
    # 不期待具体 z，只期待 p 不显著
    assert p > 0.05


def test_mk_too_few_samples():
    """样本 < 4 直接返回 (0, 1)。"""
    z, p = mann_kendall([1.0, 2.0, 3.0])
    assert z == 0.0 and p == 1.0


# ---------- compute_trend: MK 默认 ----------

def test_trend_mk_strong_decrease_002768():
    """002768 实测：累计比例 17.74 → 13.73 → 11.99 → 9.78 → 8.14。"""
    records = [
        _mk_rec("2025-04-20", 17.74, 22.00),  # 前次起始无意义，只看累计序列
        _mk_rec("2025-08-30", 13.73, 17.74),
        _mk_rec("2025-12-17", 11.99, 13.73),
        _mk_rec("2026-01-22", 9.78, 11.99),
        _mk_rec("2026-04-14", 8.14, 9.78),
    ]
    result = compute_trend(records, anchor_date="2026-04-14")
    assert result["持续递减（一年内）"] == "Y"
    assert result["持续递增（一年内）"] == ""
    assert result["质押异动"] == "小幅转减"  # Δ = 8.14 - 9.78 = -1.64，|Δ|∈[0.5,3)


def test_trend_mk_strong_increase():
    records = [
        _mk_rec("2025-01-10", 2.0, 1.0),
        _mk_rec("2025-04-10", 4.0, 2.0),
        _mk_rec("2025-07-10", 6.0, 4.0),
        _mk_rec("2025-10-10", 8.0, 6.0),
        _mk_rec("2026-01-10", 10.0, 8.0),
    ]
    result = compute_trend(records, anchor_date="2026-01-10")
    assert result["持续递增（一年内）"] == "Y"
    assert result["持续递减（一年内）"] == ""


def test_trend_mk_too_few_returns_empty():
    records = [
        _mk_rec("2025-01-10", 5.0, 4.0),
        _mk_rec("2025-06-10", 6.0, 5.0),
    ]
    result = compute_trend(records, anchor_date="2025-06-10")
    assert result["持续递增（一年内）"] == ""
    assert result["持续递减（一年内）"] == ""


def test_trend_mk_small_sample_strict_monotonic_fallback():
    """小样本兜底：n=4 严格单调递减 → down（MK 在 n=4 无法达到 p<0.05）。

    这对应 002768.SZ 实测：聚合后 4 个点 [13.73, 11.99, 9.78, 8.14] 严格递减，
    但 MK Z≈-1.70 p≈0.089 > 0.05；兜底规则应判为 down。
    """
    records = [
        _mk_rec("2025-08-30", 13.73, 17.74),
        _mk_rec("2025-12-17", 11.99, 13.73),
        _mk_rec("2026-01-22", 9.78, 11.99),
        _mk_rec("2026-04-14", 8.14, 9.78),
    ]
    result = compute_trend(records, anchor_date="2026-04-14")
    assert result["持续递减（一年内）"] == "Y"


def test_empty_records():
    result = compute_trend([], anchor_date="2026-01-10")
    assert result == {"持续递增（一年内）": "", "持续递减（一年内）": "", "质押异动": ""}


# ---------- compute_trend: 月度下采样 ----------

def test_trend_monthly_allows_reversals():
    """4 月降、5 月小反弹、6 月再降 → 允许 2 次反转 → 判 down。"""
    records = [
        _mk_rec("2025-04-10", 10.0, 11.0),
        _mk_rec("2025-05-10", 10.5, 10.0),  # 反弹
        _mk_rec("2025-06-10", 9.0, 10.5),
        _mk_rec("2025-07-10", 8.0, 9.0),
        _mk_rec("2026-01-10", 5.0, 8.0),
    ]
    result = compute_trend(records, anchor_date="2026-01-10",
                           trend_algo="monthly_downsample", b_max_reversals=2)
    assert result["持续递减（一年内）"] == "Y"


def test_trend_monthly_reversals_exceed():
    """多次反转 → none。"""
    records = [
        _mk_rec("2025-01-10", 1.0, 0.0),
        _mk_rec("2025-02-10", 3.0, 1.0),
        _mk_rec("2025-03-10", 2.0, 3.0),
        _mk_rec("2025-04-10", 4.0, 2.0),
        _mk_rec("2025-05-10", 1.0, 4.0),
        _mk_rec("2025-06-10", 5.0, 1.0),
    ]
    result = compute_trend(records, anchor_date="2025-06-10",
                           trend_algo="monthly_downsample", b_max_reversals=2)
    assert result["持续递增（一年内）"] == ""
    assert result["持续递减（一年内）"] == ""


# ---------- compute_trend: 线性回归 ----------

def test_trend_linear_high_r2_up():
    records = [
        _mk_rec(f"2025-{m:02d}-10", float(m), float(m - 1)) for m in range(1, 13)
    ]
    result = compute_trend(records, anchor_date="2025-12-10",
                           trend_algo="linear_regression", c_min_r2=0.7)
    assert result["持续递增（一年内）"] == "Y"


def test_trend_linear_low_r2_returns_none():
    """强振荡 → R² 低 → none。"""
    records = [
        _mk_rec(f"2025-{m:02d}-10",
                10.0 + (5 if m % 2 else -5), 10.0) for m in range(1, 13)
    ]
    result = compute_trend(records, anchor_date="2025-12-10",
                           trend_algo="linear_regression", c_min_r2=0.7)
    assert result["持续递增（一年内）"] == ""
    assert result["持续递减（一年内）"] == ""


# ---------- 异动分类 ----------

def test_event_small_increase():
    """Δ = +1 (在 [0.5, 3) 内) → 小幅转增。"""
    records = [_mk_rec("2026-04-14", 11.0, 10.0)]
    result = compute_trend(records, anchor_date="2026-04-14")
    assert result["质押异动"] == "小幅转增"


def test_event_large_increase():
    """Δ = +5 ≥ 3 → 大幅激增。"""
    records = [_mk_rec("2026-04-14", 15.0, 10.0)]
    result = compute_trend(records, anchor_date="2026-04-14")
    assert result["质押异动"] == "大幅激增"


def test_event_large_decrease():
    """Δ = -5 → 大幅骤减。"""
    records = [_mk_rec("2026-04-14", 5.0, 10.0)]
    result = compute_trend(records, anchor_date="2026-04-14")
    assert result["质押异动"] == "大幅骤减"


def test_event_no_change():
    """|Δ| < 0.5 → 无变化。"""
    records = [_mk_rec("2026-04-14", 10.2, 10.0)]
    result = compute_trend(records, anchor_date="2026-04-14")
    assert result["质押异动"] == "本次质押趋势无变化"


def test_event_no_matching_date():
    """records 中无匹配 anchor_date 的行 → 空。"""
    records = [_mk_rec("2026-01-10", 5.0, 10.0)]
    result = compute_trend(records, anchor_date="2026-04-14")
    assert result["质押异动"] == ""


def test_event_multi_rows_same_day():
    """同一天多笔：取 max(累计) - min(前次累计)。"""
    records = [
        _mk_rec("2026-04-14", 8.14, 9.78),  # 一条解押
        _mk_rec("2026-04-14", 9.57, 8.14),  # 一条新增质押
    ]
    result = compute_trend(records, anchor_date="2026-04-14")
    # max(accum)=9.57, min(pre)=8.14, Δ=1.43 → 小幅转增
    assert result["质押异动"] == "小幅转增"
