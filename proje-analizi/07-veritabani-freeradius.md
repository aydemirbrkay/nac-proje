# NAC Sistemi: Veritabanı ve FreeRADIUS Yapılandırması

## İçindekiler

- [Part 1: Veritabanı Şeması (init.sql)](#part-1-veritabanı-şeması-initsql)
- [Part 2: FreeRADIUS Yapılandırması](#part-2-freeradius-yapılandırması)
- [Entegrasyon Mimarisi](#entegrasyon-mimarisi)
- [Güvenlik ve Production Notları](#güvenlik-ve-production-notları)

---

# Part 1: Veritabanı Şeması (init.sql)

## Genel Amaç ve Mimarisi

NAC (Network Access Control) sistemi, FreeRADIUS ile tamamen uyumlu bir veritabanı şeması kullanır. Şema iki ana bölümden oluşur:

1. **FreeRADIUS Standart Tabloları**: RADIUS protokolüne göre tanımlanmış kimlik doğrulama, kimlik doğrulama sonrası, grup ve muhasebe tabloları
2. **NAC-Spesifik Tablolar**: MAC-Based Authentication (MAB) için kayıtlı cihazlar tablosu

Bu yapı sayesinde:
- 802.1X (Supplicant-based) authentication → `radcheck`, `radusergroup`, `radgroupreply` tabloları
- MAC-Based Authentication (MAB) → `mac_devices` tablosu
- Oturum muhasebesi (Accounting) → `radacct` tablosu
- Dinamik VLAN atamaları → `radgroupreply` tablosu

Tüm tablolar FreeRADIUS `rlm_sql` modülü ve NAC API tarafından sorgulanır.

---

## Tablo Şemaları

### radcheck

#### Amaç

`radcheck` tablosu, FreeRADIUS'un **authorize** aşamasında sorguladığı, kullanıcıların kimlik bilgilerini (username + password) içeren tablodur. Aynı zamanda diğer kimlik doğrulama işlemleri için öznitelik depolama alanı da sağlar.

Tablo, aşağıdaki kontrol öznitelikleri depolamanın yanı sıra, FreeRADIUS'a "bu kullanıcı için şu kontrolü yap" talimatı verir:
- `op` alanı: `:=` (atama), `==` (eşitlik kontrolü), `+=` (ekleme), `!=` (eşit değil) gibi operatörler

#### Şema

| Column | Type | Amaç |
|--------|------|------|
| id | SERIAL PRIMARY KEY | Tek kimlik numarası |
| username | VARCHAR(64) NOT NULL | Kullanıcı adı (örn: admin_ali, emp_mehmet) |
| attribute | VARCHAR(64) NOT NULL | Kontrol özniteliği adı (örn: Cleartext-Password, User-Profile) |
| op | CHAR(2) DEFAULT ':=' | Operatör: `:=` (atama), `==` (kontrol), `+=` (ekleme), `!=` (eşit değil) |
| value | VARCHAR(253) NOT NULL | Öznitelik değeri (örn: şifre, NULL, profil adı) |
| **Indexler** | | |
| idx_radcheck_username | Composite | username bazlı hızlı sorgu |

#### Kullanımı

- **FreeRADIUS authorize aşaması**: `SELECT * FROM radcheck WHERE username = %s`
- **NAC API**: Veritabanında kayıtlı kullanıcıları sorgulamak için
- **rlm_sql modülü**: Standart SQL-based authentication

#### Örnek Veriler

```sql
| id | username    | attribute           | op  | value        |
|----|-------------|---------------------|-----|--------------|
| 1  | admin_ali   | Cleartext-Password  | :=  | Admin1234!   |
| 2  | emp_mehmet  | Cleartext-Password  | :=  | Emp1234!     |
| 3  | emp_ayse    | Cleartext-Password  | :=  | Emp5678!     |
| 4  | guest_user  | Cleartext-Password  | :=  | Guest1234!   |
```

#### Notlar

- **Şifre Depolama**: Örnek veriler plaintext içerir (Cleartext-Password). Production ortamında:
  - Şifreler bcrypt/scrypt ile hashlenmelidir
  - `User-Password` yerine `Cleartext-Password` kullanılması debug amaçlıdır
  - API'nin `/seed` endpoint'i hash oluşturabilir
- **Op Operatörü**: Farklı senaryolar için:
  - `:=` (assign) - değeri belirle
  - `==` (check) - kontrol et
  - `+=` (add) - ekle
  - `!=` (not equal) - eşit değil kontrolü

---

### radreply

#### Amaç

`radreply` tablosu, **kullanıcıya-spesifik** RADIUS yanıt atribütlerini depolamak için kullanılır. Kimlik doğrulaması başarılı olduğunda, FreeRADIUS bu tablodaki atribütleri Access-Accept paketine ekler.

Gruptan ziyade bireysel kullanıcıya özel öznitelikler burada tanımlanır:
- Kullanıcı-spesifik VLAN atlaması
- Kullanıcıya özel timeout değerleri
- Kullanıcı-bazlı QoS parametreleri

#### Şema

| Column | Type | Amaç |
|--------|------|------|
| id | SERIAL PRIMARY KEY | Tek kimlik numarası |
| username | VARCHAR(64) NOT NULL | Kullanıcı adı |
| attribute | VARCHAR(64) NOT NULL | Yanıt özniteliği (örn: Tunnel-Private-Group-Id, Session-Timeout) |
| op | CHAR(2) DEFAULT ':=' | Operatör |
| value | VARCHAR(253) NOT NULL | Öznitelik değeri |
| **Indexler** | | |
| idx_radreply_username | Composite | username bazlı hızlı sorgu |

#### Kullanımı

- **FreeRADIUS post-auth aşaması**: `SELECT * FROM radreply WHERE username = %s`
- **Kullanıcı-spesifik politikalar**: Gruptan farklı özel kurallar
- Örnek: Belirli bir employee'nin farklı VLAN'a bağlanması

#### Örnek Veriler

Mevcut NAC sisteminde bu tablo boş olabilir (grup-bazlı atamalar tercih edilir), ancak şu şekilde kullanılabilir:

```sql
| id | username   | attribute                | op  | value  |
|----|------------|--------------------------|----|--------|
| 1  | admin_ali  | Session-Timeout          | :=  | 28800  |
| 2  | emp_mehmet | Tunnel-Private-Group-Id  | :=  | 20     |
```

#### Notlar

- **Grup vs Kullanıcı**: Eğer hem `radreply` hem `radgroupreply`'de aynı atribüt varsa, kullanıcı-spesifik değer öncelik alır
- **Priority**: `radusergroup.priority` bazlı sıralama yapılır

---

### radusergroup

#### Amaç

`radusergroup` tablosu, kullanıcılar ile gruplar arasındaki bağlantıyı tanımlar. Bir kullanıcı birden fazla gruba üyeliği olabilir, her grup farklı polítikaları (VLAN'ları) tanımlar.

`priority` alanı, bir kullanıcının birden fazla gruba üye olması durumunda hangi grubun öncelikli olacağını belirler (düşük sayı = yüksek öncelik).

#### Şema

| Column | Type | Amaç |
|--------|------|------|
| id | SERIAL PRIMARY KEY | Tek kimlik numarası |
| username | VARCHAR(64) NOT NULL | Kullanıcı adı |
| groupname | VARCHAR(64) NOT NULL | Grup adı |
| priority | INTEGER DEFAULT 1 | Öncelik (düşük değer = yüksek öncelik) |
| **Indexler** | | |
| idx_radusergroup_username | Composite | username bazlı sorgu |

#### Kullanımı

- **FreeRADIUS authorize aşaması**: `SELECT * FROM radusergroup WHERE username = %s ORDER BY priority`
- **NAC API**: Kullanıcı-grup ilişkilerini yönetmek için
- **Çok-grup senaryoları**: Bir kullanıcı hem 'employee' hem 'vpn_users' grubunda olabilir

#### Örnek Veriler

```sql
| id | username    | groupname       | priority |
|----|-------------|-----------------|----------|
| 1  | admin_ali   | admin           | 1        |
| 2  | emp_mehmet  | employee        | 1        |
| 3  | emp_ayse    | employee        | 1        |
| 4  | guest_user  | guest           | 1        |
| 5  | emp_mehmet  | vpn_users       | 2        |
```

#### Notlar

- **Çok-Grup Desteği**: Bir kullanıcının birden fazla gruba üye olması, farklı policy'ler uygulanmasını sağlar
- **Priority Sıralaması**: Priority küçükten büyüğe doğru işlenir (1 = en yüksek)
- **Olmayan Gruplar**: Eğer tanımlı olmayan bir gruba eklenmişse, `radgroupreply`'de tanımı olması gerekir

---

### radgroupreply

#### Amaç

`radgroupreply` tablosu, **grup-bazlı** RADIUS yanıt atribütlerini depolamak için kullanılır. NAC sistemi içinde en önemli tablodur çünkü VLAN ve policy atlamalarını bu tablo tanımlar.

Bir kullanıcı bir gruba üye olduğunda, FreeRADIUS otomatik olarak bu grubun tüm atribütlerini Access-Accept paketine ekler.

#### Şema

| Column | Type | Amaç |
|--------|------|------|
| id | SERIAL PRIMARY KEY | Tek kimlik numarası |
| groupname | VARCHAR(64) NOT NULL | Grup adı |
| attribute | VARCHAR(64) NOT NULL | Grup özniteliği (örn: Tunnel-Type, Tunnel-Medium-Type) |
| op | CHAR(2) DEFAULT ':=' | Operatör |
| value | VARCHAR(253) NOT NULL | Öznitelik değeri |
| **Indexler** | | |
| idx_radgroupreply_groupname | Composite | groupname bazlı sorgu |

#### Kullanımı

- **FreeRADIUS post-auth aşaması**: `SELECT * FROM radgroupreply WHERE groupname IN (user's groups)`
- **VLAN Ataması**: Tunnel-Type, Tunnel-Medium-Type, Tunnel-Private-Group-Id
- **Ağ Politikaları**: Filter-Id (ACL referansı)

#### Örnek Veriler (4 Grup, 4 VLAN)

```sql
-- Admin grubu → VLAN 10
| id | groupname | attribute                | op  | value      |
|----|-----------|--------------------------|-----|------------|
| 1  | admin     | Tunnel-Type              | :=  | 13         |
| 2  | admin     | Tunnel-Medium-Type       | :=  | 6          |
| 3  | admin     | Tunnel-Private-Group-Id  | :=  | 10         |
| 4  | admin     | Filter-Id                | :=  | admin-acl  |

-- Employee grubu → VLAN 20
| 5  | employee  | Tunnel-Type              | :=  | 13         |
| 6  | employee  | Tunnel-Medium-Type       | :=  | 6          |
| 7  | employee  | Tunnel-Private-Group-Id  | :=  | 20         |
| 8  | employee  | Filter-Id                | :=  | employee-acl|

-- Guest grubu → VLAN 30
| 9  | guest     | Tunnel-Type              | :=  | 13         |
| 10 | guest     | Tunnel-Medium-Type       | :=  | 6          |
| 11 | guest     | Tunnel-Private-Group-Id  | :=  | 30         |
| 12 | guest     | Filter-Id                | :=  | guest-acl  |

-- IoT Devices grubu → VLAN 40
| 13 | iot_devices | Tunnel-Type            | :=  | 13         |
| 14 | iot_devices | Tunnel-Medium-Type     | :=  | 6          |
| 15 | iot_devices | Tunnel-Private-Group-Id| :=  | 40         |
| 16 | iot_devices | Filter-Id              | :=  | iot-acl    |
```

#### RADIUS Atribütleri Açıklaması

- **Tunnel-Type (13)**: VLAN tüneli
- **Tunnel-Medium-Type (6)**: IEEE 802 (Ethernet/VLAN)
- **Tunnel-Private-Group-Id**: VLAN ID (10-40)
- **Filter-Id**: Ağ ACL referansı (switch tarafında tanımlı kurallar)

#### Notlar

- **VLAN Ataması Mekanizması**: Switch/AP, RADIUS Access-Accept paketinde bu atribütleri gördüğünde, kullanıcıyı belirtilen VLAN'a atar
- **Tag Protokolü**: IEEE 802.1Q (Tagged VLAN), Tunnel-Type=13 ile aktif edilir
- **ACL Integration**: Filter-Id switch/AP'de tanımlı ACL referansına bağlanır

---

### radacct

#### Amaç

`radacct` tablosu, FreeRADIUS'un **accounting** fonksiyonunun temel veri depolandığı tablodur. Her oturum başladığında, güncellendiğinde ve bittiğinde bu tabloya kayıt yazılır.

NAC sistemi içinde kullanıcı davranışının izlenmesi, audit trail ve ağ trafiğinin ölçülmesi gibi işlevler için kritiktir.

#### Şema

| Column | Type | Amaç |
|--------|------|------|
| id | BIGSERIAL PRIMARY KEY | Benzersiz kayıt ID'si |
| acctsessionid | VARCHAR(64) NOT NULL | Oturum ID'si (NAS tarafından atanır) |
| acctuniqueid | VARCHAR(32) UNIQUE | Benzersiz oturum tanımlayıcı (start + NAS-IP + session-id) |
| username | VARCHAR(64) NOT NULL | Kimlik doğrulanan kullanıcı adı |
| nasipaddress | VARCHAR(15) NOT NULL | NAS'ın IP adresi (Access Point, Switch) |
| nasportid | VARCHAR(32) | NAS üzerindeki port ID'si (örn: eth0, interface 5) |
| acctstarttime | TIMESTAMP | Oturum başlama zamanı |
| acctupdatetime | TIMESTAMP | Son güncelleme zamanı (interim accounting) |
| acctstoptime | TIMESTAMP | Oturum bitiş zamanı |
| acctsessiontime | BIGINT DEFAULT 0 | Oturum süresi (saniye) |
| acctinputoctets | BIGINT DEFAULT 0 | Indirilen veri (byte) |
| acctoutputoctets | BIGINT DEFAULT 0 | Yüklenen veri (byte) |
| acctterminatecause | VARCHAR(32) | Oturum sona erme nedeni (User-Request, Lost-Carrier, vb.) |
| framedipaddress | VARCHAR(15) | Kullanıcıya atanan IP adresi |
| callingstation | VARCHAR(50) | MAC adresi (çağrı istasyonu) |
| acctstatustype | VARCHAR(25) | Status türü (Start, Interim-Update, Stop) |
| **Indexler** | | |
| idx_radacct_username | Composite | username bazlı sorgu |
| idx_radacct_session | Composite | acctsessionid bazlı sorgu |
| idx_radacct_start | Composite | acctstarttime bazlı sorgu (raporlar için) |

#### Kullanımı

- **FreeRADIUS accounting aşaması**: Her Accounting-Request paketinde bu tabloya INSERT/UPDATE
- **Oturum İzleme**: Aktif kullanıcıları bulmak (acctstoptime IS NULL)
- **Audit Trail**: Kimler ne zaman bağlandı/ayrıldı
- **Trafik Ölçümü**: Kullanıcı başına veri kullanımı (acctinputoctets + acctoutputoctets)
- **Raporlama**: Zaman-bazlı sorgular (acctstarttime BETWEEN ...)

#### Örnek Veriler

```sql
| id | acctsessionid | username   | nasipaddress | acctstarttime      | acctstoptime | acctsessiontime | acctinputoctets | acctoutputoctets | callingstation   |
|----|-----------|-----------|-----------|----|----|----|---|---|--|
| 1  | 01234567  | emp_mehmet  | 192.168.1.1  | 2025-03-23 09:00:00 | 2025-03-23 17:30:00 | 30600 | 1073741824 | 536870912 | AA:BB:CC:DD:EE:11 |
| 2  | 01234568  | emp_ayse    | 192.168.1.2  | 2025-03-23 09:15:00 | 2025-03-23 12:00:00 | 10260 | 536870912  | 268435456 | AA:BB:CC:DD:EE:22 |
| 3  | 01234569  | guest_user  | 192.168.1.1  | 2025-03-23 14:30:00 | NULL                | 3600  | 268435456  | 134217728 | AA:BB:CC:DD:EE:33 |
```

#### Veri Birimleri

- **acctsessiontime**: Saniye cinsinden
- **acctinputoctets / acctoutputoctets**: Bayt cinsinden
- **Zaman alanları**: PostgreSQL TIMESTAMP (UTC tercih edilir)

#### Notlar

- **Interim Accounting**: Oturum devam ederken periyodik güncellemeler (acctupdatetime değişir)
- **Stop Sonrası**: Oturum bittiğinde acctstoptime, acctterminatecause, acctsessiontime doldurulur
- **Performans**: username, acctsessionid, acctstarttime indexleri sorguları hızlandırır
- **Arşivleme**: Eski kayıtları düzenli olarak arşivlemek / silmek önerilir

---

### mac_devices

#### Amaç

`mac_devices` tablosu, **MAC-Based Authentication (MAB)** için kayıtlı cihazları depolamak için kullanılır. MAB, 802.1X desteği olmayan yazıcılar, IP telefonlar, kameralar gibi cihazların ağa erişmesini sağlar.

Cihaz, bağlantı yaptığında MAC adresi bu tabloda sorgulanır:
- Bulunursa: Atanan gruba göre VLAN taması
- Bulunmazsa: Guest VLAN'a aktarılır (veya reddedilir)

#### Şema

| Column | Type | Amaç |
|--------|------|------|
| id | SERIAL PRIMARY KEY | Cihaz ID'si |
| mac_address | VARCHAR(17) UNIQUE | MAC adresi (AA:BB:CC:DD:EE:FF formatı) |
| device_name | VARCHAR(128) | Cihazın insanlar tarafından okunur adı (örn: "Kat-1 Yazıcı") |
| device_type | VARCHAR(64) | Cihaz tipi (printer, ip_phone, camera, vb.) |
| groupname | VARCHAR(64) DEFAULT 'guest' | Atanan grup (radgroupreply'de tanımlı grup) |
| is_active | BOOLEAN DEFAULT TRUE | Cihazın aktif olup olmadığı (devre dışı = hiçbir ağ erişimi) |
| created_at | TIMESTAMP DEFAULT NOW() | Cihazın kaydolunduğu zaman |
| **Indexler** | | |
| idx_mac_devices_mac | Composite | mac_address benzersiz ve hızlı sorgu |

#### Kullanımı

- **NAC API**: Gelen MAC adresini sorgulamak
- **MAB Pipeline**: `SELECT * FROM mac_devices WHERE mac_address = %s AND is_active = true`
- **Cihaz Yönetimi**: Hangi cihazlar ağa erişebileceğini kontrol etme

#### Örnek Veriler (3 MAB Cihazı)

```sql
| id | mac_address       | device_name           | device_type | groupname    | is_active | created_at          |
|----|-------------------|------------------------|-------------|-----------|--------|----|
| 1  | AA:BB:CC:DD:EE:01 | Kat-1 Yazıcı           | printer     | iot_devices | TRUE   | 2025-03-01 10:00:00 |
| 2  | AA:BB:CC:DD:EE:02 | Resepsiyon IP Telefon | ip_phone    | employee    | TRUE   | 2025-03-02 10:00:00 |
| 3  | AA:BB:CC:DD:EE:03 | Güvenlik Kamerası     | camera      | iot_devices | TRUE   | 2025-03-03 10:00:00 |
```

#### MAB Akışı

1. Cihaz ağa bağlanır → MAC adresi açığa çıkar
2. NAS, RADIUS sunucusuna Accounting-Start gönderir (Calling-Station-Id = MAC)
3. NAC API: `SELECT * FROM mac_devices WHERE mac_address = calling_station_id`
4. Bulunursa: Cihazın `groupname` kaydedilir
5. `radgroupreply`'den grup atribütleri (VLAN, ACL) alınır
6. VLAN ataması yapılır

#### Notlar

- **MAC Formatı**: Standart AA:BB:CC:DD:EE:FF (büyük harfler tercih edilir)
- **is_active**: Cihazı geçici olarak devre dışı bırakmak için kullanılır (silme yerine)
- **Guest Fallback**: Kayıtlı olmayan MAC → 'guest' grubuna atanır (radgroupreply'de tanımlı)
- **Güvenlik**: MAC spoofing riski vardır; production'da ek doğrulama gerekebilir

---

# Part 2: FreeRADIUS Yapılandırması

## FreeRADIUS Mimarisi ve Module Sistemi

FreeRADIUS, modüler bir RADIUS sunucusudur. Temel fonksiyonu, RADIUS istek-yanıt döngüsünü yönetmektir:

```
Supplicant → NAS (Switch/AP) → FreeRADIUS → Policy Engine / Database
```

### Virtual Servers (Sites)

FreeRADIUS, istekleri işlemek için **virtual servers** (sanal sunucular) kullanır. Her virtual server, belirli bir amaç için bir istek işleme pipeline'ı tanımlar:

- **default**: Auth + accounting requests
- **inner-tunnel**: EAP (Extensible Authentication Protocol) tunnel işlemeleri
- **status**: FreeRADIUS sağlık kontrolü

NAC sistemi, **default** virtual server'ı kullanır.

### Modules (Modüller)

Her aşamada çeşitli modüller çalıştırılabilir:

- **rlm_sql**: Veritabanı sorgulaması
- **rlm_rest**: HTTP/REST API çağrıları
- **rlm_exec**: Harici programları çalıştırma
- **rlm_files**: Düz metin dosyalarından veri okuma
- **rlm_ldap**: LDAP directory sorgulaması
- **rlm_pap**: Password authentication (PAP yöntemi)
- **rlm_chap**: Challenge-Handshake Authentication Protocol
- **rlm_mschap**: Microsoft CHAP

NAC sistemi, **rlm_rest** modülünü ön plana çıkarır (FastAPI entegrasyonu).

---

## clients.conf

#### Amaç

`clients.conf` dosyası, FreeRADIUS sunucusuna bağlanma yetkisine sahip olan **NAS** (Network Access Server) cihazlarını tanımlar. Her NAS, paylaşımlı bir anahtar (secret) ile kimlik doğrulanır.

Tanımlı olmayan bir NAS'tan gelen istekler otomatik olarak reddedilir.

#### İçeriği

##### Localhost Client (Testing)

```conf
client localhost {
    ipaddr    = 127.0.0.1
    secret    = testing123
    shortname = localhost
}
```

- **ipaddr**: Localhost'un IP adresi (127.0.0.1)
- **secret**: Paylaşımlı anahtar ("testing123" — test amaçlıdır)
- **shortname**: Kısa isim (log dosyalarında gösterilir)

**Kullanımı:**
- `radtest` ve `radclient` komutları localhost'tan test istek gönderir
- Development ortamında debugging için

##### Docker Network Client (Production)

```conf
client docker_network {
    ipaddr    = 172.20.0.0/24
    secret    = testing123
    shortname = docker
}
```

- **ipaddr**: Docker Compose ağının subnet'i (172.20.0.0/24)
- **secret**: Paylaşımlı anahtar (tüm konteynerler için ortak)
- **shortname**: Docker

**Kullanımı:**
- Docker Compose ortamında, tüm konteynerler bu subnet'tedir
- AP, switch, gateway gibi NAS cihazları bu subnet üzerinde çalışır
- SUBNET tanımı (/24) tüm 172.20.0.x IP'lerini kabul eder

#### FastAPI Entegrasyonu

`clients.conf`'de FreeRADIUS sunucusunun erişim kontrolü yapılır. FastAPI (nac-api konteyneri) istekleri göndermeyen, FreeRADIUS ise API'ye HTTP istekleri atar (`rlm_rest`).

#### Production Notları

- **Secret Güvenliği**: Production'da `testing123` yerine güçlü, rastgele bir anahtar kullanılmalıdır (minimum 32 karakter)
- **IP Kısıtlaması**: Eğer belirli NAS IP'leri biliniyorsa, `/24` subnet yerine tam IP'ler tanımlanmalıdır:
  ```conf
  client switch_main {
      ipaddr = 192.168.1.10
      secret = your_secret_key_here
  }
  ```
- **Multi-NAS**: Farklı NAS'lar için ayrı client blokları oluşturulabilir
- **Shared Secret Rotation**: Production'da periyodik olarak değiştirilmelidir

---

## mods-enabled/rest

#### Amaç

`mods-enabled/rest` dosyası, **rlm_rest** modülünün konfigürasyonudur. Bu modül, FreeRADIUS'u HTTP REST client'a dönüştürür.

NAC sistemi tamamen REST API uygulaması için tasarlandığından, tüm kimlik doğrulama ve yetkilendirme işlemleri FastAPI policy engine'e delegeli hale getirilebilir.

**Akış:**
```
Supplicant → NAS → FreeRADIUS (rlm_rest) → FastAPI API (nac-api) → Database
```

#### İçeriği

##### Genel Ayarlar

```conf
rest {
    connect_uri = "http://nac-api:8000"
    connect_timeout = 5.0
    timeout = 10.0
```

- **connect_uri**: FastAPI API'sinin temel adresi
  - `nac-api`: Docker Compose DNS çözümlemesi (service adı)
  - `8000`: FastAPI default portu
- **connect_timeout**: TCP bağlantı timeout'ı (5 saniye)
- **timeout**: HTTP istek-yanıt timeout'ı (10 saniye)

##### Authorize Bloğu

```conf
authorize {
    uri  = "${..connect_uri}/auth"
    method = "post"
    body = "json"
    data = "{\"username\":\"%{User-Name}\",\"password\":\"%{User-Password}\",\"calling_station_id\":\"%{Calling-Station-Id}\"}"
    force_to = "plain"
}
```

**Parametreler:**
- **uri**: `/auth` endpoint'ine POST isteği
- **method**: HTTP POST
- **body**: JSON body
- **data**: Gönderilecek JSON payload
  - `%{User-Name}`: RADIUS isteğinden kullanıcı adı
  - `%{User-Password}`: RADIUS isteğinden şifre
  - `%{Calling-Station-Id}`: MAC adresi (MAB için)
- **force_to**: Yanıtı plain text olarak işle

**Yanıt Kodu Anlamları:**
- **HTTP 200**: Kimlik doğrulama başarılı → Accept
- **HTTP 401**: Kimlik doğrulama başarısız → Reject
- **Diğer kodlar**: Hata, istemi iptal

**FastAPI /auth Endpoint'i Beklediği:**
```json
{
    "username": "emp_mehmet",
    "password": "Emp1234!",
    "calling_station_id": "AA:BB:CC:DD:EE:11"
}
```

**Yanıtı:**
```json
{
    "success": true,
    "message": "Authentication successful",
    "group": "employee"
}
```

##### Post-Auth Bloğu

```conf
post-auth {
    uri  = "${..connect_uri}/authorize"
    method = "post"
    body = "json"
    data = "{\"username\":\"%{User-Name}\",\"calling_station_id\":\"%{Calling-Station-Id}\"}"
    force_to = "plain"
}
```

**Kullanımı:**
- Kimlik doğrulama başarılı olduktan sonra VLAN ve policy atlaması için
- `/authorize` endpoint'ine POST isteği

**FastAPI /authorize Endpoint'i Beklediği:**
```json
{
    "username": "emp_mehmet",
    "calling_station_id": "AA:BB:CC:DD:EE:11"
}
```

**Yanıtı (örnek):**
```json
{
    "vlan_id": 20,
    "filter_id": "employee-acl",
    "group": "employee"
}
```

##### Accounting Bloğu

```conf
accounting {
    uri  = "${..connect_uri}/accounting"
    method = "post"
    body = "json"
    data = "{\"username\":\"%{User-Name}\",\"acct_status_type\":\"%{Acct-Status-Type}\",\"acct_session_id\":\"%{Acct-Session-Id}\",\"acct_unique_session_id\":\"%{Acct-Unique-Session-Id}\",\"nas_ip_address\":\"%{NAS-IP-Address}\",\"nas_port_id\":\"%{NAS-Port-Id}\",\"acct_session_time\":\"%{Acct-Session-Time}\",\"acct_input_octets\":\"%{Acct-Input-Octets}\",\"acct_output_octets\":\"%{Acct-Output-Octets}\",\"acct_terminate_cause\":\"%{Acct-Terminate-Cause}\",\"framed_ip_address\":\"%{Framed-IP-Address}\",\"calling_station_id\":\"%{Calling-Station-Id}\"}"
    force_to = "plain"
}
```

**Kullanımı:**
- Oturum başlangıç (Acct-Status-Type = Start)
- Periyodik güncellemeler (Interim-Update)
- Oturum sonu (Stop)

**FastAPI /accounting Endpoint'i Beklediği:**
```json
{
    "username": "emp_mehmet",
    "acct_status_type": "Start",
    "acct_session_id": "01234567",
    "nas_ip_address": "192.168.1.1",
    "acct_session_time": 0,
    "acct_input_octets": 0,
    "acct_output_octets": 0,
    "calling_station_id": "AA:BB:CC:DD:EE:11"
}
```

##### Connection Pool

```conf
pool {
    start = 5
    min = 3
    max = 20
    spare = 5
    uses = 0
    lifetime = 0
    idle_timeout = 60
}
```

- **start**: Başlangıçta açılacak bağlantı sayısı (5)
- **min**: Minimum bağlantı sayısı (3)
- **max**: Maximum bağlantı sayısı (20)
- **spare**: Yeni istekler için hazırda beklemesi gereken bağlantı sayısı (5)
- **idle_timeout**: Boş bağlantının kapatılmadan önce bekleyeceği süre (60 saniye)

**Amaç**: REST API'ye yapılan HTTP isteklerini havuzlamak, bağlantı açma/kapama overhead'ini azaltmak

#### FastAPI Entegrasyonu

NAC API'sinin `/auth`, `/authorize`, `/accounting` endpoint'leri bu çağrıları işler:

```python
# FastAPI içinde (pseudocode):
@app.post("/auth")
async def authenticate(req: AuthRequest):
    # radcheck tablosundan kullanıcıyı sor
    # Şifreyi doğrula
    # HTTP 200 veya 401 döndür

@app.post("/authorize")
async def authorize(req: AuthorizeRequest):
    # radusergroup ve radgroupreply'den VLAN bilgisi al
    # Filter-Id ata
    # Yanıt döndür

@app.post("/accounting")
async def accounting(req: AccountingRequest):
    # radacct tablosuna INSERT/UPDATE yap
    # Oturum süresini hesapla
    # Trafik kayıtlarını tut
```

#### Production Notları

- **Timeout Ayarları**:
  - Development: 10 saniye makul
  - Production: 5-10 saniye arasında ayarlanmalıdır (sağlık kontrolleri eklenmelidir)
- **FastAPI Health Check**: API'nin sağlık durumunu monitoring etmek gerekir
- **Connection Pool Size**: Beklenen eşzamanlı istek sayısına göre ayarlanmalıdır
- **Error Handling**: API down olursa FreeRADIUS fallback mekanizması olması gerekir
- **Logging**: Tüm REST çağrıları log edilmelidir (debug ve audit için)
- **TLS/SSL**: Production'da `https://` kullanılmalıdır (şu anda `http://`)

---

## sites-enabled/default

#### Amaç

`sites-enabled/default` dosyası, FreeRADIUS'un **default virtual server**'ının konfigürasyonudur. Bu virtual server, tüm auth ve accounting isteklerini işleyen ana pipeline'ı tanımlar.

Pipeline dört aşamadan oluşur:
1. **authorize** - kimlik doğrulama
2. **authenticate** - ek kimlik doğrulama (boş, REST'te yapıldı)
3. **post-auth** - başarılı auth sonrası (VLAN atlaması)
4. **accounting** - oturum kayıtları

#### İçeriği

##### Listen Blokları

```conf
server default {
    listen {
        type = auth
        ipaddr = *
        port = 1812
    }

    listen {
        type = acct
        ipaddr = *
        port = 1813
    }
}
```

- **port 1812**: RADIUS authentication istekleri (Access-Request)
- **port 1813**: RADIUS accounting istekleri (Accounting-Request)
- **ipaddr = ***: Tüm IP adreslerini dinle

##### Authorize Aşaması

```conf
authorize {
    filter_username
    rest
    update control {
        Auth-Type := Accept
    }
}
```

**Adımlar:**

1. **filter_username**: Gelen User-Name'i temizle/normalize et
   - Büyük harfleri küçültme
   - Whitespace'leri kaldırma
   - Geçersiz karakterleri filtre etme

2. **rest**: FastAPI `/auth` endpoint'ine POST isteği gönder
   - Username, password, MAC gönder
   - HTTP 200 = başarılı
   - HTTP 401 = başarısız (otomatik reject)

3. **update control { Auth-Type := Accept }**:
   - Auth-Type'ı "Accept" olarak ayarla
   - Bu, authenticate aşamasını atlatmak için kullanılır
   - REST'te auth yapıldı, ek adım gerekli değil

**Akış Diyagramı:**
```
Auth Request → filter_username → rest (/auth) →
  ├─ HTTP 200 → Auth-Type := Accept → post-auth'a git
  └─ HTTP 401 → Access-Reject → sonlandır
```

##### Authenticate Aşaması

```conf
authenticate {
    # Boş - rest authorization'da halledildi
}
```

Boş bırakılmış çünkü tüm kimlik doğrulama REST API'de yapılmaktadır.

**Neden?**
- Traditional RADIUS: radcheck tablosundan şifre al, rlm_pap modülü ile karşılaştır
- REST-based NAC: FastAPI'de tüm kimlik doğrulama mantığı var

##### Post-Auth Aşaması

```conf
post-auth {
    rest
    Post-Auth-Type REJECT {
        rest
    }
}
```

**İki durum:**

1. **Başarılı Auth** (HTTP 200):
   - `rest` modülü `/authorize` endpoint'ine çağrı yapar
   - VLAN, Filter-Id bilgisi döner
   - Access-Accept paketine bu atribütler eklenir

2. **Başarısız Auth** (HTTP 401):
   - `Post-Auth-Type REJECT` bloğu çalışır
   - `rest` modülü tekrar çağrılabilir (opsiyonel)
   - Access-Reject paketine ek bilgiler eklenir

**Akış:**
```
authorize başarılı ↓
post-auth {
    rest → /authorize → VLAN ataması
} ↓
Access-Accept + VLAN atribütleri
```

##### Accounting Aşaması

```conf
accounting {
    rest
}
```

- Tüm accounting paketleri (Start, Interim-Update, Stop) FastAPI `/accounting` endpoint'ine gönderilir
- API, `radacct` tablosuna INSERT/UPDATE yapar
- Session tracking ve data usage reporting

**Paket Türleri:**
- **Start**: Oturum başladı → INSERT radacct
- **Interim-Update**: Oturum devam ediyor → UPDATE radacct (trafik, süre)
- **Stop**: Oturum bitti → UPDATE radacct (final stats)

---

## Module Execution Order (Modül Çalışma Sırası)

FreeRADIUS, authorization → authenticate → post-auth → accounting sırasında modülleri belirli bir sırayla çalıştırır.

### NAC Sistemi Akışı

```
1. RADIUS Request geldi (Access-Request)
   ↓
2. authorize aşaması:
   ├─ filter_username → username temizle
   ├─ rest → FastAPI /auth çağrı
   │   ├─ HTTP 200: Auth başarılı
   │   │  └─ update control { Auth-Type := Accept }
   │   └─ HTTP 401: Auth başarısız → Reject
   ↓
3. authenticate aşaması: (boş)
   ↓
4. post-auth aşaması:
   ├─ Auth başarılı ise:
   │  └─ rest → FastAPI /authorize çağrı (VLAN atlaması)
   └─ Auth başarısız ise:
      └─ Post-Auth-Type REJECT { rest }
   ↓
5. Access-Accept/Reject paketini gönder
   ↓
6. Accounting Request gelirse:
   ├─ accounting aşaması:
   │  └─ rest → FastAPI /accounting çağrı
   │     └─ radacct tablosuna INSERT/UPDATE
   ↓
7. İşlem tamamlandı
```

### Modül Return Kodları

Her modül şu kodlardan birini döndürür:

| Kod | Anlamı | Sonuç |
|-----|--------|-------|
| ok | İşlem başarılı, devam et | Sonraki modüle git |
| notfound | Kural bulunamadı | Devam et (kritik değil) |
| noop | Hiçbir şey yapılmadı | Devam et |
| invalid | Geçersiz istek | Devam et (kural bağlıdır) |
| fail | Hata oluştu | Reject (kritik hata) |
| reject | Kimlik doğrulama başarısız | Access-Reject döndür |

---

## Debug Mode (-X Flag)

FreeRADIUS, detaylı log çıkışı için **debug mode**'da çalıştırılabilir:

```bash
# FreeRADIUS debug mode'da başlat
radiusd -X
```

**Output:**
```
Ready to process requests.

rad_receive: Request on authentication socket from client 127.0.0.1:54321 to 127.0.0.1:1812
    Access-Request Id 123 from 0x7fffffff0000 to 0x0
        User-Name = "emp_mehmet"
        User-Password = "Emp1234!"
        Calling-Station-Id = "AA:BB:CC:DD:EE:11"

+- entering group authorize {...}
|
+--[filter_username] = ok
|
+--[rest] = ok
|
rest: Expanding ${..connect_uri}/auth
rest: Sending HTTP POST to http://nac-api:8000/auth
rest: Response code 200
rest: Response: {"success": true, "group": "employee"}

+- entering group post-auth {...}
|
+--[rest] = ok
|
rest: Sending HTTP POST to http://nac-api:8000/authorize
rest: Response code 200
rest: Response: {"vlan_id": 20}

Sending Access-Accept of id 123 from 192.168.1.1:1812 to 127.0.0.1:54321
    Tunnel-Type:0 = VLAN
    Tunnel-Medium-Type:0 = IEEE-802
    Tunnel-Private-Group-Id:0 = "20"
    Filter-Id = "employee-acl"
```

**Önemli Log Satırları:**
- `Expand ${..connect_uri}` - URI expansion
- `Sending HTTP POST to ...` - API çağrı
- `Response code 200/401` - HTTP status
- `Sending Access-Accept/Reject` - Yanıt paketi

### Docker'da Debug Mode

```bash
# Docker container'da FreeRADIUS debug mode'da başlat
docker compose exec freeradius radiusd -X
```

---

## Production vs Development Konfigürasyonu

### Development

**clients.conf:**
```conf
secret = testing123
ipaddr = 172.20.0.0/24  # Tüm docker subnet'i
```

**rest:**
```conf
connect_uri = "http://nac-api:8000"  # HTTP (unencrypted)
timeout = 10.0  # Uzun timeout
```

**sites-enabled/default:**
```conf
# Minimal konfigürasyon
```

**Avantajları:**
- Debugging kolay
- Hızlı geliştirme
- Test ve tanılama basit

### Production

**clients.conf:**
```conf
secret = $LONG_RANDOM_KEY_32_CHAR_MINIMUM  # Güçlü anahtar
ipaddr = 192.168.1.10  # Belirli NAS IP'leri
ipaddr = 192.168.1.11
```

**rest:**
```conf
connect_uri = "https://nac-api:8443"  # HTTPS (encrypted)
connect_timeout = 5.0
timeout = 8.0
pool {
    min = 5
    max = 50  # Daha yüksek kapasitesi
}
```

**sites-enabled/default:**
```conf
# Detaylı hata handling
# Fallback mekanizmaları
# TLS/SSL enforcing
```

**Güvenlik Kontrolleri:**
- Secret rotation (haftalık/aylık)
- API authentication (API key, OAuth)
- Rate limiting
- Audit logging
- Network isolation (VPN/firewall)
- Certificate pinning

**Monitoring:**
- FreeRADIUS uptime
- API latency
- Database connection pool
- Failed auth rates
- Accounting latency

---

# Entegrasyon Mimarisi

## Bileşenler Arası Harita

```
┌─────────────────────────────────────────────────────────────┐
│                     Client/Supplicant                       │
│                  (802.1X or MAC-based auth)                │
└──────────────────────────────┬──────────────────────────────┘
                               │ RADIUS Access-Request
                               ↓
┌──────────────────────────────────────────────────────────────┐
│                    NAS (Switch/AP)                           │
│                  (Port Access Control)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │ Username, Password, MAC, NAS-IP
                       ↓
┌──────────────────────────────────────────────────────────────┐
│                   FreeRADIUS Server                          │
│                                                              │
│  1. authorize:       (filter_username, rest → /auth)        │
│  2. authenticate:    (empty)                                │
│  3. post-auth:       (rest → /authorize)                    │
│  4. accounting:      (rest → /accounting)                   │
│                                                              │
│  Modules: rlm_rest, rlm_sql (optional)                      │
│  Listen: 127.0.0.1:1812 (auth), 1813 (acct)               │
└──────────────────┬───────────────────────────────────────────┘
                   │ HTTP POST /auth, /authorize, /accounting
                   ↓
┌──────────────────────────────────────────────────────────────┐
│                   FastAPI API (nac-api)                      │
│                                                              │
│  Endpoints:                                                 │
│  - POST /auth        (username, password, mac)              │
│  - POST /authorize   (username, mac)                        │
│  - POST /accounting  (oturum bilgileri)                     │
│                                                              │
│  Policy Engine:                                             │
│  - Şifre doğrulama                                          │
│  - Grup belirleme                                           │
│  - VLAN ataması                                             │
│  - Oturum tracking                                          │
└──────────────────┬───────────────────────────────────────────┘
                   │ SELECT/INSERT/UPDATE
                   ↓
┌──────────────────────────────────────────────────────────────┐
│                  PostgreSQL Database                         │
│                                                              │
│  Tables:                                                    │
│  - radcheck (users)                                         │
│  - radreply (user attributes)                              │
│  - radusergroup (user-group mapping)                        │
│  - radgroupreply (group-vlan mapping)                       │
│  - radacct (session accounting)                            │
│  - mac_devices (mac-based auth)                            │
└──────────────────────────────────────────────────────────────┘
```

## NAC Kimlik Doğrulama Akışı (802.1X)

```
1. Supplicant (laptop) → NAS'a bağlanır

2. NAS → FreeRADIUS: Access-Request
   {
       User-Name: "emp_mehmet"
       User-Password: "Emp1234!"
       Calling-Station-Id: "AA:BB:CC:DD:EE:11"
       NAS-IP-Address: "192.168.1.1"
   }

3. FreeRADIUS authorize:
   - filter_username: "emp_mehmet" temizle
   - rest POST http://nac-api:8000/auth {
       "username": "emp_mehmet",
       "password": "Emp1234!",
       "calling_station_id": "AA:BB:CC:DD:EE:11"
     }

4. API:
   - radcheck'ten emp_mehmet'i sor
   - Şifreyi doğrula (hash compare)
   - HTTP 200 döndür

5. FreeRADIUS post-auth:
   - Auth başarılı
   - rest POST http://nac-api:8000/authorize {
       "username": "emp_mehmet",
       "calling_station_id": "AA:BB:CC:DD:EE:11"
     }

6. API:
   - radusergroup'tan emp_mehmet'in grupları sor → "employee"
   - radgroupreply'den "employee" grubu için VLAN sor
   - {
       "vlan_id": 20,
       "filter_id": "employee-acl",
       "group": "employee"
     }

7. FreeRADIUS:
   - radusergroup ve radgroupreply'den atribütler al
   - Tunnel-Type: 13 (VLAN)
   - Tunnel-Private-Group-Id: 20
   - Filter-Id: "employee-acl"

8. FreeRADIUS → NAS: Access-Accept {
       Tunnel-Type: 13
       Tunnel-Medium-Type: 6
       Tunnel-Private-Group-Id: 20
       Filter-Id: "employee-acl"
   }

9. NAS:
   - Supplicant'ı VLAN 20'ye atar
   - Access control list (employee-acl) uygular

10. FreeRADIUS ← NAS: Accounting-Request (Start)
    - acctsessionid: "01234567"
    - acct_status_type: "Start"

11. FreeRADIUS accounting:
    - rest POST http://nac-api:8000/accounting {
        "username": "emp_mehmet",
        "acct_status_type": "Start",
        "acct_session_id": "01234567",
        ...
      }

12. API:
    - radacct'a INSERT yap
    - Oturum başlangıç kaydı

13. Oturum devam ederken periyodik:
    - Accounting-Request (Interim-Update)
    - radacct'a UPDATE (trafik, süre)

14. Oturum bittiğinde:
    - Accounting-Request (Stop)
    - radacct'a UPDATE (final stats)
```

## MAC-Based Authentication (MAB) Akışı

```
1. Yazıcı → NAS'a bağlanır (DHCP kullanır, 802.1X yok)

2. NAS → FreeRADIUS: Access-Request
   {
       User-Name: "AA:BB:CC:DD:EE:01"  # MAC adresi user olarak
       Calling-Station-Id: "AA:BB:CC:DD:EE:01"
       NAS-IP-Address: "192.168.1.1"
   }

3. FreeRADIUS authorize:
   - filter_username: "AA:BB:CC:DD:EE:01" temizle
   - rest POST http://nac-api:8000/auth {
       "username": "AA:BB:CC:DD:EE:01",
       "calling_station_id": "AA:BB:CC:DD:EE:01"
     }

4. API:
   - mac_devices'ten MAC adresi sor
   - Bulundu: groupname = "iot_devices", is_active = true
   - HTTP 200 döndür

5. FreeRADIUS post-auth:
   - rest POST http://nac-api:8000/authorize {
       "username": "AA:BB:CC:DD:EE:01",
       "calling_station_id": "AA:BB:CC:DD:EE:01"
     }

6. API:
   - mac_devices'ten groupname = "iot_devices" oku
   - radgroupreply'den "iot_devices" grubu için VLAN sor
   - Tunnel-Private-Group-Id: 40

7. FreeRADIUS → NAS: Access-Accept {
       Tunnel-Type: 13
       Tunnel-Medium-Type: 6
       Tunnel-Private-Group-Id: 40
       Filter-Id: "iot-acl"
   }

8. NAS:
   - Yazıcıyı VLAN 40'a atar
   - IoT ACL kurallarını uygular
```

---

# Güvenlik ve Production Notları

## Şifre Güvenliği

### Development (Mevcut)
- Plaintext şifreler (`Cleartext-Password`) kabul edilir
- Test ve debugging amaçlı

### Production (Tavsiye Edilen)

1. **Hash Yöntemi**: Bcrypt veya Scrypt
   ```
   Kullanıcı şifresi: "Emp1234!"
   Hash: "$2b$12$vI8asubPEM7gexjZ38.v...."
   ```

2. **API Doğrulaması**:
   ```python
   from passlib.context import CryptContext

   pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

   @app.post("/auth")
   async def authenticate(req: AuthRequest):
       user = db.query(RadCheck).filter(username=req.username).first()
       if not pwd_context.verify(req.password, user.value):
           return JSONResponse(status_code=401, content={"error": "Invalid password"})
       return {"success": true}
   ```

3. **Veritabanı**:
   - Şifreler sadece hash olarak depolanır
   - Plaintext şifreler API memory'sinde de hashlenmelidir (logging'e kaçmasını önlemek için)

## Secret Key Yönetimi

### FreeRADIUS Secret (clients.conf)

**Development:**
```conf
secret = testing123  # Örnek secret
```

**Production:**
```conf
secret = $(FREERADIUS_SECRET)  # Environment variable
```

**Oluşturma:**
```bash
openssl rand -hex 32  # 64-karakter hex string
# Çıktı: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2
```

**Rotation (Production):**
- Haftalık veya aylık değiştirilmelidir
- Zero-downtime rotation için, eski ve yeni secret'leri paralel desteklemek gerekebilir:
  ```conf
  client docker_network {
      ipaddr = 172.20.0.0/24
      secret = new_secret_key_here
      # old_secret = old_secret_key_here  # Geçiş döneminde
  }
  ```

## TLS/SSL (HTTPS)

### Mevcut Durum
```conf
connect_uri = "http://nac-api:8000"  # Unencrypted
```

### Production (Zorunlu)
```conf
connect_uri = "https://nac-api:8443"
tls {
    ca_file = "/etc/freeradius/certs/ca.crt"
    certificate_file = "/etc/freeradius/certs/cert.pem"
    private_key_file = "/etc/freeradius/certs/key.pem"
    cipher_list = "ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256"
}
```

**Sertifika Oluşturma:**
```bash
# Self-signed cert (test amaçlı)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365

# CA-signed cert (production)
# 1. CSR oluştur
openssl req -new -key key.pem -out cert.csr
# 2. CA'ya göndersen imza al
# 3. cert.pem dosyası olarak kaydet
```

## Database Security

### Veritabanı Bağlantısı

**Development:**
```
postgresql://user:password@localhost/nac_db
```

**Production:**
```
postgresql://user:$DB_PASSWORD@db.internal:5432/nac_db?sslmode=require
```

- **sslmode=require**: Şifreli bağlantı zorunlu
- **Dahili Network**: Public internet'e açık değil
- **Firewall**: FreeRADIUS ve API konteynerlerine sınırlı erişim

### Veritabanı Credentials

```bash
# Ortam değişkenlerine kaydet (konteyner secret'leri ile)
export DB_PASSWORD=$(cat /run/secrets/db_password)
export DB_USER=$(cat /run/secrets/db_user)
```

## Logging ve Audit Trail

### FreeRADIUS Logs

**Development:**
```bash
radiusd -X  # STDOUT'a tüm detaylar
```

**Production:**
```conf
# /etc/freeradius/radiusd.conf
log {
    destination = "files"
    file = "${logdir}/radius.log"
    level = 2  # INFO level

    # Detaylı request logging
    requests = "${logdir}/requests.log"
}
```

**Log Dosyaları:**
- `/var/log/freeradius/radius.log` - Genel log
- `/var/log/freeradius/requests.log` - Her isteğin detayı
- `/var/log/freeradius/sql.log` - SQL sorgularının detayı

### API Logging

**FastAPI (production):**
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/nac-api/app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

@app.post("/auth")
async def authenticate(req: AuthRequest):
    logger.info(f"AUTH_REQUEST: username={req.username}")
    # ... işle ...
    logger.info(f"AUTH_SUCCESS: username={req.username}")
    return {"success": true}
```

### Veritabanı Audit

**PostgreSQL Logging:**
```sql
-- Kimlik doğrulama başarısızlıkları ve radikal değişiklikleri logla
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    event_time TIMESTAMP DEFAULT NOW(),
    event_type VARCHAR(64),  -- AUTH_FAILED, USER_CREATED, USER_DELETED, vb.
    username VARCHAR(64),
    source_ip VARCHAR(15),
    details TEXT
);

-- Trigger: radcheck'te değişim yapıldığında log al
CREATE TRIGGER radcheck_audit AFTER INSERT OR UPDATE OR DELETE ON radcheck
FOR EACH ROW
EXECUTE FUNCTION log_radcheck_change();
```

## Rate Limiting ve DOS Protection

### FreeRADIUS Rate Limiting

```conf
# /etc/freeradius/mods-enabled/dynamic_clients
dynamic_clients {
    server = "home"
    lifetime = 3600  # Yeni NAS'lar 1 saatlik cache'de
    allow_unknown = no  # Tanımlanmayan NAS'ları reddet
}
```

### API Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/auth")
@limiter.limit("100/minute")  # IP başına max 100 istek/dakika
async def authenticate(req: AuthRequest):
    # ...
```

## Monitoring ve Alerting

### Kritik Metrikleri

1. **FreeRADIUS Uptime**: Container health check
2. **API Response Time**: > 5 saniye ise alert
3. **Database Connection Pool**: > 90% ise warning
4. **Failed Auth Rate**: > 10% ise alert
5. **Disk Space**: /var/log ve database için

### Docker Health Check

```yaml
# docker-compose.yml
services:
  freeradius:
    healthcheck:
      test: ["CMD", "radtest", "test", "test", "localhost", "0", "testing123"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram

auth_counter = Counter('nac_auth_total', 'Total auth attempts', ['username', 'result'])
auth_duration = Histogram('nac_auth_duration_seconds', 'Auth request duration')

@app.post("/auth")
async def authenticate(req: AuthRequest):
    with auth_duration.time():
        try:
            # ... işle ...
            auth_counter.labels(username=req.username, result='success').inc()
        except Exception:
            auth_counter.labels(username=req.username, result='failure').inc()
```

---

## Sonuç

NAC sistemi, FreeRADIUS ve FastAPI entegrasyonu sayesinde modern, esnek bir ağ erişim kontrol platformu sağlar:

**Veritabanı:** PostgreSQL standartlarına uygun, RADIUS-uyumlu şema
**FreeRADIUS:** REST modülü ile FastAPI'ye delegeli politika yönetimi
**FastAPI API:** Şifre doğrulaması, VLAN ataması, oturum tracking
**Security:** Production ortamında TLS, strong secrets, audit logging gerekli

Bileşenler arasındaki data flow temizdir ve her bileşen bağımsız olarak test edilebilir.

---

**Döküman Tarihi:** 2025-03-23
**Sistem Sürümü:** 1.0
**Durum:** Production-Ready (Security hardening ile)
