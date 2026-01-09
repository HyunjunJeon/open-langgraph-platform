"""PostgreSQL adapter for LangGraph checkpointer and store."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore

from .base import CheckpointerAdapter


class PostgresCheckpointerAdapter(CheckpointerAdapter):
    """Adapter for AsyncPostgresSaver/AsyncPostgresStore."""

    name = "postgres"

    def __init__(self, dsn: str | None, options: dict[str, Any] | None = None) -> None:
        super().__init__(dsn, options)
        # normalize_dsn verifies dsn is not None and returns str
        self._dsn: str = self._normalize_dsn(self._dsn)
        self._checkpointer: AsyncPostgresSaver | None = None
        self._checkpointer_cm = None
        self._store: AsyncPostgresStore | None = None
        self._store_cm = None

        self._setup_on_init = self._options.get("setup_on_init", True)
        self._checkpointer_options = self._read_options("checkpointer")
        self._store_options = self._read_options("store")

    async def get_checkpointer(self) -> AsyncPostgresSaver:
        if self._checkpointer is None:
            self._checkpointer_cm = AsyncPostgresSaver.from_conn_string(self._dsn, **self._checkpointer_options)
            self._checkpointer = await self._checkpointer_cm.__aenter__()
            if self._setup_on_init:
                await self._checkpointer.setup()
        return self._checkpointer

    async def get_store(self) -> AsyncPostgresStore:
        if self._store is None:
            self._store_cm = AsyncPostgresStore.from_conn_string(self._dsn, **self._store_options)
            self._store = await self._store_cm.__aenter__()
            if self._setup_on_init:
                await self._store.setup()
        return self._store

    async def close(self) -> None:
        if self._checkpointer_cm is not None:
            await self._checkpointer_cm.__aexit__(None, None, None)
            self._checkpointer_cm = None
            self._checkpointer = None

        if self._store_cm is not None:
            await self._store_cm.__aexit__(None, None, None)
            self._store_cm = None
            self._store = None

    def _read_options(self, key: str) -> dict[str, Any]:
        value = self._options.get(key, {})
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError(f"Postgres checkpointer option '{key}' must be a JSON object.")
        return value

    @staticmethod
    def _normalize_dsn(dsn: str | None) -> str:
        if not dsn:
            raise ValueError("Postgres checkpointer requires a DSN.")

        if dsn.startswith("postgresql+asyncpg://"):
            dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
        elif dsn.startswith("postgres://"):
            dsn = dsn.replace("postgres://", "postgresql://", 1)

        if not dsn.startswith("postgresql://"):
            raise ValueError("Postgres checkpointer DSN must start with postgresql://")
        return dsn
