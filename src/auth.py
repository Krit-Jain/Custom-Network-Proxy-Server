"""
auth.py — Secure password hashing and user management.

Replaces plaintext password storage with PBKDF2-HMAC-SHA256,
a password hashing algorithm recommended by NIST SP 800-132.

Storage format
──────────────
Each line in users.txt:
    username:pbkdf2$iterations$salt_hex$hash_hex

Example:
    admin:pbkdf2$600000$a1b2c3d4e5f6$deadbeef...

Security properties
───────────────────
  • 600,000 PBKDF2 iterations (OWASP 2024 recommendation)
  • 32-byte random salt per user (prevents rainbow tables)
  • 32-byte derived key
  • Constant-time comparison via hmac.compare_digest
"""

import hashlib
import hmac
import os

# ── Hashing parameters ───────────────────────────────────────
_ALGORITHM = "sha256"
_ITERATIONS = 600_000
_SALT_LENGTH = 32   # bytes
_KEY_LENGTH = 32    # bytes
_PREFIX = "pbkdf2"


def hash_password(plain: str) -> str:
    """
    Hash a plaintext password for storage.

    Returns a string in the format:
        pbkdf2$iterations$salt_hex$hash_hex
    """
    salt = os.urandom(_SALT_LENGTH)
    dk = hashlib.pbkdf2_hmac(
        _ALGORITHM,
        plain.encode("utf-8"),
        salt,
        _ITERATIONS,
        dklen=_KEY_LENGTH,
    )
    return (
        f"{_PREFIX}${_ITERATIONS}${salt.hex()}${dk.hex()}"
    )


def verify_password(plain: str, stored: str) -> bool:
    """
    Verify a plaintext password against a stored hash.

    Supports both the new PBKDF2 format and legacy plaintext
    for backwards compatibility during migration.

    Uses constant-time comparison to prevent timing attacks.
    """
    if stored.startswith(f"{_PREFIX}$"):
        return _verify_pbkdf2(plain, stored)

    # Legacy plaintext fallback (for migration period)
    return hmac.compare_digest(plain, stored)


def _verify_pbkdf2(plain: str, stored: str) -> bool:
    """Verify against a PBKDF2-formatted hash string."""
    try:
        parts = stored.split("$")
        if len(parts) != 4:
            return False

        _, iterations_str, salt_hex, hash_hex = parts
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, IndexError):
        return False

    dk = hashlib.pbkdf2_hmac(
        _ALGORITHM,
        plain.encode("utf-8"),
        salt,
        iterations,
        dklen=len(expected),
    )

    return hmac.compare_digest(dk, expected)


def load_users(filepath: str) -> dict[str, str]:
    """
    Read username:hash pairs from a users file.

    Lines starting with '#' are ignored. Empty lines are skipped.
    Returns a dict mapping username → stored hash/password string.
    """
    users: dict[str, str] = {}
    try:
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    username, credential = line.split(":", 1)
                    users[username.strip()] = credential.strip()
    except FileNotFoundError:
        pass
    return users
