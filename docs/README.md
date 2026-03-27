# NAC Sistem Derinlemesine Analizi

## Genel Bakış

Bu dokümantasyon, FreeRADIUS tabanlı Ağ Erişim Denetimi (NAC) sisteminin kapsamlı mimarî analizidir. Python (FastAPI), PostgreSQL, Redis ve Docker teknolojileri kullanılarak oluşturulmuş bu sistem, ağ kullanıcılarının kimlik doğrulama, yetkilendirme ve oturum yönetimini gerçekleştirmektedir. 41 dosyadan oluşan bu proje, üretim ortamında güvenli ve ölçeklenebilir NAC çözümü sunmaktadır.

## Proje Tanımı

**Proje Adı:** NAC System (Network Access Control System)
**Teknoloji Yığını:** Python 3.13, FastAPI, SQLAlchemy, asyncpg, PostgreSQL 18, Redis 8, FreeRADIUS 3.2
**Kapsam:** 41 kaynak dosyası, 5 Docker servisi, 8.695 satır analiz dokümantasyonu
**Amaç:** PAP, MAB ve Accounting protokolleri üzerinden ağ erişim kontrolü ve kimlik doğrulama

Bu analiz önemlidir çünkü sistemin her katmanını (Docker, ağ, Python mimarisi, veritabanı, RADIUS) detaylı olarak belgeler; mimarlık kararlarını açıklar; üretim dönüşüme hazırlık sağlar.

## Dokümantasyon Haritası

| # | Dosya | İçerik | Hedef Okuyucu |
|---|-------|--------|---------------|
| 1 | 📋 [00-dosya-envanteri.md](00-dosya-envanteri.md) | Dosya envanteri (41 dosya cataloglanmış) | Tüm okuyucular |
| 2 | 🐳 [01-servis-analizi.md](01-servis-analizi.md) | 5 Docker servisi analizi | DevOps, Sistem Mimarları |
| 3 | 🔗 [02-network-baglanti.md](02-network-baglanti.md) | Ağ topolojisi ve bağlantı haritası | DevOps, Network Uzmanları |
| 4 | 🏗️ [03-dockerfile-anatomisi.md](03-dockerfile-anatomisi.md) | Dockerfile katmanları ve optimizasyon | DevOps, Container Uzmanları |
| 5 | 💾 [04-volume-veri-yonetimi.md](04-volume-veri-yonetimi.md) | Veri kalıcılığı ve Volume yönetimi | DevOps, Veritabanı Yöneticileri |
| 6 | 🌊 [05-istek-akisi.md](05-istek-akisi.md) | İstek akışları (3 senaryo: PAP, MAB, Accounting) | Tüm okuyucular |
| 7 | 🐍 [06-python-mimarisi-ve-dosyalar.md](06-python-mimarisi-ve-dosyalar.md) | Python mimarisi (12 dosya, 3 katman) | Python Geliştiricileri, Mimarlar |
| 8 | 🗄️ [07-veritabani-freeradius.md](07-veritabani-freeradius.md) | Veritabanı şeması + FreeRADIUS konfigürasyonu | Veritabanı Yöneticileri, Network Uzmanları |
| 9 | 📄 [08-diger-dosyalar.md](08-diger-dosyalar.md) | Kalan dosyalar (25+ dosya) | Tüm okuyucular |
| 10 | 📚 [GLOSSARY.md](GLOSSARY.md) | Teknik terimler sözlüğü (Türkçe ↔ İngilizce) | Tüm okuyucular |

**Not:** `diagrams/` klasörü mimarî diyagramlar için rezerve edilmiştir (Mermaid formatı).

## Hızlı Başlangıç (Bu Dokümantasyonu Okuyanlar İçin)

### Hedef Okuyucu Segmentleri

- **Yazılım Mimarları** → Sistem tasarımı, katmanlar, request flow
- **DevOps Mühendisleri** → Docker, ağ, Volume, healthcheck
- **Python Geliştiricileri** → FastAPI, SQLAlchemy, async patterns, code organization
- **Network/RADIUS Uzmanları** → Auth protocols, FreeRADIUS config, VLAN, MAB flow

### Önerilen Okuma Sırası

