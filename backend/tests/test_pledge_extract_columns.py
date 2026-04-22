import os
import tempfile
import pandas as pd
import pytest
from services.workflow_executor import WorkflowExecutor


@pytest.fixture
def executor():
    with tempfile.TemporaryDirectory() as base:
        ex = WorkflowExecutor(base_dir=base, workflow_type="质押")
        yield ex


class TestExtractColumnsPledge:
    @pytest.mark.asyncio
    async def test_keeps_all_original_columns(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "证券简称": ["平安银行"],
            "最新公告日": ["2026-04-20"],
            "来源": ["中大盘"],
            "质押比例-20260118": [0.10],
            "质押比例-20260304": [0.12],
            "额外列A": ["foo"],
        })
        await executor._extract_columns_pledge(df.copy(), str(tmp_path / "out.xlsx"))
        out_df = pd.read_excel(str(tmp_path / "out.xlsx"))
        assert set(df.columns) <= set(out_df.columns)
        assert "额外列A" in out_df.columns
        assert "质押比例-20260118" in out_df.columns

    @pytest.mark.asyncio
    async def test_maps_pledge_date_to_latest_announce(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "证券简称": ["平安银行"],
            "来源": ["中大盘"],
            "股权质押公告日期-20260420": ["2026-04-20"],
        })
        await executor._extract_columns_pledge(df.copy(), str(tmp_path / "out.xlsx"))
        out_df = pd.read_excel(str(tmp_path / "out.xlsx"))
        assert "最新公告日" in out_df.columns
        assert str(out_df.iloc[0]["最新公告日"]).startswith("2026-04-20")
        # 原列仍保留
        assert "股权质押公告日期-20260420" in out_df.columns

    @pytest.mark.asyncio
    async def test_maps_name_to_abbreviation(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "名称": ["平安银行"],
            "最新公告日": ["2026-04-20"],
            "来源": ["小盘"],
        })
        await executor._extract_columns_pledge(df.copy(), str(tmp_path / "out.xlsx"))
        out_df = pd.read_excel(str(tmp_path / "out.xlsx"))
        assert "证券简称" in out_df.columns
        assert out_df.iloc[0]["证券简称"] == "平安银行"

    @pytest.mark.asyncio
    async def test_fills_missing_required_cols_with_empty(self, executor, tmp_path):
        df = pd.DataFrame({"证券代码": ["000001.SZ"]})
        await executor._extract_columns_pledge(df.copy(), str(tmp_path / "out.xlsx"))
        out_df = pd.read_excel(str(tmp_path / "out.xlsx"))
        for col in ("证券代码", "证券简称", "最新公告日", "来源"):
            assert col in out_df.columns

    @pytest.mark.asyncio
    async def test_latest_announce_wins_over_pledge_date(self, executor, tmp_path):
        """当最新公告日和股权质押公告日期-* 同时存在，最新公告日原值不被覆盖。"""
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "证券简称": ["平安银行"],
            "最新公告日": ["2026-05-01"],           # 已有值
            "股权质押公告日期-20260420": ["2026-04-20"],  # 另一个来源
            "来源": ["中大盘"],
        })
        await executor._extract_columns_pledge(df.copy(), str(tmp_path / "out.xlsx"))
        out_df = pd.read_excel(str(tmp_path / "out.xlsx"))
        # 最新公告日 应保留原值，不被 股权质押公告日期-* 覆盖
        assert str(out_df.iloc[0]["最新公告日"]).startswith("2026-05-01")
        # 源列也保留
        assert "股权质押公告日期-20260420" in out_df.columns
