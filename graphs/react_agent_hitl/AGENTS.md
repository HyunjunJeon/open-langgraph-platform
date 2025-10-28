# Human-in-the-Loop ReAct Agent

이 디렉토리는 도구 실행 전 사람의 승인을 받는 **Human-in-the-Loop(HITL)** 패턴의 ReAct 에이전트를 구현합니다.

## 개요

### HITL 패턴이란?

Human-in-the-Loop(HITL)은 에이전트가 중요한 액션을 수행하기 전에 사람의 검토와 승인을 받는 패턴입니다. 이 에이전트는 LangGraph의 `interrupt()` 함수를 활용하여 도구 실행 전 실행을 일시 중단하고, 사용자가 다음 중 하나를 선택할 수 있도록 합니다:

- **승인(accept)**: 도구를 원래 인자 그대로 실행
- **수정(edit)**: 도구 인자를 수정한 후 실행
- **응답(response)**: 도구 실행을 취소하고 사용자 메시지로 대체
- **무시(ignore)**: 도구 실행을 취소하고 대화 종료

### 기본 ReAct Agent와의 차이점

| 특징 | react_agent | react_agent_hitl |
|------|-------------|-------------------|
| 도구 실행 | 자동 실행 | 사용자 승인 필요 |
| 인터럽트 | 없음 | `human_approval` 노드 |
| 도구 수정 | 불가능 | 실행 전 인자 수정 가능 |
| 사용자 제어 | 낮음 | 높음 (모든 도구 호출 검토) |

### 동작 흐름

```
시작
  ↓
call_model (LLM이 도구 호출 결정)
  ↓
도구 호출 있음?
  ├─ 예 → human_approval (인터럽트, 사용자 승인 대기)
  │         ↓
  │      사용자 응답 처리
  │         ├─ accept → tools (도구 실행) → call_model
  │         ├─ edit → tools (수정된 인자로 실행) → call_model
  │         ├─ response → call_model (사용자 메시지와 함께)
  │         └─ ignore → END (종료)
  │
  └─ 아니오 → END (최종 응답)
```

## 파일 구조

### 1. `__init__.py`
**역할**: 패키지 진입점 및 그래프 내보내기

```python
from react_agent_hitl.graph import graph

__all__ = ["graph"]
```

- `graph` 객체를 외부에 노출하여 `open_langgraph.json`에서 참조 가능
- 패키지 수준의 문서화 제공

### 2. `context.py`
**역할**: 런타임 설정 컨텍스트 정의

**주요 구성 요소**:
- `Context` dataclass: 에이전트 실행 시 필요한 설정 파라미터
  - `system_prompt`: 에이전트 행동 정의
  - `model`: 사용할 언어 모델 (예: `"openai/gpt-4o-mini"`)
  - `max_search_results`: 검색 결과 최대 개수

**특징**:
- 환경 변수 자동 로드: `__post_init__`에서 환경 변수 우선 적용
- LangGraph 템플릿 시스템 통합: `model` 필드에 메타데이터 어노테이션
- `Runtime[Context]` 패턴으로 그래프 노드에서 접근 가능

**사용 예**:
```python
async def call_model(state: State, runtime: Runtime[Context]):
    model = load_chat_model(runtime.context.model)
    prompt = runtime.context.system_prompt.format(...)
```

### 3. `state.py`
**역할**: 그래프 상태 구조 정의

**주요 구성 요소**:
- `InputState`: 외부 인터페이스 (클라이언트가 제공하는 입력)
  - `messages`: 대화 메시지 히스토리 (add_messages 리듀서 사용)

- `State`: 완전한 내부 상태 (InputState 확장)
  - `is_last_step`: 재귀 한계 도달 여부 (LangGraph 관리 변수)

**메시지 누적 패턴**:
1. `HumanMessage` - 사용자 입력
2. `AIMessage` (tool_calls 포함) - 에이전트의 도구 호출 요청
3. **[인터럽트 발생]** - 사용자 승인 대기
4. `ToolMessage(s)` - 도구 실행 결과 또는 취소 메시지
5. `AIMessage` (tool_calls 없음) - 최종 응답
6. `HumanMessage` - 다음 대화 턴

