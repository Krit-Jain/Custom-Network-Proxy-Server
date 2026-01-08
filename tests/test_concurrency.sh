#!/bin/bash
set -e

echo "=============================="
echo "[TEST] Concurrency Test"
echo "=============================="

echo ""
echo "Launching concurrent requests..."

for i in {1..10}; do
  curl -x localhost:8888 http://neverssl.com > /dev/null &
done

wait

echo ""
echo "[PASS] Concurrent requests completed successfully"
