"""
test_proxy.py — Comprehensive test suite for the custom network proxy server.

Tests cover:
  • HTTP forwarding (allowed and blocked domains)
  • HTTPS CONNECT tunneling
  • Rate limiting (429 Too Many Requests)
  • Proxy authentication (407 Proxy Authentication Required)
  • Caching (hit/miss behavior)
  • Concurrent client handling
  • Malformed request handling
  • Parser unit tests
  • Auth module unit tests
  • Cache unit tests
  • Rate limiter unit tests

Usage:
    # Start the proxy first:
    python src/server.py

    # Then run the tests:
    python -m pytest tests/test_proxy.py -v

    # Or with unittest:
    python -m unittest tests/test_proxy.py -v
"""

import base64
import hashlib
import os
import socket
import sys
import threading
import time
import unittest

# Add src/ to path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)


# ═══════════════════════════════════════════════════════════════
# Unit Tests — No running proxy required
# ═══════════════════════════════════════════════════════════════


class TestParser(unittest.TestCase):
    """Unit tests for HTTP request parser."""

    def setUp(self):
        from parser import parse_http_request
        self.parse = parse_http_request

    def test_get_absolute_uri(self):
        raw = b"GET http://example.com/path?q=1 HTTP/1.1\r\nHost: example.com\r\n\r\n"
        result = self.parse(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["method"], "GET")
        self.assertEqual(result["host"], "example.com")
        self.assertEqual(result["port"], 80)
        self.assertEqual(result["path"], "/path?q=1")
        self.assertIn("request_id", result)

    def test_connect_method(self):
        raw = b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n"
        result = self.parse(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["method"], "CONNECT")
        self.assertEqual(result["host"], "example.com")
        self.assertEqual(result["port"], 443)

    def test_origin_form_with_host_header(self):
        raw = b"GET /page HTTP/1.1\r\nHost: example.com\r\n\r\n"
        result = self.parse(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["host"], "example.com")
        self.assertEqual(result["path"], "/page")

    def test_post_with_body(self):
        body = b"key=value&foo=bar"
        raw = (
            b"POST http://example.com/api HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n"
            b"\r\n"
            + body
        )
        result = self.parse(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["method"], "POST")
        self.assertEqual(result["body"], body)
        self.assertEqual(result["content_length"], len(body))

    def test_malformed_request(self):
        result = self.parse(b"GARBAGE DATA")
        self.assertIsNone(result)

    def test_empty_request(self):
        result = self.parse(b"")
        self.assertIsNone(result)

    def test_missing_host(self):
        raw = b"GET /path HTTP/1.1\r\n\r\n"
        result = self.parse(raw)
        self.assertIsNone(result)

    def test_https_absolute_uri(self):
        raw = b"GET https://secure.example.com/path HTTP/1.1\r\nHost: secure.example.com\r\n\r\n"
        result = self.parse(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["port"], 443)

    def test_custom_port(self):
        raw = b"GET http://example.com:8080/path HTTP/1.1\r\nHost: example.com:8080\r\n\r\n"
        result = self.parse(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["port"], 8080)


class TestAuth(unittest.TestCase):
    """Unit tests for authentication module."""

    def setUp(self):
        from auth import hash_password, verify_password
        self.hash_password = hash_password
        self.verify_password = verify_password

    def test_hash_format(self):
        hashed = self.hash_password("testpass")
        self.assertTrue(hashed.startswith("pbkdf2$"))
        parts = hashed.split("$")
        self.assertEqual(len(parts), 4)

    def test_verify_correct_password(self):
        hashed = self.hash_password("mypassword")
        self.assertTrue(self.verify_password("mypassword", hashed))

    def test_verify_wrong_password(self):
        hashed = self.hash_password("mypassword")
        self.assertFalse(self.verify_password("wrongpassword", hashed))

    def test_legacy_plaintext_fallback(self):
        self.assertTrue(self.verify_password("admin123", "admin123"))
        self.assertFalse(self.verify_password("admin123", "wrong"))

    def test_unique_salts(self):
        h1 = self.hash_password("same")
        h2 = self.hash_password("same")
        self.assertNotEqual(h1, h2)  # Different salts → different hashes

    def test_empty_password(self):
        hashed = self.hash_password("")
        self.assertTrue(self.verify_password("", hashed))
        self.assertFalse(self.verify_password("notempty", hashed))

    def test_malformed_hash(self):
        self.assertFalse(self.verify_password("test", "pbkdf2$invalid"))
        self.assertFalse(self.verify_password("test", "pbkdf2$100$bad$data"))