**인터럽트 시 상태 처리**:
- `interrupt()` 호출 시 현재 상태가 체크포인트에 보존됨
- 사용자가 도구를 수정하면 AIMessage가 업데이트됨
- 사용자가 응답을 선택하면 HumanMessage가 추가됨

### 4. `graph.py`
**역할**: 핵심 그래프 로직 및 HITL 메커니즘 구현

**주요 노드**:

#### `call_model(state: State, runtime: Runtime[Context])`
LLM을 호출하여 다음 액션 결정
- 도구 목록을 모델에 바인딩
- 시스템 프롬프트 포맷팅 (현재 시간 포함)
- 재귀 한계 도달 시 에러 메시지 반환

#### `human_approval(state: State)` ⭐
**핵심 인터럽트 지점**

도구 실행 전 사용자 승인 요청

**동작 흐름**:
1. 도구 호출이 포함된 가장 최근 AI 메시지 찾기
2. `interrupt()` 호출로 실행 일시 중단
   ```python
   human_response = interrupt({
       "action_request": {
           "action": "tool_execution",
           "args": {tc["name"]: tc.get("args", {}) for tc in tool_message.tool_calls}
       },
       "config": {
           "allow_respond": True,
           "allow_accept": True,
           "allow_edit": True,
           "allow_ignore": True
       }
   })
   ```
3. 사용자 응답 대기 (체크포인트에 상태 저장됨)
4. 사용자 응답에 따라 분기 처리

#### `route_model_output(state: State)`
모델 출력에 따라 다음 노드 결정
- 도구 호출 있음 → `human_approval`
- 도구 호출 없음 → `END`

**헬퍼 함수들**:
- `_find_tool_message()`: 도구 호출이 포함된 최근 AI 메시지 찾기
- `_create_tool_cancellations()`: 도구 취소 메시지 생성
- `_parse_args()`: JSON 문자열 인자 파싱
- `_update_tool_calls()`: 사용자 수정 인자로 도구 호출 업데이트

**그래프 구조**:
```python
builder = StateGraph(State, input_schema=InputState, context_schema=Context)
builder.add_node(call_model)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_node(human_approval)
builder.add_edge("__start__", "call_model")
builder.add_conditional_edges("call_model", route_model_output, path_map=["human_approval", END])
builder.add_edge("tools", "call_model")
graph = builder.compile(name="ReAct Agent")
```

### 5. `prompts.py`
**역할**: 시스템 프롬프트 템플릿 정의

```python
SYSTEM_PROMPT = """You are a helpful AI assistant.

System time: {system_time}"""
```

- 에이전트의 페르소나 및 행동 방식 정의
- `{system_time}` 변수는 런타임에 동적으로 치환됨
- 프로덕션 환경에서는 더 상세한 프롬프트로 커스터마이징 가능

### 6. `tools.py`
**역할**: 에이전트가 사용할 도구 정의

**주요 구성 요소**:
- `search(query: str)`: 웹 검색 도구
  - Tavily 기반 검색 (현재는 시뮬레이션)
  - `Runtime[Context]`를 통해 `max_search_results` 설정 접근
  - 비동기 함수로 구현

```python
async def search(query: str) -> dict[str, Any] | None:
    runtime = get_runtime(Context)
    return {
        "query": query,
        "max_search_results": runtime.context.max_search_results,
        "results": f"Simulated search results for '{query}'"
    }

TOOLS: list[Callable[..., Any]] = [search]
```

**확장 방법**:
- 새로운 도구 함수를 정의하고 `TOOLS` 리스트에 추가
- 각 도구는 docstring으로 사용법 설명 (LLM이 참조)
- 프로덕션 환경에서는 실제 API 호출로 구현 필요

### 7. `utils.py`
**역할**: 공통 유틸리티 함수

**주요 함수**:

#### `get_message_text(msg: BaseMessage) -> str`
메시지에서 텍스트 콘텐츠 추출
- 단순 문자열, 딕셔너리, 멀티모달 리스트 모두 지원
- 텍스트만 추출하여 반환

#### `load_chat_model(fully_specified_name: str) -> BaseChatModel`
"provider/model" 형식에서 채팅 모델 로드
- 예: `"openai/gpt-4"`, `"anthropic/claude-3-opus"`
- 설정 파일이나 환경 변수로 모델 지정 시 유용

