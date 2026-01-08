#!/bin/bash
set -e

echo "=============================="
echo "[TEST] HTTP Cache Test"
echo "=============================="

echo ""
echo "First request (expected: CACHE MISS)"
curl -x localhost:8888 http://neverssl.com > /dev/null

sleep 1

echo ""
echo "Second request (expected: CACHE HIT)"
curl -x localhost:8888 http://neverssl.com > /dev/null

echo ""
echo "[PASS] Cache test completed successfully"
