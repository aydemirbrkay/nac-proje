# Network Connectivity Map and Diagrams

## 1. Network Architecture Overview

### Docker Internal Network

**Network Type:** Bridge (isolated from host, internal communication only)
**Subnet:** 172.20.0.0/24 (255 available IPs)
**Gateway:** 172.20.0.1 (Docker default)
**Network Name:** nac-network (from docker-compose.yml)

**Purpose:** Internal service-to-service communication. Each container gets an IP like 172.20.0.2, 172.20.0.3, etc. This isolated network ensures:
- Containers can reach each other by service name (DNS resolution)
- Services are not exposed to external networks unless port-mapped
- Clear separation between internal communication and host access

**DNS Resolution:** Docker embedded DNS server (127.0.0.11:53 inside containers)
- Service name → IP address (automatic hostname lookup)
- Example: "postgres" resolves to 172.20.0.2
- Example: "nac-api" resolves to 172.20.0.4
- No manual /etc/hosts configuration needed


## 2. Service IP Assignments (Theoretical)

| Servis | Container Adı | Tahmini IP | Port (Internal) | Port (Host) | Protokol |
|--------|---|---|---|---|---|
| PostgreSQL | nac-postgres | 172.20.0.2 | 5432/TCP | 0.0.0.0:5432 | TCP |
| Redis | nac-redis | 172.20.0.3 | 6379/TCP | 0.0.0.0:6379 | TCP |
| FastAPI | nac-api | 172.20.0.4 | 8000/TCP | 0.0.0.0:8000 | TCP/HTTP |
| FreeRADIUS | nac-freeradius | 172.20.0.5 | 1812/UDP, 1813/UDP, 18120/UDP | 0.0.0.0:1812-1813, 0.0.0.0:18120 | UDP |

**Note:** IPs 172.20.0.x are theoretical and assigned dynamically by Docker. The important part is that services communicate using service names (postgres, redis, nac-api, nac-freeradius) which are automatically resolved by Docker DNS.


## 3. Service-to-Service Connections (Internal)

### 3.1 FastAPI → PostgreSQL

```
Source:      nac-api (172.20.0.4)
Destination: postgres:5432 (172.20.0.2:5432)
Protocol:    TCP
```

**Connection Details:**
- Connection String: `postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@postgres:5432/nac`
- Driver: asyncpg (non-blocking async driver for Python async/await)
- Pool Size: 10 connections + 5 overflow
- Timeout: Configurable (default 30 seconds)
- SSL Mode: Not configured (internal network only)

**Purpose:** FastAPI application queries user credentials, VLAN assignments, and accounting data from PostgreSQL.

**Communication Flow:**
1. FastAPI initiates TCP connection to "postgres:5432"
2. Docker DNS resolves "postgres" to 172.20.0.2
3. TCP connection established to 172.20.0.2:5432
4. Authentication: PostgreSQL username/password verified
5. Database: "nac" database selected
6. Query execution: SELECT/INSERT/UPDATE/DELETE

---

### 3.2 FastAPI → Redis

```
Source:      nac-api (172.20.0.4)
Destination: redis:6379 (172.20.0.3:6379)
Protocol:    TCP
```

**Connection Details:**
- Connection String: `redis://:${REDIS_PASSWORD}@redis:6379/0`
- Driver: redis-py (or aioredis for async)
- Cache Mode: Session storage, rate limiting, temporary data
- Database: Default 0 (no database selection for this config)
- Timeout: 5 seconds per operation

**Purpose:** FastAPI uses Redis for:
- Session caching (user authentication tokens)
- Rate limiting (requests per user/IP)
- Temporary request/response caching
- Distributed state (if multiple FastAPI instances exist)

**Communication Flow:**
1. FastAPI initiates TCP connection to "redis:6379"
2. Docker DNS resolves "redis" to 172.20.0.3
3. TCP connection established to 172.20.0.3:6379
4. Authentication: Password verified
5. Commands: SET, GET, INCR, EXPIRE, etc.

---

### 3.3 FreeRADIUS → FastAPI (REST)

```
Source:      nac-freeradius (172.20.0.5)
Destination: nac-api:8000 (172.20.0.4:8000)
Protocol:    HTTP/REST
Driver:      rlm_rest (FreeRADIUS REST module)
```

**Connection Details:**
- Base URL: `http://nac-api:8000`
- HTTP Method: POST
- Content-Type: application/json
- Timeout: 10 seconds
- Connection Pool: 5-20 persistent connections
- Retries: Configurable (default 2)

**Endpoints:**

| Endpoint | Method | Purpose | Request Body |
|----------|--------|---------|--------------|
| `/auth` | POST | Authenticate user, check credentials | `{"username": "user", "password": "pass"}` |
| `/authorize` | POST | Check authorization, assign VLAN | `{"username": "user", "nas_ip": "192.168.1.1"}` |
| `/accounting` | POST | Log session events (start/update/stop) | `{"username": "user", "acct_status": "Start"}` |

**Purpose:** FreeRADIUS delegates authentication and authorization decisions to FastAPI REST API instead of using traditional RADIUS backend (SQL, LDAP).

**Communication Flow:**
1. FreeRADIUS receives Access-Request from NAS
2. FreeRADIUS parses username/password from RADIUS packet
3. FreeRADIUS constructs HTTP POST request to http://nac-api:8000/auth
4. Docker DNS resolves "nac-api" to 172.20.0.4
5. HTTP request sent to 172.20.0.4:8000/auth
6. FastAPI processes request, queries PostgreSQL/Redis
7. FastAPI returns JSON response: `{"result": "Accept", "vlan": "100"}`
8. FreeRADIUS parses response and generates RADIUS Access-Accept/Reject packet
9. FreeRADIUS sends RADIUS response back to NAS

