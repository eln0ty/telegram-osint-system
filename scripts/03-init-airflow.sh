#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE=${COMPOSE_FILE:-deployment/docker-compose.yml}

echo "[airflow] Running initialization container..."
docker compose -f "$COMPOSE_FILE" build airflow-webserver airflow-scheduler
docker compose -f "$COMPOSE_FILE" up airflow-init

echo "[airflow] Starting webserver and scheduler..."
docker compose -f "$COMPOSE_FILE" up -d airflow-webserver airflow-scheduler

echo "[airflow] Visit http://localhost:8080 to log in."
