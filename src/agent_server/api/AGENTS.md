# AGENTS.md - API 레이어 가이드

## 폴더 개요

`src/agent_server/api/` 디렉토리는 Open LangGraph의 **Agent Protocol API 레이어**를 구현합니다. 이 레이어는 LangGraph 기반 에이전트 시스템에 대한 RESTful HTTP 인터페이스를 제공하며, FastAPI 라우터를 통해 클라이언트 요청을 처리하고 서비스 계층으로 위임합니다.

### 역할 및 책임

- **HTTP 엔드포인트 노출**: Agent Protocol 표준을 준수하는 REST API 제공
- **요청/응답 처리**: FastAPI Pydantic 모델을 통한 자동 검증 및 직렬화
- **인증 및 권한**: `get_current_user` 의존성을 통한 사용자 격리 및 보안
- **서비스 오케스트레이션**: 비즈니스 로직을 서비스 계층으로 위임
- **SSE 스트리밍**: 실시간 에이전트 실행 이벤트를 Server-Sent Events로 전달

### 아키텍처 계층

```bash
┌─────────────────────────────────────┐
│     API 레이어 (이 디렉토리)         │  ← HTTP 요청/응답 처리
│   assistants.py, runs.py, etc.      │
├─────────────────────────────────────┤
│      서비스 계층                      │  ← 비즈니스 로직
│   assistant_service.py,              │
│   streaming_service.py, etc.         │
├─────────────────────────────────────┤
│      코어 레이어                      │  ← 인프라 및 공유 컴포넌트
│   database.py, auth_deps.py,         │
│   langgraph_service.py               │
└─────────────────────────────────────┘
```

---

## 파일 목록 및 설명

### 1. `runs.py` - 실행(Run) 엔드포인트

**역할**: LangGraph 그래프 실행을 관리하는 Agent Protocol API 엔드포인트

**주요 기능**:
- 실행 생성 및 비동기 백그라운드 처리
- SSE 스트리밍을 통한 실시간 이벤트 전달
- Human-in-the-Loop (HITL) 중단점 지원
- 이벤트 저장 및 재연결 시 재생
- 실행 취소/중단 및 상태 관리

**핵심 엔드포인트**:
- `POST /threads/{thread_id}/runs` - 실행 생성 (백그라운드)
- `POST /threads/{thread_id}/runs/stream` - 실행 생성 및 스트리밍
- `GET /threads/{thread_id}/runs/{run_id}` - 실행 조회
- `GET /threads/{thread_id}/runs` - 실행 목록 조회
- `PATCH /threads/{thread_id}/runs/{run_id}` - 실행 상태 업데이트
- `GET /threads/{thread_id}/runs/{run_id}/stream` - 실행 스트리밍
- `POST /threads/{thread_id}/runs/{run_id}/cancel` - 실행 취소/중단
- `DELETE /threads/{thread_id}/runs/{run_id}` - 실행 삭제

**특징**:
- PostgreSQL 기반 Run 테이블에 영속화
- `active_runs` 딕셔너리로 백그라운드 Task 추적
- `streaming_service`와 `broker`를 통한 이벤트 조정
- 멀티 스트림 모드 지원 (`values`, `messages`, `updates`, `debug`)

---

### 2. `threads.py` - 스레드(Thread) 엔드포인트

**역할**: LangGraph 기반 대화 스레드의 CRUD 및 상태 관리 API

**주요 기능**:
- 스레드 생성, 조회, 수정, 삭제
- 체크포인트 기반 상태 조회 (특정 시점의 대화 상태)
- 스레드 히스토리 조회 (과거 체크포인트 목록)
- 메타데이터 기반 스레드 검색
- 멀티테넌트 사용자 격리

**핵심 엔드포인트**:
- `POST /threads` - 새 스레드 생성
- `GET /threads` - 사용자의 스레드 목록 조회
- `GET /threads/{thread_id}` - 특정 스레드 조회
- `DELETE /threads/{thread_id}` - 스레드 삭제 (활성 실행 자동 취소)
- `POST /threads/search` - 메타데이터 기반 검색
- `GET /threads/{thread_id}/state/{checkpoint_id}` - 체크포인트 상태 조회
- `POST /threads/{thread_id}/state/checkpoint` - 체크포인트 상태 조회 (SDK 호환)
- `GET /threads/{thread_id}/history` - 스레드 히스토리 조회
- `POST /threads/{thread_id}/history` - 스레드 히스토리 조회 (SDK 호환)

