# Python Dosya Mimarisi ve Temel Dosyalar Analizi

## Bölüm 1: Python Dosya Mimarisi

### Katman Yapısı (Layered Architecture)

NAC Policy Engine uygulaması katmanlı mimari prensiplerine uygun olarak tasarlanmış. Her katman belirli sorumluluklar üstlenir:

```
┌────────────────────────────────────────────────────────┐
│                   API Gateway Layer                     │
│         (FastAPI / main.py — Healthcheck, Routing)     │
└────────────────┬─────────────────────────────────────┘
                 │
     ┌───────────┼───────────┐
     │           │           │
┌────▼────┐ ┌────▼─────┐ ┌──▼───────┐
│ Routes  │ │ Services │ │ Database │
│ Layer   │ │ Layer    │ │ Layer    │
└────┬────┘ └────┬─────┘ └──┬───────┘
     │           │           │
┌────▼───────────▼───────────▼────────────┐
│    PostgreSQL + Redis (Data Layer)      │
│      FreeRADIUS Schema Tables           │
└─────────────────────────────────────────┘
```

#### 1.1 Routes Layer (`routes/`)
API endpoint'lerini tanımlar. Her modül FreeRADIUS'tan gelen istekleri işler:

- **`auth.py`** — Kimlik doğrulama (PAP/CHAP + MAB)
  - POST `/auth` — FreeRADIUS rlm_rest modülünden gelen auth paketlerini işler
  - PAP: Username + Password doğrulaması
  - MAB: MAC adresi ile cihaz doğrulaması
  - Rate limiting entegrasyonu

- **`authorize.py`** — Yetkilendirme (VLAN + Policy Atama)
  - POST `/authorize` — Kullanıcı grubuna göre VLAN ataması
  - Grup bazlı atribütleri radgroupreply tablosundan çeker
  - Kullanıcı-spesifik reply atribütlerini ekler

- **`accounting.py`** — Oturum Kayıtlaması
  - POST `/accounting` — Start/Interim-Update/Stop paketlerini işler
  - PostgreSQL'e session log kaydeder
  - Redis'te aktif oturum cache'i yönetir

- **`users.py`** — Kullanıcı Listesi
  - GET `/users` — Kayıtlı tüm kullanıcıları ve durumlarını döner
  - Online status bilgisini Redis'ten çeker

- **`sessions.py`** — Aktif Oturumlar
  - GET `/sessions/active` — Redis'teki aktif oturumları listeler
  - SCAN komutu kullanarak non-blocking erişim sağlar

#### 1.2 Services Layer (`services/`)
İş mantığı ve altyapı hizmetleri:

- **`redis_service.py`** — Redis Bağlantı Yönetimi
  - Async Redis client oluşturur
  - Connection pool otomatik yönetir
  - Tüm modüller tarafından kullanılan singleton client

- **`rate_limiter.py`** — Brute-Force Koruma
  - Fixed-window rate limiting (5 deneme / 5 dakika)
  - Redis INCR ile atomik sayaç tutma
  - TTL yönetimi

#### 1.3 Core Module'ler (Ana Dizin)

- **`config.py`** — Pydantic Settings
  - .env dosyasından environment variable'ları yükler
  - Merkezi konfigürasyon noktası

- **`database.py`** — SQLAlchemy Async Engine
  - AsyncSession factory
  - Connection pool yönetimi
  - FastAPI dependency injection (get_db)

- **`models.py`** — SQLAlchemy ORM
  - FreeRADIUS şemasıyla uyumlu ORM sınıfları
  - 6 tablo tanımı: RadCheck, RadReply, RadUserGroup, RadGroupReply, RadAcct, MacDevice

- **`schemas.py`** — Pydantic Validation
  - Request/Response modelleri
  - FreeRADIUS rlm_rest formatıyla uyumlu

- **`main.py`** — FastAPI App Initialization
  - App oluşturma ve route registration
  - Lifespan context manager (startup/shutdown)
  - Healthcheck endpoint

### 1.4 __init__.py Dosyaları

```
api/
├── routes/
│   └── __init__.py    # Package definition (boş veya empty)
└── services/
    └── __init__.py    # Package definition (boş veya empty)
```

**Amacı:** Python'a bu dizinleri package olarak tanıtır. İmport edilebilir kılınır.

```python
# Örnek: routes modülünü import etme
from routes import auth, authorize  # Mümkün çünkü __init__.py var
```

### 1.5 __pycache__ ve .pyc Dosyaları

```
api/
├── __pycache__/
│   ├── config.cpython-311.pyc
│   ├── database.cpython-311.pyc
│   ├── models.cpython-311.pyc
│   ├── main.cpython-311.pyc
│   └── schemas.cpython-311.pyc
└── routes/
    └── __pycache__/
        ├── auth.cpython-311.pyc
        ├── authorize.cpython-311.pyc
        └── ...
```

**Nedir?**
- `.pyc` → Compiled Python bytecode
- `__pycache__/` → .pyc dosyalarını saklayan dizin
- Otomatik olarak Python tarafından oluşturulur

**Neden oluşturulur?**
- Python ilk çalıştırıldığında source code'u bytecode'a derler
- Bytecode'u cache'lediğinde, sonraki import'lar hızlı olur
- Parsing/compilation adımı atlayarak başlangıç hızı artar

**Versiyon Bilgisi:**
- `cpython-311` → CPython 3.11 versiyonu
- Farklı Python versiyonları ayrı .pyc dosyaları oluşturur

**.gitignore İçinde:**
```
__pycache__/
*.pyc
```
Neden? Versiyona kontrol yapılması gerekmez:
- Local ortama özeldir
- Yeniden derlenir
- Repository'yi şişirir
- Merge conflict'lerine sebep olur

---

## Bölüm 2: Temel Python Dosyaları Detaylı Analizi

### 2.1 config.py

**Ne Yapar?**
Pydantic-settings kullanarak .env dosyasından environment variable'larını yükler. Tüm konfigürasyon merkezi olarak bu dosyada tutulur.

**Detaylı İçeriği:**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # PostgreSQL
    DATABASE_URL: str                    # Örn: "postgresql+asyncpg://user:pass@localhost/raddb"

    # Redis
    REDIS_URL: str                       # Örn: "redis://localhost:6379/0"

    # Güvenlik
    SECRET_KEY: str                      # API key veya JWT secret

    # Rate limiting
    MAX_AUTH_ATTEMPTS: int = 5           # Maksimum başarısız deneme
    AUTH_LOCKOUT_SECONDS: int = 300      # 5 dakika lockout süresi

    class Config:
        env_file = ".env"                # .env dosyasını oku

settings = Settings()                    # Global singleton instance
```

**Pydantic-Settings Özellikleri:**
- Tür kontrolleri: `str`, `int` vs.
- Default değerleri: `MAX_AUTH_ATTEMPTS: int = 5`
- Otomatik type casting: `"5"` → `5`
- .env dosyasından otomatik yükleme

**Kullanım Örneği (Diğer Dosyalarda):**
```python
from config import settings

