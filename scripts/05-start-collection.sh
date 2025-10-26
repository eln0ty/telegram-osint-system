#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE=${COMPOSE_FILE:-deployment/docker-compose.yml}

echo "[run] Starting producer and worker services..."
docker compose -f "$COMPOSE_FILE" up -d producer worker

if docker compose -f "$COMPOSE_FILE" ps airflow-webserver >/dev/null 2>&1; then
  echo "[run] Triggering Airflow DAG telegram_collection..."
  docker compose -f "$COMPOSE_FILE" exec -T airflow-webserver airflow dags trigger telegram_collection
else
  echo "[run] Airflow not running; skip DAG trigger."
fi

echo "[run] Tail logs with: docker compose -f $COMPOSE_FILE logs -f producer worker"
