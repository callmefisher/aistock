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

    def test_drops_source_info_cols_exact(self, executor, tmp_path):
        """源表带 4 类信息列（精确名）：不复制到剩余列，前 7 列由 match 值或空填充。"""
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "证券简称": ["A"],
            "最新公告日": ["2026-04-20"],
            "来源": ["中大盘"],
            # 源表已带 4 类信息列（可能是用户历史数据残留）
            "百日新高": ["源表值-不该保留"],
            "站上20日线": ["源表值-不该保留"],
            "国央企": ["源表值-不该保留"],
            "所属板块": ["源表值-不该保留"],
            "质押比例-20260420": [0.10],
        })
        output_path = tmp_path / "out.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        # 前 7 列仍在（固定），但对应单元格值应为空（源表值被丢弃，match 未跑）
        for col_name in ("百日新高", "站上20日线", "国央企", "所属板块"):
            idx = header.index(col_name) + 1
            val = ws.cell(2, idx).value
            assert val in (None, "", 0), f"{col_name} 应空，实际={val!r}"
        # 剩余列中不应再出现这 4 列（及其 _N 副本）
        rest_cols = header[8:]  # 序号 + 7 固定 = 前 8 项
        for forbidden in ("百日新高", "站上20日线", "国央企", "所属板块"):
            assert forbidden not in rest_cols
        # 质押比例列应保留
        assert "质押比例-20260420" in header

    def test_drops_source_info_cols_synonyms(self, executor, tmp_path):
        """源表带 4 类信息列的同义词变体：也应被丢弃，不出现在剩余列里。"""
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "证券简称": ["A"],
            "最新公告日": ["2026-04-20"],
            "来源": ["中大盘"],
            # 同义词变体
            "百日最高价": ["源值"],       # → 百日新高
            "20日均线": ["源值"],         # → 站上20日线
            "20日线": ["源值2"],          # → 站上20日线（另一个变体）
            "国企": ["源值"],             # → 国央企
            "一级板块": ["源值"],         # → 所属板块
            "板块": ["源值2"],            # → 所属板块（另一个变体）
            # 非 4 类信息列：应保留
            "质押比例-20260420": [0.10],
            "额外业务列": ["保留"],
        })
        output_path = tmp_path / "out.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        for forbidden in ("百日最高价", "20日均线", "20日线", "国企", "一级板块", "板块"):
            assert forbidden not in header, f"{forbidden} 应被丢弃"
        # 质押比例和额外业务列应保留
        assert "质押比例-20260420" in header
        assert "额外业务列" in header

    def test_keeps_non_info_columns_intact(self, executor, tmp_path):
        """源表大量业务列（非 4 类信息）：应全部保留在剩余列区域，按源序。"""
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "证券简称": ["A"],
            "最新公告日": ["2026-04-20"],
            "来源": ["中大盘"],
            "股权质押公告日期-20260420": ["2026-04-20"],
            "质押比例-20260118": [0.08],
            "质押比例-20260304": [0.10],
            "质押比例-20260420": [0.12],
            "大股东名称": ["张三"],
            "质押方": ["某证券"],
            "备注": ["..."],
        })
        output_path = tmp_path / "out.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        for c in ("股权质押公告日期-20260420", "质押比例-20260118", "质押比例-20260304",
                  "质押比例-20260420", "大股东名称", "质押方", "备注"):
            assert c in header, f"{c} 应保留"


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


