## Airflow integration notes

This directory now ships the production-ready `telegram_collection` DAG. It orchestrates the
collection run through six Python tasks (health checks, collection, validation, reporting,
cleanup, notification) and relies on the shared `code.producer` module via `run_for_airflow`.

### How the DAG works

1. **`health_checks`** ensures PostgreSQL, Redis, and RabbitMQ are reachable using the same
   environment variables as the application services.
2. **`collect_messages`** executes `code.producer.run_for_airflow`, pushing a run summary to XCom.
3. **`validate_ingestion`** compares message counts inserted during the window with the producer
   summary for basic sanity checking.
4. **`generate_report`** composes a structured report saved to XCom for downstream consumers.
5. **`cleanup_old_messages`** applies retention (default 30 days) and triggers `VACUUM ANALYZE`.
6. **`notify_completion`** logs a completion message—extend this task to integrate Slack, email, etc.

### Required configuration

- Mount `code/` under `/opt/project/code` and ensure `.env` or equivalent environment variables are
  available to the Airflow container (Docker Compose does this automatically).
- Airflow connection variables map 1:1 with the service environment variables:
  - `API_ID`, `API_HASH`, `STRING_SESSION`
  - `POSTGRES_*` for the application database
  - `AIRFLOW_DB_*` automatically configured in Docker Compose for the metadata DB
  - `RABBITMQ_*`, `REDIS_*`
- Set `RETENTION_DAYS` if you want to override the default cleanup horizon.

### Testing the DAG locally

The Docker Compose stack provisions an Airflow metadata database and runs the
`airflow-init` service to initialize the environment. Once everything is up,
leave the services running—`telegram_collection` is scheduled to execute hourly
(`schedule_interval="@hourly"`), so the scheduler will trigger collections automatically.

Run the following to validate the DAG within the web UI:

```bash
docker compose -f deployment/docker-compose.yml up airflow-webserver airflow-scheduler
```

### Extending the DAG

- Add SLAs or alerts by expanding `notify_completion`.
- Replace the default cleanup task if you maintain historical archives elsewhere.
- Integrate downstream analytics tasks by branching off the report task.
