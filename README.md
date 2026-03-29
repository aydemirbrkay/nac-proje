# Network Access Control (NAC) Sistemi

**FreeRADIUS + FastAPI + PostgreSQL + Redis** ile kurumsal ağlarda IEEE 802.1X / RADIUS tabanlı ağ erişim kontrolü.

Sistem; kimlik doğrulama (PAP/CHAP ve MAB), yetkilendirme ve VLAN atama, oturum muhasebesi (accounting) ile rate limiting özelliklerini Docker ile paketlenmiş dört servis üzerinde sunar.

---

## Mimari

```
  Ağ Cihazı (Switch / AP / VPN Gateway)
          │  RADIUS isteği (UDP 1812 / 1813)
          ▼
  ┌──────────────────┐        rlm_rest (HTTP)
  │   FreeRADIUS 3.2 │ ─────────────────────────▶ ┌─────────────────────────┐
  │  1812/udp  Auth  │                             │  FastAPI Policy Engine  │
  │  1813/udp  Acct  │ ◀─────────────────────────  │       port 8000         │
  └──────────────────┘        JSON cevap           └──────────┬──────────────┘
                                                              │
                                               ┌─────────────┴─────────────┐
                                               │                           │
                                    ┌──────────┴──────────┐   ┌───────────┴──────────┐
                                    │   PostgreSQL 18      │   │      Redis 8          │
                                    │   Kullanıcı/Grup/    │   │  Oturum Cache &       │
                                    │   Accounting DB      │   │  Rate Limiter         │
                                    └─────────────────────┘   └──────────────────────┘
```

---

## Servisler

| Konteyner | Teknoloji | Port | Görev |
|-----------|-----------|------|-------|
| `nac-api` | FastAPI + Python 3.13 | `8000` | Policy Engine — kimlik doğrulama, yetkilendirme, oturum kaydı |
| `nac-freeradius` | FreeRADIUS 3.2 | `1812/udp`, `1813/udp`, `18120/udp` | RADIUS sunucusu — rlm_rest ile API'ye bağlanır |
| `nac-postgres` | PostgreSQL 18 | `5432` | Kullanıcı, grup, VLAN ve accounting veritabanı |
| `nac-redis` | Redis 8 | `6379` | Aktif oturum cache'i ve rate limiting |

---

## Kullanıcı Grupları ve VLAN Atamaları

| Grup | VLAN | Açıklama |
|------|------|---------|
| `admin` | 10 | IT Yöneticileri — tam erişim |
| `employee` | 20 | Şirket çalışanları — standart erişim |
| `guest` | 30 | Misafirler — sınırlı erişim |
| `iot_devices` | 40 | IoT cihazları — yalnızca MAB (MAC Auth Bypass) |

---

## Kimlik Doğrulama Akışı

```
PAP/CHAP:  Kullanıcı → Switch → FreeRADIUS → rlm_rest → POST /auth → FastAPI → PostgreSQL
MAB:       Cihaz MAC → Switch → FreeRADIUS → rlm_rest → POST /auth → FastAPI → mac_devices tablosu
```

Başarılı doğrulama sonrası FreeRADIUS `/authorize` endpoint'inden VLAN atribütlerini alır ve switch'e iletir.

---

## Gereksinimler

