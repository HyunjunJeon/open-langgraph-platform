"""SSE 재생 기능을 위한 PostgreSQL 기반 영속적 이벤트 저장소

이 모듈은 Server-Sent Events(SSE) 스트리밍 중 발생한 모든 이벤트를
PostgreSQL 데이터베이스에 저장하여 재생 기능을 제공합니다.
클라이언트가 연결이 끊겼다가 재연결하면 저장된 이벤트를 순차적으로 다시 받을 수 있습니다.

주요 구성 요소:
• EventStore - PostgreSQL 백엔드 이벤트 저장소 (싱글톤)
• store_sse_event() - SSE 이벤트 저장 헬퍼 함수
• event_store - 전역 EventStore 인스턴스

사용 예:
    from ...services.event_store import event_store, store_sse_event

    # 이벤트 저장
    await store_sse_event(run_id, event_id, "values", {"key": "value"})

    # 특정 시점 이후 이벤트 조회 (재연결 시)
    events = await event_store.get_events_since(run_id, last_event_id)

    # 정리 작업 시작/중지
    await event_store.start_cleanup_task()
    await event_store.stop_cleanup_task()
"""

import asyncio
import contextlib
import json
from datetime import UTC, datetime

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from ..core.database import db_manager
from ..core.serializers import GeneralSerializer
from ..core.sse import SSEEvent