**Herkese:**
1. Bu README (2 dakika) — Genel bakış ve navigasyon
2. [00-dosya-envanteri.md](00-dosya-envanteri.md) (5 dakika) — Proje yapısı
3. [01-servis-analizi.md](01-servis-analizi.md) (10 dakika) — Servis genel bakışı
4. [02-network-baglanti.md](02-network-baglanti.md) (10 dakika) — Servisler nasıl bağlanıyor
5. [05-istek-akisi.md](05-istek-akisi.md) (15 dakika) — Kimlik doğrulama akışları

**Python Geliştiricileri için:**
- [06-python-mimarisi-ve-dosyalar.md](06-python-mimarisi-ve-dosyalar.md) (20 dakika) — Code organization, patterns
- [07-veritabani-freeradius.md](07-veritabani-freeradius.md) (15 dakika) — ORM models, SQL queries

**DevOps/SysOps Mühendisleri için:**
- [03-dockerfile-anatomisi.md](03-dockerfile-anatomisi.md) (10 dakika) — Container build
- [04-volume-veri-yonetimi.md](04-volume-veri-yonetimi.md) (10 dakika) — Data persistence
- [01-servis-analizi.md](01-servis-analizi.md) (health checks, environment)

**Network/RADIUS Uzmanları için:**
- [02-network-baglanti.md](02-network-baglanti.md) (ağ topolojisi)
- [07-veritabani-freeradius.md](07-veritabani-freeradius.md) (RADIUS config, auth protocols)
- [05-istek-akisi.md](05-istek-akisi.md) (PAP, MAB, Accounting flows)

## Proje Mimarisi (Bir Sayfalık Özet)

```
┌─────────────────────────────────────────────────────────────┐
│                      Network Device / Client                │
│                    (RADIUS Client: 192.168.1.x)             │
└────────────────────────────┬────────────────────────────────┘
                             │ RADIUS Requests (UDP:1812-1813)
                             │ RADIUS-Secret-Key
                             ▼
        ┌────────────────────────────────────────────┐
        │        FreeRADIUS Container                │
        │     (port 1812, 1813, 18120)               │
        │  ┌──────────────────────────────────────┐  │
        │  │  RADIUS Server (PAP, MAB, Acct)     │  │
        │  │  Module: rlm_rest (REST API calls)  │  │
        │  └────────┬─────────────────────────────┘  │
        │           │ HTTP REST Calls                │
        └───────────┼──────────────────────────────┬─┘
                    │                              │
     ┌──────────────▼──────────────┐  ┌───────────▼──────────┐
     │   API Container (FastAPI)   │  │  PostgreSQL (DB)     │
     │   - POST /auth              │  │  - users table       │
     │   - POST /authorize         │  │  - sessions table    │
     │   - POST /accounting        │  │  - groups table      │
     │   - GET /users              │  │  - devices table     │
     │   - GET /sessions/active    │  │  - vlans table       │
     │   - GET /health             │  │  - rules table       │
     └─────────────┬─────────────┘  └─────────────┬─────────┘
                   │ DB Queries                   │
                   │ (asyncpg)                    │ Connections:
     ┌─────────────▼─────────────────────────────▼──────────┐
     │           PostgreSQL Network Layer                   │
     │   (async conn pool, NOTIFY for sessions)            │
     └──────────────────────┬──────────────────────────────┘
                            │
     ┌──────────────────────▼────────────────────┐
     │         Redis Container (Cache)           │
     │  - Session state caching                  │
     │  - User permissions cache                 │
     │  - Rate limiting counters                 │
     └─────────────────────────────────────────┘
```

**Servisler:**
1. **FreeRADIUS** → RADIUS server, ağ cihazlarından requests alır
2. **API** → FastAPI, auth/authorize/accounting logic
3. **PostgreSQL** → Persistent data storage
4. **Redis** → Session cache, permission cache
5. **pgAdmin** (optional) → Database management UI

**Ağ Katmanları:**
- Docker Compose network: `nac-network` (default bridge)
- Host ports: FreeRADIUS (1812-1813), API (8000), pgAdmin (5050)
- Internal DNS: Service names resolve to container IPs

## Anahtar Bulgular

### ✅ Güçlü Yönler

