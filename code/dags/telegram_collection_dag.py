from __future__ import annotations

import logging
from datetime import timedelta
from typing import Dict

import os

import pika
import psycopg2
import redis
from airflow import DAG
from airflow.exceptions import AirflowFailException
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

from code.config.settings import load_settings
from code.producer import run_for_airflow

logger = logging.getLogger(__name__)

DEFAULT_ARGS = {
    "owner": "osint",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))


def _postgres_ping() -> None:
    settings = load_settings().postgres
    with psycopg2.connect(
        host=settings.host,
        port=settings.port,
        user=settings.user,
        password=settings.password,
        dbname=settings.database,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()


def _redis_ping() -> None:
    settings = load_settings().redis
    client = redis.Redis(
        host=settings.host,
        port=settings.port,
        db=settings.db,
        password=settings.password,
    )
    if not client.ping():
        raise AirflowFailException("Redis ping failed")


def _rabbitmq_ping() -> None:
    settings = load_settings().rabbitmq
    credentials = pika.PlainCredentials(settings.user, settings.password)
    params = pika.ConnectionParameters(
        host=settings.host,
        port=settings.port,
        virtual_host=settings.vhost,
        credentials=credentials,
        heartbeat=30,
        blocked_connection_timeout=10,
    )
    connection = pika.BlockingConnection(params)
    connection.close()


def health_checks() -> Dict[str, str]:
    try:
        _postgres_ping()
        _redis_ping()
        _rabbitmq_ping()
    except Exception as exc:  # pragma: no cover - Airflow runtime validation
        raise AirflowFailException(f"Dependency health check failed: {exc}") from exc
    return {"status": "ok"}


def trigger_collection(**context) -> Dict[str, object]:
    summary = run_for_airflow()
    context["ti"].xcom_push(key="collection_summary", value=summary)
    return summary


def validate_ingestion(**context) -> Dict[str, int]:
    ti = context["ti"]
    summary = ti.xcom_pull(task_ids="collect_messages", key="collection_summary") or {}
    expected = sum(ch.get("messages", 0) for ch in summary.get("channels", []))
    settings = load_settings().postgres
    with psycopg2.connect(
        host=settings.host,
        port=settings.port,
        user=settings.user,
        password=settings.password,
        dbname=settings.database,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                  FROM messages
                 WHERE collected_at >= NOW() - INTERVAL '6 hours';
                """
            )
            count = cur.fetchone()[0]
    if expected and count < expected // 2:
        raise AirflowFailException(
            f"Ingestion validation failed: expected at least {expected // 2} rows, found {count}"
        )
    return {"rows_ingested": count}


def generate_run_report(**context) -> Dict[str, object]:
    ti = context["ti"]
    summary = ti.xcom_pull(task_ids="collect_messages", key="collection_summary") or {}
    validation = ti.xcom_pull(task_ids="validate_ingestion") or {}
    report = {
        "channels": summary.get("channels", []),
        "messages_requested": summary.get("messages", 0),
        "messages_validated": validation.get("rows_ingested", 0),
    }
    logger.info("Run report: %s", report)
    return report


def cleanup_old_messages() -> None:
    settings = load_settings().postgres
    conn_args = dict(
        host=settings.host,
        port=settings.port,
        user=settings.user,
        password=settings.password,
        dbname=settings.database,
    )
    deleted = 0
    with psycopg2.connect(**conn_args) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM messages
                 WHERE collected_at < NOW() - INTERVAL %s;
                """,
                (f"{RETENTION_DAYS} days",),
            )
            deleted = cur.rowcount or 0

    vacuum_conn = psycopg2.connect(**conn_args)
    try:
        vacuum_conn.set_session(autocommit=True)
        with vacuum_conn.cursor() as cur:
            cur.execute("VACUUM ANALYZE messages;")
    finally:
        vacuum_conn.close()
    logger.info("Cleaned up %s stale rows older than %s days", deleted, RETENTION_DAYS)


def notify_completion(**context) -> None:
    ti = context["ti"]
    report = ti.xcom_pull(task_ids="generate_report") or {}
    logger.info("Telegram collection complete: %s", report)


with DAG(
    dag_id="telegram_collection",
    default_args=DEFAULT_ARGS,
    description="Collect Telegram OSINT data and validate ingestion.",
    schedule_interval="@hourly",
    start_date=days_ago(1),
    catchup=False,
) as dag:
    start = EmptyOperator(task_id="start")

    readiness = PythonOperator(
        task_id="health_checks",
        python_callable=health_checks,
    )

    collect = PythonOperator(
        task_id="collect_messages",
        python_callable=trigger_collection,
        provide_context=True,
    )

    validate = PythonOperator(
        task_id="validate_ingestion",
        python_callable=validate_ingestion,
        provide_context=True,
    )

    report = PythonOperator(
        task_id="generate_report",
        python_callable=generate_run_report,
        provide_context=True,
    )

    cleanup = PythonOperator(
        task_id="cleanup_old_messages",
        python_callable=cleanup_old_messages,
    )

    notify = PythonOperator(
        task_id="notify_completion",
        python_callable=notify_completion,
        provide_context=True,
    )

    end = EmptyOperator(task_id="end")

    start >> readiness >> collect >> validate >> report >> cleanup >> notify >> end
