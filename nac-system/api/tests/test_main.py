"""Smoke test: verify auth_admin router is registered and /admin/login is reachable."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_admin_login_route_registered():
    """POST /admin/login must return 401/429/403, not 404."""
    from main import app
    from database import get_db

    mock_db = AsyncMock()
    r = MagicMock()
    r.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = r

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db

    with patch("routes.auth_admin.is_rate_limited", AsyncMock(return_value=False)), \
         patch("routes.auth_admin.record_failed_attempt", AsyncMock(return_value=1)):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/admin/login",
                json={"username": "admin_ali", "password": "wrong"},
            )

    app.dependency_overrides.clear()

    assert response.status_code != 404, "Route /admin/login not registered in main.py"
    assert response.status_code == 401