class EventStore:
    """PostgreSQL-based SSE event store

    This class stores all SSE events that occur during a run in PostgreSQL,
    and provides functionality to replay events from a specific point in time upon reconnection.
    It also manages a background task to periodically clean up old events.

    Key features:
    - Event storage: Stores SSE events with sequence numbers using store_event()
    - Event replay: Retrieves events after a specific point using get_events_since()
    - Automatic cleanup: Automatically deletes events older than 1 hour every 300 seconds
    - Run information: Retrieves event count and last event for a run using get_run_info()

    Database schema:
    - Table: run_events
    - Key columns: id, run_id, seq, event, data (JSONB), created_at
    - Indexes: run_id, composite index on (run_id, seq)

    Cleanup policy:
    - Cleanup interval: 300 seconds (5 minutes)
    - Retention period: 1 hour
    - Background task: Runs as an asyncio.Task

    Usage pattern:
    - Singleton instance: event_store
    - Call start_cleanup_task() from lifespan to start the cleanup task
    """

    CLEANUP_INTERVAL = 300  # 초 단위 (5분)

    def __init__(self) -> None:
        self._cleanup_task: asyncio.Task | None = None

    async def start_cleanup_task(self) -> None:
        """Start the background cleanup task

        This method starts a background task that periodically deletes old events.
        It does not create a new task if one is already running.

        Behavior:
        - Creates a new task only if the cleanup task is not present or has finished
        - Runs _cleanup_loop() in the background using asyncio.create_task()
        - Called on FastAPI lifespan startup

        Note:
            This method is automatically called from FastAPI's lifespan event.
        """
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task

        This method safely cancels the running cleanup task and waits for it to terminate.
        CancelledError is automatically ignored.

        Behavior:
        1. Check if the task is running
        2. Request task cancellation (task.cancel())
        3. Wait for cancellation to complete (ignoring CancelledError)

        Note:
            This method is automatically called on FastAPI lifespan shutdown.
        """
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

    async def store_event(self, run_id: str, event: SSEEvent) -> None:
        """Store an SSE event with a sequence number in PostgreSQL

        This method saves an SSE event to the run_events table.
        It extracts a sequence number from the event ID to make it sortable.

        Event ID format:
        - Expected format: "{run_id}_event_{seq}"
        - Example: "abc123_event_0", "abc123_event_1"
        - Uses a default of 0 if seq extraction fails

        Behavior:
        1. Extract sequence number from event.id
        2. Acquire a PostgreSQL connection
        3. Execute an INSERT query (ignoring conflicts)
        4. Store data as JSONB type

        Args:
            run_id (str): Unique run identifier
            event (SSEEvent): The SSE event to store (id, event, data, timestamp)

        Note:
            - Prevents duplicate insertions with ON CONFLICT DO NOTHING
            - created_at is automatically set to NOW() by the DB
        """
        # 이벤트 ID에서 시퀀스 번호 추출 (형식: {run_id}_event_{seq})
        try:
            seq = int(str(event.id).split("_event_")[-1])
        except Exception:
            seq = 0

        engine = db_manager.get_engine()
        async with engine.begin() as conn:
            stmt = text(
                """
                INSERT INTO run_events (id, run_id, seq, event, data, created_at)
                VALUES (:id, :run_id, :seq, :event, :data, NOW())
                ON CONFLICT (id) DO NOTHING
                """
            ).bindparams(bindparam("data", type_=JSONB))
            await conn.execute(
                stmt,
                {
                    "id": event.id,
                    "run_id": run_id,
                    "seq": seq,
                    "event": event.event,
                    "data": event.data,
                },
            )

    async def get_events_since(self, run_id: str, last_event_id: str) -> list[SSEEvent]:
        """Retrieve all events after a specific event (for replay on reconnect)

        This method returns all events in sequence order that occurred after
        the last event a client received, for when they reconnect.

        Behavior:
        1. Extract sequence number from last_event_id
        2. Query for all events with a greater sequence number
        3. Order by seq ASC to ensure sequential replay

        Args:
            run_id (str): Unique run identifier
            last_event_id (str): The ID of the last received event (format: "{run_id}_event_{seq}")

        Returns:
            list[SSEEvent]: A list of events sorted by sequence

        Note:
            - If last_event_id parsing fails, last_seq = -1 (returns all events)
            - Used with the SSE Last-Event-ID header
        """
        # 마지막 이벤트 ID에서 시퀀스 번호 추출
        try:
            last_seq = int(str(last_event_id).split("_event_")[-1])
        except Exception:
            last_seq = -1  # 파싱 실패 시 모든 이벤트 반환

        engine = db_manager.get_engine()
        async with engine.begin() as conn:
            rs = await conn.execute(
                text(
                    """
                    SELECT id, event, data, created_at
                    FROM run_events
                    WHERE run_id = :run_id AND seq > :last_seq
                    ORDER BY seq ASC
                    """
                ),
                {"run_id": run_id, "last_seq": last_seq},
            )
            rows = rs.fetchall()
        return [SSEEvent(id=r.id, event=r.event, data=r.data, timestamp=r.created_at) for r in rows]

    async def get_all_events(self, run_id: str) -> list[SSEEvent]:
        """Retrieve all events for a specific run (for full replay)

        This method returns all events for a specific run in sequence order.
        It is used for debugging or replaying the entire event stream from the beginning.

        Args:
            run_id (str): Unique run identifier

        Returns:
            list[SSEEvent]: All events sorted by sequence

        Note:
            - Returns in order of occurrence by sorting by seq ASC
            - Used when a client connects without a Last-Event-ID
        """
        engine = db_manager.get_engine()
        async with engine.begin() as conn:
            rs = await conn.execute(
                text(
                    """
                    SELECT id, event, data, created_at
                    FROM run_events
                    WHERE run_id = :run_id
                    ORDER BY seq ASC
                    """
                ),
                {"run_id": run_id},
            )
            rows = rs.fetchall()
        return [SSEEvent(id=r.id, event=r.event, data=r.data, timestamp=r.created_at) for r in rows]

    async def cleanup_events(self, run_id: str) -> None:
        """Delete all events for a specific run

        This method deletes all stored events for a specific run from the database.
        It can be used to manually clean up when a run is complete or replay is no longer needed.

        Args:
            run_id (str): The unique identifier of the run to delete

        Note:
            - Automatic cleanup is handled by _cleanup_old_runs() on a time basis
            - This method is for manual cleanup (e.g., immediate deletion after run completion)
        """
        engine = db_manager.get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM run_events WHERE run_id = :run_id"),
                {"run_id": run_id},
            )

    async def get_run_info(self, run_id: str) -> dict | None:
        """Retrieve event statistics for a specific run

        This method returns event metadata for a run,
        providing event count, last event ID, and timestamp.

        Behavior:
        1. Query for the first/last sequence numbers (MIN(seq), MAX(seq))
        2. Query for the ID and created_at of the last event
        3. Calculate event count (last_seq - first_seq + 1)

        Args:
            run_id (str): Unique run identifier

        Returns:
            dict | None: A dictionary of event statistics or None (if no events)
                - run_id: Run ID
                - event_count: Total number of events
                - first_event_time: First event time (currently None)
                - last_event_time: Creation time of the last event
                - last_event_id: ID of the last event

        Note:
            - Returns None if there are no events
            - Useful for client state synchronization and debugging
        """
        engine = db_manager.get_engine()
        async with engine.begin() as conn:
            # 첫 번째/마지막 시퀀스 번호 조회
            rs = await conn.execute(
                text(
                    """
                    SELECT MIN(seq) AS first_seq, MAX(seq) AS last_seq
                    FROM run_events
                    WHERE run_id = :run_id
                    """
                ),
                {"run_id": run_id},
            )
            row = rs.fetchone()
            if not row or row.last_seq is None:
                return None

            # 마지막 이벤트의 ID와 생성 시간 조회
            rs2 = await conn.execute(
                text(
                    """
                    SELECT id, created_at
                    FROM run_events
                    WHERE run_id = :run_id AND seq = :last_seq
                    LIMIT 1
                    """
                ),
                {"run_id": run_id, "last_seq": row.last_seq},
            )
            last = rs2.fetchone()
        return {
            "run_id": run_id,
            "event_count": int(row.last_seq) - int(row.first_seq) + 1 if row.first_seq is not None else 0,
            "first_event_time": None,
            "last_event_time": last.created_at if last else None,
            "last_event_id": last.id if last else None,
        }

    async def _cleanup_loop(self) -> None:
        """Background loop for the cleanup task (internal method)

        This method runs an infinite loop, calling _cleanup_old_runs()
        to delete old events at each CLEANUP_INTERVAL (300 seconds).

        Behavior:
        1. Wait for CLEANUP_INTERVAL (300 seconds)
        2. Call _cleanup_old_runs() (deletes events older than 1 hour)
        3. Go back to step 1 and repeat

        Exception handling:
        - CancelledError: Normal shutdown (when stop_cleanup_task() is called)
        - Exception: Print an error log and continue running

        Note:
            - This method is run as an asyncio.Task by start_cleanup_task()
            - The loop continues to run even if cleanup fails (service stability)
        """
        while True:
            try:
                await asyncio.sleep(self.CLEANUP_INTERVAL)  # 300초 대기
                await self._cleanup_old_runs()
            except asyncio.CancelledError:
                break  # 정상 종료
            except Exception as e:
                print(f"Error in event store cleanup: {e}")

    async def _cleanup_old_runs(self) -> None:
        """Delete old events older than 1 hour (internal method)

        This method deletes all events that were created more than 1 hour ago.
        It is called periodically to save disk space and maintain database performance.

        Deletion condition:
        - created_at < NOW() - INTERVAL '1 hour'
        - i.e., all events created more than 1 hour before the current time

        Note:
            - Called every 300 seconds (5 minutes) by _cleanup_loop()
            - Default retention period: 1 hour
            - Uses PostgreSQL INTERVAL syntax
        """
        engine = db_manager.get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM run_events WHERE created_at < NOW() - INTERVAL '1 hour'"))


# ---------------------------------------------------------------------------
# Global event store instance
# ---------------------------------------------------------------------------

event_store = EventStore()


async def store_sse_event(run_id: str, event_id: str, event_type: str, data: dict) -> SSEEvent:
    """Helper function to serialize and store an SSE event

    This function serializes SSE event data into a JSONB-safe format and then
    stores it in PostgreSQL. It handles complex Python objects and provides
    a fallback mechanism to prevent execution from stopping on failure.

    Workflow:
    1. Serialize complex objects (datetime, UUID, etc.) with GeneralSerializer
    2. Ensure JSONB compatibility with a JSON roundtrip
    3. On serialization failure, convert to string and store (fallback)
    4. Create an SSEEvent object (with UTC timestamp)
    5. Call event_store.store_event() to save to DB

    Args:
        run_id (str): Unique run identifier
        event_id (str): Event ID (format: "{run_id}_event_{seq}")
        event_type (str): Event type ("values", "messages", "end", etc.)
        data (dict): Event payload (may contain complex objects)

    Returns:
        SSEEvent: The stored SSE event object

    Note:
        - GeneralSerializer handles datetime, UUID, Pydantic models, etc.
        - On serialization failure, saves as {"raw": str(data)} to prevent interruption
        - Primarily used in streaming_service.py
    """
    serializer = GeneralSerializer()

    # 복잡한 객체를 JSONB 안전 형식으로 직렬화
    try:
        safe_data = json.loads(json.dumps(data, default=serializer.serialize))
    except Exception:
        # 직렬화 실패 시 문자열로 변환 (실행 중단 방지)
        safe_data = {"raw": str(data)}

    event = SSEEvent(id=event_id, event=event_type, data=safe_data, timestamp=datetime.now(UTC))
    await event_store.store_event(run_id, event)
    return event
