# Subgraph Agent (서브그래프 에이전트)

## 개요

**Subgraph Agent**는 기존 LangGraph 그래프를 노드로 재사용하는 서브그래프 구성(composition) 패턴을 보여주는 예제입니다. 이 패턴을 통해 복잡한 에이전트 시스템을 모듈화된 구조로 구축할 수 있으며, 기존 그래프를 새로운 워크플로우의 일부로 통합할 수 있습니다.

### 서브그래프 패턴의 장점

- **재사용성**: 기존 그래프(`react_agent`)를 노드로 삽입하여 재사용
- **모듈성**: 복잡한 로직을 독립적인 서브그래프로 분리
- **유지보수성**: 각 서브그래프를 독립적으로 개발 및 테스트 가능
- **구성 가능성**: 여러 서브그래프를 조합하여 복잡한 워크플로우 구축

### 그래프 구조

```
__start__ → no_stream → subgraph_agent → __end__
```

메인 그래프는 전처리 노드(`no_stream`)를 거쳐 서브그래프(`react_agent`)를 실행하고 최종 결과를 반환하는 선형 구조입니다.

## 파일 구조

### 1. `__init__.py`

모듈 진입점으로 `graph` 객체를 export합니다.

**주요 내용:**
- 서브그래프 구성 패턴 개요
- `subgraph_agent` 노드 - `react_agent` 그래프를 서브그래프로 실행
- `no_stream` 노드 - 스트리밍 비활성화 태그를 사용한 LLM 호출

### 2. `graph.py`

서브그래프를 포함하는 메인 그래프를 정의합니다.

**주요 구성 요소:**

#### 노드 함수

**`no_stream(state, runtime)`**
- `langsmith:nostream` 태그와 함께 LLM을 호출하는 전처리 노드
- 서브그래프로 전달하기 전에 초기 응답 생성
- LangSmith 추적에서 스트리밍 없이 전체 응답을 한 번에 기록

**동작 흐름:**
1. Runtime Context에서 모델 설정 및 시스템 프롬프트 로드
2. `langsmith:nostream` 태그와 함께 채팅 모델 초기화
3. 현재 UTC 시각을 시스템 프롬프트에 포맷팅
4. 시스템 메시지와 대화 이력을 결합하여 LLM 호출
5. LLM 응답을 메시지 목록에 추가하여 반환

**`subgraph_agent` 노드**
- `react_agent.graph`를 직접 노드로 추가
- LangGraph는 컴파일된 그래프를 노드로 사용 가능
- 서브그래프는 메인 그래프의 상태를 받아 실행 후 업데이트된 상태를 반환

#### 그래프 빌더

```python
builder = StateGraph(State, input_schema=InputState, context_schema=Context)
```

`react_agent`와 동일한 `State`, `InputState`, `Context`를 사용하여 서브그래프와 메인 그래프 간의 원활한 데이터 흐름을 보장합니다.

## 서브그래프 통합 방식

### 1. 동일한 State 구조 사용

메인 그래프와 서브그래프는 동일한 `State`, `InputState`, `Context`를 공유합니다:

```python
from react_agent.context import Context
from react_agent.state import InputState, State
from react_agent import graph as react_graph
```

이를 통해 상태 전달 시 변환 없이 직접 데이터가 흐를 수 있습니다.

### 2. 서브그래프 노드 추가

컴파일된 그래프를 노드로 직접 추가:

```python
builder.add_node("subgraph_agent", react_graph)
```

LangGraph는 서브그래프를 일반 노드처럼 처리하며, 메인 그래프의 상태를 입력으로 전달하고 업데이트된 상태를 반환받습니다.

### 3. 엣지 연결

```python
builder.add_edge("__start__", "no_stream")      # 시작 → 전처리
builder.add_edge("no_stream", "subgraph_agent") # 전처리 → 서브그래프
builder.add_edge("subgraph_agent", "__end__")   # 서브그래프 → 종료
```

## 데이터 흐름

### State 공유 패턴

```
1. 입력 메시지 → InputState
2. no_stream 노드 실행
   - 시스템 프롬프트 + 메시지 이력 → LLM 호출
   - AIMessage 추가 → State 업데이트
3. 업데이트된 State → subgraph_agent (react_agent 그래프)
   - react_agent의 ReAct 사이클 실행
   - 도구 호출 및 추론 반복
   - 최종 AIMessage 생성
4. 최종 State → __end__
```

### Runtime Context 전달

