# ReAct Agent

## 그래프 개요

ReAct Agent는 **Reasoning(추론)과 Acting(행동)을 결합한 패턴**을 구현한 LangGraph 기반 에이전트입니다. 이 패턴은 LLM이 문제 해결을 위해 사고 과정(Thought)과 도구 실행(Action)을 반복하며 점진적으로 답변을 구성하는 방식입니다.

### ReAct 패턴 동작 원리

```
사용자 질문
    ↓
[Reasoning] LLM이 상황을 분석하고 필요한 도구 결정
    ↓
[Action] 선택된 도구 실행 (예: 웹 검색)
    ↓
[Observation] 도구 실행 결과를 LLM에 전달
    ↓
[Reasoning] 결과를 분석하고 추가 도구 필요 여부 판단
    ↓
최종 답변 생성 또는 사이클 반복
```

### 주요 특징

- **간단한 구조**: 복잡한 중단(interrupt) 없이 연속 실행
- **자동 도구 선택**: LLM이 컨텍스트에 따라 적절한 도구를 자동으로 결정
- **상태 관리**: LangGraph StateGraph를 통해 대화 히스토리와 실행 컨텍스트 유지
- **무한 루프 방지**: 재귀 제한(recursion_limit)을 통한 안전한 실행

---

## 파일 구조

ReAct Agent는 7개의 모듈로 구성되며, 각 모듈은 명확한 책임을 가집니다:

```
graphs/react_agent/
├── __init__.py         # 패키지 진입점, 컴파일된 graph 내보내기
├── context.py          # Runtime[Context] 패턴 - 실행 설정 정의
├── graph.py            # 그래프 정의 - 노드, 엣지, 실행 흐름
├── prompts.py          # 시스템 프롬프트 템플릿
├── state.py            # 상태 스키마 정의 (메시지, 스텝 카운터)
├── tools.py            # 에이전트가 사용할 도구 함수들
└── utils.py            # 헬퍼 함수 (모델 로딩, 메시지 처리)
```

### 파일별 역할

#### `__init__.py` - 패키지 진입점
- 컴파일된 `graph` 객체를 외부에 노출
- open_langgraph.json에서 참조할 수 있도록 내보내기

```python
from react_agent.graph import graph

__all__ = ["graph"]
```

#### `context.py` - 런타임 컨텍스트
- LangGraph의 `Runtime[Context]` 패턴 구현
- 에이전트 실행 시 필요한 설정 매개변수 정의
- 환경 변수 자동 로드 지원

**주요 설정:**
- `system_prompt`: 에이전트의 역할과 동작 정의
- `model`: 사용할 LLM 모델 (예: "openai/gpt-4o-mini")
- `max_search_results`: 검색 도구의 최대 결과 수

#### `graph.py` - 그래프 아키텍처
- StateGraph 빌더를 통해 노드와 엣지 정의
- ReAct 패턴의 핵심 실행 흐름 구현
- 조건부 라우팅 로직 (도구 호출 vs 종료)

#### `prompts.py` - 프롬프트 템플릿
- 에이전트의 시스템 메시지 정의
- 동적 변수 치환 지원 (예: `{system_time}`)

#### `state.py` - 상태 스키마
- `InputState`: 외부 입력 인터페이스 (사용자 메시지)
- `State`: 전체 실행 상태 (메시지 히스토리, 재귀 제한 플래그)
- `add_messages` 리듀서를 통한 메시지 누적

#### `tools.py` - 도구 정의
- 에이전트가 호출할 수 있는 함수들
- 현재 구현: `search` 도구 (웹 검색 시뮬레이션)
- `Runtime[Context]`를 통해 사용자별 설정 접근

#### `utils.py` - 유틸리티 함수
- `load_chat_model()`: "provider/model" 형식으로 LLM 초기화
- `get_message_text()`: 메시지 객체에서 텍스트 추출

---

## 그래프 아키텍처

### 노드 구성

ReAct Agent는 2개의 노드로 구성됩니다:

#### 1. `call_model` 노드 (추론)
**역할**: LLM을 호출하여 다음 행동을 결정

```python
async def call_model(state: State, runtime: Runtime[Context]) -> dict:
    model = load_chat_model(runtime.context.model).bind_tools(TOOLS)
    system_message = runtime.context.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )
    response = await model.ainvoke(
        [{"role": "system", "content": system_message}, *state.messages]
    )
    return {"messages": [response]}
```

