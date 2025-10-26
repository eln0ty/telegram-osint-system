from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator, Optional

import psycopg2
from psycopg2.pool import ThreadedConnectionPool

from code.config.settings import PostgresSettings

logger = logging.getLogger(__name__)


class DatabasePool:
    """
    Thin wrapper around ThreadedConnectionPool with context helpers.
    """

    def __init__(self, settings: PostgresSettings):
        self._settings = settings
        self._pool: Optional[ThreadedConnectionPool] = None

    def initialize(self) -> None:
        if self._pool:
            return
        logger.info(
            "Creating PostgreSQL connection pool (host=%s db=%s min=%s max=%s)",
            self._settings.host,
            self._settings.database,
            self._settings.min_pool_size,
            self._settings.max_pool_size,
        )
        self._pool = ThreadedConnectionPool(
            minconn=self._settings.min_pool_size,
            maxconn=self._settings.max_pool_size,
            host=self._settings.host,
            port=self._settings.port,
            user=self._settings.user,
            password=self._settings.password,
            dbname=self._settings.database,
        )

    @contextmanager
    def connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        if not self._pool:
            self.initialize()
        assert self._pool  # for mypy
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    @contextmanager
    def cursor(self) -> Generator[psycopg2.extensions.cursor, None, None]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                yield cur
                conn.commit()

    def closeall(self) -> None:
        if self._pool:
            logger.info("Closing PostgreSQL pool connections")
            self._pool.closeall()


def create_pool(settings: PostgresSettings) -> DatabasePool:
    pool = DatabasePool(settings)
    pool.initialize()
    return pool