engine = create_async_engine(settings.DATABASE_URL)  # DATABASE_URL'yi oku
redis_client = redis.from_url(settings.REDIS_URL)   # REDIS_URL'yi oku
```

**Bağlantıları:**
- `database.py` → `settings.DATABASE_URL` kullanır
- `services/redis_service.py` → `settings.REDIS_URL` kullanır
- `services/rate_limiter.py` → `settings.MAX_AUTH_ATTEMPTS` ve `settings.AUTH_LOCKOUT_SECONDS` kullanır

**Kritik Noktalar:**
- `.env` dosyası Git'e commit edilmemelidir (`.gitignore`'da olmalı)
- `.env.example` örnek dosya sağlanmalı
- Üretim ortamında environment variable'lar sistem üzerinden set edilmeli (Docker, Kubernetes vb.)

---

### 2.2 database.py

**Ne Yapar?**
SQLAlchemy async engine ve session factory'sini oluşturur. Tüm veritabanı işlemleri bu dosya üzerinden yönetilir.

**Detaylı İçeriği:**

```python
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker
)
from config import settings

# Async Engine Oluşturma
engine = create_async_engine(
    settings.DATABASE_URL,           # "postgresql+asyncpg://user:pass@localhost/raddb"
    echo=False,                      # SQL loglarını kapat (debug için True yapılabilir)
    pool_size=10,                    # Pool'da tutulacak max bağlantı
    max_overflow=5,                  # Pool dolduğunda +5 ek bağlantı açılabilir
)
# Toplam: 10 + 5 = 15 maksimum bağlantı

# Session Factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,          # Commit sonrası nesneler geçerli kalır
)

# FastAPI Dependency
async def get_db() -> AsyncSession:
    """Her endpoint çağrısında bu fonksiyon çalışır."""
    async with async_session() as session:
        try:
            yield session                 # Endpoint'e session ver
            await session.commit()        # Endpoint başarılı olduysa commit
        except Exception:
            await session.rollback()      # Hata varsa rollback
            raise
```

**Connection Pool Yönetimi:**
```
İstek 1, 2, 3... → Pool (10 bağlantı)
İstek 11, 12... → Overflow queue (5 bağlantı)

Total = 15 bağlantı → Eşzamanlı 15 istek işlenebilir
```

**Async/Await Mimarisi:**
```python
# asyncio sayesinde non-blocking I/O
async with async_session() as session:
    result = await db.execute(stmt)  # Thread bloklarken diğer tasklar çalışır
    await session.commit()           # Commit tamamlanmadan bekler
```

**FastAPI Integration:**

```python
# Routes'te kullanım
from fastapi import Depends
from database import get_db

@router.post("/auth")
async def authenticate(
    request: RadiusAuthRequest,
    db: AsyncSession = Depends(get_db),  # Dependency injection
):
    stmt = select(RadCheck).where(...)
    result = await db.execute(stmt)       # Session otomatik manage edilir
    return response
