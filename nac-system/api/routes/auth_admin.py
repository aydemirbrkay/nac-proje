"""
Admin authentication — JWT token üretimi ve doğrulaması.

POST /admin/login → admin grubundaki kullanıcılar JWT token alır.
get_current_admin → JWT korumalı endpoint'lerde kullanılan bağımlılık.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models import RadCheck, RadUserGroup
from schemas import AdminLoginRequest, TokenResponse
from services.rate_limiter import is_rate_limited, record_failed_attempt, reset_attempts

logger = logging.getLogger(__name__)
router = APIRouter()
bearer_scheme = HTTPBearer()

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 8
RATE_LIMIT_PREFIX = "admin_fail"


def _create_token(username: str) -> str:
    """HS256 JWT token üretir."""
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": username, "group": "admin", "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


@router.post("/admin/login", response_model=TokenResponse)
async def admin_login(
    request: AdminLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Admin kullanıcısı için JWT token üretir."""
    username = request.username

    if await is_rate_limited(username, key_prefix=RATE_LIMIT_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Çok fazla başarısız deneme. Lütfen bekleyin.",
        )

    stmt = select(RadCheck).where(
        RadCheck.username == username,
        RadCheck.attribute == "Hashed-Password",
    )
    result = await db.execute(stmt)
    radcheck = result.scalar_one_or_none()

    password_invalid = radcheck is None or not await asyncio.to_thread(
        bcrypt.checkpw,
        request.password.encode(),
        radcheck.value.encode(),
    )
    if password_invalid:
        await record_failed_attempt(username, key_prefix=RATE_LIMIT_PREFIX)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı adı veya şifre hatalı.",
        )

    stmt = select(RadUserGroup).where(
        RadUserGroup.username == username,
        RadUserGroup.groupname == "admin",
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        await record_failed_attempt(username, key_prefix=RATE_LIMIT_PREFIX)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu endpoint sadece admin kullanıcılara açıktır.",
        )

    await reset_attempts(username, key_prefix=RATE_LIMIT_PREFIX)
    token = _create_token(username)
    logger.info(f"Admin login: {username}")
    return TokenResponse(access_token=token)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """JWT doğrulama bağımlılığı. Korumalı endpoint'lerde Depends(get_current_admin) ile kullanılır."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        username: str = payload.get("sub")
        if username is None or payload.get("group") != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Geçersiz veya süresi dolmuş token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return username
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya süresi dolmuş token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
