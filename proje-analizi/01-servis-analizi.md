# Docker-Compose Servisleri Analizi — NAC Sistemi

Sistem dört kritik servisten oluşur: PostgreSQL (veri), Redis (cache), FastAPI (politika motoru), FreeRADIUS (kimlik doğrulama). Bu dokümantasyon her servisin sorumluluğunu, yapılandırmasını ve birbirleriyle etkileşimini açıklar.

---

## PostgreSQL — Kullanıcı, grup ve muhasebe veritabanı

### Sorumluluğu ve Mimarisi

**Amaç:** PostgreSQL, NAC sisteminin merkezi veri deposudur. Kullanıcı hesapları, cihaz bilgileri, ağ erişim politikaları ve muhasebe kayıtlarını saklar. ACID garantileri ve işlem tutarlılığı ile veri bütünlüğünü sağlar. Tüm kalıcı veri bu serviste depolanır.

**Bu servis olmasaydı sistem nasıl davranırdı?**
Sistem hiçbir veri saklayamaz, yeniden başlatıldıktan sonra tüm bilgiler kaybedilirdi. Kullanıcı kimlik doğrulaması yapılamaz, politika kararları alınamaz. NAC tamamen işlevsiz hale gelir.

### Base Image Seçimi

**Image:** `postgres:18-alpine`

**Neden bu image?**
- **Alpine:** Sadece 66 MB boyut (tam imajdan 200+ MB küçük). Container başlangıç süresi hızlı, güvenlik yama alanı minimal.
- **PostgreSQL 18:** En son stabil sürüm (2024 itibaren). Performans iyileştirmeleri, JSON işlemleri, paralel sorgu yeteneği.
- **Lightweight:** Sadece gerekli paketler içerir. Ürün ortamı için uygun.

**Bağımlılıklar:**
- PostgreSQL server (18.0)
- libc, libssl (TLS/SSL bağlantılar için)
- pg_isready aracı (healthcheck için)

### Environment Variables

| Variable | Amaç | Örnek | Kaynaktan Yükleme |
|----------|------|-------|------------------|
| POSTGRES_DB | İlk oluşturulacak veritabanı adı | `nac` | .env dosyası |
| POSTGRES_USER | Veritabanı yöneticisi kullanıcı adı | `postgres` | .env dosyası |
| POSTGRES_PASSWORD | PostgreSQL superuser şifresi | `secure_password_123` | .env dosyası |

**Yükleme Mekanizması:**
`env_file: .env` — Docker, .env dosyasını okur ve içindeki `KEY=VALUE` çiftlerini environment variable olarak konteyner içine enjekte eder. `environment:` bölümündeki `${POSTGRES_DB}` gibi referanslar .env'den çekilen değerlerle değiştirilir. Bu yaklaşım şifreli değerleri compose dosyasında görmek istemediğimiz zaman kullanılır (version control'e giremez).

### Direktifler ve Davranışları

**image: postgres:18-alpine**
- Docker Hub'dan önceden derlenmiş imajı kullan, Dockerfile ile inşa etme.
- Kurulumda vakit kazandırır, resmi PostgreSQL takımının testi almış imajdır.

**container_name: nac-postgres**
- Container'a sabit ad verir. Network içinde DNS (`postgres` hostname) olarak erişilebilir hale gelir.
- İnsan okunabilir log ve hata mesajları.

**env_file: .env**
- Proje kökünde `.env` dosyası arar, içindeki tüm `KEY=VALUE` satırlarını environment'e yükler.

