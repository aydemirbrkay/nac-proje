# Volume ve Veri Yönetimi

## 1. Volume Türleri ve Stratejisi

Docker'da 3 volume türü mevcuttur. NAC projesi bu üçünü de kullanmaktadır:

| Tür | Konum | Kullanım | Avantaj |
|-----|-------|----------|---------|
| **Named Volume** | `/var/lib/docker/volumes/[name]/_data` | Kalıcı veri, shared | Lifecycle yönetimi, portability |
| **Bind Mount** | Host dosya sistemi | Hot-reload, config | Doğrudan host erişimi, geliştirme |
| **Anonymous Volume** | `/var/lib/docker/volumes/[UUID]/_data` | Temporary storage | NAC'ta kullanılmıyor |

### NAC Projesinde Kullanılan Volume'lar

```yaml
volumes:
  pg_data:     # Named volume — PostgreSQL data (persistent)
  redis_data:  # Named volume — Redis RDB dump (optional persistence)

services:
  postgres:
    volumes:
      - pg_data:/var/lib/postgresql/data           # Named volume
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro  # Bind mount (RO)

  redis:
    volumes:
      - redis_data:/data                            # Named volume

  api:
    volumes:
      - ./api:/app                                  # Bind mount (dev hot-reload)

  freeradius:
    volumes:
      - ./freeradius/clients.conf:/etc/freeradius/clients.conf
      - ./freeradius/mods-enabled/rest:/etc/freeradius/mods-enabled/rest
      - ./freeradius/sites-enabled/default:/etc/freeradius/sites-enabled/default
```

**Özet:** 2 named volume (kritik veri), 5 bind mount (config + geliştirme)

---

## 2. Named Volumes Detaylı Analiz

### 2.1 pg_data — PostgreSQL Kalıcı Veri

#### Konum

- **Linux:** `/var/lib/docker/volumes/pg_data/_data`
- **Windows (WSL2):** `\\.\pipe\docker_engine` → VM içinde → `C:\Users\[user]\AppData\Local\Docker\wsl\data\...`
- **macOS:** `~/Library/Containers/com.docker.docker/Data/vms/0/data/docker/volumes/pg_data/_data`

#### Kapsam — Veritabanında Nelerin Saklandığı

```
/var/lib/postgresql/data/
├── base/
│   ├── 1/                          # PostgreSQL sistem DB (templates, postgres)
│   ├── 16384/                      # NAC veritabanı (OID 16384)
│   │   ├── pg_filenode.map         # File node mapping
│   │   ├── [radcheck table]        # Kullanıcı erişim kuralları
│   │   ├── [radreply table]        # Cevap attributeleri
│   │   ├── [radacct table]         # Accounting logs
│   │   ├── [users table]           # Sistem kullanıcıları
│   │   └── [index files]           # B-tree indeksler
│   └── ...
├── pg_wal/                         # Write-ahead logs (crash recovery)
│   └── 000000010000000000000001    # WAL segment dosyaları
├── pg_xact/                        # Transaction status (commit/rollback)
├── pg_commit_ts/                   # Commit timestamp (optional)
├── postgresql.conf                 # Database configuration
├── pg_hba.conf                     # Host-based authentication
└── postmaster.pid                  # Running process ID
```

#### Kalıcılık Davranışı

| Durum | Sonuç | Volume |
|-------|-------|--------|
| Container normal shutdown | Graceful → data flushed → disk | ✓ Kalır |
| Container crash/SIGKILL | WAL replay on next start | ✓ Kalır |
| `docker-compose down` | Services stop, keep state | ✓ Kalır |
| `docker-compose down -v` | **Volumes DELETED** | ❌ Silinir |
| Host reboot/power loss | Data safe (persistent disk) | ✓ Kalır |

#### Kritik Veri

```
✓ radcheck          # 10.000+ kullanıcı access rules
✓ radreply          # Response attributes
✓ radacct           # Accounting logs (milyonlar)
✓ users             # System user credentials
✓ Schema/Indexes    # Database structure
```

**Sonuç:** PostgreSQL veri kaybı katastrofiktir → En yüksek koruma

#### Yararlılık Seviyeleri

- **Yüksek:** User accounts persist across restarts, accounting logs preserved
- **Kritik:** Veri kaybı = Sistem non-operational

---

### 2.2 redis_data — Redis RDB Dump

#### Konum

