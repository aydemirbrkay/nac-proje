# Teknik Terimler Sözlüğü (Technical Glossary)

NAC Sistem Derinlemesine Analizi'nde kullanılan Türkçe ve İngilizce teknik terimler.

---

## A

### Accounting (Muhasebe/Oturum Kaydı)
**Türkçe:** Muhasebe, Oturum Kaydı
**İngilizce:** Accounting
**Tanım:** RADIUS protokolünün üçüncü aşaması. Kullanıcı oturumu başladıktan sonra, oturum süresini, veri transferini ve kaynak kullanımını kaydetme mekanizması. FreeRADIUS `Accounting-Request` ve `Accounting-Response` mesajları kullanır.
**Örnek:** `POST /accounting { "user": "john", "session_id": "sess_123", "duration": 3600 }`
**Bağlantılı:** PAP, MAB, RADIUS

### Active-Active Deployment (Aktif-Aktif Dağıtım)
**Türkçe:** Aktif-Aktif Dağıtım
**Tanım:** Birden fazla API sunucusu aynı anda istek işlemektedir. Yük dengeleme ve failover sağlar.
**Notlar:** Şu anda docker-compose'ta single API instance; production'da multiple API containers + load balancer önerilir.

### Async/Asynchronous (Asenkron)
**Türkçe:** Asenkron
**İngilizce:** Async, Asynchronous
**Tanım:** Non-blocking işlem modeli. FastAPI, asyncpg ve PostgreSQL async driver'lar ile asenkron request handling. Aynı thread'de birden fazla IO operation paralel hale getirilebilir.
**Örnek:** `async def authenticate(user: str, password: str):`
**Bağlantılı:** Event Loop, FastAPI, asyncpg

### asyncpg
**Türkçe:** asyncpg
**Tanım:** PostgreSQL için Python async driver. SQLAlchemy tarafından kullanılır. Non-blocking database connections sağlar.
**Bağlantılı:** SQLAlchemy, PostgreSQL, Async

---

## B

### Backend (Arka Uç)
**Türkçe:** Arka Uç, Sunucu Tarafı
**Tanım:** Ağ istemcisinden gelen RADIUS request'lerini işleyen sunucu tarafı. Bu projede FreeRADIUS + FastAPI API.

### Bearer Token (Taşıyıcı Token)
**Türkçe:** Taşıyıcı Token
**Tanım:** HTTP Authorization header'ında gönderilentoken. `Authorization: Bearer <token>` formatında. Şu anda bu projede uygulanmamış; future security enhancement.

### Bridge Network (Köprü Ağı)
**Türkçe:** Köprü Ağı
**İngilizce:** Bridge Network
**Tanım:** Docker'ın default network driver'ı. Bu projede `docker-compose` services arasında default bridge network kullanılır. Servis adları container adları olarak DNS çözülür.
**Örnek:** `api` servisi, `postgres` servisine `postgresql://postgres:5432` yerine `postgresql://postgres:5432` ile bağlanabilir.
**Bağlantılı:** Docker Network, Docker Compose

---

## C

### Cache (Önbellek)
**Türkçe:** Önbellek
**İngilizce:** Cache
**Tanım:** Sık erişilen verilerin hızlı erişim için bellekte saklanması. Bu projede Redis, session ve permission cache'i yapar.
**Örnek:** Kullanıcı izinleri database'den alınıp Redis'e cache edilir; sonraki request'lerde Redis'ten döner.

### Connection Pool (Bağlantı Havuzu)
**Türkçe:** Bağlantı Havuzu
**Tanım:** Tekrar tekrar database bağlantısı açıp kapamak yerine, pool'da saklanan bağlantıları reuse etme. Performans artışı sağlar.
**Bağlantılı:** asyncpg, SQLAlchemy, PostgreSQL

