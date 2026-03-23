# Dockerfile Anatomisi

## Dockerfile Mimarisi Özeti

**Amaç:** FastAPI uygulamasını çalışabilir hale getirmek (development + production template)

**Katman Sayısı:** 6 ana layer (+ intermediate layers)

**Build Time vs Runtime Ayrımı:**
- Build-time: FROM, RUN, COPY (image oluştururken çalışır)
- Runtime: CMD, EXPOSE (container çalışırken etkili)

**Base Image:** Python 3.13-slim (66MB)

---

## FROM python:3.13-slim — Base Image Seçimi

### Ne Yapar?
- Docker image'ının temelini belirler
- Üzerine tüm diğer katmanlar eklenir
- Image önceden derlenmiş ve optimize edilmiş Python'u içerir

### Neden python:3.13-slim?

**Seçenekler ve Neden Slim?**

| Image | Boyut | Kapsamı | Kullanım Durumu |
|-------|-------|---------|-----------------|
| python:3.13-slim | 66MB | Minimum (Python + apt) | ✓ Tercih — hafif, hızlı build |
| python:3.13-alpine | 42MB | Minimal (musl libc) | Çok hafif ama bağımlılık sorunları |
| python:3.13 | 360MB | Full (build tools, docs) | Geliştirme, ağır uygulamalar |
| python:3.13-bullseye | 890MB | Debian Bullseye full | Legacy uygulamalar |

Slim tercih sebebi:
- Debian tabanlı (Linux compatibility iyi)
- apt paket yöneticisi var (gcc, libpq-dev kurulabiliyor)
- Alpine'den daha stabil (fewer broken packages)
- Alpine'den 24MB daha büyük ama reliability worth it

### Python 3.13 Seçimi

```
Python 3.13 (latest stable)
- Async/await support (asyncpg, asyncio)
- Type hints fully mature
- Performance improvements
- Security patches active
```

### Başlangıç State

Image inceleme komutu:
```bash
docker image inspect python:3.13-slim
# Shows: OS=Debian 12 (bookworm), Architecture=amd64, Size=66MB
```

---

## WORKDIR /app — Çalışma Dizini

### Ne Yapar?
- Container içindeki çalışma dizinini belirler
- Tüm sonraki RUN, COPY, CMD komutları bu dizinde çalışacak
- Dizin yoksa otomatik oluşturur

### Sonucu
```
/app/
  ├── requirements.txt (copy edilecek)
  ├── main.py (copy edilecek)
  ├── config.py (copy edilecek)
  └── ... (tüm Python dosyaları)
```

### Neden Gerekli?
- PATH düzeni komutsuz kalırsa (`.` copy ederken sorun)
- Çalışan process'i izlemek/debug kolay
- Volume mount'leri temiz

---

## RUN apt-get update && apt-get install — Sistem Bağımlılıkları

### Ne Yapar?
- Sistem paketlerini yükler (C compiler, PostgreSQL client library)
- Üç adet RUN'ı tek satırda zincirler (&&)

### Neden Gerekli?

**gcc (C Compiler):**
- asyncpg (Python PostgreSQL driver) C extension'lar içerir
- asyncpg compile edilmesi gerekir
- Saf Python paket değil

**libpq-dev (PostgreSQL Development Library):**
- asyncpg compile edilirken PostgreSQL header dosyaları gerekir
- psycopg2, asyncpg gibi drivers bunu talep eder
- Runtime'da libpq.so.6 gerekir (production image'da)

### Komut Detayı

```bash
apt-get update
# Paket liste indeksini güncelle (fresh mirrors)

apt-get install -y --no-install-recommends gcc libpq-dev
# -y: sor, cevap ver (otomatik)
# --no-install-recommends: suggested paketleri kuru
#    (image boyutunu kontrol et: 300MB → 100MB fark)

rm -rf /var/lib/apt/lists/*
# apt cache'ini sil (layer boyutunu azalt)
# /var/lib/apt/lists/ ~ 40MB boşa harcanmış
```

### Neden Zincir (&&)?

Eğer ayrı RUN komutları olsaydı:
```dockerfile
RUN apt-get update
RUN apt-get install gcc libpq-dev
RUN rm -rf /var/lib/apt/lists/*
```

Sonuç: 3 layer (3x okunan/yazılan), her layer taşıyor
Şimdi: 1 layer, cache hit tek seferde

### Cache Implications

