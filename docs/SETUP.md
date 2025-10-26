# Setup Guide

This guide walks through provisioning the Telegram OSINT system from scratch.

## 1. Prerequisites

- Docker Engine 24+
- Docker Compose v2
- Telegram API credentials (API ID, API Hash, session string)
- Optional: Python 3.11+ for running tests locally

## 2. Clone and Configure

```bash
git clone <repo-url> telegram-osint-system
cd telegram-osint-system
cp .env.example .env
```

Edit `.env` with your Telegram credentials and adjust passwords as needed.

## 3. Build and Launch

```bash
docker compose -f deployment/docker-compose.yml up --build -d
```

Services started:

- `postgres`: application database
- `airflow-db`: Airflow metadata store
- `redis`: deduplication cache
- `rabbitmq`: messaging backbone
- `producer`: Telegram collector
- `worker`: message processor (3 replicas)
- `airflow-webserver`, `airflow-scheduler`: orchestration UI and scheduler

Monitor logs:

```bash
docker compose -f deployment/docker-compose.yml logs -f producer worker
```

## 4. Initialize Database Partitions

The Docker Compose init step already loads `init.sql`. To top up partitions:

```bash
docker compose -f deployment/docker-compose.yml exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -f /docker-entrypoint-initdb.d/01-create-partitions.sql
```

Run this monthly (or automate via cron/DAG) to maintain future partitions.

## 5. Validate Connectivity

Use the provided script:

```bash
./scripts/04-test-connections.sh
```

It checks PostgreSQL, Redis, and RabbitMQ endpoints using the values from `.env`.

## 6. Airflow Access

Visit http://localhost:8080 and log in with the credentials from `.env`.
Enable the `telegram_collection` DAG and trigger a manual run to verify end-to-end flow.

## 7. Shutdown and Cleanup

```bash
docker compose -f deployment/docker-compose.yml down
```

To remove all persisted data (Postgres volumes), append `-v`.
