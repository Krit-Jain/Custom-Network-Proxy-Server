"""
logger.py — Structured JSON logging with rotation and metrics.

Architecture
────────────
Two output channels run in parallel:

  1. **File handler** — Writes one JSON object per line to a rotating
     log file.  Each line is a valid JSON document that can be parsed
     by log aggregators (ELK, Loki, jq, etc.).

  2. **Stderr handler** — Writes compact, human-readable lines for
     real-time development feedback.

Both channels receive the same LogEntry; the only difference is
serialization format.

In-memory state
───────────────
  • ``metrics`` — thread-safe counters for dashboard gauges.
  • ``host_counters`` — per-host hit counts for "top hosts" panel.
  • ``log_ring_buffer`` — bounded deque of the last N structured log
    entries, consumed by the SSE dashboard endpoint.
"""

import json
import logging
import logging.handlers
import os
import threading
from collections import deque
from datetime import datetime, timezone

from config_loader import get_logging_config
from log_schema import LogEntry

# ── Load configuration ───────────────────────────────────────
_cfg = get_logging_config()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "..", _cfg["log_file"])
LOG_DIR = os.path.dirname(LOG_FILE)
MAX_LOG_SIZE = _cfg["max_size"]
BACKUP_COUNT = _cfg["backup_count"]
LOG_LEVEL_NAME = _cfg["log_level"]

# Ensure the log directory exists
os.makedirs(LOG_DIR, exist_ok=True)


# ── Custom JSON formatter ────────────────────────────────────

class _JSONFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        # The LogEntry dict is attached to the record by log_event()
        entry = getattr(record, "log_entry_dict", None)
        if entry:
            return json.dumps(entry, ensure_ascii=False, default=str)
        # Fallback for non-structured messages
        return json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "event": "SYSTEM",
            "message": record.getMessage(),
        }, ensure_ascii=False)


class _HumanFormatter(logging.Formatter):
    """Emit compact, readable log lines for the terminal."""

    def format(self, record: logging.LogRecord) -> str:
        entry: LogEntry | None = getattr(record, "log_entry", None)
        if entry:
            return f"  {entry.to_human()}"
        return f"  {record.getMessage()}"


# ── Configure stdlib logger ──────────────────────────────────

_logger = logging.getLogger("proxy")
_logger.setLevel(logging.DEBUG)
_logger.propagate = False

# Remove any handlers from previous imports (hot-reload safety)
_logger.handlers.clear()

# File handler → JSON (rotates automatically)
_file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE,
    maxBytes=MAX_LOG_SIZE,
    backupCount=BACKUP_COUNT,
    encoding="utf-8",
)
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(_JSONFormatter())
_logger.addHandler(_file_handler)

# Stderr handler → human-readable
_stderr_handler = logging.StreamHandler()
_stderr_handler.setLevel(
    getattr(logging, LOG_LEVEL_NAME, logging.INFO)
)
_stderr_handler.setFormatter(_HumanFormatter())
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
    Log a structured proxy event.

    Writes to three destinations simultaneously:
      1. Log file → JSON (one object per line)
      2. Stderr → human-readable (for development)
      3. Ring buffer → dict (for dashboard SSE stream)

    Parameters
    ----------
    message : str
        Human-readable description.
    **extra : dict
        Structured fields matching LogEntry field names
        (request_id, client_ip, host, port, method, action,
        status_code, latency_ms, bytes_transferred).
    """
    # Determine log level from kwargs or default to INFO
    level_name = extra.pop("level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # Build the structured LogEntry
    entry = LogEntry(
        event=extra.get("action", "PROXY"),
        message=message,
        level=level_name,
        request_id=extra.get("request_id"),
        client_ip=extra.get("client_ip"),
        method=extra.get("method"),
        host=extra.get("host"),
        port=extra.get("port"),
        path=extra.get("path"),
        action=extra.get("action"),
        status_code=extra.get("status_code"),
        latency_ms=extra.get("latency_ms"),
        bytes_transferred=extra.get("bytes_transferred"),
    )

    # Create a log record and attach the structured data
    record = _logger.makeRecord(
        name="proxy",
        level=level,
        fn="",
        lno=0,
        msg=message,
        args=(),
        exc_info=None,
    )
    record.log_entry = entry          # for HumanFormatter
    record.log_entry_dict = entry.to_dict()  # for JSONFormatter

    _logger.handle(record)

    # Push to ring buffer for the dashboard
    with _ring_lock:
        log_ring_buffer.append(entry.to_dict())


def get_recent_logs(n: int = 50) -> list[dict]:
    """Return the *n* most recent log entries (newest first)."""
    with _ring_lock:
        return list(log_ring_buffer)[-n:][::-1]