```
/var/lib/docker/volumes/redis_data/_data/
├── dump.rdb              # Redis database snapshot (binary format)
├── appendonly.aof        # Append-only file (optional, NAC'ta disable)
└── [sentinel files]      # Sentinel config (if enabled)
```

#### Persistence Stratejisi

```
Redis In-Memory Cache:
├─ Default mode: Volatile (memory only)
│  └─ Container stops → Data lost
├─ RDB mode: Periodic snapshot
│  └─ BGSAVE on shutdown → dump.rdb saved
├─ AOF mode: Every write logged
│  └─ Complete recovery, but slower
└─ Hybrid (RDB + AOF): Best of both

NAC Konfigürasyonu:
├─ Image: redis:8-alpine (minimal)
├─ Explicit config: Yok (default = RDB mode)
├─ Persistence: RDB snapshot (shutdown time)
└─ Recovery: Point-in-time (saniyeler kaybı)
```

#### Kapsam — Neler Saklanır

```yaml
Redis data (session cache):
  - user_session:{id}          # Authentication tokens
  - rate_limit:{ip}            # Request rate limiters
  - temp_cache:{key}           # Temporary computations
  - ntp_sync:{timestamp}       # NTP sync state
```

**Veri Türü:** Geçici, cache, session

#### Kalıcılık Davranışı

| Durum | RDB Dump | Veri |
|-------|----------|------|
| `docker-compose up/down` | Saved | ✓ Korunur |
| Container crash | May incomplete | Kısmi kayıp (~sn) |
| SIGKILL | Possible loss | ❌ Kaybedilir |
| Power loss | Incomplete | ❌ Kaybedilir |
| Host reboot | Safe (persistent) | ✓ Korunur |

#### Yararlılık Seviyeleri

- **Orta:** Rate limiter counters survive restart
- **Tolerable:** Session cache loseable (users re-login)
- **Tavsiye:** Enable AOF for production

**Sonuç:** Redis veri kaybı irritating ama tolerable

---

## 3. Bind Mounts Detaylı Analiz

### 3.1 ./api:/app — Python Uygulaması (Hot Reload)

#### Mapping Detayı

```
Host Container                     Container Path
./api/main.py              →       /app/main.py
./api/routes/auth.py       →       /app/routes/auth.py
./api/routes/users.py      →       /app/routes/users.py
./api/config.py            →       /app/config.py
./api/__pycache__/         →       /app/__pycache__/
./api/.git/                →       /app/.git/
[tüm files]                →       [tüm files]
```

#### Amaç: Geliştirme Sırasında Hot-Reload

```
Sıra:
1. Developer: main.py dosyasını host'ta değiştirir
2. Mount: Değişiklik container'a yayılır (nanosaniye)
3. Uvicorn: File watcher değişimi algılar
   → Process otomatik restarts
   → New code running (30-500ms)
4. Browser: F5 → Yeni kod görülür
```

**Avantaj:** Compile-test-fix cycle'da saniye cinsinden gain

#### File Permission Issues

```
Olası Sorun:
├─ Host file: owner=user (UID 1000)
├─ Container process: running as root (UID 0) or app (UID 999)
└─ Permission mismatch → Read/Write failures

Örnek Hata:
permission denied: /app/main.py
→ Container process cannot modify file

Çözüm:
├─ Host: chmod 666 /api/* (permissive)
├─ atau Dockerfile: RUN chown -R app:app /app
└─ Good practice: Match UIDs
```

#### Performance Consideration

```
Performance Impact:
├─ Small project (10 files): Negligible
├─ Medium project (100 files): ~5% I/O overhead
├─ Large project (1000+ files): ~20% slower

NAC API size: ~50 files → Negligible impact

Optimization (optional):
├─ Exclude __pycache__: /app/__pycache__ (anonymous volume)
├─ Exclude .git: /app/.git (anonymous volume)
├─ Exclude .venv: /app/.venv (anonymous volume)
└─ But not implemented in NAC (not needed)
```

#### Read-Write Access

No `:ro` flag → Full read-write
```bash
# Container can:
docker exec api rm -rf /app/*    # Dangerous!
docker exec api touch /app/new_file.py
```

**Risk:** Accidental deletion/modification from container

---

### 3.2 ./db/init.sql — Database Initialization (Read-Only)

#### Mapping

```
Host                          Container
./db/init.sql        →        /docker-entrypoint-initdb.d/init.sql (RO)
```

#### Read-Only Flag (`:ro`)