- **Async-first tasarım:** FastAPI + asyncpg, high concurrency support
- **Modular architecture:** Servisler düzgün ayrılmış, Docker-friendly
- **Flexible auth:** PAP ve MAB destekli, REST API esnekliği
- **Data persistence:** PostgreSQL + Redis kombinasyonu, recovery capability
- **Monitoring:** Health checks her serviste tanımlı

### ⚠️ Üretim Hazırlık Notları

- **Secret management:** `.env` dosyası version control'e sokulmuş, production'da Vault/Secrets Manager kullanılmalı
- **TLS/SSL:** RADIUS üzerinde DTLS, API üzerinde HTTPS, Docker compose'ta henüz basit HTTP
- **Database:** PostgreSQL max_connections değeri, connection pooling optimization gerekebilir
- **Logging:** Centralized logging (ELK, CloudWatch) konfigürasyonu eksik
- **Rate limiting:** FreeRADIUS ve API endpoint'leri için DDoS koruması

### 🔒 Güvenlik Notları

- **RADIUS Secret:** `RADIUS_SECRET` ortam değişkeni olarak saklanıyor; production'da rotasyonu önerilir
- **Database passwords:** `DATABASE_PASSWORD` cleartext `.env`; use secrets management
- **API auth:** Şu anda RADIUS secret ile trust, bearer token/mTLS alternative'ler araştırılmalı
- **Network isolation:** Docker network yerine separate network interfaces recommended for production
- **Audit logging:** Accounting records tutulsa da, immutable audit log solution önerilir

## İstatistikler

| Metrik | Sayı |
|--------|------|
| Toplam dosya sayısı | 41 |
| Python kaynak dosyası (.py) | 14 |
| Docker servisi | 5 |
| Veritabanı tablosu | 6 |
| API endpoint | 5+ |
| RADIUS port | 3 |
| Dokümantasyon dosyası | 10 |
| Analiz satır sayısı | 8.695 |
| Konfigürasyon dosyası | 4 |
| Shell betiği | 2 |

## Kullanılan Teknolojiler

| Katman | Teknoloji | Versiyon |
|--------|-----------|----------|
| **Web Framework** | FastAPI | 0.100+ |
| **Python Runtime** | Python | 3.13 |
| **ORM** | SQLAlchemy | 2.0+ |
| **Async Driver** | asyncpg | 0.28+ |
| **Data Validation** | Pydantic | 2.0+ |
| **Database** | PostgreSQL | 18 |
| **Cache** | Redis | 8 |
| **Auth Server** | FreeRADIUS | 3.2 |
| **Container** | Docker | Latest |
| **Orchestration** | Docker Compose | 1.29+ |
| **Admin Panel** | pgAdmin | 4+ |

## Dokümantasyon Türü

- ✅ **Teknik Derinlik:** Her dosya, her direktif, her konfigürasyon açıklanmış
- ✅ **Pedagojik Yaklaşım:** "Ne" (What) + "Neden" (Why) + "Nasıl" (How)
- ✅ **Dil Desteği:** Türkçe birincil, İngilizce terimler ve kod (GLOSSARY.md'de)
- ✅ **Görsel:** ASCII diyagramlar, request flow akış şemaları, SQL query örnekleri
- ✅ **Praktik:** Gerçek konfigürasyon örnekleri, troubleshooting notları, production tips
- ✅ **Cross-linked:** Dosyalar arasında referans linkler, ilişkili bölümler bağlantılı

## Lisans & Atıf

Generated with Claude Code (Anthropic's official Claude CLI)
Analysis Date: 2026-03-23
Version: 1.0.0

---

## İlgili Kaynaklar

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [FreeRADIUS Official Docs](https://freeradius.org/)
- [PostgreSQL 18 Docs](https://www.postgresql.org/docs/18/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [SQLAlchemy 2.0 Docs](https://docs.sqlalchemy.org/)

## Sorular & Feedback

Bu dokümantasyon açık projedir. Improvements, clarifications, veya eklemeler için:
1. İlgili `.md` dosyasında kesin bölümü bulun
2. Değişiklik nedenini açıklayan bir not ekleyin
3. Diğer bölümlere cross-reference'lar güncelleyin

---

**Son Güncelleme:** 2026-03-23
**Durum:** Complete Analysis (Türkçe, İngilizce terimler, Pedagogical approach)
