# Telegram OSINT System

An end-to-end data collection pipeline for Telegram OSINT research. The stack collects
messages from curated channels, publishes them to RabbitMQ, persists normalized records
in PostgreSQL, and orchestrates collection/validation with Apache Airflow.

## Highlights

- **Modular services** for collection (`producer`), processing (`worker`), and orchestration (Airflow).
- **Reliable ingestion** with RabbitMQ quorum queues, Redis-backed deduplication, and PostgreSQL connection pools.
- **Infrastructure as code** via Docker Compose, ready for local development or small-scale production.
- **Automation scripts** for bootstrapping, validating, and operating the platform.

## Project Layout

```
telegram-osint-system/
├── code/                   # Application source
├── deployment/             # Docker and database assets
├── docs/                   # In-depth documentation
├── logs/                   # Log mount points (gitignored)
├── scripts/                # Operational scripts
└── tests/                  # Pytest scaffolding
```

Refer to [`docs/SETUP.md`](docs/SETUP.md) for a detailed walkthrough.

## Quick Start

1. Copy `.env.example` to `.env` and provide Telegram credentials plus desired secrets.
2. Build and start the stack (keep it running so the Airflow scheduler can fire the hourly DAG runs):

   ```bash
   docker compose -f deployment/docker-compose.yml up --build
   ```

3. Verify health:

   ```bash
   ./scripts/04-test-connections.sh
   ```

4. Trigger a manual collection run:

   ```bash
   ./scripts/05-start-collection.sh
   ```

Airflow becomes available on http://localhost:8080 after initialization.

## Airflow DAG

The `telegram_collection` DAG orchestrates the run:

- Health checks for PostgreSQL, Redis, and RabbitMQ
- Producer execution with XCom summaries
- Data validation and reporting
- Retention cleanup with optional VACUUM

See [`code/dags/README_AIRFLOW.md`](code/dags/README_AIRFLOW.md) and [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) for configuration details.

## Testing

Install dependencies and run pytest:

```bash
pip install -r requirements.txt
pytest
```

## Contributing

1. Fork the repository and open a feature branch.
2. Keep scripts idempotent and document operational changes in `docs/`.
3. Add or update tests in `tests/` for new business logic.
