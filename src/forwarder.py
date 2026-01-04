import socket
import threading
from cache import cache
import time
from logger import log_event

BUFFER_SIZE = 4096
MAX_OBJECT_SIZE = 512 * 1024  # 512 KB

def tunnel(client_sock, server_sock):
    def forward(src, dst):
        try:
            while True:
                data = src.recv(BUFFER_SIZE)
                if not data:
                    break
                dst.sendall(data)
        except:
            pass

    t1 = threading.Thread(target=forward, args=(client_sock, server_sock))
    t2 = threading.Thread(target=forward, args=(server_sock, client_sock))
    t1.start()
    t2.start()
    t1.join()
    t2.join()


def forward_http(parsed, client_sock):
    cache_key = (
        parsed["method"],
        parsed["host"],
        parsed["port"],
        parsed["path"]
    )

    # ---------- CACHE HIT ----------
    if parsed["method"] == "GET":
        cached = cache.get(cache_key)
        if cached:
            log_event(f"CACHE HIT → {parsed['host']}:{parsed['port']}")
            client_sock.sendall(cached["response"])
            return
        else:
            log_event(f"CACHE MISS → {parsed['host']}:{parsed['port']}")

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.connect((parsed["host"], parsed["port"]))
    request = parsed["raw"].decode(errors="ignore")

    # Force connection close to make response finite
    request = request.replace(
        "Connection: keep-alive",
        "Connection: close"
    )

    if "Connection:" not in request:
        request = request.replace("\r\n\r\n", "\r\nConnection: close\r\n\r\n")

    server_sock.sendall(request.encode())


    response_chunks = []
    total_size = 0
    cacheable = parsed["method"] == "GET"

    while True:
        data = server_sock.recv(BUFFER_SIZE)
        if not data:
            break

        client_sock.sendall(data)

        if cacheable:
            total_size += len(data)
            if total_size <= MAX_OBJECT_SIZE:
                response_chunks.append(data)
            else:
                cacheable = False  # too large to cache

    server_sock.close()

    # ---------- STORE IN CACHE ----------
    if parsed["method"] == "GET" and cacheable:
        full_response = b"".join(response_chunks)
        cache.put(
            cache_key,
            {
                "response": full_response,
                "timestamp": time.time(),
                "size": total_size
            }
        )
        log_event(f"CACHE STORE → {parsed['host']}:{parsed['port']} ({total_size} bytes)")
