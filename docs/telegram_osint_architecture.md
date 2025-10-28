# OSINT Telegram Collection System – Architecture Design

This document captures the updated architecture for the Telegram OSINT platform, aligning the codebase, Docker stack, and Airflow orchestration.

---

## 1. System Architecture

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          APACHE AIRFLOW                             │
│  ┌──────────────┐  ┌────────────────┐  ┌─────────────────┐          │
│  │  Scheduler   │→ │  DAG Executor  │→ │   Task Monitor  │          │
│  └──────────────┘  └─────────┬──────┘  └─────────────────┘          │
│                              │  Trigger Hourly via Scheduler        │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  PRODUCER (Batch)   │  Airflow-triggered
                    │  • Health Checks    │  • Collect 200/channel
                    │  • Rate Limiting    │  • Stats Reporting
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │     RABBITMQ        │  Quorum Queue + DLQ
                    │  Durable, HA Ready  │  • Backpressure buffer
                    └──────────┬──────────┘
                               │
                  ┌────────────┼───────────┐
                  │            │           │
           ┌──────▼─────┐ ┌────▼────┐ ┌────▼─────┐
           │  WORKER 1  │ │WORKER 2 │ │ WORKER 3 │  Always running
           │ • Validate │ │• Dedup  │ │ • Persist│  • Auto-scale
           └──────┬─────┘ └────┬────┘ └────┬─────┘
                  │            │           │
                  └────────────┼───────────┘
                               │
              ┌────────────────┴───────────────┐
              │                │               │
      ┌───────▼──────┐ ┌───────▼──────┐ ┌──────▼─────────┐
      │ POSTGRESQL   │ │    REDIS     │ │ ELASTICSEARCH* │
      │ • Partitions │ │ • Dedup TTL  │ │ • Analytics    │
      │ • Run logs   │ │ • Fail-open  │ │ • Full-text    │
      └──────────────┘ └──────────────┘ └────────────────┘
```

\* Elasticsearch integration remains optional; This release focuses on PostgreSQL as the system of record.

---

## 2. Airflow Integration

### Why Airflow?

| Feature                  | Benefit                                                          |
| ------------------------ | ---------------------------------------------------------------- |
| **Scheduled Runs** | Controlled, low-risk collection windows (02:00 daily default).   |
| **Orchestration**  | Health → collection → validation → reporting in a single DAG. |
| **Retry Logic**    | Native exponential backoff with per-task retry policies.         |
| **Observability**  | DAG visualisation, task-level logs, SLA and duration tracking.   |
| **Extensibility**  | Easy to append enrichment, exports, or alerting tasks.           |

### DAG Structure

```
health_checks
    → collect_messages
        → validate_ingestion
            → generate_report
                → cleanup_old_messages
                    → notify_completion
```

- **health_checks** – Pings PostgreSQL, Redis, RabbitMQ before the run.
- **collect_messages** – Invokes `code.producer.run_for_airflow`, storing summaries in XCom.
- **validate_ingestion** – Confirms the expected row counts landed in PostgreSQL.
- **generate_report** – Serialises run metrics for dashboards/alerts.
- **cleanup_old_messages** – Applies retention (`RETENTION_DAYS`) and VACUUM ANALYZE.
- **notify_completion** – Emits final status (extend for Slack, email, etc.).

Airflow containers share the project `.env`, guaranteeing parity with application services.

---

## 3. Data Flow

1. **Collection** – `TelegramProducer` fetches channel batches, handles `FloodWaitError`, and publishes message/run events with deterministic hashes.
2. **Queueing** – RabbitMQ quorum queue (`tg.messages.v2`) buffers traffic; DLQ captures poison messages.
3. **Processing** – `MessageWorker` validates payloads, dedups via Redis (`SETNX` fail-open), persists to partitioned `messages`, and increments `collection_runs`.
4. **Validation & Reporting** – Airflow cross-checks ingestion counts, assembles structured reports, and exposes telemetry.
5. **Retention** – Airflow cleanup task deletes data older than `RETENTION_DAYS` and maintains statistics.

---

## 4. Component Responsibilities

| Component     | Responsibilities                                                          | Stack                        |
| ------------- | ------------------------------------------------------------------------- | ---------------------------- |
| Producer      | Telegram API IO, retry/backoff, message enrichment, run lifecycle events  | Python 3.11, Telethon        |
| RabbitMQ      | Durable queueing, DLQ routing, backpressure, HA readiness                 | RabbitMQ 3.13 (quorum)       |
| Worker        | Deduplication, persistence, Redis fail-open, reporting, graceful shutdown | Python 3.11, psycopg2, Redis |
| Storage       | Partitioned tables, run history, schema triggers, retention policies      | PostgreSQL 15                |
| Orchestration | Health checks, scheduling, validation, cleanup, notifications             | Apache Airflow 2.8           |

---

## 5. Database Schema Highlights

- `collection_runs` – Stores per-channel run metadata, timestamps, status, and message counts.
- `messages` – Monthly partitions via `create-partitions.sql`; primary key `(channel_id, message_id, date)` with a unique `(message_hash, date)` index for dedup defence.
- Trigger `set_messages_updated_at` maintains `updated_at` for downstream consumers.
- `ingestion_errors` (optional) records poisoned payloads when manual inspection is required.

---

## 6. Reliability, Scaling, and Operations

- **Backpressure** – Workers ACK only after successful commits; RabbitMQ durability plus DLQ ensures at-least-once delivery.
- **Retry Strategy** – Producer retries Telegram rate limits with exponential waits; workers `nack` transient failures to requeue.
- **Horizontal Scale** – Increase producer shard count via Airflow parameters; scale workers (`scripts/scale-workers.sh`) or migrate to container orchestration for HA.
- **Observability** – `StatsTracker` emits periodic counters; extend `code/utils/monitoring.py` with Prometheus/Grafana exporters for production.
- **Partitions** – Refresh monthly via `scripts/02-create-tables.sh` or schedule DAG automation to avoid hot partitions.
- **Backups** – Use `scripts/backup-database.sh` and `scripts/restore-database.sh`; integrate with S3/Blob storage for offsite retention.

---

## 7. Roadmap & Future Enhancements

- Integrate enrichment workers (NLP, IOC extraction) downstream of `generate_report`.
- Add Prometheus exporters for RabbitMQ depth, worker throughput, and Postgres health.
- Support multi-tenant channel groups through Airflow params and dynamic task mapping.
- Evaluate Kafka or cloud-native messaging when daily volume exceeds 10M messages.

This architecture balances resiliency, observability, and modularity—enabling teams to expand OSINT coverage while maintaining operational confidence.
