"""
forwarder.py — HTTP forwarding and HTTPS tunneling.

HTTP forwarding path
────────────────────
  1. Check the LRU cache for GET requests.
  2. On miss, open a TCP connection to the origin server.
  3. Build a clean outbound request:
     • Convert absolute URI to origin-form (RFC 7230 §5.3.1)
     • Strip hop-by-hop headers (RFC 7230 §6.1)
     • Inject X-Forwarded-For and Via headers
     • Forward the request body for POST/PUT/PATCH
  4. Stream the server's response back to the client.
  5. Store cacheable (GET with 200 status) responses in the LRU cache.

HTTPS tunneling path (CONNECT)
──────────────────────────────
  Bidirectional byte relay between client and server using two
  daemon threads.  The proxy never inspects TLS payloads.
"""

import socket
import threading
import time

from cache import cache
from config_loader import get_cache_config
from logger import log_event, metrics, metrics_lock

BUFFER_SIZE = 4096

_cache_cfg = get_cache_config()
MAX_OBJECT_SIZE = _cache_cfg["max_object_size"]

# ── Hop-by-hop headers (RFC 7230 §6.1) ──────────────────────
# These headers pertain to the single transport-layer connection
# and MUST NOT be forwarded to the upstream server.
HOP_BY_HOP_HEADERS = frozenset({
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "proxy-connection",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
})


# ── HTTPS tunneling ──────────────────────────────────────────

def tunnel(client_sock: socket.socket, server_sock: socket.socket):
    """
    Relay bytes bidirectionally between client and server.

    Each direction runs in its own daemon thread.  When either side
    closes the connection, the relay stops.
    """

    def _forward(src: socket.socket, dst: socket.socket):
        try:
            while True:
                data = src.recv(BUFFER_SIZE)
                if not data:
                    break
                dst.sendall(data)
        except OSError:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    t1 = threading.Thread(
        target=_forward, args=(client_sock, server_sock), daemon=True
    )
    t2 = threading.Thread(
        target=_forward, args=(server_sock, client_sock), daemon=True
    )
    t1.start()
    t2.start()
    t1.join(timeout=120)
    t2.join(timeout=120)


# ── Request building ─────────────────────────────────────────

def _build_outbound_request(parsed: dict) -> bytes:
    """
    Construct the HTTP request bytes to send to the origin server.

    Transforms the client's proxy-style request into a standard
    origin-form request and strips hop-by-hop headers per RFC 7230.
    Injects X-Forwarded-For (if client_ip available) and Via.
    Forwards the request body for methods that include one.
    """
    method = parsed["method"]
    path = parsed["path"]
    host = parsed["host"]
    port = parsed["port"]
    headers = parsed["headers"]
    body = parsed.get("body", b"")
    content_length = parsed.get("content_length")

    # ── Request line (origin-form) ───────────────────────────
    request_line = f"{method} {path} HTTP/1.1\r\n"

    # ── Filter and rebuild headers ───────────────────────────
    out_headers: list[str] = []

    # Ensure Host header is present and correct
    if port in (80, 443):
        out_headers.append(f"Host: {host}")
    else:
        out_headers.append(f"Host: {host}:{port}")

    for key, value in headers.items():
        # Skip hop-by-hop headers
        if key in HOP_BY_HOP_HEADERS:
            continue
        # Skip Host (we already set it above)
        if key == "host":
            continue
        out_headers.append(f"{key}: {value}")

    # Force Connection: close for finite response
    out_headers.append("Connection: close")

    # Add X-Forwarded-For if we have a client IP
    client_ip = parsed.get("client_ip")
    existing_xff = headers.get("x-forwarded-for")
    if client_ip:
        if existing_xff:
            out_headers.append(
                f"X-Forwarded-For: {existing_xff}, {client_ip}"
            )
        else:
            out_headers.append(f"X-Forwarded-For: {client_ip}")
    elif existing_xff:
        out_headers.append(f"X-Forwarded-For: {existing_xff}")

    # Add Via header (RFC 7230 §5.7.1)
    out_headers.append("Via: 1.1 proxy")

    # ── Assemble ─────────────────────────────────────────────
    header_block = request_line + "\r\n".join(out_headers) + "\r\n\r\n"
    request_bytes = header_block.encode("utf-8")

    # ── Append body for POST/PUT/PATCH ───────────────────────
    if method in ("POST", "PUT", "PATCH") and body:
        request_bytes += body
    elif content_length and content_length > 0 and body:
        # Other methods with a body (rare but valid)
        request_bytes += body

    return request_bytes