**처리 흐름:**
1. Runtime Context에서 모델 설정 로드
2. 도구 목록을 모델에 바인딩 (도구 호출 가능하도록)
3. 시스템 프롬프트 포맷팅 (현재 시간 주입)
4. LLM 호출 (시스템 메시지 + 대화 히스토리)
5. 응답 반환 (텍스트 답변 또는 도구 호출 요청)

**재귀 제한 처리:**
- `state.is_last_step`가 True인데 LLM이 여전히 도구를 호출하려 하면 강제 종료
- "지정된 스텝 내에 답변을 찾지 못했습니다" 메시지 반환

#### 2. `tools` 노드 (실행)
**역할**: LLM이 선택한 도구를 실제로 실행

```python
builder.add_node("tools", ToolNode(TOOLS))
```

**처리 흐름:**
1. 이전 노드(call_model)의 AIMessage에서 `tool_calls` 추출
2. 각 tool_call에 대해 해당 도구 함수 실행
3. 도구 실행 결과를 ToolMessage로 상태에 추가
4. 자동으로 call_model 노드로 복귀

### 엣지 정의

```
__start__ → call_model ⇄ tools
                ↓
            __end__
```

#### 1. 진입 엣지
```python
builder.add_edge("__start__", "call_model")
```
- 그래프 시작 시 항상 `call_model` 노드부터 실행

#### 2. 조건부 엣지 (call_model 출력)
```python
def route_model_output(state: State) -> Literal["__end__", "tools"]:
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(f"Expected AIMessage, got {type(last_message).__name__}")

    if not last_message.tool_calls:
        return "__end__"  # 도구 호출 없음 → 종료

    return "tools"  # 도구 호출 있음 → 도구 실행

builder.add_conditional_edges("call_model", route_model_output)
```

**라우팅 로직:**
- **도구 호출 있음** → `tools` 노드로 이동 (Action 단계)
- **도구 호출 없음** → `__end__`로 이동 (최종 답변 완성)

#### 3. 고정 엣지 (tools → call_model)
```python
builder.add_edge("tools", "call_model")
```
- 도구 실행 완료 후 항상 `call_model`로 복귀
- ReAct 사이클 구현: Action → Observation → Thought

### 상태 관리

#### InputState (입력 인터페이스)
```python
@dataclass
class InputState:
    messages: Annotated[Sequence[AnyMessage], add_messages] = field(default_factory=list)
```
- 외부에서 들어오는 입력 데이터 구조
- 사용자 메시지만 포함

#### State (전체 실행 상태)
```python
@dataclass
class State(InputState):
    is_last_step: IsLastStep = field(default=False)
```
- InputState를 확장하여 실행 제어 정보 추가
- `is_last_step`: LangGraph가 관리하는 재귀 제한 플래그

**add_messages 리듀서:**
- 메시지를 "추가 전용(append-only)" 방식으로 누적
- 동일한 ID를 가진 메시지는 업데이트 (덮어쓰기)
- 메시지 수정 및 재시도 패턴 지원

---

## 실행 흐름

### 일반적인 대화 흐름 예시

사용자가 "오늘 날씨는 어때?"라고 질문하는 경우:

```
Step 1: __start__ → call_model
├─ 입력: HumanMessage("오늘 날씨는 어때?")
├─ LLM 분석: "날씨 정보를 얻기 위해 검색 도구 필요"
└─ 출력: AIMessage(tool_calls=[{"name": "search", "args": {"query": "오늘 날씨"}}])

Step 2: call_model → tools (조건부 엣지)
├─ 판단: tool_calls 존재 → tools 노드로 이동
└─ 도구 실행: search("오늘 날씨")

Step 3: tools 노드 실행
├─ 검색 도구 호출
├─ 결과 반환: "오늘은 맑고 기온은 22도입니다"
└─ 출력: ToolMessage(content="오늘은 맑고 기온은 22도입니다")

Step 4: tools → call_model (고정 엣지)
├─ 도구 실행 결과를 LLM에 전달
├─ LLM이 결과를 분석하여 최종 답변 생성
└─ 출력: AIMessage("오늘은 맑은 날씨이며 기온은 22도입니다.")

Step 5: call_model → __end__ (조건부 엣지)
├─ 판단: tool_calls 없음 → 최종 답변 완성
└─ 그래프 종료
```

### 메시지 누적 패턴

각 단계마다 상태의 `messages` 리스트에 메시지가 누적됩니다:

```python
[
    HumanMessage(content="오늘 날씨는 어때?"),
    AIMessage(content="", tool_calls=[...]),           # 도구 호출 요청
    ToolMessage(content="검색 결과..."),               # 도구 실행 결과
    AIMessage(content="오늘은 맑은 날씨입니다."),      # 최종 답변
]
```

