import pytest
import os
import tempfile
import pandas as pd
from io import BytesIO
from httpx import AsyncClient

from services.workflow_executor import WorkflowExecutor


class TestFileUploadAPI:
    """文件上传API测试"""

    @pytest.fixture
    def temp_base_dir(self):
        """创建临时基础目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def executor(self, temp_base_dir):
        """创建工作流执行器实例"""
        return WorkflowExecutor(base_dir=temp_base_dir)

    @pytest.fixture
    def sample_excel_bytes(self):
        """创建示例Excel字节数据"""
        df = pd.DataFrame({
            "证券代码": ["002128.SZ", "600519.SH", "000001.SZ"],
            "证券简称": ["露天煤业", "贵州茅台", "平安银行"],
            "最新公告日": ["2026-04-01", "2026-04-09", "2026-04-05"]
        })
        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)
        return buffer.getvalue()

    def test_get_target_directory_merge_excel(self, executor):
        """测试merge_excel步骤的目标目录"""
        from api.workflows import get_target_directory

        target_dir = get_target_directory("merge_excel", "2026-04-12")
        assert target_dir.endswith("2026-04-12")

        target_dir_no_date = get_target_directory("merge_excel")
        assert os.path.basename(target_dir_no_date) == os.path.basename(target_dir)

    def test_get_target_directory_match_high_price(self, executor):
        """测试match_high_price步骤的目标目录"""
        from api.workflows import get_target_directory

        target_dir = get_target_directory("match_high_price", "2026-04-12")
        assert target_dir.endswith("百日新高")

    def test_get_target_directory_match_ma20(self, executor):
        """测试match_ma20步骤的目标目录"""
        from api.workflows import get_target_directory

        target_dir = get_target_directory("match_ma20", "2026-04-12")
        assert target_dir.endswith("20日均线")

    def test_get_target_directory_match_soe(self, executor):
        """测试match_soe步骤的目标目录"""
        from api.workflows import get_target_directory

        target_dir = get_target_directory("match_soe", "2026-04-12")
        assert target_dir.endswith("国企")

    def test_get_target_directory_match_sector(self, executor):
        """测试match_sector步骤的目标目录"""
        from api.workflows import get_target_directory

        target_dir = get_target_directory("match_sector", "2026-04-12")
        assert target_dir.endswith("一级板块")

    def test_get_target_directory_unknown_type(self, executor):
        """测试未知步骤类型的目标目录"""
        from api.workflows import get_target_directory

        target_dir = get_target_directory("unknown_type", "2026-04-12")
        assert target_dir.endswith("2026-04-12")


class TestFileOperations:
    """文件操作测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def sample_excel_file(self, temp_dir):
        """创建示例Excel文件"""
        df = pd.DataFrame({
            "证券代码": ["002128.SZ", "600519.SH"],
            "证券简称": ["露天煤业", "贵州茅台"],
            "最新公告日": ["2026-04-01", "2026-04-09"]
        })
        filepath = os.path.join(temp_dir, "sample.xlsx")
        df.to_excel(filepath, index=False)
        return filepath

    def test_list_excel_files(self, temp_dir, sample_excel_file):
        """测试列出Excel文件"""
        import glob

        files = []
        for ext in ["*.xlsx", "*.xls"]:
            pattern = os.path.join(temp_dir, ext)
            files.extend(glob.glob(pattern))

        assert len(files) >= 1
        assert any("sample.xlsx" in f for f in files)

    def test_delete_file(self, temp_dir, sample_excel_file):
        """测试删除文件"""
        assert os.path.exists(sample_excel_file)

        os.remove(sample_excel_file)
        assert not os.path.exists(sample_excel_file)

    def test_preview_excel_file(self, temp_dir, sample_excel_file):
        """测试预览Excel文件"""
        df = pd.read_excel(sample_excel_file)
        records = df.head(20).fillna('').to_dict('records')
        columns = df.columns.tolist()

        assert len(columns) == 3
        assert "证券代码" in columns
        assert len(records) == 2
        assert records[0]["证券代码"] == "002128.SZ"


