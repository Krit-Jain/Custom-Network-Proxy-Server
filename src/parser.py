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

    if method == "CONNECT":
        host, port = target.split(":")
        port = int(port)
    else:
        for line in lines[1:]:
            if line.lower().startswith("host:"):
                host_value = line.split(":", 1)[1].strip()
                if ":" in host_value:
                    host, port = host_value.split(":")
                    port = int(port)
                else:
                    host = host_value
                break

        if target.startswith("http"):
            parsed = urlparse(target)
            host = parsed.hostname
            port = parsed.port or 80

    return {
        "method": method,
        "host": host,
        "port": port,
        "raw": data
    }