### 재귀 제한 처리

LangGraph는 기본적으로 25회의 재귀 제한(recursion_limit)을 적용합니다:

```python
if state.is_last_step and response.tool_calls:
    return {
        "messages": [
            AIMessage(
                content="Sorry, I could not find an answer to your question "
                        "in the specified number of steps."
            )
        ]
    }
```

**동작 방식:**
1. 스텝 카운트가 `recursion_limit - 1`에 도달하면 `is_last_step = True`
2. `call_model` 노드에서 이를 감지하여 강제 종료
3. 다음 스텝에서 `recursion_limit` 도달 시 `RecursionError` 발생 방지

---

## 커스터마이징

### 1. 프롬프트 변경

**방법 A: prompts.py 수정**

```python
# graphs/react_agent/prompts.py
SYSTEM_PROMPT = """You are an expert research assistant.
You have access to various tools to help answer questions.

System time: {system_time}

Instructions:
- Always verify information using available tools
- Provide detailed and accurate responses
- Cite sources when possible
"""
```

**방법 B: 환경 변수로 오버라이드**

```bash
# .env 파일
SYSTEM_PROMPT="You are a specialized financial advisor. System time: {system_time}"
```

### 2. 모델 변경

**방법 A: context.py 기본값 수정**

```python
# graphs/react_agent/context.py
@dataclass(kw_only=True)
class Context:
    model: str = field(
        default="anthropic/claude-3-5-sonnet-20241022",  # 기본 모델 변경
        metadata={"description": "..."}
    )
```

**방법 B: 환境 변수 사용**

```bash
# .env 파일
MODEL=anthropic/claude-3-5-sonnet-20241022
```

**방법 C: API 요청 시 지정**

```bash
curl -X POST http://localhost:8000/threads/{thread_id}/runs \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "react_agent",
    "input": {"messages": [{"role": "user", "content": "Hello"}]},
    "config": {"configurable": {"model": "anthropic/claude-3-5-sonnet-20241022"}}
  }'
```

### 3. 도구 추가

**Step 1: tools.py에 새 도구 함수 정의**

```python
# graphs/react_agent/tools.py
from langgraph.runtime import get_runtime
from react_agent.context import Context

async def calculator(expression: str) -> dict[str, Any]:
    """수학 표현식을 계산합니다.

    Args:
        expression (str): 계산할 수학 표현식 (예: "2 + 2 * 3")

    Returns:
        dict: 계산 결과를 포함한 딕셔너리
    """
    try:
        result = eval(expression)  # 주의: 프로덕션에서는 안전한 파서 사용
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"expression": expression, "error": str(e)}

async def get_current_time() -> dict[str, str]:
    """현재 시간을 반환합니다."""
    from datetime import datetime, UTC
    now = datetime.now(tz=UTC)
    return {
        "current_time": now.isoformat(),
        "timestamp": int(now.timestamp())
    }
```

**Step 2: TOOLS 리스트에 추가**

```python
# graphs/react_agent/tools.py
TOOLS: list[Callable[..., Any]] = [
    search,
    calculator,        # 추가
    get_current_time,  # 추가
]
```

**Step 3: Context에 도구별 설정 추가 (선택사항)**

```python
# graphs/react_agent/context.py
@dataclass(kw_only=True)
class Context:
    system_prompt: str = field(default=prompts.SYSTEM_PROMPT, metadata={...})
    model: str = field(default="openai/gpt-4o-mini", metadata={...})
    max_search_results: int = field(default=10, metadata={...})

    # 새 도구 설정 추가
    enable_calculator: bool = field(
        default=True,
        metadata={"description": "Enable calculator tool for math operations"}
    )
```

### 4. 도구에서 Context 사용

```python
# graphs/react_agent/tools.py
async def search(query: str) -> dict[str, Any]:
    runtime = get_runtime(Context)  # Runtime Context 가져오기
    max_results = runtime.context.max_search_results  # 설정값 사용

    # 실제 Tavily API 호출 (예시)
    from tavily import TavilyClient
    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    results = client.search(query, max_results=max_results)

    return {
        "query": query,
        "results": results
    }
```

### 5. 재귀 제한 조정

재귀 제한은 open_langgraph.json 또는 API 요청에서 설정할 수 있습니다:

**open_langgraph.json 설정:**

```json
{
  "graphs": {
    "react_agent": "./graphs/react_agent/__init__.py:graph"
  },
  "default_config": {
    "recursion_limit": 50
  }
}
```

**API 요청에서 설정:**