```
:ro = read-only mount
→ Container cannot modify file
→ Security: Prevent accidental writes
→ Clarity: This is template, not mutable data
```

#### PostgreSQL Initialization Flow

```
PostgreSQL Startup Sequence:
1. Datadir check: /var/lib/postgresql/data exists?
   ├─ NO: Initialize new cluster (initdb)
   └─ YES: Skip (data already exists)

2. Entrypoint script runs
   ├─ Scan /docker-entrypoint-initdb.d/
   ├─ Sort *.sql, *.sh alphabetically
   ├─ Execute each file (init.sql first)
   └─ CREATE TABLE radcheck, radreply, ...

3. Database ready
   ├─ Schema now in pg_data:/var/lib/postgresql/data/base/
   └─ Future restarts: Skip entrypoint (data exists)
```

#### Critical Behavior: Init Only Once

```
First Run (no pg_data volume data):
├─ init.sql executes → Schema created
├─ radcheck table created (empty)
└─ Next startup: Data exists → init.sql SKIPPED

Implication:
├─ Modify init.sql → Need fresh database
├─ Command: docker-compose down -v && docker-compose up -d
├─ WARNING: Deletes all data (radacct logs, user configs)
```

#### Content Example

```sql
-- db/init.sql snippet
CREATE TABLE IF NOT EXISTS radcheck (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL,
    attribute VARCHAR(64) NOT NULL,
    op VARCHAR(2) NOT NULL,
    value VARCHAR(253)
);

CREATE TABLE IF NOT EXISTS radacct (
    radacctid BIGSERIAL PRIMARY KEY,
    username VARCHAR(64),
    acctsessionid VARCHAR(32),
    acctstarttime TIMESTAMP,
    acctstoptime TIMESTAMP,
    acctinputoctets BIGINT,
    acctoutputoctets BIGINT
);

-- Create indexes for performance
CREATE INDEX radcheck_username ON radcheck(username);
CREATE INDEX radacct_username ON radacct(username);
CREATE INDEX radacct_sessionid ON radacct(acctsessionid);
```

---

### 3.3 ./freeradius/* — Configuration Files (Multiple Bind Mounts)

#### Mapping

```
Host (./freeradius/)                     Container (/etc/freeradius/)
clients.conf                    →        /etc/freeradius/clients.conf
mods-enabled/rest              →        /etc/freeradius/mods-enabled/rest
sites-enabled/default          →        /etc/freeradius/sites-enabled/default
```

#### Amaç: Config Reloading

```
Scenario: Update client secret
1. Edit ./freeradius/clients.conf (host)
2. Mount: Change propagated to container
3. FreeRADIUS: Reload config (SIGHUP or restart)
4. Result: New secret active immediately
5. Benefit: No image rebuild, fast iteration
```

#### Permission Requirement: chmod 600

```yaml
freeradius:
  entrypoint: >
    /bin/sh -c
    "chmod 600 /etc/freeradius/clients.conf &&
     chmod 600 /etc/freeradius/mods-enabled/rest &&
     /usr/sbin/radiusd -fxx"
```

**Why chmod 600?**
```
FreeRADIUS Security Model:
├─ clients.conf contains shared secrets
├─ Shared secrets are sensitive (like passwords)
├─ Requirement: Only owner can read/write
├─ Enforcement: chmod 600 (owner rwx, group/other none)
└─ FreeRADIUS refuses to start if wrong permissions
```

#### Version Control

```
Git tracking:
├─ ./freeradius/clients.conf    ✓ In version control
├─ ./freeradius/mods-enabled/   ✓ In version control
└─ ./freeradius/sites-enabled/  ✓ In version control

Benefits:
├─ Config changes tracked
├─ Easy rollback (git revert)
├─ Collaborative (team edits)
└─ Disaster recovery (restore from git)
```

---

## 4. Veri Kalıcılığı Matrisi

Tüm volume'ların özet durumu:

| Service | Volume Tipi | Veri Türü | Kalıcı mı? | Kayıp Riski | Kritikalite |
|---------|-------------|-----------|-----------|------------|-------------|
| PostgreSQL | Named (pg_data) | User credentials, radcheck | ✅ Evet | 🟢 Düşük | **🔴 Yüksek** |
| PostgreSQL Init | Bind (init.sql) | Schema template | ✅ Evet (host dosya) | 🟢 Düşük | **🟡 Orta** |
| Redis | Named (redis_data) | Session cache, rate limits | ⚠️ Kısmi (RDB) | 🟡 Orta | **🟡 Orta** |
| FastAPI Code | Bind (./api) | Python application | ✅ Evet (host dosya) | 🟢 Düşük | **🔴 Yüksek** |
| FreeRADIUS Config | Bind (./freeradius) | RADIUS config + secrets | ✅ Evet (host dosya) | 🟢 Düşük | **🔴 Yüksek** |

