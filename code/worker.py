from __future__ import annotations

import json
import logging
import signal
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Optional

import pika
from pika import spec
from pika.adapters.blocking_connection import BlockingChannel

from code.config.settings import AppSettings, load_settings
from code.utils.database import DatabasePool, create_pool
from code.utils.monitoring import StatsTracker, setup_logging
from code.utils.redis_client import RedisClient

logger = logging.getLogger(__name__)


class RabbitMQConsumer:
    def __init__(self, settings: AppSettings):
        self.settings = settings.rabbitmq
        self._connection: pika.BlockingConnection | None = None
        self._channel: BlockingChannel | None = None

    def connect(self) -> BlockingChannel:
        credentials = pika.PlainCredentials(self.settings.user, self.settings.password)
        params = pika.ConnectionParameters(
            host=self.settings.host,
            port=self.settings.port,
            virtual_host=self.settings.vhost,
            credentials=credentials,
            heartbeat=self.settings.heartbeat,
            blocked_connection_timeout=300,
        )
        self._connection = pika.BlockingConnection(params)
        channel = self._connection.channel()
        try:
            self._declare_queues(channel)
        except pika.exceptions.ChannelClosedByBroker:
            logger.warning("Queue declaration failed, recreating queues")
            channel = self._connection.channel()
            for name in (self.settings.queue, f"{self.settings.queue}.dlq"):
                try:
                    channel.queue_delete(queue=name)
                except pika.exceptions.ChannelClosedByBroker:
                    channel = self._connection.channel()
            self._declare_queues(channel)
        channel.basic_qos(prefetch_count=self.settings.prefetch)
        self._channel = channel
        logger.info("Worker connected to RabbitMQ queue %s", self.settings.queue)
        return channel

    def _declare_queues(self, channel: BlockingChannel) -> None:
        dlq = {"x-queue-type": "quorum"}
        main = {
            "x-queue-type": "quorum",
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": f"{self.settings.queue}.dlq",
        }
        channel.queue_declare(queue=f"{self.settings.queue}.dlq", durable=self.settings.durable, arguments=dlq)
        channel.queue_declare(queue=self.settings.queue, durable=self.settings.durable, arguments=main)

    def channel(self) -> BlockingChannel:
        if not self._channel:
            raise RuntimeError("RabbitMQ channel is not connected")
        return self._channel

    def close(self) -> None:
        if self._channel and self._channel.is_open:
            self._channel.close()
        if self._connection and self._connection.is_open:
            self._connection.close()


