import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parents[2]
CHANNELS_FILE = Path(__file__).with_name("channels.yaml")
DEFAULT_ENV_PATH = BASE_DIR / ".env"


def _maybe_load_dotenv() -> None:
    """
    Attempt to load a .env file if python-dotenv is available.
    The load is lazy so the module remains optional.
    """
    if load_dotenv and DEFAULT_ENV_PATH.exists():
        load_dotenv(DEFAULT_ENV_PATH, override=False)


def _get_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _load_channels() -> List[str]:
    if CHANNELS_FILE.exists():
        with CHANNELS_FILE.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        channels = data.get("channels", [])
        if isinstance(channels, list):
            return [str(c).strip() for c in channels if c]
    # fallback to env variable if provided
    return _get_list(os.getenv("TELEGRAM_CHANNELS", ""))


@dataclass
class TelegramSettings:
    api_id: int
    api_hash: str
    session: str
    channels: List[str] = field(default_factory=list)
    message_limit: int = 200
    delay_between_channels: float = 2.0
    delay_between_messages: float = 0.1
    fetch_retries: int = 3


@dataclass
class RabbitMQSettings:
    host: str
    user: str
    password: str
    vhost: str = "/"
    queue: str = "tg.messages.v2"
    port: int = 5672
    heartbeat: int = 60
    prefetch: int = 50
    durable: bool = True


@dataclass
class PostgresSettings:
    host: str
    port: int
    user: str
    password: str
    database: str
    min_pool_size: int = 1
    max_pool_size: int = 10


@dataclass
class RedisSettings:
    host: str
    port: int
    db: int = 0
    password: Optional[str] = None
    ttl_seconds: int = 86400


@dataclass
class MonitoringSettings:
    stats_interval: int = 60
    log_level: str = "INFO"


@dataclass
class ProducerSettings:
    enable_airflow_mode: bool = False


@dataclass
class WorkerSettings:
    batch_size: int = 100
    report_interval: int = 60


@dataclass
class AppSettings:
    telegram: TelegramSettings
    rabbitmq: RabbitMQSettings
    postgres: PostgresSettings
    redis: RedisSettings
    monitoring: MonitoringSettings = field(default_factory=MonitoringSettings)
    producer: ProducerSettings = field(default_factory=ProducerSettings)
    worker: WorkerSettings = field(default_factory=WorkerSettings)


def load_settings() -> AppSettings:
    """
    Load configuration from environment variables and optional YAML files.
    """
    _maybe_load_dotenv()
    telegram = TelegramSettings(
        api_id=int(os.getenv("API_ID", os.getenv("TELEGRAM_API_ID", "0"))),
        api_hash=os.getenv("API_HASH", os.getenv("TELEGRAM_API_HASH", "")),
        session=os.getenv("STRING_SESSION", os.getenv("TELEGRAM_SESSION", "")),
        channels=_load_channels(),
        message_limit=int(os.getenv("TELEGRAM_MESSAGE_LIMIT", "200")),
        delay_between_channels=float(os.getenv("TELEGRAM_DELAY_BETWEEN_CHANNELS", "2.0")),
        delay_between_messages=float(os.getenv("TELEGRAM_DELAY_BETWEEN_MESSAGES", "0.1")),
        fetch_retries=int(os.getenv("TELEGRAM_FETCH_RETRIES", "3")),
    )
    rabbitmq = RabbitMQSettings(
        host=os.getenv("RABBITMQ_HOST", "rabbitmq"),
        user=os.getenv("RABBITMQ_USER", "guest"),
        password=os.getenv("RABBITMQ_PASS", os.getenv("RABBITMQ_PASSWORD", "guest")),
        vhost=os.getenv("RABBITMQ_VHOST", "/"),
        queue=os.getenv("RABBITMQ_QUEUE", "tg.messages.v2"),
        port=int(os.getenv("RABBITMQ_PORT", "5672")),
        heartbeat=int(os.getenv("RABBITMQ_HEARTBEAT", "60")),
        prefetch=int(os.getenv("RABBITMQ_PREFETCH", "50")),
        durable=os.getenv("RABBITMQ_QUEUE_DURABLE", "true").lower() != "false",
    )
    postgres = PostgresSettings(
        host=os.getenv("PGHOST", os.getenv("POSTGRES_HOST", "postgres")),
        port=int(os.getenv("PGPORT", os.getenv("POSTGRES_PORT", "5432"))),
        user=os.getenv("PGUSER", os.getenv("POSTGRES_USER", "postgres")),
        password=os.getenv("PGPASSWORD", os.getenv("POSTGRES_PASSWORD", "")),
        database=os.getenv("PGDATABASE", os.getenv("POSTGRES_DB", "postgres")),
        min_pool_size=int(os.getenv("POSTGRES_MIN_POOL", "1")),
        max_pool_size=int(os.getenv("POSTGRES_MAX_POOL", "10")),
    )
    redis = RedisSettings(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD"),
        ttl_seconds=int(os.getenv("REDIS_TTL_SECONDS", "86400")),
    )
    monitoring = MonitoringSettings(
        stats_interval=int(os.getenv("MONITORING_STATS_INTERVAL", "60")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
    producer = ProducerSettings(
        enable_airflow_mode=os.getenv("PRODUCER_AIRFLOW_MODE", "false").lower() == "true",
    )
    worker = WorkerSettings(
        batch_size=int(os.getenv("WORKER_BATCH_SIZE", "100")),
        report_interval=int(os.getenv("WORKER_REPORT_INTERVAL", "60")),
    )
    return AppSettings(
        telegram=telegram,
        rabbitmq=rabbitmq,
        postgres=postgres,
        redis=redis,
        monitoring=monitoring,
        producer=producer,
        worker=worker,
    )


__all__ = [
    "AppSettings",
    "load_settings",
]