**environment:**
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` — PostgreSQL imajı bu değişkenleri tanır ve başlatıldığında veritabanını ve superuser'ı bu parametrelerle oluşturur.

**Ports:**
- `5432:5432` — Host'un 5432 portuna gelen istekler konteyner'ın 5432'ye yönlendirilir. Yerel geliştirme için `psql -h localhost -p 5432 -U postgres` ile bağlantı sağlanabilir. Prodüksyon'da bu port kapalı olmalı (sadece nac-network üzerinde erişim).

**Volumes:**
```yaml
- pg_data:/var/lib/postgresql/data        # Named volume — kalıcı veri
- ./db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro  # Bind mount
```

1. **pg_data:/var/lib/postgresql/data**
   - Named volume — Docker'ın kontrol ettiği kalıcı depolama.
   - Konteyner silinse bile pg_data hacmi kalır. `docker volume ls` ile görülebilir.
   - Container başladığında PostgreSQL veri dosyaları bu hacim altında tutulur.
   - `docker-compose down` yapılsa bile veri kaybolmaz; `docker-compose up` tekrar veriyi okur.

2. **./db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro**
   - Bind mount — host'un `./db/init.sql` dosyası doğrudan konteyner'daki `/docker-entrypoint-initdb.d/` klasörüne bağlanır.
   - `:ro` (read-only) — konteyner dosyayı değiştiremez; sadece okuyabilir.
   - PostgreSQL imajı `/docker-entrypoint-initdb.d/` klasöründeki `.sql` dosyalarını ilk başlatmada otomatik olarak çalıştırır.
   - Tablolar, indeksler, örnek veriler bu SQL dosyasında oluşturulabilir.

**networks: nac-network**
- Container, nac-network (172.20.0.0/24) bridge ağına katılır.
- Diğer konteynerler `postgres` hostname'ı (DNS) ile bu servise bağlanabilir.

**depends_on: (implicit — başka servis ona bağlı)**
- PostgreSQL bir başka servise bağlı değil; tüm servislerin temeli.

**healthcheck:**
```yaml
test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
interval: 5s
timeout: 3s
retries: 5
```
- **Test:** `pg_isready` PostgreSQL'e bağlanmayı dener. Başarılıysa exit code 0, başarısızsa sıfırdan farklı.
  - `-U ${POSTGRES_USER}` — kullanıcı adını belirler.
  - `-d ${POSTGRES_DB}` — veritabanı adını belirler.
- **interval: 5s** — Her 5 saniyede bir healthcheck çalıştırılır.
- **timeout: 3s** — pg_isready komutu 3 saniye içinde cevap vermezse "başarısız" sayılır.
- **retries: 5** — 5 üst üste başarısızlık sonunda konteyner "unhealthy" işaretlenir.
- **Sonuç:** PostgreSQL bağlantı kabul ettiğinde "healthy" olur. FastAPI ve FreeRADIUS "depends_on: postgres: service_healthy" kurulıyla başlamayı bekler.

### Startup Sırası Akışı (PostgreSQL Perspektifi)

```
docker-compose up
│
├─ PostgreSQL konteyner başlatılır
│  │
│  ├─ postgres:18-alpine imajı indirilir (zaten yoksa)
│  ├─ Konteyner oluşturulur (container_name: nac-postgres)
│  │
│  ├─ Volumes mount edilir:
│  │  ├─ pg_data hacmi /var/lib/postgresql/data'ya bağlanır
│  │  └─ ./db/init.sql, /docker-entrypoint-initdb.d/'ye bağlanır
│  │
│  ├─ Environment variables yüklenir:
│  │  ├─ POSTGRES_DB=nac (from .env)
│  │  ├─ POSTGRES_USER=postgres (from .env)
│  │  └─ POSTGRES_PASSWORD=*** (from .env)
│  │
│  ├─ PostgreSQL server başlatılır
│  │  ├─ Eğer pg_data boşsa: init.sql otomatik çalıştırılır
│  │  │  └─ Tablolar, indeksler oluşturulur, ilk veriler yüklenir
│  │  └─ Eğer pg_data dolduysa: önceki veri geliştirilir
│  │
│  ├─ Healthcheck başlar (5s aralıklı):
│  │  ├─ Deneme 1: pg_isready → Başarısız (Henüz açılmıyor)
│  │  ├─ Deneme 2: pg_isready → Başarısız
│  │  ├─ ...
│  │  └─ Deneme N: pg_isready → Başarılı! ✓ (healthy)
│  │
│  └─ PostgreSQL ready signal → Diğer servisleri bekleme kaldırır
│
└─ [API ve FreeRADIUS başlatmasını bekliyorlar]
```

### Network Bağlantısı

**Network:** `nac-network` (172.20.0.0/24 bridge driver)
- IPAM (IP Address Management) ile sabit subnet belirlenir.
- Her konteyner bu ağda benzersiz bir IP alır (örn. 172.20.0.2).

**DNS Çözümlemesi:**
- Docker daemon, konteyner içinde kendi DNS sunucusu çalıştırır (127.0.0.11:53).
- Hostname `postgres` konteyner'ın IP'sine otomatik çözümlenir.
- Konteyner adı (container_name: nac-postgres) DNS olarak çalışmaz; servis adı (services -> postgres) çalışır.

**Bu servis kime bağlanıyor?**
- PostgreSQL başka servislere bağlanmaz; pasif dinler.

**Kimin bağlanabileceği?**
- **FastAPI (api):** `postgres:5432` — kullanıcı/şifre ile bağlanır.
- **FreeRADIUS:** Doğrudan PostgreSQL'e bağlanmaz, FastAPI aracılığı ile veri sorgular.

**Güvenlik Notu:**
- Host portu 5432 açık (geliştirme için). Prodüksyon'da kapatılmalı.
- Network izole (nac-network), host dışındaki konteynerler erişemez.

### Kritik Noktalar ⚠️

1. **Volume Kalıcılığı:** `pg_data` hacmi silinmezse veri kalır. `docker-compose down --volumes` ile açıkça silinmelilidir.

2. **init.sql Zamanlaması:** İlk başlatmada çalışır. Komut dosyasında DDL/DML hataları containerı başlatmayabilir.

3. **Şifre Yönetimi:** .env dosyası git'e giremez (`.gitignore`'a eklenmelilidir). Şifreler hardcode edilmemelidir.

4. **Connection Pool:** FastAPI'de bağlantı havuzu ayarlanmalı (psycopg2 bağlantı limitleri).

5. **Backup Stratejisi:** Prodüksyon'da düzenli pg_dump gereklidir; docker compose'ta yalnızca hacim tutulur.

---

## Redis — Oturum önbelleği ve oran sınırlandırması

### Sorumluluğu ve Mimarisi

**Amaç:** Redis, NAC sisteminin hızlı, geçici veri deposudur. Kullanıcı oturum bilgilerini (session tokens), oran sınırlandırması sayıları, önbelleğe alınmış politika kararlarını tutarak sistem performansını artırır. PostgreSQL'e kıyasla çok daha hızlı okuma/yazma sağlar (işlem başına <1ms).

**Bu servis olmasaydı sistem nasıl davranırdı?**
Her istek PostgreSQL'e vurur, sorgu latencysi 10-50ms artar. İoT cihazlarından gelen yüzlerce istek/saniye düşer. Oturum yönetimi zor, oran sınırlandırması çalışmaz (spam/DoS koruması olmaz).

### Base Image Seçimi

**Image:** `redis:8-alpine`

**Neden bu image?**
- **Alpine:** 30 MB boyut (tam redis imajdan 60+ MB küçük). Container başlangıç hızlı.
- **Redis 8:** En son versyon. Stream veri yapıları, Cluster mode, ACL (Access Control Lists) desteği.
- **Lightweight:** Sadece Redis server ve temel bağımlılıklar. Geliştirme ve ürün ortamı için uygun.

**Bağımlılıklar:**
- Redis server (8.0)
- libc, libssl (TLS için)
- redis-cli aracı (healthcheck ve yönetim için)

### Environment Variables

| Variable | Amaç | Örnek | Kaynaktan Yükleme |
|----------|------|-------|------------------|
| REDIS_PASSWORD | Redis kimlik doğrulama şifresi | `redis_secure_pass_456` | .env dosyası |

**Yükleme Mekanizması:**
`env_file: .env` — PostgreSQL gibi, .env dosyasından `REDIS_PASSWORD` çekilerek `command:` satırında `${REDIS_PASSWORD}` yerine konur. Redis sunucu başlatıldığında `--requirepass` parametresi ile şifre koruması etkinleştirilir.

### Direktifler ve Davranışları

**image: redis:8-alpine**
- Resmi Redis Docker imajını kullan.

**container_name: nac-redis**
- Container sabit adı, network'te DNS "redis" olarak erişilebilir.

**command: redis-server --requirepass ${REDIS_PASSWORD}**
- Varsayılan komut yerine özel komut çalıştırılır.
- `redis-server` — Redis daemon başlatılır.
- `--requirepass ${REDIS_PASSWORD}` — Bağlantılardan önce şifre istenir. Client `AUTH` komutu ile kimlik doğrulaması yapmalı.
- Örneğin, Redis istemcisi: `redis-cli -a redis_secure_pass_456 PING` → `PONG`.

**Ports:**
- `6379:6379` — Redis'in standart portu. Host'tan konteyner'a yönlendirme. Geliştirmede lokal bağlantı için (`redis-cli -p 6379`).

**Volumes:**
```yaml
- redis_data:/data
```
- **redis_data:** Named volume — Redis veri dosyaları burada tutulur.
- Redis açılırken RDB (snapshot) veya AOF (append-only file) bu hacimdeki dosyalardan yüklenir.
- Hafif yapısına rağmen, veri kaybetmemek için persistence gereklidir.

**networks: nac-network**
- nac-network bridge'ine katılır. "redis" hostname'ı ile diğer servislerce erişilebilir.

**Healthcheck:**
```yaml
test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
interval: 5s
timeout: 3s
retries: 5
```
- **Test:** `redis-cli -a ${REDIS_PASSWORD} ping` — Redis istemcisi ile şifre ile ping gönderilir.
  - `-a` — authentication password'u belirtir.
  - `ping` — Redis "PONG" cevabı beklenir.
- **interval: 5s** — Her 5 saniye kontrol.
- **timeout: 3s** — 3 saniye içinde cevap gelmezse başarısız.
- **retries: 5** — 5 başarısız sonuç sonunda unhealthy.
- **Sonuç:** Redis bağlantı kabul ettiğinde healthy olur.

### Startup Sırası Akışı (Redis Perspektifi)

```
docker-compose up
│
├─ Redis konteyner başlatılır
│  │
│  ├─ redis:8-alpine imajı kontrol edilir
│  ├─ Konteyner oluşturulur (container_name: nac-redis)
│  │
│  ├─ Volume mount:
│  │  └─ redis_data hacmi /data'ya bağlanır
│  │
│  ├─ Environment yüklenir:
│  │  └─ REDIS_PASSWORD=redis_secure_pass_456
│  │
│  ├─ Custom command çalıştırılır:
│  │  └─ redis-server --requirepass redis_secure_pass_456
│  │
│  ├─ Redis server açılır
│  │  ├─ /data klasöründe dump.rdb varsa yüklenir (persistence)
│  │  └─ Yeni bağlantılar kabul etmeye başlar
│  │
│  ├─ Healthcheck başlar:
│  │  ├─ redis-cli -a redis_secure_pass_456 ping
│  │  ├─ PONG cevabı alınırsa healthy ✓
│  │
│  └─ Redis ready
│
└─ FastAPI ve FreeRADIUS başlatmasına hızlı ilerleme (bağımlılık yok)
```

### Network Bağlantısı

**Network:** `nac-network` (172.20.0.0/24)

**DNS Çözümlemesi:**
- Hostname "redis" otomatik çözümlenir konteyner'ın IP'sine.

**Bu servis kime bağlanıyor?**
- Redis başka servislere bağlanmaz; sadece dinler.

**Kimin bağlanabileceği?**
- **FastAPI (api):** `redis:6379` — session depolama, cache, rate limiting.
  - İstemci bağlantısında `AUTH redis_secure_pass_456` (REDIS_PASSWORD) ile kimlik doğrulama.
- **FreeRADIUS:** Doğrudan kullanmaz (FastAPI aracılığıyla erişir).

### Kritik Noktalar ⚠️

1. **Veri Kalıcılığı:** Redis varsayılan olarak tamamen RAM'de çalışır. `redis_data` hacmi olmadan konteyner silinmesiyle veri kaybolur.

2. **AOF vs RDB:** docker-compose'ta redis-server komutuna `--appendonly yes` parametresi eklenmemiş. İdeal durumda persistence mode açık olmalı.

3. **Şifre Yönetimi:** `--requirepass` şifresi .env'dedir, güvenli tutulmalıdır.

4. **Connection Limits:** Redis tek thread'lidir. Yüksek bağlantı sayısı (>1000 concurrent) için, pool yönetimi FastAPI tarafında yapılmalı.

5. **Eviction Policy:** Redis belleği dolduğunda default policy "noeviction" (hata). Production'da `maxmemory-policy allkeys-lru` veya `volatile-lru` ayarlanmalı.

---

## FastAPI — Politika motoru (API servisi)

### Sorumluluğu ve Mimarisi

**Amaç:** FastAPI servis, NAC sisteminin zeka merkezidir. Ağa bağlanan cihazları tanır, RADIUS sunucusu isteklerini alır, PostgreSQL'den politikaları okur, Redis'te kararları önbelleğe alır ve FreeRADIUS'a Accept/Reject yanıtı gönderir. Python ile yazılmış, async/await desteği ile eşzamanlı çok sayıda isteği işleyebilir.

**Bu servis olmasaydı sistem nasıl davranırdı?**
Politika kararları alınamaz. FreeRADIUS tüm istekleri reddet. Ağ erişimi olmaz. Sistem tamamen işlevsiz.

### Base Image Seçimi

**image:** Kendi Dockerfile'dan inşa edilir:
```yaml
build:
  context: ./api
  dockerfile: Dockerfile
