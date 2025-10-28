# LangGraph SDK API Reference

> 이 문서는 `scripts/analyze_sdk_api.py`로 자동 생성되었습니다.

## 개요

LangGraph SDK (0.2.4)가 제공하는 공식 클라이언트 API 메서드 목록입니다.
OpenSource LangGraph Platform는 이 API 스펙을 준수하여 구현되어야 합니다.

## AssistantsClient

> Client for managing assistants in LangGraph.

This class provides methods to interact with assistants,
which are versioned configurations of your graph.

???+ example "Example"

    ```python
    client = get_client(url="http://localhost:2024")
    assistant = await client.assistants.get("assistant_id_123")
    ```

**메서드 개수:** 11개

| 메서드 | 파라미터 | 반환 타입 |
|--------|----------|----------|
| `count()` | metadata, graph_id, headers, params | int |
| `create()` | graph_id, config, context, metadata, assistant_id, if_exists, name, headers, description, params | Assistant |
| `delete()` | assistant_id, headers, params | None |
| `get()` | assistant_id, headers, params | Assistant |
| `get_graph()` | assistant_id, xray, headers, params | dict[str, list[dict[str, Any]]] |
| `get_schemas()` | assistant_id, headers, params | GraphSchema |
| `get_subgraphs()` | assistant_id, namespace, recurse, headers, params | Subgraphs |
| `get_versions()` | assistant_id, metadata, limit, offset, headers, params | list[AssistantVersion] |
| `search()` | metadata, graph_id, limit, offset, sort_by, sort_order, select, headers, params | list[Assistant] |
| `set_latest()` | assistant_id, version, headers, params | Assistant |
| `update()` | assistant_id, graph_id, config, context, metadata, name, headers, description, params | Assistant |

### 메서드 상세

#### `count()`

Count assistants matching filters.

Args:
    metadata: Metadata to filter by. Exact match for each key/value.
    graph_id: Optional graph id to filter by.
    headers: Optional custom headers to inc...

**Parameters:**

- `metadata` (Json) = None
- `graph_id` (str | None) = None
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** int

---

#### `create()`

Create a new assistant.

Useful when graph is configurable and you want to create different assistants based on different configurations.

Args:
    graph_id: The ID of the graph the assistant should ...

**Parameters:**

