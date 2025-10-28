# Core Layer - 핵심 인프라 및 데이터 접근 계층

## 폴더 개요

`core/` 디렉토리는 Open LangGraph 서버의 **기반 인프라 계층**입니다. 데이터베이스 연결, 인증, 직렬화, SSE 스트리밍 등 애플리케이션 전체에서 사용되는 핵심 컴포넌트를 제공합니다.

### 핵심 역할

1. **데이터베이스 관리**: SQLAlchemy와 LangGraph 영속성 컴포넌트의 통합 관리
2. **인증 시스템**: LangGraph SDK Auth와 FastAPI의 완전한 통합
3. **ORM 모델**: Agent Protocol 메타데이터 테이블 정의
4. **직렬화**: LangGraph 객체의 JSON 변환 처리
5. **SSE 포맷팅**: Server-Sent Events 표준 메시지 생성
6. **헬스 체크**: 서비스 상태 모니터링 엔드포인트

### 아키텍처 원칙

- **싱글톤 패턴**: 데이터베이스 연결 등 공유 리소스는 전역 인스턴스 사용
- **지연 초기화**: 리소스를 필요할 때만 생성하여 시작 시간 단축
- **컨텍스트 관리**: 비동기 컨텍스트 매니저로 리소스 자동 정리
- **계층 분리**: API/Services 계층이 직접 데이터베이스를 다루지 않고 Core를 통해 접근

---

## 파일 목록 및 설명

### 핵심 데이터베이스 계층

#### `database.py` - 데이터베이스 관리자
**역할**: SQLAlchemy와 LangGraph 컴포넌트의 통합 관리

**주요 클래스**:
- `DatabaseManager`: 데이터베이스 연결 및 LangGraph 영속성 관리
  - SQLAlchemy 엔진 생성 (Agent Protocol 메타데이터용)
  - LangGraph `AsyncPostgresSaver` 관리 (체크포인트 저장)
  - LangGraph `AsyncPostgresStore` 관리 (장기 메모리 저장)
  - URL 형식 자동 변환 (asyncpg ↔ psycopg)

**싱글톤 인스턴스**:
```python
db_manager = DatabaseManager()  # 전역 인스턴스
```

**주요 메서드**:
- `initialize()`: 앱 시작 시 DB 연결 초기화
- `close()`: 앱 종료 시 연결 정리
- `get_checkpointer()`: LangGraph 체크포인터 반환 (캐시됨)
- `get_store()`: LangGraph Store 반환 (캐시됨)
- `get_engine()`: SQLAlchemy 엔진 반환

**특이 사항**:
- LangGraph는 `postgresql://` URL 필요, SQLAlchemy는 `postgresql+asyncpg://` 사용
- 체크포인터/Store는 첫 호출 시 컨텍스트 매니저 진입 후 캐시
- 데이터베이스 스키마는 Alembic 마이그레이션으로 관리

#### `orm.py` - SQLAlchemy ORM 모델
**역할**: Agent Protocol 메타데이터 테이블 정의

**주요 모델**:
1. **`Assistant`**: 어시스턴트 정의
   - `assistant_id`: UUID (자동 생성)
   - `graph_id`: 실행할 그래프 ID
   - `config`: LangGraph 실행 설정 (JSONB)
   - `context`: 런타임 컨텍스트 (JSONB)
   - `user_id`: 멀티테넌트 격리
   - 인덱스: user_id, (user_id, assistant_id), (user_id, graph_id, config)

2. **`AssistantVersion`**: 어시스턴트 버전 이력
   - 복합 PK: (assistant_id, version)
   - CASCADE DELETE: 어시스턴트 삭제 시 버전도 삭제

3. **`Thread`**: 대화 스레드 메타데이터
   - `thread_id`: 클라이언트가 제공하는 ID
   - `status`: idle/busy/interrupted
   - `metadata_json`: 어시스턴트/그래프 정보 (JSONB)
   - `user_id`: 소유자

4. **`Run`**: 실행 기록
   - `run_id`: UUID (자동 생성)
   - `status`: pending/running/completed/failed/cancelled/interrupted
   - `input`, `output`: JSONB
   - `config`, `context`: 실행 설정 (JSONB)
   - FK: thread_id, assistant_id (CASCADE DELETE)
   - 인덱스: thread_id, user_id, status, assistant_id, created_at

5. **`RunEvent`**: SSE 이벤트 저장 (재생용)
   - `id`: {run_id}_event_{seq}
   - `seq`: 시퀀스 번호 (정렬용)
   - `event`: 이벤트 타입
   - `data`: 페이로드 (JSONB)
   - 인덱스: run_id, (run_id, seq)

