#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <backup-file.sql>" >&2
  exit 1
fi

BACKUP_FILE=$1
COMPOSE_FILE=${COMPOSE_FILE:-deployment/docker-compose.yml}
DB=${POSTGRES_DB:-osint}
USER=${POSTGRES_USER:-osint}

if [[ ! -f $BACKUP_FILE ]]; then
  echo "Backup file $BACKUP_FILE not found" >&2
  exit 1
fi

echo "[restore] Dropping existing schema..."
docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$USER" -d "$DB" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

echo "[restore] Restoring from $BACKUP_FILE"
docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$USER" -d "$DB" < "$BACKUP_FILE"

echo "[restore] Done."