```bash
curl -X POST http://localhost:8000/threads/{thread_id}/runs \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "react_agent",
    "input": {"messages": [{"role": "user", "content": "복잡한 질문"}]},
    "config": {"recursion_limit": 50}
  }'
```

---

## 사용 예제

### 1. open_langgraph.json 등록

ReAct Agent를 서버에 등록하려면 `open_langgraph.json`에 추가합니다:

```json
{
  "graphs": {
    "react_agent": "./graphs/react_agent/__init__.py:graph"
  },
  "auth": {
    "path": "./auth.py:auth"
  },
  "env": ".env"
}
```

### 2. 서버 실행

```bash
# 개발 서버 시작
uv run uvicorn src.agent_server.main:app --reload

# 또는 Docker 사용
docker compose up open-langgraph
```

### 3. 어시스턴트 조회

ReAct Agent는 자동으로 기본 어시스턴트가 생성됩니다:

```bash
curl http://localhost:8000/assistants

# 응답 예시:
{
  "data": [
    {
      "assistant_id": "react_agent",
      "graph_id": "react_agent",
      "name": "ReAct Agent",
      "description": "Reasoning and Action agent",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 4. 스레드 생성

```bash
curl -X POST http://localhost:8000/threads \
  -H "Content-Type: application/json" \
  -d '{}'