**특징**:
- LangGraph 체크포인터를 통한 상태 영속화
- SQLAlchemy ORM으로 스레드 메타데이터 관리
- `ThreadStateService`를 통한 LangGraph StateSnapshot 변환
- 인증된 사용자별 자동 격리

---

### 3. `assistants.py` - 어시스턴트(Assistant) 엔드포인트

**역할**: Agent Protocol 어시스턴트의 CRUD 및 그래프 스키마 추출 API

**주요 기능**:
- 어시스턴트 생성 (중복 검사 포함)
- 어시스턴트 목록 조회 및 검색
- 어시스턴트 업데이트 (버전 이력 관리)
- 어시스턴트 삭제 및 버전 롤백
- 그래프 스키마 추출 (5가지 타입)
- 그래프 구조 조회 (시각화용)

**핵심 엔드포인트**:
- `POST /assistants` - 어시스턴트 생성
- `GET /assistants` - 어시스턴트 목록 조회
- `POST /assistants/search` - 필터링 및 페이지네이션 검색
- `POST /assistants/count` - 검색 결과 총 개수
- `GET /assistants/{assistant_id}` - 특정 어시스턴트 조회
- `PATCH /assistants/{assistant_id}` - 어시스턴트 업데이트
- `DELETE /assistants/{assistant_id}` - 어시스턴트 삭제
- `POST /assistants/{assistant_id}/latest` - 특정 버전으로 롤백
- `POST /assistants/{assistant_id}/versions` - 버전 이력 조회
- `GET /assistants/{assistant_id}/schemas` - 그래프 스키마 추출
- `GET /assistants/{assistant_id}/graph` - 그래프 구조 조회
- `GET /assistants/{assistant_id}/subgraphs` - 서브그래프 조회

**특징**:
- **계층화된 아키텍처**: 비즈니스 로직을 `assistant_service.py`로 분리
- **버전 이력 관리**: 모든 업데이트를 `assistant_versions` 테이블에 보관
- **그래프 스키마 지원**: input/output/state/config/context 스키마 추출
- **서브그래프 지원**: 중첩된 그래프 구조 조회

---

### 4. `store.py` - 장기 메모리(Store) 엔드포인트

**역할**: LangGraph Store API를 통한 영구 저장소 기능 제공

**주요 기능**:
- 키-값 저장 (네임스페이스 기반 격리)
- 아이템 조회 및 삭제
- 검색 (키워드/시맨틱/하이브리드)
- 사용자별 네임스페이스 자동 스코핑

**핵심 엔드포인트**:
- `PUT /store/items` - 아이템 저장
- `GET /store/items` - 아이템 조회
- `DELETE /store/items` - 아이템 삭제
- `POST /store/items/search` - 아이템 검색

**특징**:
- **LangGraph 공식 Store**: `AsyncPostgresStore`를 직접 사용
- **네임스페이스 격리**: 사용자별 자동 스코핑으로 보안 보장
- **벡터 검색**: 시맨틱/하이브리드 검색 지원 (임베딩 기반)
- **SDK 호환**: dotted 네임스페이스 문자열 및 리스트 형식 모두 지원

---

## 엔드포인트 구조

### REST API 설계 원칙

Open LangGraph의 API는 **Agent Protocol** 표준을 기반으로 설계되었으며, RESTful 패턴을 따릅니다:

```
/assistants          - 어시스턴트 리소스 (에이전트 정의)
/threads             - 스레드 리소스 (대화 세션)
/threads/{id}/runs   - 실행 리소스 (그래프 실행)
/store/items         - 저장소 리소스 (장기 메모리)
```

### HTTP 메서드 규칙

| 메서드 | 용도 | 예시 |
|--------|------|------|
| `GET` | 리소스 조회 | `GET /threads/{thread_id}` |
| `POST` | 리소스 생성 또는 액션 실행 | `POST /threads` |
| `PATCH` | 리소스 부분 업데이트 | `PATCH /assistants/{id}` |
| `PUT` | 리소스 전체 교체 또는 저장 | `PUT /store/items` |
| `DELETE` | 리소스 삭제 | `DELETE /threads/{id}` |

### 응답 코드 규칙

| 코드 | 의미 | 사용 시점 |
|------|------|-----------|
| `200 OK` | 성공 (응답 본문 있음) | GET, PATCH, POST (조회/업데이트) |
| `204 No Content` | 성공 (응답 본문 없음) | DELETE |
| `400 Bad Request` | 잘못된 요청 | 유효성 검증 실패 |
| `404 Not Found` | 리소스 없음 | 존재하지 않는 리소스 접근 |
| `409 Conflict` | 리소스 충돌 | 중복 생성, 활성 실행 삭제 시도 |
| `422 Unprocessable Entity` | 의미적 검증 실패 | 유효하지 않은 파라미터 |

