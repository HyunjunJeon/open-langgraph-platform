# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Project: Open LangGraph — Open Source LangGraph Backend (Agent Protocol Server)

## Development Commands

### Environment Setup

```bash
# Install dependencies
uv install

# Activate virtual environment (IMPORTANT for migrations)
source .venv/bin/activate

# Start database
docker compose up postgres -d

# Apply migrations
python3 scripts/migrate.py upgrade
```

### Running the Application

#### **Option 1: Docker (Recommended for beginners)**

```bash
# Start everything (database + migrations + server)
docker compose up open-langgraph
```

#### **Option 2: Local Development (Recommended for advanced users)**

```bash
# Start development server with auto-reload
uv run uvicorn src.agent_server.main:app --reload

# Start with specific host/port
uv run uvicorn src.agent_server.main:app --host 0.0.0.0 --port 8000 --reload

# Alternative: Use the run_server.py script
python3 run_server.py  # or: make run

# Start development database
docker compose up postgres -d
```

### Testing

```bash
# Run all tests
uv run pytest
# or: make test

# Run specific test file
uv run pytest tests/test_api/test_assistants.py

# Run tests with async support
uv run pytest -v --asyncio-mode=auto

# Run with coverage
uv run pytest --cov=src --cov-report=html
# or: make test-cov

# Run end-to-end tests only
uv run pytest -m e2e

# Health check endpoint test
curl http://localhost:8000/health
```

### Database Management

```bash
# Database migrations (using our custom script)
python3 scripts/migrate.py upgrade
python3 scripts/migrate.py revision -m "description"
python3 scripts/migrate.py revision --autogenerate -m "description"

# Check migration status
python3 scripts/migrate.py current
python3 scripts/migrate.py history

# Reset database (development)
python3 scripts/migrate.py reset

# Start database
docker compose up postgres -d
```

### Code Quality

**Using Makefile (Recommended):**

```bash
# Auto-format code with ruff
make format

# Check code quality
make lint

# Run type checking with mypy
make type-check

# Run security checks with bandit
make security

# Run all CI checks locally
make ci-check

# Install dev dependencies + git hooks
make dev-install
```

**Using uv directly:**

```bash
# Format code
uv run ruff format .
uv run ruff check --fix .

# Lint code
uv run ruff check .

# Type check
uv run mypy src/

# Security check
uv run bandit -c pyproject.toml -r src/
```

## Project Naming Conventions

**IMPORTANT**: This project was renamed from "Aegra" to "Open LangGraph" in October 2025. All references have been updated across the codebase.

**Naming Rules by Context**:

- **Docker/Git**: `open-langgraph` (hyphenated)
  - Docker service name: `docker compose up open-langgraph`
  - Docker image: `open-langgraph:latest`
  - GitHub repository: `opensource-langgraph-platform`

- **Python/Database**: `open_langgraph` (underscored)
  - Configuration file: `open_langgraph.json`
  - Database name: `open_langgraph`
  - Database user: `open_langgraph_user`
  - Python package name: `open-langgraph` (in pyproject.toml)

- **Display Names**: "Open LangGraph" (spaced, title case)
  - API responses: `{"name": "Open LangGraph", ...}`
  - Documentation titles
  - User-facing messages

- **Environment Variables**: `OPEN_LANGGRAPH_CONFIG` (all caps with underscores)
  - Config path: `OPEN_LANGGRAPH_CONFIG=./open_langgraph.json`
  - Database URL: `DATABASE_URL=postgresql+asyncpg://...`

**Backward Compatibility**:
- The system maintains `langgraph.json` as a fallback configuration filename for compatibility
- All new deployments should use `open_langgraph.json`

## High-Level Architecture

Open LangGraph is an **Agent Protocol server** that acts as an HTTP wrapper around **official LangGraph packages**. The key architectural principle is that LangGraph handles ALL state persistence and graph execution, while the FastAPI layer only provides Agent Protocol compliance.

### Core Integration Pattern

**Database Architecture**: The system uses a hybrid approach:

- **LangGraph manages state**: Official `AsyncPostgresSaver` and `AsyncPostgresStore` handle conversation checkpoints, state history, and long-term memory
- **Minimal metadata tables**: Our SQLAlchemy models only track Agent Protocol metadata (assistants, runs, thread_metadata)
- **URL format difference**: LangGraph requires `postgresql://` while our SQLAlchemy uses `postgresql+asyncpg://`

### Configuration System

**open_langgraph.json**: Central configuration file that defines:

- Graph definitions: `"graph_id": "path/to/file.py:export_name"`
- Example: `"agent": "./graphs/react_agent/graph.py:graph"`
- Config path can be overridden via `OPEN_LANGGRAPH_CONFIG` environment variable

**auth.py**: Uses LangGraph SDK Auth patterns:

- `@auth.authenticate` decorator for user authentication
- `@auth.on.{resource}.{action}` for resource-level authorization
- Returns `Auth.types.MinimalUserDict` with user identity and metadata

### Database Manager Pattern

**DatabaseManager** (src/agent_server/core/database.py):

- Initializes both SQLAlchemy engine and LangGraph components
- Handles URL conversion between asyncpg and psycopg formats
- Provides singleton access to checkpointer and store instances
- Auto-creates LangGraph tables via `.setup()` calls
- **Note**: Database schema is now managed by Alembic migrations (see `alembic/versions/`)

### Graph Loading Strategy

Agents are Python modules that export a compiled `graph` variable:

```python
# graphs/weather_agent.py
workflow = StateGraph(WeatherState)
# ... define nodes and edges
graph = workflow.compile()  # Must export as 'graph'
```

**Graph Registration**: Graphs are registered in `open_langgraph.json` with format `"graph_id": "path/to/file.py:export_name"`. The LangGraph service automatically creates a default assistant for each graph using deterministic UUIDs (via `uuid5`), allowing clients to reference graphs by `graph_id` directly.

**Runtime Context Pattern**: Graphs can access user authentication and configuration through the `Runtime[Context]` pattern. Nodes receive `runtime: Runtime[Context]` parameter which provides access to `runtime.context` for user data, model configuration, and custom settings.

### FastAPI Integration

**Lifespan Management**: The app uses `@asynccontextmanager` to properly initialize/cleanup LangGraph components during FastAPI startup/shutdown.

**Health Checks**: Comprehensive health endpoint tests connectivity to:

- SQLAlchemy database engine
- LangGraph checkpointer
- LangGraph store

### Service Layer Architecture

**Key Services** (src/agent_server/services/):

- **langgraph_service.py**: Graph loading, caching, and configuration management. Handles graph registry from `open_langgraph.json` and creates default assistants with deterministic UUIDs.
- **streaming_service.py**: Manages SSE (Server-Sent Events) streaming for real-time agent responses. Coordinates with event store for replay functionality.
- **event_store.py**: Postgres-backed persistent storage for SSE events. Enables event replay and supports streaming reconnection. Includes automatic cleanup task for old events.
- **broker.py**: Message broker pattern for coordinating run execution and event distribution.
- **event_converter.py**: Converts LangGraph events to Agent Protocol format for client compatibility.
- **thread_state_service.py**: Manages thread state retrieval and checkpoint history.

### Observability Integration

**Langfuse Support**: Optional tracing and observability via Langfuse:

- Enable by setting `LANGFUSE_LOGGING=true` in `.env`
- Automatically tracks run metadata (user_id, thread_id, run_id as tags)
- Callbacks are injected into LangGraph config in `create_run_config()`
- See `docs/langfuse-usage.md` for detailed configuration

### Authentication Flow

1. HTTP request with Authorization header
2. LangGraph SDK Auth extracts and validates token
3. Returns user context with identity, permissions, org_id
4. Resource handlers filter data based on user context
5. Multi-tenant isolation via user metadata injection

## Key Dependencies