---

### 3.4 Optional: PostgreSQL → (No direct external connections)

PostgreSQL is only accessed by FastAPI. It does not initiate connections to other services. Other containers may connect to it for:
- Database management tools (during development)
- Backup/restore utilities
- Monitoring agents


## 4. External (Host) Connections

### 4.1 PostgreSQL (Host Port)

```
Host:        0.0.0.0:5432
Protocol:    TCP
Visibility:  Exposed to host and external clients
```

**Purpose:** Development and administration access
- Direct database queries using psql CLI
- GUI tools (DBeaver, pgAdmin)
- Backup/restore operations
- Manual schema modifications

**Port Mapping:**
- Container: 172.20.0.2:5432 (internal)
- Host: 0.0.0.0:5432 (external)
- Access: `psql -h localhost -p 5432 -U postgres -d nac`

**Security Note:** This port exposes the entire database. In production, should be removed or restricted to localhost only.

---

### 4.2 Redis (Host Port)

```
Host:        0.0.0.0:6379
Protocol:    TCP
Visibility:  Exposed to host and external clients
```

**Purpose:** Cache monitoring and debugging
- redis-cli access from host
- Monitoring dashboards
- Cache inspection
- Session management

**Port Mapping:**
- Container: 172.20.0.3:6379 (internal)
- Host: 0.0.0.0:6379 (external)
- Access: `redis-cli -h localhost -p 6379 -a password`

**Security Note:** This port exposes all cached data. In production, should be removed or restricted to localhost only.

---

### 4.3 FastAPI (Host Port)

```
Host:        0.0.0.0:8000
Protocol:    HTTP/REST
Visibility:  Exposed to host and external clients
```

**Purpose:** Primary API endpoint access
- Client applications connect here
- Swagger UI documentation
- ReDoc interactive documentation
- Health check endpoint

**Key Endpoints:**
- `GET /health` — Health check (returns 200 OK)
- `POST /auth` — Authentication endpoint
- `POST /authorize` — Authorization endpoint
- `POST /accounting` — Accounting endpoint
- `GET /docs` — Swagger UI
- `GET /redoc` — ReDoc documentation

**Port Mapping:**
- Container: 172.20.0.4:8000 (internal)
- Host: 0.0.0.0:8000 (external)
- Access: `curl http://localhost:8000/health`

**Production Considerations:**
- Run behind reverse proxy (nginx, HAProxy)
- Implement TLS/HTTPS
- Restrict access by IP or VPN
- Use load balancer for high availability

---

### 4.4 FreeRADIUS (Host Ports - UDP)

```
Host:        0.0.0.0
Protocols:   UDP (1812, 1813, 18120)
Visibility:  Exposed to network
```

**RADIUS Protocol Breakdown:**

| Port | Purpose | Packet Type | Direction |
|------|---------|-------------|-----------|
| 1812 | Authentication | Access-Request / Access-Accept | Bidirectional |
| 1813 | Accounting | Accounting-Request / Accounting-Response | Bidirectional |
| 18120 | CoA (Change of Authorization) | CoA-Request / CoA-ACK | Bidirectional |

**Port Mapping:**
- Container: 172.20.0.5:1812/UDP, 1812/UDP, 18120/UDP (internal)
- Host: 0.0.0.0:1812/UDP, 0.0.0.0:1813/UDP, 0.0.0.0:18120/UDP (external)

**Typical Clients (External):**
- Network switches (Cisco, Arista, Juniper)
- WiFi access points (Ruckus, Ubiquiti, Aruba)
- VPN gateways (Fortinet, Palo Alto, Juniper)
- Supplicants (802.1X client devices)

**Access Control:**
- FreeRADIUS clients.conf defines which NAS IP addresses are allowed
- Shared secret (pre-shared key) required for authentication
- Example: `client 192.168.1.1/32 { secret = testing123; }`

**Security Considerations:**
- UDP is connectionless (no encryption by default)
- Shared secret must be strong and unique per NAS
- Consider RADIUS over TLS (RadSec) for sensitive environments
- Implement network firewall rules to restrict RADIUS access

---

## 5. RADIUS Protocol Flow (Detailed Sequence Diagram)

### 5.1 Authentication Flow (Access-Request → Access-Accept)

```
[External NAS/Switch]
         |
         | RADIUS UDP:1812
         | Access-Request(username=bob, password=secret)
         |
         v
[FreeRADIUS on Docker]
    (172.20.0.5:1812/UDP)
         |
         | Parse Access-Request packet
         | Extract: username, password, nas_ip, etc.
         |
         v
[Construct HTTP POST request]
   POST http://nac-api:8000/auth
   Content-Type: application/json
   {
     "username": "bob",
     "password": "secret",
     "nas_ip": "192.168.1.1",
     "request_id": "12345"
   }
         |
         | Docker DNS: nac-api → 172.20.0.4
         | TCP connection to 172.20.0.4:8000
         |
         v
[FastAPI on Docker]
    (172.20.0.4:8000)
         |
         | POST /auth handler
         | Check Redis cache: redis://:password@redis:6379
         | Query database: postgresql+asyncpg://...@postgres:5432/nac
         |
         v
[PostgreSQL]
    (172.20.0.2:5432)
         |
         | SELECT * FROM radcheck WHERE username='bob'
         | Return: {password_hash, enabled, vlan, ...}
         |
         v
[FastAPI validation]
   Compare password_hash with provided password
   Generate response:
   {
     "result": "Accept",
     "vlan": "100",
     "filter_id": "standard",
     "session_id": "sess_xyz"
   }
         |
         | Cache result in Redis for 5 minutes
         |
         v
[FreeRADIUS]
   Parse HTTP 200 response
   Extract: vlan="100", filter_id="standard"
   Construct RADIUS packet:
   Access-Accept(
     vlan=100,
     filter_id=standard,
     session_id=sess_xyz
   )
         |
         | UDP packet back to NAS
         |
         v
[NAS/Switch]
   Receives Access-Accept
   User authentication successful
   VLAN 100 is assigned
   Port configured accordingly
```

