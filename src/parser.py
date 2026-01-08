from urllib.parse import urlparse

BUFFER_SIZE = 4096
HEADER_TERMINATOR = b"\r\n\r\n"
MAX_HEADER_SIZE = 8192


def recv_http_request(sock):
    data = b""
    while HEADER_TERMINATOR not in data:
        if len(data) > MAX_HEADER_SIZE:
            break
        chunk = sock.recv(BUFFER_SIZE)
        if not chunk:
            break
        data += chunk
    return data


def parse_http_request(data):
    text = data.decode(errors="ignore")
    lines = text.split("\r\n")

    # ---- Safe request-line parsing ----
    try:
        method, target, _ = lines[0].split(maxsplit=2)
    except ValueError:
        return None

    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    host = None
    port = 80
    path = "/"

    if method == "CONNECT":
        try:
            host, port = target.rsplit(":", 1)
            port = int(port)
            path = None
        except ValueError:
            return None

    else:
        if target.startswith("http://") or target.startswith("https://"):
            parsed = urlparse(target)
            host = parsed.hostname
            if parsed.scheme == "https":
                port = parsed.port or 443
            else:
                port = parsed.port or 80
            path = parsed.path or "/"
        else:
            path = target or "/"
            host_header = headers.get("host")
            if host_header:
                try:
                    host, port = host_header.rsplit(":", 1)
                    port = int(port)
                except ValueError:
                    host = host_header

    return {
        "method": method,
        "host": host,
        "port": port,
        "path": path,
        "headers": headers,
        "raw": data
    }
