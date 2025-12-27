import socket
import threading
from handler import handle_client

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8888


def start_proxy():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((LISTEN_HOST, LISTEN_PORT))
    sock.listen(50)

    print(f"[+] Proxy listening on {LISTEN_HOST}:{LISTEN_PORT}")

    while True:
        client, addr = sock.accept()
        threading.Thread(
            target=handle_client,
            args=(client, addr),
            daemon=True
        ).start()


if __name__ == "__main__":
    start_proxy()
