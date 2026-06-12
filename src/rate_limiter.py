"""
rate_limiter.py — Per-IP token bucket rate limiter.

Implements the Token Bucket algorithm to enforce per-client request
rate limits.  Each unique client IP gets its own bucket that refills
at a configurable rate.  When a bucket is empty, requests are
rejected with HTTP 429 Too Many Requests.

Algorithm
─────────
Each bucket has a *capacity* (max burst size) and a *refill_rate*
(tokens restored per second).  On each request:

  1. Calculate elapsed time since the last request from this IP.
  2. Add (elapsed × refill_rate) tokens, capped at capacity.
  3. If tokens ≥ 1, consume one token and allow the request.
  4. Otherwise, reject with 429 and a Retry-After header.

Memory management
─────────────────
Stale buckets (no activity for >10 minutes) are periodically pruned
to prevent unbounded memory growth from unique IPs.

Thread safety
─────────────
A global lock protects the bucket registry; each bucket has its own
fine-grained lock for token operations to minimize contention.
"""

import math
import threading
import time

from config_loader import get_rate_limit_config

# ── Load configuration ───────────────────────────────────────
_cfg = get_rate_limit_config()

RATE_LIMIT_ENABLED: bool = _cfg["enabled"]
DEFAULT_CAPACITY: int = _cfg["capacity"]
DEFAULT_REFILL_RATE: float = _cfg["refill_rate"]

# Buckets inactive for longer than this (seconds) are pruned
_STALE_THRESHOLD = 600  # 10 minutes


class TokenBucket:
    """
    A single token bucket for one client IP.

    Attributes
    ----------
    capacity : int
        Maximum number of tokens (burst size).
    refill_rate : float
        Tokens added per second.
    tokens : float
        Current token count.
    last_refill : float
        Monotonic timestamp of the last refill calculation.
    """

    __slots__ = ("capacity", "refill_rate", "tokens", "last_refill", "lock")

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)  # Start full
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def consume(self) -> bool:
        """
        Try to consume one token.

        Returns True if the request is allowed, False if rate-limited.
        """
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill

            # Refill tokens based on elapsed time
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.refill_rate,
            )
            self.last_refill = now

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False

    def remaining(self) -> int:
        """Return the number of tokens currently available."""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            current = min(
                self.capacity,
                self.tokens + elapsed * self.refill_rate,
            )
            return int(current)

    def retry_after(self) -> float:
        """
        Estimate seconds until the next token is available.

        Used to populate the Retry-After response header.
        """
        with self.lock:
            if self.tokens >= 1.0:
                return 0.0
            deficit = 1.0 - self.tokens
            return math.ceil(deficit / self.refill_rate)


class RateLimiter:
    """
    Per-IP rate limiter managing a registry of token buckets.

    Thread-safe: uses a global lock for the bucket registry and
    per-bucket locks for token operations.
    """

    def __init__(
        self,
        capacity: int = DEFAULT_CAPACITY,
        refill_rate: float = DEFAULT_REFILL_RATE,
    ):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()
        self._last_prune = time.monotonic()

    def is_allowed(self, ip: str) -> bool:
        """
        Check if a request from *ip* is allowed.

        Creates a new bucket for first-time IPs (starts full).
        Periodically prunes stale buckets.
        """
        if not RATE_LIMIT_ENABLED:
            return True

        bucket = self._get_or_create_bucket(ip)
        allowed = bucket.consume()

        # Periodic cleanup (not on every call)
        self._maybe_prune()

        return allowed

    def get_retry_after(self, ip: str) -> int:
        """Return the Retry-After value in seconds for this IP."""
        with self._lock:
            bucket = self._buckets.get(ip)
            if bucket:
                return int(bucket.retry_after())
        return 1

    def get_remaining(self, ip: str) -> int:
        """Return remaining tokens for this IP."""
        with self._lock:
            bucket = self._buckets.get(ip)
            if bucket:
                return bucket.remaining()
        return self.capacity

    def _get_or_create_bucket(self, ip: str) -> TokenBucket:
        """Get existing bucket or create a new one for this IP."""
        with self._lock:
            if ip not in self._buckets:
                self._buckets[ip] = TokenBucket(
                    self.capacity, self.refill_rate
                )
            return self._buckets[ip]

    def _maybe_prune(self):
        """Remove buckets that haven't been used in _STALE_THRESHOLD seconds."""
        now = time.monotonic()
        if now - self._last_prune < 60:  # Check at most once per minute
            return

        with self._lock:
            self._last_prune = now
            stale_ips = [
                ip
                for ip, bucket in self._buckets.items()
                if now - bucket.last_refill > _STALE_THRESHOLD
            ]
            for ip in stale_ips:
                del self._buckets[ip]

    def snapshot(self) -> dict:
        """Return stats for the dashboard."""
        with self._lock:
            return {
                "active_buckets": len(self._buckets),
                "capacity": self.capacity,
                "refill_rate": self.refill_rate,
            }


# ── Global rate limiter instance ─────────────────────────────
rate_limiter = RateLimiter()
