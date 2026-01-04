echo "[TEST] Cache test"

echo "First request (expect CACHE MISS)"
curl -x localhost:8888 http://neverssl.com > /dev/null

sleep 1

echo "Second request (expect CACHE HIT)"
curl -x localhost:8888 http://neverssl.com > /dev/null