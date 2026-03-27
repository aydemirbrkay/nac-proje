"""
Accounting endpoint.
FreeRADIUS her oturum olayında bu endpoint'e POST yapar.

Üç tip accounting paketi işlenir:
  - Start:          Oturum başlangıcı → DB'ye yeni kayıt, Redis'e cache
  - Interim-Update: Periyodik güncelleme → DB + Redis güncelle
  - Stop:           Oturum sonu → DB güncelle, Redis'ten sil
"""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import RadAcct, RadUserGroup, RadGroupReply
from schemas import RadiusAccountingRequest, AccountingResponse
from services.redis_service import redis_client

# Grup → Birim eşleştirmesi
# burada FreeRADIUS'daki grup isimlerini şirketinizdeki birim isimlerine eşleyebilirsiniz.
# istenildiği takdirde arttırılabilir veya veritabanından dinamik olarak çekilebilir.
DEPARTMENT_MAP = {
    "admin": "IT Yönetimi",
    "employee": "Şirket Çalışanları",
    "guest": "Misafir / Dış Erişim",
    "iot_devices": "IoT / Cihaz Yönetimi",
}

logger = logging.getLogger(__name__)
router = APIRouter()

# Redis'te aktif oturumlar bu prefix ile saklanır
ACTIVE_SESSION_PREFIX = "session:"


