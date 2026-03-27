# Network Access Control (NAC) Sistemi

**FreeRADIUS + FastAPI + PostgreSQL + Redis** ile kurumsal ağlarda IEEE 802.1X / RADIUS tabanlı ağ erişim kontrolü.

Sistem; kimlik doğrulama (PAP/CHAP ve MAB), yetkilendirme ve VLAN atama, oturum muhasebesi (accounting) ile rate limiting özelliklerini Docker ile paketlenmiş dört servis üzerinde sunar.

---

## Mimari

```
Ağ Cihazı (Switch/AP)
        │  RADIUS (UDP 1812/1813)
        ▼
  ┌─────────────┐      HTTP/REST       ┌─────────────────────┐
  │ FreeRADIUS  │ ──────────────────►  │  FastAPI            │
  │  3.2        │   rlm_rest modülü    │  Policy Engine      │
  └─────────────┘                      │  (Python 3.13)      │
                                       └──────────┬──────────┘
                                                  │
                              ┌───────────────────┼───────────────────┐
                              ▼                                       ▼
                     ┌────────────────┐                    ┌──────────────────┐
                     │  PostgreSQL 18 │                    │    Redis 8       │
                     │  Kullanıcı DB  │                    │  Oturum Cache    │
                     │  Accounting    │                    │  Rate Limiting   │
                     └────────────────┘                    └──────────────────┘
```

---

## Servisler

| Servis       | İmaj                              | Port(lar)                | Görev                                 |
|--------------|-----------------------------------|--------------------------|---------------------------------------|
| freeradius   | freeradius/freeradius-server:3.2  | 1812/udp, 1813/udp       | RADIUS kimlik doğrulama + accounting  |
| api          | python:3.13 (Dockerfile)          | 8000/tcp                 | Policy Engine — REST API              |
| postgres     | postgres:18-alpine                | 5432/tcp                 | Kullanıcı, grup ve accounting veritabanı |
| redis        | redis:8-alpine                    | 6379/tcp                 | Oturum cache ve rate limiting         |

---

## Gereksinimler

