#!/usr/bin/env bash
# shellcheck disable=SC1090
set -euo pipefail

HOST=${1:?"Usage: wait-for-it.sh host port [timeout]"}
PORT=${2:?"Usage: wait-for-it.sh host port [timeout]"}
TIMEOUT=${3:-30}

echo "[wait] Waiting for $HOST:$PORT (timeout ${TIMEOUT}s)"

for ((i=0; i<TIMEOUT; i++)); do
  if nc -z "$HOST" "$PORT" >/dev/null 2>&1; then
    echo "[wait] Service reachable"
    exit 0
  fi
  sleep 1
done

echo "[wait] Timeout waiting for $HOST:$PORT" >&2
exit 1
