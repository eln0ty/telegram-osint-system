#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE=${COMPOSE_FILE:-deployment/docker-compose.yml}

echo "[init] Bringing up core services (Postgres, Airflow DB, Redis, RabbitMQ)..."
docker compose -f "$COMPOSE_FILE" up --build -d postgres airflow-db redis rabbitmq

echo "[init] Ensuring application image is built..."
docker compose -f "$COMPOSE_FILE" build producer

echo "[init] Core infrastructure is running. Use ./scripts/03-init-airflow.sh next."
