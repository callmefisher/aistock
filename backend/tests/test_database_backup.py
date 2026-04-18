import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient


class TestDatabaseExport:
    @pytest.mark.asyncio
    async def test_export_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/database/export")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_export_requires_superuser(self, client: AsyncClient, auth_headers: dict):
        """非管理员应返回 403"""
        response = await client.get("/api/v1/database/export", headers=auth_headers)
        assert response.status_code == 403
        assert "管理员" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_export_success(self, client: AsyncClient, superuser_auth_headers: dict):
        with patch("api.database_backup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stderr=b"", stdout=b"-- MySQL dump\nCREATE TABLE test (id INT);"
            )
            response = await client.get("/api/v1/database/export", headers=superuser_auth_headers)
        assert response.status_code == 200
        assert "attachment" in response.headers.get("content-disposition", "")

    @pytest.mark.asyncio
    async def test_export_mysqldump_failure(self, client: AsyncClient, superuser_auth_headers: dict):
        with patch("api.database_backup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr=b"Access denied", stdout=b"")
            response = await client.get("/api/v1/database/export", headers=superuser_auth_headers)
        assert response.status_code == 500
        assert "Access denied" in response.json()["detail"]


class TestDatabaseImport:
    @pytest.mark.asyncio
    async def test_import_requires_auth(self, client: AsyncClient):
        response = await client.post("/api/v1/database/import")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_import_requires_superuser(self, client: AsyncClient, auth_headers: dict):
        """非管理员应返回 403"""
        response = await client.post(
            "/api/v1/database/import",
            headers=auth_headers,
            files={"file": ("backup.sql", b"-- MySQL dump", "text/plain")},
        )
        assert response.status_code == 403
        assert "管理员" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_import_rejects_non_sql(self, client: AsyncClient, superuser_auth_headers: dict):
        response = await client.post(
            "/api/v1/database/import",
            headers=superuser_auth_headers,
            files={"file": ("backup.zip", b"fake content", "application/zip")},
        )
        assert response.status_code == 400
        assert "sql" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_import_rejects_invalid_sql_header(self, client: AsyncClient, superuser_auth_headers: dict):
        """内容不以 -- 开头应返回 400"""
        response = await client.post(
            "/api/v1/database/import",
            headers=superuser_auth_headers,
            files={"file": ("backup.sql", b"INVALID CONTENT", "text/plain")},
        )
        assert response.status_code == 400
        assert "SQL" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_import_success(self, client: AsyncClient, superuser_auth_headers: dict):
        with patch("api.database_backup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")
            response = await client.post(
                "/api/v1/database/import",
                headers=superuser_auth_headers,
                files={"file": ("backup.sql", b"-- MySQL dump\nSELECT 1;", "text/plain")},
            )
        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_import_mysql_failure(self, client: AsyncClient, superuser_auth_headers: dict):
        with patch("api.database_backup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr=b"Table doesn't exist")
            response = await client.post(
                "/api/v1/database/import",
                headers=superuser_auth_headers,
                files={"file": ("backup.sql", b"-- MySQL dump", "text/plain")},
            )
        assert response.status_code == 500
        assert "Table doesn't exist" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_import_rejects_oversized_file(self, client: AsyncClient, superuser_auth_headers: dict):
        """超过大小限制的文件应返回 413（通过 patch MAX_IMPORT_SIZE 降低阈值验证逻辑）"""
        from unittest.mock import patch as mock_patch

        with mock_patch("api.database_backup.MAX_IMPORT_SIZE", 10):
            response = await client.post(
                "/api/v1/database/import",
                headers=superuser_auth_headers,
                files={"file": ("backup.sql", b"-- " + b"x" * 20, "text/plain")},
            )
        assert response.status_code == 413
        assert "500MB" in response.json()["detail"]
