"""SSE 스트리밍 오케스트레이션 서비스

이 모듈은 LangGraph 실행 이벤트를 SSE(Server-Sent Events) 프로토콜로
클라이언트에게 실시간 스트리밍하고, PostgreSQL에 영속화하여 재생을 지원합니다.

주요 구성 요소:
• StreamingService - SSE 스트리밍 및 이벤트 관리 총괄
• streaming_service - 전역 서비스 인스턴스

주요 기능:
• 실시간 이벤트 스트리밍: LangGraph 실행 이벤트를 SSE로 전달
• 이벤트 영속화: PostgreSQL에 저장하여 재연결 시 재생 가능
• 브로커 기반 분배: 프로듀서-컨슈머 패턴으로 다중 클라이언트 지원
• 이벤트 변환: LangGraph 형식 → Agent Protocol SSE 형식

사용 예:
    from services.streaming_service import streaming_service

    # 실행 스트리밍 (재연결 지원)
    async for sse_event in streaming_service.stream_run_execution(run, last_event_id="run_123_event_42"):
        yield sse_event

    # 실행 취소 시그널
    await streaming_service.signal_run_cancelled(run_id)
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from ..core.sse import create_error_event, create_metadata_event
from ..models import Run
from ..utils import extract_event_sequence, generate_event_id
from .broker import broker_manager
from .event_converter import EventConverter
from .event_store import event_store, store_sse_event

logger = logging.getLogger(__name__)


class StreamingService:
    """SSE Streaming Orchestration Service (LangGraph Compatible)

    This class streams LangGraph execution events via SSE (Server-Sent Events)
    and persists them in PostgreSQL to support replay on reconnection.

    Key features:
    - Real-time event streaming: Producer-consumer pattern via broker
    - Event persistence: Utilizes PostgreSQL-based event store
    - Reconnection support: Event replay based on last_event_id
    - Event conversion: LangGraph format → Agent Protocol SSE format
    - Execution control: Signaling for cancellation, interruption, and errors

    Architecture:
    - Producer: execute_run_async() sends LangGraph events to broker + DB
    - Consumer: stream_run_execution() reads events from broker and sends as SSE
    - Storage: event_store saves events to PostgreSQL, enabling replay

    Usage pattern:
    - Singleton instance: streaming_service (at the bottom of the module)
    - Async streaming: stream_run_execution() returns an AsyncIterator
    """

    def __init__(self) -> None:
        # Per-run event sequence counters (for event ID generation and deduplication)
        self.event_counters: dict[str, int] = {}
        # Converter for LangGraph events → Agent Protocol SSE
        self.event_converter = EventConverter()

    def _process_interrupt_updates(self, raw_event: Any, only_interrupt_updates: bool) -> tuple[Any, bool]:
        """Process interrupt updates (filtering and conversion)

        When a user does not request the 'updates' stream_mode, this selectively processes only interrupt updates.
        LangGraph issues an 'updates' event with an __interrupt__ key when an interruption occurs.
        This is converted to a 'values' event to be delivered to the client.

        Workflow:
        1. Apply filtering only if only_interrupt_updates=True
        2. Pass only 'updates' events that have a non-empty __interrupt__ key
        3. Convert the passed interrupt update to a 'values' event
        4. Skip all other 'updates' events

        Args:
            raw_event (Any): The raw event from LangGraph (tuple or dict)
            only_interrupt_updates (bool): If True, process only interrupt updates

        Returns:
            tuple[Any, bool]: (processed_event, should_skip)
                - processed_event: The converted or original event
                - should_skip: If True, do not send this event to the broker/store
        """
        if (
            isinstance(raw_event, tuple)
            and len(raw_event) >= 2
            and raw_event[0] == "updates"
            and only_interrupt_updates
        ):
            # Since the user did not request updates, process only interrupt updates
            if (
                isinstance(raw_event[1], dict)
                and "__interrupt__" in raw_event[1]
                and len(raw_event[1].get("__interrupt__", [])) > 0
            ):
                # Convert interrupt update to a values event to deliver to the client
                return ("values", raw_event[1]), False
            else:
                # Skip regular updates as they were not requested
                return raw_event, True
        else:
            # Return the original event if no filtering is needed or it's not an interrupt mode
            return raw_event, False

    def _next_event_counter(self, run_id: str, event_id: str) -> int:
        """Update the per-run event counter and return the next sequence number

        This method extracts the sequence number from the event_id to update the per-run counter.
        The counter is used for event ID generation and deduplication.

        How it works:
        1. Extract sequence number from event_id (e.g., "run_123_event_42" → 42)
        2. Compare with the currently stored counter
        3. If the extracted number is larger, update the counter
        4. Return the latest counter value

        Args:
            run_id (str): Unique run identifier
            event_id (str): Event ID (format: {run_id}_event_{sequence})

        Returns:
            int: The updated event counter value
        """
        try:
            idx = self._extract_event_sequence(event_id)
            current = self.event_counters.get(run_id, 0)
            if idx > current:
                self.event_counters[run_id] = idx
                return idx
        except Exception:
            pass  # 형식 오류 무시 (비정상 event_id 포맷)
        return self.event_counters.get(run_id, 0)

    async def put_to_broker(
        self,
        run_id: str,
        event_id: str,
        raw_event: Any,
        only_interrupt_updates: bool = False,
    ) -> None:
        """Add an event to the broker queue to deliver to live consumers (clients)

        This method delivers events that occur during LangGraph execution in real time via the broker.
        It acts as the producer in a producer-consumer pattern.

        Workflow:
        1. Get or create the broker for the run
        2. Update the event counter (track sequence)
        3. Filter and convert interrupt updates
        4. Add the event to the broker queue

        Args:
            run_id (str): Unique run identifier
            event_id (str): Unique event identifier (format: {run_id}_event_{sequence})
            raw_event (Any): The raw event from LangGraph
            only_interrupt_updates (bool): If True, process only interrupt updates (default: False)

        Note:
            - The broker is a memory-based queue that distributes events to multiple clients
            - Events are also saved to the DB separately via store_event_from_raw()
        """
        broker = broker_manager.get_or_create_broker(run_id)
        self._next_event_counter(run_id, event_id)

        # 인터럽트 업데이트 필터링 및 변환
        processed_event, should_skip = self._process_interrupt_updates(raw_event, only_interrupt_updates)
        if should_skip:
            return

        await broker.put(event_id, processed_event)

    async def store_event_from_raw(
        self,
        run_id: str,
        event_id: str,
        raw_event: Any,
        only_interrupt_updates: bool = False,
    ) -> None:
        """Convert a raw event to storage format and persist it in PostgreSQL

        This method parses a LangGraph event and saves it to the PostgreSQL event store.
        This is essential for replaying events on reconnection.

        Workflow:
        1. Filter and convert interrupt updates
        2. Parse the event structure (extract node_path, stream_mode, payload)
        3. Determine the storage format based on stream_mode
        4. Save to PostgreSQL via event_store

        Supported stream_modes:
        - messages: Message chunk streaming (e.g., LLM responses)
        - values: Graph state values (general execution data)
        - updates: State updates (including interrupts)
        - end: Signal for run completion

        Args:
            run_id (str): Unique run identifier
            event_id (str): Unique event identifier
            raw_event (Any): The raw event from LangGraph
            only_interrupt_updates (bool): If True, save only interrupt updates

        Note:
            - Stored events are used by the replay logic in stream_run_execution()
            - event_store.cleanup_old_events() periodically deletes old events
        """
        # Filter and convert interrupt updates
        processed_event, should_skip = self._process_interrupt_updates(raw_event, only_interrupt_updates)
        if should_skip:
            return

        # Parse the processed event structure
        node_path = None
        stream_mode_label = None
        event_payload = None

        if isinstance(processed_event, tuple):
            if len(processed_event) == 2:
                # (stream_mode, payload) format
                stream_mode_label, event_payload = processed_event
            elif len(processed_event) == 3:
                # (node_path, stream_mode, payload) format
                node_path, stream_mode_label, event_payload = processed_event
        else:
            # Treat single value as 'values'
            stream_mode_label = "values"
            event_payload = processed_event

        # Determine storage format based on stream_mode and save
        if stream_mode_label == "messages":
            # Message chunk streaming (e.g., LLM responses)
            await store_sse_event(
                run_id,
                event_id,
                "messages",
                {
                    "type": "messages_stream",
                    "message_chunk": event_payload[0]
                    if isinstance(event_payload, tuple) and len(event_payload) >= 1
                    else event_payload,
                    "metadata": event_payload[1]
                    if isinstance(event_payload, tuple) and len(event_payload) >= 2
                    else None,
                    "node_path": node_path,
                },
            )
        elif stream_mode_label == "values" or stream_mode_label == "updates":
            # Graph state values or updates
            await store_sse_event(
                run_id,
                event_id,
                "values",
                {"type": "execution_values", "chunk": event_payload},
            )
        elif stream_mode_label == "end":
            # Run completion signal
            payload_dict = event_payload if isinstance(event_payload, dict) else {}
            await store_sse_event(
                run_id,
                event_id,
                "end",
                {
                    "type": "run_complete",
                    "status": payload_dict.get("status", "completed"),
                    "final_output": payload_dict.get("final_output"),
                },
            )
        # Other stream_modes can be added if needed

    async def signal_run_cancelled(self, run_id: str) -> None:
        """Send a run cancellation signal to the broker to notify clients

        Called when a run is cancelled to send a cancellation event to all connected clients
        and clean up the broker.

        Workflow:
        1. Increment the event counter (generate a new sequence number)
        2. Create a cancellation event ID
        3. Send an "end" event to the broker (status: cancelled)
        4. Clean up the broker (no more events)

        Args:
            run_id (str): Unique run identifier

        Note:
            - This method is called from cancel_run()
            - Clients cannot reconnect after the broker is cleaned up
        """
        counter = self.event_counters.get(run_id, 0) + 1
        self.event_counters[run_id] = counter
        event_id = generate_event_id(run_id, counter)

        broker = broker_manager.get_or_create_broker(run_id)
        if broker:
            await broker.put(event_id, ("end", {"status": "cancelled"}))

        broker_manager.cleanup_broker(run_id)

    async def signal_run_error(self, run_id: str, error_message: str) -> None:
        """Send a run error signal to the broker to notify clients

        Called when an error occurs during a run to send an error event to all connected clients
        and clean up the broker.

        Workflow:
        1. Increment the event counter (generate a new sequence number)
        2. Create an error event ID
        3. Send an "end" event to the broker (status: failed, with error message)
        4. Clean up the broker

        Args:
            run_id (str): Unique run identifier
            error_message (str): The error message to deliver to the client

        Note:
            - This method is called from the exception handling in execute_run_async()
            - Also called from interrupt_run() (treating interruption as an error)
        """
        counter = self.event_counters.get(run_id, 0) + 1
        self.event_counters[run_id] = counter
        event_id = generate_event_id(run_id, counter)

        broker = broker_manager.get_or_create_broker(run_id)
        if broker:
            await broker.put(event_id, ("end", {"status": "failed", "error": error_message}))

        broker_manager.cleanup_broker(run_id)

    def _extract_event_sequence(self, event_id: str) -> int:
        """Extract sequence number from event_id

        Event ID format: {run_id}_event_{sequence}
        Example: "run_abc123_event_42" → 42

        Args:
            event_id (str): Unique event identifier

        Returns:
            int: The extracted sequence number
        """
        return extract_event_sequence(event_id)

    async def stream_run_execution(
        self,
        run: Run,
        last_event_id: str | None = None,
        cancel_on_disconnect: bool = False,
    ) -> AsyncIterator[str]:
        """Stream execution events via SSE (with reconnection support)

        This method streams all events for a LangGraph run via SSE (Server-Sent Events).
        It acts as the consumer in a producer-consumer pattern and supports event replay on reconnection.

        Workflow:
        1. Send metadata event (sequence 0, only on first connection)
        2. Replay stored events (events after last_event_id)
        3. Stream live events (received in real time from the broker)

        Reconnection support:
        - If the client provides a last_event_id, replay starts from that event
        - Replays stored events from PostgreSQL first, then streams live events
        - Deduplication: Skips already sent events using sequence numbers

        Args:
            run (Run): The run object (contains run_id, status, etc.)
            last_event_id (str | None): The ID of the last received event (provided on reconnect)
            cancel_on_disconnect (bool): If True, cancel the run on disconnect (default: False)

        Yields:
            str: An SSE-formatted event string (event: type\ndata: json\nid: id\n\n)

        Raises:
            asyncio.CancelledError: If the stream is cancelled (e.g., client disconnect)

        Note:
            - Used with FastAPI's StreamingResponse
            - Waits for the broker to finish even after the run is complete
            - Sends an error event and terminates the stream on error
        """
        run_id = run.run_id
        try:
            # Send metadata event first (sequence 0, not stored in the store)
            if not last_event_id:
                event_id = generate_event_id(run_id, 0)
                metadata_event = create_metadata_event(run_id, event_id)
                yield metadata_event

            # Replay stored events (on reconnect or first connection)
            last_sent_sequence = 0
            if last_event_id:
                last_sent_sequence = self._extract_event_sequence(last_event_id)

            async for sse_event in self._replay_stored_events(run_id, last_event_id):
                yield sse_event

            # If the run is still active, stream live events
            async for sse_event in self._stream_live_events(run, last_sent_sequence):
                yield sse_event

        except asyncio.CancelledError:
            logger.debug(f"Stream cancelled for run {run_id}")
            if cancel_on_disconnect:
                # Also cancel the background execution task on disconnect
                self._cancel_background_task(run_id)
            raise
        except Exception as e:
            logger.error(f"Error in stream_run_execution for run {run_id}: {e}")
            yield create_error_event(str(e))

    async def _replay_stored_events(self, run_id: str, last_event_id: str | None) -> AsyncIterator[str]:
        """Replay events stored in PostgreSQL (reconnection support)

        This method queries events from the PostgreSQL event store and resends them to the client.
        This is a core feature for recovering missed events on reconnection.

        How it works:
        1. If last_event_id is provided: query for events after that event
        2. If last_event_id is not provided: query for all stored events (first connection)
        3. Yield each event converted to SSE format

        Args:
            run_id (str): Unique run identifier
            last_event_id (str | None): The ID of the last received event (or None for from the beginning)

        Yields:
            str: An SSE-formatted event string

        Note:
            - event_store.get_events_since() performs a range query based on sequence number
            - Stored events are returned sorted by sequence
        """
        if last_event_id:
            stored_events = await event_store.get_events_since(run_id, last_event_id)
        else:
            stored_events = await event_store.get_all_events(run_id)

        for ev in stored_events:
            sse_event = self._stored_event_to_sse(run_id, ev)
            if sse_event:
                yield sse_event

    async def _stream_live_events(self, run: Run, last_sent_sequence: int) -> AsyncIterator[str]:
        """Stream live events from the broker (real-time delivery)

        This method receives events in real time from the broker queue and sends them to the client.
        It acts as the consumer in a producer-consumer pattern.

        How it works:
        1. Get the broker for the run (or create it)
        2. Check if the run is complete and the broker is finished (if both true, no streaming)
        3. Receive events from the broker's async iterator
        4. Skip duplicate events (compare sequence with replayed events)
        5. Yield each event converted to SSE format

        Deduplication:
        - Skips events that have already been sent by comparing with last_sent_sequence
        - Prevents re-sending events that were sent during the replay phase

        Args:
            run (Run): The run object (for status checking)
            last_sent_sequence (int): The last sequence number that was already sent

        Yields:
            str: An SSE-formatted event string

        Note:
            - broker.aiter() waits for new events to arrive (blocking)
            - The iterator terminates when the broker receives a finish signal
        """
        run_id = run.run_id
        broker = broker_manager.get_or_create_broker(run_id)

        # If the run is complete and the broker is also finished, there are no events to stream
        if run.status in ["completed", "failed", "cancelled", "interrupted"] and broker.is_finished():
            return

        # Stream live events
        if broker:
            async for event_id, raw_event in broker.aiter():
                # Skip events that were already sent during the replay phase (deduplication)
                current_sequence = self._extract_event_sequence(event_id)
                if current_sequence <= last_sent_sequence:
                    continue

                sse_event = await self._convert_raw_to_sse(event_id, raw_event)
                if sse_event:
                    yield sse_event
                    last_sent_sequence = current_sequence

    def _cancel_background_task(self, run_id: str) -> None:
        """Cancel the background execution task when a client disconnects

        When cancel_on_disconnect=True, this method cancels the background task for the run
        if the client disconnects.

        Workflow:
        1. Look up the run task in the active_runs dictionary
        2. If the task exists and is not yet done, cancel it
        3. Log a warning on failure (not a critical error)

        Args:
            run_id (str): Unique run identifier

        Note:
            - active_runs is a global dictionary managed in the api.runs module
            - task.cancel() raises an asyncio.CancelledError
            - execute_run_async() handles the CancelledError to perform cleanup
        """
        try:
            from ..api.runs import active_runs

            task = active_runs.get(run_id)
            if task and not task.done():
                task.cancel()
        except Exception as e:
            logger.warning(f"Failed to cancel background task for run {run_id} on disconnect: {e}")

    async def _convert_raw_to_sse(self, event_id: str, raw_event: Any) -> str | None:
        """Convert a raw event from the broker to SSE format

        This method uses EventConverter to convert a LangGraph event to Agent Protocol SSE format.

        Args:
            event_id (str): Unique event identifier
            raw_event (Any): The raw event from the broker (tuple or dict)

        Returns:
            str | None: An SSE-formatted string or None (on conversion failure)
        """
        return self.event_converter.convert_raw_to_sse(event_id, raw_event)

    async def interrupt_run(self, run_id: str) -> bool:
        """Interrupt a run (force stop)

        Interrupts and stops a running graph.
        Mainly used by administrators or for emergency stops.

        Workflow:
        1. Send an error signal ("Run was interrupted")
        2. Update the run status to "interrupted"
        3. Return success status

        Args:
            run_id (str): Unique run identifier

        Returns:
            bool: True on successful interruption, False on failure

        Note:
            - Uses signal_run_error() to treat as an error event
            - This is different from LangGraph's interrupt() (this is a force stop)
        """
        try:
            await self.signal_run_error(run_id, "Run was interrupted")
            await self._update_run_status(run_id, "interrupted")
            return True
        except Exception as e:
            logger.error(f"Error interrupting run {run_id}: {e}")
            return False

    async def cancel_run(self, run_id: str) -> bool:
        """Cancel a run (for tasks that are queued or in progress)

        Cancels a graph task that is either queued or in progress.
        Called when a client explicitly requests cancellation.

        Workflow:
        1. Send a cancellation signal (an "end" event to the broker)
        2. Update the run status to "cancelled"
        3. Return success status

        Args:
            run_id (str): Unique run identifier

        Returns:
            bool: True on successful cancellation, False on failure

        Note:
            - signal_run_cancelled() performs broker cleanup
            - Can also cancel an already completed run (just updates the status)
        """
        try:
            await self.signal_run_cancelled(run_id)
            await self._update_run_status(run_id, "cancelled")
            return True
        except Exception as e:
            logger.error(f"Error cancelling run {run_id}: {e}")
            return False

    async def _update_run_status(
        self,
        run_id: str,
        status: str,
        output: Any | None = None,
        error: str | None = None,
    ) -> None:
        """Update the run status in the database (using a shared updater)

        This method updates the status of a Run ORM model.
        It uses a lazy import to avoid circular imports.

        Args:
            run_id (str): Unique run identifier
            status (str): The new run status ("running", "completed", "failed", "cancelled", "interrupted")
            output (Any | None): The run output (provided on completion)
            error (str | None): The error message (provided on failure)

        Note:
            - Uses api.runs.update_run_status() to update the database
            - This method is for internal use, called from interrupt_run and cancel_run
        """
        try:
            # Lazy import to avoid circular import
            from ..api.runs import update_run_status

            await update_run_status(run_id, status, output, error)
        except Exception as e:
            logger.error(f"Error updating run status for {run_id}: {e}")

    def is_run_streaming(self, run_id: str) -> bool:
        """Check if a run is currently streaming (broker is active)

        This method checks if a run has an active broker that has not yet finished.
        It is used to determine if a client can receive streaming events.

        Args:
            run_id (str): Unique run identifier

        Returns:
            bool: True if streaming, False otherwise

        Note:
            - Returns False if the broker does not exist or finish() has been called
            - Returns True if the run is complete but the broker has not finished (sending final events)
        """
        broker = broker_manager.get_broker(run_id)
        return broker is not None and not broker.is_finished()

    async def cleanup_run(self, run_id: str) -> None:
        """Clean up streaming resources for a run

        Cleans up streaming-related resources like the broker after a run is completed or cancelled.
        This is necessary to prevent memory leaks.

        Args:
            run_id (str): Unique run identifier

        Note:
            - broker_manager.cleanup_broker() removes the broker instance
            - Event counters are kept in memory (small footprint)
            - Stored PostgreSQL events are periodically cleaned up by cleanup_old_events()
        """
        broker_manager.cleanup_broker(run_id)

    def _stored_event_to_sse(self, run_id: str, ev: Any) -> str | None:
        """Convert a stored event object from PostgreSQL to an SSE string

        This method converts an event object queried from the event_store into SSE format.
        It is used in the replay logic.

        Args:
            run_id (str): Unique run identifier
            ev: The stored event object (returned from event_store)

        Returns:
            str | None: An SSE-formatted string or None (on conversion failure)

        Note:
            - Uses EventConverter.convert_stored_to_sse() for conversion
            - Uses a different method than raw event conversion (due to different storage format)
        """
        return self.event_converter.convert_stored_to_sse(ev, run_id)


# ---------------------------------------------------------------------------
# Global streaming service instance (singleton pattern)
# ---------------------------------------------------------------------------
# This instance is used throughout the application to manage SSE streaming
streaming_service = StreamingService()
