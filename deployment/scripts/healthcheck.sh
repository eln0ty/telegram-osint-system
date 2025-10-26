#!/usr/bin/env bash
set -euo pipefail

SERVICE=${1:?"Usage: healthcheck.sh <postgres|redis|rabbitmq>"}

case "$SERVICE" in
  postgres)
    pg_isready -U "${POSTGRES_USER:-osint}" -d "${POSTGRES_DB:-osint}" -h "${PGHOST:-localhost}" -p "${PGPORT:-5432}"
    ;;
  redis)
    redis-cli -h "${REDIS_HOST:-localhost}" -p "${REDIS_PORT:-6379}" ping
    ;;
  rabbitmq)
    rabbitmq-diagnostics ping
    ;;
  *)
    echo "Unknown service $SERVICE" >&2
    exit 1
    ;;
esac