## 인터럽트 메커니즘 상세

### 1. 인터럽트 트리거

```python
human_response = interrupt({
    "action_request": {
        "action": "tool_execution",
        "args": {tc["name"]: tc.get("args", {}) for tc in tool_message.tool_calls}
    },
    "config": {
        "allow_respond": True,   # 사용자가 직접 응답 가능
        "allow_accept": True,    # 도구 승인 가능
        "allow_edit": True,      # 도구 인자 수정 가능
        "allow_ignore": True     # 도구 실행 거부 가능
    }
})
```

### 2. 체크포인트 저장

- LangGraph가 자동으로 현재 상태를 PostgreSQL에 저장
- 스레드 ID와 체크포인트 ID로 나중에 복원 가능
- 메시지 히스토리, 메타데이터 모두 보존됨

### 3. 클라이언트 알림

- SSE(Server-Sent Events) 스트림으로 인터럽트 이벤트 전송
- 이벤트에 `action_request`와 `config` 포함
- 클라이언트는 사용자에게 승인/거부 UI 표시

### 4. 사용자 응답 대기

- 실행이 일시 중단되고 사용자 입력 대기
- 타임아웃 없음 (사용자가 결정할 때까지 대기)
- 스레드는 다른 요청과 독립적으로 관리됨

## 사용자 응답 처리

### 1. Accept (승인)

**요청**:
```json
[{"type": "accept"}]
```

**처리**:
```python
if response_type == "accept":
    return Command(goto="tools")
```

**결과**:
- 도구를 원래 인자 그대로 실행
- `tools` 노드로 라우팅
- 도구 실행 후 `call_model`로 복귀

### 2. Edit (수정)

**요청**:
```json
[{
    "type": "edit",
    "args": {
        "args": {
            "search": {
                "query": "modified search query"
            }
        }
    }
}]
```

**처리**:
```python
elif response_type == "edit" and isinstance(response_args, dict) and "args" in response_args:
    updated_calls = _update_tool_calls(tool_message.tool_calls, response_args)
    updated_message = AIMessage(
        content=tool_message.content,
        tool_calls=updated_calls,
        id=tool_message.id
    )
    return Command(goto="tools", update={"messages": [updated_message]})
```

**결과**:
- 도구 인자가 사용자 제공 값으로 업데이트됨
- 수정된 AIMessage로 상태 업데이트
- 수정된 인자로 도구 실행

### 3. Response (응답)

**요청**:
```json
[{
    "type": "response",
    "args": "I don't think we need to search for that."
}]
```

**처리**:
```python
elif response_type == "response":
    tool_responses = _create_tool_cancellations(
        tool_message.tool_calls, "was interrupted for human input"
    )
    human_message = HumanMessage(content=str(response_args))
    return Command(
        goto="call_model",
        update={"messages": tool_responses + [human_message]}
    )
```

**결과**:
- 도구 호출들이 취소 메시지로 변환됨
- 사용자 텍스트가 HumanMessage로 추가됨
- `call_model`로 라우팅되어 모델이 새로운 컨텍스트로 응답

### 4. Ignore (무시)

**요청**:
```json
[{"type": "ignore"}]
```

**처리**:
```python
else:  # ignore 또는 잘못된 형식
    reason = (
        "cancelled by human operator"
        if response_type == "ignore"
        else "invalid format"
    )
    tool_responses = _create_tool_cancellations(tool_message.tool_calls, reason)
    return Command(goto=END, update={"messages": tool_responses})
```

**결과**:
- 도구 호출들이 취소 메시지로 변환됨
- 그래프 실행 종료 (`END`)
- 대화 중단됨

## 재개 워크플로우

### 1. 초기 실행

```bash
# 스레드 생성 및 실행 시작
POST /threads/{thread_id}/runs
Content-Type: application/json

{
  "assistant_id": "react_agent_hitl",
  "input": {
    "messages": [
      {"role": "user", "content": "Search for latest AI news"}
    ]
  }
}
```

### 2. 인터럽트 이벤트 수신

클라이언트는 SSE 스트림에서 다음 이벤트를 받음:

```json
{
  "event": "interrupt",
  "data": {
    "action_request": {
      "action": "tool_execution",
      "args": {
        "search": {
          "query": "latest AI news"
        }
      }
    },
    "config": {
      "allow_respond": true,
      "allow_accept": true,
      "allow_edit": true,
      "allow_ignore": true
    }
  }
}
```

