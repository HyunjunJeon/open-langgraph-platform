"""Thread State Conversion Service

This module converts LangGraph checkpointer snapshots into the Agent Protocol's ThreadState format.
It supports thread state retrieval by providing a client-friendly format for LangGraph's state snapshots.

Main components:
• ThreadStateService - Snapshot → ThreadState conversion service
• LangGraphSerializer - Task and interrupt serialization

Usage example:
    from services.thread_state_service import ThreadStateService

    service = ThreadStateService()
    thread_state = service.convert_snapshot_to_thread_state(snapshot, thread_id)
"""

import logging
from datetime import datetime
from typing import Any

from ..core.serializers import LangGraphSerializer
from ..models.threads import ThreadCheckpoint, ThreadState

logger = logging.getLogger(__name__)


class ThreadStateService:
    """Service to convert LangGraph snapshots to ThreadState objects

    This class transforms a LangGraph checkpointer snapshot into the Agent Protocol's ThreadState.
    The snapshot contains the graph execution state, the next node to execute, tasks, interrupts, etc.

    Key features:
    - Converts single/multiple snapshots to ThreadState
    - Extracts and transforms checkpoint metadata
    - Serializes tasks and interrupts
    - Parses and normalizes timestamps

    Usage pattern:
    - Can be used as a singleton instance
    - Combines with LangGraphSerializer for state conversion
    """

    def __init__(self) -> None:
        # LangGraph-specific serializer (for converting tasks, interrupts)
        self.serializer = LangGraphSerializer()

    def convert_snapshot_to_thread_state(self, snapshot: Any, thread_id: str) -> ThreadState:
        """Convert a LangGraph snapshot to ThreadState format

        This method transforms a LangGraph StateSnapshot into the Agent Protocol's ThreadState.
        It extracts state values, the next execution node, metadata, and checkpoint information from the snapshot
        to provide it in a format that clients can understand.

        Conversion process:
        1. Extract base values: values, next, metadata, created_at
        2. Tasks/Interrupts: Serialize with the serializer
        3. Create checkpoint objects: current, parent
        4. Backward compatibility: Extract checkpoint_id

        Args:
            snapshot (Any): LangGraph StateSnapshot object
            thread_id (str): Unique thread identifier

        Returns:
            ThreadState: The thread state in Agent Protocol format

        Raises:
            Exception: If an error occurs during snapshot conversion

        Note:
            - The snapshot is returned from LangGraph's checkpointer.aget_tuple(), etc.
            - ThreadState is used in the GET /threads/{thread_id}/state API
        """
        try:
            # Extract base values (graph state, next node, metadata, etc.)
            values = getattr(snapshot, "values", {})
            next_nodes = getattr(snapshot, "next", []) or []
            metadata = getattr(snapshot, "metadata", {}) or {}
            created_at = self._extract_created_at(snapshot)

            # Extract tasks and interrupts with the serializer (convert to client-friendly format)
            tasks = self.serializer.extract_tasks_from_snapshot(snapshot)
            interrupts = self.serializer.extract_interrupts_from_snapshot(snapshot)

            # Create checkpoint objects (current state and parent state)
            current_checkpoint = self._create_checkpoint(snapshot.config, thread_id)
            parent_checkpoint = (
                self._create_checkpoint(snapshot.parent_config, thread_id) if snapshot.parent_config else None
            )

            # Extract checkpoint ID for backward compatibility (string format)
            checkpoint_id = self._extract_checkpoint_id(snapshot.config)
            parent_checkpoint_id = (
                self._extract_checkpoint_id(snapshot.parent_config) if snapshot.parent_config else None
            )

            return ThreadState(
                values=values,
                next=next_nodes,
                tasks=tasks,
                interrupts=interrupts,
                metadata=metadata,
                created_at=created_at,
                checkpoint=current_checkpoint,
                parent_checkpoint=parent_checkpoint,
                checkpoint_id=checkpoint_id,
                parent_checkpoint_id=parent_checkpoint_id,
            )

        except Exception as e:
            logger.error(
                f"Failed to convert snapshot to thread state: {e} "
                f"(thread_id={thread_id}, snapshot_type={type(snapshot).__name__})"
            )
            raise

    def convert_snapshots_to_thread_states(self, snapshots: list[Any], thread_id: str) -> list[ThreadState]:
        """Convert multiple snapshots to a list of ThreadState objects

        This method transforms a checkpoint history (snapshots from multiple points in time) into a list of ThreadStates.
        It converts each snapshot individually and continues processing the rest even if some fail.

        Use cases:
        - GET /threads/{thread_id}/history - Retrieve the full execution history
        - Provide a list of checkpoints in reverse chronological order

        Args:
            snapshots (list[Any]): A list of LangGraph snapshots
            thread_id (str): Unique thread identifier

        Returns:
            list[ThreadState]: A list of converted ThreadState objects

        Note:
            - Individual snapshot conversion failures are logged and skipped
            - Partial failures during batch processing do not stop the entire process
            - Can return an empty list (if all conversions fail)
        """
        thread_states = []

        for i, snapshot in enumerate(snapshots):
            try:
                thread_state = self.convert_snapshot_to_thread_state(snapshot, thread_id)
                thread_states.append(thread_state)
            except Exception as e:
                logger.error(
                    f"Failed to convert snapshot in batch: {e} (thread_id={thread_id}, snapshot_index={i})"
                )
                # Continue processing without stopping the entire batch on individual snapshot failure
                continue

        return thread_states

    def _extract_created_at(self, snapshot: Any) -> datetime | None:
        """Extract and parse the creation timestamp from a snapshot

        This method converts the created_at field of a snapshot to a datetime object.
        It handles both string (ISO 8601) and datetime object formats.

        Args:
            snapshot (Any): LangGraph StateSnapshot object

        Returns:
            datetime | None: The parsed datetime object or None

        Note:
            - Supports ISO 8601 format: "2025-10-27T12:00:00Z"
            - Converts Z suffix to +00:00 (UTC)
            - Logs a warning and returns None on parsing failure
        """
        created_at = getattr(snapshot, "created_at", None)
        if isinstance(created_at, str):
            try:
                # Parse ISO 8601 format (convert Z → +00:00)
                return datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Invalid created_at format: {created_at}")
                return None
        elif isinstance(created_at, datetime):
            # Return as is if already a datetime object
            return created_at
        return None

    def _create_checkpoint(self, config: Any, thread_id: str) -> ThreadCheckpoint:
        """Create a ThreadCheckpoint object from a LangGraph config

        This method extracts checkpoint metadata from a LangGraph RunnableConfig
        to create an Agent Protocol ThreadCheckpoint object.

        Args:
            config (Any): LangGraph RunnableConfig dictionary
            thread_id (str): Unique thread identifier

        Returns:
            ThreadCheckpoint: The checkpoint metadata object

        Note:
            - config.configurable.checkpoint_id: Unique checkpoint ID
            - config.configurable.checkpoint_ns: Checkpoint namespace (for subgraphs)
            - Returns an empty checkpoint if config is not present
        """
        if not config or not isinstance(config, dict):
            # Return an empty checkpoint if config is not present
            return ThreadCheckpoint(checkpoint_id=None, thread_id=thread_id, checkpoint_ns="")

        # Extract checkpoint information from the configurable section
        configurable = config.get("configurable", {})
        checkpoint_id = configurable.get("checkpoint_id")
        checkpoint_ns = configurable.get("checkpoint_ns", "")

        return ThreadCheckpoint(
            checkpoint_id=checkpoint_id,
            thread_id=thread_id,
            checkpoint_ns=checkpoint_ns,
        )

    def _extract_checkpoint_id(self, config: Any) -> str | None:
        """Extract the checkpoint ID as a string from the config (for backward compatibility)

        This method returns the checkpoint ID as a string for compatibility with previous API versions.
        It supports legacy clients that use a simple string ID instead of a ThreadCheckpoint object.

        Args:
            config (Any): LangGraph RunnableConfig dictionary

        Returns:
            str | None: The checkpoint ID string or None

        Note:
            - New code is recommended to use _create_checkpoint() for the ThreadCheckpoint object
            - This method is for maintaining backward compatibility
        """
        if not config or not isinstance(config, dict):
            return None

        configurable = config.get("configurable", {})
        checkpoint_id = configurable.get("checkpoint_id")
        # Convert checkpoint ID to string (if it exists)
        return str(checkpoint_id) if checkpoint_id is not None else None
