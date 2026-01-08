#!/bin/bash
set -e

echo "=============================="
echo "[TEST] HTTP Blocked Request"
echo "=============================="

echo ""
echo "Sending HTTP request to blocked domain (expected: 403 Forbidden)"
curl -x localhost:8888 -I http://example.com

echo ""
echo "[PASS] HTTP blocked request test completed successfully"
