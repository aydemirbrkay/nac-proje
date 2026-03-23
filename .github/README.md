# NAC System Deep Analysis Documentation

Private repository containing comprehensive architectural analysis of a RADIUS-based Network Access Control system.

## Overview

This repository holds an in-depth technical analysis of a NAC (Network Access Control) system built with:
- **Backend:** Python 3.13, FastAPI, SQLAlchemy, asyncpg
- **Infrastructure:** Docker Compose, PostgreSQL 18, Redis 8, FreeRADIUS 3.2
- **Scale:** 41 source files, 5 Docker services, 8,695+ lines of comprehensive analysis

## Contents

### Main Documentation
- **10 markdown analysis documents** (8,695+ lines total)
  - `proje-analizi/README.md` — Main entry point and navigation guide
  - `proje-analizi/00-dosya-envanteri.md` — File inventory (41 files)
  - `proje-analizi/01-servis-analizi.md` — 5 Docker services analysis
  - `proje-analizi/02-network-baglanti.md` — Network topology and connectivity
  - `proje-analizi/03-dockerfile-anatomisi.md` — Dockerfile layers and optimization
  - `proje-analizi/04-volume-veri-yonetimi.md` — Data persistence and volumes
  - `proje-analizi/05-istek-akisi.md` — Request flows (3 scenarios)
  - `proje-analizi/06-python-mimarisi-ve-dosyalar.md` — Python architecture (12 files, 3 layers)
  - `proje-analizi/07-veritabani-freeradius.md` — Database schema + FreeRADIUS config
  - `proje-analizi/08-diger-dosyalar.md` — Remaining files (25+ files)

### Technical Glossary
- **`proje-analizi/GLOSSARY.md`** — 100+ technical terms in Turkish ↔ English
  - RADIUS protocol terms (PAP, MAB, Accounting, CHAP)
  - Docker concepts (Container, Image, Volume, Network)
  - Database concepts (ORM, Schema, Transaction, Connection Pool)
  - Security concepts (TLS, mTLS, Secret Manager, Rate Limiting)
  - Network concepts (VLAN, DNS, DTLS, NAC)
  - Performance metrics (Latency, Throughput, Timeout)

### Architecture Diagrams
- **`proje-analizi/diagrams/`** — 7 Mermaid architecture diagrams (when available)
  - Service topology
  - Network flow
  - Request lifecycle
  - Database schema
  - Python module dependencies
  - PAP/MAB/Accounting flows
  - CI/CD pipeline recommendations

## Getting Started

1. **Read the main README:**
   ```
   proje-analizi/README.md
   ```

2. **Choose your learning path based on role:**
   - **System Architects:** Start with 00 → 01 → 05 → (02 or 06)
   - **DevOps Engineers:** Start with 01 → 02 → 03 → 04 → Health checks section
   - **Python Developers:** Start with 06 → 07 → models.py → schemas.py
   - **Network/RADIUS Specialists:** Start with 05 → 07 → FreeRADIUS configuration

3. **Reference the glossary:**
   - Look up unfamiliar terms in GLOSSARY.md
   - Turkish-English cross-references included

## Documentation Standards

- ✅ **Technical Depth:** Every line, every directive explained
- ✅ **Pedagogical:** "What" + "Why" + "How" approach
- ✅ **Multi-language:** Turkish primary, English technical terms
- ✅ **Visual:** ASCII diagrams, request flows, SQL examples
- ✅ **Practical:** Configuration examples, troubleshooting, production tips
- ✅ **Cross-linked:** Hyperlinked sections with related content

## Key System Components

### Services (5 Docker containers)
1. **FreeRADIUS** - RADIUS authentication server (UDP ports 1812-1813)
2. **API** - FastAPI NAC policy engine (HTTP port 8000)
3. **PostgreSQL** - Persistent data storage (6 tables)
4. **Redis** - In-memory cache for sessions and permissions
5. **pgAdmin** - Database management UI (port 5050)

