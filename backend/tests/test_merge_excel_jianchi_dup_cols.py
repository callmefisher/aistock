"""回归：合并步骤重复列名防护（通用逻辑）。

bug 背景（2026-10-26 线上批量执行失败）：Wind 导出同一列出现两次，
pandas 读取时第二列被 mangle 成 ".1" 后缀。减持类型剥离 \\n 后缀后两列同名，
merged_df[col] 返回 DataFrame 而非 Series，访问 .dtype 抛出
'DataFrame' object has no attribute 'dtype'，merge_excel 整步失败，
后续步骤因输入为空全部连锁失败。

同类潜在路径：质押的 _maybe_flatten_pledge_multiheader 会把
"质押比例\\n[截止日期]最新" 和 ".1" 变体都改名为 "质押比例最新" → 同名重复列。

修复：合并读取每个文件后通用列名去重（保留首个），
覆盖所有工作流类型（减持/质押/招投标/股权转让等）。
"""
import os
import tempfile
import pandas as pd
import pytest
from services.workflow_executor import WorkflowExecutor

DATE = "2026-10-26"
WTYPE_JIANCHI = "减持叠加质押和大宗交易"
WTYPE_PLEDGE = "质押"


@pytest.fixture
def tmpbase():
    with tempfile.TemporaryDirectory() as base:
        yield base


# ---------- 减持叠加质押和大宗交易 ----------

def _make_wind_excel(filepath: str):
    """模拟 Wind 导出：'最新大股东减持公告日期' 列重复出现两次。

    pandas read_excel 会把第二次出现的同名表头 mangle 成 '.1' 后缀，
    剥离 \\n 后两列同名 → 触发旧 bug。
    """
    df = pd.DataFrame({
        "证券代码": ["000001.SZ", "300001.SZ"],
        "证券名称": ["平安银行", "特锐德"],
        "最新大股东减持公告日期\n[截止日期]最新": ["2026-10-20", "2026-10-21"],
        "最新大股东减持公告日期\n[截止日期]最新.1": ["2026-10-20", "2026-10-21"],
        "所属申万行业指数名称(可查历史)\n[截止日期]最新\n[行业类别3]1级": ["银行", "电源设备"],
    })
    df.to_excel(filepath, index=False)


@pytest.mark.asyncio
async def test_merge_with_duplicate_wind_columns(tmpbase):
    """减持：重复列剥离 \\n 后同名，应去重保留首个，合并成功而非崩溃。"""
    upload_dir = os.path.join(tmpbase, WTYPE_JIANCHI, DATE)
    os.makedirs(upload_dir, exist_ok=True)
    _make_wind_excel(os.path.join(upload_dir, "6、全部A股减持中叠加质押和大宗交易1026.xlsx"))

    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type=WTYPE_JIANCHI)
    result = await ex._merge_excel({}, date_str=DATE)
    assert result["success"], result["message"]

    df = result["_df"]
    # 剥离 \n 后重复列已去重，无同名列
    assert not df.columns.duplicated().any()
    # 列名映射生效：证券名称→证券简称，最新大股东减持公告日期→最新公告日
    assert "证券简称" in df.columns
    assert "最新公告日" in df.columns
    assert len(df) == 2


# ---------- 质押 ----------

def _make_pledge_excel_with_dup_ratio(filepath: str):
    """模拟质押源文件：两个'质押比例...最新'列（Wind 导出重复）。

    read_excel 后第二列被 mangle 为 '.1'；列名规整（情况A）会把两列
    都改名为 '质押比例最新' → 重复列 → 旧代码在 merged_df[col].dtype 崩溃。
    """
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "证券简称": ["平安银行"],
            "质押比例\n[截止日期]最新": [30.5],
            "质押比例\n[截止日期]最新.1": [31.2],
            "最新公告日": ["2026-10-20"],
        }).to_excel(writer, sheet_name="中大盘A", index=False)


@pytest.mark.asyncio
async def test_pledge_merge_with_duplicate_ratio_columns(tmpbase):
    """质押：质押比例规整产生同名重复列，应去重保留首个，合并成功而非崩溃。"""
    upload_dir = os.path.join(tmpbase, WTYPE_PLEDGE, DATE)
    os.makedirs(upload_dir, exist_ok=True)
    _make_pledge_excel_with_dup_ratio(
        os.path.join(upload_dir, "质押dup.xlsx"))

    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type=WTYPE_PLEDGE)
    result = await ex._merge_excel({}, date_str=DATE)
    assert result["success"], result["message"]

    df = result["_df"]
    assert not df.columns.duplicated().any()
    assert "质押比例最新" in df.columns
    # 保留首个重复列的值（30.5，非 31.2）
    assert df["质押比例最新"].iloc[0] == 30.5
    assert "来源" in df.columns
    assert len(df) == 1


# ---------- 通用性：其他类型不受影响 ----------

@pytest.mark.asyncio
async def test_other_type_no_dup_noop(tmpbase):
    """招投标（走通用路径、无列名改写）：无重复列时去重为 no-op，输出不受影响。"""
    upload_dir = os.path.join(tmpbase, "招投标", DATE)
    os.makedirs(upload_dir, exist_ok=True)
    pd.DataFrame({
        "证券代码": ["000001.SZ", "300001.SZ"],
        "证券名称": ["平安银行", "特锐德"],
        "发生日期": ["2026-10-20", "2026-10-21"],
    }).to_excel(os.path.join(upload_dir, "行动事件库.xlsx"), index=False)

    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="招投标")
    result = await ex._merge_excel({}, date_str=DATE)
    assert result["success"], result["message"]

    df = result["_df"]
    # 招投标列名映射：证券名称→证券简称，发生日期→最新公告日（序号为合并步骤自动生成）
    assert list(df.columns) == ["序号", "证券代码", "证券简称", "最新公告日"]
    assert len(df) == 2
