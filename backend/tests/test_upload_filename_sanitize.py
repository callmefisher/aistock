"""测试 upload-step-file 对 filename 的 basename 剥离防御"""
import io
import os
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import Workflow


async def _upload(client: AsyncClient, headers: dict, *, filename: str, workflow_type: str, step_type: str, date_str: str):
    """辅助：构造 multipart 上传请求"""
    return await client.post(
        "/api/v1/workflows/upload-step-file/",
        headers=headers,
        files={"file": (filename, io.BytesIO(b"fake xlsx content"), "application/octet-stream")},
        data={
            "workflow_id": "0",
            "step_index": "0",
            "step_type": step_type,
            "workflow_type": workflow_type,
            "date_str": date_str,
        },
    )


class TestUploadFilenameSanitization:
    """filename 含路径分隔符时应被剥离为 basename"""

    @pytest.mark.asyncio
    async def test_webkitdirectory_relative_path_stripped(
        self, client: AsyncClient, auth_headers: dict, tmp_path, monkeypatch
    ):
        """Safari webkitdirectory 下 file.name = '0422/foo.xlsx' 应正确保存为 foo.xlsx"""
        # 重定向 BASE_DIR 到 tmp 避免污染真实数据
        from api import workflows as wf_module
        monkeypatch.setattr(wf_module, "BASE_DIR", str(tmp_path))

        resp = await _upload(
            client, auth_headers,
            filename="0422/foo.xlsx",
            workflow_type="并购重组",
            step_type="merge_excel",
            date_str="2026-04-23",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True, data
        saved_path = data["file"]["path"]
        assert os.path.basename(saved_path) == "foo.xlsx"
        assert "0422/foo.xlsx" not in saved_path
        assert os.path.isfile(saved_path)

    @pytest.mark.asyncio
    async def test_windows_backslash_path_stripped(
        self, client: AsyncClient, auth_headers: dict, tmp_path, monkeypatch
    ):
        """Windows 风格分隔符也被剥离"""
        from api import workflows as wf_module
        monkeypatch.setattr(wf_module, "BASE_DIR", str(tmp_path))

        resp = await _upload(
            client, auth_headers,
            filename=r"sub\bar.xlsx",
            workflow_type="并购重组",
            step_type="merge_excel",
            date_str="2026-04-23",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert os.path.basename(data["file"]["path"]) == "bar.xlsx"

    @pytest.mark.asyncio
    async def test_path_traversal_attempt_rejected(
        self, client: AsyncClient, auth_headers: dict, tmp_path, monkeypatch
    ):
        """../../etc/passwd 被剥到 passwd，不会写到 target_dir 之外"""
        from api import workflows as wf_module
        monkeypatch.setattr(wf_module, "BASE_DIR", str(tmp_path))

        resp = await _upload(
            client, auth_headers,
            filename="../../etc/passwd",
            workflow_type="并购重组",
            step_type="merge_excel",
            date_str="2026-04-23",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        saved = data["file"]["path"]
        # basename 是 "passwd"，存放在 target_dir 内
        assert os.path.basename(saved) == "passwd"
        assert saved.startswith(str(tmp_path))

    @pytest.mark.asyncio
    async def test_empty_or_dot_filename_rejected(
        self, client: AsyncClient, auth_headers: dict, tmp_path, monkeypatch
    ):
        """空、仅 `.`、仅 `..` 的 filename 被拒"""
        from api import workflows as wf_module
        monkeypatch.setattr(wf_module, "BASE_DIR", str(tmp_path))

        for bad in ["..", "./"]:
            resp = await _upload(
                client, auth_headers,
                filename=bad,
                workflow_type="并购重组",
                step_type="merge_excel",
                date_str="2026-04-23",
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is False, f"{bad!r} 应被拒但实际：{data}"

    @pytest.mark.asyncio
    async def test_normal_filename_unchanged(
        self, client: AsyncClient, auth_headers: dict, tmp_path, monkeypatch
    ):
        """普通文件名不受影响"""
        from api import workflows as wf_module
        monkeypatch.setattr(wf_module, "BASE_DIR", str(tmp_path))

        resp = await _upload(
            client, auth_headers,
            filename="1并购重组0423.xlsx",
            workflow_type="并购重组",
            step_type="merge_excel",
            date_str="2026-04-23",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert os.path.basename(data["file"]["path"]) == "1并购重组0423.xlsx"
