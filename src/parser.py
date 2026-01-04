from urllib.parse import urlparse

BUFFER_SIZE = 4096
HEADER_TERMINATOR = b"\r\n\r\n"


def recv_http_request(sock):
    data = b""
    while HEADER_TERMINATOR not in data:
        chunk = sock.recv(BUFFER_SIZE)
        if not chunk:
            break
        data += chunk
    return data


def parse_http_request(data):
    text = data.decode(errors="ignore")
    lines = text.split("\r\n")
    method, target, _ = lines[0].split()

    host = None
    port = 80
    path = "/"

    if method == "CONNECT":
        host, port = target.split(":")
        port = int(port)
        path = None  # CONNECT has no path

    else:
        # Absolute-form (proxy requests)
        if target.startswith("http://") or target.startswith("https://"):
            parsed = urlparse(target)
            host = parsed.hostname
            port = parsed.port or 80
            path = parsed.path or "/"   # ✅ CRITICAL LINE
        else:
            # Origin-form
            path = target or "/"        # ✅ CRITICAL LINE

        # Extract Host header
        for line in lines[1:]:
            if line.lower().startswith("host:"):
                host_value = line.split(":", 1)[1].strip()
                if ":" in host_value:
                    host, port = host_value.split(":")
                    port = int(port)
                else:
                    host = host_value
                break
    headers = {}

    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    return {
        "method": method,
        "host": host,
        "port": port,
        "path": path,
        "headers": headers,
        "raw": data
    }