class TestFileUploadFlow:
    """文件上传流程测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_upload_creates_directory(self, temp_dir):
        """测试上传文件时创建目录"""
        target_dir = os.path.join(temp_dir, "2026-04-12")
        os.makedirs(target_dir, exist_ok=True)

        filepath = os.path.join(target_dir, "test.xlsx")
        df = pd.DataFrame({"A": [1, 2]})
        df.to_excel(filepath, index=False)

        assert os.path.exists(target_dir)
        assert os.path.exists(filepath)

    def test_multiple_files_in_same_directory(self, temp_dir):
        """测试同一目录下多个文件"""
        target_dir = os.path.join(temp_dir, "百日新高")
        os.makedirs(target_dir, exist_ok=True)

        for i in range(3):
            filepath = os.path.join(target_dir, f"stock_{i}.xlsx")
            df = pd.DataFrame({"股票代码": [f"00{i}"], "股票简称": [f"股票{i}"]})
            df.to_excel(filepath, index=False)

        import glob
        files = glob.glob(os.path.join(target_dir, "*.xlsx"))
        assert len(files) == 3


class TestDownloadResult:
    """下载结果测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def workflow_output_files(self, temp_dir):
        """创建工作流输出文件"""
        date_dir = os.path.join(temp_dir, "2026-04-12")
        os.makedirs(date_dir, exist_ok=True)

        output_file = os.path.join(date_dir, "total_1.xlsx")
        df = pd.DataFrame({
            "证券代码": ["002128.SZ", "600519.SH"],
            "证券简称": ["露天煤业", "贵州茅台"]
        })
        df.to_excel(output_file, index=False)

        return {
            "date_dir": date_dir,
            "output_file": output_file,
            "output_filename": "total_1.xlsx"
        }

    def test_find_result_file_by_name(self, temp_dir, workflow_output_files):
        """测试按文件名查找结果文件"""
        output_filename = workflow_output_files["output_filename"]
        date_dir = workflow_output_files["date_dir"]

        filepath = os.path.join(date_dir, output_filename)
        assert os.path.exists(filepath)

    def test_find_latest_result_file(self, temp_dir, workflow_output_files):
        """测试查找最新的结果文件"""
        import glob

        date_dir = workflow_output_files["date_dir"]
        files = glob.glob(os.path.join(date_dir, "*.xlsx"))

        latest = sorted(files)[-1] if files else None
        assert latest is not None
        assert latest.endswith("total_1.xlsx")

    def test_result_file_content(self, temp_dir, workflow_output_files):
        """测试结果文件内容"""
        filepath = workflow_output_files["output_file"]
        df = pd.read_excel(filepath)

        assert len(df) == 2
        assert "证券代码" in df.columns
        assert "证券简称" in df.columns


class TestUploadWithWorkflowExecutor:
    """与工作流执行器集成的上传测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def executor(self, temp_dir):
        """创建工作流执行器"""
        return WorkflowExecutor(base_dir=temp_dir)

    def test_merge_with_uploaded_files(self, temp_dir, executor):
        """测试合并上传的文件"""
        import asyncio

        date_dir = os.path.join(temp_dir, "2026-04-12")
        os.makedirs(date_dir, exist_ok=True)

        df1 = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        df2 = pd.DataFrame({"A": [5, 6], "B": [7, 8]})

        df1.to_excel(os.path.join(date_dir, "uploaded_1.xlsx"), index=False)
        df2.to_excel(os.path.join(date_dir, "uploaded_2.xlsx"), index=False)

        config = {"output_filename": "merged.xlsx"}
        result = asyncio.run(executor._merge_excel(config, date_str="2026-04-12"))

        assert result["success"] is True
        assert result["files_merged"] == 2
        assert result["rows"] == 4

    def test_match_uses_uploaded_files(self, temp_dir, executor):
        """测试匹配使用上传的文件"""
        import asyncio

        match_dir = os.path.join(temp_dir, "百日新高")
        os.makedirs(match_dir, exist_ok=True)

        match_df = pd.DataFrame({
            "股票代码": ["002128", "600519"],
            "股票简称": ["露天煤业", "贵州茅台"]
        })
        match_df.to_excel(os.path.join(match_dir, "high_prices.xlsx"), index=False)

        source_df = pd.DataFrame({
            "证券代码": ["002128.SZ", "600519.SH", "000001.SZ"],
            "证券简称": ["A", "B", "C"]
        })

        config = {
            "source_dir": "百日新高",
            "new_column_name": "百日新高",
            "output_filename": "output.xlsx"
        }
        result = asyncio.run(executor._match_high_price(config, source_df, date_str="2026-04-12"))

        assert result["success"] is True
        assert "百日新高" in result["message"]