- **langgraph**: Core graph execution framework
- **langgraph-checkpoint-postgres**: Official PostgreSQL state persistence
- **langgraph-sdk**: Authentication and SDK components
- **psycopg[binary]**: Required by LangGraph packages (not asyncpg)
- **FastAPI + uvicorn**: HTTP API layer
- **SQLAlchemy**: For Agent Protocol metadata tables only
- **alembic**: Database migration management
- **asyncpg**: Async PostgreSQL driver for SQLAlchemy
- **greenlet**: Required for async SQLAlchemy operations
- **langfuse** (optional): Observability and tracing for agent runs

## Authentication System

The server uses environment-based authentication switching with proper LangGraph SDK integration:

**Authentication Types:**

- `AUTH_TYPE=noop` - No authentication (allow all requests, useful for development)
- `AUTH_TYPE=custom` - Custom authentication (integrate with your auth service)

**Configuration:**

```bash
# Set in .env file
AUTH_TYPE=noop  # or "custom"
```

**Custom Authentication:**
To implement custom auth, modify the `@auth.authenticate` and `@auth.on` decorated functions in `auth.py`:

1. Update the custom `authenticate()` function to integrate with your auth service (Firebase, JWT, etc.)
2. The `authorize()` function handles user-scoped access control automatically
3. Add any additional environment variables needed for your auth service

**Middleware Integration:**
Authentication runs as middleware on every request. LangGraph operations automatically inherit the authenticated user context for proper data scoping.

## Development Patterns

**Import patterns**: Always use relative imports within the package and absolute imports for external dependencies.

**Database access**: Use `db_manager.get_checkpointer()` and `db_manager.get_store()` for LangGraph operations, `db_manager.get_engine()` for metadata queries.

**Authentication**: Use `get_current_user(request)` dependency to access authenticated user in FastAPI routes. The user is automatically set by LangGraph auth middleware.

**Error handling**: Use `Auth.exceptions.HTTPException` for authentication errors to maintain LangGraph SDK compatibility.

**Testing**: Tests should be async-aware and use pytest-asyncio for proper async test support.

**Configuration Management**:

- User context injection: Use `inject_user_context()` to add user data to LangGraph config
- Thread configs: Use `create_thread_config()` for thread-scoped operations
- Run configs: Use `create_run_config()` for run-scoped operations with full observability

**Graph Development**:

- Graphs must export a `graph` variable (either compiled or uncompiled StateGraph)
- Use `Runtime[Context]` pattern to access user context in graph nodes
- Define custom Context classes in graph modules for type-safe configuration access
- **Available Examples** (all registered in `open_langgraph.json`):
  - `graphs/react_agent/`: Standard ReAct agent with tool calling (graph_id: `agent`)
  - `graphs/react_agent_hitl/`: ReAct agent with human-in-the-loop interrupts (graph_id: `agent_hitl`)
  - `graphs/subgraph_agent/`: Example of subgraph composition (graph_id: `subgraph_agent`)

**Human-in-the-Loop (HITL)**:

- Use `interrupt()` in graph nodes to pause execution for user approval
- LangGraph automatically handles state persistence during interrupts
- Clients can resume execution by sending updates via the runs API

Always run test commands (`uv run pytest` or `make test`) before completing tasks. Code quality checks are enforced via pre-commit hooks (`make dev-install` to set up).

## Migration System

The project now uses Alembic for database schema management:

**Key Files:**

- `alembic.ini`: Alembic configuration
- `alembic/env.py`: Environment setup with async support
- `alembic/versions/`: Migration files
- `scripts/migrate.py`: Custom migration management script

**Migration Commands:**

```bash
# Apply migrations
python3 scripts/migrate.py upgrade

# Create new migration
python3 scripts/migrate.py revision -m "description"

# Check status
python3 scripts/migrate.py current
python3 scripts/migrate.py history

# Reset (destructive)
python3 scripts/migrate.py reset
```

**Important Notes:**

- Always activate virtual environment before running migrations
- Docker automatically runs migrations on startup
- Migration files are version-controlled and should be committed with code changes
