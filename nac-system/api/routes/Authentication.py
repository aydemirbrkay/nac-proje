"""
Authentication endpoint.
FreeRADIUS rlm_rest modülü, her auth isteğinde bu 
endpoint'e (Kullanıcı adı/şifre kontrolünün yapıldığı API adresi ) POST yapar.


FreeRADIUS kendi başına karar vermez, rlm_rest ile
http://nac-api:8000/auth adresine POST atar ve "bu kullanıcıyı kabul edeyim mi?" diye sorar.
 Karar FastAPI tarafında verilir.

İki doğrulama modu:
  1. PAP/CHAP: username + password ile doğrulama (bcrypt hash ile)
  2. MAB: Calling-Station-Id (MAC adresi) ile cihaz doğrulama

Akış:
  Client → Switch → FreeRADIUS → [rlm_rest] → POST /auth → FastAPI → PostgreSQL
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import bcrypt

from database import get_db
from models import RadCheck, MacDevice, RadUserGroup, RadGroupReply
from schemas import RadiusAuthRequest, AuthResponse

# Grup → Birim eşleştirmesi
# bağlanan kişinin bağlanabileceği gruplar ve bu gruplara karşılık gelen birim isimleri
DEPARTMENT_MAP = {
    "admin": "IT Yönetimi",
    "employee": "Şirket Çalışanları",
    "guest": "Misafir / Dış Erişim",
    "iot_devices": "IoT / Cihaz Yönetimi",
}
from services.rate_limiter import (
    is_rate_limited,  # çok fazla yanlış deneme olup olmadığını kontrol eder
    record_failed_attempt,  # yanlış denemeyi kaydeder ve sayacı artırır
    reset_attempts, # başarılı girişte sayacı sıfırlar
    get_remaining_lockout, # yanlış girdiniz ... saniye kaldı gibi mesajlarda kalan süreyi göstermek
)

logger = logging.getLogger(__name__)
router = APIRouter()



def normalize_mac(mac: str) -> str:
    """MAC adresini tutarlı formata çevirir: AA:BB:CC:DD:EE:FF"""
    clean = mac.replace("-", "").replace(".", "").replace(":", "").upper()
    if len(clean) != 12:  # 12 hex karakter değilse, orijinal değeri döndür
        return mac.upper()
    return ":".join(clean[i:i+2] for i in range(0, 12, 2))  
    # her 2 karakteri ":" ile ayırır ve MAC formatına çevirir


@router.post("/auth", response_model=AuthResponse)
async def authenticate(
    request: RadiusAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Kullanıcı veya cihaz kimlik doğrulaması yapar.

    FreeRADIUS'tan gelen 2 tür istek vardır:
    - MAB: username = MAC adresi, calling_station_id = MAC adresi, password boş/yok
    - PAP: username + password alanları dolu
    """
    username = request.username
    logger.info(f"Auth isteği geldi: username={username}")

    # ── 1. MAB kontrolü ──
    # MAB'da username olarak MAC adresi gelir.
    # MAC formatı tespiti: ":" veya "-" içeriyorsa veya 12 hex karakter ise MAB
    is_mab = request.calling_station_id is not None and (
        request.password is None or request.password == "" or
        request.password == request.username
    )

    if is_mab:
        return await _handle_mab(request.calling_station_id or username, db)

    # ── 2. PAP/CHAP Doğrulama ──
    return await _handle_pap(username, request.password or "", db)


async def _handle_pap(username: str, password: str, db: AsyncSession) -> AuthResponse:
    """PAP/CHAP şifre tabanlı doğrulama (Hashed-Password veya Cleartext-Password)."""

    # Rate limit kontrolü
    if await is_rate_limited(username):
        remaining = await get_remaining_lockout(username)
        logger.warning(f"Kullanıcı kilitli: {username}, kalan süre: {remaining}s")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Hesap geçici olarak kilitli. {remaining} saniye sonra tekrar deneyin.",
        )

