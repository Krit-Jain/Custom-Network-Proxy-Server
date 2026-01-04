echo "[TEST] Concurrency test"

for i in {1..10}; do
  curl -x localhost:8888 http://neverssl.com > /dev/null &
done

wait
echo "Concurrent requests completed"