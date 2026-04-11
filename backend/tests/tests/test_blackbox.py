"""
后端黑盒测试套件（E2E测试）
不依赖内部实现，通过HTTP接口进行完整的功能测试
"""

import pytest
import httpx
from typing import Dict


class TestBlackBoxAPI:
    """
    黑盒API测试
    将整个应用视为黑盒，只通过外部接口进行测试
    """

    @pytest.fixture
    def base_url(self) -> str:
        """从环境变量或配置文件获取API基础URL"""
        import os
        return os.getenv("TEST_API_BASE_URL", "http://localhost:8000")

    @pytest.fixture
    def client(self, base_url: str) -> httpx.Client:
        """创建HTTP客户端"""
        return httpx.Client(base_url=base_url, timeout=30.0, follow_redirects=True)

    @pytest.mark.integration
    def test_api_health_check(self, client: httpx.Client):
        """
        黑盒测试：API健康检查
        验证API服务正常运行
        """
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.integration
    def test_api_root_endpoint(self, client: httpx.Client):
        """
        黑盒测试：根端点
        验证API根路径返回正确信息
        """
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data

    @pytest.mark.integration
    def test_api_spec_endpoint(self, client: httpx.Client):
        """
        黑盒测试：OpenAPI规范端点
        验证OpenAPI文档可访问
        """
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    @pytest.mark.integration
    def test_api_docs_endpoint(self, client: httpx.Client):
        """
        黑盒测试：API文档端点
        验证Swagger UI可访问
        """
        response = client.get("/docs")
        assert response.status_code == 200