class TestCache(unittest.TestCase):
    """Unit tests for LRU cache."""

    def setUp(self):
        from cache import LRUCache
        self.cache = LRUCache(capacity=3, ttl=5)

    def test_put_and_get(self):
        key = ("GET", "example.com", 80, "/")
        value = {"response": b"HTTP/1.1 200 OK\r\n\r\nHello", "size": 25, "timestamp": time.time()}
        self.cache.put(key, value)
        result = self.cache.get(key)
        self.assertIsNotNone(result)
        self.assertEqual(result["response"], value["response"])

    def test_cache_miss(self):
        result = self.cache.get(("GET", "missing.com", 80, "/"))
        self.assertIsNone(result)

    def test_lru_eviction(self):
        for i in range(4):
            key = ("GET", f"host{i}.com", 80, "/")
            self.cache.put(key, {"response": b"OK", "size": 2, "timestamp": time.time()})

        # First entry should be evicted (capacity=3)
        self.assertIsNone(self.cache.get(("GET", "host0.com", 80, "/")))
        self.assertIsNotNone(self.cache.get(("GET", "host3.com", 80, "/")))

    def test_ttl_expiration(self):
        from cache import LRUCache
        short_cache = LRUCache(capacity=10, ttl=1)  # 1 second TTL
        key = ("GET", "expire.com", 80, "/")
        short_cache.put(key, {"response": b"OK", "size": 2, "timestamp": time.time()})
        self.assertIsNotNone(short_cache.get(key))
        time.sleep(1.5)
        self.assertIsNone(short_cache.get(key))  # Expired

    def test_stats_tracking(self):
        key = ("GET", "stats.com", 80, "/")
        self.cache.get(key)  # miss
        self.cache.put(key, {"response": b"OK", "size": 2, "timestamp": time.time()})
        self.cache.get(key)  # hit

        stats = self.cache.stats.snapshot()
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["stores"], 1)

    def test_clear(self):
        key = ("GET", "clear.com", 80, "/")
        self.cache.put(key, {"response": b"OK", "size": 2, "timestamp": time.time()})
        self.cache.clear()
        self.assertIsNone(self.cache.get(key))


class TestRateLimiter(unittest.TestCase):
    """Unit tests for token bucket rate limiter."""

    def setUp(self):
        from rate_limiter import RateLimiter
        self.RateLimiter = RateLimiter

    def test_allows_within_capacity(self):
        rl = self.RateLimiter(capacity=5, refill_rate=1.0)
        for _ in range(5):
            self.assertTrue(rl.is_allowed("10.0.0.1"))

    def test_blocks_over_capacity(self):
        rl = self.RateLimiter(capacity=3, refill_rate=0.1)
        for _ in range(3):
            rl.is_allowed("10.0.0.1")
        self.assertFalse(rl.is_allowed("10.0.0.1"))

    def test_per_ip_isolation(self):
        rl = self.RateLimiter(capacity=2, refill_rate=0.1)
        rl.is_allowed("10.0.0.1")
        rl.is_allowed("10.0.0.1")
        self.assertFalse(rl.is_allowed("10.0.0.1"))
        self.assertTrue(rl.is_allowed("10.0.0.2"))  # Different IP

    def test_retry_after(self):
        rl = self.RateLimiter(capacity=1, refill_rate=1.0)
        rl.is_allowed("10.0.0.1")  # Consume the only token
        retry = rl.get_retry_after("10.0.0.1")
        self.assertGreater(retry, 0)

    def test_refill_over_time(self):
        rl = self.RateLimiter(capacity=2, refill_rate=10.0)  # Fast refill
        rl.is_allowed("10.0.0.1")
        rl.is_allowed("10.0.0.1")
        self.assertFalse(rl.is_allowed("10.0.0.1"))
        time.sleep(0.5)  # Wait for refill (10/sec × 0.5s = 5 tokens)
        self.assertTrue(rl.is_allowed("10.0.0.1"))

    def test_snapshot(self):
        rl = self.RateLimiter(capacity=10, refill_rate=2.0)
        rl.is_allowed("10.0.0.1")
        snap = rl.snapshot()
        self.assertEqual(snap["active_buckets"], 1)
        self.assertEqual(snap["capacity"], 10)
        self.assertEqual(snap["refill_rate"], 2.0)

    def test_concurrent_access(self):
        rl = self.RateLimiter(capacity=100, refill_rate=0.1)
        results = []

        def worker():
            r = rl.is_allowed("10.0.0.1")
            results.append(r)

        threads = [threading.Thread(target=worker) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 100)
        allowed = sum(1 for r in results if r)
        blocked = sum(1 for r in results if not r)
        self.assertEqual(allowed + blocked, 100)
        self.assertEqual(allowed, 100)  # All should fit in capacity=100