class TestPledgeFirstAppearance:
    def _write_public_baseline(self, public_dir, code, date_val, date_str):
        """写一份历史 public 文件，含某代码的某公告日。"""
        from openpyxl import Workbook
        wb = Workbook()
        wb.remove(wb.active)
        ws = wb.create_sheet(f"中大盘{date_str}")
        ws.append(["序号", "证券代码", "证券简称", "最新公告日"])
        ws.append([1, code, "A", date_val])
        ws2 = wb.create_sheet(f"小盘{date_str}")
        ws2.append(["序号", "证券代码", "证券简称", "最新公告日"])
        wb.save(str(public_dir / f"5质押{date_str}.xlsx"))

    def test_new_code_green(self, executor, tmp_path):
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"], "证券简称": ["A"],
            "最新公告日": ["2026-04-20"], "来源": ["中大盘"],
        })
        output_path = tmp_path / "out.xlsx"
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        col_date = header.index("最新公告日") + 1
        assert GREEN_COLOR in _get_fill(ws, 2, col_date)

    def test_existing_code_newer_date_green(self, executor, tmp_path):
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        self._write_public_baseline(public_dir, "000001.SZ", "2026-03-01", "20260301")
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"], "证券简称": ["A"],
            "最新公告日": ["2026-04-20"], "来源": ["中大盘"],
        })
        output_path = tmp_path / "out.xlsx"
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        col_date = header.index("最新公告日") + 1
        assert GREEN_COLOR in _get_fill(ws, 2, col_date)

    def test_existing_code_same_or_older_not_green(self, executor, tmp_path):
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        self._write_public_baseline(public_dir, "000001.SZ", "2026-04-20", "20260420")
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"], "证券简称": ["A"],
            "最新公告日": ["2026-04-20"], "来源": ["中大盘"],
        })
        output_path = tmp_path / "out.xlsx"
        executor._finalize_pledge_output(df, "20260421", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260421"]
        header = [c.value for c in ws[1]]
        col_date = header.index("最新公告日") + 1
        fill = _get_fill(ws, 2, col_date)
        assert GREEN_COLOR not in fill

    def test_baseline_merges_both_sheets(self, executor, tmp_path):
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        from openpyxl import Workbook
        wb_pub = Workbook()
        wb_pub.remove(wb_pub.active)
        ws_big = wb_pub.create_sheet("中大盘20260301")
        ws_big.append(["序号", "证券代码", "证券简称", "最新公告日"])
        ws_big.append([1, "000002.SZ", "B", "2026-04-20"])
        ws_small = wb_pub.create_sheet("小盘20260301")
        ws_small.append(["序号", "证券代码", "证券简称", "最新公告日"])
        wb_pub.save(str(public_dir / "5质押20260301.xlsx"))
        # 新文件：小盘 sheet 里有 000002.SZ @ 2026-04-20（同日期，不该绿）
        df = pd.DataFrame({
            "证券代码": ["000002.SZ"], "证券简称": ["B"],
            "最新公告日": ["2026-04-20"], "来源": ["小盘"],
        })
        output_path = tmp_path / "out.xlsx"
        executor._finalize_pledge_output(df, "20260421", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["小盘20260421"]
        header = [c.value for c in ws[1]]
        col_date = header.index("最新公告日") + 1
        fill = _get_fill(ws, 2, col_date)
        assert GREEN_COLOR not in fill


class TestFinalizePledgeIfNeeded:
    def test_non_pledge_noop(self, tmp_path):
        ex = WorkflowExecutor(base_dir=str(tmp_path), workflow_type="并购重组")
        result = ex.finalize_pledge_if_needed(
            last_output_path=str(tmp_path / "nonexistent.xlsx"),
            date_str="20260420",
        )
        assert result is False

    def test_pledge_runs_finalize_and_syncs(self, tmp_path, monkeypatch):
        ex = WorkflowExecutor(base_dir=str(tmp_path), workflow_type="质押")
        daily_dir = tmp_path / "data" / "excel" / "质押" / "20260420"
        daily_dir.mkdir(parents=True)
        public_dir = tmp_path / "data" / "excel" / "质押" / "public"
        public_dir.mkdir(parents=True)
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"], "证券简称": ["A"],
            "最新公告日": ["2026-04-20"], "来源": ["中大盘"],
        })
        last_output = daily_dir / "output_5.xlsx"
        df.to_excel(str(last_output), index=False)

        # monkeypatch resolver 以返回可控路径
        monkeypatch.setattr(ex.resolver, "get_daily_dir", lambda d=None: str(daily_dir))
        monkeypatch.setattr(ex.resolver, "get_public_directory", lambda d=None: str(public_dir))

        result = ex.finalize_pledge_if_needed(
            last_output_path=str(last_output),
            date_str="20260420",
        )
        assert result is True
        final = daily_dir / "5质押20260420.xlsx"
        assert final.exists()
        assert (public_dir / "5质押20260420.xlsx").exists()
