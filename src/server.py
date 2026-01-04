import socket
import threading
from handler import handle_client
import signal
import sys

server_socket = None

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8888


def graceful_shutdown(signum, frame):
    print("\n[+] Shutting down proxy gracefully...")
    global server_socket
    if server_socket:
        server_socket.close()
    sys.exit(0)


def start_proxy():
    global server_socket

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((LISTEN_HOST, LISTEN_PORT))
    server_socket.listen(50)

    print(f"[+] Proxy listening on {LISTEN_HOST}:{LISTEN_PORT}")

    while True:
        try:
            client, addr = server_socket.accept()
            threading.Thread(
                target=handle_client,
                args=(client, addr),
                daemon=True
            ).start()
        except OSError:
            # Raised when server_socket is closed during shutdown
            break


if __name__ == "__main__":
    # Register signals BEFORE starting server loop
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    start_proxy()