@router.post("/accounting", response_model=AccountingResponse)
async def accounting(
    request: RadiusAccountingRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Accounting paketini işler.
    acct_status_type'a göre Start/Interim-Update/Stop dallanır.
    """
    status = request.acct_status_type.lower().replace("-", "")
    logger.info(
        f"Accounting: user={request.username}, "
        f"status={request.acct_status_type}, "
        f"session={request.acct_session_id}"
    )
# Radius isteği geldiğnide acct_status_type alanına göre hangi işlemin yapılacağına karar verir.
# Start → _handle_start, Interim-Update → _handle_interim, Stop → _handle_stop fonksiyonları çağrılır.
# OTURUM BAŞLADI OTURUM DEVAM EDİYOR OTURUM BİTTİ LOGLARININ DOCKERDA GÖZÜKEN

    if status in ("start",):
        return await _handle_start(request, db)
    elif status in ("interimupdate", "interim", "alive"):  
        return await _handle_interim(request, db)
    elif status in ("stop",):
        return await _handle_stop(request, db)
    else:
        logger.warning(f"Bilinmeyen accounting status: {request.acct_status_type}")
        return AccountingResponse(result="ok", message="Bilinmeyen status tipi.")




# DB DE KAYITLI KİŞİLERİN GRUP, VLAN VE BİRİM BİLGİLERİNİ ÇEKME FONKSİYONU


async def _lookup_user_info(username: str, db: AsyncSession) -> tuple[str | None, str | None, str | None]:
    """Kullanıcının grup, VLAN ve birim bilgisini veritabanından çeker."""
    # Grup bul
    stmt = select(RadUserGroup).where(RadUserGroup.username == username).order_by(RadUserGroup.priority)
    result = await db.execute(stmt)
    user_group = result.scalar_one_or_none()

    if not user_group:
        return None, None, None

    group = user_group.groupname
    department = DEPARTMENT_MAP.get(group, "Bilinmeyen Birim")

    # VLAN bul
    stmt = select(RadGroupReply).where(
        RadGroupReply.groupname == group,
        RadGroupReply.attribute == "Tunnel-Private-Group-Id",
    )
    result = await db.execute(stmt)
    vlan_reply = result.scalar_one_or_none()
    vlan_id = vlan_reply.value if vlan_reply else None

    return group, vlan_id, department


async def _handle_start(
    req: RadiusAccountingRequest,
    db: AsyncSession,
) -> AccountingResponse:
    """Oturum başlangıcı — yeni kayıt oluştur."""

    now = datetime.now()
    unique_id = req.acct_unique_session_id or req.acct_session_id

    # Kullanıcının grup/VLAN/birim bilgisini çek
    group, vlan_id, department = await _lookup_user_info(req.username, db)

    # PostgreSQL'e kaydet

    # PostgreSQL'e yeni oturum kaydı oluştur
    acct = RadAcct(
        acctsessionid=req.acct_session_id,  # FreeRADIUS tarafından gönderilen oturum ID'si
        acctuniqueid=unique_id,             # Oturum ID'si veya unique session ID'si (varsa)
        username=req.username,
        nasipaddress=req.nas_ip_address, 
        nasportid=req.nas_port_id,
        acctstarttime=now,
        acctupdatetime=now,
        framedipaddress=req.framed_ip_address, 
        callingstation=req.calling_station_id, # MAC adresi
        acctstatustype="Start",
    )
    db.add(acct)
    await db.flush()

    
    # Amaç redis ile veriyi cache'leyerek hızlı erişim sağlamak ve oturum bilgilerini gerçek zamanlı olarak takip edebilmek.
    # takip edilen bilgileri istenilene göre arttırabiliriz.
    
    session_data = {
        "username": req.username,
        "session_id": req.acct_session_id,
        "nas_ip": req.nas_ip_address,
        "nas_port": req.nas_port_id,
        "mac": req.calling_station_id,
        "start_time": now.isoformat(),
        "group": group,
        "vlan_id": vlan_id,
        "department": department,
        "session_duration": 0,
        "input_octets": 0,
        "output_octets": 0,
    }
    redis_key = f"{ACTIVE_SESSION_PREFIX}{unique_id}"
    await redis_client.set(redis_key, json.dumps(session_data))
    # yukardaki session_datayı Redis'e JSON string olarak kaydetmeye yarar.
    # seassions.py de ise bu JSON string'i tekrar Python dict'e çevirir ve ActiveSession modeline dönüştürür.

    # Kullanıcının aktif oturum listesine ekle
    # Amaç: Bir kullanıcının aynı anda birden fazla oturumu olabilir ve bu oturumları takip etmek isteyebiliriz.
    # user_sessions:ahmet  →  { "sess_001", "sess_002", "sess_003" }

    user_sessions_key = f"user_sessions:{req.username}"
    await redis_client.sadd(user_sessions_key, unique_id)


# DOCKER LOGLARININ GÖZÜKEN KISMI
    logger.info(
        f"[OTURUM AÇILDI] {req.username} | "
        f"Grup: {group} | VLAN: {vlan_id} | Birim: {department} | "
        f"Session: {req.acct_session_id} | MAC: {req.calling_station_id} | "
        f"Switch: {req.nas_ip_address} Port: {req.nas_port_id}"
    )
    return AccountingResponse(result="ok", message="Oturum başlatıldı.")


async def _handle_interim(
    req: RadiusAccountingRequest,
    db: AsyncSession,
) -> AccountingResponse:
    """Periyodik güncelleme — mevcut kaydı güncelle."""

    now = datetime.now()
    unique_id = req.acct_unique_session_id or req.acct_session_id

    # PostgreSQL güncelle
    stmt = (
        update(RadAcct)
        .where(RadAcct.acctuniqueid == unique_id)
        .values(
            acctupdatetime=now,
            acctsessiontime=req.acct_session_time,
            acctinputoctets=req.acct_input_octets,
            acctoutputoctets=req.acct_output_octets,
            acctstatustype="Interim-Update",
        )
    )
    await db.execute(stmt)

    # Redis cache güncelle
    redis_key = f"{ACTIVE_SESSION_PREFIX}{unique_id}"
    existing = await redis_client.get(redis_key)
    if existing:
        session_data = json.loads(existing)
        session_data["session_duration"] = req.acct_session_time
        session_data["input_octets"] = req.acct_input_octets
        session_data["output_octets"] = req.acct_output_octets
        await redis_client.set(redis_key, json.dumps(session_data))

    # Birim bilgisini çek
    group, vlan_id, department = await _lookup_user_info(req.username, db)

    logger.info(
        f"[OTURUM DEVAM] {req.username} | "
        f"Grup: {group} | VLAN: {vlan_id} | Birim: {department} | "
        f"Session: {req.acct_session_id} | MAC: {req.calling_station_id} | "
        f"Switch: {req.nas_ip_address} Port: {req.nas_port_id} | "
        f"Süre: {req.acct_session_time}s"
    )
    return AccountingResponse(result="ok", message="Oturum güncellendi.")


async def _handle_stop(
    req: RadiusAccountingRequest,
    db: AsyncSession,
) -> AccountingResponse:
    """Oturum sonu — kaydı kapat ve Redis'ten temizle."""

    now = datetime.now()
    unique_id = req.acct_unique_session_id or req.acct_session_id

    # PostgreSQL güncelle
    stmt = (
        update(RadAcct)
        .where(RadAcct.acctuniqueid == unique_id)
        .values(
            acctstoptime=now,
            acctupdatetime=now,
            acctsessiontime=req.acct_session_time,
            acctinputoctets=req.acct_input_octets,
            acctoutputoctets=req.acct_output_octets,
            acctterminatecause=req.acct_terminate_cause,
            acctstatustype="Stop",
        )
    )
    await db.execute(stmt)

    # Redis'ten aktif oturumu sil
    redis_key = f"{ACTIVE_SESSION_PREFIX}{unique_id}"
    await redis_client.delete(redis_key)

    # Kullanıcının aktif oturum listesinden çıkar
    user_sessions_key = f"user_sessions:{req.username}"
    await redis_client.srem(user_sessions_key, unique_id)
    # srem komutu tekrar eden unique_id'yi user_sessions:{username} set'inden siler.
    # Böylece kullanıcının aktif oturum listesi güncel kalır. 

    # Birim bilgisini çek
    group, vlan_id, department = await _lookup_user_info(req.username, db)

    logger.info(
        f"[OTURUM KAPANDI] {req.username} | "
        f"Grup: {group} | VLAN: {vlan_id} | Birim: {department} | "
        f"Session: {req.acct_session_id} | MAC: {req.calling_station_id} | "
        f"Switch: {req.nas_ip_address} Port: {req.nas_port_id} | "
        f"Süre: {req.acct_session_time}s | Neden: {req.acct_terminate_cause}"
    )
    return AccountingResponse(result="ok", message="Oturum sonlandırıldı.")
