#!/bin/bash
set -e

echo "=============================="
echo "[TEST] HTTPS Allowed Request"
echo "=============================="

echo ""
echo "Sending HTTPS request through proxy (expected: CONNECT success)"
curl -v -x localhost:8888 https://neverssl.com >/dev/null

echo ""
echo "[PASS] HTTPS allowed request test completed successfully"
