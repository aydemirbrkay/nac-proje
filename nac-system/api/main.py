"""
NAC Policy Engine — FastAPI Ana Uygulama

FreeRADIUS'un rlm_rest modülü bu API'ye istek atar.
Üç temel işlev:
  1. /auth        → Kimlik doğrulama (PAP/CHAP + MAB)
  2. /authorize   → Yetkilendirme (grup + VLAN atama)
  3. /accounting  → Oturum kayıt (start/update/stop)

Yardımcı endpoint'ler:
  4. /users            → Kullanıcı listesi
  5. /sessions/active  → Aktif oturumlar (Redis)
  6. /health           → Healthcheck
"""


import json
import asyncio
import random
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI

from routes import Authentication as auth, authorize, accounting, users, sessions, auth_admin
from services.redis_service import redis_client
from database import engine

# DOCKER ÇIKTILARI
# NAC-API de gözüken her şey burada tanımlanır — grup isimleri, birim isimleri, log formatları vb.
# Switchlerin çalışma mantığı ile aynı

# Grup → Birim eşleştirmesi
DEPARTMENT_MAP = {
    "admin": "IT Yönetimi",
    "employee": "Şirket Çalışanları",
    "guest": "Misafir / Dış Erişim",
    "iot_devices": "IoT / Cihaz Yönetimi",
}

# NAS simülasyonu: Interim-Update periyodu (saniye)
# her 30 saniyede bir aktif oturumların süre ve trafik bilgisi güncellenir (gerçek ağda genellikle 60 saniye)
INTERIM_UPDATE_INTERVAL = 30

# Oturum açma/kapama simülasyonu periyodu (saniye)
# her 45-90 saniyede bir rastgele oturum açılır veya kapanır
SESSION_EVENT_MIN_INTERVAL = 45
SESSION_EVENT_MAX_INTERVAL = 90

# Simülasyon kullanıcı havuzu — gerçek ağdaki kullanıcıları temsil eder
# Her kullanıcının grubu, VLAN'ı, birimi, switch IP'si, portu ve MAC adresi tanımlı
USER_POOL = [
    {"username": "admin_ali",     "group": "admin",    "vlan_id": "10", "department": "IT Yönetimi",           "nas_ip": "192.168.1.1", "nas_port": "Gi0/1", "mac": "AA:BB:CC:11:22:01"},
    {"username": "admin_zeynep",  "group": "admin",    "vlan_id": "10", "department": "IT Yönetimi",           "nas_ip": "192.168.1.1", "nas_port": "Gi0/2", "mac": "AA:BB:CC:11:22:02"},
    {"username": "admin_burak",   "group": "admin",    "vlan_id": "10", "department": "IT Yönetimi",           "nas_ip": "192.168.1.1", "nas_port": "Gi0/3", "mac": "AA:BB:CC:11:22:03"},
    {"username": "emp_mehmet",    "group": "employee", "vlan_id": "20", "department": "Şirket Çalışanları",    "nas_ip": "192.168.1.2", "nas_port": "Gi0/1", "mac": "AA:BB:CC:22:33:01"},
    {"username": "emp_ayse",      "group": "employee", "vlan_id": "20", "department": "Şirket Çalışanları",    "nas_ip": "192.168.1.2", "nas_port": "Gi0/2", "mac": "AA:BB:CC:22:33:02"},
    {"username": "emp_fatma",     "group": "employee", "vlan_id": "20", "department": "Şirket Çalışanları",    "nas_ip": "192.168.1.2", "nas_port": "Gi0/3", "mac": "AA:BB:CC:22:33:03"},
    {"username": "emp_can",       "group": "employee", "vlan_id": "20", "department": "Şirket Çalışanları",    "nas_ip": "192.168.1.3", "nas_port": "Gi0/1", "mac": "AA:BB:CC:22:33:04"},
    {"username": "emp_deniz",     "group": "employee", "vlan_id": "20", "department": "Şirket Çalışanları",    "nas_ip": "192.168.1.3", "nas_port": "Gi0/2", "mac": "AA:BB:CC:22:33:05"},
    {"username": "guest_user",    "group": "guest",    "vlan_id": "30", "department": "Misafir / Dış Erişim",  "nas_ip": "192.168.1.4", "nas_port": "Gi0/1", "mac": "AA:BB:CC:33:44:01"},
    {"username": "guest_ahmet",   "group": "guest",    "vlan_id": "30", "department": "Misafir / Dış Erişim",  "nas_ip": "192.168.1.4", "nas_port": "Gi0/2", "mac": "AA:BB:CC:33:44:02"},
    {"username": "guest_elif",    "group": "guest",    "vlan_id": "30", "department": "Misafir / Dış Erişim",  "nas_ip": "192.168.1.4", "nas_port": "Gi0/3", "mac": "AA:BB:CC:33:44:03"},
    {"username": "guest_tamir",   "group": "guest",    "vlan_id": "30", "department": "Misafir / Dış Erişim",  "nas_ip": "192.168.1.4", "nas_port": "Gi0/4", "mac": "AA:BB:CC:33:44:04"},
]

