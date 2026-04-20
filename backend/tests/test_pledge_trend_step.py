"""阶段3 - _pledge_trend_analysis 步骤执行器测试。"""
import os
import tempfile
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from services.workflow_executor import WorkflowExecutor


@pytest.fixture
def tmpbase():
    with tempfile.TemporaryDirectory() as base:
        upload_dir = os.path.join(base, "质押", "2026-04-20")
        os.makedirs(upload_dir, exist_ok=True)
        yield base


def _input_df():
    return pd.DataFrame([
        {"序号": 1, "证券代码": "002768.SZ", "证券简称": "国恩股份",
         "最新公告日": "2026-04-14", "来源": "小盘"},
        {"序号": 2, "证券代码": "000001.SZ", "证券简称": "平安银行",
         "最新公告日": "2026-04-14", "来源": "中大盘"},
    ])


def _mock_ds_factory(mapping: dict):
    """mapping: {symbol: (records, source)}。"""
    class Fake:
        def __init__(self, *a, **kw): pass
        def get_history(self_inner, symbol, anchor, window_days=365):
            return mapping.get(symbol, ([], "empty"))
    return Fake


@pytest.mark.asyncio
async def test_missing_latest_date_column_returns_error(tmpbase):
    """输入 df 缺"最新公告日" → 步骤失败。"""
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    df = pd.DataFrame([{"证券代码": "002768"}])
    result = await ex._pledge_trend_analysis({}, df, date_str="2026-04-20")
    assert result["success"] is False
    assert "最新公告日" in result["message"]


@pytest.mark.asyncio
async def test_missing_anchor_row_returns_error(tmpbase):
    """任一行锚点为空 → 整步骤失败。"""
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    df = pd.DataFrame([
        {"证券代码": "002768", "证券简称": "国恩", "最新公告日": "2026-04-14"},
        {"证券代码": "000001", "证券简称": "平安", "最新公告日": ""},  # 缺锚点
    ])
    result = await ex._pledge_trend_analysis({}, df, date_str="2026-04-20")
    assert result["success"] is False
    assert "缺少'最新公告日'锚点" in result["message"]


@pytest.mark.asyncio
async def test_happy_path_writes_3_columns(tmpbase):
    """正常流程：3 列正确写入 + 文件生成。"""
    rec_decline = [
        {"公告日期": "2025-04-20", "累计质押比例": 17.74, "前次累计质押比例": 22.00},
        {"公告日期": "2025-08-30", "累计质押比例": 13.73, "前次累计质押比例": 17.74},
        {"公告日期": "2025-12-17", "累计质押比例": 11.99, "前次累计质押比例": 13.73},
        {"公告日期": "2026-01-22", "累计质押比例": 9.78,  "前次累计质押比例": 11.99},
        {"公告日期": "2026-04-14", "累计质押比例": 8.14,  "前次累计质押比例": 9.78},
    ]
    mapping = {
        "002768": (rec_decline, "eastmoney"),
        "000001": ([], "empty"),
    }
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    with patch("services.pledge_data_source.PledgeDataSource", _mock_ds_factory(mapping)), \
         patch("core.redis_client.get_redis", return_value=None):
        result = await ex._pledge_trend_analysis({}, _input_df(), date_str="2026-04-20")
    assert result["success"] is True
    assert "持续递增（一年内）" in result["columns"]
    assert "持续递减（一年内）" in result["columns"]
    assert "质押异动" in result["columns"]
    df_out = result["_df"]
    row_002768 = df_out[df_out["证券代码"] == "002768.SZ"].iloc[0]
    assert row_002768["持续递减（一年内）"] == "Y"
    assert row_002768["质押异动"] == "小幅转减"
    row_000001 = df_out[df_out["证券代码"] == "000001.SZ"].iloc[0]
    assert row_000001["持续递增（一年内）"] == ""
    assert row_000001["持续递减（一年内）"] == ""


@pytest.mark.asyncio
async def test_stats_include_by_source_and_by_result(tmpbase):
    """stats 字段含 by_source + by_result 分布。"""
    rec = [{"公告日期": "2026-04-14", "累计质押比例": 10.0, "前次累计质押比例": 10.3}]
    mapping = {
        "002768": (rec, "eastmoney"),
        "000001": ([], "empty"),
    }
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    with patch("services.pledge_data_source.PledgeDataSource", _mock_ds_factory(mapping)), \
         patch("core.redis_client.get_redis", return_value=None):
        result = await ex._pledge_trend_analysis({}, _input_df(), date_str="2026-04-20")
    stats = result["stats"]
    assert stats["total"] == 2
    assert stats["by_source"]["eastmoney"] == 1
    assert stats["by_source"]["empty"] == 1
    assert stats["ok"] == 1
    assert stats["empty"] == 1