def _parse_response_status(first_chunk: bytes) -> int | None:
    """
    Extract the HTTP status code from the first chunk of a response.

    Returns the status code as an int, or None if it can't be parsed.
    """
    try:
        status_line = first_chunk.split(b"\r\n", 1)[0]
        parts = status_line.split(None, 2)
        if len(parts) >= 2:
            return int(parts[1])
    except (ValueError, IndexError):
        pass
    return None


# ── HTTP forwarding ──────────────────────────────────────────

def forward_http(parsed: dict, client_sock: socket.socket):
    """
    Forward an HTTP request to the origin server and relay the
    response back to the client.

    Implements cache-aside: on cache hit the response is served
    directly without contacting the origin.

    Measures end-to-end latency and logs it for observability.
    """
    method = parsed["method"]
    host = parsed["host"]
    port = parsed["port"]
    path = parsed["path"]
    request_id = parsed.get("request_id", "")

    cache_key = (method, host, port, path)

    # ── Cache lookup (GET only) ──────────────────────────────
    if method == "GET":
        cached = cache.get(cache_key)
        if cached:
            log_event(
                f"CACHE HIT → {host}:{port}{path}",
                request_id=request_id,
                host=host,
                action="CACHE_HIT",
            )
            with metrics_lock:
                metrics["cached"] += 1
            try:
                client_sock.sendall(cached["response"])
            except OSError:
                pass
            return
        else:
            log_event(
                f"CACHE MISS → {host}:{port}{path}",
                request_id=request_id,
                host=host,
                action="CACHE_MISS",
            )

    # ── Connect to origin server ─────────────────────────────
    t_start = time.monotonic()

    try:
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.settimeout(10)
        server_sock.connect((host, port))
    except OSError:
        client_sock.sendall(
            b"HTTP/1.1 502 Bad Gateway\r\n"
            b"Connection: close\r\n"
            b"Content-Length: 0\r\n\r\n"
        )
        with metrics_lock:
            metrics["errors"] += 1
        return

    # ── Build and send outbound request ──────────────────────
    outbound = _build_outbound_request(parsed)

    try:
        server_sock.sendall(outbound)
    except OSError:
        server_sock.close()
        client_sock.sendall(
            b"HTTP/1.1 502 Bad Gateway\r\n"
            b"Connection: close\r\n"
            b"Content-Length: 0\r\n\r\n"
        )
        with metrics_lock:
            metrics["errors"] += 1
        return

    # ── Stream the response back ─────────────────────────────
    response_chunks: list[bytes] = []
    total_size = 0
    cacheable = method == "GET"
    status_code = None

    while True:
        try:
            data = server_sock.recv(BUFFER_SIZE)
            if not data:
                break
            client_sock.sendall(data)

            # Extract status code from the first chunk
            if status_code is None:
                status_code = _parse_response_status(data)
                # Only cache 200 OK responses
                if status_code and status_code != 200:
                    cacheable = False

            if cacheable:
                total_size += len(data)
                if total_size <= MAX_OBJECT_SIZE:
                    response_chunks.append(data)
                else:
                    cacheable = False
                    response_chunks.clear()
        except OSError:
            break

    server_sock.close()

    latency_ms = round((time.monotonic() - t_start) * 1000, 1)

    # ── Store in cache (GET 200 only) ────────────────────────
    if cacheable and response_chunks:
        full_response = b"".join(response_chunks)
        cache.put(
            cache_key,
            {
                "response": full_response,
                "timestamp": time.time(),
                "size": total_size,
            },
        )
        log_event(
            f"CACHE STORE → {host}:{port}{path} ({total_size}B, {latency_ms}ms)",
            request_id=request_id,
            host=host,
            action="CACHE_STORE",
            latency_ms=latency_ms,
            bytes_transferred=total_size,
        )
    else:
        log_event(
            f"FORWARDED → {host}:{port}{path} [{status_code}] ({total_size}B, {latency_ms}ms)",
            request_id=request_id,
            host=host,
            action="FORWARDED",
            status_code=status_code,
            latency_ms=latency_ms,
            bytes_transferred=total_size,
        )
