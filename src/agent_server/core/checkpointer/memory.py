"""In-memory adapter for testing and local development."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from .base import CheckpointerAdapter


class MemoryCheckpointerAdapter(CheckpointerAdapter):
    """Adapter for in-memory checkpointer and store."""

    name = "memory"

    def __init__(self, dsn: str | None = None, options: dict[str, Any] | None = None) -> None:
        super().__init__(dsn, options)
        self._dsn = None
        self._checkpointer: MemorySaver | None = None
        self._store: InMemoryStore | None = None

    async def get_checkpointer(self) -> MemorySaver:
        if self._checkpointer is None:
            self._checkpointer = MemorySaver()
        return self._checkpointer

    async def get_store(self) -> InMemoryStore:
        if self._store is None:
            self._store = InMemoryStore()
        return self._store

    async def close(self) -> None:
        self._checkpointer = None
        self._store = None
