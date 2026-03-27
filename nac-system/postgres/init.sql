-- ============================================================
-- NAC Sistemi — Veritabanı Şeması
-- FreeRADIUS uyumlu tablo yapısı + accounting tablosu
-- ============================================================

-- ── radcheck: Kullanıcı kimlik bilgileri ──
-- FreeRADIUS authorize aşamasında bu tabloyu sorgular.
-- "op" alanı: := (atama), == (eşitlik kontrolü), += (ekleme)

CREATE TABLE IF NOT EXISTS radcheck (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(64) NOT NULL,
    attribute   VARCHAR(64) NOT NULL,
    op          CHAR(2) NOT NULL DEFAULT ':=',
    value       VARCHAR(253) NOT NULL
);
CREATE INDEX idx_radcheck_username ON radcheck(username);

-- ── radreply: Kullanıcıya dönülecek RADIUS atribütleri ──
-- Başarılı auth sonrası kullanıcıya özel atribütler burada.
CREATE TABLE IF NOT EXISTS radreply (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(64) NOT NULL,
    attribute   VARCHAR(64) NOT NULL,
    op          CHAR(2) NOT NULL DEFAULT ':=',
    value       VARCHAR(253) NOT NULL
);
CREATE INDEX idx_radreply_username ON radreply(username);