---

## 요청/응답 흐름

### 전형적인 요청 흐름

```
1. 클라이언트 → HTTP 요청 (JSON body)
        ↓
2. FastAPI 라우터 → Pydantic 모델 검증
        ↓
3. 인증 미들웨어 → get_current_user() 의존성 주입
        ↓
4. API 핸들러 → 서비스 계층 호출
        ↓
5. 서비스 계층 → 비즈니스 로직 처리
        ↓
6. 코어 계층 → 데이터베이스/LangGraph 작업
        ↓
7. 서비스 계층 → 결과 반환
        ↓
8. API 핸들러 → Pydantic 응답 모델 직렬화
        ↓
9. FastAPI → HTTP 응답 (JSON)
```

### 계층 간 데이터 흐름 예시 (어시스턴트 생성)

```python
# 1. API 레이어 (assistants.py)
@router.post("/assistants", response_model=Assistant)
async def create_assistant(
    request: AssistantCreate,                      # ← Pydantic 자동 검증
    user: User = Depends(get_current_user),        # ← 인증 의존성 주입
    service: AssistantService = Depends(get_assistant_service),  # ← 서비스 주입
):
    return await service.create_assistant(request, user.identity)

# 2. 서비스 레이어 (assistant_service.py)
async def create_assistant(self, request: AssistantCreate, user_id: str):
    # 그래프 검증
    langgraph_service = get_langgraph_service()
    await langgraph_service.get_graph(request.graph_id)

    # 중복 검사
    existing = await self._find_duplicate(user_id, request)
    if existing and request.if_exists == "error":
        raise HTTPException(409, "Duplicate assistant")

    # 데이터베이스 저장
    async with self.db_session() as session:
        assistant_orm = AssistantORM(...)
        session.add(assistant_orm)
        await session.commit()

    return Assistant.model_validate(...)

# 3. 코어 레이어 (langgraph_service.py)
async def get_graph(self, graph_id: str):
    # open_langgraph.json에서 그래프 로드 및 캐싱
    if graph_id in self.graph_cache:
        return self.graph_cache[graph_id]

    graph = await self._load_and_compile_graph(graph_id)
    self.graph_cache[graph_id] = graph
    return graph
```

### SSE 스트리밍 흐름 (실행 생성 및 스트리밍)

```
1. 클라이언트 → POST /threads/{id}/runs/stream
        ↓
2. API (runs.py) → Run 레코드 생성 (status="streaming")
        ↓
3. API → asyncio.create_task(execute_run_async(...))
        ↓
4. API → StreamingResponse(streaming_service.stream_run_execution(...))
        ↓
5. 백그라운드 Task → graph.astream() 실행
        ↓
6. 백그라운드 Task → 각 이벤트를:
   - streaming_service.put_to_broker() (라이브 스트림)
   - streaming_service.store_event_from_raw() (재생용 저장)
        ↓
7. streaming_service → SSE 이벤트로 직렬화
        ↓
8. 클라이언트 ← text/event-stream 응답 수신
```

---

## 인증 및 권한

### 인증 시스템

Open LangGraph는 **LangGraph SDK Auth** 패턴을 사용하여 요청별 인증 및 사용자 컨텍스트를 관리합니다.

#### 인증 의존성 (`get_current_user`)

모든 API 엔드포인트는 `get_current_user` 의존성을 통해 인증된 사용자를 주입받습니다:

```python
from ..core.auth_deps import get_current_user
from ..models import User

@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    user: User = Depends(get_current_user),  # ← 인증된 사용자 자동 주입
):
    # user.identity로 사용자 격리
    stmt = select(ThreadORM).where(
        ThreadORM.thread_id == thread_id,
        ThreadORM.user_id == user.identity,  # ← 멀티테넌트 격리
    )
    ...
```

#### 인증 흐름

```
1. HTTP 요청 → Authorization 헤더 (Bearer token)
        ↓
2. LangGraph SDK Auth 미들웨어 → 토큰 추출 및 검증
        ↓
3. auth.py → @auth.authenticate 함수 실행
        ↓
4. User 객체 생성 → { identity, metadata, org_id, ... }
        ↓
5. FastAPI 의존성 → get_current_user()가 User 반환
        ↓
6. API 핸들러 → user.identity로 데이터 필터링
```

