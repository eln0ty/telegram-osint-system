#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE=${COMPOSE_FILE:-deployment/docker-compose.yml}
DB=${POSTGRES_DB:-osint}
USER=${POSTGRES_USER:-osint}

echo "[health] Checking PostgreSQL..."
docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "$USER" -d "$DB"

echo "[health] Checking Redis..."
docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping

echo "[health] Checking RabbitMQ..."
docker compose -f "$COMPOSE_FILE" exec -T rabbitmq rabbitmq-diagnostics ping

echo "[health] All core services responded successfully."