class TestAuthenticationFlow:
    """
    黑盒测试：认证流程
    从用户角度测试完整的认证流程
    """

    @pytest.fixture
    def base_url(self) -> str:
        import os
        return os.getenv("TEST_API_BASE_URL", "http://localhost:8000")

    @pytest.fixture
    def test_credentials(self) -> Dict[str, str]:
        """测试凭据"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        return {
            "username": f"blackbox_user_{unique_id}",
            "email": f"blackbox_{unique_id}@test.com",
            "password": "TestPass123!"
        }

    @pytest.mark.integration
    def test_complete_registration_login_flow(
        self, base_url: str, test_credentials: Dict[str, str]
    ):
        """
        黑盒测试：完整注册和登录流程
        用户视角：
        1. 注册新账户
        2. 使用新账户登录
        3. 验证获取的token有效
        """
        client = httpx.Client(base_url=base_url, timeout=30.0, follow_redirects=True)

        register_response = client.post(
            "/api/v1/auth/register",
            json=test_credentials
        )
        assert register_response.status_code == 200, \
            f"注册失败: {register_response.text}"

        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_credentials["username"],
                "password": test_credentials["password"]
            }
        )
        assert login_response.status_code == 200, \
            f"登录失败: {login_response.text}"

        token = login_response.json()["access_token"]
        assert token is not None

        me_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_response.status_code == 200
        assert me_response.json()["username"] == test_credentials["username"]

    @pytest.mark.integration
    def test_invalid_login_rejected(self, base_url: str):
        """
        黑盒测试：无效登录被拒绝
        验证错误的凭据会被正确拒绝
        """
        client = httpx.Client(base_url=base_url, timeout=30.0, follow_redirects=True)

        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent_user",
                "password": "wrong_password"
            }
        )
        assert response.status_code == 401

    @pytest.mark.integration
    def test_unauthorized_access_blocked(self, base_url: str):
        """
        黑盒测试：未授权访问被阻止
        验证没有token无法访问受保护资源
        """
        client = httpx.Client(base_url=base_url, timeout=30.0, follow_redirects=True)

        protected_resources = [
            "/api/v1/data-sources/",
            "/api/v1/rules/",
            "/api/v1/tasks/",
        ]

        for resource in protected_resources:
            response = client.get(resource)
            assert response.status_code == 401, \
                f"资源 {resource} 应该需要认证"


class TestBusinessWorkflows:
    """
    黑盒测试：业务工作流
    从最终用户角度测试完整的业务场景
    """

    @pytest.fixture
    def base_url(self) -> str:
        import os
        return os.getenv("TEST_API_BASE_URL", "http://localhost:8000")

    @pytest.fixture
    def authenticated_client(self, base_url: str) -> tuple:
        """创建已认证的客户端"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]

        client = httpx.Client(base_url=base_url, timeout=30.0)

        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "username": f"workflow_user_{unique_id}",
                "email": f"workflow_{unique_id}@test.com",
                "password": "Workflow123!"
            }
        )
        assert register_response.status_code == 200

        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": f"workflow_user_{unique_id}",
                "password": "Workflow123!"
            }
        )
        assert login_response.status_code == 200

        token = login_response.json()["access_token"]
        auth_client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
            follow_redirects=True
        )

        return auth_client, unique_id

    @pytest.mark.integration
    def test_data_source_management_workflow(self, authenticated_client: tuple):
        """
        黑盒测试：数据源管理工作流
        用户场景：
        1. 创建数据源
        2. 查看数据源列表
        3. 更新数据源
        4. 删除数据源
        """
        client, _ = authenticated_client

        create_response = client.post(
            "/api/v1/data-sources/",
            json={
                "name": "工作流测试数据源",
                "website_url": "https://workflow-test.com",
                "login_type": "password",
                "data_format": "excel"
            }
        )
        assert create_response.status_code == 200
        data_source_id = create_response.json()["id"]

        list_response = client.get("/api/v1/data-sources/")
        assert list_response.status_code == 200
        assert len(list_response.json()) > 0

        update_response = client.put(
            f"/api/v1/data-sources/{data_source_id}/",
            json={"name": "更新的工作流测试数据源"}
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "更新的工作流测试数据源"

        delete_response = client.delete(
            f"/api/v1/data-sources/{data_source_id}/"
        )
        assert delete_response.status_code == 200

    @pytest.mark.integration
    def test_rule_management_workflow(self, authenticated_client: tuple):
        """
        黑盒测试：规则管理工作流
        用户场景：
        1. 创建筛选规则
        2. 查看规则列表
        3. 验证规则
        4. 删除规则
        """
        client, _ = authenticated_client

        create_response = client.post(
            "/api/v1/rules/",
            json={
                "name": "工作流测试规则",
                "description": "筛选PE<20的股票",
                "natural_language": "筛选PE小于20的股票",
                "filter_conditions": [
                    {"column": "PE", "operator": "less_than", "value": 20}
                ],
                "priority": 1
            }
        )
        assert create_response.status_code == 200
        rule_id = create_response.json()["id"]

        list_response = client.get("/api/v1/rules/")
        assert list_response.status_code == 200
        assert len(list_response.json()) > 0

        delete_response = client.delete(f"/api/v1/rules/{rule_id}/")
        assert delete_response.status_code == 200

    @pytest.mark.integration
    def test_task_lifecycle_workflow(self, authenticated_client: tuple):
        """
        黑盒测试：任务生命周期工作流
        用户场景：
        1. 创建数据源和规则
        2. 创建任务
        3. 手动执行任务
        4. 查看任务状态
        5. 删除任务
        """
        client, _ = authenticated_client

        ds_response = client.post(
            "/api/v1/data-sources/",
            json={
                "name": "任务测试数据源",
                "website_url": "https://task-test.com",
                "login_type": "password",
                "data_format": "excel"
            }
        )
        assert ds_response.status_code == 200
        data_source_id = ds_response.json()["id"]

        rule_response = client.post(
            "/api/v1/rules/",
            json={
                "name": "任务测试规则",
                "description": "测试规则",
                "natural_language": "筛选PE小于20",
                "filter_conditions": [
                    {"column": "PE", "operator": "less_than", "value": 20}
                ]
            }
        )
        assert rule_response.status_code == 200
        rule_id = rule_response.json()["id"]

        task_response = client.post(
            "/api/v1/tasks/",
            json={
                "name": "工作流测试任务",
                "data_source_ids": [data_source_id],
                "rule_ids": [rule_id],
                "schedule_type": "manual"
            }
        )
        assert task_response.status_code == 200
        task_id = task_response.json()["id"]

        run_response = client.post(f"/api/v1/tasks/{task_id}/run/")
        assert run_response.status_code == 200

        delete_response = client.delete(f"/api/v1/tasks/{task_id}/")
        assert delete_response.status_code == 200


class TestErrorHandling:
    """
    黑盒测试：错误处理
    验证API对错误输入的处理
    """

    @pytest.fixture
    def base_url(self) -> str:
        import os
        return os.getenv("TEST_API_BASE_URL", "http://localhost:8000")

    @pytest.mark.integration
    def test_invalid_json_rejected(self, base_url: str):
        """黑盒测试：无效JSON被拒绝"""
        client = httpx.Client(base_url=base_url, timeout=30.0)

        response = client.post(
            "/api/v1/auth/register",
            content=b"not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    @pytest.mark.integration
    def test_missing_required_fields_rejected(self, base_url: str):
        """黑盒测试：缺少必需字段被拒绝"""
        client = httpx.Client(base_url=base_url, timeout=30.0)

        response = client.post(
            "/api/v1/auth/register",
            json={"username": "test"}  # 缺少email和password
        )
        assert response.status_code == 422

    @pytest.mark.integration
    def test_invalid_email_format_rejected(self, base_url: str):
        """黑盒测试：无效邮箱格式被拒绝"""
        client = httpx.Client(base_url=base_url, timeout=30.0)

        import uuid
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": f"user_{uuid.uuid4().hex[:8]}",
                "email": "not_an_email",
                "password": "password123"
            }
        )
        assert response.status_code == 422

    @pytest.mark.integration
    def test_nonexistent_resource_returns_404(self, base_url: str):
        """黑盒测试：不存在资源返回404（需认证）"""
        client = httpx.Client(base_url=base_url, timeout=30.0, follow_redirects=True)

        response = client.get("/api/v1/data-sources/99999/")
        assert response.status_code == 401  # 未认证先返回401