**세션 팩토리**:
```python
async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 의존성 주입용 세션 생성"""
```

**중요 사항**:
- 실제 대화 상태는 LangGraph 체크포인터에 저장됨 (이 테이블들은 메타데이터만)
- JSONB 컬럼은 복잡한 설정과 컨텍스트를 유연하게 저장
- 모든 테이블에 user_id 인덱스 (멀티테넌트 격리)

---

### 인증 시스템

#### `auth_middleware.py` - LangGraph 인증 미들웨어
**역할**: LangGraph SDK Auth를 FastAPI와 통합

**주요 클래스**:
1. **`LangGraphUser`**: Starlette BaseUser 구현
   - MinimalUserDict를 BaseUser 인터페이스로 감싸기
   - 필수 속성: identity, is_authenticated, display_name
   - `__getattr__`로 커스텀 필드(permissions, org_id 등) 접근 허용

2. **`LangGraphAuthBackend`**: 인증 백엔드
   - auth.py에서 Auth 인스턴스 동적 로드
   - 모든 요청에 대해 `authenticate()` 메서드 호출
   - `@auth.authenticate` 핸들러와 연동

**흐름**:
```
클라이언트 요청
  ↓ (Authorization 헤더)
AuthenticationMiddleware
  ↓
LangGraphAuthBackend.authenticate()
  ↓
auth.py의 @auth.authenticate 핸들러
  ↓ (성공)
request.user = LangGraphUser 설정
```

**주요 함수**:
- `get_auth_backend()`: AUTH_TYPE 환경 변수 기반 백엔드 선택
- `on_auth_error()`: Agent Protocol 형식의 401 응답 생성

**환경 변수**:
- `AUTH_TYPE=noop`: 인증 없음 (개발용)
- `AUTH_TYPE=custom`: 커스텀 인증 (auth.py 구현)

#### `auth_ctx.py` - 인증 컨텍스트 관리
**역할**: 그래프 노드에서 인증 정보 접근 가능하게 함

**주요 함수**:
```python
def get_auth_ctx() -> Auth.types.BaseAuthContext | None:
    """현재 인증 컨텍스트 반환 (그래프 노드에서 사용)"""

@asynccontextmanager
async def with_auth_ctx(user: BaseUser | None, permissions: list[str] | None):
    """비동기 블록 실행 중 인증 컨텍스트 임시 설정"""
```

**사용 패턴**:
```python
# 그래프 노드에서 사용자 확인
def my_node(state):
    auth_ctx = get_auth_ctx()
    if auth_ctx and auth_ctx.user:
        user_id = auth_ctx.user.identity
        # 사용자별 처리...

# 실행 시 컨텍스트 주입
async with with_auth_ctx(user, ["read", "write"]):
    result = await graph.ainvoke(input_data)
```

**기술 구현**:
- `contextvars.ContextVar` 사용 (asyncio 친화적)
- 스레드 로컬 대신 컨텍스트 변수로 안전한 비동기 처리

#### `auth_deps.py` - FastAPI 인증 의존성
**역할**: FastAPI 라우터에서 사용할 인증 헬퍼

**주요 함수**:
1. **`get_current_user(request: Request) -> User`**
   - 미들웨어가 설정한 request.user 추출
   - LangGraphUser를 Open LangGraph User 모델로 변환
   - 401 예외 발생 (미인증 시)

2. **`get_user_id(user: User = Depends(get_current_user)) -> str`**
   - 사용자 ID만 필요한 경우 사용

3. **`require_permission(permission: str) -> Callable`**
   - 특정 권한 요구하는 의존성 생성 (커링 패턴)
   - 403 예외 발생 (권한 없을 시)

4. **`require_authenticated(request: Request) -> User`**
   - 인증 여부만 확인 (get_current_user의 별칭)

**사용 예**:
```python
@router.get("/assistants")
async def list_assistants(user: User = Depends(get_current_user)):
    return await get_assistants_for_user(user.identity)

@router.delete("/admin")
async def admin_only(user: User = Depends(require_permission("admin"))):
    # 관리자만 접근 가능
```

---

### 직렬화 계층

#### `serializers/` - 직렬화 모듈

##### `base.py` - 직렬화 인터페이스
```python
class Serializer(ABC):
    @abstractmethod
    def serialize(self, obj: Any) -> Any:
        """JSON 호환 형식으로 변환"""

class SerializationError(Exception):
    """직렬화 실패 시 예외"""
```

##### `general.py` - 범용 직렬화
**역할**: LangGraph SDK의 _orjson_default 로직 기반 범용 직렬화

