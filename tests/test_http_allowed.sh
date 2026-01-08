#!/bin/bash
set -e

echo "=============================="
echo "[TEST] HTTP Allowed Request"
echo "=============================="

echo ""
echo "Sending HTTP request through proxy (expected: 200 OK)"
curl -x localhost:8888 -I http://neverssl.com

echo ""
echo "[PASS] HTTP allowed request test completed successfully"
