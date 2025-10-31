from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from app.db.database import Base, get_keycloak_db
from app.db.redis import get_redis
from app.main import app
from app.services.keycloak_service import keycloak_service
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Test database URL - using in-memory SQLite for tests
TEST_KEYCLOAK_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# Create test engine
test_engine = create_async_engine(
    TEST_KEYCLOAK_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)

# Create test session maker
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session
        await session.rollback()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing"""
    mock_redis = AsyncMock()
    mock_redis.set_session = AsyncMock()
    mock_redis.get_session = AsyncMock(return_value=None)
    mock_redis.delete_session = AsyncMock()
    mock_redis.set_cache = AsyncMock()
    mock_redis.get_cache = AsyncMock(return_value=None)
    return mock_redis


@pytest.fixture
def mock_keycloak():
    """Mock Keycloak service for testing"""
    mock_service = MagicMock()
    mock_service.authenticate_user = AsyncMock()
    mock_service.create_user = AsyncMock()
    mock_service.refresh_token = AsyncMock()
    mock_service.logout_user = AsyncMock()
    mock_service.get_user_by_id = AsyncMock()
    mock_service.update_user = AsyncMock()
    return mock_service


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession, mock_redis, mock_keycloak
) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with mocked dependencies"""

    def override_get_keycloak_db():
        return db_session

    def override_get_redis():
        return mock_redis

    app.dependency_overrides[get_keycloak_db] = override_get_keycloak_db
    app.dependency_overrides[get_redis] = override_get_redis

    # Mock keycloak service
    app.dependency_overrides[keycloak_service] = lambda: mock_keycloak

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        "username": "testuser",
        "email": "test@hospital.com",
        "password": "SecurePassword123!",
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture
def sample_login_data():
    """Sample login data for testing"""
    return {"username": "testuser", "password": "SecurePassword123!"}


@pytest.fixture
def mock_jwt_token():
    """Mock JWT token for testing"""
    return {
        "access_token": "mock.jwt.token",
        "refresh_token": "mock.refresh.token",
        "expires_in": 1800,
        "userinfo": {
            "sub": "mock-keycloak-id",
            "preferred_username": "testuser",
            "email": "test@hospital.com",
            "given_name": "Test",
            "family_name": "User",
            "email_verified": True,
            "realm_access": {"roles": ["clinician"]},
        },
    }