**처리 순서**:
1. Pydantic v2 모델 (`model_dump()`)
2. Pydantic v1/LangChain 객체 (`dict()`)
3. LangGraph Interrupt 객체 (value + id)
4. NamedTuple (`_asdict()`)
5. Set/Frozenset → List
6. Tuple/List (재귀)
7. Dict (재귀)
8. 기본 JSON 타입 (str, int, float, bool, None)
9. 기타 → `str(obj)` (fallback)

##### `langgraph.py` - LangGraph 전용 직렬화
**역할**: LangGraph 특화 객체(tasks, interrupts, snapshots) 처리

**주요 메서드**:
- `serialize_task()`: Task → ThreadTask 형식
- `serialize_interrupt()`: Interrupt 객체 직렬화
- `extract_tasks_from_snapshot()`: 스냅샷에서 task 추출
- `extract_interrupts_from_snapshot()`: 스냅샷에서 interrupt 추출

---

### SSE 스트리밍 계층

#### `sse.py` - Server-Sent Events 포맷팅
**역할**: SSE 표준 메시지 생성 및 헤더 관리

**핵심 함수**:
```python
def get_sse_headers() -> dict[str, str]:
    """SSE 표준 헤더 (Content-Type: text/event-stream 등)"""

def format_sse_message(
    event: str,
    data: Any,
    event_id: str | None = None,
    serializer: Callable[[Any], Any] | None = None
) -> str:
    """SSE 표준 형식으로 메시지 생성"""
```

**이벤트 생성 함수**:
- `create_metadata_event()`: run_id, attempt 등
- `create_values_event()`: 그래프 출력 값
- `create_updates_event()`: 상태 업데이트
- `create_debug_event()`: 디버그 정보 (체크포인트 포함)
- `create_messages_event()`: 메시지 스트리밍 (토큰 단위)
- `create_end_event()`: 스트림 종료
- `create_error_event()`: 오류 발생
- 기타: events, state, logs, tasks, subgraphs, checkpoints, custom

**SSE 형식 예시**:
```
event: values
data: {"messages":[{"role":"assistant","content":"Hello"}]}
id: run_123_event_1

event: end
data: {"status":"completed"}

```

**특이 사항**:
- LangSmith Studio 호환성 위해 debug 이벤트에 checkpoint 필드 자동 추가
- 메시지 스트리밍은 (chunk, metadata) 튜플 처리 지원
- 레거시 함수들(create_start_event 등)은 하위 호환성 유지

---

### 헬스 체크 계층

#### `health.py` - 서비스 상태 모니터링
**역할**: Kubernetes/Docker 환경에서 서비스 상태 확인

**엔드포인트**:

1. **`GET /info`**: 서비스 정보
```json
{
  "name": "Open LangGraph",
  "version": "0.1.0",
  "description": "Production-ready Agent Protocol server built on LangGraph",
  "status": "running"
}
```

2. **`GET /health`**: 포괄적 헬스 체크
```json
{
  "status": "healthy",
  "database": "connected",
  "langgraph_checkpointer": "connected",
  "langgraph_store": "connected"
}
```
- SQLAlchemy 엔진 연결 확인 (`SELECT 1`)
- LangGraph 체크포인터 연결 확인
- LangGraph Store 연결 확인
- 하나라도 실패 시 503 응답

3. **`GET /ready`**: Kubernetes Readiness Probe
- DB 엔진 초기화 확인
- LangGraph 컴포넌트 초기화 확인
- 미준비 시 503 응답

4. **`GET /live`**: Kubernetes Liveness Probe
- 단순 alive 체크
- 항상 200 응답

---

## 주요 패턴

### 1. 싱글톤 패턴 (Singleton Pattern)

**사용 위치**: `database.py`의 `db_manager`

```python
# database.py
class DatabaseManager:
    def __init__(self):
        self.engine = None
        self._checkpointer = None
        self._store = None

# 전역 싱글톤 인스턴스
db_manager = DatabaseManager()
```

**이점**:
- 애플리케이션 전체에서 단일 DB 연결 풀 공유
- 리소스 낭비 방지
- 초기화 한 번만 수행

### 2. 지연 초기화 패턴 (Lazy Initialization)

**사용 위치**: `get_checkpointer()`, `get_store()`

```python
async def get_checkpointer(self) -> AsyncPostgresSaver:
    if self._checkpointer is None:
        self._checkpointer_cm = AsyncPostgresSaver.from_conn_string(...)
        self._checkpointer = await self._checkpointer_cm.__aenter__()
        await self._checkpointer.setup()
    return self._checkpointer
```

