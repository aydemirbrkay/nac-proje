"""Tests for JWT login endpoint and get_current_admin dependency."""
import bcrypt
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from database import get_db


def _make_db_with_results(*scalar_results):
    """Helper: build an AsyncMock db that returns scalar_results in order."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    side_effects = []
    for val in scalar_results:
        r = MagicMock()
        r.scalar_one_or_none.return_value = val
        side_effects.append(r)
    mock_db.execute.side_effect = side_effects
    return mock_db


def _make_app(mock_db):
    from routes.auth_admin import router

    async def override_db():
        yield mock_db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_db
    return app


@pytest.mark.asyncio
async def test_login_returns_token_for_valid_admin():
    real_hash = bcrypt.hashpw(b"adminpass123", bcrypt.gensalt(rounds=4)).decode()

    mock_radcheck = MagicMock()
    mock_radcheck.value = real_hash

    mock_group = MagicMock()
    mock_group.groupname = "admin"

    mock_db = _make_db_with_results(mock_radcheck, mock_group)
    app = _make_app(mock_db)

    with patch("routes.auth_admin.is_rate_limited", AsyncMock(return_value=False)), \
         patch("routes.auth_admin.reset_attempts", AsyncMock()):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/admin/login",
                json={"username": "admin_ali", "password": "adminpass123"},
            )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 28800


@pytest.mark.asyncio
async def test_login_rejects_non_admin():
    real_hash = bcrypt.hashpw(b"pass12345", bcrypt.gensalt(rounds=4)).decode()
    mock_radcheck = MagicMock()
    mock_radcheck.value = real_hash

    mock_db = _make_db_with_results(mock_radcheck, None)
    app = _make_app(mock_db)

    with patch("routes.auth_admin.is_rate_limited", AsyncMock(return_value=False)), \
         patch("routes.auth_admin.record_failed_attempt", AsyncMock(return_value=1)):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/admin/login",
                json={"username": "emp_mehmet", "password": "pass12345"},
            )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_login_rejects_wrong_password():
    real_hash = bcrypt.hashpw(b"correctpass", bcrypt.gensalt(rounds=4)).decode()
    mock_radcheck = MagicMock()
    mock_radcheck.value = real_hash

    mock_db = _make_db_with_results(mock_radcheck)
    app = _make_app(mock_db)

    with patch("routes.auth_admin.is_rate_limited", AsyncMock(return_value=False)), \
         patch("routes.auth_admin.record_failed_attempt", AsyncMock(return_value=1)):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/admin/login",
                json={"username": "admin_ali", "password": "wrongpass"},
            )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limited():
    mock_db = _make_db_with_results()
    app = _make_app(mock_db)

    with patch("routes.auth_admin.is_rate_limited", AsyncMock(return_value=True)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/admin/login",
                json={"username": "admin_ali", "password": "any"},
            )

    assert response.status_code == 429