### 5.2 Accounting Flow (Session Logging)

```
[NAS/Switch]
         |
         | RADIUS UDP:1813
         | Accounting-Request(status=Start, username=bob, session_id=sess_xyz)
         |
         v
[FreeRADIUS]
    (172.20.0.5:1813/UDP)
         |
         | Parse Accounting-Request
         | Extract: acct_status, username, session_id, nas_ip, etc.
         |
         v
[Construct HTTP POST]
   POST http://nac-api:8000/accounting
   {
     "username": "bob",
     "acct_status": "Start",
     "session_id": "sess_xyz",
     "nas_ip": "192.168.1.1",
     "timestamp": "2024-03-23T10:30:00Z"
   }
         |
         v
[FastAPI]
    POST /accounting handler
         |
         | INSERT INTO radacct (username, session_id, acct_status, start_time)
         | UPDATE Redis: SET session:sess_xyz:active 1 EX 86400
         |
         v
[PostgreSQL & Redis]
   Save accounting record
   Mark session as active
         |
         v
[FreeRADIUS]
   Return HTTP 200 OK
         |
         v
[FreeRADIUS to NAS]
   Accounting-Response (OK)
         |
         v
[NAS continues monitoring session]
   ...periodic Accounting-Update packets...
         |
         | Eventually:
         | Accounting-Request(status=Stop, session_time=3600)
         |
         v
[FreeRADIUS → FastAPI]
   POST /accounting
   {"acct_status": "Stop", "session_time": 3600}
         |
         v
[FastAPI → PostgreSQL]
   UPDATE radacct SET stop_time=NOW(), stop_reason='...'
   WHERE session_id='sess_xyz'
         |
         v
[FastAPI → Redis]
   DEL session:sess_xyz:active
         |
         v
Session terminated, accounting complete
```

### 5.3 CoA (Change of Authorization) Flow

```
[Policy Engine or Admin Action]
    Need to change user VLAN mid-session
         |
         | Invoke CoA via FastAPI admin endpoint
         | POST /coax/change
         | {"session_id": "sess_xyz", "new_vlan": "200"}
         |
         v
[FastAPI]
   Lookup session in Redis
   Determine NAS IP and session details
   Construct RADIUS CoA-Request packet:
   {
     session_id: "sess_xyz",
     vlan: "200"
   }
         |
         | UDP:18120 to NAS IP (192.168.1.1)
         |
         v
[NAS/Switch]
   Receives CoA-Request (UDP:18120)
   Validates RADIUS shared secret
   Applies new VLAN assignment
   Sends CoA-ACK back to FreeRADIUS:18120
         |
         v
[FreeRADIUS]
   Receives CoA-ACK
   Reports success to FastAPI
         |
         v
[FastAPI]
   Updates session record in Redis and PostgreSQL
   User now on VLAN 200 immediately
```


## 6. Network Diagram (Mermaid)

```mermaid
graph TB
    subgraph external["External/Host Network"]
        NAS["🖧 Network Switch<br/>(External Client)<br/>192.168.1.x"]
        Admin["👤 Administrator<br/>(Host Machine)<br/>0.0.0.0"]
        Supplicant["📱 802.1X Supplicant<br/>(Laptop/Phone)<br/>192.168.1.x"]
    end

    subgraph host["Docker Host (0.0.0.0)"]
        direction TB
        HostPort1["Host Port Mapping<br/>0.0.0.0:1812/UDP → 172.20.0.5:1812"]
        HostPort2["Host Port Mapping<br/>0.0.0.0:1813/UDP → 172.20.0.5:1813"]
        HostPort3["Host Port Mapping<br/>0.0.0.0:18120/UDP → 172.20.0.5:18120"]
        HostPort4["Host Port Mapping<br/>0.0.0.0:8000 → 172.20.0.4:8000"]
        HostPort5["Host Port Mapping<br/>0.0.0.0:5432 → 172.20.0.2:5432"]
        HostPort6["Host Port Mapping<br/>0.0.0.0:6379 → 172.20.0.3:6379"]
    end

    subgraph network["🌐 Docker Bridge Network<br/>172.20.0.0/24"]
        Radius["📡 FreeRADIUS<br/>nac-freeradius<br/>172.20.0.5<br/>🔌 1812, 1813, 18120/UDP<br/>🌐 DNS: 127.0.0.11:53"]
        API["🔌 FastAPI<br/>nac-api<br/>172.20.0.4<br/>8000/TCP<br/>🌐 DNS: 127.0.0.11:53"]
        PG["🗄️ PostgreSQL<br/>nac-postgres<br/>172.20.0.2<br/>5432/TCP<br/>🌐 DNS: 127.0.0.11:53"]
        Redis["⚡ Redis<br/>nac-redis<br/>172.20.0.3<br/>6379/TCP<br/>🌐 DNS: 127.0.0.11:53"]
    end

    %% External connections
    NAS -->|RADIUS/UDP:1812<br/>Access-Request/Accept| HostPort1
    NAS -->|RADIUS/UDP:1813<br/>Accounting| HostPort2
    NAS -->|CoA/UDP:18120<br/>Change VLAN| HostPort3
    Supplicant -->|EAP over Ethernet<br/>to NAS| NAS
    Admin -->|HTTP REST<br/>curl, postman| HostPort4
    Admin -->|psql CLI| HostPort5
    Admin -->|redis-cli| HostPort6

    %% Host port mapping to internal
    HostPort1 --> Radius
    HostPort2 --> Radius
    HostPort3 --> Radius
    HostPort4 --> API
    HostPort5 --> PG
    HostPort6 --> Redis

    %% Internal service communication
    Radius -->|HTTP REST POST<br/>http://nac-api:8000/auth<br/>http://nac-api:8000/authorize<br/>http://nac-api:8000/accounting| API
    API -->|TCP Connection<br/>postgresql+asyncpg://...<br/>SELECT/INSERT/UPDATE| PG
    API -->|TCP Connection<br/>redis://:password@redis:6379<br/>SET/GET/INCR| Redis

    %% DNS resolution (implicit)
    Radius -.->|Docker DNS 127.0.0.11:53<br/>nac-api → 172.20.0.4| API
    API -.->|Docker DNS<br/>postgres → 172.20.0.2| PG
    API -.->|Docker DNS<br/>redis → 172.20.0.3| Redis

    %% Legend
    style network fill:#e1f5ff
    style external fill:#fff3e0
    style host fill:#f3e5f5
```