- `graph_id` (str | None)
- `config` (Config | None) = None
- `context` (Context | None) = None
- `metadata` (Json) = None
- `assistant_id` (str | None) = None
- `if_exists` (OnConflictBehavior | None) = None
- `name` (str | None) = None
- `headers` (Mapping[str, str] | None) = None
- `description` (str | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** Assistant

---

#### `delete()`

Delete an assistant.

Args:
    assistant_id: The assistant ID to delete.
    headers: Optional custom headers to include with the request.
    params: Optional query parameters to include with the re...

**Parameters:**

- `assistant_id` (str)
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** None

---

#### `get()`

Get an assistant by ID.

Args:
    assistant_id: The ID of the assistant to get.
    headers: Optional custom headers to include with the request.
    params: Optional query parameters to include with...

**Parameters:**

- `assistant_id` (str)
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** Assistant

---

#### `get_graph()`

Get the graph of an assistant by ID.

Args:
    assistant_id: The ID of the assistant to get the graph of.
    xray: Include graph representation of subgraphs. If an integer value is provided, only su...

**Parameters:**

- `assistant_id` (str)
- `xray` (int | bool) = False
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** dict[str, list[dict[str, Any]]]

---

#### `get_schemas()`

Get the schemas of an assistant by ID.

Args:
    assistant_id: The ID of the assistant to get the schema of.
    headers: Optional custom headers to include with the request.
    params: Optional que...

**Parameters:**

- `assistant_id` (str)
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** GraphSchema

---

#### `get_subgraphs()`

Get the schemas of an assistant by ID.

Args:
    assistant_id: The ID of the assistant to get the schema of.
    namespace: Optional namespace to filter by.
    recurse: Whether to recursively get su...

**Parameters:**

- `assistant_id` (str)
- `namespace` (str | None) = None
- `recurse` (bool) = False
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** Subgraphs

---

#### `get_versions()`

List all versions of an assistant.

Args:
    assistant_id: The assistant ID to get versions for.
    metadata: Metadata to filter versions by. Exact match filter for each KV pair.
    limit: The maxi...

**Parameters:**

- `assistant_id` (str)
- `metadata` (Json) = None
- `limit` (int) = 10
- `offset` (int) = 0
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** list[AssistantVersion]

---

#### `search()`

Search for assistants.

Args:
    metadata: Metadata to filter by. Exact match filter for each KV pair.
    graph_id: The ID of the graph to filter by.
        The graph ID is normally set in your lan...

**Parameters:**

- `metadata` (Json) = None
- `graph_id` (str | None) = None
- `limit` (int) = 10
- `offset` (int) = 0
- `sort_by` (AssistantSortBy | None) = None
- `sort_order` (SortOrder | None) = None
- `select` (list[AssistantSelectField] | None) = None
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** list[Assistant]

---

#### `set_latest()`

Change the version of an assistant.

Args:
    assistant_id: The assistant ID to delete.
    version: The version to change to.
    headers: Optional custom headers to include with the request.
    pa...

**Parameters:**

- `assistant_id` (str)
- `version` (int)
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** Assistant

---

#### `update()`

Update an assistant.

Use this to point to a different graph, update the configuration, or change the metadata of an assistant.

Args:
    assistant_id: Assistant to update.
    graph_id: The ID of th...

**Parameters:**

- `assistant_id` (str)
- `graph_id` (str | None) = None
- `config` (Config | None) = None
- `context` (Context | None) = None
- `metadata` (Json) = None
- `name` (str | None) = None
- `headers` (Mapping[str, str] | None) = None
- `description` (str | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** Assistant

---

## ThreadsClient

> Client for managing threads in LangGraph.

A thread maintains the state of a graph across multiple interactions/invocations (aka runs).
It accumulates and persists the graph's state, allowing for continuity between separate
invocations of the graph.

???+ example "Example"

    ```python
    client = get_client(url="http://localhost:2024"))
    new_thread = await client.threads.create(metadata={"user_id": "123"})
    ```

**메서드 개수:** 11개

| 메서드 | 파라미터 | 반환 타입 |
|--------|----------|----------|
| `copy()` | thread_id, headers, params | None |
| `count()` | metadata, values, status, headers, params | int |
| `create()` | metadata, thread_id, if_exists, supersteps, graph_id, headers, params | Thread |
| `delete()` | thread_id, headers, params | None |
| `get()` | thread_id, headers, params | Thread |
| `get_history()` | thread_id, limit, before, metadata, checkpoint, headers, params | list[ThreadState] |
| `get_state()` | thread_id, checkpoint, checkpoint_id, subgraphs, headers, params | ThreadState |
| `join_stream()` | thread_id, last_event_id, stream_mode, headers, params | AsyncIterator[StreamPart] |
| `search()` | metadata, values, status, limit, offset, sort_by, sort_order, select, headers, params | list[Thread] |
| `update()` | thread_id, metadata, headers, params | Thread |
| `update_state()` | thread_id, values, as_node, checkpoint, checkpoint_id, headers, params | ThreadUpdateStateResponse |

### 메서드 상세

#### `copy()`

Copy a thread.

Args:
    thread_id: The ID of the thread to copy.
    headers: Optional custom headers to include with the request.
    params: Optional query parameters to include with the request.
...

**Parameters:**

- `thread_id` (str)
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** None

---

#### `count()`

Count threads matching filters.

Args:
    metadata: Thread metadata to filter on.
    values: State values to filter on.
    status: Thread status to filter on.
    headers: Optional custom headers t...

**Parameters:**

- `metadata` (Json) = None
- `values` (Json) = None
- `status` (ThreadStatus | None) = None
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** int

---

#### `create()`

Create a new thread.

Args:
    metadata: Metadata to add to thread.
    thread_id: ID of thread.
        If None, ID will be a randomly generated UUID.
    if_exists: How to handle duplicate creation...

**Parameters:**

- `metadata` (Json) = None
- `thread_id` (str | None) = None
- `if_exists` (OnConflictBehavior | None) = None
- `supersteps` (Sequence[dict[str, Sequence[dict[str, Any]]]] | None) = None
- `graph_id` (str | None) = None
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** Thread

---

#### `delete()`

Delete a thread.

Args:
    thread_id: The ID of the thread to delete.
    headers: Optional custom headers to include with the request.
    params: Optional query parameters to include with the reque...

**Parameters:**

- `thread_id` (str)
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** None

---

#### `get()`

Get a thread by ID.

Args:
    thread_id: The ID of the thread to get.
    headers: Optional custom headers to include with the request.
    params: Optional query parameters to include with the reque...

**Parameters:**

- `thread_id` (str)
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** Thread

---

#### `get_history()`

Get the state history of a thread.

Args:
    thread_id: The ID of the thread to get the state history for.
    checkpoint: Return states for this subgraph. If empty defaults to root.
    limit: The m...

**Parameters:**

- `thread_id` (str)
- `limit` (int) = 10
- `before` (str | Checkpoint | None) = None
- `metadata` (Mapping[str, Any] | None) = None
- `checkpoint` (Checkpoint | None) = None
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** list[ThreadState]

---

#### `get_state()`

Get the state of a thread.

Args:
    thread_id: The ID of the thread to get the state of.
    checkpoint: The checkpoint to get the state of.
    checkpoint_id: (deprecated) The checkpoint ID to get ...

**Parameters:**

- `thread_id` (str)
- `checkpoint` (Checkpoint | None) = None
- `checkpoint_id` (str | None) = None
- `subgraphs` (bool) = False
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** ThreadState

---

#### `join_stream()`

Get a stream of events for a thread.

Args:
    thread_id: The ID of the thread to get the stream for.
    last_event_id: The ID of the last event to get.
    headers: Optional custom headers to inclu...

**Parameters:**

- `thread_id` (str)
- `last_event_id` (str | None) = None
- `stream_mode` (ThreadStreamMode | Sequence[ThreadStreamMode]) = run_modes
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** AsyncIterator[StreamPart]

---

#### `search()`

Search for threads.

Args:
    metadata: Thread metadata to filter on.
    values: State values to filter on.
    status: Thread status to filter on.
        Must be one of 'idle', 'busy', 'interrupte...

**Parameters:**

- `metadata` (Json) = None
- `values` (Json) = None
- `status` (ThreadStatus | None) = None
- `limit` (int) = 10
- `offset` (int) = 0
- `sort_by` (ThreadSortBy | None) = None
- `sort_order` (SortOrder | None) = None
- `select` (list[ThreadSelectField] | None) = None
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** list[Thread]

---

#### `update()`

Update a thread.

Args:
    thread_id: ID of thread to update.
    metadata: Metadata to merge with existing thread metadata.
    headers: Optional custom headers to include with the request.
    para...

**Parameters:**

- `thread_id` (str)
- `metadata` (Mapping[str, Any])
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** Thread

---

#### `update_state()`

Update the state of a thread.

Args:
    thread_id: The ID of the thread to update.
    values: The values to update the state with.
    as_node: Update the state as if this node had just executed.
  ...

**Parameters:**

- `thread_id` (str)
- `values` (dict[str, Any] | Sequence[dict] | None)
- `as_node` (str | None) = None
- `checkpoint` (Checkpoint | None) = None
- `checkpoint_id` (str | None) = None
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** ThreadUpdateStateResponse

---

## RunsClient

> Client for managing runs in LangGraph.

A run is a single assistant invocation with optional input, config, context, and metadata.
This client manages runs, which can be stateful (on threads) or stateless.

???+ example "Example"

    ```python
    client = get_client(url="http://localhost:2024")
    run = await client.runs.create(assistant_id="asst_123", thread_id="thread_456", input={"query": "Hello"})
    ```

**메서드 개수:** 10개

| 메서드 | 파라미터 | 반환 타입 |
|--------|----------|----------|
| `cancel()` | thread_id, run_id, wait, action, headers, params | None |
| `create()` | thread_id, assistant_id, input, command, stream_mode, stream_subgraphs, stream_resumable, metadata, config, context, checkpoint, checkpoint_id, checkpoint_during, interrupt_before, interrupt_after, webhook, multitask_strategy, if_not_exists, on_completion, after_seconds, headers, params, on_run_created, durability | Run |
| `create_batch()` | payloads, headers, params | list[Run] |
| `delete()` | thread_id, run_id, headers, params | None |
| `get()` | thread_id, run_id, headers, params | Run |
| `join()` | thread_id, run_id, headers, params | dict |
| `join_stream()` | thread_id, run_id, cancel_on_disconnect, stream_mode, headers, params, last_event_id | AsyncIterator[StreamPart] |
| `list()` | thread_id, limit, offset, status, select, headers, params | list[Run] |
| `stream()` | thread_id, assistant_id, input, command, stream_mode, stream_subgraphs, stream_resumable, metadata, config, context, checkpoint, checkpoint_id, checkpoint_during, interrupt_before, interrupt_after, feedback_keys, on_disconnect, on_completion, webhook, multitask_strategy, if_not_exists, after_seconds, headers, params, on_run_created, durability | AsyncIterator[StreamPart] |
| `wait()` | thread_id, assistant_id, input, command, metadata, config, context, checkpoint, checkpoint_id, checkpoint_during, interrupt_before, interrupt_after, webhook, on_disconnect, on_completion, multitask_strategy, if_not_exists, after_seconds, raise_error, headers, params, on_run_created, durability | list[dict] | dict[str, Any] |

### 메서드 상세

#### `cancel()`

Get a run.

Args:
    thread_id: The thread ID to cancel.
    run_id: The run ID to cancel.
    wait: Whether to wait until run has completed.
    action: Action to take when cancelling the run. Possi...

**Parameters:**

- `thread_id` (str)
- `run_id` (str)
- `wait` (bool) = False
- `action` (CancelAction) = interrupt
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** None

---

#### `create()`

Create a background run.

Args:
    thread_id: the thread ID to assign to the thread.
        If None will create a stateless run.
    assistant_id: The assistant ID or graph name to stream from.
    ...

**Parameters:**

- `thread_id` (str | None)
- `assistant_id` (str)
- `input` (Mapping[str, Any] | None) = None
- `command` (Command | None) = None
- `stream_mode` (StreamMode | Sequence[StreamMode]) = values
- `stream_subgraphs` (bool) = False
- `stream_resumable` (bool) = False
- `metadata` (Mapping[str, Any] | None) = None
- `config` (Config | None) = None
- `context` (Context | None) = None
- `checkpoint` (Checkpoint | None) = None
- `checkpoint_id` (str | None) = None
- `checkpoint_during` (bool | None) = None
- `interrupt_before` (All | Sequence[str] | None) = None
- `interrupt_after` (All | Sequence[str] | None) = None
- `webhook` (str | None) = None
- `multitask_strategy` (MultitaskStrategy | None) = None
- `if_not_exists` (IfNotExists | None) = None
- `on_completion` (OnCompletionBehavior | None) = None
- `after_seconds` (int | None) = None
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None
- `on_run_created` (Callable[[RunCreateMetadata], None] | None) = None
- `durability` (Durability | None) = None

**Returns:** Run

---

#### `create_batch()`

Create a batch of stateless background runs.

**Parameters:**

- `payloads` (list[RunCreate])
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** list[Run]

---

#### `delete()`

Delete a run.

Args:
    thread_id: The thread ID to delete.
    run_id: The run ID to delete.
    headers: Optional custom headers to include with the request.
    params: Optional query parameters t...

**Parameters:**

- `thread_id` (str)
- `run_id` (str)
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** None

---

#### `get()`

Get a run.

Args:
    thread_id: The thread ID to get.
    run_id: The run ID to get.
    headers: Optional custom headers to include with the request.
    params: Optional query parameters to include...

**Parameters:**

- `thread_id` (str)
- `run_id` (str)
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** Run

---

#### `join()`

Block until a run is done. Returns the final state of the thread.

Args:
    thread_id: The thread ID to join.
    run_id: The run ID to join.
    headers: Optional custom headers to include with the ...

**Parameters:**

- `thread_id` (str)
- `run_id` (str)
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** dict

---

#### `join_stream()`

Stream output from a run in real-time, until the run is done.
Output is not buffered, so any output produced before this call will
not be received here.

Args:
    thread_id: The thread ID to join.
  ...

**Parameters:**

- `thread_id` (str)
- `run_id` (str)
- `cancel_on_disconnect` (bool) = False
- `stream_mode` (StreamMode | Sequence[StreamMode] | None) = None
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None
- `last_event_id` (str | None) = None

**Returns:** AsyncIterator[StreamPart]

---

#### `list()`

List runs.

Args:
    thread_id: The thread ID to list runs for.
    limit: The maximum number of results to return.
    offset: The number of results to skip.
    status: The status of the run to fil...

**Parameters:**

- `thread_id` (str)
- `limit` (int) = 10
- `offset` (int) = 0
- `status` (RunStatus | None) = None
- `select` (list[RunSelectField] | None) = None
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** list[Run]

---

#### `stream()`

Create a run and stream the results.

Args:
    thread_id: the thread ID to assign to the thread.
        If None will create a stateless run.
    assistant_id: The assistant ID or graph name to strea...

**Parameters:**

- `thread_id` (str | None)
- `assistant_id` (str)
- `input` (Mapping[str, Any] | None) = None
- `command` (Command | None) = None
- `stream_mode` (StreamMode | Sequence[StreamMode]) = values
- `stream_subgraphs` (bool) = False
- `stream_resumable` (bool) = False
- `metadata` (Mapping[str, Any] | None) = None
- `config` (Config | None) = None
- `context` (Context | None) = None
- `checkpoint` (Checkpoint | None) = None
- `checkpoint_id` (str | None) = None
- `checkpoint_during` (bool | None) = None
- `interrupt_before` (All | Sequence[str] | None) = None
- `interrupt_after` (All | Sequence[str] | None) = None
- `feedback_keys` (Sequence[str] | None) = None
- `on_disconnect` (DisconnectMode | None) = None
- `on_completion` (OnCompletionBehavior | None) = None
- `webhook` (str | None) = None
- `multitask_strategy` (MultitaskStrategy | None) = None
- `if_not_exists` (IfNotExists | None) = None
- `after_seconds` (int | None) = None
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None
- `on_run_created` (Callable[[RunCreateMetadata], None] | None) = None
- `durability` (Durability | None) = None

**Returns:** AsyncIterator[StreamPart]

---

#### `wait()`

Create a run, wait until it finishes and return the final state.

Args:
    thread_id: the thread ID to create the run on.
        If None will create a stateless run.
    assistant_id: The assistant ...

**Parameters:**

- `thread_id` (str | None)
- `assistant_id` (str)
- `input` (Mapping[str, Any] | None) = None
- `command` (Command | None) = None
- `metadata` (Mapping[str, Any] | None) = None
- `config` (Config | None) = None
- `context` (Context | None) = None
- `checkpoint` (Checkpoint | None) = None
- `checkpoint_id` (str | None) = None
- `checkpoint_during` (bool | None) = None
- `interrupt_before` (All | Sequence[str] | None) = None
- `interrupt_after` (All | Sequence[str] | None) = None
- `webhook` (str | None) = None
- `on_disconnect` (DisconnectMode | None) = None
- `on_completion` (OnCompletionBehavior | None) = None
- `multitask_strategy` (MultitaskStrategy | None) = None
- `if_not_exists` (IfNotExists | None) = None
- `after_seconds` (int | None) = None
- `raise_error` (bool) = True
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None
- `on_run_created` (Callable[[RunCreateMetadata], None] | None) = None
- `durability` (Durability | None) = None

**Returns:** list[dict] | dict[str, Any]

---

## StoreClient

> Client for interacting with the graph's shared storage.

The Store provides a key-value storage system for persisting data across graph executions,
allowing for stateful operations and data sharing across threads.

???+ example "Example"

    ```python
    client = get_client(url="http://localhost:2024")
    await client.store.put_item(["users", "user123"], "mem-123451342", {"name": "Alice", "score": 100})
    ```

**메서드 개수:** 5개

| 메서드 | 파라미터 | 반환 타입 |
|--------|----------|----------|
| `delete_item()` | namespace, key, headers, params | None |
| `get_item()` | namespace, key, refresh_ttl, headers, params | Item |
| `list_namespaces()` | prefix, suffix, max_depth, limit, offset, headers, params | ListNamespaceResponse |
| `put_item()` | namespace, key, value, index, ttl, headers, params | None |
| `search_items()` | namespace_prefix, filter, limit, offset, query, refresh_ttl, headers, params | SearchItemsResponse |

### 메서드 상세

#### `delete_item()`

Delete an item.

Args:
    key: The unique identifier for the item.
    namespace: Optional list of strings representing the namespace path.
    headers: Optional custom headers to include with the re...

**Parameters:**

- `namespace` (Sequence[str])
- `key` (str)
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** None

---

#### `get_item()`

Retrieve a single item.

Args:
    key: The unique identifier for the item.
    namespace: Optional list of strings representing the namespace path.
    refresh_ttl: Whether to refresh the TTL on this...

**Parameters:**

- `namespace` (Sequence[str])
- `key` (str)
- `refresh_ttl` (bool | None) = None
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** Item

---

#### `list_namespaces()`

List namespaces with optional match conditions.

Args:
    prefix: Optional list of strings representing the prefix to filter namespaces.
    suffix: Optional list of strings representing the suffix t...

**Parameters:**

- `prefix` (list[str] | None) = None
- `suffix` (list[str] | None) = None
- `max_depth` (int | None) = None
- `limit` (int) = 100
- `offset` (int) = 0
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** ListNamespaceResponse

---

#### `put_item()`

Store or update an item.

Args:
    namespace: A list of strings representing the namespace path.
    key: The unique identifier for the item within the namespace.
    value: A dictionary containing t...

**Parameters:**

- `namespace` (Sequence[str])
- `key` (str)
- `value` (Mapping[str, Any])
- `index` (Literal[False] | list[str] | None) = None
- `ttl` (int | None) = None
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** None

---

#### `search_items()`

Search for items within a namespace prefix.

Args:
    namespace_prefix: List of strings representing the namespace prefix.
    filter: Optional dictionary of key-value pairs to filter results.
    li...

**Parameters:**

- `namespace_prefix` (Sequence[str])
- `filter` (Mapping[str, Any] | None) = None
- `limit` (int) = 10
- `offset` (int) = 0
- `query` (str | None) = None
- `refresh_ttl` (bool | None) = None
- `headers` (Mapping[str, str] | None) = None
- `params` (QueryParamTypes | None) = None

**Returns:** SearchItemsResponse

---

