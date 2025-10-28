# AGENTS.md - Models Layer Documentation

## 1. 폴더 개요

`src/agent_server/models/` 디렉토리는 Open LangGraph 서버의 **데이터 검증 및 직렬화 레이어**를 담당합니다. [Pydantic](https://docs.pydantic.dev/) 기반 모델을 사용하여 Agent Protocol 표준을 준수하는 API 요청/응답을 정의합니다.

### 주요 역할

- **Agent Protocol 준수**: Agent Protocol 명세에 정의된 표준 API 스키마 구현
- **데이터 검증**: 요청 데이터의 타입 검증 및 제약 조건 확인 (Pydantic validators)
- **직렬화/역직렬화**: JSON ↔ Python 객체 변환, ORM 모델 ↔ API 응답 변환
- **타입 안정성**: FastAPI와 통합되어 자동 문서화 및 런타임 타입 체크 제공
- **멀티테넌시**: 모든 엔티티에 `user_id` 필드를 통한 사용자별 데이터 격리

### 아키텍처 위치

```
HTTP Request → FastAPI Router → Pydantic Model (검증) → Service Layer → Database
                                       ↓
HTTP Response ← FastAPI Router ← Pydantic Model (직렬화) ← Service Layer ← Database
```

---

## 2. 파일 목록 및 설명

### 2.1 `runs.py` - 실행(Run) 모델

LangGraph 그래프 실행의 전체 생명주기를 관리하는 모델입니다.

**주요 클래스:**

| 클래스 | 용도 | 주요 필드 |
|--------|------|----------|
| `RunCreate` | 실행 생성/재개 요청 | `assistant_id`, `input`, `command`, `stream`, `interrupt_before/after` |
| `Run` | 실행 엔티티 (DB 매핑) | `run_id`, `thread_id`, `status`, `input`, `output`, `error_message` |
| `RunStatus` | 경량 상태 응답 | `run_id`, `status`, `message` |

**핵심 기능:**

- **HITL (Human-in-the-Loop)**: `interrupt_before/after`, `command` 필드로 실행 중단 및 재개
- **스트리밍**: `stream`, `stream_mode` 필드로 SSE(Server-Sent Events) 실시간 이벤트 전송
- **동시성 제어**: `multitask_strategy`로 동일 스레드의 동시 실행 처리 전략 지정
- **Validator**: `input`과 `command`의 상호 배타성 검증 (`@model_validator`)

**생명주기 상태:**
```
pending → running → completed
                 ↘ failed
                 ↘ cancelled
```

---

### 2.2 `threads.py` - 스레드 모델

대화 세션(Thread)의 생성, 조회, 상태 관리 모델입니다.

**주요 클래스:**

| 클래스 | 용도 | 주요 필드 |
|--------|------|----------|
| `ThreadCreate` | 스레드 생성 요청 | `metadata`, `initial_state` |
| `Thread` | 스레드 엔티티 (메타데이터) | `thread_id`, `status`, `metadata`, `user_id` |
| `ThreadSearchRequest` | 스레드 검색 요청 | `metadata`, `status`, `limit`, `offset`, `order_by` |
| `ThreadSearchResponse` | 검색 결과 (페이지네이션) | `threads`, `total`, `limit`, `offset` |
| `ThreadCheckpoint` | 체크포인트 식별자 | `checkpoint_id`, `thread_id`, `checkpoint_ns` |
| `ThreadState` | 그래프 실행 상태 | `values`, `next`, `tasks`, `interrupts`, `checkpoint` |
| `ThreadHistoryRequest` | 상태 이력 조회 요청 | `limit`, `before`, `metadata`, `checkpoint_ns` |

**핵심 개념:**

- **Thread vs ThreadState**:
  - `Thread`: 스레드의 메타데이터 (상태, 생성일, user_id 등)
  - `ThreadState`: 특정 체크포인트의 그래프 실행 상태 (채널 값, 다음 노드 등)

- **Checkpoint 네임스페이스**:
  - 빈 문자열 `""`: 메인 그래프
  - `"subgraph_1"`: 서브그래프 실행 추적
  - 계층적 네임스페이스 지원 (예: `"nested.subgraph_2"`)

---

### 2.3 `assistants.py` - 어시스턴트 모델

LangGraph 그래프를 래핑하는 어시스턴트 엔티티의 CRUD 모델입니다.

**주요 클래스:**

| 클래스 | 용도 | 주요 필드 |
|--------|------|----------|
| `AssistantCreate` | 어시스턴트 생성 요청 | `graph_id`, `config`, `context`, `metadata`, `if_exists` |
| `Assistant` | 어시스턴트 엔티티 | `assistant_id`, `name`, `graph_id`, `version`, `user_id` |
| `AssistantUpdate` | 어시스턴트 업데이트 요청 | `name`, `description`, `config`, `metadata` |
| `AssistantSearchRequest` | 어시스턴트 검색 요청 | `name`, `description`, `graph_id`, `metadata` |
| `AgentSchemas` | 그래프 스키마 (JSON Schema) | `input_schema`, `output_schema`, `state_schema`, `config_schema` |

**핵심 개념:**

- **Config vs Context (LangGraph 0.6.0+)**:
  - `config`: 런타임 실행 설정 (예: `{"model_name": "gpt-4", "temperature": 0.7}`)
  - `context`: 컴파일 타임 컨텍스트 (그래프가 configurable한 경우)

- **버전 관리**:
  - `version` 필드가 업데이트마다 자동 증가
  - 설정 변경 이력 추적 가능

- **if_exists 옵션**:
  - `"error"`: 중복 생성 시 오류 반환 (기본값)
  - `"do_nothing"`: 이미 존재하면 무시

---

### 2.4 `store.py` - 저장소 모델

LangGraph Store (장기 메모리 및 키-값 저장소) 통합 모델입니다.

**주요 클래스:**

| 클래스 | 용도 | 주요 필드 |
|--------|------|----------|
| `StorePutRequest` | 항목 저장 요청 | `namespace`, `key`, `value` |
| `StoreGetResponse` | 항목 조회 응답 | `key`, `value`, `namespace` |
| `StoreSearchRequest` | 항목 검색 요청 | `namespace_prefix`, `query`, `limit`, `offset` |
| `StoreSearchResponse` | 검색 결과 (페이지네이션) | `items`, `total`, `limit`, `offset` |
| `StoreItem` | 저장소 항목 | `key`, `value`, `namespace` |
| `StoreDeleteRequest` | 항목 삭제 요청 | `namespace`, `key` |

**네임스페이스 계층 구조:**

```python
# 사용자별 설정 저장
namespace = ["user", "123", "preferences"]
key = "theme"
value = {"mode": "dark", "color": "blue"}

# 팀별 리소스 저장
namespace = ["team", "sales", "resources"]
key = "quota"
value = 10000
```

**네임스페이스 변환:**
- API: `list[str]` 형식 수신
- LangGraph Store: `tuple[str, ...]` 형식 요구
- 서비스 레이어에서 자동 변환 처리

---

### 2.5 `auth.py` - 인증 모델

인증 및 권한 부여 시스템의 사용자 컨텍스트 모델입니다.

**주요 클래스:**

| 클래스 | 용도 | 주요 필드 |
|--------|------|----------|
| `User` | 인증된 사용자 정보 | `identity`, `display_name`, `permissions`, `org_id` |
| `AuthContext` | 요청 인증 컨텍스트 | `user`, `request_id` |
| `TokenPayload` | JWT 토큰 페이로드 | `sub`, `name`, `scopes`, `org`, `exp`, `iat` |

**멀티테넌시 격리:**

```python
user = User(
    identity="user123",
    display_name="홍길동",
    permissions=["assistants:read", "threads:write"],
    org_id="org_abc"  # 조직별 데이터 격리
)
```

**LangGraph 통합:**
- `LangGraph SDK Auth.types.MinimalUserDict`와 호환
- `Runtime[Context]`를 통해 그래프 노드에서 `user.identity`, `user.org_id` 접근 가능

---

### 2.6 `errors.py` - 오류 응답 모델

Agent Protocol 표준 오류 응답 구조를 정의합니다.

**주요 클래스:**

| 클래스/함수 | 용도 | 반환값 |
|------------|------|--------|
| `AgentProtocolError` | 표준 오류 응답 모델 | `error`, `message`, `details` |
| `get_error_type()` | HTTP 상태 코드 → 오류 타입 변환 | `str` (예: "not_found", "unauthorized") |

**오류 응답 예시:**

```json
{
  "error": "not_found",
  "message": "Thread abc-123 not found",
  "details": {
    "thread_id": "abc-123",
    "user_id": "user-456"
  }
}
```

**지원하는 오류 타입:**

| HTTP 코드 | 오류 타입 | 설명 |
|----------|----------|------|
| 400 | `bad_request` | 잘못된 요청 형식 |
| 401 | `unauthorized` | 인증 실패 |
| 403 | `forbidden` | 권한 부족 |
| 404 | `not_found` | 리소스 없음 |
| 409 | `conflict` | 리소스 충돌 |
| 422 | `validation_error` | 데이터 검증 실패 |
| 500 | `internal_error` | 서버 내부 오류 |
| 503 | `service_unavailable` | 서비스 이용 불가 |

---

## 3. 모델 계층 구조

### 3.1 Request/Response 패턴

```
[Request Models]           [Entity Models]           [Response Models]
      ↓                          ↓                          ↓
RunCreate --------→ Service → Run (ORM) --------→ Run (API Response)
AssistantCreate → Service → Assistant (ORM) → Assistant (API Response)
ThreadCreate ----→ Service → Thread (ORM) ------→ Thread (API Response)
```

### 3.2 ORM 통합

**Pydantic의 `from_attributes=True` 설정:**

```python
class Thread(BaseModel):
    thread_id: str
    status: str
    metadata: dict[str, Any]
    user_id: str
    created_at: datetime

    class Config:
        from_attributes = True  # ORM 모델에서 자동 변환
```

**사용 예:**

```python
# ORM 모델 (SQLAlchemy)
orm_thread = db.query(ThreadMetadata).filter_by(thread_id="abc").first()

# Pydantic 모델로 자동 변환
api_thread = Thread.model_validate(orm_thread)
```

### 3.3 별칭(Alias) 사용

**ORM 필드명과 API 필드명이 다른 경우:**

```python
class Assistant(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_dict")
    # ORM: metadata_dict (SQLAlchemy reserved keyword 회피)
    # API: metadata (Agent Protocol 표준)

    class Config:
        from_attributes = True
```

---

## 4. 검증 규칙 (Validators)

### 4.1 Field-level Validation

**Pydantic Field constraints:**

```python
class ThreadSearchRequest(BaseModel):
    limit: int | None = Field(20, le=100, ge=1)  # 1 <= limit <= 100
    offset: int | None = Field(0, ge=0)          # offset >= 0
```

### 4.2 Model-level Validation

**`@model_validator` 사용 예시:**

```python
class RunCreate(BaseModel):
    input: dict[str, Any] | None = None
    command: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_input_command_exclusivity(self) -> Self:
        """input과 command는 상호 배타적"""
        if self.input is not None and self.command is not None:
            if self.input == {}:
                self.input = None  # 프론트엔드 호환성
            else:
                raise ValueError("Cannot specify both 'input' and 'command'")
        if self.input is None and self.command is None:
            raise ValueError("Must specify either 'input' or 'command'")
        return self
```

### 4.3 자동 검증 시점

**FastAPI 통합:**

```python
@app.post("/threads/{thread_id}/runs")
async def create_run(
    thread_id: str,
    run_create: RunCreate  # Pydantic 모델 자동 검증
):
    # 이미 검증된 데이터
    pass
```

**검증 실패 시:**
- HTTP 422 (Unprocessable Entity)
- 자동으로 `validation_error` 응답 생성

---

## 5. Agent Protocol 준수

### 5.1 표준 엔드포인트 매핑

| Agent Protocol 리소스 | Pydantic 모델 | HTTP 메서드 |
|-----------------------|--------------|------------|
| `/assistants` | `AssistantCreate`, `Assistant` | POST, GET |
| `/threads` | `ThreadCreate`, `Thread` | POST, GET |
| `/threads/{id}/runs` | `RunCreate`, `Run` | POST, GET |
| `/threads/{id}/state` | `ThreadState` | GET, POST |
| `/store` | `StorePutRequest`, `StoreGetResponse` | GET, POST, DELETE |

### 5.2 필수 필드

**Agent Protocol에서 요구하는 필수 필드:**

```python
class Run(BaseModel):
    run_id: str          # 실행 고유 ID
    thread_id: str       # 스레드 ID
    assistant_id: str    # 어시스턴트 ID
    status: str          # 상태 (pending, running, completed, failed, cancelled)
    created_at: datetime # 생성 시각
    updated_at: datetime # 수정 시각
```

### 5.3 메타데이터 필드

**모든 엔티티에 JSONB 메타데이터 지원:**

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

**용도:**
- 검색 및 필터링
- 사용자 정의 속성 저장
- 태그 및 분류

---

## 6. 사용 예제

### 6.1 실행 생성 (기본 실행)

```python
from models.runs import RunCreate

# 새 실행 시작
run_create = RunCreate(
    assistant_id="weather_agent",
    input={"location": "Seoul", "date": "2025-10-27"}
)
```

### 6.2 HITL 재개 (Human-in-the-Loop)

```python
# 중단 설정
run_create = RunCreate(
    assistant_id="approval_agent",
    input={"request": "data"},
    interrupt_before=["approval_node"]  # approval_node 실행 전 중단
)

# 재개 (사용자 승인 후)
run_resume = RunCreate(
    assistant_id="approval_agent",
    command={"resume": {"approved": True}}  # 승인 데이터 전달
)
```

### 6.3 스레드 생성 및 검색

```python
from models.threads import ThreadCreate, ThreadSearchRequest

# 스레드 생성
thread_create = ThreadCreate(
    metadata={"user_name": "Alice", "topic": "weather"},
    initial_state={"messages": []}
)

# 스레드 검색
search_request = ThreadSearchRequest(
    metadata={"topic": "weather"},  # JSONB 필터
    status="idle",
    limit=20,
    offset=0,
    order_by="created_at DESC"
)
```

### 6.4 저장소 항목 저장

```python
from models.store import StorePutRequest

# 사용자 설정 저장
store_put = StorePutRequest(
    namespace=["user", "123", "preferences"],
    key="theme",
    value={"mode": "dark", "color": "blue"}
)
```

### 6.5 어시스턴트 생성

```python
from models.assistants import AssistantCreate

# 어시스턴트 생성
assistant_create = AssistantCreate(
    graph_id="weather_agent",
    config={"model": "gpt-4", "temperature": 0.7},
    metadata={"team": "sales", "version": "1.0"},
    if_exists="error"  # 중복 시 오류 발생
)
```

### 6.6 ORM 변환

```python
from models.threads import Thread

# ORM 모델에서 API 응답 변환
orm_thread = await db.get_thread(thread_id="abc")
api_thread = Thread.model_validate(orm_thread)

# JSON 직렬화
response_json = api_thread.model_dump(mode="json")
```

### 6.7 오류 응답 생성

```python
from models.errors import AgentProtocolError, get_error_type
from fastapi import HTTPException

# 오류 응답 생성
error = AgentProtocolError(
    error=get_error_type(404),
    message="Thread not found",
    details={"thread_id": "abc-123"}
)

# FastAPI HTTPException으로 래핑
raise HTTPException(status_code=404, detail=error.model_dump())
```

---

## 7. 모범 사례 (Best Practices)

### 7.1 모델 재사용

**공통 필드는 Base 모델로 추출:**

```python
class TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: datetime

class Run(TimestampMixin):
    run_id: str
    # ... 다른 필드들
```

### 7.2 선택적 필드 처리

**None vs 기본값:**

```python
# None: 필드가 생략 가능
metadata: dict[str, Any] | None = None

# 기본값: 필드 생략 시 빈 dict 사용
metadata: dict[str, Any] = Field(default_factory=dict)
```

### 7.3 검증 로직 집중화

**복잡한 검증은 @model_validator에서 처리:**

```python
@model_validator(mode="after")
def validate_business_logic(self) -> Self:
    # 여러 필드 간의 복잡한 관계 검증
    if self.stream and not self.stream_mode:
        self.stream_mode = ["values"]  # 기본값 설정
    return self
```

### 7.4 타입 안정성

**Type hints 적극 활용:**

```python
# 명확한 타입 지정
config: dict[str, Any] | None = Field(default_factory=dict)

# Union 타입 사용
stream_mode: str | list[str] | None = None
```

### 7.5 문서화

**Field description 활용:**

```python
assistant_id: str = Field(
    ...,
    description="실행할 어시스턴트(그래프) ID. open_langgraph.json에 정의된 graph_id 사용"
)
```

---

## 8. 관련 문서

- [CLAUDE.md](/Users/jhj/Desktop/personal/opensource-langgraph-platform/CLAUDE.md) - 전체 프로젝트 가이드
- [Pydantic Documentation](https://docs.pydantic.dev/) - Pydantic 공식 문서
- [Agent Protocol Specification](https://github.com/AI-Engineer-Foundation/agent-protocol) - Agent Protocol 명세
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/) - LangGraph 공식 문서

---

## 9. 요약

**Models 레이어의 핵심 역할:**

1. **데이터 검증**: Pydantic validators를 통한 런타임 타입 체크 및 제약 조건 확인
2. **Agent Protocol 준수**: 표준 API 스키마 구현으로 클라이언트 호환성 보장
3. **ORM 통합**: `from_attributes=True`로 SQLAlchemy 모델과 자동 변환
4. **타입 안정성**: FastAPI와 통합되어 자동 문서화 및 IDE 지원
5. **멀티테넌시**: `user_id` 및 `org_id` 필드를 통한 데이터 격리

**파일별 책임:**

| 파일 | 책임 | 주요 모델 |
|------|------|----------|
| `runs.py` | 그래프 실행 생명주기 관리 | `RunCreate`, `Run`, `RunStatus` |
| `threads.py` | 대화 세션 및 상태 관리 | `Thread`, `ThreadState`, `ThreadCheckpoint` |
| `assistants.py` | 어시스턴트 CRUD 및 스키마 | `Assistant`, `AssistantCreate`, `AgentSchemas` |
| `store.py` | 장기 메모리 저장소 통합 | `StorePutRequest`, `StoreSearchResponse` |
| `auth.py` | 인증 및 사용자 컨텍스트 | `User`, `AuthContext`, `TokenPayload` |
| `errors.py` | 표준 오류 응답 | `AgentProtocolError`, `get_error_type()` |

**다음 단계:**
- 각 모델의 실제 사용 예제는 `/src/agent_server/routes/` 참조
- 서비스 레이어 통합은 `/src/agent_server/services/` 참조
- 전체 API 엔드포인트 목록은 OpenAPI 문서 (http://localhost:8000/docs) 참조
