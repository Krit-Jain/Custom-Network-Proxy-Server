import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BLOCKLIST_FILE = os.path.join(BASE_DIR, "..", "config", "blocked_domains.txt")


def load_blocklist():
    blocked = set()
    if os.path.exists(BLOCKLIST_FILE):
        with open(BLOCKLIST_FILE) as f:
            for line in f:
                # Remove inline comments and whitespace
                line = line.split("#", 1)[0].strip().lower()
                if line:
                    blocked.add(line)
    return blocked


def is_blocked(host):
    if not host:
        return False

    host = host.lower()
    blocked_set = load_blocklist()  # reload to reflect config changes

    for blocked in blocked_set:
        # Exact match (domain or IP)
        if host == blocked:
            return True

        # Subdomain match
        if host.endswith("." + blocked):
            return True

    return False
