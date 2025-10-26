# Configuration Reference

This document describes the key environment variables and settings that control the Telegram OSINT system. All variables can be defined in `.env` and are referenced by Docker Compose and the application modules.

## Telegram

| Variable | Description |
|----------|-------------|
| `API_ID` | Telegram application ID |
| `API_HASH` | Telegram application hash |
| `STRING_SESSION` | Telethon session string (full access) |
| `TELEGRAM_MESSAGE_LIMIT` | Maximum messages to fetch per channel (default `200`) |
| `TELEGRAM_DELAY_BETWEEN_CHANNELS` | Seconds to wait between channels |
| `TELEGRAM_DELAY_BETWEEN_MESSAGES` | Delay between individual messages |
| `TELEGRAM_FETCH_RETRIES` | Max retries when encountering rate limits |

## RabbitMQ

| Variable | Default | Notes |
|----------|---------|-------|
| `RABBITMQ_HOST` | `rabbitmq` | Service hostname |
| `RABBITMQ_PORT` | `5672` | AMQP port |
| `RABBITMQ_USER` | `osint` | User configured in Docker Compose |
| `RABBITMQ_PASS` | `osint` | Password |
| `RABBITMQ_VHOST` | `/` | Virtual host |
| `RABBITMQ_QUEUE` | `tg.messages.v2` | Primary queue name |
| `RABBITMQ_HEARTBEAT` | `60` | Heartbeat interval |
| `RABBITMQ_PREFETCH` | `50` | Prefetch count for consumers |

## PostgreSQL (application)

| Variable | Default |
|----------|---------|
| `POSTGRES_USER` / `PGUSER` | `osint` |
| `POSTGRES_PASSWORD` / `PGPASSWORD` | `osint` |
| `POSTGRES_DB` / `PGDATABASE` | `osint` |
| `PGHOST` | `postgres` |
| `PGPORT` | `5432` |
| `POSTGRES_MIN_POOL` | `1` |
| `POSTGRES_MAX_POOL` | `10` |

## Redis

- `REDIS_HOST` (default `redis`)
- `REDIS_PORT` (default `6379`)
- `REDIS_DB` (default `0`)
- `REDIS_TTL_SECONDS` (default `86400`, 24 hours)

## Airflow Metadata

| Variable | Default | Usage |
|----------|---------|-------|
| `AIRFLOW_DB_USER` | `airflow` | Metadata DB user |
| `AIRFLOW_DB_PASSWORD` | `airflow` | Metadata DB password |
| `AIRFLOW_DB_NAME` | `airflow` | Metadata DB name |
| `AIRFLOW_FERNET_KEY` | *required* | Generate using `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `AIRFLOW_USERNAME` | `admin` | Web UI admin user |
| `AIRFLOW_PASSWORD` | `admin` | Web UI admin password |
| `AIRFLOW_EMAIL` | `admin@example.com` | Web UI admin email |

## Monitoring & Retention

- `LOG_LEVEL` (default `INFO`)
- `MONITORING_STATS_INTERVAL` (default `60` seconds)
- `RETENTION_DAYS` (default `30`) used by the DAG cleanup task.

## Docker Compose Profiles

The provided Compose file loads `.env` automatically. Update variables and re-run `docker compose up` to apply changes.
