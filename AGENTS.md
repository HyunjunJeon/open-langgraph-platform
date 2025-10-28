# OpenSource LangGraph Platform - Complete Structure Guide

This project is an open-source alternative to LangGraph Platform, a FastAPI-based Agent Protocol server. This document serves as an entry point to understand the overall project structure and navigate component documentation.

---

## Table of Contents

- [Project Overview](#-project-overview)
- [Core Value Proposition](#-core-value-proposition)
- [Tech Stack](#-tech-stack)
- [Project Structure Map](#-project-structure-map)
- [Layer Architecture](#-layer-architecture)
- [Getting Started](#-getting-started)
- [Key Components](#-key-components)
- [Documentation Navigation](#-documentation-navigation)
- [Quick Reference](#-quick-reference)
- [Developer Roadmap](#-developer-roadmap)

---

## Project Overview

**An open-source platform that allows you to run all LangGraph features on your own infrastructure**. Instead of LangGraph Platform's SaaS service, you can deploy and manage AI agents with complete control and data sovereignty.

### Core Design Philosophy

```bash
LangGraph-Centric Architecture
├─ LangGraph handles ALL state management and graph execution
├─ FastAPI provides ONLY Agent Protocol-compliant HTTP layer
└─ Minimal metadata stored in custom DB tables
```

**Design Principles:**

- Use LangGraph packages directly (no wrappers)
- 100% compatible with official LangGraph Client SDK
- Zero vendor lock-in
- Production ready (PostgreSQL, streaming, authentication)

---

## Core Value Proposition

### LangGraph Platform vs OpenSource LangGraph Platform

| Feature | LangGraph Platform | OpenSource LangGraph Platform (Self-Hosted) |
|---------|-------------------|---------------------|
| **Cost** | $$$+ per month | **Free** (infrastructure costs only) |
| **Data Control** | Third-party hosting | **Your infrastructure** |
| **Vendor Lock-in** | High | **Zero** |
| **Customization** | Platform constraints | **Complete control** |
| **Authentication** | Limited | **Custom auth** (JWT/OAuth/Firebase) |
| **Database** | Not owned | **Your PostgreSQL** |
| **Tracing** | LangSmith required | **Optional** (Langfuse/None) |

### Key Features

- **Self-Hosted**: Run on your own infrastructure
- **Drop-in Replacement**: Use existing LangGraph Client SDK as-is
- **Production Ready**: PostgreSQL persistence, streaming, authentication
- **Agent Protocol Compliant**: Implements open-source standard
- **Agent Chat UI Compatible**: Works seamlessly with LangChain's Agent Chat UI
- **Observability Integration**: Optional Langfuse integration

---

## 🛠️ Tech Stack

### Core Technologies

#### **Backend Framework**

- **FastAPI** - High-performance ASGI-based web framework
- **Uvicorn** - ASGI server
- **Python 3.11+** - Async processing and type hints

#### **AI Agent Framework**

- **LangGraph** - State management and graph execution engine
- **LangGraph Checkpoint Postgres** - PostgreSQL-based checkpoint storage
- **LangGraph Store** - Long-term memory storage
- **LangGraph SDK Auth** - Authentication and authorization management

#### **Database**

- **PostgreSQL** - Primary database (LangGraph state + metadata)
- **psycopg[binary]** - Required driver for LangGraph
- **asyncpg** - Async driver for SQLAlchemy
- **SQLAlchemy** - ORM (metadata tables only)
- **Alembic** - Database migration tool

#### **Observability (Optional)**

- **Langfuse** - LLM tracing and observability

#### **Development Tools**

- **uv** - Python package manager
- **pytest** - Testing framework
- **ruff** - Linter and formatter
- **mypy** - Type checker
- **pre-commit** - Git hooks manager

---

## Project Structure Map

```bash
ROOT/
├── Core Configuration
│   ├── open_langgraph.json              # Graph definitions and config (langgraph.json)
│   ├── auth.py                 # Authentication system
│   ├── .env.example            # Environment variables template
│   ├── pyproject.toml          # Python project configuration
│   └── docker-compose.yml      # Local development environment
│
├── Documentation             → [docs/AGENTS.md]
│   ├── README.md               # Documentation hub
│   ├── developer-guide.md      # Developer guide
│   ├── architecture-ko.md      # Architecture details
│   ├── code-quality.md         # Code quality standards
│   ├── migration-cheatsheet.md # Migration reference
│   ├── langfuse-usage.md       # Observability setup
│   ├── troubleshooting-ko.md   # Troubleshooting
│   └── examples-ko.md          # Practical examples
│
├── Source Code
│   └── agent_server/
│       ├── Authentication & Context
│       │   ├── core/auth_ctx.py         # Authentication context
│       │   ├── core/auth_deps.py        # Authentication dependencies
│       │   └── core/auth_middleware.py  # Authentication middleware
│       │
│       ├── Core Layer          → [src/agent_server/core/AGENTS.md]
│       │   ├── database.py        # DatabaseManager (LangGraph + SQLAlchemy)
│       │   ├── orm.py             # SQLAlchemy models
│       │   ├── health.py          # Health checks
│       │   ├── sse.py             # Server-Sent Events
│       │   └── serializers/       # Serialization (JSON, LangGraph)
│       │       ├── base.py        # Base serialization
│       │       ├── general.py     # General serialization
│       │       └── langgraph.py   # LangGraph-specific
│       │
│       ├── Service Layer       → [src/agent_server/services/AGENTS.md]
│       │   ├── langgraph_service.py    # Graph loading/caching
│       │   ├── assistant_service.py    # Assistant management
│       │   ├── streaming_service.py    # SSE streaming
│       │   ├── event_store.py          # Event persistence
│       │   ├── broker.py               # Message broker
│       │   ├── event_converter.py      # LangGraph → Agent Protocol
│       │   └── thread_state_service.py # Thread state retrieval
│       │
│       ├── API Layer           → [src/agent_server/api/AGENTS.md]
│       │   ├── assistants.py      # /assistants endpoints
│       │   ├── threads.py         # /threads endpoints
│       │   ├── runs.py            # /runs endpoints
│       │   └── store.py           # /store endpoints
│       │
│       ├── Models              → [src/agent_server/models/AGENTS.md]
│       │   ├── assistants.py      # Assistant schemas
│       │   ├── threads.py         # Thread schemas
│       │   ├── runs.py            # Run schemas
│       │   ├── store.py           # Store schemas
│       │   ├── auth.py            # Auth schemas
│       │   └── errors.py          # Error schemas
│       │
│       ├── Observability       → [src/agent_server/observability/AGENTS.md]
│       │   └── langfuse_integration.py
│       │
│       ├── Middleware          → [src/agent_server/middleware/AGENTS.md]
│       │   └── double_encoded_json.py
│       │
│       ├── Utils               → [src/agent_server/utils/AGENTS.md]
│       │   ├── assistants.py      # Assistant helpers
│       │   └── sse_utils.py       # SSE utilities
│       │
│       └── main.py                # FastAPI application entry point
│
├── Agent Graphs
│   ├── react_agent/          → [graphs/react_agent/AGENTS.md]
│   │   ├── graph.py          # ReAct pattern implementation
│   │   ├── context.py        # Runtime Context
│   │   ├── state.py          # State schema
│   │   ├── tools.py          # Tool functions
│   │   ├── prompts.py        # Prompt templates
│   │   └── utils.py          # Helper functions
│   │
│   ├── react_agent_hitl/     → [graphs/react_agent_hitl/AGENTS.md]
│   │   ├── graph.py          # Human-in-the-Loop pattern
│   │   ├── context.py        # Runtime Context
│   │   ├── state.py          # State schema (approval flags)
│   │   ├── tools.py          # Tool functions
│   │   ├── prompts.py        # Prompt templates
│   │   └── utils.py          # Helper functions
│   │
│   └── subgraph_agent/       → [graphs/subgraph_agent/AGENTS.md]
│       └── graph.py          # Subgraph composition pattern
│
├── Tests                  → [tests/AGENTS.md]
│   ├── unit/                 # Unit tests
│   │   ├── test_core/        # Core layer tests
│   │   ├── test_services/    # Service layer tests
│   │   ├── test_models/      # Model validation tests
│   │   ├── test_middleware/  # Middleware tests
│   │   ├── test_observability/ # Observability tests
│   │   └── test_utils/       # Utility tests
│   │
│   ├── integration/          # Integration tests
│   │   ├── test_api/         # API endpoint tests
│   │   └── test_services/    # Service integration tests
│   │
│   ├── e2e/                  # E2E tests
│   │   ├── test_assistants/  # Assistant flows
│   │   ├── test_threads/     # Thread flows
│   │   ├── test_runs/        # Run flows
│   │   ├── test_streaming/   # Streaming flows
│   │   ├── test_human_in_loop/ # HITL flows
│   │   └── test_store/       # Store flows
│   │
│   ├── fixtures/             # Test fixtures
│   └── conftest.py           # pytest configuration
│
├── Database
│   ├── alembic/              # Migration system
│   │   ├── versions/         # Migration files
│   │   └── env.py            # Alembic environment config
│   ├── alembic.ini           # Alembic configuration
│   └── scripts/migrate.py    # Custom migration tool
│
├── Deployment
│   ├── Dockerfile            # Container image
│   ├── docker-compose.yml    # Local development environment
│   └── .dockerignore         # Docker ignore files
│
└── Development Tools
    ├── Makefile              # Development task automation
    ├── run_server.py         # Server startup script
    ├── .pre-commit-config.yaml
    ├── .python-version       # Python version (3.11)
    └── pyproject.toml        # Project configuration
```

---

## Layer Architecture

This project follows a clear layered architecture:

```bash
┌─────────────────────────────────────────────────────────┐
│                    Client Layer                         │
│  (LangGraph Client SDK / HTTP Clients / Agent Chat UI) │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                   API Layer (FastAPI)                   │ → api/AGENTS.md
│  ┌──────────────┬──────────────┬──────────────────────┐│
│  │ /assistants  │  /threads    │  /runs  │  /store    ││
│  │ (CRUD)       │  (CRUD)      │  (Stream/Execute)    ││
│  └──────────────┴──────────────┴──────────────────────┘│
│                 Agent Protocol Endpoints                │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  Service Layer                          │ → services/AGENTS.md
│  ┌─────────────────────────────────────────────────────┐│
│  │  LangGraphService    │  StreamingService            ││
│  │  (Graph load/cache)  │  (SSE streaming)             ││
│  ├─────────────────────────────────────────────────────┤│
│  │  EventStore          │  EventConverter              ││
│  │  (Event persistence) │  (LangGraph → Agent Protocol)││
│  ├─────────────────────────────────────────────────────┤│
│  │  Broker              │  ThreadStateService          ││
│  │  (Message coordination) │  (State retrieval)        ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                   Core Layer                            │ → core/AGENTS.md
│  ┌─────────────────────────────────────────────────────┐│
│  │  DatabaseManager (Singleton)                        ││
│  │  ├─ get_checkpointer() → AsyncPostgresSaver        ││
│  │  ├─ get_store() → AsyncPostgresStore               ││
│  │  └─ get_engine() → AsyncEngine (SQLAlchemy)        ││
│  ├─────────────────────────────────────────────────────┤│
│  │  Authentication System                              ││
│  │  ├─ auth_middleware.py (Request auth)              ││
│  │  ├─ auth_deps.py (Dependency injection)            ││
│  │  └─ auth_ctx.py (User context)                     ││
│  ├─────────────────────────────────────────────────────┤│
│  │  Serializers (Data serialization)                  ││
│  │  Health Checks (System status)                     ││
│  │  SSE Utilities (Streaming support)                 ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│              Data Layer (PostgreSQL)                    │
│  ┌──────────────────┬──────────────────────────────────┐│
│  │ LangGraph Tables │  Platform Metadata Tables        ││
│  │ ├─ checkpoints   │  ├─ assistants                   ││
│  │ ├─ writes        │  ├─ runs                         ││
│  │ └─ store         │  ├─ thread_metadata              ││
│  │                  │  └─ event_store                   ││
│  └──────────────────┴──────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

#### 1. API Layer (HTTP Interface)

**Responsibilities:**

- Provide Agent Protocol endpoints
- Request validation (Pydantic models)
- Authentication/authorization checks
- Response formatting

**Files:** `src/agent_server/api/*.py`

#### 2. Service Layer (Business Logic)

**Responsibilities:**

- Graph loading and caching
- Execution coordination (run creation, streaming)
- Event conversion and storage
- State management

**Files:** `src/agent_server/services/*.py`

#### 3. Core Layer (Infrastructure)

**Responsibilities:**

- Database connection management
- LangGraph component initialization
- Authentication system
- Serialization/deserialization

**Files:** `src/agent_server/core/*.py`

#### 4. Data Layer (Persistence)

**Responsibilities:**

- LangGraph state storage (checkpoints, writes, store)
- Agent Protocol metadata (assistants, runs, threads)
- Event storage (SSE replay)

**Database:** PostgreSQL

### Data Flow

**Request Flow (Client → Server):**

```bash
1. HTTP Request (LangGraph Client SDK)
   ↓
2. FastAPI Router (API Layer)
   ↓
3. Auth Middleware (auth_middleware.py)
   ↓
4. Service Call (Service Layer)
   ↓
5. LangGraph Graph Execution (Core Layer)
   ↓
6. State Persistence (PostgreSQL via Checkpointer)
```

**Streaming Flow (Server → Client):**

```bash
1. Graph Execution Start (LangGraph)
   ↓
2. Event Generation (LangGraph Events)
   ↓
3. Event Conversion (EventConverter)
   ↓
4. Event Storage (EventStore → PostgreSQL)
   ↓
5. SSE Transmission (StreamingService → Client)
```

---

## Getting Started

### Entry Point for New Developers

#### Step 1: Environment Setup (5 minutes)

```bash
# Clone repository
git clone https://github.com/HyunjunJeon/opensource-langgraph-platform
cd opensource-langgraph-platform

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate  # Mac/Linux
# .venv/Scripts/activate  # Windows

# Configure environment variables
cp .env.example .env
# Edit .env file and add required keys like OPENAI_API_KEY

# Start PostgreSQL + server with Docker
docker compose up open-langgraph
```

#### Step 2: Verify Functionality

```bash
# Health check
curl http://localhost:8000/health

# Check API documentation
open http://localhost:8000/docs

# List assistants
curl http://localhost:8000/assistants
```

#### Step 3: Run Your First Agent

```python
import asyncio
from langgraph_sdk import get_client

async def main():
    # Connect to OpenSource LangGraph Platform server
    client = get_client(url="http://localhost:8000")

    # Create thread
    thread = await client.threads.create()

    # Run agent
    async for chunk in client.runs.stream(
        thread_id=thread["thread_id"],
        assistant_id="agent",  # react_agent
        input={"messages": [{"role": "user", "content": "Hello!"}]},
        stream_mode=["values"]
    ):
        print(chunk)

asyncio.run(main())
```

### Recommended Learning Path

The reading order differs by role:

#### 🆕 New Developer (Understanding Codebase)

```bash
1. This document (AGENTS.md) - Understand overall structure
   ↓
2. docs/developer-guide.md - Development environment setup
   ↓
3. docs/architecture-ko.md - Understand architecture
   ↓
4. graphs/react_agent/AGENTS.md - Analyze example agent
   ↓
5. src/agent_server/core/AGENTS.md - Learn Core layer
   ↓
6. src/agent_server/services/AGENTS.md - Learn Service layer
   ↓
7. src/agent_server/api/AGENTS.md - Learn API layer
```

#### 🏗️ Architect (System Design)

```bash
1. This document (AGENTS.md) - Understand overall structure
   ↓
2. docs/architecture-ko.md - Architecture details
   ↓
3. src/agent_server/core/AGENTS.md - Infrastructure layer
   ↓
4. src/agent_server/services/AGENTS.md - Business logic
   ↓
5. CLAUDE.md - Design philosophy and patterns
```

#### 🤖 Agent Developer (Custom Graph Development)

```bash
1. graphs/react_agent/AGENTS.md - Basic pattern
   ↓
2. graphs/react_agent_hitl/AGENTS.md - HITL pattern
   ↓
3. graphs/subgraph_agent/AGENTS.md - Subgraph pattern
   ↓
4. docs/examples-ko.md - Practical examples
   ↓
5. LangGraph Official Docs - Advanced patterns
```

#### 🚀 DevOps / Deployment

```bash
1. This document (AGENTS.md) - Understand overall structure
   ↓
2. docs/developer-guide.md - Deployment section
   ↓
3. docs/migration-cheatsheet.md - DB migration
   ↓
4. docs/langfuse-usage.md - Observability setup
   ↓
5. docs/troubleshooting-ko.md - Troubleshooting
```

---

## 🔑 Key Components

### Core Services

#### 1. DatabaseManager

**Location:** `src/agent_server/core/database.py`

**Responsibilities:**

- Initialize LangGraph components (Checkpointer, Store)
- Manage SQLAlchemy engine
- Convert URL formats (asyncpg ↔ psycopg)

**Main Methods:**

```python
db_manager = DatabaseManager.get_instance()
checkpointer = db_manager.get_checkpointer()  # LangGraph state management
store = db_manager.get_store()                # Long-term memory
engine = db_manager.get_engine()              # Metadata queries
```

#### 2. LangGraphService

**Location:** `src/agent_server/services/langgraph_service.py`

**Responsibilities:**

- Load graph definitions from open_langgraph.json
- Compile and cache graphs
- Create default assistants (deterministic UUID)

#### 3. StreamingService

**Location:** `src/agent_server/services/streaming_service.py`

**Responsibilities:**

- SSE (Server-Sent Events) streaming
- Event buffering and transmission
- Event replay on reconnection

#### 4. EventStore

**Location:** `src/agent_server/services/event_store.py`

**Responsibilities:**

- PostgreSQL-based event persistence
- Streaming reconnection support
- Automatic event cleanup (TTL)

#### 5. Authentication System

**Location:** `src/agent_server/core/auth_*.py`, `auth.py`

**Responsibilities:**

- Implement LangGraph SDK Auth patterns
- User authentication (`@auth.authenticate`)
- Resource authorization (`@auth.on.{resource}.{action}`)
- Multi-tenant isolation

### Graph Examples

#### 1. ReAct Agent

**Location:** `graphs/react_agent/`
**Documentation:** [graphs/react_agent/AGENTS.md](graphs/react_agent/AGENTS.md)

**Pattern:** Reasoning + Acting cycle

- LLM automatically selects and executes tools
- Simple structure, no interrupts
- Includes web search tool

**Use Cases:**

- Information retrieval agent
- Q&A bot
- Research assistant

#### 2. ReAct Agent HITL

**Location:** `graphs/react_agent_hitl/`
**Documentation:** [graphs/react_agent_hitl/AGENTS.md](graphs/react_agent_hitl/AGENTS.md)

**Pattern:** Human-in-the-Loop (approval gate)

- Requires user approval before tool execution
- Uses `interrupt()` to pause execution
- Can resume after approval

**Use Cases:**

- Financial transaction agent
- Sensitive data operations
- Compliance-required workflows

#### 3. Subgraph Agent

**Location:** `graphs/subgraph_agent/`
**Documentation:** [graphs/subgraph_agent/AGENTS.md](graphs/subgraph_agent/AGENTS.md)

**Pattern:** Subgraph composition

- Modularize complex workflows
- Call other graphs within a graph
- Reusable components

**Use Cases:**

- Complex multi-step processes
- Modular agent systems
- Workflow orchestration

---

## 📚 Documentation Navigation

### Component Documentation

Each directory contains detailed component documentation (`AGENTS.md`):

#### General Documentation

- **[docs/AGENTS.md](docs/AGENTS.md)** - Documentation hub and guides
  - developer-guide.md - Environment setup, development workflow
  - architecture-ko.md - System architecture details
  - code-quality.md - Linting, formatting, type checking
  - migration-cheatsheet.md - Database migration reference
  - langfuse-usage.md - Observability and tracing
  - troubleshooting-ko.md - Common troubleshooting
  - examples-ko.md - Practical code examples

#### Core Layer (Infrastructure)

- **[src/agent_server/core/AGENTS.md](src/agent_server/core/AGENTS.md)** (Coming soon)
  - DatabaseManager usage
  - LangGraph integration patterns
  - Authentication system structure
  - Serialization/deserialization
  - Health check mechanisms

#### Service Layer (Business Logic)

- **[src/agent_server/services/AGENTS.md](src/agent_server/services/AGENTS.md)** (Coming soon)
  - LangGraphService: Graph loading/caching
  - StreamingService: SSE streaming
  - EventStore: Event persistence
  - Broker: Message coordination
  - EventConverter: Format conversion
  - ThreadStateService: State retrieval

#### API Layer (HTTP Endpoints)

- **[src/agent_server/api/AGENTS.md](src/agent_server/api/AGENTS.md)** (Coming soon)
  - /assistants - Assistant CRUD
  - /threads - Thread management
  - /runs - Execution and streaming
  - /store - Long-term memory storage

#### Models (Data Schemas)

- **[src/agent_server/models/AGENTS.md](src/agent_server/models/AGENTS.md)** (Coming soon)
  - Pydantic model structure
  - Validation rules
  - Type definitions

#### Agent Graphs (Agent Implementation)

- **[graphs/react_agent/AGENTS.md](graphs/react_agent/AGENTS.md)** ✅
  - ReAct pattern detailed explanation
  - Node/edge structure
  - Customization guide
  - Usage examples

- **[graphs/react_agent_hitl/AGENTS.md](graphs/react_agent_hitl/AGENTS.md)** (Coming soon)
  - Human-in-the-Loop pattern
  - interrupt() usage
  - Approval flow

- **[graphs/subgraph_agent/AGENTS.md](graphs/subgraph_agent/AGENTS.md)** (Coming soon)
  - Subgraph composition
  - Modularization patterns
  - Complex workflows

#### Tests

- **[tests/AGENTS.md](tests/AGENTS.md)** (Coming soon)
  - Test structure
  - Fixture usage
  - Async testing
  - E2E test writing

### External Resources

- **[LangGraph Official Docs](https://langchain-ai.github.io/langgraph/)**
  - StateGraph concepts
  - Checkpoint system
  - Tool calling patterns

- **[Agent Protocol Spec](https://github.com/AI-Engineer-Foundation/agent-protocol)**
  - REST API standard
  - Endpoint definitions
  - Schema specifications

- **[FastAPI Docs](https://fastapi.tiangolo.com/)**
  - Async routing
  - Dependency injection
  - SSE streaming

- **[Langfuse Docs](https://langfuse.com/docs)**
  - LLM tracing
  - Observability setup

---

## ⚡ Quick Reference

### Frequently Used Files

#### Configuration Files

```bash
open_langgraph.json              # Graph definitions
auth.py                 # Authentication config
.env                    # Environment variables
pyproject.toml          # Python project settings
alembic.ini             # Migration configuration
```

#### Entry Points

```bash
src/agent_server/main.py              # FastAPI app
run_server.py                         # Server startup script
scripts/migrate.py                    # Migration tool
```

#### Core Services

```bash
src/agent_server/core/database.py               # DB management
src/agent_server/services/langgraph_service.py  # Graph loading
src/agent_server/services/streaming_service.py  # Streaming
src/agent_server/api/runs.py                    # Run endpoints
```

#### Example Agents

```bash
graphs/react_agent/graph.py           # ReAct pattern
graphs/react_agent_hitl/graph.py      # HITL pattern
graphs/subgraph_agent/graph.py        # Subgraph pattern
```

### Key Concepts Index

| Concept | Description | Related Files |
|---------|-------------|---------------|
| **Agent Protocol** | LLM agent API standard | api/*.py |
| **Checkpointer** | LangGraph state persistence | core/database.py |
| **Store** | Long-term memory storage | core/database.py, api/store.py |
| **SSE** | Server-Sent Events streaming | services/streaming_service.py |
| **Event Store** | Event replay storage | services/event_store.py |
| **Runtime Context** | Graph execution config | graphs/*/context.py |
| **StateGraph** | LangGraph graph definition | graphs/*/graph.py |
| **HITL** | Human-in-the-Loop | graphs/react_agent_hitl/ |
| **Alembic** | DB migration | alembic/, scripts/migrate.py |
| **Langfuse** | LLM tracing and observability | observability/langfuse_integration.py |

### Common Tasks CheatSheet

#### Development Environment

```bash
# Start server (Docker)
docker compose up open-langgraph

# Start server (Local)
uv run uvicorn src.agent_server.main:app --reload

# Run tests
uv run pytest

# Format code
make format

# Lint
make lint

# Type check
make type-check
```

#### Database

```bash
# Apply migrations
python3 scripts/migrate.py upgrade

# Create new migration
python3 scripts/migrate.py revision --autogenerate -m "description"

# Check migration status
python3 scripts/migrate.py current
```

#### API Calls

```bash
# Health check
curl http://localhost:8000/health

# List assistants
curl http://localhost:8000/assistants

# Create thread
curl -X POST http://localhost:8000/threads

# Run (streaming)
curl -X POST http://localhost:8000/threads/{thread_id}/runs/stream \
  -H "Content-Type: application/json" \
  -d '{"assistant_id": "agent", "input": {"messages": [{"role": "user", "content": "Hello"}]}}'
```
