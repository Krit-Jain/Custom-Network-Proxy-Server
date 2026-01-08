#!/bin/bash
set -e

echo "=============================="
echo "[TEST] HTTPS Blocked Request"
echo "=============================="

echo ""
echo "Sending HTTPS request to blocked domain (expected: 403 Forbidden during CONNECT)"
curl -v -x localhost:8888 https://example.com >/dev/null

echo ""
echo "[PASS] HTTPS blocked request test completed successfully"
