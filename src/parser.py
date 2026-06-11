"""
parser.py — HTTP request parsing.

Receives raw bytes from the client socket and produces a structured
dict containing all fields needed for forwarding:

  • method, host, port, path (with query string)
  • headers dict (lowercase keys)
  • content_length (int or None)
  • body (bytes — the request body for POST/PUT/PATCH)
  • request_id (UUID4 — unique per request for log correlation)
  • raw (original bytes)

Handles both absolute-URI proxy requests and origin-form requests
with a Host header.  Implements header-accumulation loop per
RFC 7230 §3 to handle partial reads.
"""

import uuid
from urllib.parse import urlparse

BUFFER_SIZE = 4096
HEADER_TERMINATOR = b"\r\n\r\n"
MAX_HEADER_SIZE = 65536  # 64 KB — generous for real-world headers


def recv_http_request(sock):
    """
    Read from *sock* until the full HTTP header block is received.

    Accumulates data in a loop until the \\r\\n\\r\\n terminator is
    found or MAX_HEADER_SIZE is exceeded.  If Content-Length is
    present, continues reading to capture the request body.

    Returns the complete raw bytes (headers + body), or b\"\" on
    connection close / oversize.
    """
    data = b""
    sock.settimeout(30)

    # ── Phase 1: accumulate headers ──────────────────────────
    while HEADER_TERMINATOR not in data:
        if len(data) > MAX_HEADER_SIZE:
            return b""
        try:
            chunk = sock.recv(BUFFER_SIZE)
        except OSError:
            break
        if not chunk:
            break
        data += chunk

    if HEADER_TERMINATOR not in data:
        return data  # Incomplete headers — caller will get None from parse

    # ── Phase 2: read request body if Content-Length present ──
    header_end = data.index(HEADER_TERMINATOR) + len(HEADER_TERMINATOR)
    header_block = data[:header_end].decode(errors="ignore")

    content_length = _extract_content_length(header_block)
    if content_length and content_length > 0:
        body_received = len(data) - header_end
        remaining = content_length - body_received
        while remaining > 0:
            try:
                chunk = sock.recv(min(BUFFER_SIZE, remaining))
            except OSError:
                break
            if not chunk:
                break
            data += chunk
            remaining -= len(chunk)

    return data


def _extract_content_length(header_text: str) -> int | None:
    """Extract Content-Length value from raw header text."""
    for line in header_text.split("\r\n"):
        if line.lower().startswith("content-length:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def parse_http_request(data: bytes) -> dict | None:
    """
    Parse raw HTTP request bytes into a structured dict.

    Returns None if the request line is malformed or the host
    cannot be determined.

    Returned dict fields:
        method          str     HTTP method (GET, POST, CONNECT, …)
        host            str     Destination hostname or IP
        port            int     Destination port
        path            str     Request path including query string
        headers         dict    Header name (lowercase) → value
        content_length  int|None
        body            bytes   Request body (empty for GET/HEAD)
        request_id      str     UUID4 for log correlation
        raw             bytes   Original raw bytes
    """
    if not data or HEADER_TERMINATOR not in data:
        return None

    header_end = data.index(HEADER_TERMINATOR) + len(HEADER_TERMINATOR)
    header_block = data[:header_end].decode(errors="ignore")
    body = data[header_end:]

    lines = header_block.split("\r\n")

    # ── Request line ─────────────────────────────────────────
    try:
        method, target, version = lines[0].split(maxsplit=2)
    except ValueError:
        return None

    # ── Headers ──────────────────────────────────────────────
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if not line:
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()

    # ── Content-Length ────────────────────────────────────────
    content_length = None
    cl_str = headers.get("content-length")
    if cl_str:
        try:
            content_length = int(cl_str)
        except ValueError:
            pass

    # ── Destination resolution ───────────────────────────────
    host = None
    port = 80
    path = "/"

    if method == "CONNECT":
        # CONNECT host:port
        try:
            host, port_str = target.rsplit(":", 1)
            port = int(port_str)
            path = None
        except ValueError:
            return None

    elif target.startswith("http://") or target.startswith("https://"):
        # Absolute URI: GET http://example.com/path?q=1 HTTP/1.1
        parsed_url = urlparse(target)
        host = parsed_url.hostname
        if parsed_url.scheme == "https":
            port = parsed_url.port or 443
        else:
            port = parsed_url.port or 80
        # Preserve query string
        path = parsed_url.path or "/"
        if parsed_url.query:
            path += "?" + parsed_url.query

    else:
        # Origin form: GET /path?q=1 HTTP/1.1  (with Host header)
        path = target or "/"
        host_header = headers.get("host")
        if host_header:
            if ":" in host_header:
                try:
                    host, port_str = host_header.rsplit(":", 1)
                    port = int(port_str)
                except ValueError:
                    host = host_header
            else:
                host = host_header

    if not host:
        return None

    return {
        "method": method,
        "host": host,
        "port": port,
        "path": path,
        "headers": headers,
        "content_length": content_length,
        "body": body,
        "request_id": str(uuid.uuid4()),
        "raw": data,
    }
