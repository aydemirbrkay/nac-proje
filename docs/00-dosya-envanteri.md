# Dosya Envanteri ve Proje Yapısı

## Özet

| Metrik | Sayı |
|--------|------|
| **Konfigürasyon dosyaları** | 4 |
| **Python kaynak dosyaları (.py)** | 14 |
| **Derlenmiş Python (.pyc)** | 14 |
| **Shell betikleri (.sh)** | 2 |
| **Docker dosyaları** | 1 |
| **Dokümantasyon/Config** | 6 |
| **Toplam dosya** | **41** |

## Tam Proje Ağacı

```
nac-system/
├── .env                              # Environment variable'lar (secret'lar)
├── .env.example                      # Şablon — production'da düzenlenmeli
├── .gitignore                        # Git ignore kuralları
├── README.md                         # Proje belgesi
├── docker-compose.yml                # Docker Compose orkestrasyon
│
├── api/                              # FastAPI NAC Policy Engine
│   ├── main.py                       # FastAPI ana uygulama
│   ├── config.py                     # Pydantic-settings konfigürasyonu
│   ├── database.py                   # SQLAlchemy async engine
│   ├── models.py                     # ORM modelleri (Kullanıcı, Grup, vb.)
│   ├── schemas.py                    # Pydantic request/response şemaları
│   ├── requirements.txt              # Python bağımlılıkları
│   ├── Dockerfile                    # API konteynerı için build
│   │
│   ├── __pycache__/                  # Python bytecode cache
│   │   ├── config.cpython-313.pyc
│   │   ├── database.cpython-313.pyc
│   │   ├── main.cpython-313.pyc
│   │   ├── models.cpython-313.pyc
│   │   └── schemas.cpython-313.pyc
│   │
│   ├── routes/                       # API endpoint'leri
│   │   ├── __init__.py               # routes paketini tanımla
│   │   ├── auth.py                   # POST /auth — kimlik doğrulama
│   │   ├── authorize.py              # POST /authorize — yetkilendirme
│   │   ├── accounting.py             # POST /accounting — oturum kayıt
│   │   ├── users.py                  # GET /users — kullanıcı listesi
│   │   ├── sessions.py               # GET /sessions/active — aktif oturumlar
│   │   │
│   │   └── __pycache__/              # routes paket bytecode cache
│   │       ├── accounting.cpython-313.pyc
│   │       ├── auth.cpython-313.pyc
│   │       ├── authorize.cpython-313.pyc
│   │       ├── sessions.cpython-313.pyc
│   │       ├── users.cpython-313.pyc
│   │       └── __init__.cpython-313.pyc
│   │
│   └── services/                     # Yardımcı hizmetler
│       ├── __init__.py               # services paketini tanımla
│       ├── redis_service.py          # Redis bağlantı ve oturum yönetimi
│       ├── rate_limiter.py           # Hız sınırlama (auth attempts)
│       │
│       └── __pycache__/              # services paket bytecode cache
│           ├── rate_limiter.cpython-313.pyc
│           ├── redis_service.cpython-313.pyc
│           └── __init__.cpython-313.pyc
│
├── db/                               # PostgreSQL veritabanı başlatma
│   └── init.sql                      # Tablo, sekans, indeks DDL'leri
│
├── freeradius/                       # FreeRADIUS sunucu konfigürasyonu
│   ├── clients.conf                  # RADIUS client'ları tanımla (IP/secret)
│   │
│   ├── mods-enabled/                 # Etkin modüller
│   │   └── rest                      # rlm_rest modülü (FastAPI'ye proxy)
│   │
│   └── sites-enabled/                # Etkin site konfigürasyonları
│       └── default                   # Varsayılan RADIUS sunucusu
│
└── tests/                            # Test betikleri
    ├── test_all.sh                   # Tüm bileşenleri test et
    └── test_radius.sh                # RADIUS sunucusunu test et
```

## Dizin Katalogları

### api/ — FastAPI NAC Policy Engine

**İçeriği:** FreeRADIUS rlm_rest modülü tarafından çağrılan NAC politika motorunun ana uygulaması.

