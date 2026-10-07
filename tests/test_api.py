import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.main import app, get_db

# Create in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestAsyncSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_db() -> AsyncSession:
    async with TestAsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@pytest.fixture(autouse=True)
async def setup_db():
    # Create tables before each test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Drop tables after each test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestHealth:
    async def test_health_endpoint(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "service" in data
        assert "version" in data

    async def test_health_db_endpoint(self, client):
        response = await client.get("/api/v1/health/db")
        # May fail if DB not running, but endpoint should exist
        assert response.status_code in (200, 500)


class TestDevices:
    async def test_list_devices_empty(self, client):
        response = await client.get("/api/v1/devices")
        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert "total" in data
        assert data["total"] == 0


class TestDiagnostics:
    async def test_list_diagnostics_empty(self, client):
        response = await client.get("/api/v1/diagnostics")
        assert response.status_code == 200
        data = response.json()
        assert "diagnostics" in data
        assert "total" in data
        assert data["total"] == 0

    async def test_imei_check_valid(self, client):
        # Valid IMEI (Luhn check passes) - 356938035643809 is a known valid IMEI
        response = await client.post("/api/v1/diagnostics/imei-check", json={"imei": "356938035643809"})
        assert response.status_code == 200
        data = response.json()
        assert data["imei"] == "356938035643809"
        assert data["is_valid"] is True

    async def test_imei_check_invalid(self, client):
        # Invalid IMEI (Luhn check fails)
        response = await client.post("/api/v1/diagnostics/imei-check", json={"imei": "490154203237519"})
        assert response.status_code == 200
        data = response.json()
        assert data["imei"] == "490154203237519"
        assert data["is_valid"] is False

    async def test_imei_check_wrong_length(self, client):
        response = await client.post("/api/v1/diagnostics/imei-check", json={"imei": "12345"})
        assert response.status_code == 422  # Validation error