### Container (Konteyner)
**Türkçe:** Konteyner
**Tanım:** Uygulamanın ve bağımlılıklarının Docker image'ından oluşturulmuş yalıtılmış ortamı. Process, filesystem, network namespace'i olan izole environment.
**Örnek:** `docker run` komutu ile bir container başlatılır.
**Bağlantılı:** Docker, Image, Dockerfile

### CRUD (Create, Read, Update, Delete)
**Türkçe:** CRUD İşlemleri
**Tanım:** Veritabanı üzerinde temel dört işlem: Oluştur, Oku, Güncelle, Sil.
**Örnek:** SQLAlchemy ORM models.py'de CRUD işlemleri tanımlanır.

---

## D

### Database (Veritabanı)
**Türkçe:** Veritabanı
**Tanım:** Yapılandırılmış veri deposi. Bu projede PostgreSQL kullanılır.
**Bağlantılı:** PostgreSQL, Schema, Table, Row

### DHCP (Dynamic Host Configuration Protocol)
**Türkçe:** Dinamik Host Yapılandırma Protokolü
**Tanım:** Ağ cihazlarına otomatik IP adresi atayan protokol. Bu projede doğrudan kullanılmaz ama NAC context'inde cihaz tanımlama için kullanılabilir.

### Docker (Docker Engine)
**Türkçe:** Docker
**Tanım:** Konteyner orchestration ve runtime platform. Uygulamaları Docker image'larından container'larda çalıştırır.
**Bağlantılı:** Container, Image, Dockerfile, Docker Compose

### Docker Compose
**Türkçe:** Docker Compose
**Tanım:** Multi-container Docker uygulamaları orchestrate eden tool. `docker-compose.yml` dosyasında services, networks, volumes tanımlanır.
**Örnek:** `docker-compose up` komutu ile tüm services başlatılır.
**Bağlantılı:** Docker, Service, Container, Volume

### Dockerfile
**Türkçe:** Dockerfile
**Tanım:** Docker image oluşturmak için talimatlar içeren dosya. Base image, dependencies kurulumu, executable ayarlama adımları içerir.
**Örnek:** `FROM python:3.13`, `RUN pip install -r requirements.txt`, `CMD ["python", "main.py"]`
**Bağlantılı:** Docker, Image, Container

### DNS (Domain Name System)
**Türkçe:** Alan Adı Sistemi
**Tanım:** İP adresleri ile domain adlarını eşleyen sistem. Docker'da, servis adları container IP'lerine DNS tarafından çözülür.
**Örnek:** Docker network'te `api` servisi adı `172.20.0.2` IP'ye çözülür.

### DTLS (Datagram Transport Layer Security)
**Türkçe:** Datagram Taşıma Katmanı Güvenliği
**Tanım:** RADIUS gibi UDP-tabanlı protokoller için TLS benzeri şifreleme. RADIUS şifrelemesinde kullanılabilir.
**Bağlantılı:** RADIUS, UDP, TLS, Security

---

## E

### Endpoint (Uç Nokta)
**Türkçe:** Uç Nokta, API Bitiş Noktası
**Tanım:** API tarafından sunulan URL path ve HTTP metodu kombinasyonu. Bu projede: `/auth`, `/authorize`, `/accounting`, `/users`, `/sessions/active`.
**Örnek:** `POST /auth` endpoint'ine kimlik doğrulama request'i gönderilir.
**Bağlantılı:** API, FastAPI, HTTP

### Environment Variable (Ortam Değişkeni)
**Türkçe:** Ortam Değişkeni
**Tanım:** İşletim sistemi tarafından sağlanan, application tarafından okunan konfigürasyon değişkeni. `.env` dosyasından yüklenir.
**Örnek:** `DATABASE_URL`, `RADIUS_SECRET`, `REDIS_URL`
**Bağlantılı:** .env, Config, Pydantic Settings

---

## F

