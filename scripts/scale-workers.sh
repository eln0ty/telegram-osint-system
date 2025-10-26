#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <replica-count>" >&2
  exit 1
fi

COUNT=$1
COMPOSE_FILE=${COMPOSE_FILE:-deployment/docker-compose.yml}

echo "[scale] Scaling worker service to $COUNT replicas..."
docker compose -f "$COMPOSE_FILE" up -d --scale worker="$COUNT" worker

echo "[scale] Current worker containers:"
docker compose -f "$COMPOSE_FILE" ps worker
