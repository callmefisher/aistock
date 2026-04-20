"""阶段2 验收：质押工作流合并步骤特化。"""
import os
import tempfile
import pandas as pd
import pytest
from services.workflow_executor import WorkflowExecutor


def _make_pledge_excel(filepath: str, sheets: dict):
    """sheets: {sheet_name: list[dict|list]}  同 DataFrame 行结构。"""
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for name, rows in sheets.items():
            df = pd.DataFrame(rows)
            df.to_excel(writer, sheet_name=name, index=False)


@pytest.fixture
def tmpbase():
    with tempfile.TemporaryDirectory() as base:
        upload_dir = os.path.join(base, "质押", "2026-04-20")
        public_dir = os.path.join(base, "质押", "public")
        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(public_dir, exist_ok=True)
        yield base


def test_source_derive_zhongdapan():
    """中大盘开头的 sheet 名 → 来源=中大盘。"""
    ex = WorkflowExecutor(base_dir="/tmp", workflow_type="质押")
    assert ex._derive_pledge_source("中大盘Sheet1") == "中大盘"
    assert ex._derive_pledge_source("中大盘") == "中大盘"


def test_source_derive_xiaopan():
    """非中大盘开头 → 来源=小盘。"""
    ex = WorkflowExecutor(base_dir="/tmp", workflow_type="质押")
    assert ex._derive_pledge_source("小盘A") == "小盘"
    assert ex._derive_pledge_source("Sheet1") == "小盘"
    assert ex._derive_pledge_source("其他") == "小盘"


@pytest.mark.asyncio
async def test_merge_multi_sheet_single_file(tmpbase):
    """单文件多 Sheet，产出"来源"列；中大盘 sheet 行归中大盘，其他归小盘。"""
    upload_dir = os.path.join(tmpbase, "质押", "2026-04-20")
    filepath = os.path.join(upload_dir, "raw1.xlsx")
    _make_pledge_excel(filepath, {
        "中大盘A": [{"证券代码": "000001.SZ", "证券简称": "平安银行", "最新公告日": "2026-04-10"}],
        "小盘B":   [{"证券代码": "300001.SZ", "证券简称": "特锐德",   "最新公告日": "2026-04-12"}],
    })

    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    result = await ex._merge_excel({}, date_str="2026-04-20")
    assert result["success"], result["message"]

    df = result["_df"]
    assert "来源" in df.columns
    # 至少每个来源各 1 条
    sources = set(df["来源"].tolist())
    assert "中大盘" in sources and "小盘" in sources
    row_zd = df[df["证券代码"] == "000001.SZ"].iloc[0]
    assert row_zd["来源"] == "中大盘"
    row_xp = df[df["证券代码"] == "300001.SZ"].iloc[0]
    assert row_xp["来源"] == "小盘"


@pytest.mark.asyncio
async def test_merge_multi_file_multi_sheet(tmpbase):
    """多文件 × 多 Sheet 合并，行数 = 所有 sheet 总行数。"""
    upload_dir = os.path.join(tmpbase, "质押", "2026-04-20")
    _make_pledge_excel(os.path.join(upload_dir, "f1.xlsx"), {
        "中大盘": [{"证券代码": "000001.SZ", "证券简称": "平安", "最新公告日": "2026-04-10"}],
    })
    _make_pledge_excel(os.path.join(upload_dir, "f2.xlsx"), {
        "小盘1": [{"证券代码": "300001.SZ", "证券简称": "特锐德", "最新公告日": "2026-04-12"}],
        "小盘2": [{"证券代码": "300002.SZ", "证券简称": "神州泰岳", "最新公告日": "2026-04-13"}],
    })

    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    result = await ex._merge_excel({}, date_str="2026-04-20")
    assert result["success"]
    df = result["_df"]
    assert len(df) == 3


@pytest.mark.asyncio
async def test_merge_maps_zheng_quan_ming_cheng_to_jian_cheng(tmpbase):
    """源列"证券名称"应映射为"证券简称"。"""
    upload_dir = os.path.join(tmpbase, "质押", "2026-04-20")
    _make_pledge_excel(os.path.join(upload_dir, "f.xlsx"), {
        "小盘": [{"证券代码": "000001.SZ", "证券名称": "平安银行", "最新公告日": "2026-04-10"}],
    })
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    result = await ex._merge_excel({}, date_str="2026-04-20")
    assert result["success"]
    df = result["_df"]
    assert "证券简称" in df.columns
    assert "证券名称" not in df.columns
    assert (df["证券简称"] == "平安银行").any()


@pytest.mark.asyncio
async def test_merge_maps_pledge_announce_date_to_latest(tmpbase):
    """前缀含"股权质押公告日期"的列映射为"最新公告日"。"""
    upload_dir = os.path.join(tmpbase, "质押", "2026-04-20")
    _make_pledge_excel(os.path.join(upload_dir, "f.xlsx"), {
        "小盘": [{"证券代码": "000001.SZ", "证券简称": "平安", "股权质押公告日期": "2026-04-10"}],
    })
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    result = await ex._merge_excel({}, date_str="2026-04-20")
    assert result["success"]
    df = result["_df"]
    assert "最新公告日" in df.columns
    assert "股权质押公告日期" not in df.columns


@pytest.mark.asyncio
async def test_merge_auto_generate_seq_when_missing(tmpbase):
    """源文件无"序号"列时，合并后自动生成 1..N。"""
    upload_dir = os.path.join(tmpbase, "质押", "2026-04-20")
    _make_pledge_excel(os.path.join(upload_dir, "f.xlsx"), {
        "小盘": [
            {"证券代码": "000001.SZ", "证券简称": "平安", "最新公告日": "2026-04-10"},
            {"证券代码": "000002.SZ", "证券简称": "万科", "最新公告日": "2026-04-11"},
        ],
    })
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    result = await ex._merge_excel({}, date_str="2026-04-20")
    assert result["success"]
    df = result["_df"]
    assert "序号" in df.columns
    assert sorted(df["序号"].tolist()) == [1, 2]


@pytest.mark.asyncio
async def test_extract_columns_keeps_source_for_pledge(tmpbase):
    """extract_columns 默认提取列针对质押类型保留"来源"列。"""
    upload_dir = os.path.join(tmpbase, "质押", "2026-04-20")
    _make_pledge_excel(os.path.join(upload_dir, "f.xlsx"), {
        "中大盘": [{"证券代码": "000001.SZ", "证券简称": "平安", "最新公告日": "2026-04-10"}],
        "小盘":   [{"证券代码": "300001.SZ", "证券简称": "特锐德", "最新公告日": "2026-04-12"}],
    })
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    merge_result = await ex._merge_excel({}, date_str="2026-04-20")
    extract_result = await ex._extract_columns({}, merge_result["_df"], date_str="2026-04-20")
    assert extract_result["success"], extract_result["message"]
    cols = extract_result["columns"]
    assert "来源" in cols