### FastAPI
**Türkçe:** FastAPI
**Tanım:** Modern, hızlı Python web framework. Async support, automatic API documentation (Swagger), Pydantic integration.
**Bağlantılı:** Python, Pydantic, Async, API, REST

### FreeRADIUS
**Türkçe:** FreeRADIUS
**Tanım:** Open-source RADIUS server. PAP, MAB, CHAP gibi auth protokollerini destekler. Bu projede network cihazlarından RADIUS request'lerini işler.
**Bağlantılı:** RADIUS, PAP, MAB, Server

---

## G

### Glossary (Sözlük)
**Türkçe:** Sözlük, Terimler Sözlüğü
**Tanım:** Bu dosya. Teknik terimlerin Türkçe ve İngilizce tanımlarını içerir.

### Graceful Shutdown (Nazik Kapatma)
**Türkçe:** Nazik Kapatma, Düzgün Kapatma
**Tanım:** Running process'ler tamamlandıktan sonra uygulamanın kapatılması. Incomplete transactions riskini azaltır.
**Notlar:** Docker Compose'ta `stop_grace_period` ile timeout ayarlanabilir.

### Group (Grup, Kullanıcı Grubu)
**Türkçe:** Grup, Kullanıcı Grubu
**Tanım:** Birden fazla kullanıcıyı bir araya getiren, ortak izinler atanan logical unit. Bu projede `groups` tablosunda saklanır.
**Örnek:** "Yönetim Grubu", "IT Destek Grubu"
**Bağlantılı:** User, Permission, VLAN

---

## H

### Health Check (Sağlık Kontrolü)
**Türkçe:** Sağlık Kontrolü, Sistem Kontrolü
**Tanım:** Servis'in sağlıklı çalışıp çalışmadığını belirten mekanizma. Docker Compose'ta `healthcheck` tanımı, periodik olarak endpoint'ler çağırır.
**Örnek:** FreeRADIUS için `radius-status`, API için `/health` endpoint'i.
**Bağlantılı:** Docker Compose, Endpoint, Monitoring

### HTTP (HyperText Transfer Protocol)
**Türkçe:** Köprü Metni Aktarım Protokolü
**Tanım:** Web'deki request-response protokolü. FastAPI API endpoint'leri HTTP üzerinden sunulur.
**Bağlantılı:** REST, Endpoint, API

### HTTPS (HTTP Secure)
**Türkçe:** Güvenli HTTP
**Tanım:** TLS/SSL şifrelemesi ile HTTP. Production'da API endpoint'leri HTTPS ile sunulmalı.
**Notlar:** Şu anda docker-compose'ta HTTP; production'da TLS sertifikaları gerekir.
**Bağlantılı:** HTTP, TLS, SSL, Security

---

## I

### Image (Docker Image)
**Türkçe:** Görüntü, Docker Görüntüsü
**Tanım:** Container'ı başlatmak için gerekli tüm dosya, library ve konfigürasyonları içeren template. Dockerfile'dan build edilir.
**Örnek:** `docker build -t api:1.0 .` komutu ile Dockerfile'dan image oluşturulur.
**Bağlantılı:** Dockerfile, Container, Docker

### Index (Dizin, Veritabanı Dizini)
**Türkçe:** Dizin, Veritabanı Dizini
**Tanım:** Database table'ında hızlı arama için oluşturulan veri yapısı. Primary key, unique, ve custom indexes.
**Örnek:** `users` table'ında `username` column'u indexed olabilir.
**Bağlantılı:** Database, Table, PostgreSQL

---

## J

### JSON (JavaScript Object Notation)
**Türkçe:** JSON
**Tanım:** Veri formatı. API request/response'larda JSON kullanılır.
**Örnek:** `{"username": "john", "password": "secret"}`
**Bağlantılı:** API, REST, Pydantic

---

## K