```

**Neden custom build?**
- Proje kodu, dependencies (requirements.txt), konfigürasyon içerir.
- Resmi Python imajından (python:3.11-slim) başlayarak custom layer ekler.
- ./api Dockerfile'da FastAPI, uvicorn, psycopg2, redis, vb. paketler yüklenir.

**Dockerfile varsayılan yapısı (tahmin):**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Bağımlılıklar:**
- Python 3.11 runtime
- FastAPI, Uvicorn (ASGI server)
- psycopg2-binary (PostgreSQL client)
- redis (Redis client)
- python-dotenv, pydantic, vb.

### Environment Variables

| Variable | Amaç | Örnek | Kaynaktan Yükleme |
|----------|------|-------|------------------|
| DATABASE_URL | PostgreSQL bağlantı adresi | `postgresql://user:pass@postgres:5432/nac` | .env dosyası |
| REDIS_URL | Redis bağlantı adresi | `redis://:password@redis:6379/0` | .env dosyası |
| FASTAPI_ENV | Ortam (dev/prod) | `development` | .env dosyası |
| (others) | Politika kuralları, gizli anahtarlar, vb. | — | .env dosyası |

**Yükleme Mekanizması:**
`env_file: .env` — Tüm environment variable'lar .env'den konteyner'a yüklenir. Python kodu `os.getenv("DATABASE_URL")` veya pydantic `.env` dosyası yükleme mekanizması ile erişir.

