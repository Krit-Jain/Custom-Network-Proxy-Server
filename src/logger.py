import os
import threading
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "..", "logs")
LOG_FILE = os.path.join(LOG_DIR, "proxy.log")
ROTATED_LOG_FILE = os.path.join(LOG_DIR, "proxy.log.1")

MAX_LOG_SIZE = 10 * 1024  # 10 kB

metrics = {
    "total": 0,
    "allowed": 0,
    "blocked": 0
}

metrics_lock = threading.Lock()
log_lock = threading.Lock()


def ensure_log_dir():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)


def rotate_logs_if_needed():
    """
    Rotate proxy.log if it exceeds MAX_LOG_SIZE.
    """
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) >= MAX_LOG_SIZE:
        # Remove old rotated log if it exists
        if os.path.exists(ROTATED_LOG_FILE):
            os.remove(ROTATED_LOG_FILE)

        os.rename(LOG_FILE, ROTATED_LOG_FILE)


def log_event(message):
    ensure_log_dir()

    with log_lock:
        rotate_logs_if_needed()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {message}\n"

        with open(LOG_FILE, "a") as f:
            f.write(entry)