# CONFIG.PY DOSYASINDA TANIMLANAN AYARLAR KULLANILIR

    # ── Şifre doğrulaması: Hashed-Password (bcrypt) veya Cleartext-Password ──
    stmt = select(RadCheck).where(RadCheck.username == username)
    result = await db.execute(stmt)
    user_records = result.scalars().all()

    if not user_records:
        await record_failed_attempt(username)
        logger.info(f"Kullanıcı bulunamadı: {username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı.",
        )

    auth_ok = False
    for record in user_records:
        # Hashed-Password (bcrypt) — secure
        if record.attribute == "Hashed-Password":
            try:
                if bcrypt.checkpw(password.encode(), record.value.encode()):
                    auth_ok = True
                    break
            except Exception as e:
                logger.warning(f"Hash doğrulama hatası ({username}): {e}")
                continue

        # Cleartext-Password güvenlik açığı — desteklenmez
        elif record.attribute == "Cleartext-Password":
            logger.warning(f"Cleartext-Password tespit edildi: {username}. Hashed-Password kullanılmalı.")
            continue

    if not auth_ok:
        attempts = await record_failed_attempt(username)
        remaining_attempts = max(0, 5 - attempts)
        logger.info(f"Yanlış şifre: {username}, kalan deneme: {remaining_attempts}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Yanlış şifre. Kalan deneme: {remaining_attempts}",
        )

    # Başarılı giriş → rate limit sayacını sıfırla
    await reset_attempts(username)

    # Kullanıcının grup/VLAN/birim bilgisini logla
    
    stmt = select(RadUserGroup).where(RadUserGroup.username == username).order_by(RadUserGroup.priority)
    result = await db.execute(stmt)
    user_group = result.scalar_one_or_none()
    group = user_group.groupname if user_group else "—"
    department = DEPARTMENT_MAP.get(group, "Bilinmeyen")

    vlan_id = "—"
    if user_group:
        stmt = select(RadGroupReply).where(
            RadGroupReply.groupname == group,
            RadGroupReply.attribute == "Tunnel-Private-Group-Id",
        )
        result = await db.execute(stmt)
        vlan_reply = result.scalar_one_or_none()
        if vlan_reply:
            vlan_id = vlan_reply.value

    # username eşleştikten sonra loglama yapılır, böylece hangi 
    # kullanıcıların giriş yapmaya çalıştığı ve hangi gruplara ait oldukları görülebilir. 
    logger.info(
        f"[GİRİŞ BAŞARILI] {username} | "
        f"Grup: {group} | VLAN: {vlan_id} | Birim: {department}"
    )

    return AuthResponse(
        result="accept",
        message="Kimlik doğrulama başarılı.",
    )


# burada da hangi cihazların bağlandığı, hangi gruplara ait oldukları
# ve hangi VLAN'lara atandıkları görülebilir.
async def _handle_mab(mac_raw: str, db: AsyncSession) -> AuthResponse:
    """MAC Authentication Bypass — cihaz kimlik doğrulaması."""

    mac = normalize_mac(mac_raw)
    logger.info(f"MAB isteği: MAC={mac}")

    # MAC adresini veritabanında ara
    stmt = select(MacDevice).where(
        MacDevice.mac_address == mac,
        MacDevice.is_active == True,
    )
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()

    if device is None:
        # Bilinmeyen cihaz → guest VLAN'a yönlendir (HTTP 200 ile accept döner)
        logger.info(f"Bilinmeyen MAC adresi, guest VLAN'a yönlendiriliyor: {mac}")
        return AuthResponse(
            result="accept",
            message="Bilinmeyen cihaz — guest VLAN atandı.",
            reply_attributes={
                "Tunnel-Type": "13",
                "Tunnel-Medium-Type": "6",
                "Tunnel-Private-Group-Id": "30",  # Guest VLAN
            },
        )

    logger.info(f"MAB başarılı: {mac} → grup={device.groupname}")
    return AuthResponse(
        result="accept",
        message=f"Cihaz doğrulandı: {device.device_name}",
    )