**Kritikal İş Akışı:** PostgreSQL (veri) > FastAPI (kod) > FreeRADIUS (konfigürasyon)

**Tolerans:** Redis cache (yeniden oluşturulabilir), init.sql (template sadece)

---

## 5. Veri Kaybı Risk Analizi ve Senaryoları

### 5.1 Senaryo 1: Normal Shutdown (`docker-compose down`)

```bash
$ docker-compose down
```

**Akış:**
```
1. SIGTERM sent to all containers
2. Graceful shutdown:
   ├─ PostgreSQL: Flush dirty pages → disk
   ├─ Redis: BGSAVE → dump.rdb
   ├─ FastAPI: Close connections
   └─ FreeRADIUS: Shutdown cleanly
3. Containers stop
4. Named volumes PERSIST ← Critical!
5. Bind mounts PERSIST (host files)
```

**Sonuç:** ✅ **VERI KAYBIYOK** — Next run veriler hazır

**Timeline:** ~5-10 saniye

---

### 5.2 Senaryo 2: Destructive Cleanup (`docker-compose down -v`)

```bash
$ docker-compose down -v    # WARNING: DANGEROUS!
```

**Akış:**
```
1. Same as Scenario 1, BUT:
2. After shutdown:
   ├─ docker-compose down -v
   └─ Named volumes DELETED:
      ├─ pg_data → /var/lib/docker/volumes/pg_data/ REMOVED
      └─ redis_data → /var/lib/docker/volumes/redis_data/ REMOVED
3. Bind mounts NOT affected (host files remain)
```

**Sonuç:** ❌ **KRİTİK VERİ KAYBI** — PostgreSQL completely gone!

```
Lost Forever:
├─ 10.000+ radcheck rules
├─ User configurations
├─ Accounting logs (milyonlar satır)
├─ System users
└─ Database schema (fixable from init.sql)
```

**Timeline:** Instant (data unrecoverable without backup)

**Caution:** `-v` flag hiçbir zaman production'da kullanılmamalı!

---

### 5.3 Senaryo 3: Container Crash (Ungraceful Shutdown)

```bash
# FastAPI process crash
$ docker-compose up -d
```

**Akış:**
```
1. Container dies unexpectedly (SIGKILL or segfault)
2. Named volumes untouched (persist on host)
3. PostgreSQL: WAL (write-ahead log) replay
   ├─ Last committed transactions: Restored
   ├─ Uncommitted transactions: Rolled back
   └─ Crash-safe by design
4. Redis: RDB snapshot incomplete?
   ├─ Last BGSAVE point restored
   └─ Recent changes since last save: LOST
5. Container restart → Ready to run
```

**Sonuç:** ✅ PostgreSQL OK, ⚠️ Redis potentially few seconds lost

**Timeline:** ~2-5 saniye recovery (WAL replay)

---

### 5.4 Senaryo 4: Host Disk Full

```
Scenario: /var/lib/docker/volumes/ disk at 100%
```

**Akış:**
```
1. PostgreSQL write operation triggered
2. Kernel cannot allocate blocks (disk full)
3. Write fails → PostgreSQL error
4. Connection hangs (waiting for disk)
5. Potential database corruption:
   ├─ Partial page write
   ├─ Index corruption
   └─ Transaction log corruption
```

**Sonuç:** ❌ **Data corruption** (recovery difficult)

**Mitigation:**
```bash
# Monitor disk space regularly
df -h /var/lib/docker/volumes/

# Alert thresholds:
├─ 80%: Warning, cleanup old backups
├─ 90%: Critical, stop writes, investigate
└─ 95%: Emergency, service unavailable

# Cleanup unused volumes:
docker volume prune
docker image prune
```

---

### 5.5 Senaryo 5: Host Reboot / Power Loss

```
Scenario: Sudden power loss or forced reboot
```

