<div align="center">

# ⚡ Custom Network Proxy Server

### A production-grade forward proxy server built from scratch with Python

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-43%20Passed-22c55e?style=for-the-badge&logo=pytest&logoColor=white)](tests/)
[![Dependencies](https://img.shields.io/badge/Dependencies-Zero-7c3aed?style=for-the-badge)](requirements.txt)
[![RFC 7230](https://img.shields.io/badge/RFC-7230%20Compliant-0891b2?style=for-the-badge)](https://www.rfc-editor.org/rfc/rfc7230)
[![License](https://img.shields.io/badge/License-MIT-f59e0b?style=for-the-badge)](LICENSE)

**HTTP forwarding • HTTPS CONNECT tunneling • PBKDF2 authentication • Token bucket rate limiting  
LRU caching • Domain/IP/CIDR filtering • Structured JSON logging • Real-time monitoring dashboard**

Built entirely on the **Python standard library** — zero external dependencies.

---

<img src="docs/dashboard_screenshot.png" alt="Real-Time Monitoring Dashboard" width="85%">

*Real-time monitoring dashboard with dark glassmorphism UI, live metrics, and request streaming*

</div>

---

## 🌟 Why This Project Stands Out

<table>
<tr>
<td width="50%">

### 🔬 Built From the Ground Up
Every component — from TCP socket management to HTTP parsing to PBKDF2 cryptography — is implemented **from scratch** using only Python's standard library. No frameworks, no shortcuts.

</td>
<td width="50%">

### 🏗️ Production-Grade Architecture
13 modular components organized into a clean **6-step request pipeline** with proper error handling, graceful shutdown, structured logging, and comprehensive configuration management.

</td>
</tr>
<tr>
<td>

### 🔒 Security-First Design
PBKDF2-HMAC-SHA256 with **600,000 iterations** (OWASP 2024 recommended), constant-time comparison, rate limiting **before** auth (brute-force protection), and domain/IP/CIDR filtering.

</td>
<td>

### 📊 Full Observability
Real-time web dashboard with **Server-Sent Events**, Chart.js live graphs, color-coded log streaming, cache analytics, and structured JSON logging with rotation.

</td>
</tr>
</table>

---

## ✨ Features at a Glance

| Feature | Description | Module |
|:--------|:------------|:-------|
| 🔀 **HTTP/HTTPS Proxy** | Full HTTP forwarding + HTTPS CONNECT bidirectional tunneling | `forwarder.py` |
| 🧵 **Thread Pool Concurrency** | Bounded `ThreadPoolExecutor` — prevents resource exhaustion under load | `server.py` |
| 🛡️ **Token Bucket Rate Limiting** | Per-IP rate limiting with `429 Too Many Requests` + `Retry-After` header | `rate_limiter.py` |
| 🔐 **PBKDF2 Authentication** | PBKDF2-HMAC-SHA256 (600K iterations, 32-byte salt, constant-time comparison) | `auth.py` |
| 🚫 **Domain/IP/CIDR Filtering** | Exact domain, subdomain suffix, IPv4/IPv6, and CIDR range blocking with hot-reload | `filter.py` |
| 📦 **LRU Response Cache** | Thread-safe OrderedDict LRU cache with TTL eviction for HTTP GET 200 responses | `cache.py` |
| 📊 **Live Monitoring Dashboard** | Real-time web UI with SSE push, Chart.js graphs, and glassmorphism design | `dashboard.py` |
| 📝 **Structured JSON Logging** | Dual-output (JSON file + human terminal), rotation, UUID request IDs, latency tracking | `logger.py` |
| 🧪 **43 Automated Tests** | Comprehensive unittest suite — 35 unit + 8 integration tests | `test_proxy.py` |
| ⚙️ **Single-File Configuration** | All settings in one INI file with typed defaults and sensible fallbacks | `config_loader.py` |
| 🛑 **Graceful Shutdown** | `SIGINT`/`SIGTERM` handlers, socket cleanup, thread pool drain, zero leaks | `server.py` |
| 📋 **RFC 7230 Compliance** | Hop-by-hop header stripping, `Via` injection, URI rewriting, `X-Forwarded-For` | `forwarder.py` |

---

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/Krit-Jain/Custom-Network-Proxy-Server.git
cd Custom-Network-Proxy-Server

# Start the proxy server (dashboard auto-launches on :8889)
python src/server.py
```

**Expected output:**
```
[+] Dashboard running at http://localhost:8889
[+] Proxy listening on 0.0.0.0:8888  (pool=20)
```

**Send your first request:**
```bash
# HTTP request through the proxy
curl -x localhost:8888 -U admin:admin123 http://neverssl.com

# HTTPS request through the proxy
curl -x localhost:8888 -U admin:admin123 https://www.google.com
```

**Open the dashboard:** Navigate to **http://localhost:8889** in your browser.

> **Note:** No `pip install` needed — the entire project runs on the Python standard library.

---

## 🏗️ Architecture

### High-Level System Design

<div align="center">
<img src="docs/architecture_diagram.png" alt="System Architecture" width="80%">
</div>

### Component Map

```
Custom-Network-Proxy-Server/
│
├── src/                              # 13 source modules (~90 KB)
│   ├── server.py                     # TCP socket + ThreadPoolExecutor + signal handlers
│   ├── handler.py                    # 6-step request pipeline orchestrator
│   ├── parser.py                     # HTTP request parsing (RFC 7230 §3)
│   ├── forwarder.py                  # HTTP forwarding + HTTPS CONNECT tunneling
│   ├── filter.py                     # Domain/IP/CIDR blocklist with hot-reload
│   ├── cache.py                      # Thread-safe LRU cache with TTL eviction
│   ├── logger.py                     # Structured JSON logging + rotation + ring buffer
│   ├── log_schema.py                 # Canonical LogEntry dataclass
│   ├── rate_limiter.py               # Per-IP token bucket rate limiter
│   ├── auth.py                       # PBKDF2-HMAC-SHA256 authentication
│   ├── config_loader.py              # INI config parser with typed defaults
│   ├── dashboard.py                  # Real-time monitoring HTTP server (SSE)
│   └── dashboard_ui.py              # Self-contained dashboard HTML/CSS/JS
│
├── config/                           # Configuration
│   ├── proxy.conf                    # Server settings (host, port, pool size, cache, rate limit)
│   ├── blocked_domains.txt           # Domain/IP/CIDR blocklist
│   └── users.txt                     # PBKDF2-hashed user credentials
│
├── tests/                            # 43 automated tests + smoke tests
│   ├── test_proxy.py                 # 35 unit + 8 integration tests
│   ├── sample_logs/                  # Example structured log entries
│   └── *.sh                          # curl-based smoke tests
│
├── tools/
│   └── manage_users.py               # CLI for user CRUD + password migration
│
├── docs/
│   ├── design.md                     # Architecture & design document
│   └── Project_Report.html           # Comprehensive project report
│
├── logs/                             # Rotating log output directory
├── requirements.txt                  # Zero dependencies (stdlib only)
├── setup.py                          # Package configuration
└── README.md
```

---

## 📜 Request Pipeline

Every incoming connection passes through a strict **6-step security pipeline**. Each step either advances the request or terminates it with an appropriate HTTP error:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT REQUEST                               │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │  1. PARSE HTTP REQUEST         │───→ 400 Bad Request
              │     (parser.py — RFC 7230)     │     (malformed input)
              └────────────────┬───────────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │  2. RATE LIMIT CHECK           │───→ 429 Too Many Requests
              │     (Token Bucket per IP)      │     + Retry-After header
              └────────────────┬───────────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │  3. AUTHENTICATION             │───→ 407 Proxy Auth Required
              │     (PBKDF2-HMAC-SHA256)       │     (missing/invalid creds)
              └────────────────┬───────────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │  4. DOMAIN / IP FILTER         │───→ 403 Forbidden
              │     (blocklist + CIDR match)   │     (blocked destination)
              └────────────────┬───────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
       ┌────────────────────┐  ┌────────────────────┐
       │ 5. HTTPS CONNECT   │  │ 6. HTTP FORWARD    │
       │    Tunnel           │  │    + Cache Lookup   │
       │ (bidirectional     │  │ (cache-aside       │
       │  byte relay)       │  │  pattern)           │
       └────────┬───────────┘  └────────┬───────────┘
                │                       │
                └───────────┬───────────┘
                            │
                            ▼
              ┌────────────────────────────────┐
              │        RESPONSE → CLIENT       │
              └────────────────────────────────┘
```

> **Security design:** Rate limiting runs **before** authentication. This is intentional — it provides fail-fast protection against brute-force attacks, preventing attackers from overwhelming the expensive PBKDF2 computation (600K iterations per attempt).

---

## 🔐 Authentication

Passwords are stored as **PBKDF2-HMAC-SHA256** hashes following [NIST SP 800-132](https://doi.org/10.6028/NIST.SP.800-132) and [OWASP 2024](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) recommendations.

| Property | Value |
|:---------|:------|
| **Algorithm** | PBKDF2-HMAC-SHA256 |
| **Iterations** | 600,000 (OWASP 2024 minimum for SHA-256) |
| **Salt** | 32-byte random per user (`os.urandom(32)`) |
| **Key Length** | 32 bytes |
| **Comparison** | Constant-time via `hmac.compare_digest()` |
| **Storage Format** | `username:pbkdf2$iterations$salt_hex$hash_hex` |

**User Management CLI:**

```bash
python tools/manage_users.py add alice mypassword      # Add user (auto-hashed)
python tools/manage_users.py list                       # List all users
python tools/manage_users.py remove alice               # Remove user
python tools/manage_users.py migrate                    # Migrate plaintext → PBKDF2
```

---

## 🛡️ Rate Limiting — Token Bucket Algorithm

Each unique client IP gets its own token bucket:

| Parameter | Default | Description |
|:----------|:--------|:------------|
| **Capacity** | 20 tokens | Maximum burst size |
| **Refill Rate** | 2 tokens/sec | Sustained request rate |
| **Stale Threshold** | 600 seconds | Prune inactive buckets after 10 min |

When a client's bucket is empty, the proxy responds with:
```
HTTP/1.1 429 Too Many Requests
Retry-After: 1
```

**Implementation highlights:**
- Fine-grained locking: global lock for bucket registry, per-bucket locks for token operations
- Stale bucket pruning runs at most once per minute (prevents memory growth)
- Per-IP isolation — one client's traffic never affects another

---

## 🚫 Domain Filtering

Edit `config/blocked_domains.txt` (supports hot-reload at runtime):

```
# Exact domain match (also blocks subdomains)
example.com
badsite.org

# Exact IP address
192.0.2.5

# CIDR range (blocks entire subnet)
10.0.0.0/8
192.168.0.0/24
```

| Filter Type | Example | Matches |
|:------------|:--------|:--------|
| Exact Domain | `example.com` | `example.com` |
| Subdomain Suffix | `example.com` | `sub.example.com`, `a.b.example.com` |
| Exact IP | `192.0.2.5` | `192.0.2.5` |
| CIDR Range | `192.168.0.0/24` | All 256 addresses in the /24 block |

---

## 📦 Response Caching

Thread-safe **LRU cache** with **TTL eviction** using `collections.OrderedDict`:

- **O(1)** insert, lookup, delete, and LRU reordering
- Only caches **HTTP GET** requests with **200 OK** responses
- Per-object size limit (512 KB) prevents large downloads from dominating cache
- Lazy TTL expiration on `get()` — no background sweeper thread
- Full observability: hits, misses, evictions, hit rate %, current size

```ini
[cache]
enabled = true
max_entries = 100
max_object_size = 524288    # 512 KB
cache_ttl = 300              # 5 minutes
```

---

## 📊 Monitoring Dashboard

The real-time dashboard at `http://localhost:8889` provides complete proxy observability:

| Panel | Description |
|:------|:------------|
| 📈 **Live Counters** | Total / Allowed / Blocked / Cached / Rate-Limited / Errors |
| 📊 **Requests/sec Chart** | Real-time Chart.js line graph (last 60 seconds) |
| 📋 **Live Log Feed** | Color-coded stream: 🟢 ALLOW, 🔴 BLOCK, 🟡 RATE_LIMIT, 🔵 CACHE_HIT |
| 💾 **Cache Stats** | Entries, hit rate %, total size, evictions |
| 🌐 **Top Hosts** | Most requested domains ranked by hit count |
| ⏱️ **Rate Limiter** | Active IP buckets, capacity, refill rate |

**REST API:**

| Endpoint | Description |
|:---------|:------------|
| `GET /` | Dashboard HTML page |
| `GET /api/metrics` | JSON metrics snapshot |
| `GET /api/logs` | Recent log entries (JSON) |
| `GET /events` | SSE stream (real-time push every 1 second) |

---

## 📝 Structured Logging

Every event is written to **three destinations simultaneously**:

```
log_event()
    ├── 📁 JSON File    → logs/proxy.log (1 MB rotation × 5 backups)
    ├── 🖥️ Terminal     → Human-readable compact format
    └── 🔄 Ring Buffer  → Last 200 entries → Dashboard SSE stream
```

**Example JSON log entry:**
```json
{
  "timestamp": "2026-06-12T03:00:01.123+00:00",
  "level": "INFO",
  "event": "FORWARDED",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "client_ip": "192.168.1.10",
  "method": "GET",
  "host": "example.com",
  "port": 80,
  "action": "FORWARDED",
  "status_code": 200,
  "latency_ms": 45.2,
  "bytes_transferred": 15234
}
```

---

## 🔧 Configuration

All behavior is controlled via a single `config/proxy.conf` file:

```ini
[server]
listen_host = 0.0.0.0
listen_port = 8888
max_connections = 50          # OS socket backlog
thread_pool_size = 20         # Concurrent worker threads

[logging]
log_file = logs/proxy.log
max_log_size = 1048576        # 1 MB before rotation
backup_count = 5
log_level = INFO

[cache]
enabled = true
max_entries = 100
max_object_size = 524288      # 512 KB per object
cache_ttl = 300               # 5 minutes

[rate_limit]
enabled = true
capacity = 20                 # Max burst per IP
refill_rate = 2               # Tokens restored per second

[dashboard]
enabled = true
port = 8889
```

---

## 🧪 Testing

```bash
# Run unit tests only (no proxy needed)
python -m unittest tests.test_proxy -v

# Run full suite including integration tests
python src/server.py &
python -m unittest tests.test_proxy -v
```

### Test Suite — 43 Tests (35 Unit + 8 Integration)

| Module | Tests | What's Tested |
|:-------|:------|:--------------|
| **Parser** | 9 | Absolute URI, origin-form, CONNECT, POST body, malformed input, query strings |
| **Auth** | 7 | Hash/verify round-trip, plaintext fallback, unique salts, wrong password, edge cases |
| **Cache** | 6 | Put/get, LRU eviction order, TTL expiry, stats accuracy, clear, overwrite |
| **Rate Limiter** | 7 | Capacity enforcement, blocking, per-IP isolation, refill, concurrent access |
| **Log Schema** | 3 | Dict serialization, human format, timestamp auto-population |
| **Filter** | 3 | Domain exact/suffix matching, null/empty handling |
| **Integration** | 8 | HTTP forwarding, domain blocking, auth enforcement, rate limiting, 50-thread concurrency |

---

## 🛑 Graceful Shutdown

```
Ctrl+C (SIGINT) or SIGTERM
    │
    ├── Close listening socket → accept loop exits
    ├── ThreadPoolExecutor.shutdown(wait=True) → drain in-flight requests
    ├── Dashboard daemon thread → auto-terminates
    └── Zero resource leaks ✅
```

---

## ⚠️ Limitations

| Limitation | Potential Enhancement |
|:-----------|:---------------------|
| No `Cache-Control` header parsing | Implement full HTTP cache semantics (RFC 7234) |
| No chunked transfer decoding | Parse `Transfer-Encoding: chunked` |
| Thread-based concurrency | Migrate to `asyncio` for 10K+ connections |
| No TLS interception | Add optional MITM proxy mode with CA certificate |
| No connection pooling to origins | Implement `Keep-Alive` connection reuse |
| No WebSocket proxy support | Handle `Upgrade: websocket` header |

---

## 📚 Documentation

| Document | Description |
|:---------|:------------|
| [`docs/design.md`](docs/design.md) | Architecture diagrams, design decisions, Mermaid sequence diagrams |
| [`docs/Project_Report.html`](docs/Project_Report.html) | Comprehensive project report (open in browser, print to PDF) |

---

## 🔗 References

1. [RFC 7230 — HTTP/1.1 Message Syntax and Routing](https://www.rfc-editor.org/rfc/rfc7230) — IETF
2. [NIST SP 800-132 — Password-Based Key Derivation](https://doi.org/10.6028/NIST.SP.800-132) — NIST
3. [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) — OWASP 2024
4. [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events) — MDN Web Docs

---

<div align="center">

**Built with ❤️ using only the Python Standard Library**

*Custom Network Proxy Server • Krit Jain • 2026*

</div>