class MessageWorker:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.db: DatabasePool = create_pool(settings.postgres)
        self.redis = RedisClient(settings.redis)
        self.mq = RabbitMQConsumer(settings)
        self.stats = StatsTracker()
        self.channel_totals: Dict[str, int] = defaultdict(int)
        self._stop_event = threading.Event()
        self._report_thread: Optional[threading.Thread] = None

    def ensure_schema(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS collection_runs (
            id BIGSERIAL PRIMARY KEY,
            run_id TEXT UNIQUE NOT NULL,
            channel_username TEXT NOT NULL,
            messages_collected INTEGER DEFAULT 0,
            inserted_messages INTEGER DEFAULT 0,
            start_time TIMESTAMPTZ,
            end_time TIMESTAMPTZ,
            status TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_runs_channel ON collection_runs(channel_username);
        CREATE INDEX IF NOT EXISTS idx_runs_start_time ON collection_runs(start_time DESC);

        CREATE TABLE IF NOT EXISTS messages (
            channel_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            date TIMESTAMPTZ NOT NULL,
            message_hash TEXT NOT NULL,
            channel_username TEXT NOT NULL,
            text TEXT,
            views INTEGER,
            forwards INTEGER,
            replies INTEGER,
            reply_to_message_id BIGINT,
            has_media BOOLEAN,
            media_type TEXT,
            run_id TEXT,
            collected_at TIMESTAMPTZ DEFAULT NOW(),
            inserted_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (channel_id, message_id, date)
        ) PARTITION BY RANGE (date);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_hash ON messages (message_hash, date);
        CREATE INDEX IF NOT EXISTS idx_messages_channel_date ON messages (channel_id, date DESC);
        CREATE INDEX IF NOT EXISTS idx_messages_run_id ON messages (run_id);

        CREATE OR REPLACE FUNCTION set_messages_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS set_messages_updated_at ON messages;
        CREATE TRIGGER set_messages_updated_at
        BEFORE UPDATE ON messages
        FOR EACH ROW
        EXECUTE FUNCTION set_messages_updated_at();
        """
        with self.db.cursor() as cur:
            cur.execute(ddl)
        logger.info("Database schema ensured")

    def _parse_datetime(self, value: Optional[str]) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            logger.warning("Invalid datetime %s, defaulting to now()", value)
            return datetime.now(timezone.utc)

    def handle_run_start(self, payload: Dict[str, object]) -> None:
        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO collection_runs (run_id, channel_username, messages_collected, start_time, status)
                VALUES (%s, %s, 0, to_timestamp(%s), %s)
                ON CONFLICT (run_id) DO NOTHING;
                """,
                (
                    payload.get("run_id"),
                    payload.get("channel_username"),
                    payload.get("ts"),
                    payload.get("status", "running"),
                ),
            )
        logger.debug("Registered run start for %s", payload.get("channel_username"))

    def handle_run_end(self, payload: Dict[str, object]) -> None:
        with self.db.cursor() as cur:
            cur.execute(
                """
                UPDATE collection_runs
                   SET end_time = to_timestamp(%s),
                       status = %s,
                       messages_collected = COALESCE(%s, messages_collected),
                       inserted_messages = GREATEST(inserted_messages, COALESCE(%s, inserted_messages))
                 WHERE run_id = %s;
                """,
                (
                    payload.get("ts"),
                    payload.get("status", "success"),
                    payload.get("messages_collected"),
                    payload.get("messages_collected"),
                    payload.get("run_id"),
                ),
            )
        logger.debug("Registered run end for %s", payload.get("channel_username"))

    def handle_message(self, payload: Dict[str, object]) -> None:
        self.stats.increment("messages_received")
        key = payload.get("key")
        if not key:
            logger.warning("Message without dedup key, skipping")
            self.stats.increment("errors")
            return
        redis_key = f"tg:message:{key}"
        if not self.redis.mark_once(redis_key):
            self.stats.increment("duplicates")
            return

        dt = self._parse_datetime(payload.get("date"))
        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages (
                    channel_id,
                    message_id,
                    date,
                    message_hash,
                    channel_username,
                    text,
                    views,
                    forwards,
                    replies,
                    reply_to_message_id,
                    has_media,
                    media_type,
                    run_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (channel_id, message_id, date) DO NOTHING
                RETURNING channel_id;
                """,
                (
                    payload.get("channel_id"),
                    payload.get("message_id"),
                    dt,
                    payload.get("key"),
                    payload.get("channel_username"),
                    payload.get("text"),
                    payload.get("views"),
                    payload.get("forwards"),
                    payload.get("replies"),
                    payload.get("reply_to_message_id"),
                    payload.get("has_media"),
                    payload.get("media_type"),
                    payload.get("run_id"),
                ),
            )
            inserted = cur.fetchone() is not None
        if inserted:
            self.stats.increment("inserted")
            channel_username = payload.get("channel_username") or "unknown"
            self.channel_totals[channel_username] += 1
            run_id = payload.get("run_id")
            if run_id:
                with self.db.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE collection_runs
                           SET messages_collected = messages_collected + 1,
                               inserted_messages = inserted_messages + 1
                         WHERE run_id = %s;
                        """,
                        (run_id,),
                    )
        else:
            self.stats.increment("duplicates")

    def _reporter(self) -> None:
        interval = self.settings.worker.report_interval
        while not self._stop_event.wait(interval):
            snapshot = self.stats.snapshot()
            logger.info(
                "Worker stats | received=%s inserted=%s duplicates=%s errors=%s uptime=%.1fs",
                snapshot.get("messages_received", 0),
                snapshot.get("inserted", 0),
                snapshot.get("duplicates", 0),
                snapshot.get("errors", 0),
                self.stats.uptime(),
            )

    def start_reporting(self) -> None:
        thread = threading.Thread(target=self._reporter, daemon=True)
        thread.start()
        self._report_thread = thread

    def stop(self) -> None:
        self._stop_event.set()
        self.mq.close()
        self.db.closeall()

    def _on_message(self, channel: BlockingChannel, method: spec.Basic.Deliver, properties, body: bytes) -> None:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            logger.error("Invalid JSON payload received")
            self.stats.increment("errors")
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return

        event_type = payload.get("type", "message")
        try:
            if event_type == "run_start":
                self.handle_run_start(payload)
            elif event_type == "run_end":
                self.handle_run_end(payload)
            else:
                self.handle_message(payload)
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to process payload")
            self.stats.increment("errors")
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def install_signal_handlers(self) -> None:
        def _stop_handler(signum, _frame):
            logger.info("Received signal %s, stopping worker gracefully", signum)
            self.stop()

        signal.signal(signal.SIGTERM, _stop_handler)
        signal.signal(signal.SIGINT, _stop_handler)

    def consume(self) -> None:
        channel = self.mq.connect()
        channel.basic_consume(queue=self.settings.rabbitmq.queue, on_message_callback=self._on_message)
        try:
            logger.info("Worker consuming messages...")
            channel.start_consuming()
        except KeyboardInterrupt:  # pragma: no cover - interactive stop
            logger.info("Keyboard interrupt received, shutting down")
        finally:
            self.stop()


def run(settings: AppSettings | None = None) -> None:
    app_settings = settings or load_settings()
    setup_logging(app_settings.monitoring.log_level)
    worker = MessageWorker(app_settings)
    worker.ensure_schema()
    if not worker.redis.ping():
        logger.warning("Redis ping failed during startup")
    worker.install_signal_handlers()
    worker.start_reporting()
    worker.consume()


if __name__ == "__main__":  # pragma: no cover - manual execution
    run()
