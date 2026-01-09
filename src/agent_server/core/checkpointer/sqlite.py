"""SQLite adapter for LangGraph checkpointer and store."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import CheckpointerAdapter

try:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from langgraph.store.sqlite.aio import AsyncSqliteStore

    SQLITE_AVAILABLE = True
except ImportError:
    SQLITE_AVAILABLE = False
    AsyncSqliteSaver = None  # type: ignore
    AsyncSqliteStore = None  # type: ignore


class SqliteCheckpointerAdapter(CheckpointerAdapter):
    """Adapter for AsyncSqliteSaver/AsyncSqliteStore."""

    name = "sqlite"

    def __init__(self, dsn: str | None, options: dict[str, Any] | None = None) -> None:
        super().__init__(dsn, options)
        self._dsn: str = self._normalize_dsn(self._dsn)
        self._checkpointer: Any = None
        self._checkpointer_cm = None
        self._store: Any = None
        self._store_cm = None

        self._setup_on_init = self._options.get("setup_on_init", False)
        self._checkpointer_options = self._read_options("checkpointer")
        self._store_options = self._read_options("store")

    async def initialize(self) -> None:
        if not SQLITE_AVAILABLE:
            raise RuntimeError("SQLite support not installed. Run: uv pip install langgraph-checkpoint-sqlite")

        if self._dsn != ":memory:":
            Path(self._dsn).parent.mkdir(parents=True, exist_ok=True)

    async def get_checkpointer(self) -> Any:
        if not SQLITE_AVAILABLE:
            raise RuntimeError("SQLite support not installed. Run: uv pip install langgraph-checkpoint-sqlite")
        if self._checkpointer is None:
            self._checkpointer_cm = AsyncSqliteSaver.from_conn_string(self._dsn, **self._checkpointer_options)
            self._checkpointer = await self._checkpointer_cm.__aenter__()
            if self._setup_on_init:
                await self._checkpointer.setup()
        return self._checkpointer

    async def get_store(self) -> Any:
        if not SQLITE_AVAILABLE:
            raise RuntimeError("SQLite support not installed. Run: uv pip install langgraph-checkpoint-sqlite")
        if self._store is None:
            self._store_cm = AsyncSqliteStore.from_conn_string(self._dsn, **self._store_options)
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
            raise ValueError(f"SQLite checkpointer option '{key}' must be a JSON object.")
        return value

    @staticmethod
    def _normalize_dsn(dsn: str | None) -> str:
        if not dsn:
            raise ValueError("SQLite checkpointer requires a DSN or file path.")

        if "://" in dsn and not dsn.startswith("sqlite"):
            raise ValueError("SQLite checkpointer DSN must start with sqlite:// or be a file path.")

        if dsn.startswith("sqlite+aiosqlite:///"):
            dsn = dsn.replace("sqlite+aiosqlite:///", "", 1)
        elif dsn.startswith("sqlite:///"):
            dsn = dsn.replace("sqlite:///", "", 1)
        elif dsn.startswith("sqlite://"):
            dsn = dsn.replace("sqlite://", "", 1)

        return dsn or ":memory:"
