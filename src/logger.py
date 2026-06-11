"""
logger.py — Centralized logging with rotation and metrics.

Uses Python's stdlib logging module with RotatingFileHandler for
automatic multi-file log rotation.  Maintains in-memory request
metrics with thread-safe counters and a ring buffer of recent log
entries for the monitoring dashboard.
"""

import logging
import logging.handlers
import os
import threading
from collections import deque
from datetime import datetime, timezone

from config_loader import get_logging_config

# ── Load configuration ───────────────────────────────────────
_cfg = get_logging_config()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "..", _cfg["log_file"])
LOG_DIR = os.path.dirname(LOG_FILE)
MAX_LOG_SIZE = _cfg["max_size"]
BACKUP_COUNT = _cfg["backup_count"]

# Ensure the log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# ── Configure stdlib logger with RotatingFileHandler ─────────
_logger = logging.getLogger("proxy")
_logger.setLevel(logging.DEBUG)
_logger.propagate = False

# File handler (rotates automatically)
_file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE,
    maxBytes=MAX_LOG_SIZE,
    backupCount=BACKUP_COUNT,
    encoding="utf-8",
)
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(
    logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
_logger.addHandler(_file_handler)

# Stderr handler (human-readable, for development)
_stderr_handler = logging.StreamHandler()
_stderr_handler.setLevel(
    getattr(logging, _cfg["log_level"], logging.INFO)
)
_stderr_handler.setFormatter(
    logging.Formatter("  %(message)s")
)
_logger.addHandler(_stderr_handler)

# ── Metrics ──────────────────────────────────────────────────
metrics = {
    "total": 0,
    "allowed": 0,
    "blocked": 0,
    "cached": 0,
    "rate_limited": 0,
    "errors": 0,
}

metrics_lock = threading.Lock()

# Per-host request counters for "top hosts" dashboard panel
host_counters: dict[str, int] = {}
host_counters_lock = threading.Lock()

# ── Ring buffer of recent log entries (for dashboard) ────────
_RING_BUFFER_SIZE = 200
log_ring_buffer: deque[dict] = deque(maxlen=_RING_BUFFER_SIZE)
_ring_lock = threading.Lock()


def record_host(host: str):
    """Increment the per-host request counter."""
    if not host:
        return
    with host_counters_lock:
        host_counters[host] = host_counters.get(host, 0) + 1


def get_top_hosts(n: int = 10) -> list[tuple[str, int]]:
    """Return the top-N most requested hosts."""
    with host_counters_lock:
        return sorted(
            host_counters.items(), key=lambda x: x[1], reverse=True
        )[:n]


def log_event(message: str, **extra):
    """
    Log a proxy event to file + stderr + ring buffer.

    Parameters
    ----------
    message : str
        Human-readable log line.
    **extra : dict
        Structured fields stored in the ring buffer for the dashboard
        (e.g., request_id, client_ip, host, action, status, latency_ms).
    """
    _logger.info(message)

    # Build ring-buffer entry
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message,
    }
    entry.update(extra)

    with _ring_lock:
        log_ring_buffer.append(entry)


def get_recent_logs(n: int = 50) -> list[dict]:
    """Return the *n* most recent log entries (newest first)."""
    with _ring_lock:
        return list(log_ring_buffer)[-n:][::-1]
