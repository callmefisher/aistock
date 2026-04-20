"""空库 seed 行为测试。

覆盖场景：
- 空库：创建 admin/admin123 superuser
- 非空库（已有 admin，密码不是 admin123）：不动（模拟导入备份后的情形）
- 非空库（有普通用户）：不创建 admin
- 幂等：对已 seed 过的库再次调用返回 False，不重复插入
- 密码哈希可被 /login 的 verify_password 校验通过
"""
import pytest
from sqlalchemy import select

from main import seed_default_admin_if_empty
from models.models import User
from api.auth import get_password_hash, verify_password


@pytest.mark.asyncio
async def test_seed_on_empty_db_creates_admin(db_session):
    created = await seed_default_admin_if_empty(db_session)
    assert created is True

    result = await db_session.execute(select(User).where(User.username == "admin"))
    admin = result.scalar_one()
    assert admin.email == "admin@example.com"
    assert admin.is_active is True
    assert admin.is_superuser is True
    assert verify_password("admin123", admin.hashed_password)


@pytest.mark.asyncio
async def test_seed_skipped_when_admin_exists_with_other_password(db_session):
    """导入备份后 admin 行已存在、密码未知 —— seed 必须不覆盖。"""
    db_session.add(User(
        username="admin",
        email="admin@imported.com",
        hashed_password=get_password_hash("somethingelse"),
        is_active=True,
        is_superuser=True,
    ))
    await db_session.commit()

    created = await seed_default_admin_if_empty(db_session)
    assert created is False

    result = await db_session.execute(select(User).where(User.username == "admin"))
    admin = result.scalar_one()
    assert admin.email == "admin@imported.com"
    assert not verify_password("admin123", admin.hashed_password)
    assert verify_password("somethingelse", admin.hashed_password)


@pytest.mark.asyncio
async def test_seed_skipped_when_only_non_admin_user_exists(db_session):
    """库里只有普通用户也算非空，不应创建 admin。"""
    db_session.add(User(
        username="alice",
        email="alice@example.com",
        hashed_password=get_password_hash("alicepass"),
        is_active=True,
        is_superuser=False,
    ))
    await db_session.commit()

    created = await seed_default_admin_if_empty(db_session)
    assert created is False

    count = (await db_session.execute(
        select(User).where(User.username == "admin")
    )).scalar_one_or_none()
    assert count is None


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session):
    first = await seed_default_admin_if_empty(db_session)
    second = await seed_default_admin_if_empty(db_session)
    assert first is True
    assert second is False

    result = await db_session.execute(select(User).where(User.username == "admin"))
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_seed_and_login_end_to_end(db_session, client):
    created = await seed_default_admin_if_empty(db_session)
    assert created is True

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