# Logging konfigürasyonu — Docker loglarında gördüğün her satırın formatı buradan gelir
# Örnek çıktı: "2026-03-24 07:16 [INFO] main: [OTURUM DEVAM] admin_ali | ..."
#   %(asctime)s    → tarih/saat
#   %(levelname)s  → INFO, WARNING, ERROR
#   %(name)s       → hangi modülden geldi (main, routes.accounting vb.)
#   %(message)s    → log mesajının kendisi
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Health check log filtresi
# Docker her 10 saniyede /health çağırıyor — bu filtre olmasaydı loglar şöyle olurdu:
#   GET /health 200 OK
#   GET /health 200 OK    ← spam, asıl oturum loglarını gölgeliyor
#   [OTURUM DEVAM] ...
# Bu filtre sayesinde /health logları susturuluyor, sadece asıl olaylar görünüyor

class HealthCheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "GET /health" in message:
            return False
        return True

logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Uygulama yaşam döngüsü yönetimi.
    Startup'ta bağlantıları kontrol eder, shutdown'da kapatır.
    """
    # ── Startup ──
    # Docker'da konteyner başladığında ilk gördüğün loglar buradan gelir
    logger.info("NAC Policy Engine başlatılıyor...")

    # Redis bağlantı testi
    # Ağa bağlı cihazların/kullanıcıların anlık oturum bilgilerini tutar.
    # FreeRADIUS, her birkaç dakikada bir "Interim-Update" paketi gönderir (yüzlerce cihaz varsa çok fazla yazma işlemi)
    #PostgreSQL'e her güncellemede sorgu atmak yavaş ve pahalı
    #Redis bellekte çalıştığı için mikrosaniye hızında okuma/yazma sağlar
    #/sessions/active endpoint'i açıldığında PostgreSQL yerine Redis'ten anında cevap döner */
    try:
        await redis_client.ping()
        logger.info("Redis bağlantısı başarılı.")
    except Exception as e:
        logger.error(f"Redis bağlantı hatası: {e}")

    logger.info("NAC Policy Engine hazır.")

    # ── NAS Simülasyonu: Periyodik Interim-Update ──
    # Gerçek ağda switch'ler her 60 saniyede FreeRADIUS'a Interim-Update gönderir.
    # Biz bunu simüle ediyoruz — aktif oturumların trafik ve süre bilgisini günceller.
    # Docker loglarında her 30 saniyede gördüğün [OTURUM DEVAM] çıktıları bu fonksiyondan gelir
    async def interim_update_simulator():
        """Aktif oturumlar için periyodik Interim-Update simülasyonu."""
        while True:
            await asyncio.sleep(INTERIM_UPDATE_INTERVAL)
            try:
                # Redis'teki tüm aktif oturumları tara
                cursor = 0
                updated = 0
                while True:
                    cursor, keys = await redis_client.scan(
                        cursor=cursor, match="session:*", count=100
                    )
                    for key in keys:
                        raw = await redis_client.get(key)
                        if not raw:
                            continue
                        data = json.loads(raw)

                        # Süreyi ve trafiği artır (simülasyon)
                        data["session_duration"] = data.get("session_duration", 0) + INTERIM_UPDATE_INTERVAL
                        data["input_octets"] = data.get("input_octets", 0) + random.randint(10000, 500000)
                        data["output_octets"] = data.get("output_octets", 0) + random.randint(50000, 2000000)

                        await redis_client.set(key, json.dumps(data))

                        group = data.get("group", "—")
                        vlan = data.get("vlan_id", "—")
                        dept = data.get("department", "—")
                        duration = data["session_duration"]
                        session_id = data.get("session_id", "—")
                        mac = data.get("mac", "—")
                        nas_ip = data.get("nas_ip", "—")
                        nas_port = data.get("nas_port", "—")

                        logger.info(
                            f"[OTURUM DEVAM] {data['username']} | "
                            f"Grup: {group} | VLAN: {vlan} | Birim: {dept} | "
                            f"Session: {session_id} | MAC: {mac} | "
                            f"Switch: {nas_ip} Port: {nas_port} | "
                            f"Süre: {duration}s"
                        )
                        updated += 1

                    if cursor == 0:
                        break

                if updated > 0:
                    logger.info(f"[INTERIM-UPDATE] {updated} aktif oturum güncellendi.")
            except Exception as e:
                logger.error(f"Interim-Update hatası: {e}")

    # ── NAS Simülasyonu: Oturum Açma/Kapama ──
    # Gerçek ağda kullanıcılar rastgele zamanlarda bağlanıp ayrılır.
    # Bu simülasyon bunu taklit eder — Docker loglarında [OTURUM AÇILDI] ve [OTURUM KAPANDI] mesajları üretir
    async def session_lifecycle_simulator():
        """Rastgele oturum açma/kapama simülasyonu."""
        # Başlangıçta mevcut oturumları kontrol et
        await asyncio.sleep(5)  # startup tamamlansın

        while True:
            try:
                interval = random.randint(SESSION_EVENT_MIN_INTERVAL, SESSION_EVENT_MAX_INTERVAL)
                await asyncio.sleep(interval)

                # Şu an aktif olan oturumları bul
                active_usernames = set()
                cursor = 0
                while True:
                    cursor, keys = await redis_client.scan(cursor=cursor, match="session:*", count=100)
                    for key in keys:
                        raw = await redis_client.get(key)
                        if raw:
                            data = json.loads(raw)
                            active_usernames.add(data.get("username"))
                    if cursor == 0:
                        break

                # Bağlı olmayan kullanıcılar
                offline_users = [u for u in USER_POOL if u["username"] not in active_usernames]

                # %60 oturum açma, %40 oturum kapama olasılığı
                # Ama en az 3 aktif oturum kalsın (loglar boş kalmasın)
                open_session = random.random() < 0.6

                if open_session and offline_users:
                    # ── Yeni oturum aç ──
                    user = random.choice(offline_users)
                    now = datetime.now()
                    session_id = f"sess-{user['username'].split('_')[-1]}-{int(now.timestamp())}"
                    unique_id = session_id

                    session_data = {
                        "username": user["username"],
                        "session_id": session_id,
                        "nas_ip": user["nas_ip"],
                        "nas_port": user["nas_port"],
                        "mac": user["mac"],
                        "start_time": now.isoformat(),
                        "group": user["group"],
                        "vlan_id": user["vlan_id"],
                        "department": user["department"],
                        "session_duration": 0,
                        "input_octets": 0,
                        "output_octets": 0,
                    }

                    redis_key = f"session:{unique_id}"
                    await redis_client.set(redis_key, json.dumps(session_data))
                    await redis_client.sadd(f"user_sessions:{user['username']}", unique_id)

                    logger.info(
                        f"[OTURUM AÇILDI] {user['username']} | "
                        f"Grup: {user['group']} | VLAN: {user['vlan_id']} | Birim: {user['department']} | "
                        f"Session: {session_id} | MAC: {user['mac']} | "
                        f"Switch: {user['nas_ip']} Port: {user['nas_port']}"
                    )

                elif not open_session and len(active_usernames) > 3:
                    # ── Mevcut oturumu kapat ──
                    # Rastgele bir aktif oturum seç
                    cursor = 0
                    all_sessions = []
                    while True:
                        cursor, keys = await redis_client.scan(cursor=cursor, match="session:*", count=100)
                        all_sessions.extend(keys)
                        if cursor == 0:
                            break

                    if all_sessions:
                        close_key = random.choice(all_sessions)
                        raw = await redis_client.get(close_key)
                        if raw:
                            data = json.loads(raw)
                            username = data.get("username", "—")
                            group = data.get("group", "—")
                            vlan = data.get("vlan_id", "—")
                            dept = data.get("department", "—")
                            session_id = data.get("session_id", "—")
                            mac = data.get("mac", "—")
                            nas_ip = data.get("nas_ip", "—")
                            nas_port = data.get("nas_port", "—")
                            duration = data.get("session_duration", 0)

                            # Kapanma nedenleri
                            terminate_causes = ["User-Request", "Session-Timeout", "Admin-Reset", "Port-Error", "Idle-Timeout"]
                            cause = random.choice(terminate_causes)

                            # Redis'ten sil
                            unique_id = close_key.replace("session:", "")
                            await redis_client.delete(close_key)
                            await redis_client.srem(f"user_sessions:{username}", unique_id)

                            logger.info(
                                f"[OTURUM KAPANDI] {username} | "
                                f"Grup: {group} | VLAN: {vlan} | Birim: {dept} | "
                                f"Session: {session_id} | MAC: {mac} | "
                                f"Switch: {nas_ip} Port: {nas_port} | "
                                f"Süre: {duration}s | Neden: {cause}"
                            )

            except Exception as e:
                logger.error(f"Oturum simülasyon hatası: {e}")

    # Background task'ları başlat — uygulama çalıştığı sürece arka planda döner
    task_interim = asyncio.create_task(interim_update_simulator())
    task_lifecycle = asyncio.create_task(session_lifecycle_simulator())

    yield

    # ── Shutdown — docker stop veya restart yapıldığında burası çalışır ──
    task_interim.cancel()    # interim-update döngüsünü durdur
    task_lifecycle.cancel()  # oturum açma/kapama döngüsünü durdur
    logger.info("NAC Policy Engine kapatılıyor...")
    await redis_client.close()   # Redis bağlantısını kapat
    await engine.dispose()       # PostgreSQL bağlantı havuzunu kapat
    logger.info("Tüm bağlantılar kapatıldı.")


# FastAPI uygulaması
app = FastAPI(
    title="NAC Policy Engine",
    description="FreeRADIUS rlm_rest entegrasyonu ile ağ erişim kontrolü",
    version="1.0.0",
    lifespan=lifespan,
)

# Route'ları kaydet — her dosyadaki endpoint'leri uygulamaya bağlar
# Docker loglarındaki [GİRİŞ BAŞARILI], [OTURUM AÇILDI], [OTURUM KAPANDI] bu router'lardan gelir
app.include_router(auth.router, tags=["Authentication"])       # /auth endpoint'i
app.include_router(authorize.router, tags=["Authorization"])   # /authorize endpoint'i
app.include_router(accounting.router, tags=["Accounting"])     # /accounting endpoint'i
app.include_router(users.router, tags=["Users"])               # /users endpoint'i
app.include_router(sessions.router, tags=["Sessions"])         # /sessions/active endpoint'i
app.include_router(auth_admin.router, tags=["Admin"])          # /admin/login endpoint'i


@app.get("/health")
async def health_check():
    """
    Healthcheck endpoint'i.
    Docker healthcheck bu endpoint'i her 10 saniyede çağırır.
    Redis ve PostgreSQL ayakta mı kontrol eder.
    docker ps'de gördüğün (healthy) veya (unhealthy) durumu bu endpoint'in cevabına göre belirlenir.
    """
    health = {"status": "healthy", "services": {}}

    # Redis durumu
    try:
        await redis_client.ping()
        health["services"]["redis"] = "up"
    except Exception:
        health["services"]["redis"] = "down"
        health["status"] = "degraded"

    # PostgreSQL durumu (basit bağlantı kontrolü)
    try:
        async with engine.connect() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        health["services"]["postgres"] = "up"
    except Exception:
        health["services"]["postgres"] = "down"
        health["status"] = "degraded"

    return health
