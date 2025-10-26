# Troubleshooting

Common issues and quick fixes for the Telegram OSINT system.

## Producer fails to start

- **Symptom**: `STRING_SESSION missing` or Telethon authentication errors.
- **Fix**: Ensure `.env` contains valid `API_ID`, `API_HASH`, and `STRING_SESSION`. Generate a new session using the Telethon interactive script if credentials expired.

## RabbitMQ Queue Not Receiving Messages

- **Symptom**: Worker idle, queue depth zero, no producer logs.
- **Fix**: Check RabbitMQ health (`docker compose ... logs rabbitmq`). Confirm `RABBITMQ_*` variables match the Compose file. Restart the producer container after fixing credentials.

## Worker High Duplicate Rate

- **Symptom**: Worker logs show `duplicates` incrementing rapidly.
- **Fix**: Verify Redis availability (`./scripts/04-test-connections.sh`). If Redis is unavailable the worker fails open, so duplicates may appear. Restore Redis and consider lowering TTL to reclaim keys faster.

## PostgreSQL Deadlocks or Timeouts

- **Symptom**: Worker logs indicate `psycopg2` errors and `nack`.
- **Fix**: Increase `POSTGRES_MAX_POOL`, ensure partitions exist, and run `VACUUM ANALYZE` on large partitions. Inspect DB logs for blocking transactions.

## Airflow Webserver 404/Healthcheck Failing

- **Symptom**: Docker health check fails, service restarts repeatedly.
- **Fix**: Confirm `AIRFLOW_FERNET_KEY` is set and matches across all Airflow services. Run `docker compose ... logs airflow-webserver` to view stack traces. Re-run `airflow-init` if the metadata DB was reset.

## Missing Data After Successful Run

- **Symptom**: Producer reports messages but validation fails.
- **Fix**: Inspect DLQ (`docker compose exec rabbitmq rabbitmqadmin get queue=tg.messages.v2.dlq`). Messages in DLQ may need manual replay after fixing parsing issues. Also confirm `messages` partitions extend beyond the run date.

## Slow Queries

- **Symptom**: Dashboards or analytics queries degrade.
- **Fix**: Ensure indexes defined in `init.sql` exist on new partitions. Run `ANALYZE messages_<yyyymm>` after large backfills.
