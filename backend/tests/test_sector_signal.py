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
import pytest_asyncio

from models.sector_signal_model import SectorSignal  # noqa: F401 — ensure registered to Base.metadata
from services import sector_signal_service as sig_svc
from services.sector_signal_service import (
    SourceFileMissing, InsufficientHistory, SectorNotFound,
)


@pytest_asyncio.fixture(autouse=True)
async def _patch_async_session(monkeypatch):
    """确保 service 层用 test DB（SQLite in-memory），而不是生产 MySQL。
    conftest 的 db_session fixture 会建表；但本文件的 async 测试不依赖 db_session fixture，
    所以要单独建表 + 替换 AsyncSessionLocal。"""
    from tests.conftest import test_engine, TestAsyncSessionLocal
    from core.database import Base
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(sig_svc, "AsyncSessionLocal", TestAsyncSessionLocal)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


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
    # 读 DB 验证 updated_at >= created_at（使用已被 monkeypatch 替换的 AsyncSessionLocal）
    from sqlalchemy import select
    from models.sector_signal_model import SectorSignal
    async with sig_svc.AsyncSessionLocal() as s:
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