### Direktifler ve Davranışları

**build:**
```yaml
context: ./api
dockerfile: Dockerfile
```
- `./api` klasöründeki Dockerfile ile imaj inşa edilir.
- `docker-compose up` ilk çalıştırılışında veya `docker-compose build api` komut ile Dockerfile derlenmiş imaj oluşturulur.

**container_name: nac-api**
- Sabit konteyner adı.

**ports:**
- `8000:8000` — FastAPI sunucu 8000 portunda çalışır. Host'tan erişilebilir (geliştirme). Prodüksyon'da sadece nac-network üzerinde erişim ideal.

**volumes:**
```yaml
- ./api:/app
```
- Bind mount — host'un ./api klasörü konteyner'ın /app'ine bağlanır (read-write varsayılan).
- **Hot reload:** Geliştirme sırasında host'ta kod değiştirilirse, konteyner içinde Uvicorn otomatik yeniden başlar (uvicorn --reload flag'ı aktif ise).
- Prodüksyon'da bu volume KALDI, imaj içine kodlanmış kod kullanılır.

**networks:**
- nac-network katılımı. PostgreSQL ("postgres:5432"), Redis ("redis:6379") ile iletişim kurabilir.

**depends_on:**
```yaml
depends_on:
  postgres:
    condition: service_healthy
  redis:
    condition: service_healthy
```
- FastAPI başlatılmadan önce PostgreSQL ve Redis sağlıklı olmalı.
- `service_healthy` — healthcheck geçmiş olmalı (pg_isready, redis-cli ping başarılı).
- İşlem: docker-compose PostgreSQL ve Redis'i başlatır, healthcheck geçene kadar beklenir, sonra API başlatılır.

**healthcheck:**
```yaml
test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
interval: 10s
timeout: 5s
retries: 5
```
- **Test:** Python urllib ile konteyner içinde `http://localhost:8000/health` GET request'i gönderilir.
  - FastAPI uygulaması `/health` endpoint'i sağlamalı (basit 200 OK cevab).
- **interval: 10s** — 10 saniye aralıklı kontrol (API init süresi göz önüne alınarak daha uzun).
- **timeout: 5s** — 5 saniye içinde cevap.
- **retries: 5** — 5 başarısız sonuç unhealthy işareti.
- **Sonuç:** API hazır ve istekleri işlemeye başladığında healthy. FreeRADIUS başlatması bu signali bekler.

### Startup Sırası Akışı (FastAPI Perspektifi)

```
docker-compose up
│
├─ PostgreSQL healthy ✓
├─ Redis healthy ✓
│
└─ FastAPI başlatılır
   │
   ├─ Dockerfile derlenmiş imaj hazırlanır (veya cache'den)
   ├─ Konteyner oluşturulur (container_name: nac-api)
   │
   ├─ Volume mount:
   │  └─ ./api:/app — geliştirme sırasında hot reload için
   │
   ├─ Environment yüklenir:
   │  ├─ DATABASE_URL=postgresql://...
   │  └─ REDIS_URL=redis://...
   │
   ├─ Konteyner başlatılır:
   │  └─ Dockerfile CMD çalıştırılır (uvicorn main:app ...)
   │
   ├─ Python kodu çalışır:
   │  ├─ FastAPI app instance oluşturulur
   │  ├─ PostgreSQL bağlantı havuzu kurulur (os.getenv ile DATABASE_URL okur)
   │  ├─ Redis bağlantısı kurulur
   │  └─ Tüm route'lar (endpoints) kayıt edilir
   │
   ├─ Uvicorn sunucu açılır:
   │  └─ 0.0.0.0:8000 dinleme başlar
   │
   ├─ Healthcheck başlar (10s aralıklı):
   │  ├─ /health endpoint'ine GET request
   │  ├─ 200 OK cevabı alınırsa healthy ✓
   │
   └─ FastAPI ready → FreeRADIUS başlatılabilir
```

