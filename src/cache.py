from collections import OrderedDict
import threading
from config_loader import get_cache_config

# Load cache configuration
cache_cfg = get_cache_config()

CACHE_ENABLED = cache_cfg["enabled"]
MAX_CACHE_SIZE = cache_cfg["max_entries"]
MAX_OBJECT_SIZE = cache_cfg["max_object_size"]


class LRUCache:
    def __init__(self, capacity=MAX_CACHE_SIZE):
        self.capacity = capacity
        self.cache = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key):
        if not CACHE_ENABLED:
            return None

        with self.lock:
            if key not in self.cache:
                return None
            self.cache.move_to_end(key)
            return self.cache[key]

    def put(self, key, value):
        if not CACHE_ENABLED:
            return

        # Enforce max object size
        if len(value) > MAX_OBJECT_SIZE:
            return

        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)

            self.cache[key] = value

            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)


# Global cache instance
cache = LRUCache()
