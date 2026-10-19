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
        import re

        target_dir = get_target_directory("merge_excel", "2026-04-12")
        assert target_dir.endswith("2026-04-12")

        # 不传 date_str → 回落到今日（格式 YYYY-MM-DD）
        target_dir_no_date = get_target_directory("merge_excel")
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", os.path.basename(target_dir_no_date))

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


class TestWeeklyUploadTargetDirectory:
    """快捷批量上传新增类型（13/14/18号表公共数据与输出）目标目录映射测试"""

    @pytest.mark.parametrize("step_type,sub_dir", [
        ("upload_weekly_ma20_high", "本周20日收盘价新高"),
        ("upload_weekly_ma20_out", "本周20日收盘价新高输出"),
        ("upload_weekly_mv1000_high", "本周总市值千亿新高"),
        ("upload_weekly_mv1000_out", "本周总市值千亿新高输出"),
        ("upload_all_a_800", "全部A股800亿"),
        ("upload_all_a_800_out", "全部A股800亿输出"),
    ])
    def test_weekly_upload_dirs(self, step_type, sub_dir):
        """6类新文件按数据日期映射到对应子目录 data/excel/{date}/{sub_dir}/"""
        from api.workflows import get_target_directory

        target_dir = get_target_directory(step_type, "2026-10-16")
        assert target_dir.endswith(os.path.join("2026-10-16", sub_dir)), target_dir

    def test_weekly_upload_dirs_differ_between_public_and_output(self):
        """公共数据目录与输出目录必须区分（如 本周总市值千亿新高 vs …输出）"""
        from api.workflows import get_target_directory

        pub = get_target_directory("upload_weekly_mv1000_high", "2026-10-16")
        out = get_target_directory("upload_weekly_mv1000_out", "2026-10-16")
        assert pub != out
        assert pub.endswith("本周总市值千亿新高")
        assert out.endswith("本周总市值千亿新高输出")