### Key-Value Store (Anahtar-Değer Deposu)
**Türkçe:** Anahtar-Değer Deposu
**Tanım:** Veri depolama modeli. Her veri benzersiz anahtar ile saklanır. Redis key-value store'dur.
**Örnek:** `"user:123:permissions" → ["read", "write"]`
**Bağlantılı:** Redis, Cache, NoSQL

---

## L

### Layer (Katman)
**Türkçe:** Katman
**Tanım:** Dockerfile'daki her `RUN`, `COPY`, `ADD` komutu bir layer oluşturur. Image, stacked layer'lardan oluşur.
**Örnek:** Base image layer + dependencies layer + application layer
**Bağlantılı:** Dockerfile, Docker, Image

### Load Balancer (Yük Dengeleyici)
**Türkçe:** Yük Dengeleyici
**Tanım:** Gelen request'leri multiple sunucular arasında dağıtan mekanizma. Production'da multiple API instance'ları arasında yük dağılamaz.
**Notlar:** Docker Compose'ta single API instance; production'da nginx/HAProxy gerekebilir.

### Logging (Günlükleme)
**Türkçe:** Günlükleme, Kayıt Tutma
**Tanım:** Uygulamanın işlemlerini, hataları, debug bilgilerini dosya/stdout'a yazması. Troubleshooting için essential.
**Bağlantılı:** Monitoring, Debugging, ELK

---

## M

### MAB (MAC Authentication Bypass)
**Türkçe:** MAC Adresi Tabanlı Yetkilendirme Bypass
**İngilizce:** MAC Authentication Bypass
**Tanım:** Kullanıcı kimliği yerine cihazın MAC adresini kullanarak ağ erişimi vermek. PAP'ın alternatifi.
**Örnek:** Yazıcı cihazı MAC adresi ile automatic credential sağlansın.
**Akış:** Network Switch → RADIUS Request (MAC) → FreeRADIUS → API (`/authorize` check MAC) → Accept/Reject
**Bağlantılı:** RADIUS, PAP, Authentication, Network

### Mapping (Eşleme)
**Türkçe:** Eşleme
**Tanım:** Bir veri yapısı ile diğerini ilişkilendirme. Python'da dict/mapping, database'de relational mapping (foreign keys).
**Örnek:** ORM model'deki `users.groups` relationship mapping.

### Middleware (Ara Yazılım)
**Türkçe:** Ara Yazılım
**Tanım:** Request-response pipeline'ının ortasında çalışan yazılım. Logging, authentication, error handling middleware'leri olabilir.
**Bağlantılı:** FastAPI, Pipeline, Request

### Migration (Veri Taşıması, Şema Migrasyon)
**Türkçe:** Şema Migrasyon, Veri Taşıması
**Tanım:** Database schema değişim süreci. Alembic gibi tool'lar ile version control edilir.
**Notlar:** Şu anda manuel schema setup; production'da migration script'leri önerilir.

### mTLS (Mutual TLS)
**Türkçe:** Karşılıklı TLS
**Tanım:** İki taraf da sertifika ile verify etme. API ve RADIUS arasında mTLS önerilir.
**Notlar:** Şu anda uygulanmamış; security enhancement candidate.

---

## N

### NAC (Network Access Control)
**Türkçe:** Ağ Erişim Denetimi
**İngilizce:** Network Access Control
**Tanım:** Ağ kaynaklarına erişimi kimlik doğrulama ve yetkilendirme ile kontrol eden sistem. Bu projenin ana konusu.
**Bağlantılı:** RADIUS, PAP, MAB, Authentication

### Namespace (Ad Alanı)
**Türkçe:** Ad Alanı
**Tanım:** Docker'da process, filesystem, network namespace'leri izole ortam oluşturur.
**Örnek:** Container'ın kendi PID 1, kendi network interface'leri vardır.
**Bağlantılı:** Container, Docker, Isolation

### Network (Ağ)
**Türkçe:** Ağ
**Tanım:** İki veya daha fazla bilgisayarın veri paylaştığı sistem. Docker Compose'ta `nac-network` adlı internal network tanımlanmıştır.
**Bağlantılı:** Docker Network, Bridge, Service

