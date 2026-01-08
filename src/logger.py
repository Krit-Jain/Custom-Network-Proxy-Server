import os
import threading
from datetime import datetime
from config_loader import get_logging_config

# Load logging configuration
log_cfg = get_logging_config()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "..", log_cfg["log_file"])
MAX_LOG_SIZE = log_cfg["max_size"]

LOG_DIR = os.path.dirname(LOG_FILE)
ROTATED_LOG_FILE = LOG_FILE + ".1"

# Metrics
metrics = {
    "total": 0,
    "allowed": 0,
    "blocked": 0
}

metrics_lock = threading.Lock()
log_lock = threading.Lock()


def ensure_log_dir():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)


def rotate_logs_if_needed():
    """
    Rotate proxy.log if it exceeds MAX_LOG_SIZE.
    Must be called while holding log_lock.
    """
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) >= MAX_LOG_SIZE:
            if os.path.exists(ROTATED_LOG_FILE):
                os.remove(ROTATED_LOG_FILE)
            os.rename(LOG_FILE, ROTATED_LOG_FILE)
    except OSError:
        # Rotation failure should not crash the proxy
        pass


def log_event(message):
    ensure_log_dir()

    with log_lock:
        rotate_logs_if_needed()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {message}\n"

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