### Diagram Explanation

**External/Host Network (Orange):**
- NAS (Network Switch): Initiates RADIUS authentication/accounting
- Supplicant (Client Device): Initiates 802.1X handshake with NAS, which proxies to RADIUS
- Administrator: Uses host ports for direct access to services (development/debugging)

**Docker Host (Purple):**
- Port mappings bridge external clients to internal containers
- All UDP/TCP connections on 0.0.0.0 are port-forwarded to container IPs

**Docker Bridge Network (Light Blue):**
- Isolated 172.20.0.0/24 network
- Services communicate by service name (DNS resolution)
- FreeRADIUS is the ingress point for external RADIUS clients
- FastAPI orchestrates all business logic
- PostgreSQL stores permanent data
- Redis caches temporary data

**Connection Types:**
- Solid arrows: Active data flow (TCP/UDP)
- Dotted arrows: DNS resolution (implicit, happens automatically)


## 7. Connection String Reference

### 7.1 FastAPI → PostgreSQL

**Connection String Format:**
```
postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@postgres:5432/nac
```

**Component Breakdown:**

| Component | Value | Explanation |
|-----------|-------|-------------|
| Protocol | postgresql+asyncpg | PostgreSQL with asyncpg async driver |
| Username | postgres | Default PostgreSQL superuser |
| Password | ${POSTGRES_PASSWORD} | Environment variable (from docker-compose.yml) |
| Host | postgres | Service name (Docker DNS resolves to 172.20.0.2) |
| Port | 5432 | PostgreSQL default port |
| Database | nac | NAC application database |

**Python Usage:**
```python
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = "postgresql+asyncpg://postgres:password@postgres:5432/nac"
engine = create_async_engine(DATABASE_URL, pool_size=10, max_overflow=5)
```

**Manual Connection (from host):**
```bash
psql -h localhost -p 5432 -U postgres -d nac
# Then enter password when prompted
```

**Connection Pool Configuration:**
- Min Pool Size: 10 connections (always open)
- Max Overflow: 5 (additional temporary connections)
- Max Total: 15 concurrent connections
- Pool Timeout: 30 seconds
- Pool Recycle: 3600 seconds (1 hour)

---

### 7.2 FastAPI → Redis

**Connection String Format:**
```
redis://:${REDIS_PASSWORD}@redis:6379/0
```

**Component Breakdown:**

| Component | Value | Explanation |
|-----------|-------|-------------|
| Protocol | redis | Redis protocol |
| Username | (empty) | Redis typically uses password-only auth |
| Password | ${REDIS_PASSWORD} | Environment variable (from docker-compose.yml) |
| Host | redis | Service name (Docker DNS resolves to 172.20.0.3) |
| Port | 6379 | Redis default port |
| Database | 0 | Default database (0-15 available) |

**Python Usage (aioredis):**
```python
import aioredis

REDIS_URL = "redis://:password@redis:6379/0"
redis_client = await aioredis.from_url(REDIS_URL)
await redis_client.set("key", "value", ex=300)
```

**Manual Connection (from host):**
```bash
redis-cli -h localhost -p 6379 -a password
# Commands: GET key, SET key value, INCR counter, etc.
```

**Cache Usage:**
- Session tokens: `session:{session_id}` → TTL 3600s
- Rate limits: `ratelimit:{user_id}:{endpoint}` → TTL 60s
- Authentication cache: `auth_cache:{username}` → TTL 300s
- Temporary data: Any custom key-value pairs

---

### 7.3 FreeRADIUS → FastAPI (REST)

**Base URL:**
```
http://nac-api:8000
```

**Component Breakdown:**

| Component | Value | Explanation |
|-----------|-------|-------------|
| Protocol | http | HTTP (not HTTPS, internal network only) |
| Host | nac-api | Service name (Docker DNS resolves to 172.20.0.4) |
| Port | 8000 | FastAPI default uvicorn port |

**Endpoints:**

#### Authentication (`/auth`)
```
POST http://nac-api:8000/auth
Content-Type: application/json

Request:
{
  "username": "alice",
  "password": "secret123",
  "nas_ip": "192.168.1.1",
  "nas_port": 0,
  "nas_port_type": "Ethernet",
  "request_id": "12345"
}

Response (Success):
{
  "result": "Accept",
  "vlan": "100",
  "filter_id": "standard",
  "session_duration": 86400,
  "reply_message": "Authentication successful"
}

Response (Failure):
{
  "result": "Reject",
  "reply_message": "Invalid credentials"
}
```

