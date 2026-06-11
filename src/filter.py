"""
filter.py — Domain and IP-based request filtering.

Implements a configurable blocklist that is loaded once at startup
and can be hot-reloaded at runtime.  Supports:

  • Exact domain matching  (example.com)
  • Subdomain suffix matching  (*.example.com via suffix check)
  • Exact IPv4/IPv6 matching  (192.0.2.5)
  • CIDR range matching  (192.168.0.0/24)

All hostnames are canonicalized to lowercase before comparison.
"""

import ipaddress
import os
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BLOCKLIST_FILE = os.path.join(BASE_DIR, "..", "config", "blocked_domains.txt")

# ── Module-level state (loaded once, thread-safe reload) ─────
_blocked_domains: set[str] = set()
_blocked_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
_lock = threading.Lock()


def _parse_blocklist(path: str):
    """Parse the blocklist file into domains and CIDR networks."""
    domains: set[str] = set()
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []

    if not os.path.exists(path):
        return domains, networks

    with open(path, encoding="utf-8") as f:
        for line in f:
            entry = line.split("#", 1)[0].strip().lower()
            if not entry:
                continue

            # Try to parse as a CIDR network (e.g., 192.168.0.0/24)
            if "/" in entry:
                try:
                    networks.append(
                        ipaddress.ip_network(entry, strict=False)
                    )
                    continue
                except ValueError:
                    pass  # Not a valid CIDR — treat as domain

            # Try to parse as a plain IP address
            try:
                # Store single IPs as /32 or /128 networks for uniform matching
                networks.append(
                    ipaddress.ip_network(entry, strict=False)
                )
                continue
            except ValueError:
                pass  # Not an IP — treat as domain

            # Everything else is a domain name
            domains.add(entry)

    return domains, networks


def load_blocklist():
    """
    Load (or reload) the blocklist from disk.

    This is called once at module import time. Call `reload_blocklist()`
    at runtime to pick up changes without restarting the proxy.
    """
    global _blocked_domains, _blocked_networks
    with _lock:
        _blocked_domains, _blocked_networks = _parse_blocklist(
            BLOCKLIST_FILE
        )


def reload_blocklist():
    """Thread-safe hot-reload of the blocklist file."""
    load_blocklist()


def is_blocked(host: str | None) -> bool:
    """
    Check whether *host* matches any entry in the blocklist.

    Performs exact domain match, subdomain suffix match, and
    CIDR network containment check.
    """
    if not host:
        return False

    host = host.lower().strip()

    with _lock:
        # ── Domain matching ──────────────────────────────────
        if host in _blocked_domains:
            return True

        # Subdomain suffix match (e.g., sub.example.com matches example.com)
        for blocked in _blocked_domains:
            if host.endswith("." + blocked):
                return True

        # ── IP / CIDR matching ───────────────────────────────
        try:
            addr = ipaddress.ip_address(host)
            for network in _blocked_networks:
                if addr in network:
                    return True
        except ValueError:
            pass  # host is a domain name, not an IP

    return False


# ── Load blocklist once at import time ───────────────────────
load_blocklist()