-- ── radusergroup: Kullanıcı-grup ilişkileri ──
-- priority: düşük değer = yüksek öncelik
CREATE TABLE IF NOT EXISTS radusergroup (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(64) NOT NULL,
    groupname   VARCHAR(64) NOT NULL,
    priority    INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_radusergroup_username ON radusergroup(username);

-- ── radgroupreply: Grup bazlı atribütler ──
-- VLAN atamaları burada tanımlanır.
CREATE TABLE IF NOT EXISTS radgroupreply (
    id          SERIAL PRIMARY KEY,
    groupname   VARCHAR(64) NOT NULL,
    attribute   VARCHAR(64) NOT NULL,
    op          CHAR(2) NOT NULL DEFAULT ':=',
    value       VARCHAR(253) NOT NULL
);
CREATE INDEX idx_radgroupreply_groupname ON radgroupreply(groupname);

-- ── radacct: Accounting (oturum) kayıtları ──
CREATE TABLE IF NOT EXISTS radacct (
    id                  BIGSERIAL PRIMARY KEY,
    acctsessionid       VARCHAR(64) NOT NULL,
    acctuniqueid        VARCHAR(32) NOT NULL UNIQUE,
    username            VARCHAR(64) NOT NULL,
    nasipaddress        VARCHAR(15) NOT NULL,
    nasportid           VARCHAR(32),
    acctstarttime       TIMESTAMP,
    acctupdatetime      TIMESTAMP,
    acctstoptime        TIMESTAMP,
    acctsessiontime     BIGINT DEFAULT 0,
    acctinputoctets     BIGINT DEFAULT 0,
    acctoutputoctets    BIGINT DEFAULT 0,
    acctterminatecause  VARCHAR(32),
    framedipaddress     VARCHAR(15),
    callingstation      VARCHAR(50),       -- MAC adresi
    acctstatustype      VARCHAR(25)
);
CREATE INDEX idx_radacct_username ON radacct(username);
CREATE INDEX idx_radacct_session ON radacct(acctsessionid);
CREATE INDEX idx_radacct_start ON radacct(acctstarttime);

-- ── mac_devices: MAB için kayıtlı cihazlar ──
CREATE TABLE IF NOT EXISTS mac_devices (
    id          SERIAL PRIMARY KEY,
    mac_address VARCHAR(17) NOT NULL UNIQUE,  -- AA:BB:CC:DD:EE:FF formatı
    device_name VARCHAR(128),
    device_type VARCHAR(64),                  -- printer, ip_phone, camera vb.
    groupname   VARCHAR(64) NOT NULL DEFAULT 'guest',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_mac_devices_mac ON mac_devices(mac_address);

-- ============================================================
-- ÖRNEK VERİLER
-- ============================================================

-- ── Grup Politikaları (VLAN Atamaları) ──
-- Tunnel-Type=VLAN(13), Tunnel-Medium-Type=IEEE-802(6)
-- Tunnel-Private-Group-Id = VLAN numarası

-- Admin grubu → VLAN 10
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES
    ('admin', 'Tunnel-Type', ':=', '13'),
    ('admin', 'Tunnel-Medium-Type', ':=', '6'),
    ('admin', 'Tunnel-Private-Group-Id', ':=', '10'),
    ('admin', 'Filter-Id', ':=', 'admin-acl');

-- Employee grubu → VLAN 20
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES
    ('employee', 'Tunnel-Type', ':=', '13'),
    ('employee', 'Tunnel-Medium-Type', ':=', '6'),
    ('employee', 'Tunnel-Private-Group-Id', ':=', '20'),
    ('employee', 'Filter-Id', ':=', 'employee-acl');

-- Guest grubu → VLAN 30
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES
    ('guest', 'Tunnel-Type', ':=', '13'),
    ('guest', 'Tunnel-Medium-Type', ':=', '6'),
    ('guest', 'Tunnel-Private-Group-Id', ':=', '30'),
    ('guest', 'Filter-Id', ':=', 'guest-acl');

-- IoT Devices grubu → VLAN 40
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES
    ('iot_devices', 'Tunnel-Type', ':=', '13'),
    ('iot_devices', 'Tunnel-Medium-Type', ':=', '6'),
    ('iot_devices', 'Tunnel-Private-Group-Id', ':=', '40'),
    ('iot_devices', 'Filter-Id', ':=', 'iot-acl');

-- ── Kullanıcılar ──
-- Şifreler bcrypt ile hashlenmiş durumda (Hashed-Password)

-- ────────────────────────────────────────────
-- ADMIN GRUBU (VLAN 10) — IT Yöneticileri
-- ────────────────────────────────────────────
INSERT INTO radcheck (username, attribute, op, value) VALUES
    ('admin_ali', 'Hashed-Password', ':=', '$2b$12$ynmvNKl7wSq06VKUe5pXFun8ZpyTuBUOQiMCJ2spWdmdAwd.8c0VG');
INSERT INTO radusergroup (username, groupname, priority) VALUES
    ('admin_ali', 'admin', 1);

INSERT INTO radcheck (username, attribute, op, value) VALUES
    ('admin_zeynep', 'Hashed-Password', ':=', '$2b$12$P.OoZkEVvsX13l7/dCNT4ubQPc.Mo1b63Q5T898vt6fGfbiVZR5b2');
INSERT INTO radusergroup (username, groupname, priority) VALUES
    ('admin_zeynep', 'admin', 1);

INSERT INTO radcheck (username, attribute, op, value) VALUES
    ('admin_burak', 'Hashed-Password', ':=', '$2b$12$scBLj7JiqNfrycJUYnD74uRrhnZYZh2flWqdS8cTstjuR0KxiCSYu');
INSERT INTO radusergroup (username, groupname, priority) VALUES
    ('admin_burak', 'admin', 1);

-- ────────────────────────────────────────────
-- EMPLOYEE GRUBU (VLAN 20) — Şirket Çalışanları
-- ────────────────────────────────────────────
INSERT INTO radcheck (username, attribute, op, value) VALUES
    ('emp_mehmet', 'Hashed-Password', ':=', '$2b$12$8ni10iwnUu0FZJYJXf6Q1OWZvUwzPotK9LUr8p2G/b9b3AWZHLb1e');
INSERT INTO radusergroup (username, groupname, priority) VALUES
    ('emp_mehmet', 'employee', 1);

INSERT INTO radcheck (username, attribute, op, value) VALUES
    ('emp_ayse', 'Hashed-Password', ':=', '$2b$12$0f86Qj.oZIq60dCo.tBqXO37pPDod2N2vvyXLHBHxC9dOdjtzTYam');
INSERT INTO radusergroup (username, groupname, priority) VALUES
    ('emp_ayse', 'employee', 1);

INSERT INTO radcheck (username, attribute, op, value) VALUES
    ('emp_fatma', 'Hashed-Password', ':=', '$2b$12$0pln8b4rbuFrZI9JJYNeN.F4fzGCb3qkVWRbyvvTALcpJsw2XKA36');
INSERT INTO radusergroup (username, groupname, priority) VALUES
    ('emp_fatma', 'employee', 1);

INSERT INTO radcheck (username, attribute, op, value) VALUES
    ('emp_can', 'Hashed-Password', ':=', '$2b$12$TY0tr4HLn8rzWqqdjZQU7uVTc44AAOFnlDkmgeOPFPNzQ6/Zv45Pu');
INSERT INTO radusergroup (username, groupname, priority) VALUES
    ('emp_can', 'employee', 1);

INSERT INTO radcheck (username, attribute, op, value) VALUES
    ('emp_deniz', 'Hashed-Password', ':=', '$2b$12$3rZC.APBLAQ0aiaARoihIO.yJITyMOZGFulIKv50s2p6J/WAjrfW2');
INSERT INTO radusergroup (username, groupname, priority) VALUES
    ('emp_deniz', 'employee', 1);

-- ────────────────────────────────────────────
-- GUEST GRUBU (VLAN 30) — Misafirler / Geçici Erişim
-- ────────────────────────────────────────────
INSERT INTO radcheck (username, attribute, op, value) VALUES
    ('guest_user', 'Hashed-Password', ':=', '$2b$12$ByU4j60jfrS8ZChLmtEqBeitlNODYW3rdakNBVmPCtsYm9moyP84m');
INSERT INTO radusergroup (username, groupname, priority) VALUES
    ('guest_user', 'guest', 1);

INSERT INTO radcheck (username, attribute, op, value) VALUES
    ('guest_ahmet', 'Hashed-Password', ':=', '$2b$12$ww74az2si.Z/nzEyPUqw3eMKhWG2GgEosk90BVEQRdxhfZks.X/06');
INSERT INTO radusergroup (username, groupname, priority) VALUES
    ('guest_ahmet', 'guest', 1);

INSERT INTO radcheck (username, attribute, op, value) VALUES
    ('guest_elif', 'Hashed-Password', ':=', '$2b$12$YCNLIUFFpwqNzHUHtCmYruHe4P9zOK4oMJmBdSuEHXHgI6F7A8ePS');
INSERT INTO radusergroup (username, groupname, priority) VALUES
    ('guest_elif', 'guest', 1);

INSERT INTO radcheck (username, attribute, op, value) VALUES
    ('guest_tamir', 'Hashed-Password', ':=', '$2b$12$lvJdYN92haz2bbT4umbDy.9cfrq5EeCZSrzdjup.jXjSUsr5wlEWK');
INSERT INTO radusergroup (username, groupname, priority) VALUES
    ('guest_tamir', 'guest', 1);

-- ────────────────────────────────────────────
-- MAB Cihazları — MAC Adresi ile Otomatik Kimlik Doğrulama
-- ────────────────────────────────────────────
INSERT INTO mac_devices (mac_address, device_name, device_type, groupname) VALUES
    ('AA:BB:CC:DD:EE:01', 'Kat-1 Yazıcı', 'printer', 'iot_devices'),
    ('AA:BB:CC:DD:EE:02', 'Resepsiyon IP Telefon', 'ip_phone', 'employee'),
    ('AA:BB:CC:DD:EE:03', 'Güvenlik Kamerası', 'camera', 'iot_devices'),
    ('AA:BB:CC:DD:EE:04', 'Toplantı Odası Ekranı', 'display', 'employee'),
    ('AA:BB:CC:DD:EE:05', 'Kat-2 Yazıcı', 'printer', 'iot_devices'),
    ('AA:BB:CC:DD:EE:06', 'Depo Sıcaklık Sensörü', 'sensor', 'iot_devices'),
    ('AA:BB:CC:DD:EE:07', 'Giriş Kapı Kilidi', 'smart_lock', 'iot_devices'),
    ('AA:BB:CC:DD:EE:08', 'Misafir WiFi AP', 'access_point', 'guest');
