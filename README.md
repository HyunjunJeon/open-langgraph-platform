# Open Source LangGraph Platform

<p align="center">
  <strong>Self-hosted AI agent backend. Harness the power of LangGraph without vendor lock-in.</strong>
</p>

Replace LangGraph Platform with your own infrastructure.
Built with FastAPI + PostgreSQL for developers who want full control over agent orchestration.

**Agent Protocol Compliant**: Open LangGraph implements the [Agent Protocol](https://github.com/langchain-ai/agent-protocol) specification, an open-source standard for serving LLM agents in production.

**Recommended for:** Teams wanting to escape vendor lock-in • Cases with data sovereignty requirements • Situations needing custom deployment • Those aiming for cost optimization

## Why Open LangGraph instead of LangGraph Platform?

| Feature                | LangGraph Platform         | Open LangGraph (Self-hosted)                               |
| ---------------------- | -------------------------- | ------------------------------------------------- |
| **Cost**               | $$$+/month             | **Free** (Self-hosted, only infrastructure costs)           |
| **Data Control**       | Third-party hosting         | **Your own infrastructure**                           |
| **Vendor Lock-in**     | High dependency            | **Zero dependency**                                  |
| **Customization**      | Platform limitations       | **Complete control**                                  |
| **API Compatibility**  | LangGraph SDK              | **Same LangGraph SDK**                            |
| **Authentication**     | Lite: No custom auth       | **Custom Authentication** (JWT/OAuth/Firebase/NoAuth)       |
| **Database Ownership** | No custom database | **BYO Postgres** (Own credentials and schema) |
| **Human-in-the-Loop** | Supported | **Fully Supported** (Approval gates, user intervention) |
| **Observability/Tracing**  | LangSmith required   | **Optional** ([Langfuse](docs/langfuse-usage.md)/None) |

## Core Benefits

- Self-hosted: Run on your own infrastructure, apply your own rules
- Drop-in replacement: Use the existing LangGraph Client SDK without changes
- Production-ready: PostgreSQL persistence, streaming, authentication
- Quick setup: Deploy in 5 minutes with Docker
- Agent Protocol Compliant: Implements the open-source [Agent Protocol](https://github.com/langchain-ai/agent-protocol) specification
- Agent Chat UI Compatible: Works seamlessly with [LangChain's Agent Chat UI](https://github.com/langchain-ai/agent-chat-ui)

## Quick Start (5 minutes)

### Prerequisites

- Python 3.11+
- Docker (for PostgreSQL)
- uv (Python package manager)

### Getting Started

```bash
# Clone and set up
git clone https://github.com/HyunjunJeon/open-langgraph-platform.git
cd open-langgraph
# If you don't have uv, install it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync environment and dependencies
uv sync

# Activate environment
source .venv/bin/activate  # Mac/Linux
# or .venv/Scripts/activate  # Windows

# Environment variables
cp .env.example .env

# Start everything (database + migrations + server)
docker compose up open-langgraph
```

### Verify It Works

```bash
# Health check
curl http://localhost:8000/health

# Interactive API docs
open http://localhost:8000/docs
```

Your self-hosted LangGraph Platform alternative is now running locally.

## Compatible UI Toolkits

Open LangGraph is compatible with several frontends that support the LangGraph/Agent Protocol API.

### Agent Chat UI (LangChain)

The official interactive agent UI, which you can connect directly.

Example setup:
```bash
# In your Agent Chat UI project
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_ASSISTANT_ID=agent
```

References:
- Agent Chat UI GitHub: https://github.com/langchain-ai/agent-chat-ui
- Status: Fully supported

### CopilotKit (AG-UI Protocol)

CopilotKit is a modern agent UI framework that supports real-time interaction and state synchronization. It connects the frontend and agent via the AG-UI (Agent-User Interaction) protocol, based on SSE events.

Install packages:
```bash
npm install @copilotkit/react-core @ag-ui/langgraph
# or
pnpm add @copilotkit/react-core @ag-ui/langgraph
```

Next.js integration example:
```tsx
// app/page.tsx
'use client'

import { CopilotKit } from "@copilotkit/react-core";
import { useCoAgent } from "@copilotkit/react-core";

export default function AgentUI() {
  return (
    <CopilotKit
      runtimeUrl="http://localhost:8000"
      agent="agent"  // Open LangGraph assistant ID
    >
      <YourAgentInterface />
    </CopilotKit>
  );
}

function YourAgentInterface() {
  const { state, setState, run } = useCoAgent({
    name: "agent",
  });

  return (
    <div>
      {/* Custom UI components */}
      {/* CopilotKit automatically syncs with the Open LangGraph backend */}
    </div>
  );
}
```

Backend preparation (Open LangGraph):
```bash
docker compose up open-langgraph
# The agent runs at http://localhost:8000, and CopilotKit connects via SSE
```

Summary of supported features:
- Real-time streaming (SSE)
- Bidirectional state synchronization (agent ↔ UI)
- Human-in-the-Loop interrupt/approval flows
- Generative UI patterns
- Thread-based conversation history persistence

References:
- CopilotKit Docs: https://docs.copilotkit.ai/langgraph/
- AG-UI Protocol: https://github.com/ag-ui-protocol/ag-ui
- CopilotKit GitHub: https://github.com/CopilotKit/CopilotKit
- Example: https://github.com/CopilotKit/canvas-with-langgraph-python

### Custom Frontend Integration

Since it implements the standard LangGraph Platform API, you can integrate any client that supports:
- SSE-based streaming
- LangGraph SDK protocol
- Agent Protocol specification

## For Developers

**New to database migrations?** Check out the guides:

- [Developer Guide](docs/developer-guide.md) - Setup, migrations, and development workflow
- [Migration Cheatsheet](docs/migration-cheatsheet.md) - Quick reference for common commands

**Quick Development Commands:**

```bash
# Docker development (recommended)
docker compose up open-langgraph

# Local development
docker compose up postgres -d
python3 scripts/migrate.py upgrade
python3 run_server.py

# Create a new migration
python3 scripts/migrate.py revision --autogenerate -m "Add new feature"
```

## Run an Example Agent

Use the **same LangGraph Client SDK** you're already familiar with:

```python
import asyncio
from langgraph_sdk import get_client

async def main():
    # Connect to your self-hosted Open LangGraph instance
    client = get_client(url="http://localhost:8000")

    # Create an assistant (same API as LangGraph Platform)
    assistant = await client.assistants.create(
        graph_id="agent",
        if_exists="do_nothing",
        config={},
    )
    assistant_id = assistant["assistant_id"]

    # Create a thread
    thread = await client.threads.create()
    thread_id = thread["thread_id"]

    # Stream the response (same as LangGraph Platform)
    stream = client.runs.stream(
        thread_id=thread_id,
        assistant_id=assistant_id,
        input={
            "messages": [
                {"type": "human", "content": [{"type": "text", "text": "hello"}]}
            ]
        },
        stream_mode=["values", "messages-tuple", "custom"],
        on_disconnect="cancel",
    )

    async for chunk in stream:
        print(f"event: {getattr(chunk, 'event', None)}, data: {getattr(chunk, 'data', None)}")

asyncio.run(main())
```

The key takeaway: Your existing LangGraph applications work without modification.

## Architecture

```text
Client → FastAPI → LangGraph SDK → PostgreSQL
 ↓         ↓           ↓             ↓
Agent    HTTP     State        Persistent
SDK      API    Management      Storage
```

### Components

- **FastAPI**: Agent Protocol compliant HTTP layer
- **LangGraph**: State management and graph execution
- **PostgreSQL**: Persistent checkpoints and metadata
- **Agent Protocol**: Open-source specification for LLM agent APIs
- **Config-driven**: `open_langgraph.json` for graph definitions

## Project Structure

```text
open-langgraph/
├── open_langgraph.json           # Graph configuration
├── auth.py              # Authentication setup
├── graphs/              # Agent definitions
│   └── react_agent/     # ReAct agent example
├── src/agent_server/    # FastAPI application
│   ├── main.py         # Application entrypoint
│   ├── core/           # Database and infrastructure
│   ├── models/         # Pydantic schemas
│   ├── services/       # Business logic
│   └── utils/          # Helper functions
├── tests/              # Test suite
└── deployments/        # Docker and K8s configurations
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure the values:

```bash
cp .env.example .env
```

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/open_langgraph

# Authentication (extensible)
AUTH_TYPE=noop  # noop, custom

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=true

# LLM Providers
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=...
# TOGETHER_API_KEY=...
```

### Graph Configuration

`open_langgraph.json` defines the agent graphs:

```json
{
  "graphs": {
    "agent": "./graphs/react_agent/graph.py:graph"
  }
}
```

## Roadmap

For detailed plans and progress, see [ROADMAP.md](ROADMAP.md).