### Notification (Bildirim)
**Türkçe:** Bildirim, Haber
**Tanım:** PostgreSQL NOTIFY mekanizması ile client'lara event bildirimi. Session başlangıcında diğer process'leri alert etmek için kullanılabilir.

---

## O

### ORM (Object-Relational Mapping)
**Türkçe:** Nesne-İlişkisel Eşleme
**Tanım:** Database table'larını Python sınıflarına eşleyen library. SQLAlchemy ORM, `models.py`'de define edilir.
**Örnek:** `class User(Base): username: str, email: str` → `users` table
**Bağlantılı:** SQLAlchemy, Models, Database

---

## P

### PAP (Password Authentication Protocol)
**Türkçe:** Şifre Tabanlı Doğrulama Protokolü
**İngilizce:** Password Authentication Protocol
**Tanım:** RADIUS protokolünün ilk ve en yaygın auth methodu. Username ve password gönderilip, server doğrula sonucunda Accept/Reject döner.
**Akış:** Network Client → RADIUS Request (username, password) → FreeRADIUS → API (`/auth`) → Accept/Reject
**Bağlantılı:** RADIUS, MAB, Authentication, CHAP

### Pydantic
**Türkçe:** Pydantic
**Tanım:** Python data validation library. Request/response schemas define etmek için kullanılır. Type hints ile validation otomatik.
**Örnek:** `class AuthRequest(BaseModel): username: str, password: str`
**Bağlantılı:** FastAPI, Schema, Validation, Python

### PostgreSQL
**Türkçe:** PostgreSQL
**Tanım:** Open-source relational database. Bu projede persistent data storage'ı sağlar.
**Bağlantılı:** Database, SQL, Tables, Relational

---

## Q

### Query (Sorgu)
**Türkçe:** Sorgu, Veritabanı Sorgusu
**Tanım:** Database'den veri almak için yazılan SQL statement. SQLAlchemy ORM queries yazar.
**Örnek:** `SELECT * FROM users WHERE username = 'john'`
**Bağlantılı:** SQL, Database, ORM

---

## R

### RADIUS (Remote Authentication Dial-In User Service)
**Türkçe:** Uzak Kimlik Doğrulama Telefon Erişim Hizmeti
**İngilizce:** Remote Authentication Dial-In User Service
**Tanım:** Network erişim kimlik doğrulaması için standart protokol. UDP port 1812 (auth), 1813 (accounting), 18120 (CoA). FreeRADIUS bu protokolü implement eder.
**Mesaj Türleri:** Access-Request, Access-Accept, Access-Reject, Accounting-Request, Accounting-Response
**Bağlantılı:** FreeRADIUS, PAP, MAB, Network, Authentication

### Redis
**Türkçe:** Redis
**Tanım:** In-memory key-value cache server. Bu projede session cache ve permission caching'i sağlar.
**Bağlantılı:** Cache, Key-Value Store, Performance

### Relational Database (İlişkisel Veritabanı)
**Türkçe:** İlişkisel Veritabanı
**Tanım:** Tablo'lar ve ilişkiler (foreign keys) ile verisi organize eden database türü. PostgreSQL relational database'dir.
**Bağlantılı:** PostgreSQL, Table, Relationship, SQL

### REST (Representational State Transfer)
**Türkçe:** Temsili Durum Transferi
**Tanım:** Web API'leri HTTP metodu (GET, POST, PUT, DELETE) ve URL path'leri ile organize eden architectural style. FastAPI REST API'sini implement eder.
**Örnek:** `POST /auth`, `GET /users`
**Bağlantılı:** API, HTTP, Endpoint, FastAPI