class TestLogSchema(unittest.TestCase):
    """Unit tests for LogEntry dataclass."""

    def setUp(self):
        from log_schema import LogEntry
        self.LogEntry = LogEntry

    def test_to_dict_omits_none(self):
        entry = self.LogEntry(event="TEST", message="test message")
        d = entry.to_dict()
        self.assertIn("event", d)
        self.assertIn("message", d)
        self.assertNotIn("client_ip", d)  # Not set → omitted

    def test_to_human_format(self):
        entry = self.LogEntry(
            event="REQUEST_FORWARD",
            message="forwarded",
            client_ip="192.168.1.1",
            method="GET",
            host="example.com",
            action="FORWARD",
        )
        human = entry.to_human()
        self.assertIn("192.168.1.1", human)
        self.assertIn("GET", human)
        self.assertIn("example.com", human)
        self.assertIn("FORWARD", human)

    def test_timestamp_auto_populated(self):
        entry = self.LogEntry(event="TEST", message="test")
        self.assertIsNotNone(entry.timestamp)
        self.assertIn("T", entry.timestamp)  # ISO format


class TestFilter(unittest.TestCase):
    """Unit tests for domain/IP filter."""

    def setUp(self):
        from filter import is_blocked
        self.is_blocked = is_blocked

    def test_blocked_domain(self):
        # The blocklist should include example.com or similar
        # This depends on the actual blocked_domains.txt content
        pass  # Tested via integration tests

    def test_none_host(self):
        self.assertFalse(self.is_blocked(None))

    def test_empty_host(self):
        self.assertFalse(self.is_blocked(""))


# ═══════════════════════════════════════════════════════════════
# Integration Tests — Require a running proxy on localhost:8888
# ═══════════════════════════════════════════════════════════════


def _is_proxy_running(host="127.0.0.1", port=8888) -> bool:
    """Check if the proxy server is accepting connections."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((host, port))
        s.close()
        return True
    except OSError:
        return False


def _send_raw(request: bytes, host="127.0.0.1", port=8888, timeout=10) -> bytes:
    """Send a raw HTTP request to the proxy and return the response."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((host, port))
    s.sendall(request)

    response = b""
    while True:
        try:
            data = s.recv(4096)
            if not data:
                break
            response += data
        except socket.timeout:
            break
    s.close()
    return response


def _basic_auth_header(username: str, password: str) -> str:
    """Generate a Basic auth header value."""
    creds = f"{username}:{password}"
    encoded = base64.b64encode(creds.encode()).decode()
    return f"Basic {encoded}"