```
docker build (ilk kez)
├─ FROM python:3.13-slim — remote pull, 66MB cache hit
├─ WORKDIR /app — instant (no cache layer)
├─ RUN apt-get... — MISS, çalışır (30-40 saniye), result cache'lenir
├─ COPY requirements.txt — MISS (file hash değişirse)
└─ (sonraki layerlar...)

docker build (ikinci kez, hiçbir file değişmedi)
├─ FROM python:3.13-slim — CACHE HIT
├─ WORKDIR /app — CACHE HIT
├─ RUN apt-get... — CACHE HIT (instant!)
├─ COPY requirements.txt — CACHE HIT
└─ (instant build)

docker build (requirements.txt değişti)
├─ ... (CACHE HIT until COPY)
├─ COPY requirements.txt — MISS (file hash changed)
├─ RUN pip install... — MISS (re-run, previous cache invalid)
└─ COPY . . — MISS
└─ (re-build)
```

---

## COPY requirements.txt . — Bağımlılık Dosyasını Kopyala

### Ne Yapar?
- Host'taki `./api/requirements.txt` → container `/app/requirements.txt`

### Neden Ayrı Aşamada?

**Görünüşte Gereksiz:**
```dockerfile
# Sonra COPY . . yapılıyor, neden requirements.txt tekrar?
```

**Aslında Gerekli! (Cache Optimization)**

Eğer aynı layer'da yapılsaydı:
```dockerfile
# BAD: Cache-inefficient
COPY . .                                           # Tüm dosya tree
RUN pip install --no-cache-dir -r requirements.txt
```

Sonuç: İhtiyac olmayan file değişti → pip install tekrar çalışır (5-10 saniye boşa)

Doğru Seçim (Current):
```dockerfile
# GOOD: Cache-efficient
COPY requirements.txt .          # Sadece requirements.txt kopyala
RUN pip install ...              # Cache hit olsa reuse et

COPY . .                          # Sonra diğer files copy et
```

Sonuç: requirements.txt değişmezse pip install cache hit, hızlı build (2-3 saniye)

**Use Case:**
- `main.py` düzenliyorum (bug fix) → requirements değişmedi
- Build time: 2 saniye (pip install skip, sadece COPY . .)
- Alternative: 15 saniye (full pip install tekrar)

---

## RUN pip install — Python Bağımlılıkları

### Ne Yapar?
- requirements.txt'teki 12-15 paket yükler
- FastAPI, SQLAlchemy, asyncpg, redis, pydantic-settings vb.

### Flag: --no-cache-dir

```
pip install (default)
├─ Paketleri download et → ~/.cache/pip (~100MB)
├─ Install et
└─ Cache'i kontrol et (future installs hızlı)

pip install --no-cache-dir
├─ Paketleri download et
├─ Install et
└─ ~/.cache/pip KALMAz (image boyutunu azalt: 100MB saved)
```

### Production Implication