메인 그래프와 서브그래프 모두 동일한 `Runtime[Context]`를 공유:

- **모델 설정**: `runtime.context.model`
- **시스템 프롬프트**: `runtime.context.system_prompt`
- **검색 결과 제한**: `runtime.context.max_search_results`

## 스트리밍 제어

### langsmith:nostream 태그

`no_stream` 노드는 `langsmith:nostream` 태그를 사용하여 특정 LLM 호출의 스트리밍을 비활성화합니다:

```python
model = load_chat_model(runtime.context.model).with_config(
    config={"tags": ["langsmith:nostream"]}
)
```

**효과:**
- LangSmith 대시보드에서 스트리밍 이벤트 없이 완료된 응답만 표시
- 클라이언트는 해당 노드의 중간 이벤트를 받지 않음
- 서브그래프 실행 전 초기 컨텍스트 설정에 유용

### 서브그래프 스트리밍

API 호출 시 `stream_subgraphs` 파라미터로 제어:

**기본 동작 (stream_subgraphs=False):**
```python
stream = client.runs.stream(
    thread_id=thread_id,
    assistant_id=assistant_id,
    input={"messages": [...]},
    stream_mode=["messages", "values"]
)
```
- `subgraph_agent` 노드의 이벤트만 수신
- 서브그래프 내부 노드(`call_model`, `tools`)는 스트리밍되지 않음

**서브그래프 스트리밍 활성화 (stream_subgraphs=True):**
```python
stream = client.runs.stream(
    thread_id=thread_id,
    assistant_id=assistant_id,
    input={"messages": [...]},
    stream_mode=["messages", "values"],
    stream_subgraphs=True  # 서브그래프 내부 이벤트도 스트리밍
)
```
- 서브그래프의 모든 노드 이벤트 수신 가능
- `call_model`, `tools` 등 내부 노드의 실행 과정 추적 가능

## 커스터마이징 가이드

### 1. 다른 서브그래프 사용

`react_agent` 대신 다른 그래프를 사용하려면:

```python
# 다른 그래프 임포트
from other_agent import graph as other_graph

# 노드로 추가
builder.add_node("my_subgraph", other_graph)
```

**주의사항:**
- 서브그래프와 메인 그래프의 State 구조가 호환되어야 함
- 필요시 State 변환 노드 추가

### 2. 전처리 노드 커스터마이징

`no_stream` 노드를 수정하여 다른 전처리 로직 추가:

```python
async def custom_preprocessing(
    state: State, runtime: Runtime[Context]
) -> dict[str, list[AIMessage]]:
    # 커스텀 전처리 로직
    # 예: 입력 검증, 데이터 변환, 외부 API 호출 등

    model = load_chat_model(runtime.context.model)
    # ... 커스텀 로직
    return {"messages": [response]}

builder.add_node("preprocessing", custom_preprocessing)
```

### 3. 후처리 노드 추가

서브그래프 실행 후 추가 처리가 필요한 경우:

```python
async def postprocessing(state: State) -> dict:
    # 서브그래프 결과 후처리
    last_message = state.messages[-1]
    # ... 후처리 로직
    return {"messages": [...]}

builder.add_node("postprocessing", postprocessing)
builder.add_edge("subgraph_agent", "postprocessing")
builder.add_edge("postprocessing", "__end__")
```

### 4. 여러 서브그래프 조합

복잡한 워크플로우를 위해 여러 서브그래프를 순차 또는 병렬로 실행:

```python
from react_agent import graph as react_graph
from another_agent import graph as another_graph

builder.add_node("agent1", react_graph)
builder.add_node("agent2", another_graph)

# 순차 실행
builder.add_edge("agent1", "agent2")

# 또는 조건부 분기
def route_to_agent(state: State) -> str:
    # 상태에 따라 다른 서브그래프 선택
    if needs_react_agent(state):
        return "agent1"
    return "agent2"

builder.add_conditional_edges("preprocessing", route_to_agent)
```

## 사용 예제

### 1. 기본 실행

```python
from subgraph_agent import graph

# 서브그래프를 포함한 복합 그래프 실행
result = await graph.ainvoke({
    "messages": [
        {"role": "user", "content": "What's the weather like?"}
    ]
})

print(result["messages"][-1].content)
```

### 2. API를 통한 실행

open_langgraph.json에 등록된 그래프로 실행:

