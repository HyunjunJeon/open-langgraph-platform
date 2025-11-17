# 오픈소스 LangGraph Platform

<p align="center">
  <strong>셀프 호스팅 AI 에이전트 백엔드. 벤더 종속 없이 LangGraph의 강력한 기능을 활용하세요.</strong>
</p>

LangGraph Platform을 자체 인프라로 대체하세요.  
에이전트 오케스트레이션을 완전히 제어하고자 하는 개발자를 위해 FastAPI + PostgreSQL로 구축되었습니다.

**Agent Protocol 준수**: Open LangGraph는 프로덕션 환경에서 LLM 에이전트를 제공하기 위한 오픈소스 표준인 [Agent Protocol](https://github.com/langchain-ai/agent-protocol) 사양을 구현합니다.

**이런 분들께 추천합니다:** 벤더 종속에서 벗어나고자 하는 팀 • 데이터 주권 요구사항이 있는 경우 • 커스텀 배포가 필요한 경우 • 비용 최적화를 원하는 경우

## 왜 LangGraph Platform 대신 Open LangGraph인가?

| 기능                | LangGraph Platform         | Open LangGraph (셀프 호스팅)                               |
| ---------------------- | -------------------------- | ------------------------------------------------- |
| **비용**               | 월 $$$+             | **무료** (셀프 호스팅, 인프라 비용만 발생)           |
| **데이터 제어**       | 타사 호스팅         | **자체 인프라**                           |
| **벤더 종속**     | 높은 의존성            | **제로 종속**                                  |
| **커스터마이징**      | 플랫폼 제한사항       | **완전한 제어**                                  |
| **API 호환성**  | LangGraph SDK              | **동일한 LangGraph SDK**                            |
| **인증**     | Lite: 커스텀 인증 불가       | **커스텀 인증** (JWT/OAuth/Firebase/NoAuth)       |
| **데이터베이스 소유권** | 자체 데이터베이스 불가 | **BYO Postgres** (자격 증명 및 스키마 소유) |
| **Human-in-the-Loop** | 지원 | **완전 지원** (승인 게이트, 사용자 개입) |
| **관찰성/추적**  | LangSmith 강제   | **선택 가능** ([Langfuse](docs/langfuse-usage.md)/None) |

## 핵심 이점

- 셀프 호스팅: 자체 인프라에서 실행, 자체 규칙 적용
- 드롭인 대체: 기존 LangGraph Client SDK를 변경 없이 사용
- 프로덕션 준비: PostgreSQL 영속성, 스트리밍, 인증
- 빠른 설정: Docker로 5분 만에 배포
- Agent Protocol 준수: 오픈소스 [Agent Protocol](https://github.com/langchain-ai/agent-protocol) 사양 구현
- Agent Chat UI 호환: [LangChain의 Agent Chat UI](https://github.com/langchain-ai/agent-chat-ui)와 원활하게 작동

## 빠른 시작 (5분)

### 사전 요구사항

- Python 3.11+
- Docker (PostgreSQL용)
- uv (Python 패키지 매니저)

### 실행하기

```bash
# 클론 및 설정
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
