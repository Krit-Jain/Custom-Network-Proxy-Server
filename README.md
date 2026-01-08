# Custom Network Proxy Server

## 📌 Overview

This project implements a **custom forward proxy server** supporting both **HTTP and HTTPS traffic**.  
It is built using low-level socket programming and demonstrates core networking concepts such as concurrency, request parsing, filtering, caching, logging, and secure tunneling.

The proxy follows a **modular and extensible design**, making it suitable for academic evaluation and further enhancement.

---

## ✨ Features

- HTTP proxy support
- HTTPS proxy support using `CONNECT` tunneling
- Thread-per-connection concurrency model
- Domain and IP-based filtering
- Configurable blocklist
- Detailed logging with log rotation
- Optional in-memory HTTP response caching (LRU)
- Thread-safe shared components
- Graceful shutdown on SIGINT/SIGTERM
- Tested using `curl`-based scripts

---

## 🗂️ Project Structure

```bash
custom-network-proxy-server/
├── src/
│ ├── server.py # Main server loop & graceful shutdown
│ ├── handler.py # Per-client request handling
│ ├── parser.py # HTTP request parsing
│ ├── forwarder.py # HTTP forwarding & HTTPS tunneling
│ ├── filter.py # Domain/IP filtering
│ ├── cache.py # LRU cache implementation
│ └── logger.py # Logging, metrics & log rotation
│
├── config/
│ └── blocked_domains.txt
│ └── proxy.conf
│ └── users.txt
│
├── logs/
│ └── proxy.log
│
├── tests/
│ ├── test_http_allowed.sh
│ ├── test_http_blocked.sh
│ ├── test_https_allowed.sh
│ ├── test_https_blocked.sh
│ ├── test_cache.sh
│ └── test_concurrency.sh
│
├── docs/
│ └── design.md
│
├── .gitignore
└── README.md
```

---

## ⚙️ Requirements

- Python **3.10+**
- Linux / macOS / WSL recommended
- `curl` installed for testing

---

## ▶️ How to Run

### 1️⃣ Start the Proxy Server

From the project root:

```bash
python3 src/server.py
```
Expected output:

```bash
[+] Proxy listening on 0.0.0.0:8888
```
### 2️⃣ Use the Proxy with curl

HTTP request:

```bash
curl -x localhost:8888 http://neverssl.com
```

HTTPS request:

```bash
curl -x localhost:8888 https://neverssl.com
```
---

## 🔒 Filtering Configuration

Blocked domains and IPs are defined in:

```bash
config/blocked_domains.txt
```

Example:

```bash
example.com
badsite.org
192.0.2.5
```
## 📜 Logging & Metrics

- Logs are written to:
```bash
logs/proxy.log
```

### Each log entry includes:
- Timestamp
- Client IP and port
- Destination host and port
- Request type
- Action (`ALLOWED`, `BLOCKED`, `CACHE HIT`, `CACHE MISS`)

### Log Rotation
- Logs are automatically rotated when exceeding a fixed size limit
- Prevents unbounded disk usage

---

## 🧠 Caching

- Optional **in-memory LRU cache**
- Applied only to **HTTP GET** requests
- **HTTPS traffic is not cached**
- Cache is **thread-safe**
- Cache activity is logged

---

## 🧪 Testing

All functionality is tested using **curl-based scripts**.

### Run Tests

Start the proxy in one terminal:
```bash
python3 src/server.py
```
Run tests in another terminal:
```bash
./tests/test_http_allowed.sh
./tests/test_http_blocked.sh
./tests/test_https_allowed.sh
./tests/test_https_blocked.sh
./tests/test_cache.sh
./tests/test_concurrency.sh
```
### Tests Cover:
- HTTP allowed requests
- HTTP blocked requests
- HTTPS CONNECT tunneling
- HTTPS blocking
- Cache hit/miss behavior
- Concurrent client handling

## 🔐 Proxy Authentication

The proxy implements **Basic Proxy Authentication** using the
`Proxy-Authorization` HTTP header.

### Authentication Mechanism
- Clients must authenticate using a **username and password**
- Credentials are sent using HTTP Basic authentication
- Unauthorized requests receive **HTTP/1.1 407 Proxy Authentication Required**

### Configuration

User credentials are defined in:
```bash
config/users.txt
```
Format:
```bash
username:password
```

Example:
```bash
admin:admin123
user:test123
```

> Credentials are stored in plain text for simplicity.  
> Password hashing and stronger authentication schemes can be added as a future enhancement.

### Behavior
- Authentication is enforced **before filtering and forwarding**
- Both **HTTP** and **HTTPS (CONNECT)** requests require authentication
- Failed authentication attempts are logged

### Example Usage

```bash
curl -x localhost:8888 -U admin:admin123 http://neverssl.com
curl -x localhost:8888 -U admin:admin123 https://neverssl.com
```
## ⚙️ Server Configuration

Server behavior is configured using a plain text configuration file:

```bash
config/proxy.conf
```

The configuration file allows setting:
- Listening address and port
- Maximum concurrent connections
- Log file path and rotation size
- Cache size and object limits

This design separates configuration from code and improves flexibility.

## 🛑 Graceful Shutdown

- Handles `Ctrl + C` (SIGINT) and `SIGTERM`
- Listening socket is closed cleanly
- Active client-handling threads terminate naturally
- Prevents resource leaks and ensures clean server shutdown

## ⚠️ Limitations
- Full HTTP cache-control semantics are not implemented
- Chunked transfer decoding is not interpreted
- Event-driven concurrency (asyncio) is not used
- TLS interception is intentionally out of scope

## 📚 Documentation
Detailed design and architecture documentation is available in:

```bash
docs/design.md
```