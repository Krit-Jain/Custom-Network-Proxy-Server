"""
config_loader.py — Centralized configuration management.

Reads proxy.conf and exposes typed configuration accessors for all
subsystems: server, logging, cache, rate limiting, and dashboard.

All configuration values have sensible defaults so the proxy can
start even if proxy.conf is missing or incomplete.
"""

import configparser
import os

# ── Locate config file relative to this source file ──────────
CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "config",
    "proxy.conf",
)

config = configparser.ConfigParser()
config.read(CONFIG_PATH)


def get_server_config():
    """Return server-level settings (listen address, pool size)."""
    return {
        "host": config.get("server", "listen_host", fallback="0.0.0.0"),
        "port": config.getint("server", "listen_port", fallback=8888),
        "max_conn": config.getint("server", "max_connections", fallback=50),
        "thread_pool_size": config.getint(
            "server", "thread_pool_size", fallback=20
        ),
    }


def get_logging_config():
    """Return logging settings (file path, rotation, level)."""
    return {
        "log_file": config.get(
            "logging", "log_file", fallback="logs/proxy.log"
        ),
        "max_size": config.getint(
            "logging", "max_log_size", fallback=1_048_576
        ),
        "backup_count": config.getint(
            "logging", "backup_count", fallback=5
        ),
        "log_level": config.get(
            "logging", "log_level", fallback="INFO"
        ).upper(),
    }


def get_cache_config():
    """Return cache settings (enabled flag, limits, TTL)."""
    return {
        "enabled": config.getboolean("cache", "enabled", fallback=True),
        "max_entries": config.getint("cache", "max_entries", fallback=100),
        "max_object_size": config.getint(
            "cache", "max_object_size", fallback=512 * 1024
        ),
        "cache_ttl": config.getint("cache", "cache_ttl", fallback=300),
    }


def get_rate_limit_config():
    """Return rate-limiting settings (token bucket parameters)."""
    return {
        "enabled": config.getboolean(
            "rate_limit", "enabled", fallback=True
        ),
        "capacity": config.getint("rate_limit", "capacity", fallback=20),
        "refill_rate": config.getfloat(
            "rate_limit", "refill_rate", fallback=2.0
        ),
    }


def get_dashboard_config():
    """Return dashboard settings (enabled flag, port)."""
    return {
        "enabled": config.getboolean(
            "dashboard", "enabled", fallback=True
        ),
        "port": config.getint("dashboard", "port", fallback=8889),
    }