class TestDownloadResultSubdirFile:
    """download-result 端点：支持 {date} 下子目录文件下载（20号表）+ 防路径穿越。

    背景：14号表工作流附带输出 20号表 到 data/excel/{date}/20号表本周总市值千亿新高A列/，
    前端批量下载时通过 file_name="子目录/文件名" 一起下载。
    """

    def _make_weekly_mv1000_workflow(self, db_session, date_str="2026-10-16"):
        from models.models import Workflow
        wf = Workflow(
            name="本周总市值千亿新高", description="",
            workflow_type="本周总市值千亿新高", date_str=date_str,
            steps=[{"type": "weekly_mv1000_high", "config": {"date_str": date_str}, "status": "completed"}],
            status="active",
        )
        db_session.add(wf)
        return wf

    @pytest.mark.asyncio
    async def test_download_subdir_table20(self, client, auth_headers, db_session, tmp_path):
        """file_name 含子目录 → 相对 {date} 根目录解析，20号表可下载"""
        from unittest.mock import patch
        wf = self._make_weekly_mv1000_workflow(db_session)
        await db_session.commit()
        await db_session.refresh(wf)

        t20_dir = os.path.join(str(tmp_path), "2026-10-16", "20号表本周总市值千亿新高A列")
        os.makedirs(t20_dir)
        t20 = os.path.join(t20_dir, "20 总市值大于1000亿 本周最高价格大于上周最高价格.xlsx")
        pd.DataFrame({"股票代码": ["000001.SZ"]}).to_excel(t20, index=False)

        with patch("api.workflows.BASE_DIR", str(tmp_path)):
            resp = await client.get(
                f"/api/v1/workflows/download-result/{wf.id}",
                params={"file_name": "20号表本周总市值千亿新高A列/20 总市值大于1000亿 本周最高价格大于上周最高价格.xlsx"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers.get("content-type", "")
        # 下载内容为20号表文件本体（子目录解析成功）
        assert len(resp.content) > 0

    @pytest.mark.asyncio
    async def test_download_subdir_rejects_path_traversal(self, client, auth_headers, db_session, tmp_path):
        """file_name 含 ../ 路径穿越 → 400 拒绝"""
        from unittest.mock import patch
        wf = self._make_weekly_mv1000_workflow(db_session)
        await db_session.commit()
        await db_session.refresh(wf)

        secret_dir = os.path.join(str(tmp_path), "2026-10-15")
        os.makedirs(secret_dir)
        pd.DataFrame({"x": [1]}).to_excel(os.path.join(secret_dir, "secret.xlsx"), index=False)

        with patch("api.workflows.BASE_DIR", str(tmp_path)):
            resp = await client.get(
                f"/api/v1/workflows/download-result/{wf.id}",
                params={"file_name": "../2026-10-15/secret.xlsx"},
                headers=auth_headers,
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_download_plain_filename_still_works(self, client, auth_headers, db_session, tmp_path):
        """普通文件名（无子目录）→ 仍在 daily_dir（本周总市值千亿新高输出）下解析（原行为不变）"""
        from unittest.mock import patch
        wf = self._make_weekly_mv1000_workflow(db_session)
        await db_session.commit()
        await db_session.refresh(wf)

        out_dir = os.path.join(str(tmp_path), "2026-10-16", "本周总市值千亿新高输出")
        os.makedirs(out_dir)
        main_file = os.path.join(out_dir, "14 总市值大于1000亿 本周最高价格大于上周最高价格1016.xlsx")
        pd.DataFrame({"股票代码": ["000001.SZ"]}).to_excel(main_file, index=False)

        with patch("api.workflows.BASE_DIR", str(tmp_path)):
            resp = await client.get(
                f"/api/v1/workflows/download-result/{wf.id}",
                params={"file_name": "14 总市值大于1000亿 本周最高价格大于上周最高价格1016.xlsx"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers.get("content-type", "")
        assert len(resp.content) > 0


class TestBatchAggregationOrder:
    """批量执行顺序：本周三类工作流排在条件交集之后的链尾"""

    def test_agg_dependency_order_contains_weekly_types(self):
        from api.workflows import _AGG_DEPENDENCY_ORDER as order
        assert order["条件交集"] < order["当月每日新增"] < order["本月AI筛选汇总"] < order["本月AI筛选20日线汇总"]
        # 本周三类均在条件交集之后（且相互独立，固定链尾顺序）
        assert order["本周20日线新高"] > order["条件交集"]
        assert order["本周总市值千亿新高"] > order["条件交集"]
        assert order["全部A股总市值大于800亿"] > order["条件交集"]


class TestUploadClearDirectoryIndependence:
    """上传清目录独立性（API 级）：上传A只清理A目录，上传B只清理B目录，绝不联动。

    背景：「本周20日收盘价新高」（公共数据）与「本周20日收盘价新高输出」（13号表输出）
    是同一数据日期下两个独立目录。上传公共文件时只清公共目录（输出目录不动）；
    上传输出文件时只清输出目录（公共目录不动）。
    """

    def _setup_two_dirs(self, base):
        """在公共/输出两个目录各放1个老文件 + 相邻其他类型目录放1个老文件"""
        import pandas as pd
        pub = os.path.join(base, "2026-10-16", "本周20日收盘价新高")
        out = os.path.join(base, "2026-10-16", "本周20日收盘价新高输出")
        other = os.path.join(base, "2026-10-16", "本周总市值千亿新高")
        for d in (pub, out, other):
            os.makedirs(d, exist_ok=True)
        pd.DataFrame({"证券代码": ["000001.SZ"]}).to_excel(os.path.join(pub, "老公共文件.xlsx"), index=False)
        pd.DataFrame({"日期": ["2026-10-15"]}).to_excel(os.path.join(out, "老输出文件.xlsx"), index=False)
        pd.DataFrame({"x": [1]}).to_excel(os.path.join(other, "老千亿文件.xlsx"), index=False)
        return pub, out, other

    @pytest.mark.asyncio
    async def test_upload_public_clears_only_public_dir(self, client, auth_headers, tmp_path):
        """上传公共文件（upload_weekly_ma20_high）→ 只清公共目录；输出/千亿目录不受影响"""
        from unittest.mock import patch
        pub, out, other = self._setup_two_dirs(str(tmp_path))

        with patch("api.workflows.BASE_DIR", str(tmp_path)):
            resp = await client.post(
                "/api/v1/workflows/upload-step-file/",
                data={"workflow_id": 1, "step_index": 0, "step_type": "upload_weekly_ma20_high",
                      "workflow_type": "并购重组", "date_str": "2026-10-16"},
                files={"file": ("新公共文件.xlsx", b"fake-excel-bytes",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # 公共目录：老文件被清、只剩新上传的
        assert sorted(os.listdir(pub)) == ["新公共文件.xlsx"]
        # 输出目录：老文件原样保留（未受影响）
        assert os.listdir(out) == ["老输出文件.xlsx"]
        # 其他类型目录：未受影响
        assert os.listdir(other) == ["老千亿文件.xlsx"]

    @pytest.mark.asyncio
    async def test_upload_output_clears_only_output_dir(self, client, auth_headers, tmp_path):
        """上传输出文件（upload_weekly_ma20_out）→ 只清输出目录；公共/千亿目录不受影响"""
        from unittest.mock import patch
        pub, out, other = self._setup_two_dirs(str(tmp_path))

        with patch("api.workflows.BASE_DIR", str(tmp_path)):
            resp = await client.post(
                "/api/v1/workflows/upload-step-file/",
                data={"workflow_id": 1, "step_index": 0, "step_type": "upload_weekly_ma20_out",
                      "workflow_type": "并购重组", "date_str": "2026-10-16"},
                files={"file": ("13 占20日线无振幅 1016.xlsx", b"fake-excel-bytes",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # 输出目录：老文件被清、只剩新上传的
        assert sorted(os.listdir(out)) == ["13 占20日线无振幅 1016.xlsx"]
        # 公共目录：老文件原样保留（未受影响）
        assert os.listdir(pub) == ["老公共文件.xlsx"]
        # 其他类型目录：未受影响
        assert os.listdir(other) == ["老千亿文件.xlsx"]

    @pytest.mark.asyncio
    async def test_upload_same_name_overwrites_in_own_dir(self, client, auth_headers, tmp_path):
        """同名文件覆盖：目标目录只保留最新1个文件（先删老的再落新的）"""
        from unittest.mock import patch
        pub, out, _ = self._setup_two_dirs(str(tmp_path))

        with patch("api.workflows.BASE_DIR", str(tmp_path)):
            resp = await client.post(
                "/api/v1/workflows/upload-step-file/",
                data={"workflow_id": 1, "step_index": 0, "step_type": "upload_weekly_ma20_high",
                      "workflow_type": "并购重组", "date_str": "2026-10-16"},
                files={"file": ("老公共文件.xlsx", b"new-content",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                headers=auth_headers,
            )
        assert resp.json()["success"] is True
        # 同名覆盖：目录内仍只有这1个文件，且为本次上传内容
        assert os.listdir(pub) == ["老公共文件.xlsx"]
        assert open(os.path.join(pub, "老公共文件.xlsx"), "rb").read() == b"new-content"
        assert os.listdir(out) == ["老输出文件.xlsx"]


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

        # match_high_price 的源目录是 {base}/{date}/百日新高
        match_dir = os.path.join(temp_dir, "2026-04-12", "百日新高")
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
        # _match_high_price 输出 daily 目录下，需先建好
        os.makedirs(os.path.join(temp_dir, "2026-04-12"), exist_ok=True)
        result = asyncio.run(executor._match_high_price(config, source_df, date_str="2026-04-12"))

        assert result["success"] is True
        assert "匹配" in result["message"]
        # 两行 source 各匹配 1 行
        assert result.get("matched_count") == 2 or "2条" in result["message"]