- [Docker Engine](https://docs.docker.com/engine/install/) 24+
- [Docker Compose](https://docs.docker.com/compose/) v2

---

## Kurulum ve Çalıştırma

### 1. Repoyu klonlayın

```bash
git clone https://github.com/aydemirbrkay/nac-proje.git
cd nac-proje/nac-system
```

### 2. Ortam değişkenlerini yapılandırın

```bash
cp .env.example .env
```

`.env` dosyasını açıp şifreleri ve secret key'i üretim ortamına uygun değerlerle doldurun:

```bash
POSTGRES_PASSWORD=guclu-ve-benzersiz-bir-sifre
REDIS_PASSWORD=guclu-ve-benzersiz-bir-sifre
SECRET_KEY=en-az-32-karakter-rastgele-deger
RADIUS_SECRET=radius-paylaşımli-anahtar   # clients.conf ile eşleşmeli
```

### 3. Sistemi başlatın

```bash
docker-compose up -d
```

### 4. Servislerin hazır olup olmadığını kontrol edin

```bash
docker-compose ps
```

Tüm konteynerlerin `(healthy)` durumuna gelmesi beklenir (ilk başlatmada ~30 saniye sürebilir).

```bash
curl -s http://localhost:8000/health
# {"status":"healthy","services":{"redis":"up","postgres":"up"}}
```

---

## API Endpoint'leri

### FreeRADIUS Entegrasyonu (rlm_rest)

| Method | Endpoint | Açıklama |
|--------|---------|---------|
| `POST` | `/auth` | Kimlik doğrulama (PAP/CHAP + MAB) |
| `POST` | `/authorize` | Yetkilendirme + VLAN atribüt dönüşü |
| `POST` | `/accounting` | Oturum kaydı (Start / Interim-Update / Stop) |

### Kullanıcı Yönetimi (JWT korumalı)

| Method | Endpoint | Açıklama | Auth |
|--------|---------|---------|------|
| `POST` | `/admin/login` | Admin girişi, JWT token döner | ❌ |
| `GET` | `/users` | Tüm kullanıcı listesi | ✅ JWT |
| `POST` | `/users` | Yeni kullanıcı oluştur | ✅ JWT |
| `GET` | `/users/{username}` | Kullanıcı detayı | ✅ JWT |
| `PUT` | `/users/{username}` | Kullanıcı grubunu değiştir | ✅ JWT |
| `DELETE` | `/users/{username}` | Kullanıcıyı sil | ✅ JWT |
| `PUT` | `/users/{username}/password` | Şifre değiştir | ✅ JWT |

### Yardımcı

| Method | Endpoint | Açıklama |
|--------|---------|---------|
| `GET` | `/sessions/active` | Redis'teki aktif oturumlar |
| `GET` | `/health` | Servis sağlık durumu |

### Örnek İstekler

**Kimlik Doğrulama**

```bash
curl -s -X POST http://localhost:8000/auth \
  -H "Content-Type: application/json" \
  -d '{"username": "admin_ali", "password": "Admin1234!"}'
```

**Yetkilendirme**

```bash
curl -s -X POST http://localhost:8000/authorize \
  -H "Content-Type: application/json" \
  -d '{"username": "emp_mehmet"}'
```

**Aktif Oturumlar**

```bash
curl -s http://localhost:8000/sessions/active | python3 -m json.tool
```

---

## Dinamik Kullanıcı Yönetimi

Kullanıcılar `init.sql` içindeki statik verilerle sınırlı değildir. Admin yetkisiyle çalışan
sistem üzerinden kullanıcı eklenebilir, güncellenebilir ve silinebilir.

> Tüm yönetim endpoint'leri JWT token gerektirir. İşlem sırasına göre aşağıdaki adımlar izlenmelidir.

### Adım 1 — Admin Token Al

```bash
curl -X POST http://localhost:8000/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin_ali", "password": "Admin1234!"}'
```

Cevap:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 28800
}
```

Token'ı değişkene atayın (sonraki komutlarda kullanılır):
```bash
TOKEN="eyJhbGciOiJIUzI1NiJ9..."
```

> Token 8 saat geçerlidir. Yalnızca `admin` grubundaki kullanıcılar token alabilir.
> 5 başarısız girişten sonra hesap 5 dakika kilitlenir (`429 Too Many Requests`).

---

### Adım 2 — Yeni Kullanıcı Oluştur

```bash
curl -X POST http://localhost:8000/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username": "emp_yeni", "password": "Sifre1234!", "group": "employee"}'
```

Başarılı yanıt `201 Created`:
```json
{"username": "emp_yeni", "group": "employee", "vlan_id": "20", "is_online": false}
```

**Grup seçenekleri ve VLAN atamaları:**

| Grup | VLAN |
|------|------|
| `admin` | 10 |
| `employee` | 20 |
| `guest` | 30 |

> Şifre en az 8 karakter olmalıdır. Var olan kullanıcı adıyla oluşturma `409 Conflict` döner.

---

### Adım 3 — Kullanıcı Listesi

```bash
curl http://localhost:8000/users \
  -H "Authorization: Bearer $TOKEN"
```

---

### Adım 4 — Kullanıcı Detayı

```bash
curl http://localhost:8000/users/emp_yeni \
  -H "Authorization: Bearer $TOKEN"
```

`is_online: true` ise kullanıcının Redis'te aktif oturumu vardır.

---

### Adım 5 — Grup Değiştir

```bash
curl -X PUT http://localhost:8000/users/emp_yeni \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"group": "guest"}'
```

VLAN ataması otomatik güncellenir (örn. `employee` VLAN 20 → `guest` VLAN 30).

---

### Adım 6 — Şifre Değiştir

```bash
curl -X PUT http://localhost:8000/users/emp_yeni/password \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"new_password": "YeniSifre5678!"}'
```

---

### Adım 7 — Kullanıcı Sil

```bash
curl -X DELETE http://localhost:8000/users/emp_yeni \
  -H "Authorization: Bearer $TOKEN"
```

Başarılı yanıt `204 No Content` (boş gövde).
Kullanıcı PostgreSQL'den (`radcheck`, `radusergroup`, `radreply`) ve Redis'teki aktif oturumlardan silinir.

> **Not:** Silme işlemi ağ katmanında anlık etki etmez. Aktif bir ağ oturumu varsa, switch
> yeniden kimlik doğrulama yapana kadar erişim devam edebilir (RADIUS CoA kapsam dışıdır).

---

### Hata Kodları

| Durum | HTTP Kodu |
|-------|-----------|
| Var olan kullanıcı adıyla oluşturma | `409 Conflict` |
| Kullanıcı bulunamadı | `404 Not Found` |
| Geçersiz grup adı | `422 Unprocessable Entity` |
| 8 karakterden kısa şifre | `422 Unprocessable Entity` |
| Yanlış admin şifresi | `401 Unauthorized` |
| Admin grubunda olmayan kullanıcı | `403 Forbidden` |
| Eksik veya geçersiz JWT token | `401 Unauthorized` |
| Çok fazla başarısız giriş denemesi | `429 Too Many Requests` |

---

## Veritabanı Şeması

PostgreSQL'de FreeRADIUS uyumlu tablolar:

| Tablo | Açıklama |
|-------|---------|
| `radcheck` | Kullanıcı kimlik bilgileri (bcrypt hash) |
| `radreply` | Kullanıcıya özel RADIUS atribütleri |
| `radusergroup` | Kullanıcı–grup ilişkileri |
| `radgroupreply` | Grup bazlı VLAN atamaları |
| `radacct` | Accounting / oturum kayıtları |
| `mac_devices` | MAB için kayıtlı cihaz listesi |

Başlangıç verileri (`nac-system/postgres/init.sql`) ile örnek kullanıcılar ve MAB cihazları otomatik olarak yüklenir.

---

## Test Scriptleri

```bash
chmod +x tests/*.sh

# Tüm API endpoint testleri
./tests/test_all.sh

# RADIUS entegrasyon testi (radclient gerektirir)
./tests/test_radius.sh

# Çoklu kullanıcı senaryosu
./tests/test_multi_user.sh
```

---

## Ortam Değişkenleri

Tüm değişkenlerin tam açıklaması için `.env.example` dosyasına bakın.

| Değişken | Açıklama | Varsayılan |
|----------|---------|----------|
| `POSTGRES_DB` | Veritabanı adı | `nac_db` |
| `POSTGRES_USER` | DB kullanıcı adı | `nac_admin` |
| `POSTGRES_PASSWORD` | DB şifresi | — |
| `REDIS_PASSWORD` | Redis şifresi | — |
| `SECRET_KEY` | Uygulama imza anahtarı | — |
| `RADIUS_SECRET` | FreeRADIUS paylaşımlı anahtar | `testing123` |
| `MAX_AUTH_ATTEMPTS` | Maks. başarısız giriş denemesi | `5` |
| `AUTH_LOCKOUT_SECONDS` | Hesap kilitleme süresi (saniye) | `300` |

---

## Güvenlik Notları

> Bu proje geliştirme ve eğitim amaçlıdır. Production ortamına taşımadan önce aşağıdaki adımları uygulayın.

- `RADIUS_SECRET=testing123` değerini mutlaka değiştirin; `freeradius/clients.conf` dosyasında da aynı değeri güncelleyin.
- `freeradius/clients.conf` dosyasındaki `172.20.0.0/24` subnet'ini yalnızca gerçek NAS cihazlarınızı kapsayacak şekilde daraltın.
- FreeRADIUS debug modu (`-X` flag) `docker-compose.yml` içindeki `command` satırından production'da kaldırılmalıdır.
- `.env` dosyasını asla sürüm kontrolüne eklemeyin (`.gitignore`'da zaten hariç tutulmuştur).

---

## Proje Yapısı

```
nac-system/
├── docker-compose.yml          # Tüm servis tanımları
├── .env.example                # Ortam değişkeni şablonu
├── api/                        # FastAPI Policy Engine
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                 # Uygulama giriş noktası + NAS simülasyonu
│   ├── config.py               # Ayarlar (pydantic-settings)
│   ├── database.py             # Async PostgreSQL bağlantısı
│   ├── models.py               # SQLAlchemy ORM modelleri
│   ├── schemas.py              # Pydantic request/response şemaları
│   ├── routes/
│   │   ├── Authentication.py   # POST /auth
│   │   ├── authorize.py        # POST /authorize
│   │   ├── accounting.py       # POST /accounting
│   │   ├── users.py            # GET+POST /users, kullanıcı CRUD
│   │   ├── auth_admin.py       # POST /admin/login, JWT bağımlılığı
│   │   └── sessions.py         # GET /sessions/active
│   └── services/
│       ├── redis_service.py    # Redis bağlantısı
│       └── rate_limiter.py     # Brute-force koruması (key_prefix ile admin/user ayrımı)
├── postgres/
│   └── init.sql                # Şema + örnek kullanıcı/grup verileri
├── redis/
│   └── redis.conf              # Redis konfigürasyonu
├── freeradius/
│   ├── clients.conf            # NAS tanımları
│   ├── mods-enabled/rlm_rest   # REST modülü — FastAPI entegrasyonu
│   └── sites-enabled/default   # Auth/authorize/accounting akışları
└── tests/
    ├── test_all.sh
    ├── test_radius.sh
    └── test_multi_user.sh
```

---

---

## Lisans

MIT