### 권한 제어

#### 엔드포인트별 보안 정책

| 엔드포인트 | 권한 제어 | 격리 방법 |
|-----------|-----------|-----------|
| `POST /threads` | 사용자별 생성 | `user_id` 컬럼에 저장 |
| `GET /threads/{id}` | 소유자만 조회 | `WHERE user_id = user.identity` |
| `DELETE /threads/{id}` | 소유자만 삭제 | `WHERE user_id = user.identity` |
| `POST /threads/{id}/runs` | 스레드 소유자만 실행 | 스레드 소유권 검증 |
| `GET /store/items` | 네임스페이스 격리 | `apply_user_namespace_scoping()` |

#### 네임스페이스 스코핑 (Store API)

Store API는 네임스페이스 레벨에서 사용자 데이터를 격리합니다:

```python
def apply_user_namespace_scoping(user_id: str, namespace: list[str]) -> list[str]:
    """사용자별 네임스페이스 스코핑을 적용하여 데이터 격리 보장"""
    if not namespace:
        # 기본적으로 사용자 전용 네임스페이스 사용
        return ["users", user_id]

    # 명시적으로 사용자 네임스페이스를 지정한 경우 허용
    if namespace[0] == "users" and len(namespace) >= 2 and namespace[1] == user_id:
        return namespace

    # 개발 환경에서는 모든 네임스페이스 허용 (프로덕션에서는 제거 필요)
    return namespace
```

**보안 권장 사항**:
- 프로덕션 환경에서는 사용자 네임스페이스 외 접근을 차단
- 공유 네임스페이스가 필요한 경우 별도 권한 체크 로직 추가

#### 리소스별 접근 제어 (`auth.py`)

LangGraph SDK Auth의 `@auth.on` 데코레이터를 사용하여 리소스별 권한을 세밀하게 제어할 수 있습니다:

```python
from langgraph_sdk import Auth

@auth.on.assistants.read
async def authorize_assistant_read(ctx: Auth.types.AuthContext):
    """어시스턴트 읽기 권한 검증"""
    # 시스템 어시스턴트 또는 소유자만 조회 가능
    if ctx.resource.assistant_id in system_assistants:
        return ctx
    if ctx.resource.user_id == ctx.user.identity:
        return ctx
    raise Auth.exceptions.HTTPException(403, "Forbidden")

@auth.on.threads.create
async def authorize_thread_create(ctx: Auth.types.AuthContext):
    """스레드 생성 권한 검증"""
    # 할당량 체크
    if user_thread_count >= user_quota:
        raise Auth.exceptions.HTTPException(429, "Quota exceeded")
    return ctx
```

---

## 사용 예제

### 1. 어시스턴트 생성 및 조회

#### cURL 예제

```bash
# 어시스턴트 생성
curl -X POST http://localhost:8000/assistants \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "graph_id": "weather_agent",
    "name": "날씨 어시스턴트",
    "config": {
      "max_iterations": 10
    },
    "metadata": {
      "category": "utility"
    }
  }'

# 어시스턴트 목록 조회
curl -X GET http://localhost:8000/assistants \
  -H "Authorization: Bearer YOUR_TOKEN"

# 특정 어시스턴트 조회
curl -X GET http://localhost:8000/assistants/{assistant_id} \
  -H "Authorization: Bearer YOUR_TOKEN"

# 어시스턴트 검색
curl -X POST http://localhost:8000/assistants/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "graph_id": "weather_agent",
    "limit": 10,
    "offset": 0
  }'
```

#### Python SDK 예제

```python
from open_langgraph_sdk import OpenLangGraphClient

client = OpenLangGraphClient(
    base_url="http://localhost:8000",
    api_key="YOUR_TOKEN"
)

# 어시스턴트 생성
assistant = client.assistants.create(
    graph_id="weather_agent",
    name="날씨 어시스턴트",
    config={"max_iterations": 10}
)

# 어시스턴트 조회
assistant = client.assistants.get(assistant.assistant_id)

# 그래프 스키마 조회
schemas = client.assistants.get_schemas(assistant.assistant_id)
print(schemas["input_schema"])
print(schemas["output_schema"])
```

---

### 2. 스레드 생성 및 상태 조회

#### cURL 예제

