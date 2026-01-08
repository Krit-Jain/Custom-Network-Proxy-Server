import configparser
import os

CONFIG_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "config",
    "proxy.conf"
)

config = configparser.ConfigParser()
config.read(CONFIG_PATH)


def get_server_config():
    return {
        "host": config.get("server", "listen_host", fallback="0.0.0.0"),
        "port": config.getint("server", "listen_port", fallback=8888),
        "max_conn": config.getint("server", "max_connections", fallback=50),
    }


def get_logging_config():
    return {
        "log_file": config.get("logging", "log_file", fallback="logs/proxy.log"),
        "max_size": config.getint("logging", "max_log_size", fallback=1048576),
    }


def get_cache_config():
    return {
        "enabled": config.getboolean("cache", "enabled", fallback=True),
        "max_entries": config.getint("cache", "max_entries", fallback=10),
        "max_object_size": config.getint(
            "cache", "max_object_size", fallback=512 * 1024
        ),
    }