**이점**:
- 필요할 때만 리소스 할당
- 앱 시작 시간 단축
- 사용하지 않는 기능은 초기화 안 함

### 3. 컨텍스트 매니저 패턴 (Context Manager)

**사용 위치**: `auth_ctx.py`의 `with_auth_ctx()`

```python
@asynccontextmanager
async def with_auth_ctx(user, permissions):
    token = _AuthCtx.set(auth_context)
    try:
        yield
    finally:
        _AuthCtx.reset(token)
```

**이점**:
- 리소스 자동 정리 (RAII)
- 예외 발생 시에도 안전한 정리 보장
- 컨텍스트 범위 명확

### 4. 의존성 주입 패턴 (Dependency Injection)

**사용 위치**: `orm.py`의 `get_session()`, `auth_deps.py`

```python
async def get_session() -> AsyncIterator[AsyncSession]:
    maker = _get_session_maker()
    async with maker() as session:
        yield session

# FastAPI 라우터에서 사용
@router.get("/assistants")
async def list_assistants(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
):
    # session과 user 자동 주입
```

**이점**:
- 테스트 가능성 향상
- 관심사 분리
- 재사용성 증가

### 5. 팩토리 패턴 (Factory Pattern)

**사용 위치**: `sse.py`의 이벤트 생성 함수들

```python
def create_values_event(chunk_data, event_id=None):
    return format_sse_message("values", chunk_data, event_id)

def create_error_event(error, event_id=None):
    data = {"error": error, "timestamp": datetime.now(UTC).isoformat()}
    return format_sse_message("error", data, event_id)
```

**이점**:
- 객체 생성 로직 캡슐화
- 일관된 형식 보장
- 변경 지점 단일화

### 6. 전략 패턴 (Strategy Pattern)

**사용 위치**: `serializers/` 계층

```python
class Serializer(ABC):
    @abstractmethod
    def serialize(self, obj: Any) -> Any:
        pass

class GeneralSerializer(Serializer):
    def serialize(self, obj: Any) -> Any:
        # 범용 직렬화 전략

class LangGraphSerializer(Serializer):
    def serialize(self, obj: Any) -> Any:
        # LangGraph 특화 직렬화 전략
```

**이점**:
- 런타임에 알고리즘 교체 가능
- 확장에 열려있고 수정에 닫혀있음 (OCP)
- 코드 재사용성

---

## 의존성 관계

### 계층 구조 다이어그램

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer (api/)                        │
│  assistants.py, runs.py, threads.py, store.py              │
└────────────────┬────────────────────────────────────────────┘
                 │ depends on
                 ↓
┌─────────────────────────────────────────────────────────────┐
│                   Services Layer (services/)                 │
│  langgraph_service, streaming_service, event_converter...   │
└────────────────┬────────────────────────────────────────────┘
                 │ depends on
                 ↓
┌─────────────────────────────────────────────────────────────┐
│                     CORE LAYER (core/)                       │
│  ┌─────────────┬──────────────┬─────────────┬──────────┐   │
│  │ database.py │  orm.py      │  auth_*.py  │  sse.py  │   │
│  │ db_manager  │  Models      │  Auth       │  Events  │   │
│  └─────────────┴──────────────┴─────────────┴──────────┘   │
│  ┌──────────────────────┐  ┌──────────────────────────┐   │
│  │  serializers/        │  │  health.py               │   │
│  │  - base.py           │  │  - /health, /ready       │   │
│  │  - general.py        │  │  - /live, /info          │   │
│  │  - langgraph.py      │  └──────────────────────────┘   │
│  └──────────────────────┘                                   │
└────────────────┬────────────────────────────────────────────┘
                 │ depends on
                 ↓
