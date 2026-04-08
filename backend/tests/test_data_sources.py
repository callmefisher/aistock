import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import DataSource


class TestDataSourcesAPI:
    """数据源API集成测试"""

    @pytest.mark.asyncio
    async def test_get_data_sources_empty(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试获取空数据源列表"""
        response = await client.get(
            "/api/v1/data-sources/",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_data_sources_with_data(
        self, client: AsyncClient, auth_headers: dict, test_data_source: DataSource
    ):
        """测试获取包含数据的数据源列表"""
        response = await client.get(
            "/api/v1/data-sources/",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == test_data_source.name

    @pytest.mark.asyncio
    async def test_get_data_source_by_id(
        self, client: AsyncClient, auth_headers: dict, test_data_source: DataSource
    ):
        """测试根据ID获取数据源"""
        response = await client.get(
            f"/api/v1/data-sources/{test_data_source.id}/",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_data_source.id
        assert data["name"] == test_data_source.name

    @pytest.mark.asyncio
    async def test_get_data_source_not_found(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试获取不存在的数据源"""
        response = await client.get(
            "/api/v1/data-sources/99999/",
            headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_data_source(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试创建新数据源"""
        response = await client.post(
            "/api/v1/data-sources/",
            headers=auth_headers,
            json={
                "name": "新建数据源",
                "website_url": "https://newsite.com",
                "login_type": "password",
                "login_config": {"username": "user", "password": "pass"},
                "data_format": "excel",
                "extraction_config": {"sheet_name": "Data"}
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "新建数据源"
        assert data["website_url"] == "https://newsite.com"
        assert data["login_type"] == "password"

    @pytest.mark.asyncio
    async def test_update_data_source(
        self, client: AsyncClient, auth_headers: dict, test_data_source: DataSource
    ):
        """测试更新数据源"""
        response = await client.put(
            f"/api/v1/data-sources/{test_data_source.id}/",
            headers=auth_headers,
            json={
                "name": "更新后的数据源",
                "is_active": False
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "更新后的数据源"
        assert data["is_active"] is False

    @pytest.mark.asyncio
    async def test_delete_data_source(
        self, client: AsyncClient, auth_headers: dict, test_data_source: DataSource
    ):
        """测试删除数据源"""
        response = await client.delete(
            f"/api/v1/data-sources/{test_data_source.id}/",
            headers=auth_headers
        )
        assert response.status_code == 200

        response = await client.get(
            f"/api/v1/data-sources/{test_data_source.id}/",
            headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_data_source_requires_auth(self, client: AsyncClient):
        """测试数据源接口需要认证"""
        response = await client.get("/api/v1/data-sources/")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_data_source_invalid_login_type(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试创建数据源时无效的登录类型"""
        response = await client.post(
            "/api/v1/data-sources/",
            headers=auth_headers,
            json={
                "name": "测试数据源",
                "website_url": "https://test.com",
                "login_type": "invalid_type",
                "data_format": "excel"
            }
        )
        assert response.status_code == 200
