"""Tests for rate_limiter key_prefix parameter."""
import pytest
from unittest.mock import AsyncMock, patch
import importlib


@pytest.mark.asyncio
async def test_is_rate_limited_uses_custom_prefix():
    import services.rate_limiter as rl
    with patch.object(rl, "redis_client") as mock_redis:
        mock_redis.get = AsyncMock(return_value=None)
        await rl.is_rate_limited("testuser", key_prefix="admin_fail")
        mock_redis.get.assert_called_once_with("admin_fail:testuser")


@pytest.mark.asyncio
async def test_record_failed_attempt_uses_custom_prefix():
    import services.rate_limiter as rl
    with patch.object(rl, "redis_client") as mock_redis:
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()
        await rl.record_failed_attempt("testuser", key_prefix="admin_fail")
        mock_redis.incr.assert_called_once_with("admin_fail:testuser")


@pytest.mark.asyncio
async def test_reset_attempts_uses_custom_prefix():
    import services.rate_limiter as rl
    with patch.object(rl, "redis_client") as mock_redis:
        mock_redis.delete = AsyncMock()
        await rl.reset_attempts("testuser", key_prefix="admin_fail")
        mock_redis.delete.assert_called_once_with("admin_fail:testuser")


@pytest.mark.asyncio
async def test_default_prefix_unchanged():
    """Existing callers (Authentication.py) must still work without key_prefix."""
    import services.rate_limiter as rl
    with patch.object(rl, "redis_client") as mock_redis:
        mock_redis.get = AsyncMock(return_value=None)
        await rl.is_rate_limited("testuser")
        mock_redis.get.assert_called_once_with("auth_fail:testuser")
