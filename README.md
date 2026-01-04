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
