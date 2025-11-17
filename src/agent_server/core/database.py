"""LangGraph Integrated Database Manager

This module manages the database connection and LangGraph persistence components for Open LangGraph.
It manages Agent Protocol metadata tables via SQLAlchemy,
and stores conversation state using LangGraph's official AsyncPostgresSaver and AsyncPostgresStore.
"""

import os
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


class DatabaseManager:
    """Manages database connections and LangGraph persistence components.

    This class manages the following two database systems:
    1. SQLAlchemy AsyncEngine: For Agent Protocol metadata tables (Assistant, Thread, Run).
    2. LangGraph Components: For storing conversation state and checkpoints.
       - AsyncPostgresSaver: Stores checkpoints (state snapshots).
       - AsyncPostgresStore: Long-term memory and key-value store.

    Key Features:
    - Automatic URL format conversion: asyncpg -> psycopg (LangGraph requirement).
    - Singleton pattern: A single instance is used throughout the application.
    - Lazy initialization: Components are created only when needed.
    - Context manager: Automatic resource cleanup.
    """

    def __init__(self) -> None:
        self.engine: AsyncEngine | None = None
        self._checkpointer: AsyncPostgresSaver | None = None
        self._checkpointer_cm: Any = None  # holds the contextmanager so we can close it
        self._store: AsyncPostgresStore | None = None
        self._store_cm: Any = None
        self._database_url = os.getenv(
            "DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/open_langgraph"
        )

    async def initialize(self) -> None:
        """Initialize database connection and LangGraph components.

        This method is called from the lifespan event on FastAPI app startup.
        It creates the SQLAlchemy engine and prepares the LangGraph DSN.
        The actual LangGraph components are lazily created in get_checkpointer/get_store.

        Note: The database schema is managed by Alembic migrations.
              Initial setup requires running 'python3 scripts/migrate.py upgrade'.
        """
        # SQLAlchemy: For Agent Protocol metadata tables (only minimal tables are used)
        self.engine = create_async_engine(
            self._database_url,
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
        )

        # Convert asyncpg URL to psycopg format (LangGraph requirement)
        # The LangGraph package uses the psycopg driver, so URL format conversion is necessary
        # e.g., postgresql+asyncpg://user:pass@host/db → postgresql://user:pass@host/db
        dsn = self._database_url.replace("postgresql+asyncpg://", "postgresql://")

        # Store the connection string to create LangGraph components when needed
        self._langgraph_dsn = dsn
        self.checkpointer = None
        self.store = None
        # Note: LangGraph components are created as needed using a context manager

        # Note: The database schema is now managed by Alembic migrations
        # Apply migrations: 'alembic upgrade head' or 'python3 scripts/migrate.py upgrade'

        print("✅ Database and LangGraph components initialized")

    async def close(self) -> None:
        """Close database connections.

        Called from the lifespan event on FastAPI app shutdown.
        Cleans up all active connections and releases resources.
        """
        if self.engine:
            await self.engine.dispose()

        # If there is a cached checkpointer, close it
        if self._checkpointer_cm is not None:
            await self._checkpointer_cm.__aexit__(None, None, None)
            self._checkpointer_cm = None
            self._checkpointer = None

        if self._store_cm is not None:
            await self._store_cm.__aexit__(None, None, None)
            self._store_cm = None
            self._store = None

        print("✅ Database connections closed")

    async def get_checkpointer(self) -> AsyncPostgresSaver:
        """Return the LangGraph checkpointer (state store).

        This method returns an active instance of AsyncPostgresSaver.

        How it works:
        1. On first call: Enters the async context manager and caches the saver object.
        2. On subsequent calls: Reuses the cached saver (shares the DB connection pool).

        Why caching is needed:
        - LangGraph needs the actual saver object (to call methods like get_next_version).
        - Returning a context manager wrapper would fail.
        - Reusing the connection pool improves performance.

        Returns:
            AsyncPostgresSaver: An instance of the LangGraph checkpointer.

        Raises:
            RuntimeError: If the database is not initialized.
        """
        if not hasattr(self, "_langgraph_dsn"):
            raise RuntimeError("Database not initialized")
        if self._checkpointer is None:
            self._checkpointer_cm = AsyncPostgresSaver.from_conn_string(self._langgraph_dsn)
            self._checkpointer = await self._checkpointer_cm.__aenter__()
            # Create necessary tables (idempotent: safe to call multiple times)
            await self._checkpointer.setup()
        return self._checkpointer

    async def get_store(self) -> AsyncPostgresStore:
        """Return the LangGraph Store instance (vector search + key-value store).

        AsyncPostgresStore provides the following features:
        - Key-value store: For long-term memory, user preferences, etc.
        - Vector search: Embedding-based similarity search (to be supported in the future).

        It uses the same caching pattern as the checkpointer.

        Returns:
            AsyncPostgresStore: An instance of the LangGraph Store.

        Raises:
            RuntimeError: If the database is not initialized.
        """
        if not hasattr(self, "_langgraph_dsn"):
            raise RuntimeError("Database not initialized")
        if self._store is None:
            self._store_cm = AsyncPostgresStore.from_conn_string(self._langgraph_dsn)
            self._store = await self._store_cm.__aenter__()
            # Create schema (idempotent)
            await self._store.setup()
        return self._store

    def get_engine(self) -> AsyncEngine:
        """Return the SQLAlchemy engine for metadata tables.

        This engine is used only for Agent Protocol metadata tables (Assistant, Thread, Run, etc.).
        LangGraph state storage uses a separate checkpointer/store.

        Returns:
            AsyncEngine: The SQLAlchemy async engine.

        Raises:
            RuntimeError: If the database is not initialized.
        """
        if not self.engine:
            raise RuntimeError("Database not initialized")
        return self.engine


# Global database manager instance (singleton pattern)
# This instance is used throughout the application to access the DB
db_manager = DatabaseManager()
