#!/usr/bin/env bash
set -euo pipefail

mkdir -p /var/lib/cloudflare-warp /etc/warp /var/log/cloudflare-warp

/bin/warp-svc >/var/log/cloudflare-warp/warp-svc.log 2>&1 &
WARP_SVC_PID=$!

cleanup() {
    kill "${WARP_SVC_PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

for _ in $(seq 1 20); do
    if warp-cli --accept-tos status >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

if ! warp-cli --accept-tos registration show >/dev/null 2>&1; then
    warp-cli --accept-tos registration new || true
fi

if [ -n "${WARP_LICENSE_KEY:-}" ]; then
    warp-cli --accept-tos registration license "${WARP_LICENSE_KEY}" || true
fi

if [ -n "${WARP_TUNNEL_PROTOCOL:-}" ]; then
    warp-cli --accept-tos tunnel protocol set "${WARP_TUNNEL_PROTOCOL}" || true
fi

warp-cli --accept-tos mode "${WARP_MODE:-warp+doh}" || true
warp-cli --accept-tos disconnect >/dev/null 2>&1 || true
warp-cli --accept-tos connect || true

curl --max-time 10 https://www.cloudflare.com/cdn-cgi/trace || true

tail -f /dev/null &
wait $!
