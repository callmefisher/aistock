import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import Task


class TestTasksAPI:
    """任务API集成测试"""

    @pytest.mark.asyncio
    async def test_get_tasks_empty(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试获取空任务列表"""
        response = await client.get(
            "/api/v1/tasks/",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_tasks_with_data(
        self, client: AsyncClient, auth_headers: dict, test_task: Task
    ):
        """测试获取包含数据的任务列表"""
        response = await client.get(
            "/api/v1/tasks/",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == test_task.name

    @pytest.mark.asyncio
    async def test_get_task_by_id(
        self, client: AsyncClient, auth_headers: dict, test_task: Task
    ):
        """测试根据ID获取任务"""
        response = await client.get(
            f"/api/v1/tasks/{test_task.id}/",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_task.id
        assert data["name"] == test_task.name

    @pytest.mark.asyncio
    async def test_get_task_not_found(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试获取不存在的任务"""
        response = await client.get(
            "/api/v1/tasks/99999/",
            headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_task(
        self, client: AsyncClient, auth_headers: dict, test_data_source, test_rule
    ):
        """测试创建新任务"""
        response = await client.post(
            "/api/v1/tasks/",
            headers=auth_headers,
            json={
                "name": "新建任务",
                "data_source_ids": [test_data_source.id],
                "rule_ids": [test_rule.id],
                "schedule_type": "daily",
                "schedule_config": {"hour": 9, "minute": 0},
                "is_active": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "新建任务"
        assert data["schedule_type"] == "daily"

    @pytest.mark.asyncio
    async def test_update_task(
        self, client: AsyncClient, auth_headers: dict, test_task: Task
    ):
        """测试更新任务"""
        response = await client.put(
            f"/api/v1/tasks/{test_task.id}/",
            headers=auth_headers,
            json={
                "name": "更新后的任务",
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "更新后的任务"

    @pytest.mark.asyncio
    async def test_delete_task(
        self, client: AsyncClient, auth_headers: dict, test_task: Task
    ):
        """测试删除任务"""
        response = await client.delete(
            f"/api/v1/tasks/{test_task.id}/",
            headers=auth_headers
        )
        assert response.status_code == 200

        response = await client.get(
            f"/api/v1/tasks/{test_task.id}/",
            headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_run_task(
        self, client: AsyncClient, auth_headers: dict, test_task: Task
    ):
        """测试手动运行任务"""
        response = await client.post(
            f"/api/v1/tasks/{test_task.id}/run/",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == f"任务 {test_task.id} 已加入执行队列"

    @pytest.mark.asyncio
    async def test_task_requires_auth(self, client: AsyncClient):
        """测试任务接口需要认证"""
        response = await client.get("/api/v1/tasks/")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_task_execution_logs(
        self, client: AsyncClient, auth_headers: dict, test_task: Task
    ):
        """测试获取任务执行日志"""
        response = await client.get(
            f"/api/v1/tasks/{test_task.id}/logs/",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