#### Authorization (`/authorize`)
```
POST http://nac-api:8000/authorize
Content-Type: application/json

Request:
{
  "username": "alice",
  "nas_ip": "192.168.1.1",
  "nas_port": 5,
  "session_id": "sess_xyz"
}

Response:
{
  "result": "Accept",
  "vlan": "100",
  "acl_name": "standard_users",
  "idle_timeout": 3600,
  "session_timeout": 86400
}
```

#### Accounting (`/accounting`)
```
POST http://nac-api:8000/accounting
Content-Type: application/json

Request (Start):
{
  "acct_status": "Start",
  "username": "alice",
  "session_id": "sess_xyz",
  "nas_ip": "192.168.1.1",
  "nas_port": 5,
  "acct_input_octets": 0,
  "acct_output_octets": 0,
  "timestamp": "2024-03-23T10:30:00Z"
}

Request (Update):
{
  "acct_status": "Interim-Update",
  "username": "alice",
  "session_id": "sess_xyz",
  "acct_input_octets": 1048576,
  "acct_output_octets": 2097152,
  "acct_session_time": 300,
  "timestamp": "2024-03-23T10:35:00Z"
}

Request (Stop):
{
  "acct_status": "Stop",
  "username": "alice",
  "session_id": "sess_xyz",
  "acct_input_octets": 5242880,
  "acct_output_octets": 10485760,
  "acct_session_time": 3600,
  "acct_terminate_cause": "User-Request",
  "timestamp": "2024-03-23T11:30:00Z"
}

Response (all):
{
  "result": "Accept",
  "message": "Accounting received"
}
```

**HTTP Status Codes:**
- 200 OK: Request processed successfully
- 400 Bad Request: Invalid JSON or missing fields
- 401 Unauthorized: Authentication failed
- 500 Internal Server Error: Server-side error

**Connection Parameters:**
- Timeout: 10 seconds per request
- Retry: Up to 2 automatic retries on failure
- Keep-Alive: Persistent HTTP connections (5-20 concurrent)
- User-Agent: FreeRADIUS rlm_rest module

---

### 7.4 Manual Connection Strings (From Host for Debugging)

**PostgreSQL (psql):**
```bash
psql -h localhost -p 5432 -U postgres -d nac
psql -h 127.0.0.1 -p 5432 -U postgres -d nac
# Password: (from docker-compose.yml POSTGRES_PASSWORD)
```

**Redis (redis-cli):**
```bash
redis-cli -h localhost -p 6379 -a password
redis-cli -h 127.0.0.1 -p 6379 -a password
# Select database: SELECT 0
# Common commands: GET key, SET key value, KEYS pattern
```

**FastAPI (curl/HTTP):**
```bash
# Health check
curl http://localhost:8000/health

# Authentication
curl -X POST http://localhost:8000/auth \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "secret"}'

# Swagger UI
open http://localhost:8000/docs

# ReDoc
open http://localhost:8000/redoc
```

**FreeRADIUS (radtest from external):**
```bash
# Test RADIUS authentication from external machine
radtest alice secret 192.168.1.100 0 testing123
# Parameters: username password nas_ip nas_port shared_secret
# Returns: Access-Accept or Access-Reject
```


## 8. Network Isolation & Security

### 8.1 Internal Network Isolation

**Docker Bridge Network (172.20.0.0/24):**
- Only containers connected to this network can communicate
- Completely isolated from host network (unless port-mapped)
- External clients cannot directly access internal IPs (172.20.x.x)
- Containers cannot reach services on host network without special configuration

**Practical Implications:**
```
External NAS (192.168.1.1)
   ├─ Can reach: FreeRADIUS via UDP:1812 (port-mapped)
   ├─ Can reach: FastAPI via TCP:8000 (port-mapped)
   └─ CANNOT reach: PostgreSQL directly (internal-only, despite port mapping)
        ↳ Can only reach via FastAPI

Admin on host (0.0.0.0)
   ├─ Can reach: All services via port-mapped ports
   ├─ Can reach: Container IPs directly IF --network host used
   └─ CANNOT reach: Container IPs (172.20.x.x) without port mapping
```

---

### 8.2 Port Mapping Security Analysis

| Service | Port | Host | Container | Risk Level | Recommendation |
|---------|------|------|-----------|-----------|---|
| PostgreSQL | 5432 | 0.0.0.0:5432 | 172.20.0.2:5432 | 🔴 High | Remove in production, use only localhost:5432 |
| Redis | 6379 | 0.0.0.0:6379 | 172.20.0.3:6379 | 🔴 High | Remove in production, internal-only |
| FastAPI | 8000 | 0.0.0.0:8000 | 172.20.0.4:8000 | 🟡 Medium | Keep but restrict to reverse proxy subnet |
| FreeRADIUS | 1812/UDP | 0.0.0.0:1812 | 172.20.0.5:1812 | 🟡 Medium | Keep (necessary), implement firewall rules |
| FreeRADIUS | 1813/UDP | 0.0.0.0:1813 | 172.20.0.5:1813 | 🟡 Medium | Keep (necessary), implement firewall rules |
| FreeRADIUS | 18120/UDP | 0.0.0.0:18120 | 172.20.0.5:18120 | 🟡 Medium | Keep (necessary), implement firewall rules |

**Explanation:**

🔴 **High Risk: PostgreSQL & Redis**
- Exposing database directly is dangerous
- No authentication for Redis (password only, not encryption)
- No TLS for PostgreSQL (plaintext communication)
- Full database access available to anyone who can reach port

🟡 **Medium Risk: FastAPI**
- API layer provides some protection (no direct database access)
- Still should be behind reverse proxy in production
- HTTPS/TLS recommended for external connections

🟡 **Medium Risk: FreeRADIUS UDP**
- Necessary for RADIUS protocol to work
- However:
  - Must validate NAS IP (clients.conf)
  - Must use strong shared secrets
  - Should restrict firewall access to known NAS IPs

