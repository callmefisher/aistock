import os
import tempfile
import pandas as pd
import pytest
from openpyxl import load_workbook
from services.workflow_executor import WorkflowExecutor


@pytest.fixture
def executor():
    with tempfile.TemporaryDirectory() as base:
        ex = WorkflowExecutor(base_dir=base, workflow_type="质押")
        yield ex


class TestFinalizeLayout:
    def test_column_order_with_all_prefix_cols(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "证券简称": ["平安银行"],
            "最新公告日": ["2026-04-20"],
            "百日新高": ["是"],
            "站上20日线": ["是"],
            "国央企": ["是"],
            "所属板块": ["金融"],
            "来源": ["中大盘"],
            "质押比例-20260118": [0.10],
            "质押比例-20260304": [0.12],
            "额外列": ["foo"],
        })
        output_path = tmp_path / "5质押20260420.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        assert wb.sheetnames == ["中大盘20260420", "小盘20260420"]
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        assert header[0] == "序号"
        assert header[1:8] == ["证券代码", "证券简称", "最新公告日", "百日新高", "站上20日线", "国央企", "所属板块"]
        assert "来源" not in header
        assert "额外列" in header
        assert "质押比例-20260118" in header

    def test_split_by_source(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ", "000002.SZ"],
            "证券简称": ["平安银行", "万科A"],
            "最新公告日": ["2026-04-20", "2026-04-20"],
            "来源": ["中大盘", "小盘"],
        })
        output_path = tmp_path / "5质押20260420.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        big = wb["中大盘20260420"]
        small = wb["小盘20260420"]
        assert big.max_row == 2
        assert big.cell(2, 2).value == "000001.SZ"
        assert small.max_row == 2
        assert small.cell(2, 2).value == "000002.SZ"

    def test_empty_source_keeps_header_only(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "证券简称": ["平安银行"],
            "最新公告日": ["2026-04-20"],
            "来源": ["中大盘"],
        })
        output_path = tmp_path / "5质押20260420.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        small = wb["小盘20260420"]
        assert small.max_row == 1

    def test_missing_prefix_cols_filled_empty(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "证券简称": ["平安银行"],
            "最新公告日": ["2026-04-20"],
            "来源": ["中大盘"],
        })
        output_path = tmp_path / "5质押20260420.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        assert "百日新高" in header
        assert "站上20日线" in header
        assert "国央企" in header
        assert "所属板块" in header

    def test_drops_original_xuhao(self, executor, tmp_path):
        df = pd.DataFrame({
            "序号": [99],
            "证券代码": ["000001.SZ"],
            "证券简称": ["平安银行"],
            "最新公告日": ["2026-04-20"],
            "来源": ["中大盘"],
        })
        output_path = tmp_path / "5质押20260420.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        assert ws.cell(2, 1).value == 1  # 新序号 1 起

    def test_non_default_index_no_source(self, executor, tmp_path):
        """df 有非默认索引 + 无来源列：不应 crash。"""
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "证券简称": ["A"],
            "最新公告日": ["2026-04-20"],
        }, index=[99])
        output_path = tmp_path / "out.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        # 无来源 → 全部归小盘
        small = wb["小盘20260420"]
        assert small.max_row == 2
        assert small.cell(2, 2).value == "000001.SZ"

    def test_duplicate_column_names(self, executor, tmp_path):
        """df 含重复列名：不应 crash，重复列自动追加 _N 后缀。"""
        # 构造一个带重复列名的 DataFrame
        df = pd.DataFrame([["000001.SZ", "A", "2026-04-20", "中大盘", "x", "y"]])
        df.columns = ["证券代码", "证券简称", "最新公告日", "来源", "重复列", "重复列"]
        output_path = tmp_path / "out.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        # 两个"重复列"都保留（一个原名一个带后缀）
        assert header.count("重复列") == 1
        assert "重复列_1" in header


RED_COLOR = "FFC00000"
GREEN_COLOR = "FFC6EFCE"


def _get_fill(ws, row, col):
    c = ws.cell(row, col)
    if c.fill and c.fill.start_color:
        return (c.fill.start_color.rgb or "").upper()
    return ""


class TestPledgeRatioColoring:
    def test_ratio_increase_red(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"], "证券简称": ["A"],
            "最新公告日": ["2026-04-20"], "来源": ["中大盘"],
            "质押比例-20260118": [0.10],
            "质押比例-20260304": [0.15],
        })
        output_path = tmp_path / "out.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        col_right = header.index("质押比例-20260304") + 1
        assert RED_COLOR in _get_fill(ws, 2, col_right)

    def test_ratio_decrease_green(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"], "证券简称": ["A"],
            "最新公告日": ["2026-04-20"], "来源": ["中大盘"],
            "质押比例-20260118": [0.15],
            "质押比例-20260304": [0.10],
        })
        output_path = tmp_path / "out.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        col_right = header.index("质押比例-20260304") + 1
        assert GREEN_COLOR in _get_fill(ws, 2, col_right)

    def test_ratio_equal_no_color(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"], "证券简称": ["A"],
            "最新公告日": ["2026-04-20"], "来源": ["中大盘"],
            "质押比例-20260118": [0.10],
            "质押比例-20260304": [0.10],
        })
        output_path = tmp_path / "out.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        col_right = header.index("质押比例-20260304") + 1
        fill = _get_fill(ws, 2, col_right)
        assert RED_COLOR not in fill and GREEN_COLOR not in fill

    def test_ratio_either_empty_skipped(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ", "000002.SZ"],
            "证券简称": ["A", "B"],
            "最新公告日": ["2026-04-20", "2026-04-20"],
            "来源": ["中大盘", "中大盘"],
            "质押比例-20260118": [None, 0.10],
            "质押比例-20260304": [0.15, None],
        })
        output_path = tmp_path / "out.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        col_right = header.index("质押比例-20260304") + 1
        for row in (2, 3):
            fill = _get_fill(ws, row, col_right)
            assert RED_COLOR not in fill and GREEN_COLOR not in fill

    def test_ratio_leftmost_never_colored(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"], "证券简称": ["A"],
            "最新公告日": ["2026-04-20"], "来源": ["中大盘"],
            "质押比例-20260118": [0.10],
            "质押比例-20260304": [0.15],
        })
        output_path = tmp_path / "out.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        col_left = header.index("质押比例-20260118") + 1
        fill = _get_fill(ws, 2, col_left)
        assert RED_COLOR not in fill and GREEN_COLOR not in fill

    def test_ratio_with_percent_string(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"], "证券简称": ["A"],
            "最新公告日": ["2026-04-20"], "来源": ["中大盘"],
            "质押比例-20260118": ["10.0%"],
            "质押比例-20260304": ["15.0%"],
        })
        output_path = tmp_path / "out.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        col_right = header.index("质押比例-20260304") + 1
        assert RED_COLOR in _get_fill(ws, 2, col_right)