### rlm_rest (FreeRADIUS REST Module)
**Türkçe:** rlm_rest (FreeRADIUS REST Modülü)
**Tanım:** FreeRADIUS modülü, RADIUS request'lerini HTTP REST call'ı olarak external API'ye gönderiyor. Bu projede FreeRADIUS → API endpoint'leri çağırır.
**Örnek:** RADIUS Access-Request → `POST http://api:8000/auth`
**Bağlantılı:** FreeRADIUS, REST, API, Integration

### Role (Rol)
**Türkçe:** Rol, Yetki Rolü
**Tanım:** Kullanıcıya atanan yetki seti. Admin, User, Guest gibi roller tanımlanabilir.
**Notlar:** Şu anda bu projede groups ile implement edilebilir.
**Bağlantılı:** User, Permission, Group, Authorization

---

## S

### Schema (Şema)
**Türkçe:** Şema, Veritabanı Şeması
**Tanım:** Database table'ları, column'lar, relationship'lerin tanımı. Pydantic de request/response schema'sı.
**Örnek:** PostgreSQL schema 6 table'ı define eder; Pydantic AuthRequest schema username + password define eder.
**Bağlantılı:** Database, Table, ORM, Pydantic

### Secret (Gizli, Şifre)
**Türkçe:** Gizli, Şifre
**Tanım:** Sensitive veri (password, API key, private key). Şu anda `.env` dosyasında saklanmış; production'da secret manager (Vault, AWS Secrets) gerekir.
**Örnek:** `RADIUS_SECRET`, `DATABASE_PASSWORD`
**Bağlantılı:** Security, .env, Secret Manager

### Service (Servis)
**Türkçe:** Servis
**Tanım:** Docker Compose'ta tanımlanan bir container instance. `docker-compose.yml`'de 5 service tanımlanmıştır: `api`, `postgres`, `redis`, `freeradius`, `pgadmin`.
**Bağlantılı:** Docker Compose, Container, Orchestration

### Session (Oturum)
**Türkçe:** Oturum
**Tanım:** Kullanıcının ağ bağlantısı süresi. Ağa giriş (Access-Accept) ile başlar, logout/timeout ile biter. Accounting record tutulur.
**Örnek:** User John 09:00'de ağa girerse (session başlangıcı), 17:30'da çıkarsa (session bitişi), 8.5 saat accounting record tutulur.
**Bağlantılı:** Accounting, RADIUS, User

### SQL (Structured Query Language)
**Türkçe:** Yapılandırılmış Sorgu Dili
**Tanım:** Relational database'den veri almak, güncellemek, silmek için kullanılan dil. PostgreSQL SQL dialect'i destekler.
**Örnek:** `SELECT * FROM users WHERE active = true;`
**Bağlantılı:** Database, PostgreSQL, Query

### SQLAlchemy
**Türkçe:** SQLAlchemy
**Tanım:** Python ORM library. Database işlemleri Python class'ları ile yapılır. `models.py`'de SQLAlchemy ORM define edilir.
**Bağlantılı:** ORM, Python, Database, PostgreSQL

### SSL/TLS (Secure Sockets Layer / Transport Layer Security)
**Türkçe:** Güvenli Soket Katmanı / Taşıma Katmanı Güvenliği
**Tanım:** Network'te şifreli iletişim protokolü. HTTPS = HTTP + TLS.
**Notlar:** Production'da API endpoint'leri TLS ile sunulmalı. FreeRADIUS ile mTLS önerilir.
**Bağlantılı:** HTTPS, Security, DTLS

### Swagger (API Documentation)
**Türkçe:** Swagger
**Tanım:** API dokümantasyon standard'ı. FastAPI otomatik Swagger UI oluşturur. `http://localhost:8000/docs`'da interactive API documentation bulunabilir.
**Bağlantılı:** FastAPI, OpenAPI, Documentation

---

## T

