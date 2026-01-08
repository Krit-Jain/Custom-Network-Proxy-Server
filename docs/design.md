# Design and Implementation of a Custom Network Proxy Server

## 1. Overview

This project implements a custom forward proxy server that supports HTTP and HTTPS traffic.  
The proxy is capable of handling multiple concurrent client connections, filtering requests based on configurable rules, logging and rotating traffic logs, caching HTTP responses, and gracefully shutting down on termination signals.

The implementation focuses on correctness, modularity, and adherence to core networking principles.

---

## 2. Architecture

The proxy follows a modular architecture where each component has a single responsibility.

### Components

- **server.py**
  - Initializes the listening TCP socket
  - Accepts client connections
  - Spawns a thread per connection
  - Handles graceful shutdown

- **handler.py**
  - Handles a single client connection
  - Performs authentication
  - Parses requests
  - Applies filtering rules
  - Dispatches requests to HTTP forwarding or HTTPS tunneling

- **parser.py**
  - Parses HTTP request lines and headers
  - Extracts method, host, port, and normalized path
  - Supports absolute and relative URI formats

- **forwarder.py**
  - Forwards HTTP requests to origin servers
  - Streams responses back to clients
  - Implements optional HTTP response caching

- **filter.py**
  - Loads blocked domains and IPs from configuration
  - Performs canonicalized matching
  - Enforces access control rules

- **cache.py**
  - Implements an in-memory LRU cache
  - Thread-safe access for concurrent requests

- **logger.py**
  - Records proxy activity
  - Implements size-based log rotation
  - Maintains request metrics

### High-Level Architecture Diagram

                        ┌────────────────────┐
                        │       Client       │
                        │  (Browser / curl)  │
                        └─────────┬──────────┘
                                  │
                                  │ HTTP / HTTPS Request
                                  ▼
                    ┌─────────────────────────────┐
                    │        server.py            │
                    │  - TCP socket (listen)      │
                    │  - Accept connections       │
                    │  - Thread-per-connection    │
                    └─────────┬───────────────────┘
                              │
                              │ New thread
                              ▼
                  ┌────────────────────────────────┐
                  │          handler.py            │
                  │  - Receive raw request         │
                  │  - Authentication check        │
                  │  - Metrics update              │
                  │  - Dispatch based on method    │
                  └─────────┬───────────┬──────────┘
                            │           │
                            │           │
            HTTP Request    │           │ HTTPS CONNECT
                            │           │
                            ▼           ▼
          ┌────────────────────────┐   ┌────────────────────────┐
          │        filter.py       │   │        filter.py       │
          │  - Domain/IP blocking  │   │  - Domain/IP blocking  │
          └─────────┬──────────────┘   └─────────┬──────────────┘
                    │                            │
            Allowed │                            │ Allowed
                    ▼                            ▼
      ┌────────────────────────────┐   ┌────────────────────────────┐
      │       forwarder.py         │   │       forwarder.py         │
      │  (HTTP Forwarding Path)    │   │   (HTTPS Tunnel Path)      │
      │                            │   │                            │
      │  ┌─────────────────────┐   │   │  ┌─────────────────────┐   │
      │  │      cache.py       │ ◄─┼───┼─►│   tunnel() threads  │   │
      │  │  - LRU cache        │   │   │  │  - Bidirectional I/O│   │
      │  └─────────────────────┘   │   │  └─────────────────────┘   │
      │                            │   │                            │
      └─────────┬──────────────────┘   └─────────┬──────────────────┘
                │                                │
                │                                │
                ▼                                ▼
        ┌────────────────────┐          ┌────────────────────┐
        │   Origin Server    │          │   Origin Server    │
        │   (HTTP Server)    │          │   (HTTPS Server)   │
        └─────────┬──────────┘          └─────────┬──────────┘
                  │                               │
                  │ Response                      │ Encrypted Stream
                  ▼                               ▼
                  ┌───────────────────────────────┐
                  │            logger.py          │
                  │  - Log requests               │
                  │  - Log cache hit/miss         │
                  │  - Rotate logs                │
                  └───────────────────────────────┘

---

## 3. Request Flow

### HTTP Request Flow

1. Client sends an HTTP request to the proxy.
2. The proxy parses the request to extract destination information.
3. Filtering rules are applied.
4. If allowed:
   - Cache is checked for GET requests.
   - On cache hit, the response is served directly.
   - On cache miss, the request is forwarded to the origin server.
5. The server response is streamed back to the client.
6. Eligible responses are stored in cache.

---

### HTTPS Request Flow (CONNECT)

1. Client sends a `CONNECT host:port` request.
2. The proxy validates the destination against filter rules.
3. A TCP connection to the destination server is established.
4. The proxy responds with `HTTP/1.1 200 Connection Established`.
5. Encrypted bytes are forwarded bidirectionally without inspection.

---

## 4. Concurrency Model

The proxy uses a **thread-per-connection** model.

- Each client connection is handled by a dedicated thread.
- This approach simplifies request handling and is suitable for moderate workloads.
- Shared resources (cache and logs) are protected using thread locks.

---
## 5. Authentication

The proxy enforces **Basic Proxy Authentication** for all incoming requests.

- Clients must provide credentials using the `Proxy-Authorization` header
- Unauthorized requests receive `HTTP/1.1 407 Proxy Authentication Required`
- Authentication is applied uniformly to both HTTP and HTTPS (CONNECT) requests
- Credentials are configured via an external configuration file
- Authentication prevents unauthorized use of the proxy service

Authentication is performed before request filtering and forwarding to ensure secure access control.

## 6. Filtering and Configuration
Filtering and server behavior are configured using external configuration files.
- Server parameters such as listening address, port, logging path, and cache limits are defined in a separate configuration file.
- Filtering rules are defined in a simple text file (`blocked_domains.txt`).
- Each line specifies a blocked domain or IP address.
- Hostnames are normalized (lowercase, trimmed) before matching.
- Subdomain blocking is supported using suffix matching.
- Blocked requests receive an `HTTP/1.1 403 Forbidden` response.

---

## 7. Logging and Metrics

- All requests are logged with:
  - Timestamp
  - Client IP and port
  - Destination host and port
  - Request type
  - Action (allowed, blocked, cache hit/miss)
- Logs are rotated when exceeding a fixed size threshold.
- Basic metrics track total, allowed, and blocked requests.

---

## 8. Caching

- The proxy implements optional HTTP response caching.
- Only GET requests are cached.
- Responses are cached only when they are finite and below a configurable size threshold.
- HTTPS traffic is excluded from caching.
- An LRU eviction policy ensures bounded memory usage.
- Cache access is thread-safe.
- Cache hits and misses are explicitly logged.

---

## 9. Graceful Shutdown

- Signal handlers are registered for SIGINT and SIGTERM.
- On shutdown:
  - The listening socket is closed.
  - Active threads are allowed to terminate naturally.
- This prevents resource leaks and ensures clean termination.

---

## 10. Limitations and Future Work

- Full HTTP cache-control semantics are not implemented.
- Chunked transfer decoding is not interpreted.
- Event-driven concurrency models (e.g., asyncio) could improve scalability.
- TLS interception is intentionally out of scope.

---

## 11. Conclusion

This project demonstrates a functional and extensible proxy server built using low-level networking primitives.  
The modular design allows easy extension while maintaining clarity and correctness.
