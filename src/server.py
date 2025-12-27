import socket
from urllib.parse import urlparse

# ================= CONFIG =================
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8888
BUFFER_SIZE = 4096
HEADER_TERMINATOR = b"\r\n\r\n"
# =========================================


def recv_http_request(client_socket):
    """
    Receive data until full HTTP headers are read (\r\n\r\n).
    """
    data = b""
    while HEADER_TERMINATOR not in data:
        chunk = client_socket.recv(BUFFER_SIZE)
        if not chunk:
            break
        data += chunk
    return data


def parse_http_request(request_bytes):
    """
    Parse HTTP request and extract method, host, port, path.
    """
    try:
        request_text = request_bytes.decode(errors="ignore")
        lines = request_text.split("\r\n")

        # Request line
        request_line = lines[0]
        method, target, version = request_line.split()

        host = None
        port = 80
        path = target

        # Extract Host header
        for line in lines[1:]:
            if line.lower().startswith("host:"):
                host_value = line.split(":", 1)[1].strip()
                if ":" in host_value:
                    host, port = host_value.split(":")
                    port = int(port)
                else:
                    host = host_value
                break

        # Handle absolute URI
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

    except Exception as e:
        print(f"[!] Failed to parse request: {e}")
        return None


def start_proxy():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((LISTEN_HOST, LISTEN_PORT))
    server_socket.listen(10)

    print(f"[+] Proxy listening on {LISTEN_HOST}:{LISTEN_PORT}")

    while True:
        client_socket, client_addr = server_socket.accept()
        print(f"\n[+] Connection from {client_addr}")

        try:
            request_data = recv_http_request(client_socket)
            if not request_data:
                client_socket.close()
                continue

            parsed = parse_http_request(request_data)
            if not parsed:
                client_socket.close()
                continue

            print("----- Parsed Request -----")
            print(f"Method : {parsed['method']}")
            print(f"Host   : {parsed['host']}")
            print(f"Port   : {parsed['port']}")
            print(f"Path   : {parsed['path']}")
            print("--------------------------")

            # Temporary response (until Phase 3)
            response_body = "HTTP Request Parsed Successfully"
            response = (
                "HTTP/1.1 200 OK\r\n"
                f"Content-Length: {len(response_body)}\r\n"
                "Content-Type: text/plain\r\n"
                "Connection: close\r\n"
                "\r\n"
                f"{response_body}"
            )

            client_socket.sendall(response.encode())

        except Exception as e:
            print(f"[!] Error: {e}")

        finally:
            client_socket.close()
            print(f"[-] Closed connection {client_addr}")


if __name__ == "__main__":
    start_proxy()