### 3. 사용자 결정

클라이언트는 사용자에게 승인 UI 표시:
- "도구를 실행하시겠습니까?"
- "도구 인자를 수정하시겠습니까?"
- "직접 응답을 제공하시겠습니까?"
- "도구 실행을 취소하시겠습니까?"

### 4. 실행 재개

사용자가 선택한 응답 타입으로 재개:

```bash
POST /threads/{thread_id}/runs/{run_id}
Content-Type: application/json

[{"type": "accept"}]
# 또는
[{"type": "edit", "args": {"args": {"search": {"query": "modified query"}}}}]
# 또는
[{"type": "response", "args": "I'll answer directly..."}]
# 또는
[{"type": "ignore"}]
```

### 5. 실행 완료

- `accept` 또는 `edit`: 도구 실행 후 모델이 최종 응답 생성
- `response`: 모델이 사용자 메시지를 기반으로 응답 생성
- `ignore`: 실행 즉시 종료

## 사용 예제

### 예제 1: 기본 승인 플로우

**시나리오**: 사용자가 검색을 요청하고, 에이전트의 도구 호출을 승인

1. **사용자 입력**:
   ```
   "What's the weather in Seoul?"
   ```

2. **모델 응답** (도구 호출):
   ```json
   {
     "tool_calls": [{
       "name": "search",
       "args": {"query": "weather Seoul"}
     }]
   }
   ```

3. **인터럽트 발생**:
   - 클라이언트가 승인 요청 수신
   - 사용자에게 "Search for 'weather Seoul'?" 표시

4. **사용자 승인**:
   ```json
   [{"type": "accept"}]
   ```

5. **도구 실행**:
   - 검색 도구가 실행됨
   - 결과가 메시지에 추가됨

6. **최종 응답**:
   ```
   "The current weather in Seoul is..."
   ```

### 예제 2: 도구 인자 수정

**시나리오**: 사용자가 검색 쿼리를 더 구체적으로 수정

1. **사용자 입력**:
   ```
   "Find information about Python"
   ```

2. **모델 응답** (도구 호출):
   ```json
   {
     "tool_calls": [{
       "name": "search",
       "args": {"query": "Python"}
     }]
   }
   ```

3. **인터럽트 발생**:
   - 사용자가 "Python"이 너무 광범위하다고 판단

4. **사용자 수정**:
   ```json
   [{
     "type": "edit",
     "args": {
       "args": {
         "search": {
           "query": "Python programming language latest features 2024"
         }
       }
     }
   }]
   ```

5. **수정된 도구 실행**:
   - 더 구체적인 쿼리로 검색 실행
   - 더 관련성 높은 결과 반환

6. **최종 응답**:
   ```
   "Here are the latest Python features in 2024..."
   ```

### 예제 3: 직접 응답 제공

**시나리오**: 사용자가 도구 실행 대신 직접 답변을 제공

1. **사용자 입력**:
   ```
   "What's 2+2?"
   ```

2. **모델 응답** (도구 호출):
   ```json
   {
     "tool_calls": [{
       "name": "search",
       "args": {"query": "2+2"}
     }]
   }
   ```
   (모델이 불필요하게 검색하려 함)

3. **인터럽트 발생**:
   - 사용자가 검색이 불필요하다고 판단

4. **사용자 응답**:
   ```json
   [{
     "type": "response",
     "args": "The answer is 4. No need to search."
   }]
   ```

5. **모델 재호출**:
   - 도구 취소 메시지 + 사용자 메시지와 함께 모델 호출
   - 모델이 새로운 컨텍스트로 응답 생성

6. **최종 응답**:
   ```
   "You're right! The answer is 4."
   ```

### 예제 4: 도구 실행 취소

**시나리오**: 사용자가 도구 실행을 완전히 거부

1. **사용자 입력**:
   ```
   "Delete all my files"
   ```

2. **모델 응답** (도구 호출):
   ```json
   {
     "tool_calls": [{
       "name": "file_delete",
       "args": {"pattern": "*"}
     }]
   }
   ```

3. **인터럽트 발생**:
   - 위험한 작업 감지
   - 사용자에게 경고 표시