```

**Bağlantıları:**
- `main.py` → Engine'i kapatmak için `engine.dispose()`
- Tüm `routes/*` → `get_db` dependency'sini kullanır
- `models.py` → ORM tanımlarından yararlanır

**Kritik Noktalar:**
- `pool_size=10` → Çok az olursa connection timeout, çok fazla olursa resource waste
- `expire_on_commit=False` → Lazy loading'i önler, detached state'i engeller
- Transaction management: Başarısız operasyonlar otomatik rollback edilir
- PostgreSQL async driver: `asyncpg` veya `psycopg` (async variant)

---

### 2.3 models.py

**Ne Yapar?**
SQLAlchemy ORM sınıflarını tanımlar. FreeRADIUS şemasıyla uyumlu database tablo modelleri.

**Detaylı İçeriği:**

```python
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, func
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass  # Tüm ORM sınıflarının base'i
```

#### Model 1: RadCheck (Kimlik Bilgileri)
```python
class RadCheck(Base):
    __tablename__ = "radcheck"  # PostgreSQL tablosu

    id = Column(Integer, primary_key=True)
    username = Column(String(64), nullable=False, index=True)  # Indexed for fast lookup
    attribute = Column(String(64), nullable=False)
    op = Column(String(2), nullable=False, default=":=")       # Operator: :=, ==, etc.
    value = Column(String(253), nullable=False)
```

**Veriler Örneği:**
```
| id | username | attribute           | op  | value    |
|----|----------|---------------------|-----|----------|
| 1  | alice    | Cleartext-Password  | :=  | Alice123 |
| 2  | alice    | User-Category       | :=  | admin    |
| 3  | bob      | Cleartext-Password  | :=  | Bob456   |
```

#### Model 2: RadReply (Kullanıcı-Spesifik Atribütler)
```python
class RadReply(Base):
    __tablename__ = "radreply"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), nullable=False, index=True)
    attribute = Column(String(64), nullable=False)
    op = Column(String(2), nullable=False, default=":=")
    value = Column(String(253), nullable=False)
```

**Kullanım:** Belirli kullanıcılara özel RADIUS atribütleri eklemek için.

#### Model 3: RadUserGroup (Kullanıcı-Grup İlişkileri)
```python
class RadUserGroup(Base):
    __tablename__ = "radusergroup"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), nullable=False, index=True)
    groupname = Column(String(64), nullable=False)
    priority = Column(Integer, nullable=False, default=1)
```

**Veriler Örneği:**
```
| id | username | groupname | priority |
|----|----------|-----------|----------|
| 1  | alice    | staff     | 1        |
| 2  | bob      | guest     | 1        |
| 3  | charlie  | students  | 1        |
```

**Priority:** Kullanıcı birden fazla gruba aitse, priority en düşük olanı seçilir.

#### Model 4: RadGroupReply (Grup Bazlı Atribütler)
```python
class RadGroupReply(Base):
    __tablename__ = "radgroupreply"

    id = Column(Integer, primary_key=True)
    groupname = Column(String(64), nullable=False, index=True)
    attribute = Column(String(64), nullable=False)
    op = Column(String(2), nullable=False, default=":=")
    value = Column(String(253), nullable=False)
```

**Veriler Örneği (VLAN Atama):**
```
| id | groupname | attribute               | op  | value |
|----|-----------|-------------------------|-----|-------|
| 1  | staff     | Tunnel-Private-Group-Id | :=  | 10    |
| 2  | staff     | Tunnel-Type             | :=  | 13    |
| 3  | guest     | Tunnel-Private-Group-Id | :=  | 30    |
| 4  | students  | Tunnel-Private-Group-Id | :=  | 20    |
```

**Tunnel-Private-Group-Id = VLAN ID**

#### Model 5: RadAcct (Oturum Kayıtları)
```python
class RadAcct(Base):
    __tablename__ = "radacct"

    id = Column(BigInteger, primary_key=True)
    acctsessionid = Column(String(64), nullable=False)
    acctuniqueid = Column(String(32), nullable=False, unique=True)
    username = Column(String(64), nullable=False, index=True)
    nasipaddress = Column(String(15), nullable=False)
    nasportid = Column(String(32))
    acctstarttime = Column(DateTime)
    acctupdatetime = Column(DateTime)
    acctstoptime = Column(DateTime)
    acctsessiontime = Column(BigInteger, default=0)      # Saniye cinsinden
    acctinputoctets = Column(BigInteger, default=0)      # İndirilen bytes
    acctoutputoctets = Column(BigInteger, default=0)     # Yüklenen bytes
    acctterminatecause = Column(String(32))               # User-Request, Idle-Timeout vs.
    framedipaddress = Column(String(15))
    callingstation = Column(String(50))                   # Cihaz MAC adresi
    acctstatustype = Column(String(25))
```

**Oturum Yaşam Döngüsü:**
```
Start:
  INSERT: username, acctsessionid, acctstarttime, acctstatustype=Start

Interim-Update (periyodik):
  UPDATE: acctupdatetime, acctsessiontime, acctinputoctets, acctoutputoctets

Stop:
  UPDATE: acctstoptime, final counters, acctterminatecause
```

#### Model 6: MacDevice (MAB için Cihazlar)
```python
class MacDevice(Base):
    __tablename__ = "mac_devices"

    id = Column(Integer, primary_key=True)
    mac_address = Column(String(17), nullable=False, unique=True)
    device_name = Column(String(128))
    device_type = Column(String(64))
    groupname = Column(String(64), nullable=False, default="guest")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())
```

**Veriler Örneği:**
```
| id | mac_address    | device_name    | device_type | groupname | is_active |
|----|----------------|----------------|-------------|-----------|-----------|
| 1  | AA:BB:CC:DD... | Printer-A2     | printer     | devices   | true      |
| 2  | 11:22:33:44... | Scanner-B1     | scanner     | devices   | true      |
| 3  | XX:YY:ZZ:11... | LegacySwitch   | switch      | guest     | false     |
```

**Bağlantıları:**
- `routes/auth.py` → RadCheck, MacDevice sorgulaması
- `routes/authorize.py` → RadUserGroup, RadGroupReply, RadReply sorgulaması
- `routes/accounting.py` → RadAcct INSERT/UPDATE
- `routes/users.py` → RadCheck, RadUserGroup, RadGroupReply sorgulaması

**Kritik Noktalar:**
- Index'ler (`index=True`): username sık sorgulandığı için hızlı lookup
- `unique=True` (acctuniqueid): Duplicate session'ları önler
- `server_default=func.now()`: Veritabanı tarafında timestamp oluşur (timezone-safe)
- Tüm tablolar FreeRADIUS schema ile 1:1 uyum (Ek: MacDevice kendi tablo)

---

### 2.4 schemas.py

**Ne Yapar?**
Pydantic modelleri ile API request/response'larını valide eder. FreeRADIUS rlm_rest modülünün beklediği formata uygun.

**Detaylı İçeriği:**

#### Request Schemas

```python
class RadiusAuthRequest(BaseModel):
    """FreeRADIUS'un POST /auth yaptığı format."""
    username: str                           # Gerekli
    password: str | None = None             # PAP'de dolu, MAB'de boş
    calling_station_id: str | None = None   # MAB'de MAC adresi

    # Örnek JSON (PAP):
    # {"username": "alice", "password": "Alice123"}

    # Örnek JSON (MAB):
    # {"username": "AA:BB:CC:DD:EE:FF", "calling_station_id": "AA:BB:CC:DD:EE:FF"}
```

```python
class RadiusAuthorizeRequest(BaseModel):
    """FreeRADIUS'un POST /authorize yaptığı format."""
    username: str
    calling_station_id: str | None = None
```

```python
class RadiusAccountingRequest(BaseModel):
    """FreeRADIUS'un POST /accounting yaptığı format."""
    username: str
    acct_status_type: str                   # "Start", "Interim-Update", "Stop"
    acct_session_id: str
    acct_unique_session_id: str | None = None
    nas_ip_address: str = "0.0.0.0"
    nas_port_id: str | None = None
    acct_session_time: int = 0              # Saniye
    acct_input_octets: int = 0              # İndirilen bytes
    acct_output_octets: int = 0             # Yüklenen bytes
    acct_terminate_cause: str | None = None
    framed_ip_address: str | None = None
    calling_station_id: str | None = None
```

#### Response Schemas

```python
class AuthResponse(BaseModel):
    """Authentication endpoint'inin dönüş formatı."""
    result: str                             # "accept" veya "reject"
    reply_attributes: dict = {}             # RADIUS atribütleri
    message: str = ""

    # Örnek yanıt (Başarılı PAP):
    # {
    #   "result": "accept",
    #   "message": "Kimlik doğrulama başarılı."
    # }

    # Örnek yanıt (Başarılı MAB):
    # {
    #   "result": "accept",
    #   "reply_attributes": {
    #     "Tunnel-Type": "13",
    #     "Tunnel-Medium-Type": "6",
    #     "Tunnel-Private-Group-Id": "30"
    #   }
    # }
```

```python
class AuthorizeResponse(BaseModel):
    """Authorization endpoint'inin dönüş formatı."""
    result: str
    group: str | None = None                # Grup adı
    vlan_id: str | None = None              # VLAN ID
    reply_attributes: dict = {}
```

```python
class AccountingResponse(BaseModel):
    """Accounting endpoint'inin dönüş formatı."""
    result: str                             # "ok" veya "nok"
    message: str = ""
```

```python
class UserInfo(BaseModel):
    """GET /users endpoint'inin dönüş formatı."""
    username: str
    group: str | None = None
    is_online: bool = False
    vlan_id: str | None = None
```

```python
class ActiveSession(BaseModel):
    """GET /sessions/active endpoint'inin dönüş formatı."""
    username: str
    session_id: str
    nas_ip: str
    start_time: str                         # ISO 8601 format
    session_duration: int = 0                # Saniye
    input_octets: int = 0
    output_octets: int = 0
```

**Pydantic Validasyon Özellikleri:**
- Type hints: Otomatik type casting ve validation
- Default values: Eksik alanlar için default değer
- Optional fields: `str | None = None`
- JSON parsing: JSON → Python obje otomatik conversion
- OpenAPI schema generation: FastAPI dokümantasyonu otomatik oluşur

**Bağlantıları:**
- `routes/auth.py` → RadiusAuthRequest, AuthResponse
- `routes/authorize.py` → RadiusAuthorizeRequest, AuthorizeResponse
- `routes/accounting.py` → RadiusAccountingRequest, AccountingResponse
- `routes/users.py` → UserInfo
- `routes/sessions.py` → ActiveSession

**Kritik Noktalar:**
- Field names: camelCase veya snake_case FreeRADIUS'un beklentisine göre
- Type validation: `int` string verirse otomatik cast, başarısız olursa 422 error
- Optional fields: MAB'de `password=None` olabilir
- reply_attributes: Dictionary → Flexible atribütler için

---

### 2.5 main.py

**Ne Yapar?**
FastAPI uygulamasını oluşturur, route'ları kaydeder, startup/shutdown yönetir.

**Detaylı İçeriği:**

```python
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from routes import auth, authorize, accounting, users, sessions
from services.redis_service import redis_client
from database import engine

# Logging konfigürasyonu
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
```

#### Lifespan Context Manager (Startup/Shutdown)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Uygulama yaşam döngüsü.
    Başlangıç → Çalışma → Kapatılış
    """
    # ── Startup (App başlatıldığında) ──
    logger.info("NAC Policy Engine başlatılıyor...")

    # Redis bağlantı testi
    try:
        await redis_client.ping()
        logger.info("Redis bağlantısı başarılı.")
    except Exception as e:
        logger.error(f"Redis bağlantı hatası: {e}")

    logger.info("NAC Policy Engine hazır.")

    yield  # Uygulama burada çalışır

    # ── Shutdown (App kapatılırken) ──
    logger.info("NAC Policy Engine kapatılıyor...")
    await redis_client.close()      # Redis bağlantısını kapat
    await engine.dispose()          # DB connection pool'u kapat
    logger.info("Tüm bağlantılar kapatıldı.")
```

**Yaşam Döngüsü Akışı:**
```
1. FastAPI başlatılır → lifespan.__aenter__() çalışır
2. "NAC Policy Engine başlatılıyor..." → Redis ping test → Hazır log
3. yield → Uygulama çalışmaya başlar
4. Shutdown sinyali → lifespan.__aexit__() çalışır
5. Redis/PostgreSQL kapatılır → Temiz çıkış
```

#### FastAPI App Oluşturma

```python
app = FastAPI(
    title="NAC Policy Engine",
    description="FreeRADIUS rlm_rest entegrasyonu ile ağ erişim kontrolü",
    version="1.0.0",
    lifespan=lifespan,  # Startup/shutdown yöneticisi
)

# Routes Kaydı
app.include_router(auth.router, tags=["Authentication"])
app.include_router(authorize.router, tags=["Authorization"])
app.include_router(accounting.router, tags=["Accounting"])
app.include_router(users.router, tags=["Users"])
app.include_router(sessions.router, tags=["Sessions"])
```

**Tags:** OpenAPI dokümantasyonunda endpoint'leri gruplandırır.

#### Healthcheck Endpoint

```python
@app.get("/health")
async def health_check():
    """
    Docker healthcheck ve load balancer'lar bu endpoint'i kullanır.
    """
    health = {"status": "healthy", "services": {}}

    # Redis durumu
    try:
        await redis_client.ping()
        health["services"]["redis"] = "up"
    except Exception:
        health["services"]["redis"] = "down"
        health["status"] = "degraded"  # Tam healthy değil

    # PostgreSQL durumu
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
```

**Dönüş Örneği (Tümü Çalışır):**
```json
{
  "status": "healthy",
  "services": {
    "redis": "up",
    "postgres": "up"
  }
}
```

**Dönüş Örneği (Biri Down):**
```json
{
  "status": "degraded",
  "services": {
    "redis": "down",
    "postgres": "up"
  }
}
```

**Bağlantıları:**
- `database.py` → `engine` import eder
- `services/redis_service.py` → `redis_client` import eder
- `routes/*` → Route modüllerini import eder
- Tüm `routes/*` → FastAPI uygulamasına register edilir

**Kritik Noktalar:**
- Lifespan: Graceful shutdown sağlar
- Health endpoint: Monitoring sistem için kritik
- Async/await: Blocking işlem yok
- Startup failures: Hata durumunda log kaydedilir ancak uygulama başlar

**Docker Integration:**
```dockerfile
# Dockerfile'da healthcheck:
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

---

### 2.6 routes/auth.py

**Ne Yapar?**
POST `/auth` endpoint'inde PAP/CHAP ve MAB authentication'ını işler.

**Detaylı İçeriği:**

#### MAC Adres Normalizasyonu

```python
def normalize_mac(mac: str) -> str:
    """MAC adresini tutarlı formata çevirir: AA:BB:CC:DD:EE:FF"""
    clean = mac.replace("-", "").replace(".", "").replace(":", "").upper()
    if len(clean) != 12:
        return mac.upper()
    return ":".join(clean[i:i+2] for i in range(0, 12, 2))

# Örnekler:
# normalize_mac("AA-BB-CC-DD-EE-FF") → "AA:BB:CC:DD:EE:FF"
# normalize_mac("aabbccddeeff")       → "AA:BB:CC:DD:EE:FF"
# normalize_mac("AA:BB:CC:DD:EE:FF")  → "AA:BB:CC:DD:EE:FF"
```

#### Main Auth Endpoint

```python
@router.post("/auth", response_model=AuthResponse)
async def authenticate(
    request: RadiusAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    PAP/CHAP veya MAB kimlik doğrulaması.
    """
    username = request.username
    logger.info(f"Auth isteği geldi: username={username}")

    # ── 1. MAB Tespiti ──
    is_mab = request.calling_station_id is not None and (
        request.password is None or
        request.password == "" or
        request.password == request.username  # MAC olarak gelen
    )

    if is_mab:
        return await _handle_mab(request.calling_station_id or username, db)

    # ── 2. PAP/CHAP Doğrulaması ──
    return await _handle_pap(username, request.password or "", db)
```

**Mantık:**
- MAB: `calling_station_id` varsa VE `password` yoksa/boşsa → MAC Authentication
- PAP: `password` dolu → Şifre-based authentication

#### PAP Doğrulaması

```python
async def _handle_pap(username: str, password: str, db: AsyncSession) -> AuthResponse:
    """PAP/CHAP şifre tabanlı doğrulama."""

    # 1. Rate limit kontrolü
    if await is_rate_limited(username):
        remaining = await get_remaining_lockout(username)
        logger.warning(f"Kullanıcı kilitli: {username}, kalan süre: {remaining}s")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Hesap geçici olarak kilitli. {remaining} saniye sonra tekrar deneyin.",
        )

    # 2. Veritabanından kullanıcı bilgisi çek
    stmt = select(RadCheck).where(
        RadCheck.username == username,
        RadCheck.attribute == "Cleartext-Password",
    )
    result = await db.execute(stmt)
    user_record = result.scalar_one_or_none()

    if user_record is None:
        await record_failed_attempt(username)
        logger.info(f"Kullanıcı bulunamadı: {username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı.",
        )

    # 3. Şifre Kontrolü
    if password != user_record.value:
        attempts = await record_failed_attempt(username)
        remaining_attempts = max(0, 5 - attempts)
        logger.info(f"Yanlış şifre: {username}, kalan deneme: {remaining_attempts}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Yanlış şifre. Kalan deneme: {remaining_attempts}",
        )

    # 4. Başarılı Giriş
    await reset_attempts(username)
    logger.info(f"Başarılı auth: {username}")

    return AuthResponse(
        result="accept",
        message="Kimlik doğrulama başarılı.",
    )
```

**Rate Limiting Entegrasyonu:**
```
Deneme 1: FAIL → Redis: auth_fail:alice = 1 (TTL=300s)
Deneme 2: FAIL → Redis: auth_fail:alice = 2
Deneme 3: FAIL → Redis: auth_fail:alice = 3
Deneme 4: FAIL → Redis: auth_fail:alice = 4
Deneme 5: FAIL → Redis: auth_fail:alice = 5 (Locked!)
Deneme 6: → HTTP 429 "Hesap geçici olarak kilitli"
Deneme sonrası SUCCESS → Redis key silinir (reset)
```

#### MAB Doğrulaması

```python
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
        # Bilinmeyen cihaz → guest VLAN'a yönlendir
        logger.info(f"Bilinmeyen MAC adresi, guest VLAN'a yönlendiriliyor: {mac}")
        return AuthResponse(
            result="accept",
            message="Bilinmeyen cihaz — guest VLAN atandı.",
            reply_attributes={
                "Tunnel-Type": "13",             # VLAN tunneling
                "Tunnel-Medium-Type": "6",       # IEEE 802
                "Tunnel-Private-Group-Id": "30", # Guest VLAN
            },
        )

    logger.info(f"MAB başarılı: {mac} → grup={device.groupname}")
    return AuthResponse(
        result="accept",
        message=f"Cihaz doğrulandı: {device.device_name}",
    )
```

**Mantık:**
- MAC varsa ve aktifse → accept
- MAC yoksa → accept (guest VLAN ile)

**RADIUS Atribütleri:**
- `Tunnel-Type=13` → VLAN tunneling
- `Tunnel-Medium-Type=6` → IEEE 802
- `Tunnel-Private-Group-Id=30` → VLAN 30

**Bağlantıları:**
- `database.py` → `get_db` dependency
- `models.py` → RadCheck, MacDevice ORM sınıfları
- `schemas.py` → RadiusAuthRequest, AuthResponse
- `services/rate_limiter.py` → Rate limiting fonksiyonları

**Kritik Noktalar:**
- Cleartext-Password: Production'da bcrypt hash kullanılmalı
- Rate limiting: Brute-force saldırılarını önler
- MAB güvenliği: MAC spoofing tehdidi altında
- HTTP status codes: 401, 429, 200 doğru şekilde kullanılır

---

### 2.7 routes/authorize.py

**Ne Yapar?**
POST `/authorize` endpoint'inde grup-based VLAN atama ve policy döner.

**Detaylı İçeriği:**

#### MAC Normalizasyonu
```python
def normalize_mac(mac: str) -> str:
    # (auth.py ile aynı)
```

#### Main Authorize Endpoint

```python
@router.post("/authorize", response_model=AuthorizeResponse)
async def authorize(
    request: RadiusAuthorizeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Kullanıcının grubunu belirleyip VLAN ve policy atribütlerini döner.
    """
    username = request.username
    logger.info(f"Authorize isteği: username={username}")

    # ── 1. MAB Kontrolü ──
    if request.calling_station_id:
        mac = normalize_mac(request.calling_station_id)
        stmt = select(MacDevice).where(
            MacDevice.mac_address == mac,
            MacDevice.is_active == True,
        )
        result = await db.execute(stmt)
        device = result.scalar_one_or_none()

        if device:
            group = device.groupname
            return await _build_authorize_response(group, db)

        # Bilinmeyen cihaz → guest
        return AuthorizeResponse(
            result="accept",
            group="guest",
            vlan_id="30",
            reply_attributes={
                "Tunnel-Type": "13",
                "Tunnel-Medium-Type": "6",
                "Tunnel-Private-Group-Id": "30",
            },
        )

    # ── 2. Normal Kullanıcı ──
    stmt = select(RadUserGroup).where(
        RadUserGroup.username == username
    ).order_by(RadUserGroup.priority)
    result = await db.execute(stmt)
    user_group = result.scalar_one_or_none()

    if user_group is None:
        logger.warning(f"Kullanıcı grubunda değil: {username}")
        return AuthorizeResponse(
            result="reject",
            message="Kullanıcı herhangi bir gruba atanmamış.",
        )

    group = user_group.groupname

    # Grup atribütlerini al
    response = await _build_authorize_response(group, db)

    # Kullanıcı-spesifik reply atribütlerini ekle
    stmt = select(RadReply).where(RadReply.username == username)
    result = await db.execute(stmt)
    user_replies = result.scalars().all()
    for reply in user_replies:
        response.reply_attributes[reply.attribute] = reply.value

    return response
```

**Akış:**
1. MAB mi? → MacDevice'ı sor
2. Hayır → RadUserGroup'tan grup bul
3. Grup var mı? → Yes: continue, No: reject
4. Grup atribütlerini al (radgroupreply)
5. Kullanıcı-spesifik atribütleri ekle (radreply)

#### Authorization Response Builder

```python
async def _build_authorize_response(
    group: str,
    db: AsyncSession,
) -> AuthorizeResponse:
    """Grup bazlı atribütleri toplayıp AuthorizeResponse oluşturur."""

    # Grup atribütlerini çek
    stmt = select(RadGroupReply).where(RadGroupReply.groupname == group)
    result = await db.execute(stmt)
    group_replies = result.scalars().all()

    reply_attrs = {}
    vlan_id = None

    for attr in group_replies:
        reply_attrs[attr.attribute] = attr.value
        if attr.attribute == "Tunnel-Private-Group-Id":
            vlan_id = attr.value

    logger.info(f"Authorize sonucu: grup={group}, VLAN={vlan_id}")

    return AuthorizeResponse(
        result="accept",
        group=group,
        vlan_id=vlan_id,
        reply_attributes=reply_attrs,
    )
```

**Örnekler:**

**Staff grubu (VLAN 10):**
```
RadGroupReply:
├── (staff, Tunnel-Type, 13)
├── (staff, Tunnel-Medium-Type, 6)
└── (staff, Tunnel-Private-Group-Id, 10)

Sonuç:
{
  "result": "accept",
  "group": "staff",
  "vlan_id": "10",
  "reply_attributes": {
    "Tunnel-Type": "13",
    "Tunnel-Medium-Type": "6",
    "Tunnel-Private-Group-Id": "10"
  }
}
```

**Guest grubu (VLAN 30):**
```
{
  "result": "accept",
  "group": "guest",
  "vlan_id": "30",
  "reply_attributes": {
    "Tunnel-Type": "13",
    "Tunnel-Medium-Type": "6",
    "Tunnel-Private-Group-Id": "30"
  }
}
```

**Bağlantıları:**
- `database.py` → `get_db` dependency
- `models.py` → RadUserGroup, RadGroupReply, RadReply, MacDevice
- `schemas.py` → RadiusAuthorizeRequest, AuthorizeResponse

**Kritik Noktalar:**
- Zincir mantığı: User → Group → VLAN
- Priority: Kullanıcı birden fazla gruba aitse, priority en düşük seçilir
- Kullanıcı-spesifik overrides: RadReply grup atribütlerini geçersiz kılabilir
- Bilinmeyen cihazlar guest VLAN'a yönlendirilir

---

### 2.8 routes/accounting.py

**Ne Yapar?**
POST `/accounting` endpoint'inde oturum başlangıcı, periyodik güncellemeler ve kapanış olaylarını kaydeder.

**Detaylı İçeriği:**

#### Main Accounting Endpoint

```python
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

    if status in ("start",):
        return await _handle_start(request, db)
    elif status in ("interimupdate", "interim", "alive"):
        return await _handle_interim(request, db)
    elif status in ("stop",):
        return await _handle_stop(request, db)
    else:
        logger.warning(f"Bilinmeyen accounting status: {request.acct_status_type}")
        return AccountingResponse(result="ok", message="Bilinmeyen status tipi.")
```

#### Handle Start (Oturum Başlangıcı)

```python
async def _handle_start(
    req: RadiusAccountingRequest,
    db: AsyncSession,
) -> AccountingResponse:
    """Oturum başlangıcı — yeni kayıt oluştur."""

    now = datetime.now(timezone.utc)
    unique_id = req.acct_unique_session_id or req.acct_session_id

    # PostgreSQL'e kaydet
    acct = RadAcct(
        acctsessionid=req.acct_session_id,
        acctuniqueid=unique_id,
        username=req.username,
        nasipaddress=req.nas_ip_address,
        nasportid=req.nas_port_id,
        acctstarttime=now,
        acctupdatetime=now,
        framedipaddress=req.framed_ip_address,
        callingstation=req.calling_station_id,
        acctstatustype="Start",
    )
    db.add(acct)
    await db.flush()  # ID oluştur, commit etme

    # Redis'e aktif oturum cache'le
    session_data = {
        "username": req.username,
        "session_id": req.acct_session_id,
        "nas_ip": req.nas_ip_address,
        "start_time": now.isoformat(),
        "session_duration": 0,
        "input_octets": 0,
        "output_octets": 0,
    }
    redis_key = f"{ACTIVE_SESSION_PREFIX}{unique_id}"
    await redis_client.set(redis_key, json.dumps(session_data))

    # Kullanıcının aktif oturum listesine ekle
    user_sessions_key = f"user_sessions:{req.username}"
    await redis_client.sadd(user_sessions_key, unique_id)

    logger.info(f"Oturum başlatıldı: {req.username} / {req.acct_session_id}")
    return AccountingResponse(result="ok", message="Oturum başlatıldı.")
```

**Redis Yapısı (Start sonrası):**
```
Redis:
  session:<session_id> = '{"username":"alice", "start_time":"2025-03-23T...", ...}'
  user_sessions:alice = SET{<session_id1>, <session_id2>}
```

#### Handle Interim (Periyodik Güncelleme)

```python
async def _handle_interim(
    req: RadiusAccountingRequest,
    db: AsyncSession,
) -> AccountingResponse:
    """Periyodik güncelleme — mevcut kaydı güncelle."""

    now = datetime.now(timezone.utc)
    unique_id = req.acct_unique_session_id or req.acct_session_id

    # PostgreSQL güncelle
    stmt = (
        update(RadAcct)
        .where(RadAcct.acctuniqueid == unique_id)
        .values(
            acctupdatetime=now,
            acctsessiontime=req.acct_session_time,      # Oturum süresi (s)
            acctinputoctets=req.acct_input_octets,      # İndirilen bytes
            acctoutputoctets=req.acct_output_octets,    # Yüklenen bytes
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

    logger.info(f"Oturum güncellendi: {req.username} / süre={req.acct_session_time}s")
    return AccountingResponse(result="ok", message="Oturum güncellendi.")
```

**Periyodiklik:** FreeRADIUS her 15 dakikada bir (default) Interim-Update gönderir.

#### Handle Stop (Oturum Kapanışı)

```python
async def _handle_stop(
    req: RadiusAccountingRequest,
    db: AsyncSession,
) -> AccountingResponse:
    """Oturum sonu — kaydı kapat ve Redis'ten temizle."""

    now = datetime.now(timezone.utc)
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
            acctterminatecause=req.acct_terminate_cause,  # User-Request, Idle-Timeout vb.
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

    logger.info(
        f"Oturum sonlandı: {req.username} / "
        f"süre={req.acct_session_time}s, "
        f"neden={req.acct_terminate_cause}"
    )
    return AccountingResponse(result="ok", message="Oturum sonlandırıldı.")
```

**Kapanış Nedenleri:**
- `User-Request` — Kullanıcı logout etti
- `Idle-Timeout` — İnaktif timeout
- `Session-Timeout` — Session timeout
- `Admin-Reset` — Admin tarafından reset

**Bağlantıları:**
- `database.py` → `get_db` dependency
- `models.py` → RadAcct ORM sınıfı
- `schemas.py` → RadiusAccountingRequest, AccountingResponse
- `services/redis_service.py` → redis_client

**Kritik Noktalar:**
- Unique ID: Session deduplication için kritik
- Redis caching: Anlık online user listesi için
- Flush vs commit: Flush DB ID'yi oluşturur, commit veritabanında kalıcı kılır
- Terminate cause: Kapalanış analizi için

---

### 2.9 routes/users.py

**Ne Yapar?**
GET `/users` endpoint'inde tüm kayıtlı kullanıcıları ve online durumlarını döner.

**Detaylı İçeriği:**

```python
@router.get("/users", response_model=list[UserInfo])
async def list_users(db: AsyncSession = Depends(get_db)):
    """
    Tüm kayıtlı kullanıcıları listeler.
    Her kullanıcı için grup, VLAN ve online durumu döner.
    """

    # 1. Tüm benzersiz kullanıcı adlarını çek
    stmt = select(distinct(RadCheck.username))
    result = await db.execute(stmt)
    usernames = [row[0] for row in result.all()]

    users = []
    for username in usernames:
        # 2. Kullanıcının grubunu bul
        stmt = select(RadUserGroup).where(
            RadUserGroup.username == username
        ).order_by(RadUserGroup.priority)
        result = await db.execute(stmt)
        user_group = result.scalar_one_or_none()

        group = user_group.groupname if user_group else None
        vlan_id = None

        # 3. Grubun VLAN ID'sini bul
        if group:
            stmt = select(RadGroupReply).where(
                RadGroupReply.groupname == group,
                RadGroupReply.attribute == "Tunnel-Private-Group-Id",
            )
            result = await db.execute(stmt)
            vlan_reply = result.scalar_one_or_none()
            if vlan_reply:
                vlan_id = vlan_reply.value

        # 4. Redis'te aktif oturumu var mı kontrol et
        user_sessions_key = f"user_sessions:{username}"
        active_count = await redis_client.scard(user_sessions_key)
        is_online = active_count > 0

        users.append(UserInfo(
            username=username,
            group=group,
            is_online=is_online,
            vlan_id=vlan_id,
        ))

    logger.info(f"Kullanıcı listesi döndürüldü: {len(users)} kullanıcı")
    return users
```

**Örnek Dönüş:**
```json
[
  {
    "username": "alice",
    "group": "staff",
    "is_online": true,
    "vlan_id": "10"
  },
  {
    "username": "bob",
    "group": "guest",
    "is_online": false,
    "vlan_id": "30"
  },
  {
    "username": "charlie",
    "group": "students",
    "is_online": true,
    "vlan_id": "20"
  }
]
```

**Bağlantıları:**
- `database.py` → `get_db` dependency
- `models.py` → RadCheck, RadUserGroup, RadGroupReply
- `schemas.py` → UserInfo
- `services/redis_service.py` → redis_client (online status için)

**Kritik Noktalar:**
- N+1 query problem: Her kullanıcı için ayrı query çalışır (optimize edilebilir)
- Online status: Redis'teki `user_sessions:*` SET'lerinden okunur
- VLAN lookup: Group varsa, grup atribütlerinden çekilir

---

### 2.10 routes/sessions.py

**Ne Yapar?**
GET `/sessions/active` endpoint'inde Redis cache'inde depolanan aktif oturumları hızlı döner.

**Detaylı İçeriği:**

```python
@router.get("/sessions/active", response_model=list[ActiveSession])
async def get_active_sessions():
    """
    Redis'teki tüm aktif oturumları döndürür.

    SCAN komutu kullanılıyor — KEYS * yerine tercih edilmeli çünkü:
    - KEYS tüm key'leri tek seferde tarar → büyük veri setlerinde Redis'i bloklar
    - SCAN cursor-based iterasyon yapar → non-blocking'dir
    """
    sessions = []

    # SCAN ile "session:" prefix'li tüm key'leri tara
    cursor = 0
    while True:
        # Cursor-based iteration
        cursor, keys = await redis_client.scan(
            cursor=cursor,
            match=f"{ACTIVE_SESSION_PREFIX}*",  # "session:*" pattern
            count=100,                          # Her iterasyonda ~100 key kontrol et
        )

        for key in keys:
            raw = await redis_client.get(key)
            if raw:
                try:
                    data = json.loads(raw)
                    sessions.append(ActiveSession(
                        username=data.get("username", ""),
                        session_id=data.get("session_id", ""),
                        nas_ip=data.get("nas_ip", ""),
                        start_time=data.get("start_time", ""),
                        session_duration=data.get("session_duration", 0),
                        input_octets=data.get("input_octets", 0),
                        output_octets=data.get("output_octets", 0),
                    ))
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Bozuk session verisi: key={key}, hata={e}")

        # cursor 0'a dönünce tarama bitti
        if cursor == 0:
            break

    logger.info(f"Aktif oturum sayısı: {len(sessions)}")
    return sessions
```

**SCAN vs KEYS Karşılaştırması:**

```
KEYS *:
├── Tüm key'leri bir shot'ta tarar
├── Big O: O(N) blocking operation
└── Büyük Redis'lerde sorun

SCAN:
├── Cursor-based iterasyon
├── Non-blocking
├── Big O: O(N) ama distributed
└── Production-recommended
```

**Örnek SCAN Akışı:**
```
Iterasyon 1: cursor=0 → SCAN → cursor=42, keys=[session:123, session:456, ...]
Iterasyon 2: cursor=42 → SCAN → cursor=84, keys=[session:789, ...]
Iterasyon 3: cursor=84 → SCAN → cursor=0, keys=[...] (Done!)
```

**Örnek Dönüş:**
```json
[
  {
    "username": "alice",
    "session_id": "abc123def456",
    "nas_ip": "192.168.1.10",
    "start_time": "2025-03-23T14:30:00",
    "session_duration": 3600,
    "input_octets": 1024000,
    "output_octets": 2048000
  },
  {
    "username": "bob",
    "session_id": "xyz789uvw012",
    "nas_ip": "192.168.1.10",
    "start_time": "2025-03-23T15:00:00",
    "session_duration": 1800,
    "input_octets": 512000,
    "output_octets": 1024000
  }
]
```

**Bağlantıları:**
- `schemas.py` → ActiveSession
- `services/redis_service.py` → redis_client

**Kritik Noktalar:**
- SCAN cursor: 0'a dönene kadar devam etmeli
- count parameter: Hint'tir, exact count değil
- JSON parsing errors: Corrupted session data'yı handle etme
- Performance: Redis'e tek gitmesi sayesinde hızlı

---

### 2.11 services/redis_service.py

**Ne Yapar?**
Async Redis client'ını oluşturur ve connection pool'unu yönetir.

**Detaylı İçeriği:**

```python
import redis.asyncio as redis
from config import settings

# Async Redis client — connection pool otomatik yönetilir
redis_client = redis.from_url(
    settings.REDIS_URL,           # "redis://localhost:6379/0"
    decode_responses=True,         # bytes yerine str döndür
)

async def get_redis() -> redis.Redis:
    """Redis client'ı döndürür (FastAPI dependency için)."""
    return redis_client
```

**redis.asyncio Özellikleri:**
- Async/await support: Non-blocking I/O
- Connection pooling: Otomatik bağlantı havuzu
- decode_responses: Binary yerine string döner

**Örnek Kullanım:**
```python
from services.redis_service import redis_client

# Key-value set
await redis_client.set("mykey", "myvalue")

# Key-value get
value = await redis_client.get("mykey")  # "myvalue" (bytes değil, str)

# Atomic increment
count = await redis_client.incr("counter")

# TTL set
await redis_client.expire("mykey", 300)  # 5 dakika

# Set operations
await redis_client.sadd("myset", "member1", "member2")
count = await redis_client.scard("myset")

# SCAN
cursor, keys = await redis_client.scan(cursor=0, match="pattern:*")
```

**Connection URL Format:**
```
redis://[:password]@host:port/db
┌──────┬──────────┬──────┬──┐
│      │password  │port  │db│
redis://user:pass@localhost:6379/0

- host: localhost (default)
- port: 6379 (default)
- db: 0 (default)
```

**Bağlantıları:**
- `config.py` → `settings.REDIS_URL`
- Tüm route'lar → `redis_client` import eder
- `services/rate_limiter.py` → `redis_client` kullanır

**Kritik Noktalar:**
- `decode_responses=True`: String handling kolaylaştırır
- Connection pooling: Otomatik ama configurability sınırlanır
- Async driver: Sync driver (`redis-py`) değil, `redis.asyncio` kullanılmalı
- URL parsing: Invalid URL'ler başlangıçta değil, ilk işlemde fail olur

---

### 2.12 services/rate_limiter.py

**Ne Yapar?**
Başarısız login denemelerini Redis ile sayarak brute-force saldırılarını önler.

**Detaylı İçeriği:**

```python
from services.redis_service import redis_client
from config import settings

# Global config:
# MAX_AUTH_ATTEMPTS = 5
# AUTH_LOCKOUT_SECONDS = 300 (5 dakika)
```

#### 1. Rate Limited Check

```python
async def is_rate_limited(username: str) -> bool:
    """Kullanıcının kilitli olup olmadığını kontrol eder."""
    key = f"auth_fail:{username}"
    attempts = await redis_client.get(key)

    if attempts is None:
        return False  # Key yoksa, kilitli değil

    return int(attempts) >= settings.MAX_AUTH_ATTEMPTS
```

#### 2. Record Failed Attempt

```python
async def record_failed_attempt(username: str) -> int:
    """Başarısız girişi kaydeder, güncel deneme sayısını döndürür."""
    key = f"auth_fail:{username}"

    # INCR atomik — race condition olmaz
    current = await redis_client.incr(key)

    # İlk denemede TTL ayarla (sonraki denemeler TTL'yi etkilemez)
    if current == 1:
        await redis_client.expire(key, settings.AUTH_LOCKOUT_SECONDS)

    return current
```

**INCR Atomicity (Race Condition Yok):**
```
Thread 1          Thread 2          Redis Key
─────────────────────────────────────────────
                                    auth_fail:alice = 0
INCR (locked)
                  (waiting)
  → 1
(unlock)
                  INCR (locked)     auth_fail:alice = 1
                    → 2
                  (unlock)          auth_fail:alice = 2
```

#### 3. Reset Attempts

```python
async def reset_attempts(username: str) -> None:
    """Başarılı giriş sonrası sayacı sıfırlar."""
    key = f"auth_fail:{username}"
    await redis_client.delete(key)
```

#### 4. Get Remaining Lockout

```python
async def get_remaining_lockout(username: str) -> int:
    """Kilitli kullanıcının kalan bekleme süresini döndürür (saniye)."""
    key = f"auth_fail:{username}"
    ttl = await redis_client.ttl(key)
    return max(0, ttl)
```

**TTL Return Values:**
- `-2`: Key yoksa
- `-1`: Key var ama TTL yok
- Pozitif sayı: Kalan saniye

**Timeline Örneği:**

```
Saat 14:00:00 → Deneme 1 FAIL
  Redis: auth_fail:alice = 1, TTL = 300s

Saat 14:00:05 → Deneme 2 FAIL
  Redis: auth_fail:alice = 2, TTL = 295s (EXPIRE reset olmadı)

Saat 14:00:10 → Deneme 3 FAIL
  Redis: auth_fail:alice = 3, TTL = 290s

Saat 14:00:15 → Deneme 4 FAIL
  Redis: auth_fail:alice = 4, TTL = 285s

Saat 14:00:20 → Deneme 5 FAIL
  Redis: auth_fail:alice = 5, TTL = 280s (NOW LOCKED!)

Saat 14:00:25 → Deneme 6
  is_rate_limited() → true
  HTTP 429 "Hesap kilitli. 275 saniye sonra tekrar deneyin."

Saat 14:05:20 → Deneme (başarılı)
  TTL sona erdi, key otomatik silinir
  redis_client.delete() (redundant ama safe)
  reset_attempts() → OK

Saat 14:05:21 → Yeni deneme
  auth_fail:alice key yoksa → is_rate_limited() = false → OK
```

**Bağlantıları:**
- `services/redis_service.py` → `redis_client`
- `config.py` → `settings.MAX_AUTH_ATTEMPTS`, `settings.AUTH_LOCKOUT_SECONDS`
- `routes/auth.py` → Tüm fonksiyonları import eder

**Kritik Noktalar:**
- Fixed window: `acct_status_type="Stop"` kapanışa kadar counter devam eder
- INCR atomicity: SQL'de manual locking yerine Redis INCR kullanır
- EXPIRE timing: İlk denemede set edilir, sonraki denemeler TTL'yi reset etmez (istenen davranış)
- max(0, ttl): Negative TTL değerlerini 0'a clamp eder

---

## Versiyon Kontrolü ve .gitignore

### __init__.py Files

```
api/routes/__init__.py → Boş veya minimal (package marker)
api/services/__init__.py → Boş veya minimal (package marker)
```

### __pycache__ Yönetimi

**.gitignore İçeriği:**
```gitignore
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.env
```

**Neden:**
- __pycache__: Python bytecode cache, rebuild edilir
- .env: Sensitive credentials, repository'ye gelmemeli
- venv/: Virtual environment, project-spesifik

---

## Mimari Özet Tablosu

| Katman | Dosya | Sorumluluk | Bağımlılıklar |
|--------|-------|-----------|---------------|
| **Config** | config.py | Environment loading | Pydantic-settings |
| **Database** | database.py | Session management | SQLAlchemy async |
| **ORM** | models.py | Table definitions | SQLAlchemy |
| **Validation** | schemas.py | Request/Response | Pydantic |
| **Main** | main.py | App initialization | FastAPI |
| **Auth** | routes/auth.py | PAP/MAB authentication | DB, Redis, Rate limiter |
| **Authorize** | routes/authorize.py | VLAN assignment | DB |
| **Accounting** | routes/accounting.py | Session logging | DB, Redis |
| **Users** | routes/users.py | User listing | DB, Redis |
| **Sessions** | routes/sessions.py | Active sessions | Redis |
| **Redis** | services/redis_service.py | Cache management | redis.asyncio |
| **Rate Limiter** | services/rate_limiter.py | Brute-force protection | Redis |

---

## İmport Bağımlılıkları Grafiği

```
main.py
  ├─→ routes/auth.py
  │    ├─→ database.py (get_db)
  │    ├─→ models.py (RadCheck, MacDevice)
  │    ├─→ schemas.py (RadiusAuthRequest, AuthResponse)
  │    └─→ services/rate_limiter.py
  │
  ├─→ routes/authorize.py
  │    ├─→ database.py (get_db)
  │    ├─→ models.py (RadUserGroup, RadGroupReply, RadReply, MacDevice)
  │    └─→ schemas.py (RadiusAuthorizeRequest, AuthorizeResponse)
  │
  ├─→ routes/accounting.py
  │    ├─→ database.py (get_db)
  │    ├─→ models.py (RadAcct)
  │    ├─→ schemas.py (RadiusAccountingRequest, AccountingResponse)
  │    └─→ services/redis_service.py
  │
  ├─→ routes/users.py
  │    ├─→ database.py (get_db)
  │    ├─→ models.py (RadCheck, RadUserGroup, RadGroupReply)
  │    ├─→ schemas.py (UserInfo)
  │    └─→ services/redis_service.py
  │
  ├─→ routes/sessions.py
  │    ├─→ schemas.py (ActiveSession)
  │    └─→ services/redis_service.py
  │
  ├─→ database.py
  │    ├─→ config.py (settings.DATABASE_URL)
  │    └─→ models.py (Base)
  │
  └─→ services/redis_service.py
       └─→ config.py (settings.REDIS_URL)

services/rate_limiter.py
  ├─→ services/redis_service.py
  └─→ config.py (MAX_AUTH_ATTEMPTS, AUTH_LOCKOUT_SECONDS)
```

---

## Tasarım Prensipleri

### 1. **Separation of Concerns (Kaygıların Ayrılması)**
- Config: Environment management
- Database: SQL operations
- Models: Data structure
- Schemas: Validation
- Routes: API endpoints
- Services: Business logic

### 2. **Dependency Injection**
```python
@router.post("/auth")
async def authenticate(
    request: RadiusAuthRequest,
    db: AsyncSession = Depends(get_db),  # Injected
):
    pass
```

### 3. **Async/Non-blocking I/O**
- SQLAlchemy async
- redis.asyncio
- FastAPI async handlers

### 4. **Atomic Operations**
- Redis INCR: Race-condition-free
- DB transactions: Automatic rollback

### 5. **Caching Strategy**
- Active sessions: Redis (fast lookup)
- User groups: Database (read once, cache)
- Rate limits: Redis (atomic counters)

---

## Öğrenme Çıkışları

Bu mimariye bakarak öğrenilen:
1. **Async Python**: FastAPI, SQLAlchemy async, redis.asyncio
2. **Database Patterns**: ORM, connection pooling, transactions
3. **Caching**: Redis SCAN, TTL management, key naming
4. **API Design**: Request/response validation, dependency injection
5. **Security**: Rate limiting, MAC validation, cleartext warning
6. **Monitoring**: Healthcheck, logging, graceful shutdown

---

**Oluşturma Tarihi:** 2025-03-23
**Versiyon:** 1.0.0
**NAC Policy Engine** — FreeRADIUS rlm_rest entegrasyonu ile ağ erişim kontrolü
