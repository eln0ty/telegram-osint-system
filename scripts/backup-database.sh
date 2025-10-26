#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE=${COMPOSE_FILE:-deployment/docker-compose.yml}
DB=${POSTGRES_DB:-osint}
USER=${POSTGRES_USER:-osint}
BACKUP_DIR=${BACKUP_DIR:-backups}
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
FILE="$BACKUP_DIR/${DB}-${TIMESTAMP}.sql"

mkdir -p "$BACKUP_DIR"

echo "[backup] Dumping $DB to $FILE"
docker compose -f "$COMPOSE_FILE" exec -T postgres pg_dump -U "$USER" "$DB" > "$FILE"

echo "[backup] Completed."
