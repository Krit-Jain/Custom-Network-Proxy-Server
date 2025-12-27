import socket
import threading

BUFFER_SIZE = 4096


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
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.connect((parsed["host"], parsed["port"]))
    server_sock.sendall(parsed["raw"])

    while True:
        data = server_sock.recv(BUFFER_SIZE)
        if not data:
            break
        client_sock.sendall(data)

    server_sock.close()
