"""Shared test fixtures."""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock

# Set required env vars before any service modules are imported.
# config.Settings() runs at import time and requires these three variables.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/testdb")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")


@pytest.fixture
def mock_db():
    """Async SQLAlchemy session mock."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def mock_redis_client():
    """Mock redis_client."""
    mock = MagicMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock()
    mock.delete = AsyncMock()
    mock.incr = AsyncMock(return_value=1)
    mock.expire = AsyncMock()
    mock.scard = AsyncMock(return_value=0)
    mock.smembers = AsyncMock(return_value=set())
    return mock
