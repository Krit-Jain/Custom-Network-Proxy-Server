# ⚡ Custom Network Proxy Server

![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Tests](https://img.shields.io/badge/Tests-43%20passed-brightgreen)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20WSL-blue)

A **production-grade forward proxy server** built with Python's socket programming. Supports HTTP forwarding, HTTPS CONNECT tunneling, per-IP rate limiting, PBKDF2 authentication, LRU caching, structured JSON logging, and a **real-time monitoring dashboard**.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔀 **HTTP/HTTPS Proxy** | Full HTTP forwarding + HTTPS CONNECT tunneling |
| 🧵 **Thread Pool** | Bounded `ThreadPoolExecutor` (configurable, prevents resource exhaustion) |
| 🛡️ **Rate Limiting** | Per-IP token bucket algorithm with `429 Too Many Requests` + `Retry-After` |
| 🔐 **Authentication** | PBKDF2-HMAC-SHA256 password hashing (600K iterations) |
| 🚫 **Domain Filtering** | Domain, subdomain, IP, and CIDR range blocking with hot-reload |
| 📦 **Response Caching** | Thread-safe LRU cache with TTL eviction for HTTP GET requests |
| 📊 **Live Dashboard** | Real-time web dashboard with SSE, Chart.js graphs, and glassmorphism UI |
| 📝 **Structured Logging** | JSON log output with rotation, request IDs, and latency tracking |
| 🧪 **43 Tests** | Comprehensive unittest suite (35 unit + 8 integration) |
| ⚙️ **Configurable** | All settings in a single `proxy.conf` INI file |

---

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/Krit-Jain/Custom-Network-Proxy-Server.git
cd Custom-Network-Proxy-Server

# Start the proxy (dashboard launches automatically on :8889)
python src/server.py
```

**Expected output:**
```
[+] Dashboard running at http://localhost:8889
[+] Proxy listening on 0.0.0.0:8888  (pool=20)
```

---

## 🗂️ Project Structure

```
Custom-Network-Proxy-Server/
├── src/
│   ├── server.py           # Entry point — TCP socket + thread pool
│   ├── handler.py          # 6-step request pipeline
│   ├── parser.py           # HTTP request parsing (RFC 7230)
│   ├── forwarder.py        # HTTP forwarding + HTTPS tunneling
│   ├── filter.py           # Domain/IP/CIDR blocklist
│   ├── cache.py            # LRU cache with TTL
│   ├── logger.py           # Structured JSON logging + rotation
│   ├── log_schema.py       # LogEntry dataclass
│   ├── rate_limiter.py     # Token bucket rate limiter
│   ├── auth.py             # PBKDF2 password hashing
│   ├── config_loader.py    # Configuration parser
│   ├── dashboard.py        # Monitoring HTTP server (SSE)
│   └── dashboard_ui.py     # Dashboard HTML/CSS/JS
│
├── config/
│   ├── proxy.conf          # Server configuration
│   ├── blocked_domains.txt # Domain/IP blocklist
│   └── users.txt           # User credentials (PBKDF2 hashed)
│
├── tools/
│   └── manage_users.py     # CLI for user management
│
├── tests/
│   ├── test_proxy.py       # 43 unit + integration tests
│   ├── sample_logs/        # Example JSON log entries
│   └── *.sh                # curl-based smoke tests
│
├── docs/
│   └── design.md           # Architecture + design document
│
├── logs/                   # Log output directory
├── requirements.txt
├── setup.py
└── README.md
```

---

## 📡 Usage

### HTTP Requests

```bash
curl -x localhost:8888 -U admin:admin123 http://neverssl.com
```

### HTTPS Requests

```bash
curl -x localhost:8888 -U admin:admin123 https://www.google.com
```

### Dashboard

Open **http://localhost:8889** in your browser for the live monitoring dashboard.

---

## 🔧 Configuration

All settings are in `config/proxy.conf`:

```ini
[server]
listen_host = 0.0.0.0
listen_port = 8888
max_connections = 50
thread_pool_size = 20

[cache]
enabled = true
max_entries = 100
cache_ttl = 300

[rate_limit]
enabled = true
capacity = 20          # Max burst per IP
refill_rate = 2        # Tokens/sec

[dashboard]
enabled = true
port = 8889
```

---

## 🔐 User Management

Passwords are stored as PBKDF2-HMAC-SHA256 hashes (600K iterations, 32-byte salt).

```bash
# Add a user
python tools/manage_users.py add alice mypassword

# List users
python tools/manage_users.py list

# Remove a user
python tools/manage_users.py remove alice

# Migrate plaintext passwords to hashed
python tools/manage_users.py migrate
```

---

## 🚫 Domain Filtering

Edit `config/blocked_domains.txt`:

```
# Blocked domains
example.com
badsite.org

# Blocked IPs
192.0.2.5

# CIDR ranges
10.0.0.0/8
```

Supports hot-reload — call `filter.reload_blocklist()` at runtime.

---

## 📊 Monitoring Dashboard

The dashboard at `http://localhost:8889` provides:

- **Live counters** — Total / Allowed / Blocked / Cached / Rate-Limited / Errors
- **Requests/sec chart** — Real-time line graph (last 60 seconds)
- **Live log feed** — Color-coded request stream
- **Cache stats** — Entries, hit rate, size
- **Top hosts** — Most requested domains
- **Rate limiter status** — Active tracked IPs

**API Endpoints:**

| Endpoint | Description |
|---|---|
| `GET /` | Dashboard HTML page |
| `GET /api/metrics` | JSON metrics snapshot |
| `GET /api/logs` | Recent log entries (JSON) |
| `GET /events` | SSE stream (real-time push) |

---

## 🧪 Testing

```bash
# Run all unit tests (no proxy needed)
python -m unittest tests.test_proxy -v

# Run full suite including integration tests
python src/server.py &
python -m unittest tests.test_proxy -v
```

### Test Coverage

| Module | Tests |
|---|---|
| Parser | 9 tests (absolute URI, origin-form, CONNECT, POST body, malformed) |
| Auth | 7 tests (hash/verify, plaintext fallback, unique salts, edge cases) |
| Cache | 6 tests (put/get, LRU eviction, TTL expiry, stats, clear) |
| Rate Limiter | 7 tests (capacity, blocking, per-IP isolation, refill, concurrency) |
| Log Schema | 3 tests (dict serialization, human format, timestamp) |
| Filter | 3 tests (domain matching, null/empty handling) |
| Integration | 8 tests (HTTP forwarding, blocking, auth, rate limiting, concurrency) |

---

## 📜 Request Pipeline

Every request passes through this 6-step pipeline:

```
Client Request
    │
    ▼
1. Parse HTTP request (parser.py)
    │
    ▼
2. Rate limit check (rate_limiter.py) ──→ 429 Too Many Requests
    │
    ▼
3. Authentication (auth.py) ──→ 407 Proxy Auth Required
    │
    ▼
4. Domain/IP filter (filter.py) ──→ 403 Forbidden
    │
    ▼
5. HTTPS? → CONNECT tunnel (bidirectional relay)
6. HTTP?  → Forward request (with caching)
    │
    ▼
Response → Client
```

---

## 📝 Logging

- **File output**: JSON (one object per line) → `logs/proxy.log`
- **Terminal output**: Human-readable compact format
- **Rotation**: Size-based at 1 MB, 5 backup files
- **Request IDs**: UUID4 for end-to-end correlation
- **Latency tracking**: Round-trip time to origin in milliseconds

Example log entry:
```json
{
  "timestamp": "2026-06-12T03:00:01.123+00:00",
  "level": "INFO",
  "event": "FORWARDED",
  "request_id": "a1b2c3d4-...",
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

## 🛑 Graceful Shutdown

- Handles `Ctrl+C` (`SIGINT`) and `SIGTERM`
- Listening socket is closed cleanly
- Thread pool drains in-flight requests before exit
- Dashboard daemon thread terminates automatically
- Zero resource leaks

---

## ⚠️ Limitations

- Full HTTP `Cache-Control` semantics are not implemented
- Chunked transfer decoding is not interpreted (relayed transparently)
- Event-driven concurrency (`asyncio`) not used
- TLS interception (MITM) is intentionally out of scope
- No WebSocket proxy support

---

## 📚 Documentation

Detailed architecture diagrams and design decisions are documented in:

```
docs/design.md
```

---

## 📄 License

This project is for educational and academic purposes.