4. **사용자 거부**:
   ```json
   [{"type": "ignore"}]
   ```

5. **실행 종료**:
   - 도구 취소 메시지 추가
   - 그래프 실행 즉시 종료
   - 안전하게 대화 중단

## 프로덕션 고려사항

### 1. 도구 구현

현재 `search` 도구는 시뮬레이션입니다. 실제 환경에서는:

```python
async def search(query: str) -> dict[str, Any] | None:
    runtime = get_runtime(Context)

    # Tavily API 호출
    from tavily import TavilyClient
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

    results = await client.search(
        query=query,
        max_results=runtime.context.max_search_results
    )

    return {
        "query": query,
        "results": results
    }
```

### 2. 시스템 프롬프트 커스터마이징

프로덕션 환경에서는 더 상세한 프롬프트 권장:

```python
SYSTEM_PROMPT = """You are a helpful AI assistant specialized in [domain].

Guidelines:
- Always verify information before making tool calls
- Ask for clarification if the request is ambiguous
- Be mindful of sensitive operations

System time: {system_time}

Available tools:
- search: Find information on the web
- [other tools...]
"""
```

### 3. 타임아웃 처리

인터럽트는 무기한 대기하므로, 애플리케이션 레벨에서 타임아웃 구현 권장:

```python
# 클라이언트 측 타임아웃
timeout = 300  # 5분
if time_since_interrupt > timeout:
    # 자동으로 ignore 응답 전송
    await send_resume([{"type": "ignore"}])
```

### 4. 에러 처리

사용자 응답 형식 검증 강화:

```python
def validate_response(response: dict) -> bool:
    response_type = response.get("type")

    if response_type == "edit":
        # args.args 구조 검증
        if not isinstance(response.get("args"), dict):
            return False
        if "args" not in response["args"]:
            return False

    elif response_type == "response":
        # 텍스트 응답 검증
        if not response.get("args"):
            return False

    return True
```

### 5. 로깅 및 모니터링

인터럽트 지점 추적:

```python
import logging

logger = logging.getLogger(__name__)

async def human_approval(state: State) -> Command:
    logger.info(f"Interrupt triggered for tools: {[tc['name'] for tc in tool_message.tool_calls]}")

    human_response = interrupt(...)

    logger.info(f"User response: {human_response[0].get('type')}")

    # ...처리 로직
```

## 알려진 제한사항

### 1. Command(goto=END) 버그

현재 LangGraph의 알려진 버그로 인해 `Command(goto=END)`가 무한 루프를 생성할 수 있습니다.

- **GitHub 이슈**: https://github.com/langchain-ai/langgraph/issues/5572
- **영향**: `ignore` 응답 타입 처리 시 발생 가능
- **해결 방법**: LangGraph 업데이트 대기 또는 대체 종료 로직 구현

### 2. 다중 도구 호출

모델이 여러 도구를 동시에 호출하는 경우:
- 현재는 모든 도구를 한 번에 승인/거부/수정
- 향후 개선: 도구별로 개별 승인 가능하도록 확장

### 3. 중첩 인터럽트

인터럽트가 진행 중일 때 추가 인터럽트 불가:
- 한 번에 하나의 인터럽트만 처리
- 재개 후 다음 도구 호출에서 새로운 인터럽트 발생

## 참고 자료

- **LangGraph 문서**: https://langchain-ai.github.io/langgraph/
- **Interrupt 가이드**: https://langchain-ai.github.io/langgraph/how-tos/human-in-the-loop/
- **기본 ReAct Agent**: `/graphs/react_agent/AGENTS.md`
- **Agent Protocol Spec**: https://github.com/AI-Engineer-Foundation/agent-protocol

## 다음 단계

1. **open_langgraph.json에 등록**:
   ```json
   {
     "graphs": {
       "react_agent_hitl": "./graphs/react_agent_hitl/__init__.py:graph"
     }
   }
   ```

2. **실제 도구 구현**: `tools.py`에서 Tavily API 통합

3. **커스텀 프롬프트**: 도메인에 맞게 `prompts.py` 수정

4. **UI 구현**: 클라이언트에서 승인/거부 인터페이스 개발

5. **테스트**: 다양한 시나리오로 HITL 플로우 검증
