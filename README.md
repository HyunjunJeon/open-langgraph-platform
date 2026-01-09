# Open LangGraph Platform

셀프 호스팅 AI 에이전트 백엔드. 벤더 종속 없이 LangGraph의 강력한 기능을 활용하세요.  

- LangGraph Platform을 자체 인프라로 대체하세요.   
- 에이전트 오케스트레이션을 완전히 제어하고자 하는 개발자를 위해 FastAPI + PostgreSQL로 구축되었습니다.  

**Agent Protocol 준수**: Open LangGraph는 프로덕션 환경에서 LLM 에이전트를 제공하기 위한 오픈소스 표준인 [Agent Protocol](https://github.com/langchain-ai/agent-protocol) 사양을 구현합니다.

---

## 왜 LangSmith Deployment 대신 Open LangGraph Platform 을 선택해야할까요?

| 기능                | LangGraph Platform         | Open LangGraph (셀프 호스팅)                               |
| ---------------------- | -------------------------- | ------------------------------------------------- |
| **비용**               | 비용 발생            | **무료** (셀프 호스팅, 인프라 비용만 발생)           |
| **데이터 제어**       | 타사 호스팅         | **자체 인프라**                           |
| **벤더 종속**     | 높은 의존성            | **제로 종속**                                  |
| **커스터마이징**      | 플랫폼 제한사항       | **완전한 제어**                                  |
| **API 호환성**  | LangGraph SDK              | **동일한 LangGraph SDK**                            |
| **인증**     | Lite: 커스텀 인증 불가       | **커스텀 인증** (JWT/OAuth/Firebase/NoAuth)       |
| **데이터베이스 소유권** | 자체 데이터베이스 불가 | **BYO Postgres** (자격 증명 및 스키마 소유) |
| **Human-in-the-Loop** | 지원 | **완전 지원** (승인 게이트, 사용자 개입) |
| **관찰성/추적**  | LangSmith 강제   | **선택 가능** ([Langfuse](docs/langfuse-usage.md)) |

## 핵심 이점

- 셀프 호스팅: 자체 인프라에서 실행, 자체 규칙 적용
- 드롭인 대체: 기존 LangGraph Client SDK를 변경 없이 사용
- 프로덕션 준비: PostgreSQL 영속성, 스트리밍, 인증
- 빠른 설정: Docker로 빠르게 배포
- Agent Protocol 준수: 오픈소스 [Agent Protocol](https://github.com/langchain-ai/agent-protocol) 사양 구현
- Agent Chat UI 호환: [LangChain의 Agent Chat UI](https://github.com/langchain-ai/agent-chat-ui)와 원활하게 작동
- AG-UI(CopilotKit) 호환: AGUI 프로토콜을 지원하여 다양한 UI와 원활하게 작동

## 빠른 시작

### 사전 요구사항

- Python 3.13+
- Docker (PostgreSQL, Redis 등)
- uv (Python Package Manager)

### 실행하기

```bash
# uv가 없다면 설치
curl -LsSf https://astral.sh/uv/install.sh | sh

# 클론 및 설정
git clone https://github.com/HyunjunJeon/open-langgraph-platform.git
cd open-langgraph

# 환경 및 의존성 동기화
uv sync --all-extras

# 환경 활성화
source .venv/bin/activate  # Mac/Linux
# 또는 .venv/Scripts/activate  # Windows

# 환경 변수
cp .env.example .env

# 시작 (데이터베이스 + 마이그레이션 + 서버)
docker compose up open-langgraph
```

### Checks

```bash
# 헬스 체크
curl http://localhost:8000/health

# 인터랙티브 API 문서
open http://localhost:8000/docs
```

## Compatible Web UI Toolkit

Open LangGraph는 LangGraph API를 지원하는 여러 프론트엔드와 호환됩니다.

### Agent Chat UI (Official LangChain's Chat UI)

설정 예시:
```bash
# Agent Chat UI 프로젝트에서
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_ASSISTANT_ID=agent
```

- Agent Chat UI GitHub: https://github.com/langchain-ai/agent-chat-ui

### CopilotKit (AG-UI 프로토콜)

CopilotKit은 실시간 상호작용과 상태 동기화를 지원하는 현대적인 에이전트 UI 프레임워크입니다. AG-UI(Agent-User Interaction) 프로토콜을 통해 SSE 이벤트 기반으로 프론트엔드와 에이전트를 연결합니다.

패키지 설치:
```bash
npm install @copilotkit/react-core @ag-ui/langgraph
# 또는
pnpm add @copilotkit/react-core @ag-ui/langgraph
```

Next.js 연동 예시:
```tsx
// app/page.tsx
'use client'

import { CopilotKit } from "@copilotkit/react-core";
import { useCoAgent } from "@copilotkit/react-core";

export default function AgentUI() {
  return (
    <CopilotKit
      runtimeUrl="http://localhost:8000"
      agent="agent"  // Open LangGraph 어시스턴트 ID
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
      {/* 커스텀 UI 구성 */}
      {/* CopilotKit은 자동으로 Open LangGraph 백엔드와 동기화됩니다 */}
    </div>
  );
}
```

백엔드 준비(Open LangGraph Platform):
```bash
docker compose up open-langgraph-platform
# http://localhost:8000에서 에이전트가 동작하며 CopilotKit이 SSE로 연결합니다
```

지원 기능 요약:
- 실시간 스트리밍 (SSE)
- 양방향 상태 동기화 (에이전트 ↔ UI)
- Human-in-the-Loop 인터럽트/승인 플로우
- 생성형 UI 패턴
- 스레드 기반 대화 기록 영속화

참고 자료:
- CopilotKit 문서: https://docs.copilotkit.ai/langgraph/
- AG-UI 프로토콜: https://github.com/ag-ui-protocol/ag-ui
- CopilotKit GitHub: https://github.com/CopilotKit/CopilotKit
- 예제: https://github.com/CopilotKit/canvas-with-langgraph-python


## Architecture

```text
Client → FastAPI → LangGraph SDK → PostgreSQL
 ↓         ↓           ↓             ↓
Agent    HTTP     State        Persistent
SDK      API    Management      Storage
```

### 구성 요소

- **FastAPI**: Agent Protocol 준수하는 HTTP 레이어
- **LangGraph**: 상태 관리 및 그래프 실행
- **PostgreSQL**: 지속적인 체크포인트 및 메타데이터
- **Agent Protocol**: LLM 에이전트 API를 위한 오픈소스 사양
- **Config-driven**: 그래프 정의를 위한 `open_langgraph.json`

## 프로젝트 구조

```text
open-langgraph-platform/
├── open_langgraph.json  # 그래프 구성 정의
├── auth.py              # 인증 설정
├── alembic/             # 데이터베이스 마이그레이션
├── graphs/              # 에이전트 그래프 정의
│   ├── react_agent/     # ReAct 에이전트
│   ├── react_agent_hitl/# HITL 포함 ReAct 에이전트
│   └── subgraph_agent/  # 서브그래프 에이전트
├── src/agent_server/    # FastAPI 애플리케이션
│   ├── main.py          # 애플리케이션 진입점
│   ├── a2a/             # Agent-to-Agent 프로토콜
│   ├── api/             # API 라우트 핸들러
│   ├── core/            # 핵심 인프라 및 설정
│   ├── middleware/      # 미들웨어 (인증, 로깅 등)
│   ├── models/          # 데이터 모델 (Pydantic/ORM)
│   ├── observability/   # 관측성 (OpenTelemetry)
│   ├── services/        # 비즈니스 로직
│   └── utils/           # 유틸리티 함수
├── tests/               # 테스트 스위트
├── deployments/         # 배포 구성 (Docker)
└── run_server.py        # 개발 서버 실행 스크립트
```

## 구성

### 환경 변수

`.env.example`을 `.env`로 복사하고 값을 구성하세요:

```bash
cp .env.example .env
```

```bash
# 데이터베이스
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/open_langgraph

# 인증 (확장 가능)
AUTH_TYPE=noop  # noop, custom

# 서버
HOST=0.0.0.0
PORT=8000
DEBUG=true

# LLM 프로바이더
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=...
# TOGETHER_API_KEY=...
```

### 그래프 구성

`open_langgraph.json`은 에이전트 그래프를 정의합니다:

```json
{
  "graphs": {
    "agent": "./graphs/react_agent/graph.py:graph"
  }
}
```

## 로드맵

자세한 계획과 진행 상황은 [ROADMAP.md](ROADMAP.md)를 참조하세요.

## 기여하기

기여 가이드는 [CONTRIBUTING.md](CONTRIBUTING.md)를 참고하세요.
