"""
cache.py — Thread-safe LRU cache with TTL eviction.

Implements an in-memory Least-Recently-Used cache for HTTP responses.
Each entry carries a timestamp and is automatically evicted when its
time-to-live (TTL) expires.  The cache also tracks operational
statistics (hits, misses, evictions, byte size) for the monitoring
dashboard.

Design notes:
  • Uses collections.OrderedDict for O(1) LRU ordering.
  • A single threading.Lock protects all mutations.
  • TTL is checked lazily on get() — no background sweeper thread.
"""

import threading
import time
from collections import OrderedDict

from config_loader import get_cache_config

# ── Load configuration ───────────────────────────────────────
_cfg = get_cache_config()

CACHE_ENABLED: bool = _cfg["enabled"]
MAX_ENTRIES: int = _cfg["max_entries"]
MAX_OBJECT_SIZE: int = _cfg["max_object_size"]
CACHE_TTL: int = _cfg["cache_ttl"]


class CacheStats:
    """Atomic counters for cache observability."""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.stores = 0
        self.current_entries = 0
        self.current_bytes = 0
        self._lock = threading.Lock()

    def record_hit(self):
        with self._lock:
            self.hits += 1

    def record_miss(self):
        with self._lock:
            self.misses += 1

    def record_eviction(self, size: int):
        with self._lock:
            self.evictions += 1
            self.current_entries = max(0, self.current_entries - 1)
            self.current_bytes = max(0, self.current_bytes - size)

    def record_store(self, size: int):
        with self._lock:
            self.stores += 1
            self.current_entries += 1
            self.current_bytes += size

    def record_remove(self, size: int):
        """Called when an existing key is overwritten."""
        with self._lock:
            self.current_entries = max(0, self.current_entries - 1)
            self.current_bytes = max(0, self.current_bytes - size)

    def snapshot(self) -> dict:
        """Return a point-in-time copy for the dashboard."""
        with self._lock:
            total = self.hits + self.misses
            return {
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "stores": self.stores,
                "current_entries": self.current_entries,
                "current_bytes": self.current_bytes,
                "hit_rate": round(
                    (self.hits / total * 100) if total > 0 else 0.0, 1
                ),
            }


class LRUCache:
    """
    Thread-safe LRU cache with per-entry TTL.

    Each value stored must be a dict containing at least:
      - "response" (bytes): the raw HTTP response
      - "size" (int): byte length of the response
      - "timestamp" (float): time.time() when the entry was created

    The "timestamp" field is set automatically if not provided.
    """

    def __init__(
        self,
        capacity: int = MAX_ENTRIES,
        ttl: int = CACHE_TTL,
    ):
        self.capacity = capacity
        self.ttl = ttl
        self.cache: OrderedDict = OrderedDict()
        self.lock = threading.Lock()
        self.stats = CacheStats()

    def get(self, key):
        """
        Retrieve a cached response.

        Returns None on miss or if the entry has expired.
        Expired entries are evicted lazily.
        """
        if not CACHE_ENABLED:
            return None

        with self.lock:
            if key not in self.cache:
                self.stats.record_miss()
                return None

            entry = self.cache[key]

            # ── TTL expiry check ─────────────────────────────
            age = time.time() - entry.get("timestamp", 0)
            if age > self.ttl:
                size = entry.get("size", 0)
                del self.cache[key]
                self.stats.record_eviction(size)
                self.stats.record_miss()
                return None

            # Move to end (most-recently used)
            self.cache.move_to_end(key)
            self.stats.record_hit()
            return entry

    def put(self, key, value: dict):
        """
        Store a response in the cache.

        Entries exceeding MAX_OBJECT_SIZE are silently discarded.
        When the cache is full, the least-recently-used entry is evicted.
        """
        if not CACHE_ENABLED:
            return

        entry_size = value.get("size", 0)

        # Enforce per-object size limit (check the actual byte size)
        if entry_size > MAX_OBJECT_SIZE:
            return

        # Ensure timestamp is always set
        if "timestamp" not in value:
            value["timestamp"] = time.time()

        with self.lock:
            # Overwrite existing entry
            if key in self.cache:
                old_size = self.cache[key].get("size", 0)
                self.stats.record_remove(old_size)
                self.cache.move_to_end(key)

            self.cache[key] = value
            self.stats.record_store(entry_size)

            # Evict LRU entry if over capacity
            while len(self.cache) > self.capacity:
                _, evicted = self.cache.popitem(last=False)
                self.stats.record_eviction(evicted.get("size", 0))

    def clear(self):
        """Flush all cached entries."""
        with self.lock:
            self.cache.clear()
            self.stats = CacheStats()


# ── Global cache instance ────────────────────────────────────
cache = LRUCache()
