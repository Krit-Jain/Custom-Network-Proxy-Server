"""
forwarder.py — HTTP forwarding and HTTPS tunneling.

HTTP path
─────────
  1. Check the LRU cache for GET requests.
  2. On miss, open a TCP connection to the origin server.
  3. Forward the client's request (headers + body).
  4. Stream the server's response back to the client.
  5. Store cacheable (GET 200) responses.

HTTPS path (CONNECT)
────────────────────
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
            # Signal the other end that we're done
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


# ── HTTP forwarding ──────────────────────────────────────────

def forward_http(parsed: dict, client_sock: socket.socket):
    """
    Forward an HTTP request to the origin server and relay the
    response back to the client.

    Implements cache-aside: on cache hit the response is served
    directly without contacting the origin.
    """
    method = parsed["method"]
    host = parsed["host"]
    port = parsed["port"]
    path = parsed["path"]

    cache_key = (method, host, port, path)

    # ── Cache lookup (GET only) ──────────────────────────────
    if method == "GET":
        cached = cache.get(cache_key)
        if cached:
            log_event(
                f"CACHE HIT → {host}:{port}{path}",
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
                host=host,
                action="CACHE_MISS",
            )

    # ── Connect to origin server ─────────────────────────────
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

    # ── Build the outbound request ───────────────────────────
    request_text = parsed["raw"].decode(errors="ignore")

    # Force Connection: close so the origin sends a finite response
    request_text = request_text.replace(
        "Connection: keep-alive", "Connection: close"
    )
    if "connection:" not in request_text.lower():
        request_text = request_text.replace(
            "\r\n\r\n", "\r\nConnection: close\r\n\r\n", 1
        )

    try:
        server_sock.sendall(request_text.encode())
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

    # ── Relay the response ───────────────────────────────────
    response_chunks: list[bytes] = []
    total_size = 0
    cacheable = method == "GET"

    while True:
        try:
            data = server_sock.recv(BUFFER_SIZE)
            if not data:
                break
            client_sock.sendall(data)

            if cacheable:
                total_size += len(data)
                if total_size <= MAX_OBJECT_SIZE:
                    response_chunks.append(data)
                else:
                    # Too large — stop accumulating
                    cacheable = False
                    response_chunks.clear()
        except OSError:
            break

    server_sock.close()

    # ── Store in cache ───────────────────────────────────────
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
            f"CACHE STORE → {host}:{port}{path} ({total_size} bytes)",
            host=host,
            action="CACHE_STORE",
        )
