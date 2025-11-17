"""Event converter for SSE streaming

This module converts LangGraph execution events into SSE (Server-Sent Events) format.
It can handle both raw and stored events.

Main components:
- EventConverter: Class responsible for event conversion logic
- convert_raw_to_sse(): Converts real-time events to SSE
- convert_stored_to_sse(): Converts stored events to SSE (for replay)

Supported event types:
- messages: Message chunks (streaming response)
- values: State values
- updates: State updates
- state: Full state
- logs: Log messages
- tasks: Execution tasks
- subgraphs: Subgraph information
- debug: Debug information
- events: Custom events
- checkpoints: Checkpoints
- custom: User-defined events
- end: Stream termination
- error: Error information

Usage example:
    converter = EventConverter()

    # Convert real-time event
    sse_event = converter.convert_raw_to_sse(event_id, raw_event)

    # Convert stored event (replay)
    sse_event = converter.convert_stored_to_sse(stored_event, run_id)
"""

from collections.abc import Mapping
from typing import Any, Protocol

from ..core.sse import (
    create_checkpoints_event,
    create_custom_event,
    create_debug_event,
    create_end_event,
    create_error_event,
    create_events_event,
    create_logs_event,
    create_messages_event,
    create_metadata_event,
    create_state_event,
    create_subgraphs_event,
    create_tasks_event,
    create_updates_event,
    create_values_event,
)


class StoredEventLike(Protocol):
    """Protocol describing stored events replayed from the database."""

    id: str
    event: str
    data: Mapping[str, Any] | None