---

### 8.3 Production Security Recommendations

**1. Remove Unnecessary Port Mappings:**
```yaml
# BEFORE (Development)
services:
  postgres:
    ports:
      - "5432:5432"  # ❌ Expose to world
  redis:
    ports:
      - "6379:6379"  # ❌ Expose to world

# AFTER (Production)
services:
  postgres:
    # ✅ No host port mapping, internal-only
  redis:
    # ✅ No host port mapping, internal-only
    # Only FastAPI can reach via internal network
```

**2. Restrict FastAPI Port:**
```yaml
services:
  api:
    ports:
      - "127.0.0.1:8000:8000"  # ✅ Only localhost
      # OR in production:
      - "172.20.0.1:8000:8000"  # ✅ Only reverse proxy subnet
```

**3. Firewall Rules for RADIUS:**
```bash
# Allow RADIUS from specific NAS devices
ufw allow from 192.168.1.1 to any port 1812 proto udp
ufw allow from 192.168.1.2 to any port 1812 proto udp
ufw allow from 192.168.1.3 to any port 1813 proto udp
ufw allow from 192.168.1.3 to any port 18120 proto udp

# Block everything else
ufw default deny incoming
```

**4. TLS/HTTPS for REST:**
```python
# FreeRADIUS → FastAPI should use HTTPS in production
# Requires:
# - Self-signed or CA-signed certificate
# - Mutual TLS authentication
# - rlm_rest configuration update

# http://nac-api:8000  (Development)
# https://nac-api:8000 (Production, with cert validation)
```

**5. Database Encryption:**
```sql
-- Enable SSL mode for PostgreSQL
-- Update connection string:
-- postgresql+asyncpg://user:pass@postgres:5432/nac?ssl=require
```

**6. Redis Encrypted Connections:**
```
-- Upgrade to Redis with TLS support
-- Update connection string:
-- redis://:password@redis:6379/0?ssl=True&ssl_cert_reqs=required
```

**7. Network Policy (if Kubernetes):**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: nac-network-policy
spec:
  podSelector:
    matchLabels:
      app: nac-postgres
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: nac-api
      ports:
        - protocol: TCP
          port: 5432
  # Deny all other ingress traffic
```

---

## 9. DNS Resolution Details

### 9.1 Docker Embedded DNS

**DNS Server Address:** 127.0.0.11:53 (inside each container)

**How Docker DNS Works:**

```
[Container A]
    |
    | $ getaddrinfo("postgres")
    |
    v
[Query 127.0.0.11:53]
    |
    | Query: "postgres" A record
    |
    v
[Docker Daemon]
    |
    | Lookup: Find container named "postgres" on same network
    | Check: nac-network bridge network
    | Found: Container nac-postgres with IP 172.20.0.2
    |
    v
[Return DNS Response]
    |
    | Type A record: postgres → 172.20.0.2
    |
    v
[Container A receives IP]
    |
    | Now knows: postgres = 172.20.0.2
    | Proceeds with TCP connection to 172.20.0.2:5432
```

---

### 9.2 DNS Resolution Examples

**FastAPI connecting to PostgreSQL:**
```python
# Inside nac-api container
connection_string = "postgresql+asyncpg://postgres:password@postgres:5432/nac"

# What happens:
# 1. Python gethostbyname("postgres")
# 2. Query 127.0.0.11:53
# 3. Docker returns 172.20.0.2
# 4. Connect to 172.20.0.2:5432
```

**FreeRADIUS connecting to FastAPI:**
```c
// Inside nac-freeradius container
http_uri = "http://nac-api:8000/auth"

// What happens:
// 1. DNS lookup: nac-api
// 2. Query 127.0.0.11:53
// 3. Docker returns 172.20.0.4
// 4. HTTP POST to 172.20.0.4:8000/auth
```

---

### 9.3 DNS Hostname Mappings

| Service Name | Container Name | Network | Internal IP | Resolves To |
|--------------|---|---|---|---|
| postgres | nac-postgres | nac-network | 172.20.0.2 | postgres.nac-network (FQDN) |
| redis | nac-redis | nac-network | 172.20.0.3 | redis.nac-network (FQDN) |
| nac-api | nac-api | nac-network | 172.20.0.4 | nac-api.nac-network (FQDN) |
| nac-freeradius | nac-freeradius | nac-network | 172.20.0.5 | nac-freeradius.nac-network (FQDN) |

**Note:** Docker's DNS supports both short names (postgres) and fully qualified names (postgres.nac-network). Short names are typically used in connection strings.

---

### 9.4 DNS Caching

**Container DNS Caching:**
- Some containers may cache DNS results locally
- Default TTL: Varies by DNS resolver library
- Python requests: Usually 60+ seconds
- GoLang net: Golangtypically caches aggressively

**Implications:**
- If a container IP changes, old IP may still be cached
- Solution: Docker restart handles cache invalidation
- For container rescheduling (Kubernetes), use service discovery updates

---

### 9.5 Troubleshooting DNS Issues

**Container cannot resolve service name:**
```bash
# Inside container
nslookup postgres
dig postgres
ping postgres

# If fails:
# - Check: Is service running? (docker ps)
# - Check: Are both on same network? (docker network inspect nac-network)
# - Check: Service name spelled correctly (case-sensitive? No, Docker DNS is case-insensitive)
```

**Stale DNS cache:**
```bash
# Container cached old IP
# Solution: Restart container or restart Docker daemon
docker restart nac-api
```

**DNS query debugging:**
```bash
# Inside container with strace
strace -e openat,connect curl postgres:5432

