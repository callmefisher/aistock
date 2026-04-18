import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import LargeBinary
from httpx import AsyncClient, ASGITransport
from typing import AsyncGenerator

from main import app
from core.database import Base, get_async_db
from api.auth import get_password_hash, create_access_token
from models.models import User, DataSource, Rule, Task

# SQLite does not support MySQL-specific LONGBLOB type.
# Patch the WorkflowResult.data_compressed column to use LargeBinary before creating tables.
try:
    from models.models import WorkflowResult
    WorkflowResult.data_compressed.property.columns[0].type = LargeBinary()
except Exception:
    pass


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """数据库会话fixture - 每个测试使用独立数据库"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestAsyncSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP客户端fixture"""
    async def override_get_async_db():
        yield db_session

    app.dependency_overrides[get_async_db] = override_get_async_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """测试用户fixture"""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpass123"),
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def auth_headers(test_user: User) -> dict:
    """认证头fixture"""
    token = create_access_token(data={"sub": test_user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def superuser(db_session: AsyncSession) -> User:
    """超级用户fixture"""
    user = User(
        username="superuser",
        email="super@example.com",
        hashed_password=get_password_hash("superpass123"),
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def superuser_auth_headers(superuser: User) -> dict:
    """超级用户认证头fixture"""
    token = create_access_token(data={"sub": superuser.username})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def test_data_source(db_session: AsyncSession, test_user: User) -> DataSource:
    """测试数据源fixture"""
    data_source = DataSource(
        name="测试数据源",
        website_url="https://example.com",
        login_type="password",
        login_config={"username": "user", "password": "pass"},
        data_format="excel",
        extraction_config={"sheet_name": "Sheet1"},
        is_active=True,
    )
    db_session.add(data_source)
    await db_session.commit()
    await db_session.refresh(data_source)
    return data_source


@pytest_asyncio.fixture(scope="function")
async def test_rule(db_session: AsyncSession) -> Rule:
    """测试规则fixture"""
    rule = Rule(
        name="测试规则",
        description="筛选PE<20的股票",
        natural_language="筛选PE小于20的股票",
        excel_formula="IF(PE<20,TRUE,FALSE)",
        filter_conditions=[
            {"column": "PE", "operator": "less_than", "value": 20}
        ],
        priority=1,
        is_active=True,
    )
    db_session.add(rule)
    await db_session.commit()
    await db_session.refresh(rule)
    return rule


@pytest_asyncio.fixture(scope="function")
async def test_task(db_session: AsyncSession, test_data_source: DataSource, test_rule: Rule) -> Task:
    """测试任务fixture"""
    task = Task(
        name="测试任务",
        data_source_ids=[test_data_source.id],
        rule_ids=[test_rule.id],
        schedule_type="manual",
        schedule_config={},
        status="pending",
        is_active=True,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task
