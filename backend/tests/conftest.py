import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import LargeBinary
from httpx import AsyncClient, ASGITransport
from typing import AsyncGenerator
import sys
import importlib

from main import app
from core.database import Base, get_async_db
from api.auth import get_password_hash, create_access_token
from models.models import User, DataSource, Rule, Task, Workflow


# ---- 收集期跳过：依赖 Py3.8+ AsyncMock / 第三方 fakeredis / PEP585 类型语法 的测试文件
_PY38_PLUS = sys.version_info >= (3, 8)
_HAS_FAKEREDIS = importlib.util.find_spec("fakeredis") is not None

# (文件名, 跳过条件 lambda) — 条件返回 True 时跳过
_COLLECT_SKIP_FILES = {
    "test_condition_intersection_pledge.py": not _PY38_PLUS,   # AsyncMock 需 3.8+
    "test_db_writer.py":                      not _PY38_PLUS,
    "test_export_high_price_trend_step.py":   not _PY38_PLUS,
    "test_retention_service.py":              not _PY38_PLUS,
    "test_pledge_cache_cleanup.py":           not _HAS_FAKEREDIS,
    "test_pledge_data_source.py":             not _HAS_FAKEREDIS,
    "test_pledge_side_by_side_upload.py":     not _PY38_PLUS,  # PEP585 list[X]
}


def collect_ignore_glob():
    """供 pytest 自动调用：返回需要忽略的 glob 模式列表。"""
    return [name for name, skip in _COLLECT_SKIP_FILES.items() if skip]


# pytest 支持 module-level variable 形式（collect_ignore_glob 是 list）
collect_ignore_glob = collect_ignore_glob()

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


@pytest_asyncio.fixture(scope="function")
async def test_workflow(db_session: AsyncSession, tmp_path_factory) -> Workflow:
    """测试工作流 fixture（用于 test_workflows API 集成测试）。
    步骤 0 的 import_excel 指向一个真实存在的空白 xlsx，避免执行步骤测试 400。"""
    import pandas as pd
    tmp_dir = tmp_path_factory.mktemp("workflow_fixture")
    sample = tmp_dir / "sample.xlsx"
    pd.DataFrame({"证券代码": ["000001.SZ"], "证券简称": ["平安银行"]}).to_excel(sample, index=False)

    wf = Workflow(
        name="测试工作流",
        description="测试描述",
        workflow_type="",
        date_str="",
        steps=[
            {"type": "import_excel", "config": {"file_path": str(sample)}, "status": "pending"},
            {"type": "dedup", "config": {}, "status": "pending"},
        ],
        status="active",
    )
    db_session.add(wf)
    await db_session.commit()
    await db_session.refresh(wf)
    return wf
