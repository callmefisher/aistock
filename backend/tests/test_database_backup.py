import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient


class TestDatabaseExport:
    @pytest.mark.asyncio
    async def test_export_requires_auth(self, async_client: AsyncClient):
        response = await async_client.get("/api/v1/database/export")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_export_success(self, async_client: AsyncClient, auth_headers: dict):
        with patch("api.database_backup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stderr=b"", stdout=b"-- MySQL dump\nCREATE TABLE test (id INT);"
            )
            response = await async_client.get("/api/v1/database/export", headers=auth_headers)
        assert response.status_code == 200
        assert "attachment" in response.headers.get("content-disposition", "")

    @pytest.mark.asyncio
    async def test_export_mysqldump_failure(self, async_client: AsyncClient, auth_headers: dict):
        with patch("api.database_backup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr=b"Access denied", stdout=b"")
            response = await async_client.get("/api/v1/database/export", headers=auth_headers)
        assert response.status_code == 500
        assert "Access denied" in response.json()["detail"]


class TestDatabaseImport:
    @pytest.mark.asyncio
    async def test_import_requires_auth(self, async_client: AsyncClient):
        response = await async_client.post("/api/v1/database/import")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_import_rejects_non_sql(self, async_client: AsyncClient, auth_headers: dict):
        response = await async_client.post(
            "/api/v1/database/import",
            headers=auth_headers,
            files={"file": ("backup.zip", b"fake content", "application/zip")},
        )
        assert response.status_code == 400
        assert "sql" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_import_success(self, async_client: AsyncClient, auth_headers: dict):
        with patch("api.database_backup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")
            response = await async_client.post(
                "/api/v1/database/import",
                headers=auth_headers,
                files={"file": ("backup.sql", b"-- MySQL dump\nSELECT 1;", "text/plain")},
            )
        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_import_mysql_failure(self, async_client: AsyncClient, auth_headers: dict):
        with patch("api.database_backup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr=b"Table doesn't exist")
            response = await async_client.post(
                "/api/v1/database/import",
                headers=auth_headers,
                files={"file": ("backup.sql", b"-- MySQL dump", "text/plain")},
            )
        assert response.status_code == 500
        assert "Table doesn't exist" in response.json()["detail"]
