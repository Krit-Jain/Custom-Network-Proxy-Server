"""
handler.py — Per-connection request handler.

Orchestrates the full lifecycle of a single client connection:
  1. Receive and parse the HTTP request
  2. Enforce per-IP rate limiting (token bucket → 429)
  3. Authenticate the client (Basic Proxy-Authorization)
  4. Check the domain/IP blocklist
  5. Dispatch to HTTPS CONNECT tunneling, or
  6. Dispatch to HTTP forwarding
  7. Log the outcome

All exceptions are caught to prevent one bad connection from
affecting other clients sharing the thread pool.
"""

import base64
import os
import socket

from config_loader import get_server_config
from filter import is_blocked
from forwarder import forward_http, tunnel
from logger import (
    log_event,
    metrics,
    metrics_lock,
    record_host,
)
from parser import parse_http_request, recv_http_request
from rate_limiter import rate_limiter, RATE_LIMIT_ENABLED

# ── Load user credentials ────────────────────────────────────
USERS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "config",
    "users.txt",
)


def _load_users() -> dict[str, str]:
    """Read username:password pairs from config/users.txt."""
    users: dict[str, str] = {}
    try:
        with open(USERS_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    username, password = line.split(":", 1)
                    users[username.strip()] = password.strip()
    except FileNotFoundError:
        pass
    return users


USERS = _load_users()


def _check_auth(headers: dict) -> bool:
    """Validate Basic Proxy-Authorization header against USERS."""
    auth = headers.get("proxy-authorization")
    if not auth or not auth.lower().startswith("basic "):
        return False

    try:
        encoded = auth.split(None, 1)[1]
        decoded = base64.b64decode(encoded).decode("utf-8")
    except Exception:
        return False

    if ":" not in decoded:
        return False

    username, password = decoded.split(":", 1)
    return USERS.get(username) == password


def handle_client(client_sock: socket.socket, client_addr: tuple):
    """
    Handle a single client connection end-to-end.

    This function is submitted to the ThreadPoolExecutor by server.py.
    It must never raise — all exceptions are logged and swallowed.
    """
    try:
        # ── 1. Receive raw HTTP request ──────────────────────
        raw = recv_http_request(client_sock)
        if not raw:
            return

        parsed = parse_http_request(raw)
        if not parsed:
            client_sock.sendall(
                b"HTTP/1.1 400 Bad Request\r\n"
                b"Connection: close\r\n"
                b"Content-Length: 0\r\n\r\n"
            )
            with metrics_lock:
                metrics["errors"] += 1
            return

        host = parsed["host"]
        port = parsed["port"]
        method = parsed["method"]
        request_id = parsed.get("request_id", "")

        # Inject client IP so forwarder can build X-Forwarded-For
        parsed["client_ip"] = client_addr[0]

        # Count every inbound request
        with metrics_lock:
            metrics["total"] += 1

        # Track per-host stats
        record_host(host)

        # ── 2. Rate limiting (before auth — fail-fast) ───────
        client_ip = client_addr[0]
        if RATE_LIMIT_ENABLED and not rate_limiter.is_allowed(client_ip):
            retry_after = rate_limiter.get_retry_after(client_ip)
            with metrics_lock:
                metrics["rate_limited"] += 1
            log_event(
                f"[{request_id[:8]}] {client_addr} → RATE LIMITED "
                f"(retry after {retry_after}s)",
                request_id=request_id,
                client_ip=client_ip,
                host=host,
                port=port,
                method=method,
                action="RATE_LIMITED",
            )
            client_sock.sendall(
                b"HTTP/1.1 429 Too Many Requests\r\n"
                b"Connection: close\r\n"
                b"Content-Length: 0\r\n"
                + f"Retry-After: {retry_after}\r\n".encode()
                + b"\r\n"
            )
            return

        # ── 3. Authentication ────────────────────────────────
        if not _check_auth(parsed.get("headers", {})):
            log_event(
                f"[{request_id[:8]}] {client_addr} → AUTH FAILED",
                request_id=request_id,
                client_ip=client_addr[0],
                action="AUTH_FAILED",
            )
            client_sock.sendall(
                b"HTTP/1.1 407 Proxy Authentication Required\r\n"
                b'Proxy-Authenticate: Basic realm="Proxy"\r\n'
                b"Connection: close\r\n"
                b"Content-Length: 0\r\n\r\n"
            )
            return

        # ── 4. Domain / IP filtering ─────────────────────────
        if is_blocked(host):
            with metrics_lock:
                metrics["blocked"] += 1
            log_event(
                f"[{request_id[:8]}] {client_addr} → {host}:{port} | BLOCKED",
                request_id=request_id,
                client_ip=client_addr[0],
                host=host,
                port=port,
                method=method,
                action="BLOCKED",
            )
            client_sock.sendall(
                b"HTTP/1.1 403 Forbidden\r\n"
                b"Connection: close\r\n"
                b"Content-Length: 0\r\n\r\n"
            )
            return

        with metrics_lock:
            metrics["allowed"] += 1

        # ── 5. HTTPS CONNECT tunneling ───────────────────────
        if method == "CONNECT":
            log_event(
                f"[{request_id[:8]}] {client_addr} → {host}:{port} | CONNECT",
                request_id=request_id,
                client_ip=client_addr[0],
                host=host,
                port=port,
                method=method,
                action="CONNECT",
            )
            try:
                server_sock = socket.socket(
                    socket.AF_INET, socket.SOCK_STREAM
                )
                server_sock.settimeout(10)
                server_sock.connect((host, port))
                client_sock.sendall(
                    b"HTTP/1.1 200 Connection Established\r\n\r\n"
                )
                tunnel(client_sock, server_sock)
            except OSError:
                client_sock.sendall(
                    b"HTTP/1.1 502 Bad Gateway\r\n"
                    b"Connection: close\r\n"
                    b"Content-Length: 0\r\n\r\n"
                )
                with metrics_lock:
                    metrics["errors"] += 1
            finally:
                try:
                    server_sock.close()
                except Exception:
                    pass
            return

        # ── 6. HTTP forwarding ───────────────────────────────
        log_event(
            f"[{request_id[:8]}] {client_addr} → {host}:{port} | {method}",
            request_id=request_id,
            client_ip=client_addr[0],
            host=host,
            port=port,
            method=method,
            action="FORWARD",
        )
        forward_http(parsed, client_sock)

    except Exception as exc:
        # Never let an exception escape — it would kill a pool thread
        with metrics_lock:
            metrics["errors"] += 1
        try:
            log_event(
                f"{client_addr} → INTERNAL ERROR: {exc}",
                action="ERROR",
            )
        except Exception:
            pass

    finally:
        try:
            client_sock.close()
        except Exception:
            pass
