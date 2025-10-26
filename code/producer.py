from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Dict, List

import pika
from pika.adapters.blocking_connection import BlockingChannel
from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from telethon.sessions import StringSession

from code.config.settings import AppSettings, load_settings
from code.utils.monitoring import StatsTracker, setup_logging

logger = logging.getLogger(__name__)


@dataclass
class QueueArguments:
    main: Dict[str, object]
    dlq: Dict[str, object]


class RabbitMQClient:
    def __init__(self, settings: AppSettings):
        self.settings = settings.rabbitmq
        self._connection: pika.BlockingConnection | None = None
        self._channel: BlockingChannel | None = None
        self._queue_args = QueueArguments(
            main={
                "x-queue-type": "quorum",
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": f"{self.settings.queue}.dlq",
            },
            dlq={"x-queue-type": "quorum"},
        )

    @property
    def channel(self) -> BlockingChannel:
        if not self._channel:
            raise RuntimeError("RabbitMQ channel not initialized")
        return self._channel

    def connect(self) -> None:
        logger.info("Connecting to RabbitMQ at %s:%s", self.settings.host, self.settings.port)
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
            logger.warning("Queue declaration failed (likely stale arguments). Recreating queues.")
            channel = self._connection.channel()
            for name in (self.settings.queue, f"{self.settings.queue}.dlq"):
                try:
                    channel.queue_delete(queue=name)
                except pika.exceptions.ChannelClosedByBroker:
                    channel = self._connection.channel()
            self._declare_queues(channel)
        channel.basic_qos(prefetch_count=self.settings.prefetch)
        channel.confirm_delivery()
        self._channel = channel
        logger.info("RabbitMQ channel ready (queue=%s)", self.settings.queue)

    def _declare_queues(self, channel: BlockingChannel) -> None:
        channel.queue_declare(
            queue=f"{self.settings.queue}.dlq",
            durable=self.settings.durable,
            arguments=self._queue_args.dlq,
        )
        channel.queue_declare(
            queue=self.settings.queue,
            durable=self.settings.durable,
            arguments=self._queue_args.main,
        )

    def publish(self, payload: Dict[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.channel.basic_publish(
            exchange="",
            routing_key=self.settings.queue,
            body=body,
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
        )

    def publish_run_event(self, event_type: str, channel_username: str, run_id: str, **extra: object) -> None:
        payload = {
            "type": event_type,
            "channel_username": channel_username,
            "run_id": run_id,
            "ts": time.time(),
        }
        payload.update(extra)
        self.publish(payload)

    def close(self) -> None:
        if self._channel and self._channel.is_open:
            logger.info("Closing RabbitMQ channel")
            self._channel.close()
        if self._connection and self._connection.is_open:
            logger.info("Closing RabbitMQ connection")
            self._connection.close()


class TelegramProducer:
    def __init__(self, settings: AppSettings, mq: RabbitMQClient):
        self.settings = settings
        self.mq = mq
        self.stats = StatsTracker()

    @staticmethod
    def _message_key(channel_id: int, message_id: int) -> str:
        return hashlib.sha256(f"{channel_id}:{message_id}".encode()).hexdigest()

    async def _collect_channel(self, client: TelegramClient, channel_username: str) -> Dict[str, object]:
        run_id = str(uuid.uuid4())
        retries = self.settings.telegram.fetch_retries
        delay = self.settings.telegram.delay_between_messages
        self.mq.publish_run_event("run_start", channel_username, run_id, status="running", messages_collected=0)

        for attempt in range(retries + 1):
            try:
                entity = await client.get_entity(channel_username)
                collected = 0
                async for msg in client.iter_messages(entity, limit=self.settings.telegram.message_limit):
                    if not (msg.message or msg.media):
                        continue
                    channel_id = getattr(getattr(msg, "peer_id", None), "channel_id", None)
                    if channel_id is None:
                        channel_id = getattr(entity, "id", 0)
                    payload = {
                        "type": "message",
                        "run_id": run_id,
                        "key": self._message_key(channel_id, msg.id),
                        "channel_id": channel_id,
                        "channel_username": getattr(entity, "username", channel_username),
                        "message_id": msg.id,
                        "date": msg.date.isoformat() if msg.date else None,
                        "text": msg.message or "",
                        "views": msg.views or 0,
                        "forwards": msg.forwards or 0,
                        "has_media": bool(msg.media),
                        "media_type": type(msg.media).__name__ if msg.media else None,
                        "reply_to_message_id": getattr(getattr(msg, "reply_to", None), "reply_to_msg_id", None),
                        "replies": getattr(getattr(msg, "replies", None), "replies", 0),
                    }
                    self.mq.publish(payload)
                    collected += 1
                    self.stats.increment("messages_published")
                    await asyncio.sleep(delay)

                self.mq.publish_run_event(
                    "run_end",
                    channel_username,
                    run_id,
                    status="success",
                    messages_collected=collected,
                )
                logger.info("Collected %s messages from %s", collected, channel_username)
                return {"channel": channel_username, "messages": collected, "status": "success", "run_id": run_id}

            except FloodWaitError as exc:
                wait_seconds = exc.seconds + 5
                logger.warning(
                    "FloodWait while collecting %s: sleeping %s seconds (attempt %s/%s)",
                    channel_username,
                    wait_seconds,
                    attempt + 1,
                    retries + 1,
                )
                self.mq.publish_run_event(
                    "run_end",
                    channel_username,
                    run_id,
                    status="flood_wait",
                    messages_collected=0,
                    retry=attempt + 1,
                    wait_seconds=wait_seconds,
                )
                await asyncio.sleep(wait_seconds)
            except RPCError as exc:
                logger.error("RPC error while collecting %s: %s", channel_username, exc)
                break
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Unexpected error while collecting %s", channel_username)
                self.mq.publish_run_event(
                    "run_end",
                    channel_username,
                    run_id,
                    status="error",
                    messages_collected=0,
                    error=str(exc),
                )
                return {"channel": channel_username, "messages": 0, "status": "error", "run_id": run_id}

        logger.error("Failed to collect messages from %s after %s attempts", channel_username, retries + 1)
        return {"channel": channel_username, "messages": 0, "status": "failed", "run_id": run_id}

    async def run(self) -> Dict[str, object]:
        telegram = self.settings.telegram
        if not telegram.session:
            raise RuntimeError("STRING_SESSION / TELEGRAM_SESSION is required.")
        if not telegram.api_id or not telegram.api_hash:
            raise RuntimeError("TELEGRAM API credentials are missing.")
        if not telegram.channels:
            logger.warning("No channels configured. Nothing to collect.")
            return {"channels": [], "messages": 0}

        per_channel: List[Dict[str, object]] = []
        self.mq.connect()

        try:
            async with TelegramClient(
                StringSession(telegram.session),
                telegram.api_id,
                telegram.api_hash,
            ) as client:
                for index, channel_username in enumerate(telegram.channels):
                    if index > 0:
                        await asyncio.sleep(telegram.delay_between_channels)
                    result = await self._collect_channel(client, channel_username)
                    per_channel.append(result)
        finally:
            self.mq.close()
        total = sum(item["messages"] for item in per_channel)
        return {"channels": per_channel, "messages": total, "stats": self.stats.snapshot()}


async def _run_async(settings: AppSettings | None = None) -> Dict[str, object]:
    app_settings = settings or load_settings()
    setup_logging(app_settings.monitoring.log_level)
    producer = TelegramProducer(app_settings, RabbitMQClient(app_settings))
    return await producer.run()


def run(settings: AppSettings | None = None) -> Dict[str, object]:
    return asyncio.run(_run_async(settings))


def run_for_airflow(**_context: object) -> Dict[str, object]:  # pragma: no cover - Airflow entry point
    return run()


if __name__ == "__main__":  # pragma: no cover - manual execution
    summary = run()
    logger.info("Producer completed: total_messages=%s", summary.get("messages", 0))