```python
# Assistant 생성
assistant = await client.assistants.create(
    graph_id="subgraph_agent",
    if_exists="do_nothing"
)

# Thread 생성
thread = await client.threads.create()

# Run 생성 및 스트리밍
stream = client.runs.stream(
    thread_id=thread["thread_id"],
    assistant_id=assistant["assistant_id"],
    input={
        "messages": [
            {"role": "user", "content": "Hello!"}
        ]
    },
    stream_mode=["messages", "values"]
)

async for chunk in stream:
    print(chunk)
```

### 3. 서브그래프 내부 스트리밍

서브그래프의 세부 실행 과정을 확인:

```python
stream = client.runs.stream(
    thread_id=thread_id,
    assistant_id=assistant_id,
    input={
        "messages": [
            {"role": "user", "content": "Complex query requiring multiple steps"}
        ]
    },
    stream_mode=["messages", "values"],
    stream_subgraphs=True  # 서브그래프 내부 이벤트 포함
)

langgraph_node_counts = {}

async for chunk in stream:
    # 이벤트의 langgraph_node 추적
    if hasattr(chunk, 'langgraph_node'):
        node = chunk.langgraph_node
        langgraph_node_counts[node] = langgraph_node_counts.get(node, 0) + 1

# stream_subgraphs=True일 때: call_model, tools 이벤트 수신
# stream_subgraphs=False일 때: subgraph_agent 이벤트만 수신
print(langgraph_node_counts)
```

### 4. Runtime Context 커스터마이징

```python
from react_agent.context import Context

# 커스텀 컨텍스트로 실행
custom_context = Context(
    model="anthropic/claude-3-5-sonnet-20241022",
    system_prompt="You are a helpful assistant specializing in weather.",
    max_search_results=5
)

result = await graph.ainvoke(
    {"messages": [{"role": "user", "content": "Check the weather"}]},
    config={"context": custom_context}
)
```

## 구현 세부사항

### State 구조 (`react_agent.state`)

```python
@dataclass
class InputState:
    messages: Annotated[Sequence[AnyMessage], add_messages] = field(default_factory=list)

@dataclass
class State(InputState):
    is_last_step: IsLastStep = field(default=False)
```

- **messages**: `add_messages` 리듀서로 관리되는 대화 이력
- **is_last_step**: LangGraph가 관리하는 재귀 제한 플래그

### Context 구조 (`react_agent.context`)

```python
@dataclass(kw_only=True)
class Context:
    system_prompt: str = field(default=prompts.SYSTEM_PROMPT)
    model: str = field(default="openai/gpt-4o-mini")
    max_search_results: int = field(default=10)
```

환경 변수로 오버라이드 가능:
- `SYSTEM_PROMPT`
- `MODEL`
- `MAX_SEARCH_RESULTS`

### 서브그래프 실행 메커니즘

LangGraph는 서브그래프를 다음과 같이 처리합니다:

1. 메인 그래프가 `subgraph_agent` 노드 도달
2. 현재 State를 서브그래프의 입력으로 전달
3. 서브그래프(`react_agent`)가 독립적으로 실행:
   - ReAct 사이클 수행
   - 도구 호출 및 LLM 추론 반복
   - 최종 AIMessage 생성
4. 서브그래프의 출력 State를 메인 그래프로 반환
5. 메인 그래프가 다음 노드로 진행 (이 경우 `__end__`)

## 테스트

서브그래프 동작을 검증하는 E2E 테스트:

### 1. 이벤트 필터링 테스트

`tests/e2e/test_streaming/test_event_filtering_and_subgraphs.py::test_langsmith_nostream_event_filtering_e2e`

- `langsmith:nostream` 태그가 적용된 `no_stream` 노드의 이벤트가 필터링되는지 확인
- `subgraph_agent` 노드의 이벤트는 정상적으로 수신되는지 검증

### 2. 서브그래프 스트리밍 테스트

`tests/e2e/test_streaming/test_event_filtering_and_subgraphs.py::test_subgraphs_streaming_parameter_e2e`

- `stream_subgraphs=True` 파라미터가 올바르게 동작하는지 확인
- 서브그래프 내부 노드(`call_model`)의 이벤트가 수신되는지 검증

## 관련 문서

- **React Agent**: `/graphs/react_agent/AGENTS.md` - 서브그래프로 사용되는 기본 ReAct 에이전트
- **HITL Agent**: `/graphs/react_agent_hitl/AGENTS.md` - Human-in-the-Loop 패턴 예제
- **Architecture**: `/CLAUDE.md` - 전체 시스템 아키텍처 및 그래프 통합 방식
