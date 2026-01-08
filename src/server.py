import socket
import threading
import signal
import sys

from handler import handle_client
from config_loader import get_server_config

server_socket = None

# Load server configuration
server_cfg = get_server_config()
LISTEN_HOST = server_cfg["host"]
LISTEN_PORT = server_cfg["port"]
MAX_CONN = server_cfg["max_conn"]


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
    server_socket.listen(MAX_CONN)

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


def main():
    # Register signal handlers
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    start_proxy()


if __name__ == "__main__":
    main()