**Akış:**
```
1. Containers killed immediately (SIGKILL)
2. Named volumes on persistent host disk:
   ├─ PostgreSQL pg_data: Protected (journaled filesystem)
   ├─ Redis redis_data: Potentially incomplete RDB
   └─ Both recoverable on next boot
3. PostgreSQL start:
   ├─ Detects unclean shutdown
   ├─ Runs WAL recovery (automatic)
   ├─ Last committed state restored
   └─ Takes 30-60 seconds
4. Redis start:
   ├─ Last RDB snapshot loaded
   ├─ Post-snapshot changes: Lost
   └─ Cache rebuilt on demand
```

**Sonuç:** ✅ PostgreSQL recovers (WAL), ⚠️ Redis recent cache lost

**Timeline:** 30-60 saniye PostgreSQL recovery

**Protection:** Server-grade power supply (UPS) recommended

---

## 6. Yedekleme Stratejisi (Recommendations)

### 6.1 PostgreSQL Backup (CRITICAL)

#### Manual Backup

```bash
# Full database dump (SQL format)
docker-compose exec postgres pg_dump -U postgres nac > backup_$(date +%Y%m%d_%H%M%S).sql

# Compressed backup (smaller)
docker-compose exec postgres pg_dump -U postgres nac | gzip > backup_$(date +%Y%m%d).sql.gz

# Restore from backup
docker-compose exec postgres psql -U postgres nac < backup_20260323.sql

# Verify backup integrity
docker-compose exec postgres pg_restore --dbname=nac backup_20260323.sql
```

#### Automated Backup (Cron)

```bash
# Add to crontab:
0 2 * * * cd /path/to/nac-system && docker-compose exec postgres pg_dump -U postgres nac | gzip > /backups/nac_$(date +\%Y\%m\%d).sql.gz

# Keep 30 days of backups:
0 3 * * * find /backups -name "nac_*.sql.gz" -mtime +30 -delete
```

#### Backup Verification

```bash
# Test restore weekly:
docker-compose exec postgres createdb nac_test
docker-compose exec postgres psql -U postgres nac_test < /backups/nac_latest.sql
docker-compose exec postgres dropdb nac_test

# Check backup size:
ls -lh /backups/nac_*.sql.gz
# Expected: 5-50 MB (depends on radacct table size)
```

#### Retention Policy

```
Backup Schedule:
├─ Daily: Last 7 days (host storage)
├─ Weekly: Last 4 weeks (secondary storage)
├─ Monthly: Last 12 months (archive storage)
└─ Off-site: S3/Azure Blob recommended

Storage Recommendations:
├─ Host backup dir: /var/docker-backups/ (fast local)
├─ Weekly sync: rsync to NAS
├─ Offsite sync: AWS S3 (daily)
└─ Total cost: ~$10-50/month for S3 storage
```

---

### 6.2 Redis Backup (Optional)

#### Considerations

```
Should we backup Redis?
├─ Cache data: Replaceable (can rebuild)
├─ Session data: Short-lived (< 1 hour timeout)
├─ Rate limiter: Resettable (users just retry)
└─ Decision: Optional, but useful for uptime
```

#### Enable Persistence

```yaml
# docker-compose.yml
redis:
  command: redis-server --appendonly yes
  # Now uses both RDB + AOF (maximum durability)
```

#### Manual Backup

```bash
# Trigger snapshot
docker-compose exec redis redis-cli BGSAVE

# Copy dump file
docker cp nac-system-redis-1:/data/dump.rdb ./backups/redis_backup.rdb

# Restore (replace container's /data/dump.rdb then restart)
docker cp ./backups/redis_backup.rdb nac-system-redis-1:/data/dump.rdb
docker-compose restart redis
```

---

### 6.3 Configuration Backup (Via Git)

```bash
# Already versioned:
├─ ./freeradius/clients.conf ✓
├─ ./freeradius/mods-enabled/* ✓
├─ ./api/*.py ✓
└─ ./db/init.sql ✓

# Best practices:
git add proje-analizi/   # Document changes
git commit -m "Update RADIUS config"
git push origin main

# Rollback if needed:
git revert <commit-hash>
docker-compose down && docker-compose up -d
```

---

### 6.4 Disaster Recovery Plan

#### Recovery Time Objective (RTO)

```
Service Down → Service Operational
└─ PostgreSQL restore: 5-15 minutes (depending on backup size)
└─ Application restart: 30 seconds
└─ RADIUS restart: 10 seconds
─────────────────────────────────
Total RTO: ~20 minutes
```

#### Recovery Point Objective (RPO)