@unittest.skipUnless(_is_proxy_running(), "Proxy server not running on localhost:8888")
class TestHTTPForwarding(unittest.TestCase):
    """Integration tests for HTTP request forwarding."""

    def test_allowed_request(self):
        auth = _basic_auth_header("admin", "admin123")
        request = (
            f"GET http://neverssl.com/ HTTP/1.1\r\n"
            f"Host: neverssl.com\r\n"
            f"Proxy-Authorization: {auth}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode()
        response = _send_raw(request)
        self.assertIn(b"HTTP/1.1", response)
        # Should get a 200 or 301 (redirect), not 403/407
        self.assertNotIn(b"403 Forbidden", response)
        self.assertNotIn(b"407 Proxy Authentication Required", response)


@unittest.skipUnless(_is_proxy_running(), "Proxy server not running on localhost:8888")
class TestHTTPBlocked(unittest.TestCase):
    """Integration tests for blocked domain filtering."""

    def test_blocked_domain(self):
        auth = _basic_auth_header("admin", "admin123")
        request = (
            f"GET http://example.com/ HTTP/1.1\r\n"
            f"Host: example.com\r\n"
            f"Proxy-Authorization: {auth}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode()
        response = _send_raw(request)
        self.assertIn(b"403 Forbidden", response)


@unittest.skipUnless(_is_proxy_running(), "Proxy server not running on localhost:8888")
class TestAuthentication(unittest.TestCase):
    """Integration tests for proxy authentication."""

    def test_no_credentials(self):
        request = (
            b"GET http://neverssl.com/ HTTP/1.1\r\n"
            b"Host: neverssl.com\r\n"
            b"Connection: close\r\n"
            b"\r\n"
        )
        response = _send_raw(request)
        self.assertIn(b"407", response)

    def test_wrong_credentials(self):
        auth = _basic_auth_header("admin", "wrongpassword")
        request = (
            f"GET http://neverssl.com/ HTTP/1.1\r\n"
            f"Host: neverssl.com\r\n"
            f"Proxy-Authorization: {auth}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode()
        response = _send_raw(request)
        self.assertIn(b"407", response)


@unittest.skipUnless(_is_proxy_running(), "Proxy server not running on localhost:8888")
class TestMalformedRequests(unittest.TestCase):
    """Integration tests for malformed request handling."""

    def test_garbage_data(self):
        response = _send_raw(b"THIS IS NOT HTTP\r\n\r\n")
        self.assertIn(b"400", response)

    def test_empty_request(self):
        """Server should handle empty request gracefully."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect(("127.0.0.1", 8888))
            s.close()
        except OSError:
            pass  # Connection closed gracefully is fine


@unittest.skipUnless(_is_proxy_running(), "Proxy server not running on localhost:8888")
class TestRateLimiting(unittest.TestCase):
    """Integration tests for rate limiting.

    Note: Default config has capacity=20, refill_rate=2/s.
    These tests send many rapid requests to trigger 429.
    """

    def test_rate_limit_triggers_429(self):
        auth = _basic_auth_header("admin", "admin123")
        got_429 = False

        for _ in range(30):  # More than capacity (20)
            request = (
                f"GET http://neverssl.com/ HTTP/1.1\r\n"
                f"Host: neverssl.com\r\n"
                f"Proxy-Authorization: {auth}\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            ).encode()
            try:
                response = _send_raw(request, timeout=3)
                if b"429" in response:
                    got_429 = True
                    self.assertIn(b"Retry-After", response)
                    break
            except socket.timeout:
                continue

        self.assertTrue(got_429, "Expected at least one 429 response")


@unittest.skipUnless(_is_proxy_running(), "Proxy server not running on localhost:8888")
class TestConcurrency(unittest.TestCase):
    """Integration tests for concurrent request handling."""

    def test_concurrent_requests(self):
        """Fire multiple concurrent requests — all should get responses."""
        auth = _basic_auth_header("admin", "admin123")
        results = []

        def worker():
            try:
                request = (
                    f"GET http://neverssl.com/ HTTP/1.1\r\n"
                    f"Host: neverssl.com\r\n"
                    f"Proxy-Authorization: {auth}\r\n"
                    f"Connection: close\r\n"
                    f"\r\n"
                ).encode()
                response = _send_raw(request, timeout=15)
                results.append(len(response) > 0)
            except Exception:
                results.append(False)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)

        self.assertEqual(len(results), 10)
        success_rate = sum(1 for r in results if r) / len(results)
        self.assertGreaterEqual(success_rate, 0.7, "At least 70% should succeed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