**Temel İşlevleri:**
- Kimlik doğrulama (PAP/CHAP + MAB)
- Yetkilendirme (grup + VLAN atama)
- Oturum kayıt (start/update/stop)
- Kullanıcı ve oturum yönetimi

**Dosya sayısı:** 7 Python dosyası + 1 Dockerfile + 1 requirements.txt = 9

**Temel dosyalar:**
| Dosya | Amaç |
|-------|------|
| `main.py` | FastAPI uygulaması, route'ları kaydet, healthcheck |
| `config.py` | Pydantic-settings ile merkezi konfigürasyon yönetimi |
| `database.py` | SQLAlchemy async motor (PostgreSQL) |
| `models.py` | ORM modelleri (User, Group, Vlan vb.) |
| `schemas.py` | Pydantic request/response şemaları |
| `requirements.txt` | FastAPI, SQLAlchemy, Redis, asyncpg vb. |
| `Dockerfile` | Python 3.13 tabanlı konteyner görüntüsü |

**Klasör yapısı:**
- `routes/` — 5 API endpoint modülü
- `services/` — Redis ve hız sınırlama hizmetleri
- `__pycache__/` — Python bytecode cache

**__pycache__ notu:** Python kodlar ilk çalışmada `.pyc` dosyalarına derlenip bu dizinde saklanır. **`.gitignore`'a alınmış** — git depoya dahil edilmez.

---

### api/routes/ — API Endpoint'leri

**İçeriği:** FreeRADIUS'tan gelen istekleri işleyen 5 ana endpoint modülü.

**Dosya sayısı:** 6 dosya (5 modül + 1 __init__.py)

| Dosya | HTTP Metod | Amaç |
|-------|-----------|------|
| `auth.py` | POST | `/auth` — Username/password doğrulama |
| `authorize.py` | POST | `/authorize` — Yetkilendirme, VLAN atama |
| `accounting.py` | POST | `/accounting` — Start/update/stop oturum kayıt |
| `users.py` | GET | `/users` — Tüm kullanıcıları listele |
| `sessions.py` | GET | `/sessions/active` — Redis'ten aktif oturumlar |
| `__init__.py` | — | routes paketini tanımla, modülleri import et |

**__pycache__ notu:** 6 `.pyc` dosyası saklanır (5 modül + __init__.py). **`.gitignore`'a alınmış**.

---

### api/services/ — Yardımcı Hizmetler

**İçeriği:** API'nin kullandığı yardımcı servisler ve utilities.

**Dosya sayısı:** 3 dosya

| Dosya | Amaç |
|-------|------|
| `redis_service.py` | Redis bağlantı pool, oturum cache yönetimi |
| `rate_limiter.py` | Başarısız auth denemelerini sınırla (5 deneme/5 dakika) |
| `__init__.py` | services paketini tanımla |

**__pycache__ notu:** 3 `.pyc` dosyası saklanır. **`.gitignore`'a alınmış**.

---

### db/ — PostgreSQL Veritabanı Başlatma

**İçeriği:** Docker Compose başlangıcında PostgreSQL'i başlatmak için DDL ve DML komutları.

**Dosya sayısı:** 1 dosya

| Dosya | Amaç |
|-------|------|
| `init.sql` | Tabloları, sekansları, indeksleri ve seed verilerini oluştur |

---

### Dokümantasyon ve Konfigürasyon Dosyaları

**İçeriği:** Proje belgesi, API bağımlılıkları ve veritabanı/RADIUS sunucu konfigürasyonları.

**Dosya sayısı:** 6 dosya

