import logging
from typing import Optional

import redis

from code.config.settings import RedisSettings

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(self, settings: RedisSettings):
        self.settings = settings
        self._client = redis.Redis(
            host=settings.host,
            port=settings.port,
            db=settings.db,
            password=settings.password,
            decode_responses=True,
        )

    @property
    def raw(self) -> redis.Redis:
        return self._client

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except redis.RedisError as exc:
            logger.error("Redis ping failed: %s", exc)
            return False

    def mark_once(self, key: str, ttl: Optional[int] = None) -> bool:
        ttl = ttl or self.settings.ttl_seconds
        try:
            return bool(self._client.set(name=key, value="1", ex=ttl, nx=True))
        except redis.RedisError as exc:
            logger.warning("Redis set failed (%s). Allowing message to proceed.", exc)
            return True
