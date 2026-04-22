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
    """中大盘开头的 sheet 名 → 来源=中大盘（文件名不含关键字时回退到 sheet 名）。"""
    ex = WorkflowExecutor(base_dir="/tmp", workflow_type="质押")
    assert ex._derive_pledge_source("", "中大盘Sheet1") == "中大盘"
    assert ex._derive_pledge_source("", "中大盘") == "中大盘"


def test_source_derive_xiaopan():
    """非中大盘开头 → 来源=小盘（文件名不含关键字时回退到 sheet 名）。"""
    ex = WorkflowExecutor(base_dir="/tmp", workflow_type="质押")
    assert ex._derive_pledge_source("", "小盘A") == "小盘"
    assert ex._derive_pledge_source("", "Sheet1") == "小盘"
    assert ex._derive_pledge_source("", "其他") == "小盘"


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
async def test_merge_preserves_preset_columns_and_renames_to_standard(tmpbase):
    """原表含"持续递增xxx"/"持续递减xxx"/"质押异动"前缀列 → 合并后 rename 到标准名并保留。"""
    upload_dir = os.path.join(tmpbase, "质押", "2026-04-20")
    _make_pledge_excel(os.path.join(upload_dir, "f.xlsx"), {
        "小盘": [{
            "证券代码": "002768.SZ", "证券简称": "国恩",
            "最新公告日": "2026-04-14",
            "持续递增最近一年": "",
            "持续递减一年内": "Y",
            "质押异动备注": "小幅转减",
        }],
    })
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    result = await ex._merge_excel({}, date_str="2026-04-20")
    assert result["success"]
    df = result["_df"]
    assert "持续递增（一年内）" in df.columns
    assert "持续递减（一年内）" in df.columns
    assert "质押异动" in df.columns
    row = df.iloc[0]
    assert row["持续递减（一年内）"] == "Y"
    assert row["质押异动"] == "小幅转减"


@pytest.mark.asyncio
async def test_merge_ignores_hidden_sheets(tmpbase):
    """Excel 中 state=hidden / veryHidden 的 sheet 应被完全跳过。"""
    upload_dir = os.path.join(tmpbase, "质押", "2026-04-20")
    filepath = os.path.join(upload_dir, "mixed.xlsx")
    _make_pledge_excel(filepath, {
        "中大盘可见": [{"证券代码": "000001.SZ", "证券简称": "平安", "最新公告日": "2026-04-10"}],
        "中大盘隐藏": [{"证券代码": "999999.SH", "证券简称": "不应出现", "最新公告日": "2026-03-01"}],
        "小盘可见": [{"证券代码": "300001.SZ", "证券简称": "特锐德", "最新公告日": "2026-04-12"}],
    })
    # 把"中大盘隐藏"设为 hidden
    from openpyxl import load_workbook
    wb = load_workbook(filepath)
    wb["中大盘隐藏"].sheet_state = "hidden"
    wb.save(filepath)

    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    result = await ex._merge_excel({}, date_str="2026-04-20")
    assert result["success"], result["message"]
    df = result["_df"]
    codes = set(df["证券代码"])
    assert "999999.SH" not in codes
    assert "000001.SZ" in codes
    assert "300001.SZ" in codes


@pytest.mark.asyncio
async def test_merge_degrades_when_sheet_name_none_raises(tmpbase, monkeypatch):
    """pd.read_excel(sheet_name=None) 抛错时，降级 ExcelFile 逐 sheet 读。"""
    upload_dir = os.path.join(tmpbase, "质押", "2026-04-20")
    filepath = os.path.join(upload_dir, "bad.xlsx")
    _make_pledge_excel(filepath, {
        "中大盘": [{"证券代码": "002768.SZ", "证券简称": "国恩", "最新公告日": "2026-04-14"}],
        "小盘": [{"证券代码": "300001.SZ", "证券简称": "特锐德", "最新公告日": "2026-04-12"}],
    })

    import pandas as _pd
    _orig_read = _pd.read_excel
    calls = {"n": 0}

    def patched_read(path, **kw):
        if kw.get("sheet_name", False) is None:
            calls["n"] += 1
            raise ValueError("Value must be either numerical or a string containing a wildcard")
        return _orig_read(path, **kw)

    monkeypatch.setattr(_pd, "read_excel", patched_read)

    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    result = await ex._merge_excel({}, date_str="2026-04-20")
    assert result["success"], result["message"]
    assert calls["n"] >= 1  # 触发了降级路径
    df = result["_df"]
    # 两个 sheet 都被成功读到
    assert len(df) == 2