# See DNS lookups:
# connect(5, {sa_family=AF_INET, sin_port=htons(53), sin_addr=inet_addr("127.0.0.11")}, 16) = 0
# write(5, "xxxxxxxxxx", 29) = 29
# This shows DNS query to 127.0.0.11:53
```


## 10. Troubleshooting Connection Issues

### 10.1 FastAPI Cannot Reach PostgreSQL

**Symptoms:**
- FastAPI logs: `ConnectionRefusedError: [Errno 111] Connection refused`
- Application hangs on startup waiting for database

**Diagnosis Checklist:**

| Step | Command | Expected Output |
|------|---------|---|
| 1. Check if postgres running | `docker-compose ps` | postgres RUNNING (not EXIT) |
| 2. Check postgres health | `docker-compose logs postgres` | "database system is ready" |
| 3. Check if on same network | `docker network inspect nac-network` | postgres and nac-api both listed |
| 4. Check connection string | In api code | `postgresql+asyncpg://postgres:...@postgres:5432/nac` |
| 5. Test DNS resolution | `docker exec nac-api ping postgres` | Should see ICMP responses or "resolve OK" |
| 6. Test TCP connection | `docker exec nac-api curl postgres:5432` | Should hang or show "PostgreSQL welcome" |
| 7. Check credentials | docker-compose.yml | POSTGRES_PASSWORD matches connection string |
| 8. Check database name | SELECT datname FROM pg_database | "nac" database exists |

**Common Issues & Fixes:**

**Issue 1: Connection string has wrong hostname**
```python
# ❌ Wrong
DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/nac"
# localhost inside container = container itself, not host!

# ✅ Correct
DATABASE_URL = "postgresql+asyncpg://postgres:password@postgres:5432/nac"
# "postgres" = service name, DNS resolves to 172.20.0.2
```

**Issue 2: PostgreSQL not initialized**
```bash
# Symptoms: Connection succeeds but queries fail
# Fix: Delete volume and recreate
docker-compose down -v
docker-compose up postgres
# Wait for "database system is ready to accept connections"
```

**Issue 3: Password mismatch**
```yaml
# docker-compose.yml
services:
  postgres:
    environment:
      POSTGRES_PASSWORD: mypassword123  # ← This value

# Connection string must use same password
DATABASE_URL = "postgresql+asyncpg://postgres:mypassword123@postgres:5432/nac"
```

**Issue 4: Pool exhaustion**
```
Symptoms: "Too many connections" error after X requests
Fix: Increase pool size in connection string
CONNECTION_POOL_SIZE = 20  # Increase from 10
CONNECTION_POOL_OVERFLOW = 10  # Increase from 5
```

---

### 10.2 FreeRADIUS Cannot Reach FastAPI

**Symptoms:**
- FreeRADIUS logs: `[rlm_rest] REST request failed: Connection timeout`
- External NAS tries to authenticate, gets no response from RADIUS

**Diagnosis Checklist:**

| Step | Command | Expected Output |
|------|---------|---|
| 1. Check if FastAPI running | `docker-compose ps` | nac-api RUNNING (not EXIT) |
| 2. Check FastAPI health | `docker-compose logs api` | Server listening on 0.0.0.0:8000 |
| 3. Check if on same network | `docker network inspect nac-network` | nac-api and nac-freeradius both listed |
| 4. Test DNS resolution | `docker exec nac-freeradius ping nac-api` | Should get ping responses |
| 5. Test HTTP connectivity | `docker exec nac-freeradius curl http://nac-api:8000/health` | Should return 200 OK |
| 6. Check rlm_rest config | `/etc/freeradius/mods-enabled/rest` | uri = "http://nac-api:8000" |
| 7. Check timeout | `/etc/freeradius/mods-enabled/rest` | timeout = 10 |
| 8. Enable FreeRADIUS debug | FreeRADIUS startup | FreeRADIUS -X (debug mode) |

**Common Issues & Fixes:**

**Issue 1: REST module using incorrect URI**
```python
# /etc/freeradius/mods-enabled/rest
rest {
    uri = "http://nac-api:8000"  # ← Must be http://, not https://
    timeout = 10
    ...
}

# Check: ping nac-api from FreeRADIUS container
docker exec nac-freeradius ping nac-api
# Should resolve to 172.20.0.4
```

**Issue 2: FastAPI /auth endpoint not implemented**
```python
# api/main.py must have:
@app.post("/auth")
async def authenticate(username: str, password: str):
    # Validate credentials
    return {"result": "Accept", "vlan": "100"}

# If missing:
# FreeRADIUS receives HTTP 404
# Logs: "REST request returned code 404"
```

**Issue 3: FastAPI cannot reach database (chain failure)**
```
FreeRADIUS → FastAPI ✓ (HTTP 200 OK)
FastAPI → PostgreSQL ✗ (Connection failed)
Result: FastAPI returns HTTP 500 error
FreeRADIUS sees: "Internal Server Error"
User sees: Access-Reject (no response)

Fix: Ensure FastAPI can reach PostgreSQL first (see section 10.1)
```

**Issue 4: Request timeout**
```
FreeRADIUS waits 10 seconds (default timeout)
FastAPI processing takes 15 seconds (slow query)
Result: FreeRADIUS times out before FastAPI responds

Fix:
- Increase timeout in rlm_rest config: timeout = 30
- Optimize slow queries in FastAPI
- Add database indexes
- Enable Redis caching
```

**Debug Enable:**
```bash
# Run FreeRADIUS in debug mode to see REST calls
docker exec -it nac-freeradius freeradius -X
# Output shows:
# [rlm_rest] POST request to "http://nac-api:8000/auth"
# [rlm_rest] REST response code: 200
# [rlm_rest] Processed: {"result": "Accept"}
```

---

### 10.3 External NAS Cannot Reach RADIUS Server

**Symptoms:**
- External switch/AP tries to authenticate
- Gets timeout (no response from RADIUS server)
- Authentication fails for all users

