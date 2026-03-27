"""Tests for new user management schemas."""
import pytest
from pydantic import ValidationError


def test_user_create_rejects_short_password():
    from schemas import UserCreate
    with pytest.raises(ValidationError):
        UserCreate(username="ali", password="short", group="employee")


def test_user_create_rejects_invalid_group():
    from schemas import UserCreate
    with pytest.raises(ValidationError):
        UserCreate(username="ali", password="password123", group="iot_devices")


def test_user_create_valid():
    from schemas import UserCreate
    u = UserCreate(username="ali", password="password123", group="employee")
    assert u.username == "ali"
    assert u.group == "employee"


def test_password_change_rejects_short():
    from schemas import PasswordChange
    with pytest.raises(ValidationError):
        PasswordChange(new_password="abc")


def test_token_response_defaults():
    from schemas import TokenResponse
    t = TokenResponse(access_token="tok")
    assert t.token_type == "bearer"
    assert t.expires_in == 28800
