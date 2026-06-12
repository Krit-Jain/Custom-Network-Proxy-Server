"""
manage_users.py — CLI tool for managing proxy user credentials.

Usage:
    python tools/manage_users.py add <username> <password>
    python tools/manage_users.py remove <username>
    python tools/manage_users.py list
    python tools/manage_users.py migrate   (convert plaintext → hashed)

All passwords are stored as PBKDF2-HMAC-SHA256 hashes.
"""

import os
import sys

# Add src/ to path so we can import auth module
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from auth import hash_password, load_users, verify_password

USERS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "config",
    "users.txt",
)


def _save_users(users: dict[str, str]):
    """Write the full user registry back to disk."""
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        f.write("# Proxy user credentials (managed by manage_users.py)\n")
        f.write("# Format: username:pbkdf2$iterations$salt$hash\n")
        for username, credential in sorted(users.items()):
            f.write(f"{username}:{credential}\n")


def cmd_add(username: str, password: str):
    """Add or update a user with a hashed password."""
    users = load_users(USERS_FILE)
    hashed = hash_password(password)
    action = "Updated" if username in users else "Added"
    users[username] = hashed
    _save_users(users)
    print(f"[+] {action} user: {username}")


def cmd_remove(username: str):
    """Remove a user from the credentials file."""
    users = load_users(USERS_FILE)
    if username not in users:
        print(f"[-] User not found: {username}")
        sys.exit(1)
    del users[username]
    _save_users(users)
    print(f"[+] Removed user: {username}")


def cmd_list():
    """List all registered users."""
    users = load_users(USERS_FILE)
    if not users:
        print("No users configured.")
        return
    print(f"{'Username':<20} {'Credential Type'}")
    print("-" * 40)
    for username, credential in sorted(users.items()):
        if credential.startswith("pbkdf2$"):
            cred_type = "PBKDF2 (hashed)"
        else:
            cred_type = "PLAINTEXT (migrate!)"
        print(f"{username:<20} {cred_type}")


def cmd_migrate():
    """Convert any plaintext passwords to PBKDF2 hashes."""
    users = load_users(USERS_FILE)
    migrated = 0
    for username, credential in users.items():
        if not credential.startswith("pbkdf2$"):
            # Credential is plaintext — hash it
            users[username] = hash_password(credential)
            migrated += 1
            print(f"  [+] Migrated: {username}")
    if migrated > 0:
        _save_users(users)
        print(f"\n[+] Migrated {migrated} user(s) to PBKDF2.")
    else:
        print("[=] All users already use hashed credentials.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "add":
        if len(sys.argv) != 4:
            print("Usage: manage_users.py add <username> <password>")
            sys.exit(1)
        cmd_add(sys.argv[2], sys.argv[3])

    elif command == "remove":
        if len(sys.argv) != 3:
            print("Usage: manage_users.py remove <username>")
            sys.exit(1)
        cmd_remove(sys.argv[2])

    elif command == "list":
        cmd_list()

    elif command == "migrate":
        cmd_migrate()

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
