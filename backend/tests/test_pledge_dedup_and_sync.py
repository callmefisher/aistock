"""验证：质押智能去重的优先级 + 最终输出同步 public。"""
import os
import tempfile
import pandas as pd
import pytest
from services.workflow_executor import WorkflowExecutor


@pytest.fixture
def tmpbase():
    with tempfile.TemporaryDirectory() as base:
        upload_dir = os.path.join(base, "质押", "2026-04-20")
        public_dir = os.path.join(base, "质押", "public")
        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(public_dir, exist_ok=True)
        yield base


@pytest.mark.asyncio
async def test_smart_dedup_prefers_row_with_preset(tmpbase):
    """4 行重复：其中 1 行 3 列任一非空 → 保留该行。"""
    df = pd.DataFrame([
        {"证券代码": "002768", "证券简称": "国恩", "最新公告日": "2026-04-10",
         "持续递增（一年内）": "", "持续递减（一年内）": "", "质押异动": ""},
        {"证券代码": "002768", "证券简称": "国恩", "最新公告日": "2026-04-12",
         "持续递增（一年内）": "", "持续递减（一年内）": "Y", "质押异动": ""},  # 有预判
        {"证券代码": "002768", "证券简称": "国恩", "最新公告日": "2026-04-14",
         "持续递增（一年内）": "", "持续递减（一年内）": "", "质押异动": ""},
        {"证券代码": "002768", "证券简称": "国恩", "最新公告日": "2026-04-13",
         "持续递增（一年内）": "", "持续递减（一年内）": "", "质押异动": ""},
    ])
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    result = await ex._smart_dedup({}, df, date_str="2026-04-20")
    assert result["success"]
    rows = result["_df"].to_dict("records")
    assert len(rows) == 1
    kept = rows[0]
    # 保留的应是"有预判的那一行"
    assert str(kept["持续递减（一年内）"]) == "Y"
    assert str(kept["最新公告日"]) == "2026-04-12"


@pytest.mark.asyncio
async def test_smart_dedup_multiple_preset_keep_latest_date(tmpbase):
    """多行都有预判 → 保留最新公告日的。"""
    df = pd.DataFrame([
        {"证券代码": "002768", "证券简称": "国恩", "最新公告日": "2026-04-10",
         "持续递增（一年内）": "", "持续递减（一年内）": "Y", "质押异动": ""},
        {"证券代码": "002768", "证券简称": "国恩", "最新公告日": "2026-04-14",
         "持续递增（一年内）": "Y", "持续递减（一年内）": "", "质押异动": ""},  # 最新
        {"证券代码": "002768", "证券简称": "国恩", "最新公告日": "2026-04-12",
         "持续递增（一年内）": "", "持续递减（一年内）": "", "质押异动": "小幅转减"},
    ])
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    result = await ex._smart_dedup({}, df, date_str="2026-04-20")
    assert result["success"]
    kept = result["_df"].iloc[0]
    assert str(kept["最新公告日"]) == "2026-04-14"
    assert str(kept["持续递增（一年内）"]) == "Y"


@pytest.mark.asyncio
async def test_smart_dedup_all_empty_preset_falls_back(tmpbase):
    """3 列全部为空 → fallback 现有规则（按日期降序 + keep=first）。"""
    df = pd.DataFrame([
        {"证券代码": "002768", "证券简称": "国恩", "最新公告日": "2026-04-10",
         "持续递增（一年内）": "", "持续递减（一年内）": "", "质押异动": ""},
        {"证券代码": "002768", "证券简称": "国恩", "最新公告日": "2026-04-14",
         "持续递增（一年内）": "", "持续递减（一年内）": "", "质押异动": ""},
        {"证券代码": "002768", "证券简称": "国恩", "最新公告日": "2026-04-12",
         "持续递增（一年内）": "", "持续递减（一年内）": "", "质押异动": ""},
    ])
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    result = await ex._smart_dedup({}, df, date_str="2026-04-20")
    assert result["success"]
    kept = result["_df"].iloc[0]
    assert str(kept["最新公告日"]) == "2026-04-14"


def test_sync_final_to_public_copies_and_cleans(tmpbase):
    """最终输出同步到 public：复制成功后删除 public 中的其他文件。"""
    public_dir = os.path.join(tmpbase, "质押", "public")
    # public 里有 2 个旧文件（要被清理）
    old1 = os.path.join(public_dir, "old1.xlsx")
    old2 = os.path.join(public_dir, "old2.xlsx")
    pd.DataFrame([{"a": 1}]).to_excel(old1, index=False)
    pd.DataFrame([{"b": 2}]).to_excel(old2, index=False)
    # 最终输出文件
    upload_dir = os.path.join(tmpbase, "质押", "2026-04-20")
    final_path = os.path.join(upload_dir, "5质押20260420.xlsx")
    pd.DataFrame([{"证券代码": "002768.SZ"}]).to_excel(final_path, index=False)

    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    ok = ex._sync_pledge_final_to_public(final_path, date_str="2026-04-20")
    assert ok

    # 同步后 public 只有 1 个文件：新复制的 5质押20260420.xlsx
    files = sorted(os.listdir(public_dir))
    assert files == ["5质押20260420.xlsx"]
    # 内容与源一致
    import pandas as _pd
    synced = _pd.read_excel(os.path.join(public_dir, "5质押20260420.xlsx"))
    assert "002768.SZ" in str(synced.iloc[0]["证券代码"])


def test_sync_skip_when_not_pledge_type(tmpbase):
    """非质押类型调用 _sync_pledge_final_to_public → 返回 False，不执行任何 IO。"""
    public_dir = os.path.join(tmpbase, "质押", "public")
    old = os.path.join(public_dir, "old.xlsx")
    pd.DataFrame([{"a": 1}]).to_excel(old, index=False)
    upload_dir = os.path.join(tmpbase, "质押", "2026-04-20")
    final_path = os.path.join(upload_dir, "1并购重组20260420.xlsx")
    pd.DataFrame([{"c": 3}]).to_excel(final_path, index=False)

    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="并购重组")
    ok = ex._sync_pledge_final_to_public(final_path, date_str="2026-04-20")
    assert ok is False
    # old.xlsx 依然存在（非质押类型不应清理）
    assert os.path.exists(old)


def test_sync_missing_source_returns_false(tmpbase):
    """源文件不存在 → 静默返回 False。"""
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    ok = ex._sync_pledge_final_to_public("/nonexistent/path.xlsx", date_str="2026-04-20")
    assert ok is False
