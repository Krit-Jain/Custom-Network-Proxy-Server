#!/bin/bash

echo "=============================="
echo "[TEST] Proxy Authentication"
echo "=============================="

echo ""
echo "1) Request WITHOUT authentication (expected: 407)"
curl -x localhost:8888 -I http://neverssl.com

echo ""
echo "2) Request WITH authentication (expected: 200 OK)"
curl -x localhost:8888 -U admin:admin123 -I http://neverssl.com

echo ""
echo "3) HTTPS request WITH authentication (expected: CONNECT success)"
curl -x localhost:8888 -U admin:admin123 -I https://neverssl.com