### Network Bağlantısı

**Network:** nac-network (172.20.0.0/24)

**DNS Çözümlemesi:**
- Hostname "api" ile diğer konteynerlerden erişilebilir.

**Bu servis kime bağlanıyor?**
- **PostgreSQL:** `postgresql://user:pass@postgres:5432/nac` — Politika verileri sorgular, muhasebe log ekler.
- **Redis:** `redis://:password@redis:6379/0` — Session, cache, rate limit veri yazar/okur.

**Kimin bağlanabileceği?**
- **FreeRADIUS:** `http://api:8000/authorize` REST endpoint'i çağırır (RADIUS isteğini API'ye gönderir).
- **Host (geliştirme):** `curl http://localhost:8000/health` — API sağlığını kontrol edebilir.

**Request Akışı Örneği:**
```
FreeRADIUS receives RADIUS authentication request (1812/udp)
  ↓
FreeRADIUS → API (REST call to /authorize endpoint)
  ↓
FastAPI reads database (SELECT user_policies FROM users WHERE id=?)
  ↓
FastAPI queries Redis cache (GET policy:user:123)
  ↓
FastAPI evaluates policy (device trusted? network allowed? time ok?)
  ↓
FastAPI → Redis (SET session:token:xyz, rate:user:123)
  ↓
API returns {allowed: true} or {allowed: false}
  ↓
FreeRADIUS → RADIUS client (Accept or Reject)
```

### Kritik Noktalar ⚠️

1. **Bağlantı Havuzu:** Psycopg2 bağlantı havuzu (pool size) ayarlanmalı. Default 10 bağlantı, yüksek trafik için yetersiz olabilir.

2. **Redis Connection Pool:** redis-py kütüphanesi bağlantı havuz yönetimi sağlar. AsyncIO ile veya sync modu seçilmelidir.

3. **Hot Reload Prodüksyon'da Kapalı:** `./api:/app` volume'si prodüksyon'da kaldırılmalı, Uvicorn `--reload` flag'ı kapatılmalı (performans).

4. **Error Handling:** API database/Redis bağlantısı kopması durumunda graceful fail yapmalı (retry logic).

5. **Async vs Sync:** FastAPI async endpoint'ler kullanmalı, blocking işlemler (database query) thread pool'da çalıştırılmalı (await db queries).

---

## FreeRADIUS — RADIUS sunucusu

### Sorumluluğu ve Mimarisi

