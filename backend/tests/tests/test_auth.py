import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import verify_password, get_password_hash, create_access_token
from models.models import User


class TestAuthAPI:
    """认证API集成测试"""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """测试成功注册"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "newpass123"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert data["is_active"] is True
        assert data["is_superuser"] is False

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient, test_user: User):
        """测试重复用户名注册失败"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": test_user.username,
                "email": "different@example.com",
                "password": "pass123"
            }
        )
        assert response.status_code == 400
        assert "用户名已存在" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_user: User):
        """测试重复邮箱注册失败"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "differentuser",
                "email": test_user.email,
                "password": "pass123"
            }
        )
        assert response.status_code == 400
        assert "邮箱已存在" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user: User):
        """测试成功登录"""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.username,
                "password": "testpass123"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        """测试密码错误登录失败"""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.username,
                "password": "wrongpassword"
            }
        )
        assert response.status_code == 401
        assert "用户名或密码错误" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """测试用户不存在登录失败"""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent",
                "password": "somepass"
            }
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """测试获取当前用户信息"""
        response = await client.get(
            "/api/v1/auth/me",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user.username
        assert data["email"] == test_user.email

    @pytest.mark.asyncio
    async def test_get_current_user_no_token(self, client: AsyncClient):
        """测试无token访问被拒绝"""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """测试无效token访问被拒绝"""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401


class TestPasswordUtils:
    """密码工具函数单元测试"""

    def test_password_hash_and_verify(self):
        """测试密码哈希和验证"""
        password = "testpassword123"
        hashed = get_password_hash(password)

        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("wrongpassword", hashed) is False

    def test_create_access_token(self):
        """测试创建访问令牌"""
        token = create_access_token(data={"sub": "testuser"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_password_hash_different_for_same_password(self):
        """测试同一密码生成不同的哈希"""
        password = "samepassword"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        assert hash1 != hash2
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True