```
Data Loss Window (worst case)
└─ Last backup: 24 hours ago
└─ Since last backup: Radacct logs from past 24h
└─ Since last backup: User config changes from past 24h
─────────────────────────────────
Total RPO: ~24 hours
```

#### Recovery Procedure

```bash
# Step 1: Stop running system
docker-compose down

# Step 2: Delete corrupted volume
docker volume rm pg_data

# Step 3: Bring up fresh (will recreate via init.sql)
docker-compose up -d postgres

# Step 4: Wait for PostgreSQL ready
sleep 10
docker-compose exec postgres pg_isready

# Step 5: Restore from backup
docker-compose exec postgres psql -U postgres nac < /backups/nac_20260322.sql

# Step 6: Verify data
docker-compose exec postgres psql -U postgres nac -c "SELECT COUNT(*) FROM radcheck;"

# Step 7: Bring up remaining services
docker-compose up -d

# Step 8: Smoke test
curl -s http://localhost:8000/health | jq .
```

#### Test Recovery Quarterly

```bash
# Quarterly disaster recovery test:
1. Document current database size
2. Perform restore to test environment
3. Run smoke tests (user login, accounting)
4. Measure recovery time
5. Document any issues
6. Update recovery procedures
```

---

## 7. Üretim Önerileri (Production Recommendations)

### 7.1 Backup Automation

```
Priority: CRITICAL
─────────────────
Implement:
├─ Daily pg_dump to /var/docker-backups/ (local)
├─ Hourly sync to NAS via rsync
├─ Daily upload to AWS S3 (encrypted)
├─ 30-day retention policy (local)
├─ 365-day retention policy (S3)
└─ Automated restore testing (monthly)

Tool Recommendations:
├─ Bash + cron (simple, free)
├─ pg_backup_api (REST API interface)
├─ Barman (enterprise PostgreSQL backup)
└─ Borg backup (deduplicating)
```

### 7.2 Monitoring & Alerting

```
Metrics to Monitor:
├─ Volume disk usage (80% alert threshold)
├─ PostgreSQL connection pool saturation
├─ Redis memory usage
├─ Backup success/failure
├─ WAL archival status (if using)
└─ Query performance (slow queries)

Tools:
├─ Prometheus + Grafana (visualization)
├─ AlertManager (alerts)
├─ Custom health check endpoint (/health)
└─ CloudWatch (if on AWS)
```

### 7.3 Redis Persistence Decision

```
Current: RDB mode (snapshots only)
├─ Pros: Minimal performance impact
├─ Cons: Recent data loss on crash

Recommendation: Enable AOF (append-only)
├─ Command: redis-server --appendonly yes
├─ Trade-off: +5-10% CPU, +2x disk space
├─ Benefit: Point-in-time recovery (any second)
└─ Worth it for session data preservation

Production Config:
redis:
  command: >
    redis-server
    --appendonly yes
    --appendfsync everysec
    --save 60 1000
```

### 7.4 Storage Optimization

```
High-IOPS Storage for PostgreSQL:
├─ Production: SSD/NVMe (pg_data)
├─ Development: Regular disk (acceptable)
└─ Backup: HDD (cost-effective)

File System Recommendations:
├─ PostgreSQL: ext4 or XFS (journaled)
├─ Docker volumes: Mount on ext4 or ZFS
├─ Avoid: NFS for primary data (network latency)
├─ Backup: NFS OK (rsync to NAS)

Capacity Planning:
├─ radacct table growth: ~1KB per accounting record
├─ Estimated: 10M records = 10GB per year
├─ Reserve: 200GB for 20+ years
├─ Monitor: Cleanup old accounting logs (>2 years)
```

### 7.5 Named Volume Management

```bash
# List volumes
docker volume ls
# DRIVER  VOLUME NAME
# local   nac-system_pg_data
# local   nac-system_redis_data

# Inspect volume
docker volume inspect nac-system_pg_data
# Returns: mount point, labels, options

# Backup named volume
docker run --rm \
  -v pg_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/pg_data.tar.gz -C /data .

# Restore named volume
docker run --rm \
  -v pg_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/pg_data.tar.gz -C /data

# Cleanup unused volumes
docker volume prune -f
```

### 7.6 Database Maintenance