- [Docker](https://docs.docker.com/get-docker/) 24+
- [Docker Compose](https://docs.docker.com/compose/install/) 2.20+

---

## Kurulum ve Çalıştırma

### 1. Repoyu klonla

```bash
git clone https://github.com/aydemirbrkay/nac-proje.git
cd nac-proje/nac-system
```

### 2. Ortam değişkenlerini ayarla

```bash
cp .env.example .env
```

`.env` dosyasını açıp production için güçlü şifrelerle güncelle:

```env
POSTGRES_PASSWORD=güçlü_bir_şifre
REDIS_PASSWORD=güçlü_bir_şifre
SECRET_KEY=en_az_32_karakter_rastgele_anahtar
```

### 3. Sistemi başlat

```bash
docker compose up -d
```

İlk çalıştırmada Docker imajları indirilip derlenir (~2-3 dakika). Sağlık durumunu takip et:

```bash
docker compose ps
```

Tüm servisler `(healthy)` durumuna geçince sistem hazırdır.

### 4. Doğrula

```bash
curl http://localhost:8000/health
```

```json
{"status": "healthy", "services": {"redis": "up", "postgres": "up"}}
```

---

## Ortam Değişkenleri

Tüm değişkenler `nac-system/.env.example` dosyasında belgelenmiştir.

| Değişken               | Varsayılan                          | Açıklama                                      |
|------------------------|-------------------------------------|-----------------------------------------------|
| `POSTGRES_DB`          | `nac_db`                            | Veritabanı adı                                |
| `POSTGRES_USER`        | `nac_admin`                         | Veritabanı kullanıcısı                        |
| `POSTGRES_PASSWORD`    | —                                   | **Değiştirilmesi zorunlu**                    |
| `REDIS_PASSWORD`       | —                                   | **Değiştirilmesi zorunlu**                    |
| `DATABASE_URL`         | `postgresql+asyncpg://...`          | FastAPI için bağlantı URL'si                  |
| `REDIS_URL`            | `redis://:...@redis:6379/0`         | Redis bağlantı URL'si                         |
| `SECRET_KEY`           | —                                   | JWT imzalama anahtarı (min 32 karakter)       |
| `RADIUS_SECRET`        | `testing123`                        | FreeRADIUS shared secret                      |
| `MAX_AUTH_ATTEMPTS`    | `5`                                 | Başarısız giriş limiti (rate limiting)        |
| `AUTH_LOCKOUT_SECONDS` | `300`                               | Kilitleme süresi (saniye)                     |

---

## API Endpoints

Servis ayağa kalktıktan sonra Swagger UI: `http://localhost:8000/docs`

| Method | Endpoint           | Açıklama                                      |
|--------|--------------------|-----------------------------------------------|
| POST   | `/auth`            | PAP/CHAP kimlik doğrulama (FreeRADIUS → API)  |
| POST   | `/authorize`       | Grup bazlı yetkilendirme ve VLAN atama        |
| POST   | `/accounting`      | Oturum muhasebesi (Start / Interim / Stop)    |
| GET    | `/users`           | Kayıtlı kullanıcılar                          |
| GET    | `/sessions/active` | Redis'teki aktif oturumlar                    |
| GET    | `/health`          | Servis sağlık durumu                          |

---

## Kullanıcı Grupları ve VLAN Yapısı

| Grup       | VLAN | Kullanıcılar                                          |
|------------|------|-------------------------------------------------------|
| admin      | 10   | admin_ali, admin_zeynep, admin_burak                  |
| employee   | 20   | emp_mehmet, emp_ayse, emp_fatma, emp_can, emp_deniz   |
| guest      | 30   | guest_user, guest_ahmet, guest_elif, guest_tamir      |

> Tüm şifreler bcrypt (cost=12) ile hashlenmiştir. Test şifresi: `Admin1234!` (admin), `Emp1234!` (employee), `Guest1234!` (guest)

---

## Test Araçları

```bash
# Tüm endpoint testleri
cd nac-system/tests
bash test_all.sh

# RADIUS PAP/MAB testleri (radclient gerektirir)
bash test_radius.sh

# Çoklu kullanıcı simülasyonu
bash test_multi_user.sh
```

---

## Proje Yapısı

```
nac-system/
├── api/                    # FastAPI Policy Engine
│   ├── main.py             # Uygulama ve NAS simülasyonu
│   ├── routes/
│   │   ├── Authentication.py   # /auth — PAP/CHAP + MAB
│   │   ├── authorize.py        # /authorize — VLAN atama
│   │   ├── accounting.py       # /accounting — oturum kaydı
│   │   ├── users.py            # /users
│   │   └── sessions.py         # /sessions/active
│   ├── services/
│   │   ├── redis_service.py    # Redis istemcisi
│   │   └── rate_limiter.py     # Rate limiting
│   ├── models.py               # SQLAlchemy modelleri
│   ├── schemas.py              # Pydantic şemaları
│   ├── database.py             # Async engine
│   ├── config.py               # Ayarlar (.env okuma)
│   ├── requirements.txt
│   └── Dockerfile
├── freeradius/
│   ├── clients.conf            # NAS istemci tanımları
│   ├── mods-enabled/rlm_rest   # REST modülü konfigürasyonu
│   └── sites-enabled/default   # Virtual server — auth/accounting akışı
├── postgres/
│   └── init.sql                # Şema + seed data (bcrypt şifreli)
├── redis/
│   └── redis.conf              # Redis konfigürasyonu
├── tests/
│   ├── test_all.sh
│   ├── test_radius.sh
│   └── test_multi_user.sh
├── docker-compose.yml
├── .env.example
└── .gitignore
```

---

## Teknik Rapor

Sistemin detaylı mimari analizi, akış diyagramları ve veritabanı şema belgeleri:

- [NAC Teknik Raporu](docs/README.md)

---

## Lisans

MIT
