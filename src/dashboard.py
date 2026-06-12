"""
dashboard.py — Real-time monitoring dashboard server.

Runs a lightweight HTTP server on a configurable port (default 8889)
in a daemon thread alongside the proxy server.

Endpoints
─────────
  GET /           → Dashboard HTML page
  GET /api/metrics → JSON snapshot of current proxy metrics
  GET /api/logs   → JSON array of recent log entries
  GET /events     → SSE stream pushing live metrics + log events

The SSE stream pushes two event types:
  • "metrics" — full state snapshot (counters, cache, rate limiter,
                top hosts) every 1 second
  • "log"     — individual log entries as they arrive

Architecture
────────────
Uses stdlib `http.server.HTTPServer` with `ThreadingMixIn` for
concurrent SSE connections.  No external dependencies.
"""

import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

from cache import cache
from config_loader import get_dashboard_config
from dashboard_ui import DASHBOARD_HTML
from logger import (
    get_recent_logs,
    get_top_hosts,
    log_ring_buffer,
    metrics,
    metrics_lock,
    _ring_lock,
)
from rate_limiter import rate_limiter

# ── Configuration ────────────────────────────────────────────
_cfg = get_dashboard_config()
DASHBOARD_ENABLED: bool = _cfg["enabled"]
DASHBOARD_PORT: int = _cfg["port"]


class _DashboardHandler(BaseHTTPRequestHandler):
    """Handle dashboard HTTP requests and SSE streams."""

    # Suppress default stderr logging (we have our own logger)
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            self._serve_html()
        elif self.path == "/api/metrics":
            self._serve_metrics()
        elif self.path == "/api/logs":
            self._serve_logs()
        elif self.path == "/events":
            self._serve_sse()
        else:
            self.send_error(404)

    def _serve_html(self):
        """Serve the dashboard HTML page."""
        content = DASHBOARD_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def _serve_metrics(self):
        """Return current metrics as JSON."""
        data = _build_snapshot()
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _serve_logs(self):
        """Return recent log entries as JSON array."""
        logs = get_recent_logs(100)
        body = json.dumps(logs, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _serve_sse(self):
        """
        Server-Sent Events stream.

        Pushes a 'metrics' event every second with full state snapshot,
        and individual 'log' events as they arrive in the ring buffer.
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        last_log_count = len(log_ring_buffer)

        try:
            while True:
                # ── Push metrics snapshot ─────────────────────
                snapshot = _build_snapshot()
                self._send_sse_event("metrics", snapshot)

                # ── Push any new log entries ─────────────────
                with _ring_lock:
                    current_count = len(log_ring_buffer)
                    if current_count > last_log_count:
                        # New entries since last check
                        new_entries = list(log_ring_buffer)[
                            -(current_count - last_log_count):
                        ] if current_count > last_log_count else []
                        last_log_count = current_count
                    elif current_count < last_log_count:
                        # Buffer wrapped — send last few
                        new_entries = list(log_ring_buffer)[-5:]
                        last_log_count = current_count
                    else:
                        new_entries = []

                for entry in new_entries:
                    self._send_sse_event("log", entry)

                time.sleep(1)

        except (BrokenPipeError, ConnectionResetError, OSError):
            pass  # Client disconnected

    def _send_sse_event(self, event_type: str, data: dict):
        """Write a single SSE event to the response stream."""
        payload = json.dumps(data, ensure_ascii=False, default=str)
        msg = f"event: {event_type}\ndata: {payload}\n\n"
        self.wfile.write(msg.encode("utf-8"))
        self.wfile.flush()


def _build_snapshot() -> dict:
    """Build a complete state snapshot for the dashboard."""
    with metrics_lock:
        m = dict(metrics)

    return {
        "metrics": m,
        "cache": cache.stats.snapshot(),
        "rate_limiter": rate_limiter.snapshot(),
        "top_hosts": get_top_hosts(10),
    }


class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in a new thread."""
    daemon_threads = True
    allow_reuse_address = True


def start_dashboard():
    """
    Start the dashboard HTTP server in a daemon thread.

    Called by server.py before the main proxy accept-loop.
    Returns immediately. Does nothing if dashboard is disabled.
    """
    if not DASHBOARD_ENABLED:
        print("[=] Dashboard disabled in proxy.conf")
        return

    server = _ThreadedHTTPServer(("0.0.0.0", DASHBOARD_PORT), _DashboardHandler)

    thread = threading.Thread(
        target=server.serve_forever,
        name="dashboard",
        daemon=True,
    )
    thread.start()
    print(f"[+] Dashboard running at http://localhost:{DASHBOARD_PORT}")