### Table (Tablo)
**Türkçe:** Tablo, Veritabanı Tablosu
**Tanım:** Database'de satırlar ve sütunlar'dan oluşan data structure. Çeşitli relationship'leri vardır.
**Bu Projede Tablolar:**
- `users` — Kullanıcı bilgileri
- `groups` — Kullanıcı grupları
- `sessions` — Aktif/bitmiş oturumlar
- `devices` — Ağ cihazları (MAC address, VLAN)
- `vlans` — VLAN tanımları
- `rules` — Authorization kuralları

**Bağlantılı:** Database, Schema, Row, Column

### Test (Test, Sınama)
**Türkçe:** Test, Sınama
**Tanım:** Uygulamanın doğru çalışıp çalışmadığını verify etme. Unit test, integration test, e2e test.
**Notlar:** Şu anda test script'leri yoktur; CI/CD pipeline'ında önerilir.

### Timeout (Zaman Aşımı)
**Türkçe:** Zaman Aşımı
**Tanım:** İşlemin belirli süre içinde tamamlanması gerektiği kuralı. Aşıldığında işlem iptal edilir.
**Örnek:** Database query timeout, API request timeout, session timeout
**Bağlantılı:** Performance, Reliability, Configuration

### Transaction (İşlem)
**Türkçe:** İşlem, Database İşlemi
**Tanım:** Database'de bir dizi operation'ın atomik (hep birlikte) tamamlanması veya geri alınması. ACID properties.
**Örnek:** User create ve session create'ü bir transaction'da yapılırsa, user fail ederse session de fail eder.
**Bağlantılı:** Database, ACID, Atomicity

---

## U

### UDP (User Datagram Protocol)
**Türkçe:** Kullanıcı Datagram Protokolü
**Tanım:** Hızlı ama unreliable transport layer protokolü. RADIUS UDP üzerinde çalışır (TCP alternatifi var ama yaygın değildir).
**Bağlantılı:** RADIUS, Network, Protocol

### User (Kullanıcı)
**Türkçe:** Kullanıcı
**Tanım:** Ağa erişim talep eden kişi veya cihaz. `users` table'ında saklanır. Username, email, active status, group membership.
**Örnek:** john@company.com, MAC: AA:BB:CC:DD:EE:FF
**Bağlantılı:** Authentication, Group, Session, Role

---

## V

### Vault (Secret Vault)
**Türkçe:** Vault, Secret Vault
**Tanım:** Sensitive data (password, API key, cert) merkezi depolayan ve credential rotation sağlayan tool. HashiCorp Vault örneği.
**Notlar:** Şu anda kullanılmamış; production security enhancement önerilir.

### VLAN (Virtual Local Area Network)
**Türkçe:** Sanal Yerel Alan Ağı
**Tanım:** Fiziksel ağı logical ağlara bölme. NAC sisteminde farklı kullanıcı gruplarına farklı VLAN'lar atanabilir.
**Örnek:** Yönetim Grubu → VLAN 10, IT Destek → VLAN 20, Konuk → VLAN 99
**Bağlantılı:** Network, NAC, Access Control

### Volume (Depolama Alanı)
**Türkçe:** Hacim, Depolama Alanı
**Tanım:** Docker'da container dışındaki persistent storage. Host filesystem veya named volume ile bağlanır.
**Örnek:** PostgreSQL data `/var/lib/postgresql/data` volume'ü ile host'ta persist edilir.
**Bağlantılı:** Docker, Container, Persistence, Storage

---

## W

### Webhook
**Türkçe:** Webhook, Web Kancası
**Tanım:** External sistem'den bir event meydana geldiğinde HTTP callback gönderme. API event logging'inde kullanılabilir.
**Notlar:** Şu anda uygulanmamış ama event-driven logging için candidate.

---

## X

### X.509 Certificate
**Türkçe:** X.509 Sertifikası
**Tanım:** Kimlik doğrulama ve şifreleme için kullanılan dijital sertifika. TLS, mTLS, ve code signing'de kullanılır.
**Notlar:** Production'da API ve RADIUS arasında certificate-based authentication önerilir.

