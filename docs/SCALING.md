# Scaling Guide

This guide outlines strategies to scale the Telegram OSINT system as channel volume
and ingestion rates increase.

## Service Layer

| Stage | Approx. Channels | Recommended Actions |
|-------|------------------|---------------------|
| Bootstrap | 1–50 | Single producer + 1 worker replica. Default Docker Compose footprint. |
| Growth | 50–500 | Add producer containers with channel sharding; bump worker replicas to 3–5; enable metrics collection. |
| Expansion | 500–5k | Separate RabbitMQ/PostgreSQL nodes; enable HA with replication; add autoscaling triggers based on queue depth. |
| Enterprise | 5k+ | Migrate to Kubernetes or Nomad; replace RabbitMQ with Kafka; use managed Postgres (Timescale/Neon). |

## Database

- **Partition Management**: run `deployment/postgres/create-partitions.sql` monthly to keep partitions ahead of ingestion.
- **Connection Pooling**: adjust `POSTGRES_MIN_POOL`/`POSTGRES_MAX_POOL` according to worker replica count.
- **Vacuum Strategy**: schedule regular `VACUUM ANALYZE` on large partitions or rely on autovacuum tuning.

## Queueing

- Monitor queue depth; sustained backlog >10k messages indicates the need for more workers.
- Use RabbitMQ policies to mirror quorum queues when running in a cluster.

## Redis

- Scale vertically for memory; dedup keys expire after `REDIS_TTL_SECONDS`, so memory is proportional to unique messages within that window.
- For HA, deploy Redis Sentinel or Redis Cluster with consistent hashing.

## Observability

- Export worker statistics via Prometheus for visibility into throughput, duplicates, and errors.
- Set alerts on `messages_received` vs. `inserted` delta to detect processing issues.

## Backups & Disaster Recovery

- Use `scripts/backup-database.sh` and `scripts/restore-database.sh` as the base for automated backups.
- Store WAL archives offsite for point-in-time recovery (PITR) if data loss tolerance is low.