**Development:** pip cache'i useful (frequent requirements changes)
**Production:** cache gereksiz (image'a freeze edilmiş, değişmez)

```dockerfile
# Production-optimized:
RUN pip install --no-cache-dir -r requirements.txt
```

### Installed Packages (Teori)

```
fastapi          ~100KB
uvicorn          ~200KB
sqlalchemy       ~1.5MB
asyncpg          ~500KB
redis            ~200KB
pydantic-settings ~50KB
(others)         ~2MB
─────────────────────
Total            ~6-8MB
```

---

## COPY . . — Uygulama Kodunu Kopyala

### Ne Yapar?
- Host'taki tüm dosyaları container'a kopyalar
- `.dockerignore` kurallarına göre filtreler

### Source Dosyalar

```
Host (./api/)              Container (/app/)
├── main.py                ├── main.py
├── config.py              ├── config.py
├── database.py            ├── database.py
├── models.py              ├── models.py
├── schemas.py             ├── schemas.py
├── routes/                ├── routes/
│   ├── auth.py            │   ├── auth.py
│   ├── authorize.py       │   ├── authorize.py
│   └── ... (5 files)      │   └── ... (5 files)
├── services/              ├── services/
│   ├── redis_service.py   │   ├── redis_service.py
│   └── rate_limiter.py    │   └── rate_limiter.py
├── requirements.txt       ├── requirements.txt
├── Dockerfile             ├── Dockerfile
├── .gitignore             (kopyalanmaz, .dockerignore tarafından)
└── ... other files        └── ... other files
```

### NOT: __pycache__ Kopyalanmaz mı?

Host'ta `__pycache__` varsa → Container'a kopyalanmaz (gereksiz)

**Neden Gereksiz?**
1. Container kapatılınca silinir
2. Python çalıştırıldığında yeniden oluşturulur (lazy)
3. Image boyutunu artırır

**Best Practice:** .dockerignore'a ekle:
```
__pycache__
*.pyc
.venv
.env
```

### Cache Hit / Miss

```
COPY . . — MISS if:
- Herhangi bir file değişti (main.py, routes/* vs)
- Not just requirements.txt (earlier layer cached)

Subsequent layers:
- EXPOSE 8000 — no cache (metadata only)
- CMD [...] — no cache (metadata only)
```

---

## EXPOSE 8000 — Port Bildirimi

### Ne Yapar?
- Belge: Bu container port 8000'i dinliyor
- Metadata: Docker ve tools'a hint

### Önemli NOT:

EXPOSE port açmaz! Yapılacak işler:
1. docker run -p 8000:8000 (port map) gerekir
2. Veya docker-compose.yml'de ports: ["8000:8000"]

**Analoji:**
```
EXPOSE = "Bunu bilibilirim açabilirim (flag)"
-p flag  = "Aç"
```

### Kullanım

```bash
# EXPOSE işlemedi, port kapalı:
docker run my-api
# Curl from host: curl localhost:8000 → Connection refused

# docker run ile port map:
docker run -p 8000:8000 my-api
# Curl from host: curl localhost:8000 → Works!
```

### docker-compose'da Kullanımı

```yaml
api:
  ports:
    - "8000:8000"  # EXPOSE'ı geçersiz kılar (port açılır)
```

---

## CMD vs ENTRYPOINT Seçimi

### CMD vs RUN vs ENTRYPOINT

| Komut | Ne Yapar | Ne Zaman |
|-------|----------|----------|
| RUN | Image build sırasında çalışır | Build-time (Dockerfile processing) |
| CMD | Default komut (override edilebilir) | Runtime (docker run komut) |
| ENTRYPOINT | Fixed komut (override zor) | Runtime (always runs) |

### CMD Seçilmiş (doğru)

**CMD Avantajları:**
```bash
docker run myapp
# Çalıştırır: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

docker run myapp python -c "import sqlalchemy; print(...)"
# CMD'yi geçersiz kıl, özel komut çalıştır
```

**ENTRYPOINT Dezavantajları:**
```dockerfile
ENTRYPOINT ["uvicorn", "main:app", ...]
# docker run myapp python -c "..." çalışmaz (uvicorn çalışmaya devam)
```

Uvicorn için CMD Doğru. (debugging, testing gerektiğinde override gerekli)

### CMD Detayı

```bash
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

Breaking down:
- `uvicorn` — ASGI application server
- `main:app` — Module:variable (main.py'da app = FastAPI())
- `--host 0.0.0.0` — Tüm network interfaces'ten dinle (127.0.0.1 değil)
- `--port 8000` — Port 8000'de serve et
- `--reload` — File değişimi detect, auto-restart (DEVELOPMENT ONLY!)

### Production: --reload Çıkarılmalı!

```dockerfile
# Production-safe:
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
# (--reload yok, fast restart)

# Workers (performance):
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

## Build Optimization Analizi

### Current Dockerfile Strengths ✓
1. Multi-layer strategy (requirements separate)
2. RUN commands chained (single layer)
3. apt-get cache cleared (--no-cache-dir)
4. Slim base image (66MB, not 360MB)
5. .dockerignore likely used

### Improvement Opportunities (Not Critical)

**Opportunity 1: --reload Reminder**
```dockerfile
# Current (development):
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production:
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**Opportunity 2: Non-root User (Security)**
```dockerfile
# Add after RUN apt-get install:
RUN useradd -m -u 1000 appuser
USER appuser
# Reduces privilege escalation risk
```

### Layer Cache Analysis

```
Layer 1: FROM python:3.13-slim (66MB, cached from registry)
Layer 2: WORKDIR /app (0MB metadata)
Layer 3: RUN apt-get... (134MB gcc, libpq-dev)
Layer 4: COPY requirements.txt . (~5KB)
Layer 5: RUN pip install... (8-10MB packages)
Layer 6: COPY . . (2-5MB app code)
Layer 7: EXPOSE 8000 (0MB metadata)
Layer 8: CMD [...] (0MB metadata)
─────────────────────────────
Total: 66 + 0 + 134 + 0.005 + 10 + 4 + 0 + 0 = ~214 MB uncompressed
Compressed (registry): ~80-100 MB
```

### Cache Hit Probability

- Base image (python:3.13-slim): Always hit (public registry)
- apt-get layer: Hit unless apt-cache invalidated
- requirements.txt: Hit unless requirements.txt changes
- pip install: Hit unless requirements change (common)
- COPY . .: MISS if any file changes (frequent during dev)

---

## Dockerfile Güvenlik Analizi

**Eksikler (Not Critical for Development):**

1. **No User Isolation:** Container çalışıyor root olarak
   - Risk: Code execution → host compromise
   - Fix: RUN useradd -m appuser; USER appuser

2. **No Healthcheck:** Docker doesn't know if process died
   - Risk: Zombie containers (appear running, actually broken)
   - Fix: docker-compose.yml'de healthcheck (already has it!)

3. **--reload Production'da:** Auto-restart unsafe
   - Risk: Code changes during operation
   - Fix: Remove --reload flag (production)

**İyi Uygulamalar:**
- ✓ No hardcoded secrets
- ✓ Slim base image (fewer vulns)
- ✓ pip packages signed
- ✓ WORKDIR isolation