| Dosya | Amaç |
|-------|------|
| `README.md` | Proje belgesi ve kurulum talimatları |
| `api/requirements.txt` | Python bağımlılıkları (FastAPI, SQLAlchemy, asyncpg vb.) |
| `db/init.sql` | PostgreSQL tablo, sekans ve seed verisi DDL'leri |
| `freeradius/clients.conf` | RADIUS client'larını tanımla (IP adresleri, shared secret) |
| `freeradius/mods-enabled/rest` | REST modülü konfigürasyonu (FastAPI endpoint URL'leri) |
| `freeradius/sites-enabled/default` | Varsayılan RADIUS sitesi (kimlik doğrulama, yetkilendirme, accounting) |

---

### freeradius/ — FreeRADIUS Sunucu Konfigürasyonu

**İçeriği:** RADIUS sunucusu için konfigürasyon dosyaları. FastAPI'ye istekleri rlm_rest modülü aracılığıyla proxy'ler.

**Dosya sayısı:** 3 dosya

| Dosya | Amaç |
|-------|------|
| `clients.conf` | RADIUS client'larını tanımla (IP adresleri, shared secret) |
| `mods-enabled/rest` | REST modülü konfigürasyonu (FastAPI endpoint URL'leri) |
| `sites-enabled/default` | Varsayılan RADIUS sitesi (kimlik doğrulama, yetkilendirme, accounting) |

**Yapısı:**
- `mods-enabled/` — Etkin FreeRADIUS modülleri
- `sites-enabled/` — Etkin RADIUS site konfigürasyonları

---

### tests/ — Test Betikleri

**İçeriği:** Tüm bileşenleri test etmek için bash betikleri.

**Dosya sayısı:** 2 dosya

| Dosya | Amaç |
|-------|------|
| `test_all.sh` | Docker Compose'u başlat ve tüm servisleri test et |
| `test_radius.sh` | FreeRADIUS'a radclient ile RADIUS paketi gönder |

---

## Python Package Yapısı

### __init__.py Dosyaları

**Konum ve amaç:**

| Dosya | Konum | Export Edilen Modüller |
|-------|-------|----------------------|
| `routes/__init__.py` | `api/routes/` | Hiçbiri (sadece paket tanımı) |
| `services/__init__.py` | `api/services/` | Hiçbiri (sadece paket tanımı) |

**Not:** Bu dosyalar python 3.3+ için isteğe bağlıdır ama paket olarak tanınmasını sağlamak için mevcuttur. İçeriğe bakıldığında boş veya minimal import'lar bulunur.

---

### __pycache__ Dizinleri

**Konum ve amaç:**

| Dizin | İçeriği | Dosya Sayısı | Amaç |
|-------|---------|--------------|------|
| `api/__pycache__/` | 5 `.pyc` dosyası | 5 | api root modüllerinin derlenmiş bytecode'u |
| `api/routes/__pycache__/` | 6 `.pyc` dosyası | 6 | routes paketinin modüllerinin derlenmiş kodu |
| `api/services/__pycache__/` | 3 `.pyc` dosyası | 3 | services paketinin modüllerinin derlenmiş kodu |

**Toplam:** 14 `.pyc` dosyası

**Ne işe yarar:** Python yorumlayıcı, ilk çalışmada `.py` dosyalarını `.pyc` dosyalarına derler. Bu derlenmiş bytecode tekrar çalıştırıldığında daha hızlı yüklenir. Taşınabilir bilgisayarlarda Python versiyonu değişmez ise reuse edilebilir.

**Git'ten çıkarılmalı:** `.gitignore` dosyasında `__pycache__/` kuralı mevcuttur — depo'ya commit edilmez.

---

### .pyc Dosyaları

**Ne işe yarar:** Python 3.13 tarafından derlenmiş bytecode. Dosya adı formatı: `[modülAdı].cpython-313.pyc`

**Neden oluşuyor:** Python çalıştırıldığında:
1. `.py` dosyasını oku
2. AST'ye parse et
3. Bytecode'a derle
4. `.pyc` olarak cache'e yaz

**Git'ten çıkarılmalı:** `.gitignore` dosyasında `*.pyc` kuralı mevcuttur.

---

## Önemli Dosyalar

### Konfigürasyon ve Ortam

| Dosya | Amaç | Tür | Nota |
|-------|------|-----|------|
| `.env` | Environment variable'lar (secret'lar) | Configuration | Production'da secret yönetimi olmalı; depo'ya commit edilmez |
| `.env.example` | .env şablonu | Template | Geliştirici onboarding için; depo'ya commit edilir |
| `.gitignore` | Git ignore kuralları | Configuration | `__pycache__/`, `*.pyc`, `.env`, `venv/` vb. |
| `docker-compose.yml` | 5 servis orkestrasyon | YAML | PostgreSQL, Redis, API, FreeRADIUS, Network |

### Proje Dosyaları

| Dosya | Amaç | Tür |
|-------|------|-----|
| `README.md` | Proje belgesi | Markdown |
| `api/requirements.txt` | Python bağımlılıkları | Text |
| `api/Dockerfile` | API konteyner build'i | Dockerfile |
| `db/init.sql` | Database şema ve seed verisi | SQL |
| `freeradius/clients.conf` | RADIUS client'ları | Configuration |
| `freeradius/mods-enabled/rest` | REST modülü config | Configuration |
| `freeradius/sites-enabled/default` | RADIUS sitesi config | Configuration |
| `tests/test_all.sh` | Entegrasyon test betiği | Bash |
| `tests/test_radius.sh` | RADIUS test betiği | Bash |

---

## Git Ignore Durumu

### Doğru şekilde exclude edilen dosyalar:

✓ `__pycache__/` — Python bytecode cache dizinleri
✓ `*.pyc` — Derlenmiş Python dosyaları
✓ `*.pyo` — Optimize edilmiş Python dosyaları
✓ `.venv/`, `venv/` — Virtual environment'lar
✓ `.env` — Ortam secret'ları
✓ `.vscode/`, `.idea/` — IDE dosyaları
✓ `data/` — Docker volume'ları
✓ `*.log` — Log dosyaları

### Depo'ya dahil edilen önemli dosyalar:

✓ `docker-compose.yml` — Orkestrasyon config
✓ `.env.example` — Development template
✓ `db/init.sql` — Database şema
✓ `freeradius/` — RADIUS config'ler
✓ `api/Dockerfile` — Container build
✓ `requirements.txt` — Bağımlılıklar

---

## Dosya Sayısı Özeti (Hiyerarşik)

```
nac-system/                        41 dosya toplam
├── Root level                     5 dosya
│   ├── .env
│   ├── .env.example
│   ├── .gitignore
│   ├── README.md
│   └── docker-compose.yml
│
├── api/                           23 dosya
│   ├── Root (7 dosya)
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── __pycache__/ (5 dosya)
│   ├── routes/ (6 dosya)
│   │   ├── 5 modül (.py)
│   │   ├── __init__.py
│   │   └── __pycache__/ (6 dosya)
│   └── services/ (3 dosya)
│       ├── 2 modül (.py)
│       ├── __init__.py
│       └── __pycache__/ (3 dosya)
│
├── db/                            1 dosya
│   └── init.sql
│
├── freeradius/                    3 dosya
│   ├── clients.conf
│   ├── mods-enabled/rest
│   └── sites-enabled/default
│
└── tests/                         2 dosya
    ├── test_all.sh
    └── test_radius.sh
```

---

## Sistem Mimarisi — Dosya Perspektifinden

```
┌─────────────────────────────────────────────────────────┐
│ docker-compose.yml  (5 servisi orkestra eder)           │
└─────────────────────────────────────────────────────────┘
         │
         ├─→ PostgreSQL (db/init.sql ile başlatılır)
         │
         ├─→ Redis (session cache + rate limiting)
         │
         ├─→ FastAPI API (api/ dizininden build edilir)
         │        │
         │        ├─ main.py (uygulama giriş noktası)
         │        ├─ routes/ (5 endpoint modülü)
         │        ├─ services/ (Redis, rate limiter)
         │        └─ config.py (konfigürasyon)
         │
         └─→ FreeRADIUS (freeradius/ konfigürasyonları kullanır)
                  │
                  ├─ clients.conf (RADIUS client'ları)
                  ├─ mods-enabled/rest (FastAPI proxy)
                  └─ sites-enabled/default (RADIUS site config)
```

---

## Öneriler

1. **__pycache__ temizliği:** Depo'ya commit'ten önce `find . -type d -name __pycache__ -exec rm -rf {} +` çalıştır
2. **.pyc dosyaları:** `.gitignore` kuralları zaten yeterli; elle silmeye gerek yok
3. **Virtual environment:** `.venv/` veya `venv/` kullan; `.gitignore`'a zaten dahil
4. **Secret'lar:** `.env` dosyasını asla depo'ya commit'leme; `.env.example` kullan
5. **Yeni dosya eklemesi:** Tüm yeni Python dosyalarının `.gitignore` kurallarına uyduğundan emin ol