@pytest.mark.asyncio
async def test_merge_includes_public_directory_files(tmpbase):
    """质押 public 目录下的文件也会被合并。"""
    upload_dir = os.path.join(tmpbase, "质押", "2026-04-20")
    public_dir = os.path.join(tmpbase, "质押", "public")
    # 日上传目录 1 个文件
    _make_pledge_excel(os.path.join(upload_dir, "daily.xlsx"), {
        "小盘": [{"证券代码": "000001.SZ", "证券简称": "平安", "最新公告日": "2026-04-14"}],
    })
    # public 目录 1 个文件（不是以 5质押 开头）
    _make_pledge_excel(os.path.join(public_dir, "history.xlsx"), {
        "中大盘": [{"证券代码": "600519.SH", "证券简称": "茅台", "最新公告日": "2026-03-10"}],
    })
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    result = await ex._merge_excel({}, date_str="2026-04-20")
    assert result["success"], result["message"]
    df = result["_df"]
    assert len(df) == 2
    assert set(df["证券代码"]) == {"000001.SZ", "600519.SH"}


@pytest.mark.asyncio
async def test_merge_skips_previous_final_output_in_public(tmpbase):
    """public 下若已有"5质押xxx.xlsx"（上次执行的最终输出），本次合并应跳过，避免循环。"""
    upload_dir = os.path.join(tmpbase, "质押", "2026-04-20")
    public_dir = os.path.join(tmpbase, "质押", "public")
    _make_pledge_excel(os.path.join(upload_dir, "daily.xlsx"), {
        "小盘": [{"证券代码": "000001.SZ", "证券简称": "平安", "最新公告日": "2026-04-14"}],
    })
    # public 里模拟一个历史最终输出
    _make_pledge_excel(os.path.join(public_dir, "5质押20260301.xlsx"), {
        "小盘": [{"证券代码": "999999.SH", "证券简称": "历史", "最新公告日": "2026-03-01"}],
    })
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    result = await ex._merge_excel({}, date_str="2026-04-20")
    assert result["success"]
    df = result["_df"]
    assert "999999.SH" not in df["证券代码"].values
    assert "000001.SZ" in df["证券代码"].values


@pytest.mark.asyncio
async def test_extract_columns_keeps_source_for_pledge(tmpbase):
    """质押 extract_columns 保留全列，包括来源列。"""
    upload_dir = os.path.join(tmpbase, "质押", "2026-04-20")
    _make_pledge_excel(os.path.join(upload_dir, "f.xlsx"), {
        "中大盘": [{"证券代码": "000001.SZ", "证券简称": "平安", "最新公告日": "2026-04-10"}],
        "小盘":   [{"证券代码": "300001.SZ", "证券简称": "特锐德", "最新公告日": "2026-04-12"}],
    })
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    merge_result = await ex._merge_excel({}, date_str="2026-04-20")
    extract_result = await ex._extract_columns({}, merge_result["_df"], date_str="2026-04-20")
    assert extract_result["success"], extract_result["message"]
    # 新实现保留全列，通过 _df 检查列名
    out_cols = list(extract_result["_df"].columns)
    assert "来源" in out_cols


@pytest.mark.asyncio
async def test_extract_columns_preserves_preset_even_with_custom_config(tmpbase):
    """质押类型：保留全列，来源和预判列均不丢失（config 中的 columns 字段被忽略）。"""
    import pandas as pd
    df = pd.DataFrame([{
        "序号": 1, "证券代码": "002768.SZ", "证券简称": "国恩",
        "最新公告日": "2026-04-14", "来源": "小盘",
        "持续递增（一年内）": "", "持续递减（一年内）": "Y", "质押异动": "小幅转减",
    }])
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="质押")
    result = await ex._extract_columns(
        {"columns": ["序号", "证券代码", "证券简称", "最新公告日"]},
        df, date_str="2026-04-20"
    )
    assert result["success"]
    out_df = result["_df"]
    out_cols = list(out_df.columns)
    # 质押全列保留：来源 + 预判列均存在
    assert "来源" in out_cols
    assert "持续递减（一年内）" in out_cols
    assert "质押异动" in out_cols
    # 值未丢
    assert out_df.iloc[0]["持续递减（一年内）"] == "Y"
    assert out_df.iloc[0]["质押异动"] == "小幅转减"


@pytest.mark.asyncio
async def test_extract_columns_custom_config_non_pledge_unchanged(tmpbase):
    """非质押类型：自定义 columns 严格按用户输入，不兜底补充。"""
    import pandas as pd
    df = pd.DataFrame([{
        "序号": 1, "证券代码": "600000.SH", "证券简称": "浦发",
        "最新公告日": "2026-04-14", "来源": "somehow",
    }])
    ex = WorkflowExecutor(base_dir=tmpbase, workflow_type="并购重组")
    result = await ex._extract_columns(
        {"columns": ["序号", "证券代码", "证券简称", "最新公告日"]},
        df, date_str="2026-04-20"
    )
    assert result["success"]
    # 并购重组不应自动补入"来源"
    assert "来源" not in result["columns"]
