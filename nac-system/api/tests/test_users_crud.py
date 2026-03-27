"""Tests for user CRUD endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from database import get_db


def _make_db(*scalar_results):
    """Build a mock db whose execute() returns scalar_results in sequence.
    Non-SELECT calls (UPDATE, DELETE) use MagicMock with no scalar configured."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    side_effects = []
    for val in scalar_results:
        if val == "_no_scalar":
            side_effects.append(MagicMock())
        else:
            r = MagicMock()
            r.scalar_one_or_none.return_value = val
            side_effects.append(r)
    mock_db.execute.side_effect = side_effects
    return mock_db


def _make_app(mock_db):
    from routes import users
    from routes.auth_admin import get_current_admin

    async def override_db():
        yield mock_db

    app = FastAPI()
    app.include_router(users.router)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_admin] = lambda: "admin_ali"
    return app


@pytest.mark.asyncio
async def test_create_user_success():
    mock_group = MagicMock()
    mock_group.groupname = "employee"
    mock_vlan = MagicMock()
    mock_vlan.value = "20"
    mock_db = _make_db(None, mock_group, mock_vlan)
    app = _make_app(mock_db)

    with patch("routes.users.redis_client") as mock_redis:
        mock_redis.scard = AsyncMock(return_value=0)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/users",
                json={"username": "new_emp", "password": "password123", "group": "employee"},
            )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "new_emp"
    assert data["group"] == "employee"
    assert data["vlan_id"] == "20"


@pytest.mark.asyncio
async def test_create_user_conflict():
    existing = MagicMock()
    mock_db = _make_db(existing)
    app = _make_app(mock_db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/users",
            json={"username": "existing_user", "password": "password123", "group": "employee"},
        )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_get_user_detail_success():
    mock_group = MagicMock()
    mock_group.groupname = "admin"
    mock_vlan = MagicMock()
    mock_vlan.value = "10"
    existing_radcheck = MagicMock()
    mock_db = _make_db(existing_radcheck, mock_group, mock_vlan)
    app = _make_app(mock_db)

    with patch("routes.users.redis_client") as mock_redis:
        mock_redis.scard = AsyncMock(return_value=1)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/users/admin_ali")

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin_ali"
    assert data["group"] == "admin"
    assert data["vlan_id"] == "10"
    assert data["is_online"] is True


@pytest.mark.asyncio
async def test_get_user_not_found():
    mock_db = _make_db(None)
    app = _make_app(mock_db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/users/nonexistent")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_group_success():
    existing_group = MagicMock()
    existing_group.groupname = "employee"
    updated_group = MagicMock()
    updated_group.groupname = "guest"
    mock_vlan = MagicMock()
    mock_vlan.value = "30"

    # 1=SELECT radusergroup (exists), 2=UPDATE radusergroup, 3=DELETE radreply,
    # 4=SELECT radusergroup (_get_user_detail), 5=SELECT radgroupreply (_get_user_detail)
    mock_db = _make_db(existing_group, "_no_scalar", "_no_scalar", updated_group, mock_vlan)
    app = _make_app(mock_db)

    with patch("routes.users.redis_client") as mock_redis:
        mock_redis.scard = AsyncMock(return_value=0)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put("/users/emp_mehmet", json={"group": "guest"})

    assert response.status_code == 200
    assert response.json()["group"] == "guest"
    assert response.json()["vlan_id"] == "30"


@pytest.mark.asyncio
async def test_update_group_user_not_found():
    mock_db = _make_db(None)
    app = _make_app(mock_db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put("/users/nonexistent", json={"group": "guest"})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_user_success():
    existing = MagicMock()
    # 1=SELECT radcheck (exists), 2=DELETE radcheck, 3=DELETE radusergroup, 4=DELETE radreply
    mock_db = _make_db(existing, "_no_scalar", "_no_scalar", "_no_scalar")
    app = _make_app(mock_db)

    with patch("routes.users.redis_client") as mock_redis:
        mock_redis.smembers = AsyncMock(return_value={"sess-1", "sess-2"})
        mock_redis.delete = AsyncMock()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/users/emp_mehmet")

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_user_not_found():
    mock_db = _make_db(None)
    app = _make_app(mock_db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete("/users/nonexistent")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_change_password_success():
    existing = MagicMock()
    # 1=SELECT radcheck (exists), 2=UPDATE radcheck
    mock_db = _make_db(existing, "_no_scalar")
    app = _make_app(mock_db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(
            "/users/emp_mehmet/password",
            json={"new_password": "newpassword123"},
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_users_requires_jwt():
    """GET /users rejects requests without a valid JWT token."""
    from routes import users

    app = FastAPI()
    app.include_router(users.router)
    # No dependency_overrides — real JWT check applies

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/users")

    assert response.status_code in (401, 403)
