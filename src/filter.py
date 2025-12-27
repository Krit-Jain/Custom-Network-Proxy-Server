import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BLOCKLIST_FILE = os.path.join(BASE_DIR, "..", "config", "blocked_domains.txt")


def load_blocklist():
    blocked = set()
    if os.path.exists(BLOCKLIST_FILE):
        with open(BLOCKLIST_FILE) as f:
            for line in f:
                line = line.strip().lower()
                if line and not line.startswith("#"):
                    blocked.add(line)
    return blocked


BLOCKED_SET = load_blocklist()


def is_blocked(host):
    if not host:
        return False
    host = host.lower()
    for blocked in BLOCKED_SET:
        if host == blocked or host.endswith("." + blocked):
            return True
    return False