**Amaç:** FreeRADIUS, NAC sisteminin ağ geçididir. Ağ anahtarları, kablosuz erişim noktaları (AP'ler), VPN sunucuları gibi cihazlardan RADIUS kimlik doğrulama ve muhasebe isteklerini kabul eder. FastAPI'ye REST çağrısı yaparak politika kararı alır, yanıt olarak Accept veya Reject gönderir. 802.1X ağ kimlik doğrulama protokolünü uygulamayan sistemlerin NAC'ı kontrol etmesine izin verir.

**Bu servis olmasaydı sistem nasıl davranırdı?**
Cihazlar ağa bağlanamazsa (RADIUS başarısız), kimlik doğrulama protokolü devreye giremez. HAP'ler (network equipment), RADIUS istek gönderemez. Tüm ağ erişim kontrol işlemesi yapılamaz.

### Base Image Seçimi

**Image:** `freeradius/freeradius-server:latest-3.2`

**Neden bu image?**
- **FreeRADIUS 3.2:** Stabil, RFC 2865 (RADIUS), RFC 2866 (muhasebe), RFC 2868 (RADIUS Attributes) uygulanır. REST modülü (mods-enabled/rest) ile harici endpoint çağırabilir.
- **latest-3.2:** En son 3.x branch güvenlik yamaları içerir. Version 4 (development) kullanılmaz, üretim dengeleme.
- **Resmi imaj:** FreeRADIUS takımı tarafından maintain edilir.

**Bağımlılıklar:**
- FreeRADIUS server 3.2
- OpenSSL (TLS/SSL, RADIUS encryption)
- libc, libfreeradius (core libraries)
- radclient aracı (healthcheck için)

### Environment Variables

FreeRADIUS, bu docker-compose'ta env_file ile açık environment variable'lar yüklenmez. Konfigürasyon dosyaları (clients.conf, mods-enabled/rest, sites-enabled/default) direct olarak volume'lar ile bağlanır. Ancak, compose'un entrypoint chmod komut satırında environment kullanılabilir.

| Variable | Amaç | Kaynaktan Yükleme |
|----------|------|------------------|
| (konfigürasyon dosyalarında sabit) | Konfigürasyon direkt bind mount | ./freeradius/clients.conf, vb. |

### Direktifler ve Davranışları

**image: freeradius/freeradius-server:latest-3.2**
- Resmi FreeRADIUS Docker imajı.

**container_name: nac-freeradius**
- Sabit ad, network'te "freeradius" hostname'i ile erişilebilir.

**Ports:**
```yaml
- "1812:1812/udp"   # Authentication
- "1813:1813/udp"   # Accounting
- "18120:18120/udp" # CoA (Change of Authorization)
```
- **1812/udp:** RADIUS Authentication port — cihazlar kimlik doğrulama isteği gönderir.
- **1813/udp:** RADIUS Accounting port — muhasebe paketleri (başlangıç, durma, interim).
- **18120/udp:** CoA port — ağ ekipmanı politika değişikliği sonrası oturum değiştirmek için kullanılabilir.
- Tümü UDP — hızlı, stateless. Host portları kapsayıcıya yönlendirilir.

**Volumes:**
```yaml
- ./freeradius/clients.conf:/etc/freeradius/clients.conf
- ./freeradius/mods-enabled/rest:/etc/freeradius/mods-enabled/rest
- ./freeradius/sites-enabled/default:/etc/freeradius/sites-enabled/default
```
- **clients.conf:** RADIUS istemciler (ağ ekipmanları) tanımı, shared secret'ler.
  - Örnek: `client myswitch { ipaddr = 192.168.1.1; secret = sharedsecret123; }`
  - FreeRADIUS bu istemcilerin isteklerini kabul eder.

- **mods-enabled/rest:** REST modülü konfigürasyonu.
  - FastAPI'nin endpoint'ini tanımlar: `uri = "http://api:8000/authorize"`.
  - FreeRADIUS RADIUS isteğini bu endpoint'e JSON/form data ile POST eder.

- **sites-enabled/default:** Varsayılan site konfigürasyonu.
  - authenticate, authorize, accounting, post-auth işlem akışını tanımlar.
  - REST modülü çağrısını nasıl entegre edileceğini belirtir.

Tüm dosyalar **bind mount** (read-write değil read-only olabilir, `/etc/freeradius/` içi read-only genel olarak).

**entrypoint:**
```yaml
entrypoint: /bin/sh -c "chmod 600 /etc/freeradius/clients.conf /etc/freeradius/mods-enabled/rest /etc/freeradius/sites-enabled/default && freeradius -X"
```
- **Neden entrypoint?**
  - FreeRADIUS, konfigürasyon dosyalarında 600 (owner only read/write) izni beklediği dosyalar varsa hata verir (shared secret).
  - Volume mount ile bind edilen dosyalar host permission'ı korur, container'da 644 gibi daha açık olabilir.
  - `chmod 600` tüm bağlı dosyaları secure hale getirir.

- **freeradius -X:** FreeRADIUS debug modunda (-X flag) başlatılır.
  - Tüm istek/yanıt loglanır (développment/troubleshooting için).
  - Prodüksyon'da `-X` kaldırılmalı, silent mode başlatılmalı (`freeradius -l syslog`).

**command: ["freeradius", "-X"]**
- Açıkça `freeradius -X` tekrar belirtilir (entrypoint'in yanı sıra).
- Entrypoint ve command birlikte çalışır: entrypoint chmod yapıp sonra command çalıştırır.

**networks:**
- nac-network'e katılır. API ("api:8000") ile iletişim kurar.

**depends_on:**
```yaml
depends_on:
  api:
    condition: service_healthy
```
- FastAPI healthy olana kadar beklenir.
- Eğer FreeRADIUS REST modülü API'ye bağlanmaya çalışırsa ve API kapalıysa hata verir.

**healthcheck:**
```yaml
test: ["CMD", "radclient", "-c", "1", "-t", "2", "127.0.0.1", "status", "testing123"]
interval: 15s
timeout: 5s
retries: 5
start_period: 10s
```
- **Test:** `radclient` RADIUS istemcisi, localhost'a status isteği gönderir.
  - `-c 1` — 1 paket gönder.
  - `-t 2` — 2 saniye timeout.
  - `127.0.0.1` — localhost RADIUS sunucusu.
  - `status` — istatistik sorgula.
  - `testing123` — shared secret ("clients.conf"'da tanımlanmalı).

- **interval: 15s** — 15 saniye aralık (API healthcheck'ten daha uzun, FreeRADIUS başlangıç zamanı).

- **timeout: 5s** — 5 saniye içinde cevap.

- **retries: 5** — 5 başarısız unhealthy.

- **start_period: 10s** — İlk 10 saniyede başarısızlık unhealthy sayılmaz (startup zamanı).

- **Sonuç:** FreeRADIUS istekleri işlemeye başladığında healthy.

### Startup Sırası Akışı (FreeRADIUS Perspektifi)

```
docker-compose up
│
├─ FastAPI healthy ✓
│
└─ FreeRADIUS başlatılır
   │
   ├─ freeradius/freeradius-server:latest-3.2 imajı hazırlanır
   ├─ Konteyner oluşturulur (container_name: nac-freeradius)
   │
   ├─ Volumes mount edilir:
   │  ├─ ./freeradius/clients.conf → /etc/freeradius/clients.conf (read-write)
   │  ├─ ./freeradius/mods-enabled/rest → /etc/freeradius/mods-enabled/rest
   │  └─ ./freeradius/sites-enabled/default → /etc/freeradius/sites-enabled/default
   │
   ├─ Entrypoint çalıştırılır:
   │  ├─ chmod 600 /etc/freeradius/clients.conf /etc/freeradius/mods-enabled/rest /etc/freeradius/sites-enabled/default
   │  │  └─ Dosyalar 600 (owner: read/write, others: deny) izni alır
   │  │
   │  └─ freeradius -X başlatılır (debug modunda)
   │     ├─ clients.conf okunur (ağ ekipmanları tanınır)
   │     ├─ mods-enabled/rest modülü yüklenir
   │     ├─ sites-enabled/default workflow'u parse edilir
   │     ├─ 1812/udp (auth), 1813/udp (acct), 18120/udp (coa) dinleme başlar
   │     │
   │     └─ REST modülü test edilir:
   │        └─ http://api:8000/authorize endpoint'ine bağlantı denenebilir
   │
   ├─ Healthcheck başlar (10s delay sonra, 15s aralık):
   │  ├─ radclient -c 1 -t 2 127.0.0.1 status testing123
   │  ├─ FreeRADIUS status istatistik cevabı verirse healthy ✓
   │
   └─ FreeRADIUS ready → RADIUS istemcileri (ağ ekipmanları) bağlantı yapabilir
```

### Network Bağlantısı

**Network:** nac-network (172.20.0.0/24)

**DNS Çözümlemesi:**
- Hostname "freeradius" veya "api" ile diğer servislere bağlanır.

**Bu servis kime bağlanıyor?**
- **FastAPI (API):** `http://api:8000/authorize` — REST endpoint'ine RADIUS isteklerini gönderir.
  - Örnek POST: `{ "username": "user1", "password": "pass", "device_mac": "aa:bb:cc:dd:ee:ff" }`
  - Cevap: `{ "allowed": true }` veya `{ "allowed": false, "reason": "..." }`

**Kimin bağlanabileceği?**
- **Ağ Ekipmanları (RADIUS Clients):** Switch, AP, VPN sunucusu gibi cihazlar 1812 portuna RADIUS isteği gönderir.
  - clients.conf'da tanımlanması gerekir.
  - Shared secret ile kimlik doğrulanırlar.

**İstek Akışı (Ayrıntılı):**
```
1. Network Equipment (Switch: 192.168.1.100)
   ├─ Kullanıcı ağa bağlanmaya çalışır (802.1X başlatılır)
   │
   └─ Switch → FreeRADIUS (1812/udp, shared secret: switch123)
      ├─ RADIUS Access-Request:
      │  ├─ User-Name: alice
      │  ├─ User-Password: (encrypted)
      │  ├─ NAS-Identifier: switch.example.com
      │  └─ Called-Station-Id: aa:bb:cc:dd:ee:ff (switch MAC)
      │
      └─ FreeRADIUS REST modülü:
         └─ HTTP POST http://api:8000/authorize
            ├─ Request body:
            │  {
            │    "username": "alice",
            │    "device_mac": "aa:bb:cc:dd:ee:ff",
            │    "nas_ip": "192.168.1.100"
            │  }
            │
            └─ API Response:
               {
                 "allowed": true,
                 "vlan": 100,
                 "rate_limit": "10mbps"
               }

2. FreeRADIUS → Switch (1812/udp)
   ├─ RADIUS Access-Accept (if allowed)
   │  └─ Filter-Id: "vlan100"
   │     Reply-Message: "Access granted"
   │
   └─ Veya RADIUS Access-Reject (if denied)
      └─ Reply-Message: "Policy violation"

3. Switch → Port açılır (VLAN 100'e atanır, rate limit 10mbps)
   └─ Kullanıcı ağa erişim sağlanır

4. FreeRADIUS → API (Muhasebe)
   ├─ Periyodik interim-update (session info)
   └─ Stop (session sonlandığında)
```

### Kritik Noktalar ⚠️

1. **Debug Modunda Üretim:** `-X` flag'ı prodüksyon'da kapatılmalı. Verbose logging performansı düşürür, logs disk doldurabilir.

2. **Shared Secret Yönetimi:** clients.conf'da shared secret'ler hardcode'dır. Dosya permission'ı 600 olmalı. Üretim'de secret vault (HashiCorp Vault) kullanılmalı.

3. **REST Modülü Retry:** API kapalıysa REST modülü isteği retry etmelidir (timeout, error handling). Yapılandırma gereklidir.

4. **UDP vs TCP:** RADIUS protokolü UDP (stateless, hızlı). Paket kaybı olabilir, duplicate detection gereklidir (clients.conf'da).

5. **Muhasebe Depolama:** Muhasebe paketleri API'ye gönderilir. Eğer API başarısızsa paketler kaybedilebilir. Persistent queue (Redis) ile buffer kullanılmalı.

6. **CoA Desteği:** 18120 portu, dinamik politika değişiklikleri için (örn. rate limit artırma). API'den FreeRADIUS'a CoA paket göndermek entegre edilmeli.

---

## Sistem Başlatma Sırası (Tüm Hizmetler)

```
docker-compose up
│
├─ Networking hazırlama: nac-network (172.20.0.0/24 bridge)
│
├─ [Paralel] PostgreSQL + Redis başlatılması
│  │
│  ├─ PostgreSQL başlatılır
│  │  ├─ Image download/cache'ten yüklenir
│  │  ├─ pg_data hacmi mount edilir
│  │  ├─ init.sql execute (ilk çalıştırma ise)
│  │  ├─ Healthcheck: pg_isready
│  │  │  ├─ T0: unhealthy (server açılmıyor)
│  │  │  ├─ T5s: healthy ✓ (pg_isready pass)
│  │  │
│  │  └─ PostgreSQL ready signal
│  │
│  └─ Redis başlatılır
│     ├─ Image download/cache'ten yüklenir
│     ├─ redis_data hacmi mount edilir
│     ├─ redis-server --requirepass ${REDIS_PASSWORD}
│     ├─ Healthcheck: redis-cli ping
│     │  ├─ T0: unhealthy
│     │  ├─ T5s: healthy ✓ (PONG)
│     │
│     └─ Redis ready signal
│
├─ [Sequential] FastAPI başlatılması
│  │ (Bekleme: PostgreSQL healthy + Redis healthy)
│  │
│  ├─ Dockerfile derlenmiş imaj inşa edilir (ilk çalıştırma ise)
│  ├─ ./api volume mount edilir (hot reload için)
│  ├─ Konteyner başlatılır
│  ├─ Environment yüklenir (.env'den)
│  ├─ Uvicorn sunucu açılır (:8000)
│  ├─ Database connection pool kurulur
│  ├─ Redis connection kurulur
│  ├─ Routes kayıt edilir
│  ├─ Healthcheck: /health endpoint
│  │  ├─ T0: unhealthy (API init)
│  │  ├─ T10s: healthy ✓ (200 OK)
│  │
│  └─ FastAPI ready signal
│
└─ [Sequential] FreeRADIUS başlatılması
   │ (Bekleme: FastAPI healthy)
   │
   ├─ FreeRADIUS imaj hazırlanır
   ├─ Konfigürasyon volumes mount edilir
   ├─ Entrypoint: chmod 600 dosyalar
   ├─ FreeRADIUS -X başlatılır
   ├─ Clients tanınır
   ├─ REST modülü yüklenir
   ├─ Healthcheck: radclient status
   │  ├─ T0-T10s: unhealthy (start_period)
   │  ├─ T15s: healthy ✓ (status response)
   │
   └─ FreeRADIUS ready
      ├─ RADIUS istemcileri (network equipment) bağlantı yapabilir
      └─ Tüm sistem ready ✓

Toplam başlangıç süresi: ~30-40 saniye (build cache ise ~15 saniye)
```

---

## Network Topolojisi Diyagramı

```
┌─────────────────────────────────────────────────────────────┐
│ Host Machine (Windows/Linux/macOS)                          │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ nac-network (Docker bridge: 172.20.0.0/24)          │  │
│  │                                                      │  │
│  │  ┌──────────────┐  ┌──────────┐  ┌──────────────┐  │  │
│  │  │ postgres     │  │ redis    │  │ api          │  │  │
│  │  │ 172.20.0.2   │  │172.20.0.3│  │ 172.20.0.4   │  │  │
│  │  │ 5432 (listen)│  │ 6379 (l.)│  │ 8000 (listen)│  │  │
│  │  │              │  │          │  │              │  │  │
│  │  │ pg_data vol  │  │redis_data│  │ ./api mount  │  │  │
│  │  └──────────────┘  └──────────┘  └──────────────┘  │  │
│  │        ▲               ▲               ▲            │  │
│  │        └───────────────┼───────────────┘            │  │
│  │        (DNS: postgres) │ (DNS: redis)              │  │
│  │                        │                            │  │
│  │  ┌──────────────────────────────────────────────┐  │  │
│  │  │ freeradius (172.20.0.5)                      │  │  │
│  │  │ 1812/udp (auth)                              │  │  │
│  │  │ 1813/udp (accounting)                        │  │  │
│  │  │ 18120/udp (CoA)                              │  │  │
│  │  │ Volumes: clients.conf, mods/rest, sites      │  │  │
│  │  └──────────────────────────────────────────────┘  │  │
│  │        │                                            │  │
│  │        └──→ http://api:8000/authorize (REST)      │  │
│  │             (DNS: api)                            │  │
│  │                                                   │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Port Mappings (Host → Container)                  │ │
│ │ 5432:5432 → postgres:5432 (TCP)                  │ │
│ │ 6379:6379 → redis:6379 (TCP)                     │ │
│ │ 8000:8000 → api:8000 (TCP)                       │ │
│ │ 1812:1812/udp → freeradius:1812 (UDP)            │ │
│ │ 1813:1813/udp → freeradius:1813 (UDP)            │ │
│ │ 18120:18120/udp → freeradius:18120 (UDP)         │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ ┌────────────────────────────────────────────────────┐ │
│ │ File Bindings (Host → Container)                  │ │
│ │ ./db/init.sql → /docker-entrypoint-initdb.d/     │ │
│ │ ./api → /app (hot reload)                         │ │
│ │ ./freeradius/clients.conf → /etc/freeradius/...  │ │
│ │ ./freeradius/mods-enabled/rest → /etc/free...    │ │
│ │ ./freeradius/sites-enabled/default → /etc/free...│ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
└────────────────────────────────────────────────────────┘
         │
         │ External Connections (RADIUS)
         │
         ▼
    ┌─────────────────────┐
    │ Network Equipment   │
    │ (Switch, AP, VPN)   │
    │ 192.168.1.0/24      │
    └─────────────────────┘
         │
         └─ RADIUS-Request (1812/udp)
         └─ RADIUS-Response (1812/udp)
         └─ Accounting (1813/udp)
```

---

## Durdurma ve Temizleme İşlemleri

```yaml
# Tüm servisleri durdur (volumeler korunur)
docker-compose down

# Tüm servisleri durdur + volumeler sil (DIKKAT: veri kaybı)
docker-compose down --volumes

# Tüm servisleri yeniden başlat (fresh start)
docker-compose up -d --force-recreate

# Spesifik servisi yeniden başlat
docker-compose restart postgres

# Build cache'i temizle (imaj yeniden inşa)
docker-compose build --no-cache api
```

---

## Sonuç ve En İyi Uygulamalar

| Öğe | Kural | Detay |
|-----|-------|-------|
| **Environment Variables** | .env dosyası git'e girmez | .gitignore'a ekle, şifreler korun |
| **Volumes** | Named volumes prodüksyon, bind mounts geliştirme | Veri kalıcılığı önemli |
| **Healthcheck** | Her servis kendi health endpoint'ine sahip | Orchestration ve bağımlılık yönetimi |
| **Dependencies** | service_healthy condition ile sıra garantilenir | Kaotik başlangıçtan kaçın |
| **Debugging** | FreeRADIUS -X flag'ı geliştirmede yararlı | Prodüksyon'da kapatılmalı |
| **Networking** | DNS (hostname) ile harita yapılandırmasını önle | Konteyner adları değişebilir |
| **Security** | Shared secret'ler vault'ta tutulmalı | Hardcode'dan kaçın |
| **Scaling** | FreeRADIUS stateless, API stateless olabilir | Redis session store ile ölçeklendirme |

---

**Dokümantasyon Sonu**

Bu dokümantasyon, docker-compose.yml'deki her servisin sorumluluğunu, yapılandırmasını ve etkileşimlerini kapsamlı olarak açıklar. Geliştirici ve operasyon ekipleri bu belgeden sistem mimarisini anlayabilir.
