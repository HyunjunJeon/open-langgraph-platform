# Open LangGraph Architecture Guide

## Table of Contents

1. [System Overview](#system-overview)
2. [Architectural Principles](#architectural-principles)
3. [Core Layers](#core-layers)
4. [Database Architecture](#database-architecture)
5. [Core Components](#core-components)
6. [Data Flow](#data-flow)
7. [Authentication System](#authentication-system)
8. [Graph Execution Model](#graph-execution-model)
9. [Streaming Architecture](#streaming-architecture)
10. [Lifecycle Management](#lifecycle-management)

---

## System Overview

Open LangGraph is an **Agent Protocol server** that adopts an architecture of wrapping the **official LangGraph packages** with an HTTP API.

### Core Design Philosophy

```bash
┌─────────────────────────────────────────────────────┐
│                  Agent Protocol                      │
│              (Standard HTTP API Interface)           │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│                 FastAPI Layer                        │
│      (Routing, Authentication, Streaming, Metadata)  │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│               LangGraph Core                         │
│   (State Management, Graph Execution, Checkpoints, Memory) │
└──────────────────────────────────────────────────────┘
```

**Core Principle**: LangGraph is responsible for **all** state persistence and graph execution, while the FastAPI layer **only** provides Agent Protocol compliance.

---

## Architectural Principles

### 1. Separation of Concerns

| Layer | Responsibility | Technologies Used |
|--------|------|----------|
| **API Layer** | HTTP Routing, Authentication, SSE Streaming | FastAPI, LangGraph SDK Auth |
| **Service Layer** | Business Logic, Event Conversion, Broker Management | Python Service Classes |
| **Core Layer** | Database Connection, LangGraph Integration | SQLAlchemy, LangGraph |
| **LangGraph** | Graph Execution, State Persistence, Memory | LangGraph Checkpoint/Store |

### 2. Dual Database Strategy

Open LangGraph uses a **hybrid database architecture**:

- **LangGraph manages state**: Conversation checkpoints, state history, long-term memory
- **SQLAlchemy manages metadata**: Only Agent Protocol metadata (minimal tables)

```
PostgreSQL
├── LangGraph Tables (created by AsyncPostgresSaver/Store)
│   ├── checkpoints: State snapshots
│   ├── checkpoint_writes: State change history
│   └── store: Key-value long-term memory
│
└── Agent Protocol Tables (managed by Alembic migrations)
    ├── assistants: Graph metadata
    ├── threads: Conversation thread metadata
    ├── runs: Execution metadata
    └── run_events: SSE event persistence
```

### 3. Singleton Pattern

Global singleton instances maintain resource sharing and consistency:

```python
# Database Manager
db_manager = DatabaseManager()

# Service Instances
langgraph_service = LangGraphService()
streaming_service = StreamingService()
event_store = EventStore()
broker_manager = BrokerManager()
```

---

## Core Layers

### API Layer (`src/agent_server/api/`)

**Endpoint Structure**:

```python
# src/agent_server/main.py
app.include_router(health_router)        # /health
app.include_router(assistants_router)    # /assistants
app.include_router(threads_router)       # /threads
app.include_router(runs_router)          # /threads/{thread_id}/runs
app.include_router(store_router)         # /store
```

**Middleware Stack (Processing Order)**:

```
┌────────────────────────────────────┐
│    1. CORS Middleware              │  ← Handles cross-origin requests
├────────────────────────────────────┤
│    2. DoubleEncodedJSON            │  ← Handles front-end double encoding
├────────────────────────────────────┤
│    3. Authentication Middleware    │  ← LangGraph SDK-based authentication
├────────────────────────────────────┤
│    4. Router (API Endpoints)       │  ← Routing and handlers
└────────────────────────────────────┘
```

### Service Layer (`src/agent_server/services/`)

Each service has a clear responsibility:

| Service | File | Responsibility |
|--------|------|------|
| **LangGraphService** | `langgraph_service.py` | Graph loading, caching, configuration management, default assistant creation |
| **StreamingService** | `streaming_service.py` | SSE streaming orchestration, event distribution |
| **EventStore** | `event_store.py` | Event persistence, replay on reconnect, automatic cleanup |
| **BrokerManager** | `broker.py` | Per-execution event queue management, Producer-Consumer pattern |
| **EventConverter** | `event_converter.py` | LangGraph → Agent Protocol event conversion |
| **ThreadStateService** | `thread_state_service.py` | Thread state retrieval, checkpoint history |

### Core Layer (`src/agent_server/core/`)

The foundational components of the system:

```python
# Database Management
database.py          # DatabaseManager: SQLAlchemy + LangGraph integration
orm.py               # SQLAlchemy model definitions (Agent Protocol metadata)

# Authentication
auth_middleware.py   # LangGraph SDK Auth middleware
auth_deps.py         # Authentication helpers for FastAPI dependency injection
auth_ctx.py          # User context injection decorator

# SSE Streaming
sse.py               # SSE event creation utilities

# Serialization
serializers.py       # LangGraph object JSON serialization
```

---

## Database Architecture

### DatabaseManager Pattern

`DatabaseManager` oversees database connections and LangGraph persistence components in Open LangGraph.

```python
class DatabaseManager:
    """Manages database connections and LangGraph persistence components"""

    def __init__(self):
        self.engine: AsyncEngine | None = None           # SQLAlchemy
        self._checkpointer: AsyncPostgresSaver | None    # LangGraph
        self._store: AsyncPostgresStore | None           # LangGraph
```

**Key Features**:

1. **Automatic URL Format Conversion**
   ```python
   # SQLAlchemy uses the asyncpg driver
   DATABASE_URL = "postgresql+asyncpg://user:pass@host/db"

   # LangGraph uses the psycopg driver
   langgraph_dsn = DATABASE_URL.replace(
       "postgresql+asyncpg://",
       "postgresql://"
   )
   ```

2. **Context Manager-based Resource Management**
   ```python
   async def get_checkpointer(self) -> AsyncPostgresSaver:
       if self._checkpointer is None:
           # Enter context manager and cache
           self._checkpointer_cm = AsyncPostgresSaver.from_conn_string(
               self._langgraph_dsn
           )
           self._checkpointer = await self._checkpointer_cm.__aenter__()
           await self._checkpointer.setup()  # Create tables (idempotent)
       return self._checkpointer
   ```

3. **Global Access via Singleton Pattern**
   ```python
   # Global instance
   db_manager = DatabaseManager()

   # Used throughout the application
   engine = db_manager.get_engine()
   checkpointer = await db_manager.get_checkpointer()
   store = await db_manager.get_store()
   ```

### Database Schema Management

**Alembic-based Migrations**:

```bash
# Apply migrations
python3 scripts/migrate.py upgrade

# Create a new migration
python3 scripts/migrate.py revision --autogenerate -m "description"

# Check status
python3 scripts/migrate.py current
```

**Migration File Structure**:

```
alembic/
├── versions/           # Migration files
│   ├── 001_initial.py
│   ├── 002_add_events.py
│   └── ...
├── env.py             # Alembic environment configuration (async support)
└── script.py.mako     # Template
```

---

## Core Components

### 1. DatabaseManager (`core/database.py`)

**Role**: Manages database connections and the lifecycle of LangGraph components.

```python
class DatabaseManager:
    async def initialize(self) -> None:
        """Called on FastAPI startup (lifespan)"""
        # Create SQLAlchemy engine
        self.engine = create_async_engine(self._database_url)

        # Prepare LangGraph DSN (URL conversion)
        self._langgraph_dsn = self._database_url.replace(
            "postgresql+asyncpg://",
            "postgresql://"
        )

    async def get_checkpointer(self) -> AsyncPostgresSaver:
        """Returns the LangGraph checkpointer (cached)"""
        # On first call, enter context manager and cache
        # Subsequent calls reuse the cached instance

    async def get_store(self) -> AsyncPostgresStore:
        """Returns the LangGraph Store (cached)"""
        # Long-term memory and key-value store
```

**Reason for Caching**:
- LangGraph needs the actual saver/store object (method calls)
- Returning a context manager wrapper would fail
- Improves performance by reusing the connection pool

### 2. LangGraphService (`services/langgraph_service.py`)

**Role**: Manages graph loading, caching, and configuration.

```python
class LangGraphService:
    """Manages the graph registry and execution settings"""

    async def initialize(self):
        """Loads open_langgraph.json and creates default assistants"""
        # 1. Find configuration file (applies priority)
        # 2. Initialize graph registry
        # 3. Create default assistant for each graph

    async def get_graph(self, graph_id: str):
        """Loads and compiles a graph (cached)"""
        # 1. Check cache
        # 2. If not present, dynamically import module
        # 3. Compile with Postgres checkpointer
        # 4. Store in cache and return
```

**Graph Registration Flow**:

```
open_langgraph.json
{
  "graphs": {
    "agent": "./graphs/react_agent/graph.py:graph"
  }
}
         ↓
LangGraphService.initialize()
         ↓
Create default assistant (deterministic UUID)
         ↓
uuid5(NAMESPACE, "agent")
         ↓
Save to DB (assistants table)
```

**Configuration Helper Functions**:

```python
def inject_user_context(config: dict, user: User) -> dict:
    """Injects user context into the LangGraph config"""
    config["configurable"]["user_id"] = user.identity
    config["configurable"]["user_data"] = user.metadata

def create_thread_config(thread_id: str, user: User) -> dict:
    """Creates per-thread execution settings"""
    return {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "",
            "checkpoint_id": "",
        }
    }

def create_run_config(run_id: str, thread_id: str, user: User) -> dict:
    """Creates per-run settings (including observability callbacks)"""
    config = create_thread_config(thread_id, user)

    # Langfuse observability integration
    if LANGFUSE_LOGGING:
        config["callbacks"] = get_tracing_callbacks(run_id, thread_id, user)

    return config
```

### 3. StreamingService (`services/streaming_service.py`)

**Role**: Orchestrates SSE streaming and event distribution.

```python
class StreamingService:
    """Overall service for SSE streaming"""

    async def stream_run_execution(
        self,
        run: Run,
        last_event_id: str | None = None
    ) -> AsyncIterator[str]:
        """Streams execution events as SSE (supports reconnection)"""

        # 1. Replay past events on reconnect
        if last_event_id:
            async for event in self._replay_events(run.run_id, last_event_id):
                yield event

        # 2. Receive real-time events from the broker
        broker = broker_manager.get_or_create_broker(run.run_id)
        async for event_id, payload in broker.aiter():
            # 3. Convert LangGraph → Agent Protocol
            sse_event = self.event_converter.convert(payload)

            # 4. Send to client
            yield sse_event.to_string()
```

**Event Conversion Flow**:

```
LangGraph Event
{"event": "on_chain_start", "data": {...}}
         ↓
EventConverter.convert()
         ↓
Agent Protocol SSE
event: thread.run.step.created
data: {"type": "message_creation", ...}
```

### 4. EventStore (`services/event_store.py`)

**Role**: PostgreSQL-based event persistence and replay.

```python
class EventStore:
    """SSE Event Store"""

    async def store_event(
        self,
        run_id: str,
        event_id: str,
        event: str,
        data: Any
    ):
        """Stores an event in the run_events table"""
        # Extract sequence number (e.g., "run_123_event_42" → 42)
        seq = extract_event_sequence(event_id)

        # Save as PostgreSQL JSONB
        await engine.execute(
            text("INSERT INTO run_events (run_id, seq, event, data) ...")
        )

    async def get_events_since(
        self,
        run_id: str,
        last_event_id: str
    ) -> list[SSEEvent]:
        """Retrieves events since a specific point in time (reconnection)"""
        last_seq = extract_event_sequence(last_event_id)

        # Query by sequence number
        result = await engine.execute(
            text("SELECT * FROM run_events WHERE run_id = :run_id AND seq > :seq ORDER BY seq")
        )
        return [SSEEvent(...) for row in result]
```

**Automatic Cleanup Task**:

```python
async def _cleanup_loop(self):
    """Background cleanup loop (every 5 minutes)"""
    while True:
        await asyncio.sleep(300)

        # Delete events older than 1 hour
        await engine.execute(
            text("DELETE FROM run_events WHERE created_at < NOW() - INTERVAL '1 hour'")
        )
```

### 5. BrokerManager (`services/broker.py`)

**Role**: Manages per-execution event queues (Producer-Consumer pattern).

```python
class RunBroker:
    """Event broker for a single execution"""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.queue: asyncio.Queue = asyncio.Queue()
        self.finished = asyncio.Event()

    async def put(self, event_id: str, payload: Any):
        """Producer: Adds an event to the queue"""
        await self.queue.put((event_id, payload))

        # Mark broker as finished on "end" event
        if payload[0] == "end":
            self.mark_finished()

    async def aiter(self) -> AsyncIterator[tuple[str, Any]]:
        """Consumer: Iterates over events"""
        while True:
            try:
                event_id, payload = await asyncio.wait_for(
                    self.queue.get(), timeout=0.1
                )
                yield event_id, payload

                # Terminate on "end" event
                if payload[0] == "end":
                    break
            except asyncio.TimeoutError:
                if self.finished.is_set():
                    break

class BrokerManager:
    """Manages multiple RunBroker instances"""

    def get_or_create_broker(self, run_id: str) -> RunBroker:
        """Retrieves/creates a broker by execution ID"""
        if run_id not in self._brokers:
            self._brokers[run_id] = RunBroker(run_id)
        return self._brokers[run_id]
```

---

## Data Flow

### Execution Creation → Background Processing → SSE Streaming

**Overall Flowchart**:

```
1. HTTP POST /threads/{thread_id}/runs/stream
         ↓
2. create_run_streaming(run_create)
         ↓
3. Create Run ORM (save to DB)
         ↓
4. asyncio.create_task(execute_run_async)  ← Background execution
         ↓                                     ↓
5. StreamingResponse                    6. graph.astream(...)
         ↓                                     ↓
7. streaming_service.stream_run_execution()   Generate LangGraph events
         ↓                                     ↓
8. broker.aiter()  ←────────────────────  broker.put(event)
         ↓                                     ↓
9. EventConverter                         event_store.store_event()
         ↓
10. SSE → Client
```

**Background Execution Details (`execute_run_async`)**:

```python
async def execute_run_async(
    run: Run,
    input_data: dict,
    stream_modes: list[str],
    user: User
):
    """Executes a graph in the background (Producer role)"""

    # 1. Load graph
    graph = await langgraph_service.get_graph(run.assistant_id)

    # 2. Create execution config (with user context)
    config = create_run_config(run.run_id, run.thread_id, user)

    # 3. Create broker
    broker = broker_manager.get_or_create_broker(run.run_id)

    # 4. Execute LangGraph streaming
    async for raw_event in graph.astream(
        input_data,
        config=config,
        stream_mode=stream_modes
    ):
        # 5. Generate event ID
        event_id = generate_event_id(run.run_id, seq)

        # 6. Send to broker (received by Consumer)
        await broker.put(event_id, raw_event)

        # 7. Persist to event store (for reconnection)
        await store_sse_event(run.run_id, event_id, raw_event)

    # 8. Handle run completion
    await update_run_status(run.run_id, "success")
```

### Checkpoint Saving → State Restoration

**Checkpoint Lifecycle**:

```
Node completes during graph execution
         ↓
AsyncPostgresSaver.aput()
         ↓
Saved to checkpoints table
{
  thread_id: "thread_123",
  checkpoint_ns: "",
  checkpoint_id: "1ef...",
  channel_values: {...},  ← Current state
  channel_versions: {...}
}
         ↓
Automatic restoration on subsequent execution
         ↓
graph.astream(..., config={"configurable": {"thread_id": "thread_123"}})
         ↓
AsyncPostgresSaver.aget()
         ↓
Load the last checkpoint
```

**State Retrieval API**:

```python
# GET /threads/{thread_id}/state
async def get_thread_state(thread_id: str):
    checkpointer = await db_manager.get_checkpointer()

    # Retrieve the latest checkpoint
    config = {"configurable": {"thread_id": thread_id}}
    state = await checkpointer.aget(config)

    return {
        "values": state["channel_values"],
        "next": state.get("next", []),
        "checkpoint": state["checkpoint"]
    }
```

### Interrupt → Approve → Resume

**Human-in-the-Loop (HITL) Flow**:

```
1. `interrupt()` is called in a graph node
         ↓
2. LangGraph saves a checkpoint and stops
         ↓
3. "end" event is emitted (status="requires_action")
         ↓
4. Client decides to approve or reject
         ↓
5. PATCH /threads/{thread_id}/runs/{run_id}
   {
     "command": {
       "resume": "approved",  ← or "rejected"
       "goto": ["next_node"]
     }
   }
         ↓
6. graph.astream(..., input=Command(...))
         ↓
7. State is restored from checkpoint and execution resumes
```

**Interrupt Implementation Example**:

```python
# graphs/react_agent_hitl/graph.py
def approval_node(state: State, runtime: Runtime[Context]):
    """Node that requires human approval"""

    # Create approval request
    approval_request = {
        "type": "approval_required",
        "action": state["planned_action"],
        "reason": "This action requires human approval"
    }

    # Interrupt execution (saves checkpoint)
    interrupt(approval_request)

    # Execution continues from this point on resume
    if state.get("approved"):
        return {"status": "approved"}
    else:
        return {"status": "rejected"}
```

---

## Authentication System

### LangGraph SDK Auth Integration

Open LangGraph uses **LangGraph SDK Auth** to handle authentication and authorization.

**Authentication Flow**:

```
1. HTTP Request
   Authorization: Bearer <token>
         ↓
2. AuthenticationMiddleware (Starlette)
         ↓
3. get_auth_backend()
         ↓
4. `@auth.authenticate` call (auth.py)
         ↓
5. Returns MinimalUserDict
   {
     "identity": "user_123",
     "display_name": "John Doe",
     "email": "john@example.com",
     "permissions": ["admin"],
     "org_id": "org_456",
     "is_authenticated": True
   }
         ↓
6. Stored in `request.user`
         ↓
7. FastAPI router handler
   `user = get_current_user(request)`
```

### Authentication Types

**Switch based on environment variables**:

```bash
# .env
AUTH_TYPE=noop    # No authentication (for development)
AUTH_TYPE=custom  # Custom authentication (for production)
```

**No-op Authentication** (`AUTH_TYPE=noop`):

```python
# auth.py
@auth.authenticate
async def authenticate(headers: dict[str, str]) -> MinimalUserDict:
    """Allows all requests"""
    return {
        "identity": "anonymous",
        "display_name": "Anonymous User",
        "is_authenticated": True,
    }

@auth.on
async def authorize(ctx: AuthContext, value: dict) -> dict:
    """Allows access to all resources"""
    return {}  # Empty filter = no access restrictions
```

**Custom Authentication** (`AUTH_TYPE=custom`):

```python
# auth.py
@auth.authenticate
async def authenticate(headers: dict[str, str]) -> MinimalUserDict:
    """Custom authentication logic (Firebase, JWT, etc.)"""
    authorization = headers.get("authorization")

    if not authorization:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="Authorization header required"
        )

    # Token validation logic
    if authorization == "Bearer dev-token":
        return {
            "identity": "dev-user",
            "display_name": "Development User",
            "email": "dev@example.com",
            "permissions": ["admin"],
            "org_id": "dev-org",
            "is_authenticated": True,
        }

    # Integrate with a real authentication service
    # user = await verify_token(authorization)
    # return user_to_minimal_dict(user)

    raise Auth.exceptions.HTTPException(
        status_code=401,
        detail="Invalid authentication token"
    )
```

### Authorization

**Resource-specific access control**:

```python
# auth.py
@auth.on
async def authorize(ctx: AuthContext, value: dict) -> dict:
    """Filters resources by user"""

    # Context information
    # ctx.resource: "assistants", "threads", "runs", "store"
    # ctx.action: "create", "read", "update", "delete", "search"
    # ctx.user: MinimalUserDict

    # Admins can access all resources
    if "admin" in ctx.user.get("permissions", []):
        return {}  # No filtering

    # Regular users can only access resources with their org_id
    return {
        "user_id": ctx.user["identity"],
        "org_id": ctx.user.get("org_id")
    }
```

**Applying the Filter**:

```python
# api/threads.py
async def list_threads(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Lists threads (filtered by user)"""

    # Create authorization context
    auth_filter = await authorize(
        AuthContext(resource="threads", action="search", user=user),
        value={}
    )

    # Dynamically create WHERE clause
    query = select(ThreadORM)
    if "user_id" in auth_filter:
        query = query.where(ThreadORM.user_id == auth_filter["user_id"])

    result = await session.execute(query)
    return result.scalars().all()
```

### Multi-tenancy Isolation

**Injecting User Context**:

```python
# services/langgraph_service.py
def inject_user_context(config: dict, user: User) -> dict:
    """Injects user information into the LangGraph config"""
    config["configurable"]["user_id"] = user.identity
    config["configurable"]["user_data"] = {
        "email": user.email,
        "org_id": user.metadata.get("org_id"),
        "permissions": user.metadata.get("permissions", [])
    }
    return config

# Automatically injected on execution
config = create_run_config(run_id, thread_id, user)
# config["configurable"]["user_id"] = "user_123"
# config["configurable"]["user_data"] = {...}
```

**Accessing User Information in a Graph**:

```python
# graphs/my_agent/graph.py
def my_node(state: State, runtime: Runtime[Context]):
    """Using user information in a node"""

    # Extract user info from Runtime[Context]
    user_id = runtime.context.user_id
    org_id = runtime.context.user_data.get("org_id")

    # Branch logic based on user
    if org_id == "premium_org":
        return handle_premium_request(state)
    else:
        return handle_basic_request(state)
```

---

## Graph Execution Model

### StateGraph Pattern

LangGraph uses **StateGraph** to define agents.

**Basic Structure**:

```python
# graphs/my_agent/graph.py
from langgraph.graph import StateGraph, MessagesState, START, END

# 1. Define state
class MyState(MessagesState):
    query: str
    result: str | None
    step_count: int

# 2. Define node functions
def process_node(state: MyState):
    """Node that processes the state"""
    return {
        "result": f"Processed: {state['query']}",
        "step_count": state.get("step_count", 0) + 1
    }

def decision_node(state: MyState):
    """Node for branching decisions"""
    if state.get("step_count", 0) > 5:
        return "end"
    else:
        return "process"

# 3. Configure the graph
workflow = StateGraph(MyState)

# Add nodes
workflow.add_node("process", process_node)
workflow.add_node("decision", decision_node)

# Add edges
workflow.add_edge(START, "process")
workflow.add_edge("process", "decision")
workflow.add_conditional_edges(
    "decision",
    lambda x: x,  # Use the return value of decision_node
    {
        "process": "process",  # Back to process
        "end": END             # End
    }
)

# 4. Compile and export the graph
graph = workflow.compile()  # Must be exported as 'graph'
```

**Registering in `open_langgraph.json`**:

```json
{
  "graphs": {
    "my_agent": "./graphs/my_agent/graph.py:graph"
  }
}
```

### Runtime[Context] Pattern

Graph nodes can access user authentication information and settings via `Runtime[Context]`.

**Defining the Context Class**:

```python
# graphs/my_agent/graph.py
from langgraph.types import Runtime
from dataclasses import dataclass

@dataclass
class Context:
    """Graph execution context"""
    user_id: str
    user_data: dict
    model: str = "gpt-4"
    temperature: float = 0.7

def my_node(state: MyState, runtime: Runtime[Context]):
    """Accessing context via Runtime"""

    # User information
    user_id = runtime.context.user_id
    org_id = runtime.context.user_data.get("org_id")

    # Model settings
    model = runtime.context.model
    temperature = runtime.context.temperature

    # Apply user-specific settings when calling LLM
    response = llm.invoke(
        state["messages"],
        model=model,
        temperature=temperature,
        user=user_id  # User tracking
    )

    return {"messages": [response]}
```

**Context Injection**:

```python
# Automatically injected on execution
config = create_run_config(run_id, thread_id, user)
config["configurable"]["user_id"] = user.identity
config["configurable"]["user_data"] = {...}

# LangGraph automatically converts to Runtime[Context]
await graph.ainvoke(input_data, config=config)
```

### Human-in-the-Loop (HITL) Pattern

**Implementing Interrupts**:

```python
# graphs/react_agent_hitl/graph.py
from langgraph.types import interrupt

def approval_node(state: State, runtime: Runtime[Context]):
    """Node for requesting human approval"""

    # 1. Create approval request data
    approval_data = {
        "type": "tool_approval",
        "tool_name": state["tool_name"],
        "tool_input": state["tool_input"],
        "reason": "This tool requires human approval before execution"
    }

    # 2. Interrupt execution (saves checkpoint)
    result = interrupt(approval_data)

    # 3. On resume, `result` contains user input
    # PATCH /runs/{run_id} {"command": {"resume": "approved"}}

    if result == "approved":
        return {"approved": True, "status": "executing"}
    else:
        return {"approved": False, "status": "cancelled"}

# Branch with conditional edges
workflow.add_conditional_edges(
    "approval",
    lambda state: "execute" if state["approved"] else "cancel",
    {
        "execute": "execute_tool",
```