```bash
# 스레드 생성
curl -X POST http://localhost:8000/threads \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "metadata": {
      "user_name": "홍길동",
      "session_type": "chat"
    }
  }'

# 스레드 히스토리 조회 (최근 10개 체크포인트)
curl -X POST http://localhost:8000/threads/{thread_id}/history \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 10
  }'

# 특정 체크포인트 시점의 상태 조회
curl -X GET "http://localhost:8000/threads/{thread_id}/state/{checkpoint_id}" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 스레드 검색 (메타데이터 필터)
curl -X POST http://localhost:8000/threads/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "metadata": {
      "session_type": "chat"
    },
    "limit": 20
  }'
```

#### Python SDK 예제

```python
# 스레드 생성
thread = client.threads.create(
    metadata={"user_name": "홍길동"}
)

# 스레드 히스토리 조회
history = client.threads.get_history(
    thread_id=thread.thread_id,
    limit=10
)

# 특정 체크포인트 상태 조회
state = client.threads.get_state(
    thread_id=thread.thread_id,
    checkpoint_id="checkpoint_uuid"
)
print(state.values)  # 상태 값
print(state.next)    # 다음 실행 예정 노드
```

---

### 3. 실행 생성 및 스트리밍

#### cURL 예제 (백그라운드 실행)

```bash
# 백그라운드 실행 생성 (즉시 반환)
curl -X POST http://localhost:8000/threads/{thread_id}/runs \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "weather_agent",
    "input": {
      "messages": [
        {
          "role": "user",
          "content": "서울 날씨 알려줘"
        }
      ]
    },
    "stream_mode": ["values", "messages"]
  }'

# 실행 상태 조회
curl -X GET http://localhost:8000/threads/{thread_id}/runs/{run_id} \
  -H "Authorization: Bearer YOUR_TOKEN"

# 실행 완료 대기 (join)
curl -X GET http://localhost:8000/threads/{thread_id}/runs/{run_id}/join \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### SSE 스트리밍 예제

```bash
# 실행 생성 및 SSE 스트리밍
curl -N -X POST http://localhost:8000/threads/{thread_id}/runs/stream \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "weather_agent",
    "input": {
      "messages": [{"role": "user", "content": "서울 날씨"}]
    }
  }'

# 출력 예시:
# event: message
# data: {"type": "values", "data": {"messages": [...]}}
#
# event: message
# data: {"type": "messages", "data": [{"role": "assistant", "content": "..."}]}
#
# event: end
# data: null
```

#### Python SDK 예제 (스트리밍)

```python
# 스트리밍 실행
for event in client.runs.stream(
    thread_id=thread.thread_id,
    assistant_id="weather_agent",
    input={"messages": [{"role": "user", "content": "서울 날씨"}]},
    stream_mode=["values", "messages"]
):
    if event.type == "values":
        print("State:", event.data)
    elif event.type == "messages":
        print("Messages:", event.data)
```

---

### 4. Human-in-the-Loop (HITL) 실행

#### cURL 예제

```bash
# 중단점이 있는 실행 생성
curl -X POST http://localhost:8000/threads/{thread_id}/runs/stream \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "react_agent_hitl",
    "input": {"messages": [{"role": "user", "content": "파일 삭제해줘"}]},
    "interrupt_before": ["tool_node"]
  }'

# 중단된 실행 재개 (승인)
curl -X POST http://localhost:8000/threads/{thread_id}/runs \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "react_agent_hitl",
    "input": null,
    "command": {
      "resume": "approved"
    }
  }'

# 중단된 실행 취소
curl -X POST http://localhost:8000/threads/{thread_id}/runs/{run_id}/cancel?action=interrupt \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### 5. Store API 사용

#### cURL 예제

```bash
# 아이템 저장
curl -X PUT http://localhost:8000/store/items \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "namespace": ["users", "user123", "preferences"],
    "key": "theme",
    "value": {"color": "dark", "fontSize": 14}
  }'

# 아이템 조회
curl -X GET "http://localhost:8000/store/items?key=theme&namespace=users.user123.preferences" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 아이템 검색
curl -X POST http://localhost:8000/store/items/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "namespace_prefix": ["users", "user123"],
    "query": "theme",
    "limit": 10
  }'

# 아이템 삭제
curl -X DELETE http://localhost:8000/store/items \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "namespace": ["users", "user123", "preferences"],
    "key": "theme"
  }'
```

#### Python SDK 예제

```python
# 아이템 저장
client.store.put(
    namespace=["users", "user123", "preferences"],
    key="theme",
    value={"color": "dark", "fontSize": 14}
)

# 아이템 조회
item = client.store.get(
    namespace=["users", "user123", "preferences"],
    key="theme"
)
print(item.value)

# 아이템 검색
results = client.store.search(
    namespace_prefix=["users", "user123"],
    query="theme",
    limit=10
)
for item in results.items:
    print(item.key, item.value)
```

