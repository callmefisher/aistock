import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import Rule


class TestRulesAPI:
    """规则API集成测试"""

    @pytest.mark.asyncio
    async def test_get_rules_empty(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试获取空规则列表"""
        response = await client.get(
            "/api/v1/rules/",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_rules_with_data(
        self, client: AsyncClient, auth_headers: dict, test_rule: Rule
    ):
        """测试获取包含数据的规则列表"""
        response = await client.get(
            "/api/v1/rules/",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == test_rule.name

    @pytest.mark.asyncio
    async def test_get_rule_by_id(
        self, client: AsyncClient, auth_headers: dict, test_rule: Rule
    ):
        """测试根据ID获取规则"""
        response = await client.get(
            f"/api/v1/rules/{test_rule.id}/",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_rule.id
        assert data["name"] == test_rule.name

    @pytest.mark.asyncio
    async def test_get_rule_not_found(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试获取不存在的规则"""
        response = await client.get(
            "/api/v1/rules/99999/",
            headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_rule(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试创建新规则"""
        response = await client.post(
            "/api/v1/rules/",
            headers=auth_headers,
            json={
                "name": "新规则",
                "description": "筛选市值大于1000亿的股票",
                "natural_language": "筛选市值大于1000亿",
                "excel_formula": "IF(市值>1000,TRUE,FALSE)",
                "filter_conditions": [
                    {"column": "市值", "operator": "greater_than", "value": 1000}
                ],
                "priority": 1,
                "is_active": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "新规则"
        assert data["priority"] == 1

    @pytest.mark.asyncio
    async def test_update_rule(
        self, client: AsyncClient, auth_headers: dict, test_rule: Rule
    ):
        """测试更新规则"""
        response = await client.put(
            f"/api/v1/rules/{test_rule.id}/",
            headers=auth_headers,
            json={
                "name": "更新后的规则",
                "priority": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "更新后的规则"
        assert data["priority"] == 5

    @pytest.mark.asyncio
    async def test_delete_rule(
        self, client: AsyncClient, auth_headers: dict, test_rule: Rule
    ):
        """测试删除规则"""
        response = await client.delete(
            f"/api/v1/rules/{test_rule.id}/",
            headers=auth_headers
        )
        assert response.status_code == 200

        response = await client.get(
            f"/api/v1/rules/{test_rule.id}/",
            headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_rule_requires_auth(self, client: AsyncClient):
        """测试规则接口需要认证"""
        response = await client.get("/api/v1/rules/")
        assert response.status_code == 401