# 응답 예시:
{
  "thread_id": "abc-123-def-456",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 5. 실행 (Run) 생성 및 스트리밍

**Non-streaming (일반 실행):**

```bash
curl -X POST http://localhost:8000/threads/abc-123-def-456/runs \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "react_agent",
    "input": {
      "messages": [
        {
          "role": "user",
          "content": "What is the weather today in Seoul?"
        }
      ]
    }
  }'
```

**Server-Sent Events (SSE) 스트리밍:**

```bash
curl -X POST http://localhost:8000/threads/abc-123-def-456/runs/stream \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "react_agent",
    "input": {
      "messages": [
        {
          "role": "user",
          "content": "Tell me about LangGraph"
        }
      ]
    }
  }'
```

**스트리밍 응답 예시:**

```
event: metadata
data: {"run_id": "run-123"}

event: messages/partial
data: {"content": "Let me search for information"}

event: messages/complete
data: {"role": "assistant", "content": "...", "tool_calls": [...]}

event: tools/start
data: {"tool": "search", "input": {"query": "LangGraph"}}

event: tools/complete
data: {"tool": "search", "output": "LangGraph is..."}

event: messages/complete
data: {"role": "assistant", "content": "LangGraph is a framework for building..."}

event: end
data: {}
```

### 6. 실행 상태 조회

```bash
curl http://localhost:8000/threads/abc-123-def-456/runs/run-123

# 응답 예시:
{
  "run_id": "run-123",
  "thread_id": "abc-123-def-456",
  "assistant_id": "react_agent",
  "status": "success",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:05Z"
}
```

### 7. 스레드 상태 조회

```bash
curl http://localhost:8000/threads/abc-123-def-456/state

# 응답 예시:
{
  "values": {
    "messages": [
      {
        "role": "user",
        "content": "What is the weather today?"
      },
      {
        "role": "assistant",
        "content": "",
        "tool_calls": [
          {
            "id": "call_123",
            "name": "search",
            "args": {"query": "weather today"}
          }
        ]
      },
      {
        "role": "tool",
        "content": "Sunny, 22°C",
        "tool_call_id": "call_123"
      },
      {
        "role": "assistant",
        "content": "Today's weather is sunny with a temperature of 22°C."
      }
    ]
  },
  "next": []
}
```

### 8. Python 클라이언트 사용

```python
import httpx
import json

async def run_react_agent():
    base_url = "http://localhost:8000"

    # 1. 스레드 생성
    async with httpx.AsyncClient() as client:
        thread_resp = await client.post(f"{base_url}/threads")
        thread_id = thread_resp.json()["thread_id"]

        # 2. 실행 요청 (스트리밍)
        async with client.stream(
            "POST",
            f"{base_url}/threads/{thread_id}/runs/stream",
            json={
                "assistant_id": "react_agent",
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": "What's 25 * 4 + 17?"
                        }
                    ]
                },
                "config": {
                    "configurable": {
                        "model": "openai/gpt-4o-mini"
                    }
                }
            }
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    print(f"Event: {data}")

# 실행
import asyncio
asyncio.run(run_react_agent())
```

### 9. 커스텀 설정으로 실행

```bash
curl -X POST http://localhost:8000/threads/abc-123-def-456/runs \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "react_agent",
    "input": {
      "messages": [
        {"role": "user", "content": "Research quantum computing"}
      ]
    },
    "config": {
      "configurable": {
        "model": "anthropic/claude-3-5-sonnet-20241022",
        "max_search_results": 15,
        "system_prompt": "You are an expert in quantum physics. System time: {system_time}"
      },
      "recursion_limit": 30
    }
  }'
```

---

## 고급 사용 패턴

### 1. 멀티턴 대화

ReAct Agent는 대화 히스토리를 자동으로 유지합니다:

```bash
# 첫 번째 질문
curl -X POST http://localhost:8000/threads/{thread_id}/runs \
  -d '{"assistant_id": "react_agent", "input": {"messages": [{"role": "user", "content": "What is LangGraph?"}]}}'

# 후속 질문 (같은 thread_id 사용)
curl -X POST http://localhost:8000/threads/{thread_id}/runs \
  -d '{"assistant_id": "react_agent", "input": {"messages": [{"role": "user", "content": "How is it different from LangChain?"}]}}'
```

에이전트는 이전 대화 컨텍스트를 기억하고 "it"이 LangGraph를 지칭함을 이해합니다.

### 2. 메타데이터 추가

```bash
curl -X POST http://localhost:8000/threads \
  -d '{
    "metadata": {
      "user_id": "user-123",
      "session_type": "support",
      "priority": "high"
    }
  }'
```

### 3. 이벤트 리플레이

스트리밍 중 연결이 끊겼을 때 이벤트를 재생할 수 있습니다:

```bash
curl "http://localhost:8000/threads/{thread_id}/runs/{run_id}/stream?after_event_id=event-42"
```

### 4. 관찰성 (Langfuse 통합)

Langfuse를 활성화하면 모든 실행이 자동으로 추적됩니다:

```bash
# .env 파일
LANGFUSE_LOGGING=true
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

LangGraph 실행, 도구 호출, 토큰 사용량 등이 Langfuse 대시보드에 표시됩니다.

---

## 트러블슈팅

### 문제 1: "Expected AIMessage in output edges" 오류

**원인**: `route_model_output` 함수에서 마지막 메시지가 AIMessage가 아님

**해결**:
- `call_model` 노드가 항상 AIMessage를 반환하는지 확인
- 커스텀 노드를 추가한 경우 메시지 타입 검증

### 문제 2: 도구가 호출되지 않음

**원인**: 모델이 도구 호출을 지원하지 않거나 도구 바인딩 실패

**해결**:
```python
# utils.py에서 지원되는 모델인지 확인
# 도구 호출 지원 모델 예시:
# - openai/gpt-4, gpt-3.5-turbo
# - anthropic/claude-3-sonnet, claude-3-opus
# - google/gemini-pro
```

### 문제 3: RecursionError 발생

**원인**: `recursion_limit` 초과

**해결**:
```bash
# 재귀 제한 증가
curl -X POST http://localhost:8000/threads/{thread_id}/runs \
  -d '{"config": {"recursion_limit": 50}, ...}'
```

### 문제 4: 환경 변수가 적용되지 않음

**원인**: `Context.__post_init__`에서 환경 변수 로드 실패

**해결**:
```python
# context.py에서 디버깅
def __post_init__(self) -> None:
    for f in fields(self):
        if not f.init:
            continue
        print(f"Field: {f.name}, Default: {f.default}, Current: {getattr(self, f.name)}")
        env_value = os.environ.get(f.name.upper())
        print(f"Env value for {f.name.upper()}: {env_value}")
```

---

## 참고 자료

- **LangGraph 공식 문서**: https://langchain-ai.github.io/langgraph/
- **ReAct 논문**: [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- **Open LangGraph 프로젝트 CLAUDE.md**: `/Users/jhj/Desktop/personal/opensource-langgraph-platform/CLAUDE.md`
- **LangGraph 도구 호출 가이드**: https://langchain-ai.github.io/langgraph/how-tos/tool-calling/

---

## 다음 단계

ReAct Agent를 이해했다면 다음 고급 패턴을 탐색해보세요:

1. **graphs/react_agent_hitl/**: Human-in-the-Loop 패턴 (사용자 승인 필요)
2. **graphs/subgraph_agent/**: 서브그래프 합성 패턴 (복잡한 워크플로우)
3. **커스텀 그래프 생성**: 프로젝트 요구사항에 맞는 새로운 그래프 설계

---

## 라이선스

이 코드는 Open LangGraph 프로젝트의 일부로 MIT 라이선스 하에 제공됩니다.