---

### 6. 복잡한 워크플로우 예제

#### 시나리오: 날씨 어시스턴트 생성 → 스레드 생성 → 실행 → 결과 조회

```bash
# 1. 어시스턴트 생성
ASSISTANT_ID=$(curl -s -X POST http://localhost:8000/assistants \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"graph_id": "weather_agent", "name": "날씨봇"}' \
  | jq -r '.assistant_id')

# 2. 스레드 생성
THREAD_ID=$(curl -s -X POST http://localhost:8000/threads \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"metadata": {"user": "홍길동"}}' \
  | jq -r '.thread_id')

# 3. 실행 생성
RUN_ID=$(curl -s -X POST http://localhost:8000/threads/$THREAD_ID/runs \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"assistant_id\": \"$ASSISTANT_ID\",
    \"input\": {
      \"messages\": [{\"role\": \"user\", \"content\": \"서울 날씨\"}]
    }
  }" \
  | jq -r '.run_id')

# 4. 실행 완료 대기
OUTPUT=$(curl -s -X GET http://localhost:8000/threads/$THREAD_ID/runs/$RUN_ID/join \
  -H "Authorization: Bearer YOUR_TOKEN")

echo $OUTPUT | jq '.'

# 5. 스레드 히스토리 조회
curl -s -X POST http://localhost:8000/threads/$THREAD_ID/history \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 5}' \
  | jq '.'
```

---

## 추가 참고 자료

### 관련 문서

- **`/src/agent_server/services/AGENTS.md`** - 서비스 레이어 가이드
- **`/src/agent_server/core/AGENTS.md`** - 코어 레이어 가이드
- **`/src/agent_server/models/AGENTS.md`** - Pydantic 모델 가이드
- **`/CLAUDE.md`** - 프로젝트 전체 개발 가이드

### 외부 표준

- [Agent Protocol Specification](https://github.com/AI-Engineer-Foundation/agent-protocol)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Server-Sent Events (SSE) Specification](https://html.spec.whatwg.org/multipage/server-sent-events.html)

---

## 개발 가이드라인

### API 엔드포인트 추가 시 체크리스트

- [ ] FastAPI 라우터에 엔드포인트 등록
- [ ] Pydantic 요청/응답 모델 정의 (`models/`)
- [ ] `get_current_user` 의존성 주입으로 인증 적용
- [ ] 사용자별 격리 쿼리 작성 (`WHERE user_id = user.identity`)
- [ ] 서비스 계층으로 비즈니스 로직 위임
- [ ] 에러 처리 (HTTPException 사용)
- [ ] 독스트링 작성 (한글, 동작 흐름 포함)
- [ ] 테스트 작성 (`tests/test_api/`)
- [ ] Swagger UI 문서 확인 (`/docs`)

### 에러 처리 규칙

```python
from fastapi import HTTPException

# 404 Not Found - 리소스 없음
if not resource:
    raise HTTPException(404, "Resource not found")

# 400 Bad Request - 잘못된 요청
if invalid_input:
    raise HTTPException(400, "Invalid input format")

# 409 Conflict - 리소스 충돌
if duplicate:
    raise HTTPException(409, "Resource already exists")

# 422 Unprocessable Entity - 의미적 검증 실패
if out_of_range:
    raise HTTPException(422, "Value out of valid range")
```

### 로깅 규칙

```python
import logging

logger = logging.getLogger(__name__)

# 디버그 로그
logger.debug(f"Processing request: thread_id={thread_id}")

# 정보 로그
logger.info(f"Created assistant: assistant_id={assistant_id}")

# 경고 로그
logger.warning(f"Slow query detected: {elapsed_time}s")

# 에러 로그
logger.error(f"Failed to load graph: {graph_id}", exc_info=True)
```

### 비동기 처리 패턴

```python
# 비동기 데이터베이스 작업
async with session.begin():
    result = await session.execute(stmt)
    await session.commit()

# 백그라운드 태스크 생성
task = asyncio.create_task(execute_run_async(...))
active_runs[run_id] = task

# 스트리밍 응답
async def event_generator():
    async for event in source:
        yield format_sse_event(event)

return StreamingResponse(
    event_generator(),
    media_type="text/event-stream"
)
```

---

**작성일**: 2025-10-27
**작성자**: Agent 3 (AGENTS.md 문서화 전담)
**버전**: 1.0.0