```sql
-- Regular maintenance (monthly)
VACUUM ANALYZE;                        -- Optimize storage, update stats
REINDEX DATABASE nac;                  -- Rebuild indexes
ANALYZE;                               -- Update query planner stats

-- Check database size
SELECT pg_size_pretty(pg_database_size('nac'));

-- Check table sizes
SELECT
  schemaname, tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Cleanup old accounting records (>2 years)
DELETE FROM radacct
WHERE acctstarttime < now() - interval '2 years';

-- Create backup before cleanup
-- Then: VACUUM FULL; ANALYZE;
```

### 7.7 Security: Bind Mount Considerations

```
Security Risks:
├─ ./freeradius/clients.conf readable from host (shared secrets)
├─ Container can potentially access host files
├─ Permission mismatches can expose data

Mitigation:
├─ Restrict file permissions: chmod 600 clients.conf
├─ Only authorized users can read (not world)
├─ Docker daemon runs as root (risky in shared environments)
├─ Consider: Copy configs into image instead of bind mount

Alternative (more secure):
# Instead of bind mount, use docker cp on startup
# Or: Add configs directly to image (COPY in Dockerfile)
```

---

## 8. Özet: Volume Stratejisi

### Güvenlik Hiyerarşisi

```
🔴 CRITICAL (must not lose):
   ├─ pg_data (PostgreSQL)
   └─ ./db/init.sql (schema definition)

🟡 IMPORTANT (nice to keep):
   ├─ redis_data (session cache)
   ├─ ./api/* (application code)
   └─ ./freeradius/* (configuration)

🟢 ACCEPTABLE (expendable):
   └─ Build artifacts (__pycache__, .compiled)
```

### Quick Reference: Volume Commands

```bash
# List
docker volume ls

# Create
docker volume create myvolume

# Inspect
docker volume inspect pg_data

# Clean
docker volume rm myvolume
docker volume prune          # Remove unused

# Backup
docker run --rm -v pg_data:/data -v ./backups:/backup \
  alpine tar czf /backup/pg_data.tar.gz -C /data .

# Restore
docker run --rm -v pg_data:/data -v ./backups:/backup \
  alpine tar xzf /backup/pg_data.tar.gz -C /data
```

### Quick Reference: docker-compose Commands

```bash
# Safe operations (preserve data)
docker-compose down                      # ✅ Safe
docker-compose restart                   # ✅ Safe
docker-compose up -d                     # ✅ Safe

# Dangerous operations (data loss)
docker-compose down -v                   # ❌ DELETE VOLUMES!
docker-compose rm -v                     # ❌ DELETE VOLUMES!
docker volume rm pg_data                 # ❌ DELETE DATA!
```

---

## 9. Checklist: Production Deployment

Before going live:

- [ ] Backup automation setup (cron job)
- [ ] Backup verification script created
- [ ] Monitoring dashboard configured (disk space, backups)
- [ ] AlertManager rules configured (backup failures)
- [ ] Disaster recovery procedure documented
- [ ] Recovery procedure tested (quarterly)
- [ ] PostgreSQL maintenance script scheduled (VACUUM, REINDEX)
- [ ] File permission audit completed (chmod 600 on secrets)
- [ ] Storage capacity forecasted (2-5 years)
- [ ] Off-site backup sync enabled (S3 or NAS)
- [ ] RTO/RPO targets documented and approved
- [ ] Backup retention policy enforced
- [ ] Named volume ownership verified (correct docker daemon)
- [ ] Encryption at rest evaluated (if required)
- [ ] Compliance requirements (data retention, audit logs) met

---

## 10. Referanslar

### PostgreSQL Dokumentasyon
- [PostgreSQL Backup & Recovery](https://www.postgresql.org/docs/current/backup.html)
- [PostgreSQL WAL (Write-Ahead Logging)](https://www.postgresql.org/docs/current/wal.html)
- [pg_dump Manual](https://www.postgresql.org/docs/current/app-pgdump.html)

### Docker Dokumentasyon
- [Docker Volumes Official Docs](https://docs.docker.com/storage/volumes/)
- [Docker Volume Drivers](https://docs.docker.com/storage/volumes/#use-a-volume-driver)
- [Docker Best Practices: Volumes](https://docs.docker.com/develop/dev-best-practices/)

### Redis Dokumentasyon
- [Redis Persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
- [Redis RDB vs AOF](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/#rdb)

### Best Practices
- [Docker Storage Drivers Performance](https://docs.docker.com/storage/)
- [Backup & Disaster Recovery Planning](https://www.postgresql.org/docs/current/continuous-archiving.html)
