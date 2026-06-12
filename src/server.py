"""
server.py — Proxy server entry point.

Creates a listening TCP socket, accepts client connections, and
dispatches each connection to a bounded ThreadPoolExecutor.

Concurrency model
─────────────────
A fixed-size thread pool (configurable via proxy.conf) prevents
unbounded thread creation under load.  When the pool is saturated,
new connections are queued by the executor.  The OS-level backlog
(socket.listen) acts as a secondary bound.

Graceful shutdown
─────────────────
SIGINT and SIGTERM close the listening socket, which causes the
accept-loop to exit.  The thread pool is then shut down with
wait=True so that in-flight requests finish before the process
terminates.
"""

import signal
import socket
import sys
from concurrent.futures import ThreadPoolExecutor

from config_loader import get_server_config
from dashboard import start_dashboard
from handler import handle_client

# ── Load configuration ───────────────────────────────────────
_cfg = get_server_config()
LISTEN_HOST: str = _cfg["host"]
LISTEN_PORT: int = _cfg["port"]
MAX_CONN: int = _cfg["max_conn"]
POOL_SIZE: int = _cfg["thread_pool_size"]

# ── Module-level references for signal handler ───────────────
_server_socket: socket.socket | None = None
_thread_pool: ThreadPoolExecutor | None = None


def _graceful_shutdown(signum, frame):
    """Close the listening socket and drain the thread pool."""
    print("\n[+] Shutting down proxy gracefully...")

    global _server_socket, _thread_pool

    if _server_socket:
        try:
            _server_socket.close()
        except OSError:
            pass

    if _thread_pool:
        _thread_pool.shutdown(wait=True, cancel_futures=True)

    sys.exit(0)


def start_proxy():
    """Bind, listen, and accept connections in the main thread."""
    global _server_socket, _thread_pool

    # ── Create listening socket ──────────────────────────────
    _server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _server_socket.bind((LISTEN_HOST, LISTEN_PORT))
    _server_socket.listen(MAX_CONN)

    # ── Create bounded thread pool ───────────────────────────
    _thread_pool = ThreadPoolExecutor(
        max_workers=POOL_SIZE,
        thread_name_prefix="proxy-worker",
    )

    # ── Start dashboard server (daemon thread) ───────────────
    start_dashboard()

    print(
        f"[+] Proxy listening on {LISTEN_HOST}:{LISTEN_PORT}  "
        f"(pool={POOL_SIZE})"
    )

    # ── Accept loop ──────────────────────────────────────────
    while True:
        try:
            client_sock, client_addr = _server_socket.accept()
            _thread_pool.submit(handle_client, client_sock, client_addr)
        except OSError:
            # Raised when _server_socket is closed during shutdown
            break


def main():
    """Register signal handlers and start the proxy."""
    signal.signal(signal.SIGINT, _graceful_shutdown)
    signal.signal(signal.SIGTERM, _graceful_shutdown)

    start_proxy()


if __name__ == "__main__":
    main()
