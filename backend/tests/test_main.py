import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from main import app
from core.database import Base, get_async_db

SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

async_engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=True
)

AsyncTestingSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def override_get_async_db():
    async with AsyncTestingSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_async_db] = override_get_async_db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
async def async_session():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncTestingSessionLocal() as session:
        yield session
    
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