class EventConverter:
    """Converter for transforming LangGraph events into SSE format.

    This class converts various events that occur during LangGraph graph execution
    into the standard SSE (Server-Sent Events) format.

    Key features:
    - Real-time event conversion: Handles events from LangGraph astream()
    - Stored event conversion: Replays events stored in PostgreSQL
    - Stream mode detection: Automatically recognizes event types and applies the appropriate SSE format
    - Interrupt handling: Converts __interrupt__ updates into values events

    SSE format:
    - event: {event_type}
    - data: {JSON_payload}
    - id: {event_ID}

    Usage patterns:
    - Instantiate as a singleton or in the service layer
    - Call convert_raw_to_sse() for each event in streaming_service
    - Call convert_stored_to_sse() for replay from event_store
    """

    def convert_raw_to_sse(self, event_id: str, raw_event: Any) -> str | None:
        """Converts a real-time raw event into SSE format.

        Takes a raw event from LangGraph's graph.astream() and converts it
        into a standard SSE (Server-Sent Events) format string.

        Workflow:
        1. Parse the raw event to extract the stream mode and payload.
        2. Create the appropriate SSE event based on the stream mode.
        3. Return the SSE formatted string.

        Args:
            event_id (str): A unique identifier for the event (sequentially increasing ID).
            raw_event (Any): The raw event received from LangGraph.
                - tuple: (stream_mode, payload) or (node_path, stream_mode, payload)
                - dict: Processed with the default "values" mode.

        Returns:
            str | None: An SSE formatted string, or None if conversion is not possible.

        SSE format example:
            event: messages
            data: {"chunk": "Hello", "metadata": {...}}
            id: 1

        Usage example:
            converter = EventConverter()
            sse_event = converter.convert_raw_to_sse("1", ("messages", message_data))
        """
        stream_mode, payload = self._parse_raw_event(raw_event)
        return self._create_sse_event(stream_mode, payload, event_id)

    def convert_stored_to_sse(self, stored_event: StoredEventLike, run_id: str | None = None) -> str | None:
        """Converts an event stored in PostgreSQL into SSE format.

        This is used to replay events from the event_store, for example, when a client
        reconnects after a disconnection and needs to receive past events.

        Workflow:
        1. Check the type (event) of the stored event.
        2. Extract the payload from the stored data field.
        3. Generate the appropriate SSE format for each event type.
        4. Retain the original event ID to ensure order.

        Args:
            stored_event: The event ORM object fetched from the event_store.
                - event (str): The event type.
                - data (dict): The stored payload.
                - id (str): The original event ID.
            run_id (str | None): The run ID (required for metadata events).

        Returns:
            str | None: An SSE formatted string, or None if conversion is not possible.

        Supported event types:
            - messages: Message chunk (message_chunk, metadata)
            - values: State value (chunk)
            - metadata: Execution metadata (requires run_id)
            - state: Full state (state)
            - logs: Logs (logs)
            - tasks: Task list (tasks)
            - subgraphs: Subgraph information (subgraphs)
            - debug: Debug information (debug)
            - events: Custom events (event)
            - end: Stream termination
            - error: Error information (error)

        Usage example:
            stored_event = await event_store.get_event(event_id)
            sse_event = converter.convert_stored_to_sse(stored_event, run_id)
        """
        event_type = stored_event.event
        data: Mapping[str, Any] | None = stored_event.data
        event_id = stored_event.id

        def _coerce_dict(value: Any) -> dict[str, Any]:
            if isinstance(value, Mapping):
                return dict(value)
            return {}

        data_dict = _coerce_dict(data)

        if event_type == "messages":
            message_chunk = data_dict.get("message_chunk")
            metadata = data_dict.get("metadata")
            if message_chunk is None:
                return None
            # If metadata exists, pass as a tuple; otherwise, pass only the chunk.
            message_data = (message_chunk, metadata) if metadata is not None else message_chunk
            return create_messages_event(message_data, event_id=event_id)
        elif event_type == "values":
            return create_values_event(_coerce_dict(data_dict), event_id)
        elif event_type == "metadata":
            if run_id is None:
                return None
            return create_metadata_event(run_id, event_id)
        elif event_type == "state":
            return create_state_event(_coerce_dict(data_dict.get("state")), event_id)
        elif event_type == "logs":
            return create_logs_event(_coerce_dict(data_dict.get("logs")), event_id)
        elif event_type == "tasks":
            return create_tasks_event(_coerce_dict(data_dict.get("tasks")), event_id)
        elif event_type == "subgraphs":
            return create_subgraphs_event(_coerce_dict(data_dict.get("subgraphs")), event_id)
        elif event_type == "debug":
            return create_debug_event(_coerce_dict(data_dict.get("debug")), event_id)
        elif event_type == "events":
            return create_events_event(_coerce_dict(data_dict.get("event")), event_id)
        elif event_type == "end":
            return create_end_event(event_id)
        elif event_type == "error":
            error_payload = data_dict.get("error")
            error_message = error_payload if isinstance(error_payload, str) else str(error_payload)
            return create_error_event(error_message, event_id)
        return None

    def _parse_raw_event(self, raw_event: Any) -> tuple[str, Any]:
        """Parses a raw event and returns a (stream_mode, payload) tuple.

        LangGraph's graph.astream() can return events in several formats:
        - 2-tuple: (stream_mode, payload)
        - 3-tuple: (node_path, stream_mode, payload)
        - Single value: A dictionary or other data.

        This method normalizes these various formats to allow for consistent processing.

        Args:
            raw_event (Any): The raw event received from LangGraph.
                - tuple(2): (stream_mode, payload)
                - tuple(3): (node_path, stream_mode, payload)
                - Other: A single value (processed with the default "values" mode).

        Returns:
            tuple[str, Any]: A normalized (stream_mode, payload) tuple.
                - stream_mode: "messages", "values", "updates", etc.
                - payload: The event data.

        Usage example:
            # 2-tuple event
            mode, payload = self._parse_raw_event(("messages", message_data))
            # Result: ("messages", message_data)

            # 3-tuple event (with node path)
            mode, payload = self._parse_raw_event(("path.to.node", "updates", data))
            # Result: ("updates", data) - node path is currently ignored

            # Single value event
            mode, payload = self._parse_raw_event({"key": "value"})
            # Result: ("values", {"key": "value"})
        """
        if isinstance(raw_event, tuple):
            if len(raw_event) == 2:
                # (stream_mode, payload) format
                return raw_event[0], raw_event[1]
            elif len(raw_event) == 3:
                # (node_path, stream_mode, payload) format
                # The node path is currently not used, so we ignore it and return only the mode and payload.
                return raw_event[1], raw_event[2]

        # If not a tuple, process with the default "values" mode.
        return "values", raw_event

    def _create_sse_event(self, stream_mode: str, payload: Any, event_id: str) -> str | None:
        """Creates the appropriate SSE event based on the stream mode.

        Takes the parsed stream mode and payload and generates the corresponding
        SSE formatted string by calling the appropriate SSE creation function for each stream mode.

        Special handling rules:
        - updates mode: If the __interrupt__ key is present, it is converted to a values event.
          (Human-in-the-Loop interrupts are passed to the client as values).

        Args:
            stream_mode (str): The event stream mode.
                - "messages": Message chunk
                - "values": State value
                - "updates": State update
                - "state": Full state
                - "logs": Log message
                - "tasks": Execution task
                - "subgraphs": Subgraph information
                - "debug": Debug information
                - "events": Custom event
                - "checkpoints": Checkpoint
                - "custom": User-defined
                - "end": Stream termination
            payload (Any): The event data payload.
            event_id (str): The SSE event ID.

        Returns:
            str | None: An SSE formatted string, or None for unknown modes.

        SSE format:
            event: {stream_mode}
            data: {JSON_serialized_payload}
            id: {event_id}

        Usage example:
            sse = self._create_sse_event("messages", message_data, "1")
            # Result:
            # event: messages
            # data: {"chunk": "Hello"}
            # id: 1
        """
        if stream_mode == "messages":
            return create_messages_event(payload, event_id=event_id)
        elif stream_mode == "values":
            return create_values_event(payload, event_id)
        elif stream_mode == "updates":
            # Convert interrupt updates to values, otherwise keep as updates.
            # In the HITL (Human-in-the-Loop) pattern, the __interrupt__ key indicates a user approval waiting state.
            if isinstance(payload, dict) and "__interrupt__" in payload:
                return create_values_event(payload, event_id)
            else:
                return create_updates_event(payload, event_id)
        elif stream_mode == "state":
            return create_state_event(payload, event_id)
        elif stream_mode == "logs":
            return create_logs_event(payload, event_id)
        elif stream_mode == "tasks":
            return create_tasks_event(payload, event_id)
        elif stream_mode == "subgraphs":
            return create_subgraphs_event(payload, event_id)
        elif stream_mode == "debug":
            return create_debug_event(payload, event_id)
        elif stream_mode == "events":
            return create_events_event(payload, event_id)
        elif stream_mode == "checkpoints":
            return create_checkpoints_event(payload, event_id)
        elif stream_mode == "custom":
            return create_custom_event(payload, event_id)
        elif stream_mode == "end":
            return create_end_event(event_id)

        # Return None for unknown stream modes (will be ignored).
        return None


class StoredEventLike(Protocol):
    """Minimal protocol describing stored events replayed from the database."""

    id: str
    event: str
    data: Mapping[str, Any] | None
