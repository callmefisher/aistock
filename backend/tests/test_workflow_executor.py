import pytest
import os
import tempfile
import pandas as pd
from datetime import datetime

from services.workflow_executor import WorkflowExecutor


class TestWorkflowExecutor:
    """工作流执行器单元测试"""

    @pytest.fixture
    def temp_excel_dir(self):
        """创建临时Excel目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def executor(self, temp_excel_dir):
        """创建工作流执行器实例"""
        return WorkflowExecutor(base_dir=temp_excel_dir)

    @pytest.fixture
    def sample_excel_file(self, temp_excel_dir):
        """创建示例Excel文件"""
        df = pd.DataFrame({
            "证券代码": ["002128.SZ", "600519.SH", "000001.SZ"],
            "证券简称": ["露天煤业", "贵州茅台", "平安银行"],
            "最新公告日": ["2026-04-01", "2026-04-09", "2026-04-05"]
        })
        filepath = os.path.join(temp_excel_dir, "sample.xlsx")
        df.to_excel(filepath, index=False)
        return filepath

    @pytest.fixture
    def sample_excel_with_date(self, temp_excel_dir):
        """创建带序号的示例Excel文件"""
        df = pd.DataFrame({
            "序号": [1, 2, 3],
            "证券代码": ["002128.SZ", "600519.SH", "000001.SZ"],
            "证券简称": ["露天煤业", "贵州茅台", "平安银行"],
            "最新公告日": ["2026-04-01", "2026-04-09", "2026-04-05"]
        })
        filepath = os.path.join(temp_excel_dir, "sample.xlsx")
        df.to_excel(filepath, index=False)
        return filepath

    def test_get_daily_dir(self, executor, temp_excel_dir):
        """测试获取当日目录"""
        daily_dir = executor._get_daily_dir()
        assert daily_dir == temp_excel_dir

    def test_resolve_path_absolute(self, executor):
        """测试绝对路径解析"""
        abs_path = "/absolute/path/file.xlsx"
        resolved = executor._resolve_path(abs_path)
        assert resolved == abs_path

    def test_resolve_path_relative(self, executor, temp_excel_dir):
        """测试相对路径解析"""
        rel_path = "file.xlsx"
        resolved = executor._resolve_path(rel_path)
        expected = os.path.join(temp_excel_dir, "file.xlsx")
        assert resolved == expected

    def test_get_excel_files_in_dir(self, executor, sample_excel_file):
        """测试获取目录下的Excel文件"""
        daily_dir = os.path.dirname(sample_excel_file)
        files = executor._get_excel_files_in_dir(daily_dir)
        assert len(files) >= 1
        assert any("sample.xlsx" in f for f in files)

    def test_import_excel_success(self, executor, sample_excel_file):
        """测试成功导入Excel"""
        import asyncio
        config = {"file_path": sample_excel_file}
        result = asyncio.run(executor._import_excel(config))

        assert result["success"] is True
        assert result["rows"] == 3
        assert "data" in result

    def test_import_excel_not_found(self, executor):
        """测试导入不存在的Excel"""
        import asyncio
        config = {"file_path": "/nonexistent/file.xlsx"}
        result = asyncio.run(executor._import_excel(config))

        assert result["success"] is False
        assert "不存在" in result["message"]

    def test_import_excel_no_path(self, executor):
        """测试未指定文件路径"""
        import asyncio
        config = {}
        result = asyncio.run(executor._import_excel(config))

        assert result["success"] is False
        assert "未指定" in result["message"]

    def test_merge_excel_success(self, executor, temp_excel_dir):
        """测试成功合并Excel"""
        import asyncio

        df1 = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        df2 = pd.DataFrame({"A": [5, 6], "B": [7, 8]})

        df1.to_excel(os.path.join(temp_excel_dir, "file1.xlsx"), index=False)
        df2.to_excel(os.path.join(temp_excel_dir, "file2.xlsx"), index=False)

        config = {"output_filename": "total_1.xlsx"}
        result = asyncio.run(executor._merge_excel(config))

        assert result["success"] is True
        assert result["files_merged"] == 2
        assert result["rows"] == 4
        assert os.path.exists(result["file_path"])

    def test_merge_excel_excludes_total(self, executor, temp_excel_dir):
        """测试合并时排除total_开头的文件"""
        import asyncio

        df1 = pd.DataFrame({"A": [1, 2]})
        df2 = pd.DataFrame({"A": [3, 4]})

        df1.to_excel(os.path.join(temp_excel_dir, "file1.xlsx"), index=False)
        df2.to_excel(os.path.join(temp_excel_dir, "total_1.xlsx"), index=False)

        config = {"output_filename": "merged.xlsx"}
        result = asyncio.run(executor._merge_excel(config))

        assert result["success"] is True
        assert result["files_merged"] == 1

    def test_merge_excel_excludes_output(self, executor, temp_excel_dir):
        """测试合并时排除output_开头的文件"""
        import asyncio

        df1 = pd.DataFrame({"A": [1, 2]})
        df2 = pd.DataFrame({"A": [3, 4]})

        df1.to_excel(os.path.join(temp_excel_dir, "file1.xlsx"), index=False)
        df2.to_excel(os.path.join(temp_excel_dir, "output_1.xlsx"), index=False)

        config = {"output_filename": "merged.xlsx"}
        result = asyncio.run(executor._merge_excel(config))

        assert result["success"] is True
        assert result["files_merged"] == 1

    def test_merge_excel_no_files(self, executor, temp_excel_dir):
        """测试合并时没有Excel文件"""
        import asyncio
        config = {"output_filename": "total_1.xlsx"}
        result = asyncio.run(executor._merge_excel(config))

        assert result["success"] is False
        assert "没有找到" in result["message"]

    def test_dedup_success(self, executor):
        """测试简单去重"""
        import asyncio

        df = pd.DataFrame({
            "A": [1, 2, 2, 3],
            "B": [4, 5, 5, 6]
        })

        config = {}
        result = asyncio.run(executor._dedup(config, df))

        assert result["success"] is True
        assert result["original_rows"] == 4
        assert result["deduped_rows"] == 3
        assert result["removed_rows"] == 1

    def test_dedup_no_data(self, executor):
        """测试去重无数据"""
        import asyncio

        config = {}
        result = asyncio.run(executor._dedup(config, None))

        assert result["success"] is False
        assert "没有可处理" in result["message"]

    def test_smart_dedup_success(self, executor):
        """测试智能去重（按证券代码和最新公告日）"""
        import asyncio

        df = pd.DataFrame({
            "证券代码": ["002128.SZ", "002128.SZ", "002128.SZ"],
            "证券简称": ["A", "B", "C"],
            "最新公告日": ["2026-04-09", "2026-04-01", "2026-05-01"]
        })

        config = {}
        result = asyncio.run(executor._smart_dedup(config, df))

        assert result["success"] is True
        assert result["original_rows"] == 3
        assert result["deduped_rows"] == 1

        final_df = result["data"]
        assert final_df.iloc[0]["最新公告日"] == "2026-05-01"

    def test_smart_dedup_auto_detect_columns(self, executor):
        """测试智能去重自动检测列名"""
        import asyncio

        df = pd.DataFrame({
            "股票代码": ["001", "001", "002"],
            "名称": ["A", "A", "B"],
            "公告日期": ["2026-04-01", "2026-04-02", "2026-04-03"]
        })

        config = {}
        result = asyncio.run(executor._smart_dedup(config, df))

        assert result["success"] is True
        assert result["original_rows"] == 3
        assert result["deduped_rows"] == 2

    def test_smart_dedup_no_data(self, executor):
        """测试智能去重无数据"""
        import asyncio

        config = {}
        result = asyncio.run(executor._smart_dedup(config, None))

        assert result["success"] is False

    def test_extract_columns_fixed(self, executor, sample_excel_with_date):
        """测试提取固定4列"""
        import asyncio

        df = pd.read_excel(sample_excel_with_date)

        config = {}
        result = asyncio.run(executor._extract_columns(config, df))

        assert result["success"] is True
        extracted_df = result["data"]
        assert len(extracted_df.columns) == 4

    def test_extract_columns_no_data(self, executor):
        """测试提取列无数据"""
        import asyncio

        config = {}
        result = asyncio.run(executor._extract_columns(config, None))

        assert result["success"] is False
        assert "没有可处理" in result["message"]

    def test_export_excel_success(self, executor, temp_excel_dir):
        """测试导出Excel"""
        import asyncio

        df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        config = {"output_filename": "exported.xlsx"}

        result = asyncio.run(executor._export_excel(config, df))

        assert result["success"] is True
        assert "exported.xlsx" in result["file_path"]
        assert os.path.exists(result["file_path"])

    def test_export_excel_no_data(self, executor):
        """测试导出无数据"""
        import asyncio

        config = {"output_filename": "exported.xlsx"}
        result = asyncio.run(executor._export_excel(config, None))

        assert result["success"] is False
        assert "没有可导出" in result["message"]

    def test_unknown_step_type(self, executor):
        """测试未知步骤类型"""
        import asyncio

        config = {}
        result = asyncio.run(executor.execute_step("unknown_type", config))

        assert result["success"] is False
        assert "未知" in result["message"]


class TestSmartDedupLogic:
    """智能去重逻辑测试"""

    def test_keep_latest_date(self):
        """测试保留最新公告日"""
        df = pd.DataFrame({
            "证券代码": ["002128.SZ", "002128.SZ", "002128.SZ"],
            "最新公告日": ["2026-04-09", "2026-04-01", "2026-05-01"]
        })

        df["最新公告日"] = pd.to_datetime(df["最新公告日"])
        df_sorted = df.sort_values("最新公告日", ascending=False)
        df_deduped = df_sorted.drop_duplicates(subset=["证券代码"], keep="first")

        assert len(df_deduped) == 1
        assert df_deduped.iloc[0]["最新公告日"] == pd.Timestamp("2026-05-01")

    def test_multiple_stocks_dedup(self):
        """测试多只股票去重"""
        df = pd.DataFrame({
            "证券代码": ["002128.SZ", "002128.SZ", "600519.SH", "600519.SH"],
            "最新公告日": ["2026-04-01", "2026-04-09", "2026-04-01", "2026-04-05"]
        })

        df["最新公告日"] = pd.to_datetime(df["最新公告日"])
        df_sorted = df.sort_values("最新公告日", ascending=False)
        df_deduped = df_sorted.drop_duplicates(subset=["证券代码"], keep="first")

        assert len(df_deduped) == 2

        stock_codes = set(df_deduped["证券代码"])
        assert "002128.SZ" in stock_codes
        assert "600519.SH" in stock_codes

        sz_row = df_deduped[df_deduped["证券代码"] == "002128.SZ"].iloc[0]
        assert sz_row["最新公告日"] == pd.Timestamp("2026-04-09")

    def test_different_stocks_not_deduped(self):
        """测试不同股票不被去重"""
        df = pd.DataFrame({
            "证券代码": ["002128.SZ", "600519.SH", "000001.SZ"],
            "最新公告日": ["2026-04-01", "2026-04-01", "2026-04-01"]
        })

        df["最新公告日"] = pd.to_datetime(df["最新公告日"])
        df_sorted = df.sort_values("最新公告日", ascending=False)
        df_deduped = df_sorted.drop_duplicates(subset=["证券代码"], keep="first")

        assert len(df_deduped) == 3