**Diagnosis Checklist:**

| Step | Command | Expected Output |
|------|---------|---|
| 1. Check FreeRADIUS running | `docker-compose ps` | nac-freeradius RUNNING |
| 2. Check FreeRADIUS logs | `docker-compose logs freeradius` | "listening on" port 1812 |
| 3. Check NAS IP in clients.conf | `docker exec nac-freeradius cat /etc/freeradius/clients.conf` | `client 192.168.1.1/32 { secret = testing123; }` |
| 4. Verify NAS IP correct | NAS config page | NAS IP = 192.168.1.1 |
| 5. Test from external | `radtest user password nas_ip 0 secret` | Access-Accept or Access-Reject |
| 6. Test from host | On docker host: `radtest user password 127.0.0.1 0 secret` | Should work |
| 7. Check firewall rules | `sudo ufw status` | 1812/UDP, 1813/UDP allowed |
| 8. Check Docker port mapping | `docker-compose ps` | Port mapping shows 1812/UDP →→ container |

**Common Issues & Fixes:**

**Issue 1: NAS IP not authorized in clients.conf**
```
Symptoms: All NAS devices get "Client is unknown"
Solution: Add NAS IP to /etc/freeradius/clients.conf

# ❌ Wrong
# (empty clients.conf or NAS IP not listed)

# ✅ Correct
client 192.168.1.1/32 {
    secret = testing123
    shortname = switch-1
    nastype = cisco
}
```

**Issue 2: Shared secret mismatch**
```
NAS config: RADIUS secret = "MySecret123"
clients.conf: secret = "DifferentSecret"

Result: RADIUS authentication fails with "Bad authenticator"

Solution: Make sure secret matches exactly (case-sensitive)
```

**Issue 3: Firewall blocking UDP:1812**
```bash
# Test from external machine
radtest user password 192.168.1.100 0 testing123
# No response = firewall is likely blocking

# Fix: Open firewall
sudo ufw allow 1812/udp
sudo ufw allow 1813/udp
sudo firewall-cmd --permanent --add-port=1812/udp  # RedHat/CentOS
```

**Issue 4: Docker port mapping not working**
```bash
# Check if port is listening on host
netstat -tuln | grep 1812
# If no output, port not exposed

# docker-compose.yml should have:
services:
  freeradius:
    ports:
      - "1812:1812/udp"
      - "1813:1813/udp"
      - "18120:18120/udp"

# Without this, external clients cannot reach
```

**Issue 5: FreeRADIUS binding to 127.0.0.1 instead of 0.0.0.0**
```
Symptoms: NAS on same host can reach, NAS on network cannot

Check: /etc/freeradius/sites-enabled/default
Should have: listen { type = auth; address = 0.0.0.0; port = 1812; }

❌ Wrong: address = 127.0.0.1
✅ Correct: address = 0.0.0.0
```

**Test with radtest:**
```bash
# From external machine with radtest installed:
radtest -t udp username password 192.168.1.100 0 testing123

# Expected output (Access-Accept):
# Sent Access-Request Id 123 from 192.168.1.2:51234 to 192.168.1.100:1812
#   User-Name = "username"
#   User-Password = "password"
# Received Access-Accept Id 123 from 192.168.1.100:1812

# If timeout:
# radtest: no response from RADIUS server
# Indicates firewall, network, or port mapping issue
```

---

### 10.4 General Network Debugging Utilities

**From Host Machine:**

```bash
# Check if port is listening
netstat -tuln | grep -E "1812|1813|8000|5432|6379"

# Test connectivity to exposed ports
curl http://localhost:8000/health
redis-cli -h localhost -p 6379 -a password ping
psql -h localhost -p 5432 -U postgres -d nac -c "SELECT 1"

# Check Docker network
docker network ls
docker network inspect nac-network

# View container logs
docker-compose logs -f postgres
docker-compose logs -f api
docker-compose logs -f redis
docker-compose logs -f freeradius
```

**From Inside Container:**

```bash
# Execute shell in running container
docker exec -it nac-api /bin/bash

# Test DNS resolution
nslookup postgres
ping postgres
getent hosts postgres

# Test TCP connectivity
nc -zv postgres 5432
curl http://nac-api:8000/health

# Check network interfaces
ip addr show
ip route show

# View open connections
netstat -tuln
ss -tuln

# Test RADIUS (if radtest installed)
radtest username password localhost 0 secret
```

**From FreeRADIUS Container:**

```bash
# Run in debug mode to see request processing
docker exec -it nac-freeradius freeradius -X

# Test REST endpoint
docker exec -it nac-freeradius curl -X POST http://nac-api:8000/auth \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "test"}'

# Check radius client configuration
docker exec -it nac-freeradius cat /etc/freeradius/clients.conf

# View RADIUS logs
docker exec -it nac-freeradius tail -f /var/log/freeradius/radius.log
```

---

## Summary

This document provides comprehensive network connectivity mapping for the NAC system:

1. **Architecture Overview**: Docker bridge network (172.20.0.0/24) with service-to-service communication
2. **Service Assignments**: PostgreSQL, Redis, FastAPI, FreeRADIUS with internal and external ports
3. **Connection Flows**: Detailed sequences for authentication, accounting, and CoA
4. **Visual Diagrams**: Mermaid graph showing all connections and data flows
5. **Connection Strings**: Database, cache, and REST endpoint connection details with examples
6. **Security**: Network isolation, port mapping risks, and production recommendations
7. **DNS Resolution**: Docker embedded DNS (127.0.0.11:53) operation and hostname mapping
8. **Troubleshooting**: Step-by-step guides for debugging common connection issues

The document is designed for both operational understanding and practical troubleshooting of the NAC network infrastructure.
