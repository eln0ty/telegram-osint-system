#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE=${COMPOSE_FILE:-deployment/docker-compose.yml}
DATABASE=${POSTGRES_DB:-osint}
USER=${POSTGRES_USER:-osint}

echo "[db] Applying base schema..."
docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$USER" -d "$DATABASE" -f /docker-entrypoint-initdb.d/00-init.sql

echo "[db] Creating/refreshing partitions..."
docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$USER" -d "$DATABASE" -f /docker-entrypoint-initdb.d/01-create-partitions.sql

echo "[db] Schema initialization complete."
