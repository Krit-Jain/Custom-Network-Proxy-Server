import socket
from parser import recv_http_request, parse_http_request
from filter import is_blocked
from logger import log_event, metrics, metrics_lock
from forwarder import tunnel, forward_http
import base64
import os


USERS_FILE = os.path.join(
    os.path.dirname(__file__),
    "..",
    "config",
    "users.txt"
)

def load_users():
    users = {}
    with open(USERS_FILE) as f:
        for line in f:
            if ":" in line:
                u, p = line.strip().split(":", 1)
                users[u] = p
    return users


def check_auth(headers):
    auth = headers.get("proxy-authorization")
    if not auth or not auth.lower().startswith("basic "):
        return False

    encoded = auth.split()[1]
    decoded = base64.b64decode(encoded).decode()

    if ":" not in decoded:
        return False

    username, password = decoded.split(":", 1)
    users = load_users()

    return users.get(username) == password


def handle_client(client_sock, client_addr):
    try:
        req = recv_http_request(client_sock)
        if not req:
            return

        parsed = parse_http_request(req)

        # -------- AUTHENTICATION CHECK --------
        if not check_auth(parsed.get("headers", {})):
            log_event(f"{client_addr} → AUTH FAILED")
            client_sock.sendall(
                b"HTTP/1.1 407 Proxy Authentication Required\r\n"
                b"Proxy-Authenticate: Basic realm=\"Proxy\"\r\n"
                b"Content-Length: 0\r\n\r\n"
            )
            return
        # -------------------------------------

        with metrics_lock:
            metrics["total"] += 1

        if is_blocked(parsed["host"]):
            with metrics_lock:
                metrics["blocked"] += 1
            log_event(f"{client_addr} → {parsed['host']}:{parsed['port']} | BLOCKED")
            client_sock.sendall(
                b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n"
            )
            return

        with metrics_lock:
            metrics["allowed"] += 1

        # HTTPS
        if parsed["method"] == "CONNECT":
            log_event(f"{client_addr} → {parsed['host']}:{parsed['port']} | CONNECT")
            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.connect((parsed["host"], parsed["port"]))
            client_sock.sendall(
                b"HTTP/1.1 200 Connection Established\r\n\r\n"
            )
            tunnel(client_sock, server_sock)
            server_sock.close()
            return

        # HTTP
        log_event(f"{client_addr} → {parsed['host']}:{parsed['port']} | HTTP")
        forward_http(parsed, client_sock)

    finally:
        client_sock.close()