┌─────────────────────────────────────────────────────────────┐
│              External Dependencies                           │
│  SQLAlchemy, LangGraph SDK, Starlette, Pydantic             │
└─────────────────────────────────────────────────────────────┘
```

### 파일 간 의존성 상세

#### 1. database.py (중심 허브)
**의존성**: 없음 (최하위 계층)
**사용자**:
- `services/langgraph_service.py` → `db_manager.get_checkpointer()`
- `services/event_store.py` → `db_manager.get_engine()`
- `api/store.py` → `db_manager.get_store()`
- `health.py` → `db_manager.engine`, `db_manager.get_checkpointer()`

#### 2. orm.py (데이터 모델 정의)
**의존성**: `database.py` (세션 생성 시)
**사용자**:
- `api/runs.py` → `RunORM`, `ThreadORM`, `AssistantORM`, `get_session`
- `api/threads.py` → `ThreadORM`, `RunORM`, `get_session`
- `api/assistants.py` → `get_session` (간접 사용)
- `services/assistant_service.py` → `AssistantORM`, `AssistantVersionORM`, `get_session`
- `services/langgraph_service.py` → `AssistantORM`, `get_session`

#### 3. auth_middleware.py (인증 진입점)
**의존성**:
- `models/errors.py` → `AgentProtocolError`
**사용자**:
- `main.py` → `AuthenticationMiddleware` 등록

#### 4. auth_deps.py (의존성 헬퍼)
**의존성**:
- `models/auth.py` → `User` 모델
**사용자**:
- `api/assistants.py` → `get_current_user`
- `api/runs.py` → `get_current_user`
- `api/threads.py` → `get_current_user`
- `api/store.py` → `get_current_user`

#### 5. auth_ctx.py (컨텍스트 관리)
**의존성**: 없음 (LangGraph SDK만)
**사용자**:
- `api/runs.py` → `with_auth_ctx` (그래프 실행 시)

#### 6. serializers/ (직렬화 계층)
**의존성**: 없음 (독립적)
**사용자**:
- `sse.py` → `GeneralSerializer`
- `api/runs.py` → `GeneralSerializer`
- `services/event_store.py` → `GeneralSerializer`
- `services/thread_state_service.py` → `LangGraphSerializer`

#### 7. sse.py (SSE 포맷팅)
**의존성**:
- `serializers/` → `GeneralSerializer`
**사용자**:
- `services/streaming_service.py` → `create_error_event`, `create_metadata_event`
- `services/event_converter.py` → 모든 create_*_event 함수들
- `api/runs.py` → `get_sse_headers`, `create_end_event`

#### 8. health.py (헬스 체크)
**의존성**:
- `database.py` → `db_manager`
**사용자**:
- `main.py` → 라우터 등록

---

## 사용 예제

### 1. 데이터베이스 접근

#### Services에서 LangGraph 컴포넌트 사용
```python
# services/langgraph_service.py
from ..core.database import db_manager

class LangGraphService:
    async def invoke_graph(self, graph, config):
        # LangGraph 체크포인터 가져오기
        checkpointer = await db_manager.get_checkpointer()

        # 그래프 실행 시 체크포인터 전달
        compiled_graph = graph.compile(checkpointer=checkpointer)
        result = await compiled_graph.ainvoke(input_data, config)
        return result
```

#### API에서 ORM 세션 사용
```python
# api/assistants.py
from ..core.orm import get_session
from ..core.orm import Assistant as AssistantORM

@router.get("/assistants")
async def list_assistants(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
):
    # 사용자의 어시스턴트 조회
    result = await session.execute(
        select(AssistantORM)
        .where(AssistantORM.user_id == user.identity)
    )
    assistants = result.scalars().all()
    return assistants
```

### 2. 인증 사용

#### 라우터에서 인증 확인
```python
# api/runs.py
from ..core.auth_deps import get_current_user, require_permission

@router.post("/threads/{thread_id}/runs")
async def create_run(
    thread_id: str,
    user: User = Depends(get_current_user)
):
    # user는 자동으로 주입됨
    # 미인증 시 401 예외 자동 발생
    return {"thread_id": thread_id, "user_id": user.identity}

@router.delete("/admin/reset")
async def reset_database(
    admin: User = Depends(require_permission("admin"))
):
    # admin 권한 필요, 없으면 403 예외
    # 권한 있는 경우에만 이 함수 실행됨
```

#### 그래프에서 인증 컨텍스트 접근
```python
# graphs/my_agent.py
from src.agent_server.core.auth_ctx import get_auth_ctx

def my_node(state):
    # 현재 실행 중인 사용자 확인
    auth_ctx = get_auth_ctx()
    if auth_ctx and auth_ctx.user:
        user_id = auth_ctx.user.identity
        permissions = auth_ctx.permissions

        # 사용자별 로직 처리
        if "premium" in permissions:
            # 프리미엄 기능
            pass

    return state
```

#### 실행 시 컨텍스트 주입
```python
# services/streaming_service.py
from ..core.auth_ctx import with_auth_ctx

async def stream_run(run_id, user, graph, input_data):
    # 그래프 실행 중 인증 컨텍스트 주입
    async with with_auth_ctx(user, user.permissions):
        async for chunk in graph.astream(input_data):
            yield chunk
    # 블록 종료 시 자동으로 컨텍스트 정리
```

### 3. 직렬화 사용

#### 범용 직렬화
```python
from ..core.serializers import GeneralSerializer

serializer = GeneralSerializer()

