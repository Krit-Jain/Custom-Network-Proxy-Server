import socket
import threading
from urllib.parse import urlparse
import os
from datetime import datetime

# ================= CONFIG =================
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8888
BUFFER_SIZE = 4096
HEADER_TERMINATOR = b"\r\n\r\n"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BLOCKLIST_FILE = os.path.join(BASE_DIR, "..", "config", "blocked_domains.txt")
LOG_DIR = os.path.join(BASE_DIR, "..", "logs")
LOG_FILE = os.path.join(LOG_DIR, "proxy.log")
# =========================================


# ================= METRICS =================
metrics = {
    "total": 0,
    "allowed": 0,
    "blocked": 0
}
metrics_lock = threading.Lock()
# ===========================================


def ensure_log_dir():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)


def log_event(message):
    ensure_log_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {message}\n"

    with open(LOG_FILE, "a") as f:
        f.write(entry)


def load_blocklist():
    blocked = set()
    if not os.path.exists(BLOCKLIST_FILE):
        return blocked

    with open(BLOCKLIST_FILE, "r") as f:
        for line in f:
            line = line.strip().lower()
            if not line or line.startswith("#"):
                continue
            blocked.add(line)
    return blocked


BLOCKED_SET = load_blocklist()


def is_blocked(host):
    if not host:
        return False

    host = host.lower()
    for blocked in BLOCKED_SET:
        if host == blocked or host.endswith("." + blocked):
            return True
    return False


def recv_http_request(client_socket):
    data = b""
    while HEADER_TERMINATOR not in data:
        chunk = client_socket.recv(BUFFER_SIZE)
        if not chunk:
            break
        data += chunk
    return data


def parse_http_request(request_bytes):
    request_text = request_bytes.decode(errors="ignore")
    lines = request_text.split("\r\n")

    request_line = lines[0]
    method, target, version = request_line.split()

    host = None
    port = 80

    for line in lines[1:]:
        if line.lower().startswith("host:"):
            host_value = line.split(":", 1)[1].strip()
            if ":" in host_value:
                host, port = host_value.split(":")
                port = int(port)
            else:
                host = host_value
            break

    if target.startswith("http://") or target.startswith("https://"):
        parsed = urlparse(target)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

    return {
        "method": method,
        "host": host,
        "port": port,
        "raw": request_bytes
    }


def send_forbidden(client_socket):
    response = (
        "HTTP/1.1 403 Forbidden\r\n"
        "Content-Type: text/plain\r\n"
        "Content-Length: 16\r\n"
        "Connection: close\r\n"
        "\r\n"
        "Access Forbidden"
    )
    client_socket.sendall(response.encode())


def forward_request(parsed_request, client_socket):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        server_socket.connect((parsed_request["host"], parsed_request["port"]))
        server_socket.sendall(parsed_request["raw"])

        while True:
            response_chunk = server_socket.recv(BUFFER_SIZE)
            if not response_chunk:
                break
            client_socket.sendall(response_chunk)

    finally:
        server_socket.close()


def handle_client(client_socket, client_addr):
    global metrics

    try:
        request_data = recv_http_request(client_socket)
        if not request_data:
            return

        parsed = parse_http_request(request_data)
        client_id = f"{client_addr[0]}:{client_addr[1]}"
        target_id = f"{parsed['host']}:{parsed['port']}"

        with metrics_lock:
            metrics["total"] += 1

        if is_blocked(parsed["host"]):
            with metrics_lock:
                metrics["blocked"] += 1

            log_event(f"{client_id} → {target_id} | {parsed['method']} | BLOCKED")
            send_forbidden(client_socket)
            return

        with metrics_lock:
            metrics["allowed"] += 1

        log_event(f"{client_id} → {target_id} | {parsed['method']} | ALLOWED")
        forward_request(parsed, client_socket)

    except Exception as e:
        log_event(f"ERROR {client_addr} | {e}")

    finally:
        client_socket.close()


def start_proxy():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((LISTEN_HOST, LISTEN_PORT))
    server_socket.listen(50)

    print(f"[+] Proxy with logging listening on {LISTEN_HOST}:{LISTEN_PORT}")

    while True:
        client_socket, client_addr = server_socket.accept()

        thread = threading.Thread(
            target=handle_client,
            args=(client_socket, client_addr),
            daemon=True
        )
        thread.start()


if __name__ == "__main__":
    start_proxy()
