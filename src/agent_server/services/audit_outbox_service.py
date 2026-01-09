"""Audit Outbox Service for reliable audit log capture

This module implements the Outbox pattern for audit logging. Audit entries are
first written synchronously to an outbox table, then moved asynchronously to
the partitioned audit_logs table by a background batch mover.

Architecture:
- insert(): Synchronous INSERT with 1s timeout for crash-safe capture
- start_mover(): Start background batch mover task
- stop_mover(): Graceful shutdown with flush
- _batch_mover(): Move records from outbox to partitioned table

Key Features:
- Outbox pattern for crash-safe logging (no data loss on process crash)
- Batch processing for performance (500 records per batch)
- SELECT FOR UPDATE SKIP LOCKED for concurrency safety
- Metrics tracking for observability

Usage:
    from src.agent_server.services.audit_outbox_service import audit_outbox_service

    # Insert audit entry
    await audit_outbox_service.insert(audit_payload)

    # Lifecycle management (in main.py lifespan)
    await audit_outbox_service.start_mover()
    await audit_outbox_service.stop_mover()
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, text

from ..core.database import db_manager
from ..core.orm import AuditLog, AuditLogOutbox
from ..core.rls import set_rls_bypass
from .partition_service import partition_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BATCH_SIZE: int = 500
MOVE_INTERVAL_SECONDS: float = 10.0
INSERT_TIMEOUT_SECONDS: float = 1.0
FLUSH_TIMEOUT_SECONDS: float = 5.0  # Timeout for shutdown flush
MAX_RETRY_COUNT: int = 3  # Max retries for poison-pill records
MAX_RETRY_CACHE_SIZE: int = 1000  # Bound retry cache to prevent memory leak


# ---------------------------------------------------------------------------
# Metrics (Simple in-memory counters)
# ---------------------------------------------------------------------------


class AuditMetrics:
    """Simple in-memory metrics for audit operations.

    In production, these would integrate with Prometheus or similar.
    """

    def __init__(self) -> None:
        self.inserted: int = 0
        self.moved: int = 0
        self.dropped: int = 0
        self.mover_errors: int = 0
        self.poison_pills: int = 0  # Records that exceeded retry limit

    def reset(self) -> None:
        """Reset all counters."""
        self.inserted = 0
        self.moved = 0
        self.dropped = 0
        self.mover_errors = 0
        self.poison_pills = 0

    def to_dict(self) -> dict[str, int]:
        """Return metrics as dictionary."""
        return {
            "audit.inserted": self.inserted,
            "audit.moved": self.moved,
            "audit.dropped": self.dropped,
            "audit.mover_errors": self.mover_errors,
            "audit.poison_pills": self.poison_pills,
        }


# ---------------------------------------------------------------------------
# LRU Retry Cache (Memory-bounded tracking)
# ---------------------------------------------------------------------------


class LRURetryCache:
    """LRU cache for tracking retry counts with automatic eviction.

    This class replaces the plain dict used for retry tracking, providing:
    - Memory-bounded storage with LRU eviction
    - O(1) operations for get/increment/clear
    - No unbounded memory growth

    Thread Safety:
    - The underlying OrderedDict is not thread-safe, but this is used
      only within the single-threaded asyncio event loop.

    Attributes:
        max_size: Maximum number of entries to track
    """

    def __init__(self, max_size: int = 1000) -> None:
        from collections import OrderedDict

        self._cache: OrderedDict[str, int] = OrderedDict()
        self._max_size = max_size

    def increment(self, key: str) -> int:
        """Increment retry count for key, with LRU eviction.

        Args:
            key: The record ID to track

        Returns:
            int: Current retry count after increment
        """
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] += 1
        else:
            self._cache[key] = 1
            # Evict oldest if over capacity
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

        return self._cache[key]

    def get(self, key: str) -> int:
        """Get retry count without modifying LRU order.

        Args:
            key: The record ID to look up

        Returns:
            int: Current retry count (0 if not tracked)
        """
        return self._cache.get(key, 0)

    def clear(self, key: str) -> None:
        """Remove key from cache.

        Args:
            key: The record ID to remove
        """
        self._cache.pop(key, None)

    def reset(self) -> None:
        """Clear entire cache."""
        self._cache.clear()

    def __len__(self) -> int:
        """Return number of tracked entries."""
        return len(self._cache)


# ---------------------------------------------------------------------------
# Service Class
# ---------------------------------------------------------------------------


class AuditOutboxService:
    """Audit log outbox service with background batch mover.

    This service implements the transactional outbox pattern for audit logging.
    Audit entries are first written to an outbox table, then moved to the
    partitioned audit_logs table by a background task.

    Thread Safety:
    - insert() is safe to call from any coroutine
    - The batch mover uses SELECT FOR UPDATE SKIP LOCKED for concurrency

    Lifecycle:
    - Call start_mover() during application startup
    - Call stop_mover() during application shutdown

    Attributes:
        metrics (AuditMetrics): In-memory metrics counters
    """

    def __init__(self) -> None:
        """Initialize the audit outbox service."""
        self._mover_task: asyncio.Task | None = None
        self._running: bool = False
        self.metrics: AuditMetrics = AuditMetrics()
        # LRU cache for poison-pill retry tracking (replaces unbounded dict)
        self._retry_cache = LRURetryCache(max_size=MAX_RETRY_CACHE_SIZE)

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    async def insert(self, payload: dict[str, Any]) -> str | None:
        """Insert an audit entry into the outbox table.

        This method performs a synchronous INSERT with a 1 second timeout.
        If the insert times out or fails, the entry is dropped and logged.

        Args:
            payload: The audit entry data (will be stored as JSONB)

        Returns:
            str | None: The generated ID if successful, None if dropped

        Note:
            This method should never raise exceptions to avoid disrupting
            the main request flow. Errors are logged and metrics updated.
        """
        try:
            # Generate ID for the outbox entry
            entry_id = str(uuid.uuid4())

            engine = db_manager.get_engine()

            async def _do_insert() -> None:
                async with engine.begin() as conn:
                    stmt = insert(AuditLogOutbox).values(
                        id=entry_id,
                        payload=payload,
                        processed=False,
                    )
                    await conn.execute(stmt)

            # Execute with timeout
            await asyncio.wait_for(
                _do_insert(),
                timeout=INSERT_TIMEOUT_SECONDS,
            )

            self.metrics.inserted += 1
            logger.debug("Audit entry inserted: %s", entry_id)
            return entry_id

        except TimeoutError:
            self.metrics.dropped += 1
            logger.warning("Audit insert timed out after %ss", INSERT_TIMEOUT_SECONDS)
            return None

        except Exception as e:
            self.metrics.dropped += 1
            logger.exception("Audit insert failed: %s", e)
            return None

    async def start_mover(self) -> None:
        """Start the background batch mover task.

        This method starts a background asyncio task that periodically moves
        records from the outbox table to the partitioned audit_logs table.

        If the mover is already running, this method does nothing.

        Note:
            Call this method during application startup (in lifespan).
        """
        if self._mover_task is None or self._mover_task.done():
            self._running = True
            self._mover_task = asyncio.create_task(self._mover_loop())
            logger.info(
                "Audit mover started (batch_size=%d, interval=%ss)",
                BATCH_SIZE,
                MOVE_INTERVAL_SECONDS,
            )

    async def stop_mover(self) -> None:
        """Stop the background batch mover task.

        This method gracefully stops the mover task, flushing any remaining
        records before returning. Uses FLUSH_TIMEOUT_SECONDS to prevent
        indefinite hanging during shutdown.

        Note:
            Call this method during application shutdown (in lifespan).
        """
        self._running = False

        if self._mover_task is not None and not self._mover_task.done():
            # Cancel the task and wait for it
            self._mover_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._mover_task

            # Flush remaining records with timeout
            try:
                await asyncio.wait_for(
                    self._move_batch(),
                    timeout=FLUSH_TIMEOUT_SECONDS,
                )
                logger.info("Audit mover flushed remaining records")
            except TimeoutError:
                logger.warning(
                    "Audit flush timed out after %ss, some records may remain",
                    FLUSH_TIMEOUT_SECONDS,
                )
            except Exception as e:
                logger.exception("Failed to flush audit records on shutdown: %s", e)

            logger.info("Audit mover stopped")

    def get_metrics(self) -> dict[str, int]:
        """Get current metrics as a dictionary.

        Returns:
            dict[str, int]: Current metric values
        """
        return self.metrics.to_dict()

    # ---------------------------------------------------------------------------
    # Internal Methods
    # ---------------------------------------------------------------------------

    async def _mover_loop(self) -> None:
        """Background loop that drains all batches from outbox to audit_logs.

        This loop runs continuously, draining ALL available batches before
        sleeping. The "drain until empty" pattern ensures efficient processing
        of backlogs rather than processing one batch at a time with sleep
        intervals. Exception handling ensures the loop continues even if batch
        moves fail.
        """
        while self._running:
            try:
                # Drain all available batches before sleeping
                if self._running:
                    while True:
                        moved = await self._move_batch()
                        if moved == 0:
                            break
                        if not self._running:
                            break
                await asyncio.sleep(MOVE_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                logger.debug("Audit mover loop cancelled")
                break
            except Exception as e:
                self.metrics.mover_errors += 1
                logger.exception("Error in audit mover loop: %s", e)
                # Still sleep on error to prevent tight loop
                await asyncio.sleep(MOVE_INTERVAL_SECONDS)

    def _parse_timestamp(self, value: Any) -> datetime:
        """Parse timestamp from various formats with robust error handling.

        Handles:
        - datetime objects (returned as-is, with UTC if no tzinfo)
        - ISO format strings (with or without Z suffix)
        - None (returns current UTC time)
        - Invalid formats (logs warning, returns current UTC time)

        Args:
            value: The timestamp value to parse

        Returns:
            datetime: Parsed datetime with timezone info
        """
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)

        if isinstance(value, str):
            try:
                # Handle Z suffix (ISO 8601)
                if value.endswith("Z"):
                    value = value[:-1] + "+00:00"
                return datetime.fromisoformat(value)
            except ValueError as e:
                logger.warning("Invalid timestamp format '%s': %s", value[:50], e)
                return datetime.now(UTC)

        return datetime.now(UTC)

    def _increment_retry_count(self, record_id: str) -> int:
        """Increment and return retry count using LRU cache.

        The LRU cache automatically evicts oldest entries when capacity
        is exceeded, preventing unbounded memory growth.

        Args:
            record_id: The outbox record ID

        Returns:
            int: Current retry count after increment
        """
        return self._retry_cache.increment(record_id)

    def _clear_retry_count(self, record_id: str) -> None:
        """Clear retry count for a successfully processed record."""
        self._retry_cache.clear(record_id)

    def _is_partition_error(self, error: Exception) -> bool:
        """Check if an exception is a partition-related error.

        PostgreSQL raises specific errors when trying to insert into a
        partitioned table without a matching partition:
        - "no partition of relation "audit_logs" found for row"
        - "new row violates partition constraint"

        Args:
            error: The exception to check

        Returns:
            bool: True if this is a partition-related error
        """
        error_str = str(error).lower()
        return (
            "no partition" in error_str or "partition constraint" in error_str or "partition of relation" in error_str
        )

    async def _move_batch(self) -> int:
        """Move a batch of records from outbox to audit_logs.

        This method uses savepoints to isolate per-row failures, ensuring that
        a single bad record doesn't abort the entire batch. Records that fail
        repeatedly are marked as poison-pills and skipped.

        Flow:
        1. Selects unprocessed records with FOR UPDATE SKIP LOCKED
        2. For each record, uses a savepoint to isolate the insert
        3. On success: mark for deletion
        4. On failure: rollback savepoint, increment retry count
        5. Delete only successfully processed records

        Returns:
            int: Number of records successfully moved
        """
        engine = db_manager.get_engine()
        moved_count = 0
        success_ids: list[str] = []
        poison_ids: list[str] = []

        try:
            async with engine.begin() as conn:
                await set_rls_bypass(conn)
                # Select unprocessed records with lock
                select_stmt = text("""
                    SELECT id, payload, created_at
                    FROM audit_logs_outbox
                    WHERE processed = false
                    ORDER BY created_at ASC
                    LIMIT :batch_size
                    FOR UPDATE SKIP LOCKED
                """)

                result = await conn.execute(select_stmt, {"batch_size": BATCH_SIZE})
                rows = result.fetchall()

                if not rows:
                    return 0

                # Process each row with savepoint isolation
                for row in rows:
                    outbox_id = row.id
                    payload = row.payload

                    # Check if this is a poison-pill (exceeded retry limit)
                    retry_count = self._retry_cache.get(outbox_id)
                    if retry_count >= MAX_RETRY_COUNT:
                        logger.error(
                            "Poison-pill detected: record %s failed %d times, marking as processed",
                            outbox_id,
                            retry_count,
                        )
                        poison_ids.append(outbox_id)
                        self.metrics.poison_pills += 1
                        self._clear_retry_count(outbox_id)
                        continue

                    # Use savepoint for per-row isolation
                    savepoint = await conn.begin_nested()
                    try:
                        # Extract and validate fields from payload
                        audit_id = payload.get("id") or str(uuid.uuid4())
                        timestamp = self._parse_timestamp(payload.get("timestamp"))

                        # Insert into partitioned audit_logs table
                        insert_stmt = insert(AuditLog).values(
                            id=audit_id,
                            timestamp=timestamp,
                            user_id=payload.get("user_id", "unknown"),
                            org_id=payload.get("org_id"),
                            action=payload.get("action", "UNKNOWN"),
                            resource_type=payload.get("resource_type", "unknown"),
                            resource_id=payload.get("resource_id"),
                            http_method=payload.get("http_method", "UNKNOWN"),
                            path=payload.get("path", "/"),
                            ip_address=payload.get("ip_address"),
                            user_agent=payload.get("user_agent"),
                            request_body=payload.get("request_body"),
                            response_summary=payload.get("response_summary"),
                            status_code=payload.get("status_code", 0),
                            duration_ms=payload.get("duration_ms", 0),
                            error_message=payload.get("error_message"),
                            error_class=payload.get("error_class"),
                            is_streaming=payload.get("is_streaming", False),
                            metadata_dict=payload.get("metadata", {}),
                        )
                        await conn.execute(insert_stmt)
                        await savepoint.commit()

                        # Success - mark for deletion and clear retry count
                        success_ids.append(outbox_id)
                        self._clear_retry_count(outbox_id)
                        moved_count += 1

                    except Exception as e:
                        # Rollback savepoint
                        await savepoint.rollback()

                        # Check if this is a partition error - if so, create partition and retry
                        if self._is_partition_error(e):
                            try:
                                # Create partition for the record's timestamp
                                await partition_service.create_partition_for_date(timestamp)
                                logger.info(
                                    "Created missing partition for record %s, retrying insert",
                                    outbox_id,
                                )

                                # Retry the insert with a new savepoint
                                retry_savepoint = await conn.begin_nested()
                                try:
                                    retry_stmt = insert(AuditLog).values(
                                        id=audit_id,
                                        timestamp=timestamp,
                                        user_id=payload.get("user_id", "unknown"),
                                        org_id=payload.get("org_id"),
                                        action=payload.get("action", "UNKNOWN"),
                                        resource_type=payload.get("resource_type", "unknown"),
                                        resource_id=payload.get("resource_id"),
                                        http_method=payload.get("http_method", "UNKNOWN"),
                                        path=payload.get("path", "/"),
                                        ip_address=payload.get("ip_address"),
                                        user_agent=payload.get("user_agent"),
                                        request_body=payload.get("request_body"),
                                        response_summary=payload.get("response_summary"),
                                        status_code=payload.get("status_code", 0),
                                        duration_ms=payload.get("duration_ms", 0),
                                        error_message=payload.get("error_message"),
                                        error_class=payload.get("error_class"),
                                        is_streaming=payload.get("is_streaming", False),
                                        metadata_dict=payload.get("metadata", {}),
                                    )
                                    await conn.execute(retry_stmt)
                                    await retry_savepoint.commit()

                                    # Success after partition creation
                                    success_ids.append(outbox_id)
                                    self._clear_retry_count(outbox_id)
                                    moved_count += 1
                                    logger.debug(
                                        "Successfully moved record %s after partition creation",
                                        outbox_id,
                                    )
                                    continue  # Skip the normal error handling below

                                except Exception as retry_error:
                                    await retry_savepoint.rollback()
                                    logger.error(
                                        "Retry after partition creation failed for %s: %s",
                                        outbox_id,
                                        retry_error,
                                    )
                                    # Fall through to normal error handling

                            except Exception as partition_error:
                                logger.error(
                                    "Failed to create partition for record %s: %s",
                                    outbox_id,
                                    partition_error,
                                )
                                # Fall through to normal error handling

                        # Normal error handling - track retry count
                        retry = self._increment_retry_count(outbox_id)
                        logger.warning(
                            "Failed to move audit record %s (attempt %d/%d): %s",
                            outbox_id,
                            retry,
                            MAX_RETRY_COUNT,
                            e,
                        )

                # Delete successfully processed records
                if success_ids:
                    delete_stmt = delete(AuditLogOutbox).where(AuditLogOutbox.id.in_(success_ids))
                    await conn.execute(delete_stmt)

                # Mark poison-pill records as processed (so they're not retried forever)
                if poison_ids:
                    mark_processed_stmt = text("""
                        UPDATE audit_logs_outbox
                        SET processed = true
                        WHERE id = ANY(:ids)
                    """)
                    await conn.execute(mark_processed_stmt, {"ids": poison_ids})

                self.metrics.moved += moved_count

                if moved_count > 0:
                    logger.debug("Moved %d audit records", moved_count)

        except Exception as e:
            self.metrics.mover_errors += 1
            logger.exception("Batch move failed: %s", e)

        return moved_count


# ---------------------------------------------------------------------------
# Singleton Instance
# ---------------------------------------------------------------------------

audit_outbox_service = AuditOutboxService()