# Pydantic 모델 직렬화
pydantic_obj = MyModel(name="test", value=42)
json_data = serializer.serialize(pydantic_obj)
# → {"name": "test", "value": 42}

# LangGraph Interrupt 직렬화
interrupt = Interrupt(value={"question": "Continue?"}, id="int_1")
json_data = serializer.serialize(interrupt)
# → {"value": {"question": "Continue?"}, "id": "int_1"}
```

#### LangGraph 특화 직렬화
```python
from ..core.serializers import LangGraphSerializer

lg_serializer = LangGraphSerializer()

# Task 직렬화
task = PregelTask(id="task_1", name="my_node", ...)
task_dict = lg_serializer.serialize_task(task)
# → {"id": "task_1", "name": "my_node", "interrupts": [], ...}

# 스냅샷에서 tasks 추출
snapshot = await checkpointer.aget_tuple(config)
tasks = lg_serializer.extract_tasks_from_snapshot(snapshot)
```

### 4. SSE 스트리밍

#### 기본 SSE 이벤트 생성
```python
from ..core.sse import (
    get_sse_headers,
    create_metadata_event,
    create_values_event,
    create_end_event,
    format_sse_message
)

from fastapi.responses import StreamingResponse

@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    async def event_generator():
        # 메타데이터 전송
        yield create_metadata_event(run_id, event_id=f"{run_id}_event_0")

        # 값 전송
        yield create_values_event(
            {"messages": [{"role": "assistant", "content": "Hello"}]},
            event_id=f"{run_id}_event_1"
        )

        # 종료 이벤트
        yield create_end_event(event_id=f"{run_id}_event_2")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=get_sse_headers()
    )
```

#### 커스텀 SSE 이벤트
```python
from ..core.sse import format_sse_message

async def custom_stream():
    # 커스텀 이벤트 타입
    yield format_sse_message(
        event="progress",
        data={"step": 1, "total": 10, "percent": 10},
        event_id="custom_1"
    )

    # 에러 처리
    try:
        # ... 작업 수행
        pass
    except Exception as e:
        yield format_sse_message(
            event="error",
            data={"error": str(e), "timestamp": datetime.now(UTC).isoformat()},
            event_id="error_1"
        )
```

### 5. 헬스 체크

#### 서비스 상태 확인
```python
import httpx

# 프로덕션 환경에서 서비스 상태 확인
async def check_service_health():
    async with httpx.AsyncClient() as client:
        # 포괄적 헬스 체크
        response = await client.get("http://localhost:8000/health")
        if response.status_code == 200:
            health = response.json()
            print(f"Database: {health['database']}")
            print(f"Checkpointer: {health['langgraph_checkpointer']}")
            print(f"Store: {health['langgraph_store']}")
        else:
            print("Service unhealthy!")
```

#### Kubernetes 설정
```yaml
# kubernetes deployment.yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: open-langgraph
    image: open-langgraph:latest
    livenessProbe:
      httpGet:
        path: /live
        port: 8000
      initialDelaySeconds: 10
      periodSeconds: 30
    readinessProbe:
      httpGet:
        path: /ready
        port: 8000
      initialDelaySeconds: 5
      periodSeconds: 10
```

---

## 진입점 (Entry Points)

다른 레이어에서 Core를 사용하는 방법

### API Layer → Core

#### 1. 데이터베이스 세션 (ORM)
```python
# api/assistants.py
from ..core.orm import get_session, Assistant as AssistantORM

@router.get("/assistants/{assistant_id}")
async def get_assistant(
    assistant_id: str,
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(AssistantORM).where(AssistantORM.assistant_id == assistant_id)
    )
    return result.scalar_one_or_none()
```

#### 2. 인증 의존성
```python
# api/threads.py
from ..core.auth_deps import get_current_user

@router.post("/threads")
async def create_thread(
    user: User = Depends(get_current_user)
):
    # user.identity로 사용자 ID 접근
    return {"user_id": user.identity}
```

#### 3. SSE 헤더 및 이벤트
```python
# api/runs.py
from ..core.sse import get_sse_headers, create_end_event

@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    async def event_gen():
        yield create_end_event()

    return StreamingResponse(
        event_gen(),
        headers=get_sse_headers()
    )
```

#### 4. LangGraph Store (장기 메모리)
```python
# api/store.py
from ..core.database import db_manager

@router.put("/store/items")
async def put_store_item(namespace: list[str], key: str, value: dict):
    store = await db_manager.get_store()
    await store.aput((tuple(namespace),), key, value)
    return {"status": "ok"}
```

### Services Layer → Core

#### 1. LangGraph 체크포인터
```python
# services/langgraph_service.py
from ..core.database import db_manager

