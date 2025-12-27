import socket
import threading
from urllib.parse import urlparse
import os

# ================= CONFIG =================
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8888
BUFFER_SIZE = 4096
HEADER_TERMINATOR = b"\r\n\r\n"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BLOCKLIST_FILE = os.path.join(BASE_DIR, "..", "config", "blocked_domains.txt")
# =========================================


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

    # Exact or subdomain match
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
    path = target

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
        path = parsed.path or "/"

    return {
        "method": method,
        "host": host,
        "port": port,
        "path": path,
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
    try:
        request_data = recv_http_request(client_socket)
        if not request_data:
            return

        parsed = parse_http_request(request_data)

        if is_blocked(parsed["host"]):
            print(f"[BLOCKED] {client_addr} → {parsed['host']}")
            send_forbidden(client_socket)
            return

        print(f"[ALLOWED] {client_addr} → {parsed['host']}")

        forward_request(parsed, client_socket)

    except Exception as e:
        print(f"[!] Error with {client_addr}: {e}")

    finally:
        client_socket.close()


def start_proxy():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((LISTEN_HOST, LISTEN_PORT))
    server_socket.listen(50)

    print(f"[+] Proxy with filtering listening on {LISTEN_HOST}:{LISTEN_PORT}")

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
