echo "[TEST] Malformed request"

printf "BADREQUEST\r\n\r\n" | nc -w 2 localhost 8888
