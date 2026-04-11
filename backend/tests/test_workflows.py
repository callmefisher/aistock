import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import Workflow


class TestWorkflowsAPI:
    """工作流API集成测试"""

    @pytest.mark.asyncio
    async def test_get_workflows_empty(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试获取空工作流列表"""
        response = await client.get(
            "/api/v1/workflows/",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_create_workflow(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试创建新工作流"""
        response = await client.post(
            "/api/v1/workflows/",
            headers=auth_headers,
            json={
                "name": "测试工作流",
                "description": "测试描述",
                "steps": [
                    {
                        "type": "import_excel",
                        "config": {
                            "file_path": "/path/to/file.xlsx"
                        },
                        "status": "pending"
                    },
                    {
                        "type": "dedup",
                        "config": {},
                        "status": "pending"
                    },
                    {
                        "type": "extract_columns",
                        "config": {
                            "columns": [1, 2],
                            "output_filename": "output.xlsx"
                        },
                        "status": "pending"
                    }
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "测试工作流"
        assert data["description"] == "测试描述"
        assert len(data["steps"]) == 3
        assert data["steps"][0]["type"] == "import_excel"
        assert data["steps"][1]["type"] == "dedup"
        assert data["steps"][2]["type"] == "extract_columns"
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_workflows_with_data(
        self, client: AsyncClient, auth_headers: dict, test_workflow: Workflow
    ):
        """测试获取包含数据的工作流列表"""
        response = await client.get(
            "/api/v1/workflows/",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == test_workflow.name

    @pytest.mark.asyncio
    async def test_get_workflow_by_id(
        self, client: AsyncClient, auth_headers: dict, test_workflow: Workflow
    ):
        """测试根据ID获取工作流"""
        response = await client.get(
            f"/api/v1/workflows/{test_workflow.id}/",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_workflow.id
        assert data["name"] == test_workflow.name

    @pytest.mark.asyncio
    async def test_get_workflow_not_found(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试获取不存在的工作流"""
        response = await client.get(
            "/api/v1/workflows/99999/",
            headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_workflow(
        self, client: AsyncClient, auth_headers: dict, test_workflow: Workflow
    ):
        """测试更新工作流"""
        response = await client.put(
            f"/api/v1/workflows/{test_workflow.id}/",
            headers=auth_headers,
            json={
                "name": "更新后的工作流",
                "description": "更新描述",
                "steps": [
                    {
                        "type": "import_excel",
                        "config": {"file_path": "/new/path.xlsx"},
                        "status": "pending"
                    }
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "更新后的工作流"
        assert data["description"] == "更新描述"
        assert len(data["steps"]) == 1

    @pytest.mark.asyncio
    async def test_delete_workflow(
        self, client: AsyncClient, auth_headers: dict, test_workflow: Workflow
    ):
        """测试删除工作流"""
        response = await client.delete(
            f"/api/v1/workflows/{test_workflow.id}/",
            headers=auth_headers
        )
        assert response.status_code == 200

        response = await client.get(
            f"/api/v1/workflows/{test_workflow.id}/",
            headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_run_workflow(
        self, client: AsyncClient, auth_headers: dict, test_workflow: Workflow
    ):
        """测试运行工作流"""
        response = await client.post(
            f"/api/v1/workflows/{test_workflow.id}/run/",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == test_workflow.id

    @pytest.mark.asyncio
    async def test_execute_workflow_step(
        self, client: AsyncClient, auth_headers: dict, test_workflow: Workflow
    ):
        """测试执行工作流步骤"""
        response = await client.post(
            f"/api/v1/workflows/{test_workflow.id}/execute-step/",
            headers=auth_headers,
            json={"step_index": 0}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["step_index"] == 0

    @pytest.mark.asyncio
    async def test_execute_step_out_of_range(
        self, client: AsyncClient, auth_headers: dict, test_workflow: Workflow
    ):
        """测试执行超出范围的步骤"""
        response = await client.post(
            f"/api/v1/workflows/{test_workflow.id}/execute-step/",
            headers=auth_headers,
            json={"step_index": 999}
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_workflow_requires_auth(self, client: AsyncClient):
        """测试工作流接口需要认证"""
        response = await client.get("/api/v1/workflows/")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_workflow_step_types(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试各种步骤类型的工作流"""
        step_types = ["import_excel", "dedup", "extract_columns", "export_excel", "pending"]

        for step_type in step_types:
            config = {}
            if step_type == "import_excel":
                config = {"file_path": "/test.xlsx"}
            elif step_type == "extract_columns":
                config = {"columns": [1, 2], "output_filename": "out.xlsx"}
            elif step_type == "export_excel":
                config = {"output_filename": "export.xlsx"}

            response = await client.post(
                "/api/v1/workflows/",
                headers=auth_headers,
                json={
                    "name": f"工作流_{step_type}",
                    "description": f"测试{step_type}步骤",
                    "steps": [
                        {
                            "type": step_type,
                            "config": config,
                            "status": "pending"
                        }
                    ]
                }
            )
            assert response.status_code == 200, f"Failed for step type: {step_type}"
            data = response.json()
            assert data["steps"][0]["type"] == step_type