@pytest.mark.asyncio
async def test_output_file_is_final_template(tmpbase):
    """输出文件名应为 5质押{date}.xlsx（默认，不指定 output_filename）。"""
    mapping = {"002768": ([], "empty"), "000001": ([], "empty")}
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    with patch("services.pledge_data_source.PledgeDataSource", _mock_ds_factory(mapping)), \
         patch("core.redis_client.get_redis", return_value=None):
        result = await ex._pledge_trend_analysis({}, _input_df(), date_str="2026-04-20")
    assert result["file_path"].endswith("5质押20260420.xlsx")
    assert os.path.exists(result["file_path"])


@pytest.mark.asyncio
async def test_output_file_respects_user_specified(tmpbase):
    """output_filename 配置生效。"""
    mapping = {"002768": ([], "empty"), "000001": ([], "empty")}
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    with patch("services.pledge_data_source.PledgeDataSource", _mock_ds_factory(mapping)), \
         patch("core.redis_client.get_redis", return_value=None):
        result = await ex._pledge_trend_analysis(
            {"output_filename": "my_custom.xlsx"}, _input_df(), date_str="2026-04-20"
        )
    assert result["file_path"].endswith("my_custom.xlsx")


@pytest.mark.asyncio
async def test_skip_preset_row_not_queried(tmpbase):
    """原表 3 列任一非空 → skip，不调用数据源，保持原值。"""
    df = pd.DataFrame([
        {"证券代码": "002768", "证券简称": "国恩",
         "最新公告日": "2026-04-14", "来源": "小盘",
         "持续递增（一年内）": "", "持续递减（一年内）": "Y", "质押异动": ""},
        {"证券代码": "000001", "证券简称": "平安",
         "最新公告日": "2026-04-14", "来源": "中大盘",
         "持续递增（一年内）": "", "持续递减（一年内）": "", "质押异动": ""},
    ])

    class Spy:
        def __init__(self, *a, **kw):
            self.calls = []
        def get_history(self, symbol, anchor, window_days=365):
            self.calls.append(symbol)
            return [], "empty"

    spy_inst = {"val": None}
    def factory(*a, **kw):
        spy_inst["val"] = Spy()
        return spy_inst["val"]

    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    with patch("services.pledge_data_source.PledgeDataSource", factory), \
         patch("core.redis_client.get_redis", return_value=None):
        result = await ex._pledge_trend_analysis({}, df, date_str="2026-04-20")

    assert result["success"]
    df_out = result["_df"]
    # 第 1 行保留原值（已有递减=Y）
    assert df_out.iloc[0]["持续递减（一年内）"] == "Y"
    # 第 2 行被正常查询（空值）
    assert result["stats"]["skipped_preset"] == 1
    # 数据源仅被调用 1 次（只查第 2 行）
    assert spy_inst["val"].calls == ["000001"]


@pytest.mark.asyncio
async def test_skip_old_row_beyond_recency_window(tmpbase):
    """锚点早于 row_recency_days 前 → skip。"""
    from datetime import datetime as _dt, timedelta as _td
    old_date = (_dt.now() - _td(days=60)).date().isoformat()
    recent_date = (_dt.now() - _td(days=5)).date().isoformat()
    df = pd.DataFrame([
        {"证券代码": "002768", "证券简称": "国恩",
         "最新公告日": old_date, "来源": "小盘"},
        {"证券代码": "000001", "证券简称": "平安",
         "最新公告日": recent_date, "来源": "中大盘"},
    ])

    class Spy:
        def __init__(self, *a, **kw):
            self.calls = []
        def get_history(self, symbol, anchor, window_days=365):
            self.calls.append(symbol)
            return [], "empty"

    spy_inst = {"val": None}
    def factory(*a, **kw):
        spy_inst["val"] = Spy()
        return spy_inst["val"]

    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    with patch("services.pledge_data_source.PledgeDataSource", factory), \
         patch("core.redis_client.get_redis", return_value=None):
        result = await ex._pledge_trend_analysis(
            {"row_recency_days": 30}, df, date_str="2026-04-20"
        )

    assert result["success"]
    assert result["stats"]["skipped_old"] == 1
    # 数据源只被调用 1 次（只查最近行）
    assert spy_inst["val"].calls == ["000001"]


@pytest.mark.asyncio
async def test_fail_samples_limited_to_10(tmpbase):
    """单股异常 → 进入 fail_samples，最多 10 条。"""
    class BombDS:
        def __init__(self, *a, **kw): pass
        def get_history(self, symbol, anchor, window_days=365):
            raise RuntimeError(f"boom-{symbol}")
    df = pd.DataFrame([
        {"证券代码": f"00000{i}", "证券简称": f"T{i}",
         "最新公告日": "2026-04-14", "来源": "小盘"}
        for i in range(15)
    ])
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    with patch("services.pledge_data_source.PledgeDataSource", BombDS), \
         patch("core.redis_client.get_redis", return_value=None):
        result = await ex._pledge_trend_analysis({}, df, date_str="2026-04-20")
    assert result["success"] is True
    assert result["stats"]["fail"] == 15
    assert len(result["fail_samples"]) == 10