class LangGraphService:
    async def get_compiled_graph(self, graph_id: str):
        checkpointer = await db_manager.get_checkpointer()
        graph = self._load_graph(graph_id)
        return graph.compile(checkpointer=checkpointer)
```

#### 2. 직렬화
```python
# services/event_converter.py
from ..core.serializers import GeneralSerializer

class EventConverter:
    def __init__(self):
        self.serializer = GeneralSerializer()

    def convert_event(self, langgraph_event):
        # LangGraph 이벤트를 JSON으로 변환
        return self.serializer.serialize(langgraph_event)
```

#### 3. 인증 컨텍스트 주입
```python
# services/streaming_service.py
from ..core.auth_ctx import with_auth_ctx

async def execute_with_context(user, graph, input_data):
    async with with_auth_ctx(user, user.permissions):
        result = await graph.ainvoke(input_data)
    return result
```

#### 4. SSE 이벤트 생성
```python
# services/event_converter.py
from ..core.sse import (
    create_values_event,
    create_debug_event,
    create_messages_event
)

class EventConverter:
    def convert_to_sse(self, event_type, event_data, event_id):
        if event_type == "values":
            return create_values_event(event_data, event_id)
        elif event_type == "debug":
            return create_debug_event(event_data, event_id)
        elif event_type.startswith("messages"):
            return create_messages_event(event_data, event_type, event_id)
```

### Main App → Core

#### 1. 애플리케이션 라이프사이클
```python
# main.py
from .core.database import db_manager
from .core.health import router as health_router
from .core.auth_middleware import get_auth_backend, on_auth_error
from starlette.middleware.authentication import AuthenticationMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 DB 초기화
    await db_manager.initialize()
    yield
    # 종료 시 DB 연결 정리
    await db_manager.close()

app = FastAPI(lifespan=lifespan)

# 인증 미들웨어 등록
app.add_middleware(
    AuthenticationMiddleware,
    backend=get_auth_backend(),
    on_error=on_auth_error
)

# 헬스 체크 라우터 등록
app.include_router(health_router)
```

### Graph Nodes → Core

#### 1. 인증 컨텍스트 접근
```python
# graphs/my_agent.py
from src.agent_server.core.auth_ctx import get_auth_ctx

def my_secure_node(state):
    auth_ctx = get_auth_ctx()

    if not auth_ctx or not auth_ctx.user:
        raise ValueError("Authentication required")

    user_id = auth_ctx.user.identity
    permissions = auth_ctx.permissions

    # 사용자별 로직
    if "premium" in permissions:
        # 프리미엄 기능
        pass
    else:
        # 기본 기능
        pass

    return state
```

---

## 모범 사례 (Best Practices)

### 1. 데이터베이스 접근

✅ **올바른 방법**:
```python
# Services나 API에서 db_manager 사용
from ..core.database import db_manager

checkpointer = await db_manager.get_checkpointer()
```

❌ **잘못된 방법**:
```python
# LangGraph 컴포넌트를 직접 생성하지 마세요
checkpointer = AsyncPostgresSaver.from_conn_string(...)  # ❌
```

### 2. ORM 세션 관리

✅ **올바른 방법**:
```python
# FastAPI Depends로 세션 주입
async def my_endpoint(session: AsyncSession = Depends(get_session)):
    # 세션 자동 정리됨
    result = await session.execute(select(Assistant))
```

❌ **잘못된 방법**:
```python
# 수동 세션 생성 및 관리 (복잡하고 에러 발생 가능)
maker = async_sessionmaker(engine)
session = maker()
try:
    result = await session.execute(select(Assistant))
finally:
    await session.close()  # 까먹기 쉬움
```

### 3. 인증 처리

✅ **올바른 방법**:
```python
# 의존성 주입으로 인증 확인
async def endpoint(user: User = Depends(get_current_user)):
    # user는 이미 검증됨
    return {"user_id": user.identity}
```

❌ **잘못된 방법**:
```python
# 수동 인증 체크 (중복 코드)
async def endpoint(request: Request):
    if not hasattr(request, "user") or not request.user.is_authenticated:
        raise HTTPException(401, "Unauthorized")  # ❌
    user_id = request.user.identity
```

### 4. 직렬화

✅ **올바른 방법**:
```python
# GeneralSerializer 사용 (LangGraph 호환)
from ..core.serializers import GeneralSerializer