---

## Y

### YAML (YAML Ain't Markup Language)
**Türkçe:** YAML
**Tanım:** Human-readable veri serialization format. `docker-compose.yml` YAML formatındadır.
**Örnek:**
```yaml
services:
  api:
    image: api:1.0
    ports:
      - "8000:8000"
```
**Bağlantılı:** Docker Compose, Configuration, Format

---

## Z

### Zero-downtime Deployment (Sıfır Kesinti Dağıtımı)
**Türkçe:** Sıfır Kesinti Dağıtımı
**Tanım:** Eski version'dan yeni version'a geçiş yapılırken hiç traffic kaybı olmaz. Blue-green deployment, rolling deployment gibi teknikler kullanılır.
**Notlar:** Şu anda docker-compose'ta tek instance; production'da önemlidir.

---

## İlave Teknik Terimler

### CI/CD (Continuous Integration / Continuous Deployment)
**Türkçe:** Sürekli Entegrasyon / Sürekli Dağıtım
**Tanım:** Kod değişiklikleri otomatik test ve deploy edilir. GitHub Actions, GitLab CI, Jenkins örnekleridir.
**Notlar:** Bu projede CI/CD setup'ı yoktur; production'da önerilir.

### ELK (Elasticsearch, Logstash, Kibana)
**Türkçe:** ELK Stack
**Tanım:** Centralized logging solution. Application logs'ları Elasticsearch'te index'lenir, Kibana'da visualize edilir.
**Notlar:** Şu anda logging stdout'a; production'da ELK önerilir.

### Failover (Yedek Geçiş)
**Türkçe:** Yedek Geçiş, Otomatik Failover
**Tanım:** Primary sistem fail olduğunda otomatik backup sistem'e geçme. High availability için essential.
**Notlar:** Şu anda single instance; production'da multiple instance + load balancer + health monitoring gerekir.

### Idempotency (İdempotentlik)
**Türkçe:** İdempotentlik
**Tanım:** Aynı işlemin birden fazla kez çalıştırılması aynı sonucu verir. API design'ında önemlidir.
**Örnek:** `POST /accounting` idempotent olmalı; duplicate message'lar duplicate session record'ı oluşturmamalı.

### Latency (Gecikme)
**Türkçe:** Gecikme, Latency
**Tanım:** Request'ten response'a gelen süre. Network latency, database latency, etc.
**Notlar:** RADIUS authentication'da düşük latency önemlidir (< 100ms ideal).

### Rate Limiting (Oran Sınırlama)
**Türkçe:** Oran Sınırlama, Hız Sınırlama
**Tanım:** Belirli süre içinde maksimum request sayısı atası. DDoS koruması ve API abuse prevention.
**Notlar:** Şu anda uygulanmamış; production'da `/auth` ve `/authorize` endpoint'lerine önerilir.

### Rollback (Geri Alma)
**Türkçe:** Geri Alma, Rollback
**Tanım:** Deployment başarısız olduğunda önceki version'a dönme. Database migration rollback, container image downgrade.
**Notlar:** Production'da rollback strategy'si tanımlanmalı.

### SLA (Service Level Agreement)
**Türkçe:** Hizmet Düzeyi Anlaşması
**Tanım:** Service'in kullanılabilirliği, performance, support hakkındaki sözleşme. 99.9% uptime gibi.
**Notlar:** Production'da SLA tanımlanmalı (örn: 99.5% availability).

### Throughput (Verim, İşlem Kapasitesi)
**Türkçe:** Verim, İşlem Kapasitesi
**Tanım:** Birim zamanda işlenen request/transaction sayısı. Performance metric'i.
**Örnek:** "API 100 request/second throughput'u sağlayabiliyor"

---

**Son Güncelleme:** 2026-03-23
**Toplam Terim:** 100+
**Dil:** Türkçe Birincil, İngilizce İkincil
