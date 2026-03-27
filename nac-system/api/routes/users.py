"""
Users endpoint — kullanıcı yönetimi (CRUD) ve listeleme.
Tüm endpoint'ler JWT korumalıdır (get_current_admin bağımlılığı).
"""
import asyncio
import logging

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete, update, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import RadCheck, RadUserGroup, RadGroupReply, RadReply
from routes.auth_admin import get_current_admin
from schemas import UserInfo, UserCreate, UserUpdate, PasswordChange, UserDetail
from services.redis_service import redis_client

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_user_detail(username: str, db: AsyncSession) -> UserDetail:
    """Kullanıcının grup, VLAN ve online bilgisini derler."""
    stmt = select(RadUserGroup).where(RadUserGroup.username == username).order_by(RadUserGroup.priority)
    result = await db.execute(stmt)
    user_group = result.scalar_one_or_none()
    group = user_group.groupname if user_group else None

    vlan_id = None
    if group:
        stmt = select(RadGroupReply).where(
            RadGroupReply.groupname == group,
            RadGroupReply.attribute == "Tunnel-Private-Group-Id",
        )
        result = await db.execute(stmt)
        vlan_reply = result.scalar_one_or_none()
        vlan_id = vlan_reply.value if vlan_reply else None

    active_count = await redis_client.scard(f"user_sessions:{username}")
    return UserDetail(username=username, group=group, vlan_id=vlan_id, is_online=active_count > 0)


@router.get("/users", response_model=list[UserInfo])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    """Tüm kayıtlı kullanıcıları listeler."""
    stmt = select(distinct(RadCheck.username))
    result = await db.execute(stmt)
    usernames = [row[0] for row in result.all()]

    users = []
    for username in usernames:
        detail = await _get_user_detail(username, db)
        users.append(UserInfo(
            username=detail.username,
            group=detail.group,
            is_online=detail.is_online,
            vlan_id=detail.vlan_id,
        ))

    logger.info(f"Kullanıcı listesi döndürüldü: {len(users)} kullanıcı")
    return users


@router.post("/users", response_model=UserDetail, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    """Yeni kullanıcı oluşturur."""
    stmt = select(RadCheck).where(RadCheck.username == body.username)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Kullanıcı zaten mevcut.")

    hashed = await asyncio.to_thread(
        bcrypt.hashpw, body.password.encode(), bcrypt.gensalt(rounds=12)
    )
    db.add(RadCheck(username=body.username, attribute="Hashed-Password", op=":=", value=hashed.decode()))
    db.add(RadUserGroup(username=body.username, groupname=body.group, priority=1))
    await db.flush()

    logger.info(f"Kullanıcı oluşturuldu: {body.username} → {body.group}")
    return await _get_user_detail(body.username, db)


@router.get("/users/{username}", response_model=UserDetail)
async def get_user(
    username: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    """Tek kullanıcı detayı döner."""
    stmt = select(RadCheck).where(RadCheck.username == username)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı bulunamadı.")
    return await _get_user_detail(username, db)


@router.put("/users/{username}", response_model=UserDetail)
async def update_user_group(
    username: str,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    """Kullanıcının grubunu günceller. Çakışan radreply kayıtlarını temizler."""
    stmt = select(RadCheck).where(RadCheck.username == username)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı bulunamadı.")

    await db.execute(
        update(RadUserGroup).where(RadUserGroup.username == username).values(groupname=body.group)
    )
    await db.execute(delete(RadReply).where(RadReply.username == username))

    logger.info(f"Grup güncellendi: {username} → {body.group}")
    return await _get_user_detail(username, db)


@router.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    username: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    """Kullanıcıyı siler. Redis oturum verisini temizler.

    Not: Aktif RADIUS oturumu varsa switch CoA/Disconnect alınmaz —
    kullanıcı mevcut oturumu doğal bitimine kadar ağa erişmeye devam eder.
    """
    stmt = select(RadCheck).where(RadCheck.username == username)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı bulunamadı.")

    await db.execute(delete(RadCheck).where(RadCheck.username == username))
    await db.execute(delete(RadUserGroup).where(RadUserGroup.username == username))
    await db.execute(delete(RadReply).where(RadReply.username == username))

    session_ids = await redis_client.smembers(f"user_sessions:{username}")
    for sid in session_ids:
        await redis_client.delete(f"session:{sid}")
    await redis_client.delete(f"user_sessions:{username}")

    logger.info(f"Kullanıcı silindi: {username}")


@router.put("/users/{username}/password")
async def change_password(
    username: str,
    body: PasswordChange,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    """Kullanıcının şifresini değiştirir."""
    stmt = select(RadCheck).where(
        RadCheck.username == username,
        RadCheck.attribute == "Hashed-Password",
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı bulunamadı.")

    hashed = await asyncio.to_thread(
        bcrypt.hashpw, body.new_password.encode(), bcrypt.gensalt(rounds=12)
    )
    await db.execute(
        update(RadCheck)
        .where(RadCheck.username == username, RadCheck.attribute == "Hashed-Password")
        .values(value=hashed.decode())
    )

    logger.info(f"Şifre değiştirildi: {username}")
    return {"message": "Şifre başarıyla güncellendi."}
