# Custom Network Proxy Server

![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-43%20passed-22c55e)
![Dependencies](https://img.shields.io/badge/Dependencies-None-7c3aed)
![RFC 7230](https://img.shields.io/badge/RFC-7230-0891b2)

A forward proxy server built with Python's socket programming. It intercepts HTTP/HTTPS traffic between clients and origin servers, applying authentication, rate limiting, domain filtering, and response caching at each step. Includes a real-time monitoring dashboard and structured JSON logging.

The entire project uses only the Python standard library — no external packages are required.

---

## Table of Contents

- [Setup & Running](#setup--running)
- [How to Test](#how-to-test)
- [Architecture](#architecture)
- [Request Pipeline](#request-pipeline)
- [Features](#features)
  - [Authentication](#authentication)
  - [Rate Limiting](#rate-limiting)
  - [Domain Filtering](#domain-filtering)
  - [Response Caching](#response-caching)
  - [Monitoring Dashboard](#monitoring-dashboard)
  - [Logging](#logging)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Limitations](#limitations)
- [Documentation](#documentation)

---

## Setup & Running

**Prerequisites:** Python 3.10 or higher.

```bash
# Clone the repository
git clone https://github.com/Krit-Jain/Custom-Network-Proxy-Server.git
cd Custom-Network-Proxy-Server

# Start the proxy server
python src/server.py
```

On startup, the proxy binds to port `8888` and the dashboard launches on port `8889`:

```
[+] Dashboard running at http://localhost:8889
[+] Proxy listening on 0.0.0.0:8888  (pool=20)
```

No `pip install` is needed — there are no external dependencies.

---

## How to Test

### Quick Manual Test

With the proxy running, use `curl` to send requests through it:

```bash
# HTTP request (allowed domain)
curl -x localhost:8888 -U admin:admin123 http://neverssl.com

# HTTPS request
curl -x localhost:8888 -U admin:admin123 https://www.google.com

# Blocked domain → should return 403 Forbidden
curl -x localhost:8888 -U admin:admin123 http://example.com

# No credentials → should return 407 Proxy Auth Required
curl -x localhost:8888 http://neverssl.com
```

### Automated Test Suite

The project includes **43 automated tests** (35 unit + 8 integration):

```bash
# Run unit tests (no proxy server needed)
python -m unittest tests.test_proxy -v

# Run full suite including integration tests (start proxy first)
python src/server.py &
python -m unittest tests.test_proxy -v
```

**Test coverage:**

| Module | Tests | What's Verified |
|:-------|:------|:----------------|
| Parser | 9 | Absolute URI, origin-form, CONNECT, POST body, malformed input |
| Auth | 7 | Hash/verify, plaintext fallback, unique salts, wrong password |
| Cache | 6 | Put/get, LRU eviction, TTL expiry, stats, clear |
| Rate Limiter | 7 | Capacity, blocking, per-IP isolation, refill, concurrency |
| Log Schema | 3 | Dict serialization, human format, timestamp |
| Filter | 3 | Domain matching, null/empty handling |
| Integration | 8 | HTTP forwarding, blocking, auth, rate limiting, 50-thread concurrency |

### Dashboard

Open **http://localhost:8889** in a browser while the proxy is running to see live metrics, request logs, and cache statistics.

---

## Architecture

The proxy is built as 13 modular components, each with a single responsibility:

<img src="docs/architecture_diagram.png" alt="System Architecture" width="80%">

| Module | Responsibility |
|:-------|:---------------|
| `server.py` | TCP socket listener, bounded thread pool (`ThreadPoolExecutor`), signal handlers |
| `handler.py` | Request pipeline orchestration — routes each connection through 6 processing steps |
| `parser.py` | HTTP request parsing per RFC 7230 (header accumulation, URI decomposition, body reading) |
| `forwarder.py` | HTTP forwarding (header rewriting, cache-aside) and HTTPS CONNECT tunneling (bidirectional relay) |
| `filter.py` | Domain/IP/CIDR blocklist with hot-reload support |
| `cache.py` | Thread-safe LRU cache using `OrderedDict` with TTL eviction |
| `auth.py` | PBKDF2-HMAC-SHA256 password hashing and verification |
| `rate_limiter.py` | Per-IP token bucket rate limiter with stale bucket pruning |
| `logger.py` | Dual-output structured logging (JSON file + human-readable terminal) with ring buffer |
| `log_schema.py` | Canonical `LogEntry` dataclass — single schema for all log events |
| `config_loader.py` | INI configuration parser with typed defaults |
| `dashboard.py` | HTTP server for monitoring dashboard with SSE streaming |
| `dashboard_ui.py` | Self-contained dashboard HTML/CSS/JS (glassmorphism UI, Chart.js) |

---

## Request Pipeline

Every client connection passes through a 6-step pipeline in `handler.py`. Each step either advances the request or rejects it with the appropriate HTTP status code:

```
Client Request
    │
    ▼
┌──────────────────────────────────┐
│  1. Parse HTTP Request           │──→ 400 Bad Request
│     (parser.py)                  │    (malformed input)
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  2. Rate Limit Check             │──→ 429 Too Many Requests
│     (token bucket, per IP)       │    + Retry-After header
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  3. Authentication               │──→ 407 Proxy Auth Required
│     (PBKDF2 verification)        │    (missing/invalid credentials)
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  4. Domain / IP Filter           │──→ 403 Forbidden
│     (blocklist + CIDR match)     │    (blocked destination)
└──────────────┬───────────────────┘
               │
        ┌──────┴──────┐
        │             │
        ▼             ▼
  ┌───────────┐ ┌───────────────┐
  │ 5. HTTPS  │ │ 6. HTTP       │
  │ CONNECT   │ │ Forward       │
  │ Tunnel    │ │ + Cache Check │
  └─────┬─────┘ └──────┬────────┘
        │              │
        └──────┬───────┘
               ▼
         Response → Client
```

Rate limiting is placed **before** authentication intentionally — it prevents an attacker from flooding the server with authentication attempts, since PBKDF2 verification is computationally expensive.

---

## Features

### Authentication

Passwords are hashed using **PBKDF2-HMAC-SHA256** with parameters following NIST SP 800-132 and OWASP 2024 guidelines:

| Parameter | Value |
|:----------|:------|
| Algorithm | PBKDF2-HMAC-SHA256 |
| Iterations | 600,000 |
| Salt | 32 bytes (random, per user) |
| Key length | 32 bytes |
| Comparison | Constant-time (`hmac.compare_digest`) |
| Storage format | `username:pbkdf2$iterations$salt_hex$hash_hex` |

**Managing users:**

```bash
python tools/manage_users.py add <username> <password>    # Add or update user
python tools/manage_users.py remove <username>            # Remove user
python tools/manage_users.py list                         # List all users
python tools/manage_users.py migrate                      # Convert plaintext → hashed
```

Default credentials: `admin` / `admin123`

---

### Rate Limiting

Uses the **token bucket algorithm** — each client IP gets its own bucket:

| Parameter | Default | Description |
|:----------|:--------|:------------|
| Capacity | 20 | Maximum burst of requests |
| Refill rate | 2/sec | Tokens restored per second |
| Stale threshold | 10 min | Inactive buckets are pruned |

When a bucket is empty, the proxy returns `429 Too Many Requests` with a `Retry-After` header.

---

### Domain Filtering

The blocklist is configured in `config/blocked_domains.txt`:

```
# Exact domain (also blocks subdomains)
example.com
badsite.org

# IP address
192.0.2.5

# CIDR range
10.0.0.0/8
```

Supports exact domain, subdomain suffix, exact IP, and CIDR range matching. The blocklist can be hot-reloaded at runtime without restarting the proxy.

---

### Response Caching

An in-memory **LRU cache with TTL eviction** for HTTP GET responses:

- Data structure: `collections.OrderedDict` (O(1) operations)
- Only caches GET requests with 200 OK responses
- Per-object size limit: 512 KB
- TTL: 300 seconds (configurable)
- TTL is checked lazily on `get()` — no background sweeper thread
- Cache statistics (hits, misses, evictions, hit rate) are tracked and exposed via the dashboard

---

### Monitoring Dashboard

A web dashboard runs on port `8889` alongside the proxy:

<img src="docs/dashboard_screenshot.png" alt="Monitoring Dashboard" width="85%">

| Panel | What it shows |
|:------|:-------------|
| Live counters | Total, Allowed, Blocked, Cached, Rate-Limited, Errors |
| Requests/sec chart | Line graph of throughput over the last 60 seconds |
| Log feed | Color-coded request stream (green=allow, red=block, yellow=rate-limit, blue=cache-hit) |
| Cache stats | Current entries, hit rate, size |
| Top hosts | Most requested domains |
| Rate limiter | Active IP buckets |

**API endpoints:**

| Endpoint | Response |
|:---------|:---------|
| `GET /` | Dashboard HTML page |
| `GET /api/metrics` | JSON metrics snapshot |
| `GET /api/logs` | Recent log entries (JSON) |
| `GET /events` | Server-Sent Events stream (real-time push) |

The dashboard is built with `http.server` + `ThreadingMixIn` and uses SSE for live updates. The UI uses Chart.js (loaded via CDN) for graphs.

---

### Logging

Every event is written to three destinations:

1. **JSON file** — `logs/proxy.log` (one JSON object per line, 1 MB rotation, 5 backups)
2. **Terminal** — human-readable compact format
3. **Ring buffer** — last 200 entries, consumed by the dashboard SSE stream

Each request is assigned a UUID4 `request_id` for end-to-end log correlation.

**Example log entry:**

```json
{
  "timestamp": "2026-06-12T03:00:01.123+00:00",
  "level": "INFO",
  "event": "FORWARDED",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "client_ip": "192.168.1.10",
  "method": "GET",
  "host": "example.com",
  "action": "FORWARDED",
  "status_code": 200,
  "latency_ms": 45.2,
  "bytes_transferred": 15234
}
```

---

## Configuration

All settings are in `config/proxy.conf`:

```ini
[server]
listen_host = 0.0.0.0
listen_port = 8888
max_connections = 50
thread_pool_size = 20

[logging]
log_file = logs/proxy.log
max_log_size = 1048576       # 1 MB
backup_count = 5
log_level = INFO

[cache]
enabled = true
max_entries = 100
max_object_size = 524288     # 512 KB
cache_ttl = 300              # 5 minutes

[rate_limit]
enabled = true
capacity = 20
refill_rate = 2

[dashboard]
enabled = true
port = 8889
```

---

## Project Structure

```
Custom-Network-Proxy-Server/
├── src/
│   ├── server.py            # Entry point — TCP socket + thread pool
│   ├── handler.py           # 6-step request pipeline
│   ├── parser.py            # HTTP request parsing (RFC 7230)
│   ├── forwarder.py         # HTTP forwarding + HTTPS tunneling
│   ├── filter.py            # Domain/IP/CIDR blocklist
│   ├── cache.py             # LRU cache with TTL
│   ├── logger.py            # Structured JSON logging + rotation
│   ├── log_schema.py        # LogEntry dataclass
│   ├── rate_limiter.py      # Token bucket rate limiter
│   ├── auth.py              # PBKDF2 password hashing
│   ├── config_loader.py     # Configuration parser
│   ├── dashboard.py         # Monitoring HTTP server (SSE)
│   └── dashboard_ui.py      # Dashboard HTML/CSS/JS
│
├── config/
│   ├── proxy.conf           # Server configuration
│   ├── blocked_domains.txt  # Domain/IP blocklist
│   └── users.txt            # User credentials (PBKDF2 hashed)
│
├── tools/
│   └── manage_users.py      # CLI for user management
│
├── tests/
│   ├── test_proxy.py        # 43 unit + integration tests
│   ├── sample_logs/         # Example JSON log entries
│   └── *.sh                 # curl-based smoke tests
│
├── docs/
│   ├── design.md            # Architecture & design document
│   ├── Project_Report.pdf   # Detailed project report
│   └── Project_Report.html  # Report (HTML version)
│
├── logs/                    # Log output directory
├── requirements.txt
├── setup.py
└── README.md
```

---

## Graceful Shutdown

- `SIGINT` (Ctrl+C) and `SIGTERM` trigger clean shutdown
- Listening socket is closed, accept loop exits
- `ThreadPoolExecutor.shutdown(wait=True)` drains in-flight requests
- Dashboard daemon thread terminates automatically

---

## Limitations

| Limitation | Description |
|:-----------|:------------|
| No `Cache-Control` parsing | HTTP cache semantics (RFC 7234) are not fully implemented |
| No chunked transfer decoding | Chunked responses are relayed transparently |
| Thread-based concurrency | Bounded by OS thread limits; `asyncio` would scale further |
| No TLS interception | HTTPS content is tunneled opaquely (intentional design choice) |
| No connection pooling | Each request opens a new TCP connection to the origin |
| No WebSocket support | `Upgrade: websocket` is not handled |

---

## Documentation

| Document | Description |
|:---------|:------------|
| [`docs/design.md`](docs/design.md) | Architecture diagrams, design decisions, sequence diagrams |
| [`docs/Project_Report.pdf`](docs/Project_Report.pdf) | Comprehensive project report |

---

## References

- [RFC 7230 — HTTP/1.1 Message Syntax and Routing](https://www.rfc-editor.org/rfc/rfc7230)
- [NIST SP 800-132 — Password-Based Key Derivation](https://doi.org/10.6028/NIST.SP.800-132)
- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)