"""
log_schema.py — Canonical schema for all proxy log events.

Defines the LogEntry dataclass that serves as the single source of
truth for structured logging.  Every log event — whether written to
disk as JSON, displayed in the terminal, or pushed to the dashboard
— is constructed from this schema.

Using a dataclass enforces field consistency across all callers
and makes the log format self-documenting.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class LogEntry:
    """
    Structured log entry for a proxy event.

    Required fields
    ───────────────
    event       Short event identifier (e.g., "REQUEST_FORWARD",
                "REQUEST_BLOCKED", "CACHE_HIT").
    message     Human-readable description of what happened.

    Optional fields (populated by the caller as context allows)
    ──────────────────────────────────────────────────────────
    level           Log level: DEBUG, INFO, WARNING, ERROR.
    request_id      UUID4 string for end-to-end request correlation.
    client_ip       IP address of the connecting client.
    method          HTTP method (GET, POST, CONNECT, …).
    host            Destination hostname or IP.
    port            Destination port.
    path            Request path including query string.
    action          Proxy decision (FORWARD, BLOCKED, CACHE_HIT, …).
    status_code     HTTP response status code from origin server.
    latency_ms      Round-trip time to origin in milliseconds.
    bytes_transferred  Total bytes relayed to the client.
    """

    # ── Required ─────────────────────────────────────────────
    event: str
    message: str

    # ── Automatically populated ──────────────────────────────
    timestamp: str = field(default_factory=lambda: (
        datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    ))
    level: str = "INFO"

    # ── Request context (optional) ───────────────────────────
    request_id: Optional[str] = None
    client_ip: Optional[str] = None
    method: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    path: Optional[str] = None

    # ── Outcome (optional) ───────────────────────────────────
    action: Optional[str] = None
    status_code: Optional[int] = None
    latency_ms: Optional[float] = None
    bytes_transferred: Optional[int] = None

    def to_dict(self) -> dict:
        """
        Convert to a dict, omitting None values for compact JSON.

        This ensures the JSON output only contains fields that were
        actually populated, keeping log lines clean and parseable.
        """
        return {k: v for k, v in asdict(self).items() if v is not None}

    def to_human(self) -> str:
        """
        Format as a concise, human-readable line for terminal output.

        Example:
          [abc12345] 192.168.1.5 GET example.com:80/path → FORWARD [200] 1234B 45.2ms
        """
        parts: list[str] = []

        if self.request_id:
            parts.append(f"[{self.request_id[:8]}]")

        if self.client_ip:
            parts.append(self.client_ip)

        if self.method:
            parts.append(self.method)

        if self.host:
            target = self.host
            if self.port and self.port not in (80, 443):
                target += f":{self.port}"
            if self.path:
                target += self.path
            parts.append(target)

        if self.action:
            parts.append(f"→ {self.action}")

        if self.status_code:
            parts.append(f"[{self.status_code}]")

        if self.bytes_transferred is not None:
            parts.append(f"{self.bytes_transferred}B")

        if self.latency_ms is not None:
            parts.append(f"{self.latency_ms}ms")

        if parts:
            return " ".join(parts)

        return self.message