### Authentication Flows Documented
- **PAP (Password Authentication Protocol)** - Username/password authentication
- **MAB (MAC Authentication Bypass)** - Device MAC-based access
- **Accounting** - Session tracking and billing

### Database Schema
- **users** — User credentials and metadata
- **groups** — User group definitions
- **sessions** — Active/terminated user sessions
- **devices** — Network devices (MAC, VLAN assignments)
- **vlans** — VLAN definitions and access policies
- **rules** — Authorization rules and policies

## Production Considerations

### Security Notes
- Database credentials currently in `.env` — use secret manager (Vault) in production
- RADIUS secret key requires rotation policy
- API endpoint protection needs bearer tokens or mTLS
- Network isolation should use separate network interfaces
- Audit logging should use immutable log solution (ELK, CloudWatch)

### High Availability Recommendations
- Multiple API instances with load balancer
- Database replication/failover (PostgreSQL streaming)
- Redis cluster for cache reliability
- DNS-based service discovery
- Automated health checks and restart policies

### Performance Optimization
- Connection pooling configuration tuning
- Redis cache strategy optimization
- Database query indexing review
- API rate limiting implementation
- RADIUS accounting batching

## Technologies Used

| Layer | Technology | Version |
|-------|-----------|---------|
| **Framework** | FastAPI | 0.100+ |
| **Runtime** | Python | 3.13 |
| **ORM** | SQLAlchemy | 2.0+ |
| **DB Driver** | asyncpg | 0.28+ |
| **Validation** | Pydantic | 2.0+ |
| **Database** | PostgreSQL | 18 |
| **Cache** | Redis | 8 |
| **Auth Server** | FreeRADIUS | 3.2 |
| **Container** | Docker | Latest |
| **Orchestration** | Docker Compose | 1.29+ |

## Repository Structure

```
nac-system/
├── proje-analizi/                 # Analysis documentation
│   ├── README.md                 # Main entry point
│   ├── 00-dosya-envanteri.md     # File inventory
│   ├── 01-servis-analizi.md      # Service analysis
│   ├── 02-network-baglanti.md    # Network topology
│   ├── 03-dockerfile-anatomisi.md
│   ├── 04-volume-veri-yonetimi.md
│   ├── 05-istek-akisi.md         # Request flows
│   ├── 06-python-mimarisi-ve-dosyalar.md
│   ├── 07-veritabani-freeradius.md
│   ├── 08-diger-dosyalar.md
│   ├── GLOSSARY.md               # Technical terms
│   └── diagrams/                 # Architecture diagrams
├── .github/README.md             # This file
└── [source code]                 # Original application source
```

## Document Statistics

| Metric | Value |
|--------|-------|
| Total Files Analyzed | 41 |
| Python Source Files | 14 |
| Docker Services | 5 |
| Database Tables | 6 |
| API Endpoints | 5+ |
| RADIUS Ports | 3 |
| Analysis Documents | 10 |
| Total Analysis Lines | 8,695 |
| Technical Terms Glossed | 100+ |

## Contributing

This is a documentation repository. To suggest improvements:
1. Locate the relevant `.md` file in `proje-analizi/`
2. Note the specific section and suggested change
3. Document the rationale for the update
4. Update cross-references in related files

## Related Resources

- [NAC System Architecture](proje-analizi/README.md)
- [Technical Glossary](proje-analizi/GLOSSARY.md)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [FreeRADIUS Official Docs](https://freeradius.org/)
- [PostgreSQL 18 Docs](https://www.postgresql.org/docs/18/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)

## Repository Information

- **Status:** Complete Analysis (Turkish & English, Pedagogical approach)
- **Last Updated:** 2026-03-23
- **Version:** 1.0.0
- **Visibility:** Private
- **Main Language:** Markdown (Türkçe/English)

---

**Generated with Claude Code (Anthropic's official Claude CLI)**

For main documentation, start with [`proje-analizi/README.md`](../proje-analizi/README.md)
