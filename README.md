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
- 벤더 종속 제로: Apache 2.0 라이선스, 오픈소스, 완전한 제어
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
# uv가 없다면 설치
curl -LsSf https://astral.sh/uv/install.sh | sh

# 환경 및 의존성 동기화
uv sync

# 환경 활성화
source .venv/bin/activate  # Mac/Linux
# 또는 .venv/Scripts/activate  # Windows

# 환경 변수
cp .env.example .env

# 모든 것 시작 (데이터베이스 + 마이그레이션 + 서버)
docker compose up open-langgraph
```

### 작동 확인

```bash
# 헬스 체크
curl http://localhost:8000/health

# 인터랙티브 API 문서
open http://localhost:8000/docs
```

이제 셀프 호스팅 LangGraph Platform 대안이 로컬에서 실행되고 있습니다.

## 호환 UI 툴킷

Open LangGraph는 LangGraph/Agent Protocol API를 지원하는 여러 프론트엔드와 호환됩니다.

### Agent Chat UI (LangChain)

공식 대화형 에이전트 UI로, 바로 연동할 수 있습니다.

설정 예시:
```bash
# Agent Chat UI 프로젝트에서
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_ASSISTANT_ID=agent
```

참고 자료:
- Agent Chat UI GitHub: https://github.com/langchain-ai/agent-chat-ui
- 상태: 완전 지원

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

백엔드 준비(Open LangGraph):
```bash
docker compose up open-langgraph
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

### 커스텀 프론트엔드 연동

표준 LangGraph Platform API를 구현하므로 다음을 지원하는 어떤 클라이언트든 연동 가능합니다:
- SSE 기반 스트리밍
- LangGraph SDK 프로토콜
- Agent Protocol 사양

## 개발자를 위한 정보

**데이터베이스 마이그레이션이 처음이신가요?** 가이드를 확인하세요:

- [개발자 가이드](docs/developer-guide.md) - 설정, 마이그레이션 및 개발 워크플로우
- [마이그레이션 치트시트](docs/migration-cheatsheet.md) - 일반적인 명령어 빠른 참조

**빠른 개발 명령어:**

```bash
# Docker 개발 (권장)
docker compose up open-langgraph

# 로컬 개발
docker compose up postgres -d
python3 scripts/migrate.py upgrade
python3 run_server.py

# 새로운 마이그레이션 생성
python3 scripts/migrate.py revision --autogenerate -m "Add new feature"
```

## 예제 에이전트 실행

이미 익숙한 **동일한 LangGraph Client SDK**를 사용하세요:

```python
import asyncio
from langgraph_sdk import get_client

async def main():
    # 셀프 호스팅 Open LangGraph 인스턴스에 연결
    client = get_client(url="http://localhost:8000")

    # 어시스턴트 생성 (LangGraph Platform과 동일한 API)
    assistant = await client.assistants.create(
        graph_id="agent",
        if_exists="do_nothing",
        config={},
    )
    assistant_id = assistant["assistant_id"]

    # 스레드 생성
    thread = await client.threads.create()
    thread_id = thread["thread_id"]

    # 응답 스트리밍 (LangGraph Platform과 동일)
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

핵심 포인트: 기존 LangGraph 애플리케이션이 수정 없이 작동합니다.

## 아키텍처

```text
Client → FastAPI → LangGraph SDK → PostgreSQL
 ↓         ↓           ↓             ↓
Agent    HTTP     State        Persistent
SDK      API    Management      Storage
```

### 구성 요소

- **FastAPI**: Agent Protocol 준수 HTTP 레이어
- **LangGraph**: 상태 관리 및 그래프 실행
- **PostgreSQL**: 지속적인 체크포인트 및 메타데이터
- **Agent Protocol**: LLM 에이전트 API를 위한 오픈소스 사양
- **Config-driven**: 그래프 정의를 위한 `open_langgraph.json`

## 프로젝트 구조

```text
open-langgraph/
├── open_langgraph.json           # 그래프 구성
├── auth.py              # 인증 설정
├── graphs/              # 에이전트 정의
│   └── react_agent/     # ReAct 에이전트 예제
├── src/agent_server/    # FastAPI 애플리케이션
│   ├── main.py         # 애플리케이션 진입점
│   ├── core/           # 데이터베이스 및 인프라
│   ├── models/         # Pydantic 스키마
│   ├── services/       # 비즈니스 로직
│   └── utils/          # 헬퍼 함수
├── tests/              # 테스트 스위트
└── deployments/        # Docker 및 K8s 구성
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