serializer = GeneralSerializer()
json_data = json.dumps(obj, default=serializer.serialize)
```

❌ **잘못된 방법**:
```python
# 기본 json.dumps (복잡한 객체 실패)
json_data = json.dumps(obj)  # ❌ Pydantic, NamedTuple 등 실패
```

### 5. SSE 스트리밍

✅ **올바른 방법**:
```python
# 표준 SSE 헤더 사용
from ..core.sse import get_sse_headers, create_values_event

return StreamingResponse(
    event_gen(),
    headers=get_sse_headers()
)
```

❌ **잘못된 방법**:
```python
# 헤더 수동 작성 (누락 가능)
return StreamingResponse(
    event_gen(),
    headers={"Content-Type": "text/event-stream"}  # ❌ 불완전
)
```

---

## 트러블슈팅

### 1. Database not initialized 오류

**증상**:
```
RuntimeError: Database not initialized
```

**원인**: `db_manager.initialize()`가 호출되지 않음

**해결**:
```python
# main.py의 lifespan에서 초기화 확인
@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_manager.initialize()  # 반드시 필요
    yield
    await db_manager.close()
```

### 2. Authentication required 401 오류

**증상**:
```json
{"error": "unauthorized", "message": "Authentication required"}
```

**원인**:
1. Authorization 헤더 누락
2. auth.py의 authenticate 핸들러 미구현
3. AUTH_TYPE 환경 변수 잘못 설정

**해결**:
```bash
# 개발 시 인증 비활성화
AUTH_TYPE=noop

# 커스텀 인증 사용
AUTH_TYPE=custom  # auth.py 구현 필요
```

### 3. SSE 연결 끊김

**증상**: 클라이언트가 일부 이벤트만 받고 연결이 끊김

**원인**:
1. SSE 형식 불일치 (빈 줄 누락)
2. 직렬화 실패로 예외 발생

**해결**:
```python
# format_sse_message 사용 (형식 보장)
from ..core.sse import format_sse_message

yield format_sse_message("values", data, event_id)
# 자동으로 올바른 형식: "event: ...\ndata: ...\n\n"
```

### 4. Serialization failed 오류

**증상**:
```
SerializationError: Failed to serialize object
```

**원인**: JSON 직렬화 불가능한 객체 (datetime, custom class 등)

**해결**:
```python
# GeneralSerializer 사용 (대부분 처리)
from ..core.serializers import GeneralSerializer

serializer = GeneralSerializer()
safe_data = serializer.serialize(complex_obj)

# 커스텀 객체는 __str__ 또는 dict() 메서드 구현
class MyClass:
    def __str__(self):
        return f"MyClass(value={self.value})"
```

### 5. LangGraph URL format error

**증상**:
```
ValueError: Invalid connection string format
```

**원인**: LangGraph는 `postgresql://` 필요, `postgresql+asyncpg://` 사용 시 오류

**해결**: DatabaseManager가 자동 변환하므로 db_manager 사용
```python
# ✅ 자동 변환됨
checkpointer = await db_manager.get_checkpointer()

# ❌ 수동으로 생성하지 마세요
checkpointer = AsyncPostgresSaver.from_conn_string(
    "postgresql+asyncpg://..."  # LangGraph가 인식 못함
)
```

---

## 요약

Core 레이어는 Open LangGraph의 **기반 인프라**로서 다음을 제공합니다:

1. **데이터베이스 관리** (`database.py`):
   - SQLAlchemy + LangGraph 통합
   - 싱글톤 패턴의 `db_manager`
   - 지연 초기화로 성능 최적화

2. **ORM 모델** (`orm.py`):
   - Agent Protocol 메타데이터 테이블
   - FastAPI 의존성 주입 지원
   - 멀티테넌트 격리 (user_id 인덱스)

3. **인증 시스템** (`auth_*.py`):
   - LangGraph SDK Auth 통합
   - Starlette 미들웨어 연동
   - 그래프 노드에서 컨텍스트 접근

4. **직렬화** (`serializers/`):
   - LangGraph 객체의 JSON 변환
   - Pydantic, NamedTuple 등 지원
   - 안전한 fallback

5. **SSE 스트리밍** (`sse.py`):
   - 표준 SSE 형식 보장
   - LangSmith Studio 호환
   - 다양한 이벤트 타입

6. **헬스 체크** (`health.py`):
   - Kubernetes 프로브 지원
   - 전체 스택 상태 확인

**사용 시 유의사항**:
- 항상 `db_manager`를 통해 DB 접근
- FastAPI Depends로 세션과 인증 주입
- SSE는 `create_*_event` 함수 사용
- 직렬화는 `GeneralSerializer` 사용

Core는 **변경에 닫혀있고 확장에 열려있는** 안정적인 기반을 제공합니다.
