# Open LangGraph 아키텍처 가이드

## 목차

1. [시스템 개요](#시스템-개요)
2. [아키텍처 원칙](#아키텍처-원칙)
3. [핵심 레이어](#핵심-레이어)
4. [데이터베이스 아키텍처](#데이터베이스-아키텍처)
5. [핵심 컴포넌트](#핵심-컴포넌트)
6. [데이터 흐름](#데이터-흐름)
7. [인증 시스템](#인증-시스템)
8. [그래프 실행 모델](#그래프-실행-모델)
9. [스트리밍 아키텍처](#스트리밍-아키텍처)
10. [라이프사이클 관리](#라이프사이클-관리)

---

## 시스템 개요

Open LangGraph는 **Agent Protocol 서버**로, **공식 LangGraph 패키지**를 HTTP API로 감싸는 아키텍처를 채택하고 있습니다.

### 핵심 설계 철학

```bash
┌─────────────────────────────────────────────────────┐
│                  Agent Protocol                      │
│              (표준 HTTP API 인터페이스)                │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│                 FastAPI Layer                        │
│      (라우팅, 인증, 스트리밍, 메타데이터)                │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│               LangGraph Core                         │
│   (상태 관리, 그래프 실행, 체크포인트, 메모리)             │
└──────────────────────────────────────────────────────┘
```

**핵심 원칙**: LangGraph가 **모든** 상태 영속화와 그래프 실행을 담당하고, FastAPI 레이어는 **Agent Protocol 준수**만 제공합니다.

---

## 아키텍처 원칙

### 1. 관심사 분리

| 레이어 | 책임 | 사용 기술 |
|--------|------|----------|
| **API Layer** | HTTP 라우팅, 인증, SSE 스트리밍 | FastAPI, LangGraph SDK Auth |
| **Service Layer** | 비즈니스 로직, 이벤트 변환, 브로커 관리 | Python 서비스 클래스 |
| **Core Layer** | 데이터베이스 연결, LangGraph 통합 | SQLAlchemy, LangGraph |
| **LangGraph** | 그래프 실행, 상태 영속화, 메모리 | LangGraph Checkpoint/Store |

### 2. 데이터베이스 이중화 전략

Open LangGraph는 **하이브리드 데이터베이스 아키텍처**를 사용합니다:

- **LangGraph가 상태 관리**: 대화 체크포인트, 상태 히스토리, 장기 메모리
- **SQLAlchemy가 메타데이터 관리**: Agent Protocol 메타데이터만 (최소한의 테이블)

```
PostgreSQL
├── LangGraph 테이블 (AsyncPostgresSaver/Store가 생성)
│   ├── checkpoints: 상태 스냅샷
│   ├── checkpoint_writes: 상태 변경 기록
│   └── store: 키-값 장기 메모리
│
└── Agent Protocol 테이블 (Alembic 마이그레이션으로 관리)
    ├── assistants: 그래프 메타데이터
    ├── threads: 대화 스레드 메타데이터
    ├── runs: 실행 메타데이터
    └── run_events: SSE 이벤트 영속화
```

### 3. 싱글톤 패턴

전역 싱글톤 인스턴스로 리소스 공유 및 일관성 유지:

```python
# 데이터베이스 관리자
db_manager = DatabaseManager()

# 서비스 인스턴스
langgraph_service = LangGraphService()
streaming_service = StreamingService()
event_store = EventStore()
broker_manager = BrokerManager()
```

---

## 핵심 레이어

### API 레이어 (`src/agent_server/api/`)

**엔드포인트 구조**:

```python
# src/agent_server/main.py
app.include_router(health_router)        # /health
app.include_router(assistants_router)    # /assistants
app.include_router(threads_router)       # /threads
app.include_router(runs_router)          # /threads/{thread_id}/runs
app.include_router(store_router)         # /store
```

**미들웨어 스택 (처리 순서)**:

```
┌────────────────────────────────────┐
│    1. CORS Middleware              │  ← 교차 출처 요청 처리
├────────────────────────────────────┤
│    2. DoubleEncodedJSON            │  ← 프론트엔드 이중 인코딩 처리
├────────────────────────────────────┤
│    3. Authentication Middleware    │  ← LangGraph SDK 기반 인증
├────────────────────────────────────┤
│    4. Router (API Endpoints)       │  ← 라우팅 및 핸들러
└────────────────────────────────────┘
```

### 서비스 레이어 (`src/agent_server/services/`)

각 서비스는 명확한 책임을 가집니다:

| 서비스 | 파일 | 책임 |
|--------|------|------|
| **LangGraphService** | `langgraph_service.py` | 그래프 로딩, 캐싱, 설정 관리, 기본 어시스턴트 생성 |
| **StreamingService** | `streaming_service.py` | SSE 스트리밍 오케스트레이션, 이벤트 분배 |
| **EventStore** | `event_store.py` | 이벤트 영속화, 재연결 시 재생, 자동 정리 |
| **BrokerManager** | `broker.py` | 실행별 이벤트 큐 관리, Producer-Consumer 패턴 |
| **EventConverter** | `event_converter.py` | LangGraph → Agent Protocol 이벤트 변환 |
| **ThreadStateService** | `thread_state_service.py` | 스레드 상태 조회, 체크포인트 히스토리 |

### 핵심 레이어 (`src/agent_server/core/`)

시스템의 기초 구성 요소:

```python
# 데이터베이스 관리
database.py          # DatabaseManager: SQLAlchemy + LangGraph 통합
orm.py               # SQLAlchemy 모델 정의 (Agent Protocol 메타데이터)

# 인증
auth_middleware.py   # LangGraph SDK Auth 미들웨어
auth_deps.py         # FastAPI 의존성 주입용 인증 헬퍼
auth_ctx.py          # 사용자 컨텍스트 주입 데코레이터

# SSE 스트리밍
sse.py               # SSE 이벤트 생성 유틸리티

# 직렬화
serializers.py       # LangGraph 객체 JSON 직렬화
```

---

## 데이터베이스 아키텍처

### DatabaseManager 패턴

`DatabaseManager`는 Open LangGraph의 데이터베이스 연결 및 LangGraph 영속성 컴포넌트를 총괄합니다.

```python
class DatabaseManager:
    """데이터베이스 연결 및 LangGraph 영속성 컴포넌트 관리자"""

    def __init__(self):
        self.engine: AsyncEngine | None = None           # SQLAlchemy
        self._checkpointer: AsyncPostgresSaver | None    # LangGraph
        self._store: AsyncPostgresStore | None           # LangGraph
```

**주요 기능**:

1. **URL 형식 자동 변환**
   ```python
   # SQLAlchemy는 asyncpg 드라이버 사용
   DATABASE_URL = "postgresql+asyncpg://user:pass@host/db"

   # LangGraph는 psycopg 드라이버 사용
   langgraph_dsn = DATABASE_URL.replace(
       "postgresql+asyncpg://",
       "postgresql://"
   )
   ```

2. **컨텍스트 매니저 기반 리소스 관리**
   ```python
   async def get_checkpointer(self) -> AsyncPostgresSaver:
       if self._checkpointer is None:
           # 컨텍스트 매니저 진입 및 캐싱
           self._checkpointer_cm = AsyncPostgresSaver.from_conn_string(
               self._langgraph_dsn
           )
           self._checkpointer = await self._checkpointer_cm.__aenter__()
           await self._checkpointer.setup()  # 테이블 생성 (멱등성)
       return self._checkpointer
   ```

3. **싱글톤 패턴으로 전역 접근**
   ```python
   # 전역 인스턴스
   db_manager = DatabaseManager()

   # 애플리케이션 전체에서 사용
   engine = db_manager.get_engine()
   checkpointer = await db_manager.get_checkpointer()
   store = await db_manager.get_store()
   ```

### 데이터베이스 스키마 관리

**Alembic 기반 마이그레이션**:

```bash
# 마이그레이션 적용
python3 scripts/migrate.py upgrade

# 새 마이그레이션 생성
python3 scripts/migrate.py revision --autogenerate -m "description"

# 상태 확인
python3 scripts/migrate.py current
```

**마이그레이션 파일 구조**:

```
alembic/
├── versions/           # 마이그레이션 파일들
│   ├── 001_initial.py
│   ├── 002_add_events.py
│   └── ...
├── env.py             # Alembic 환경 설정 (비동기 지원)
└── script.py.mako     # 템플릿
```

---

## 핵심 컴포넌트

### 1. DatabaseManager (`core/database.py`)

**역할**: 데이터베이스 연결 및 LangGraph 컴포넌트 생명주기 관리

```python
class DatabaseManager:
    async def initialize(self) -> None:
        """FastAPI 시작 시 호출 (lifespan)"""
        # SQLAlchemy 엔진 생성
        self.engine = create_async_engine(self._database_url)

        # LangGraph DSN 준비 (URL 변환)
        self._langgraph_dsn = self._database_url.replace(
            "postgresql+asyncpg://",
            "postgresql://"
        )

    async def get_checkpointer(self) -> AsyncPostgresSaver:
        """LangGraph 체크포인터 반환 (캐싱)"""
        # 첫 호출 시 컨텍스트 매니저 진입 및 캐싱
        # 이후 호출 시 캐시된 인스턴스 재사용

    async def get_store(self) -> AsyncPostgresStore:
        """LangGraph Store 반환 (캐싱)"""
        # 장기 메모리 및 키-값 저장소
```

**캐싱 이유**:
- LangGraph는 실제 saver/store 객체가 필요 (메서드 호출)
- 컨텍스트 매니저 래퍼를 반환하면 실패
- 연결 풀 재사용으로 성능 향상

### 2. LangGraphService (`services/langgraph_service.py`)

**역할**: 그래프 로딩, 캐싱, 설정 관리

```python
class LangGraphService:
    """그래프 레지스트리 및 실행 설정 관리"""

    async def initialize(self):
        """open_langgraph.json 로드 및 기본 어시스턴트 생성"""
        # 1. 설정 파일 찾기 (우선순위 적용)
        # 2. 그래프 레지스트리 초기화
        # 3. 각 그래프에 대한 기본 어시스턴트 생성

    async def get_graph(self, graph_id: str):
        """그래프 로드 및 컴파일 (캐싱)"""
        # 1. 캐시 확인
        # 2. 없으면 모듈 동적 임포트
        # 3. Postgres 체크포인터와 함께 컴파일
        # 4. 캐시에 저장 후 반환
```

**그래프 등록 흐름**:

```
open_langgraph.json
{
  "graphs": {
    "agent": "./graphs/react_agent/graph.py:graph"
  }
}
         ↓
LangGraphService.initialize()
         ↓
기본 어시스턴트 생성 (deterministic UUID)
         ↓
uuid5(NAMESPACE, "agent")
         ↓
DB에 저장 (assistants 테이블)
```

**설정 헬퍼 함수**:

```python
def inject_user_context(config: dict, user: User) -> dict:
    """사용자 컨텍스트를 LangGraph config에 주입"""
    config["configurable"]["user_id"] = user.identity
    config["configurable"]["user_data"] = user.metadata

def create_thread_config(thread_id: str, user: User) -> dict:
    """스레드별 실행 설정 생성"""
    return {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "",
            "checkpoint_id": "",
        }
    }

def create_run_config(run_id: str, thread_id: str, user: User) -> dict:
    """실행별 설정 생성 (관찰성 콜백 포함)"""
    config = create_thread_config(thread_id, user)

    # Langfuse 관찰성 통합
    if LANGFUSE_LOGGING:
        config["callbacks"] = get_tracing_callbacks(run_id, thread_id, user)

    return config
```

### 3. StreamingService (`services/streaming_service.py`)

**역할**: SSE 스트리밍 오케스트레이션 및 이벤트 분배

```python
class StreamingService:
    """SSE 스트리밍 총괄 서비스"""

    async def stream_run_execution(
        self,
        run: Run,
        last_event_id: str | None = None
    ) -> AsyncIterator[str]:
        """실행 이벤트를 SSE로 스트리밍 (재연결 지원)"""

        # 1. 재연결 시 과거 이벤트 재생
        if last_event_id:
            async for event in self._replay_events(run.run_id, last_event_id):
                yield event

        # 2. 실시간 이벤트 브로커에서 수신
        broker = broker_manager.get_or_create_broker(run.run_id)
        async for event_id, payload in broker.aiter():
            # 3. LangGraph → Agent Protocol 변환
            sse_event = self.event_converter.convert(payload)

            # 4. 클라이언트에 전송
            yield sse_event.to_string()
```

**이벤트 변환 흐름**:

```
LangGraph Event
{"event": "on_chain_start", "data": {...}}
         ↓
EventConverter.convert()
         ↓
Agent Protocol SSE
event: thread.run.step.created
data: {"type": "message_creation", ...}
```

### 4. EventStore (`services/event_store.py`)

**역할**: PostgreSQL 기반 이벤트 영속화 및 재생

```python
class EventStore:
    """SSE 이벤트 저장소"""

    async def store_event(
        self,
        run_id: str,
        event_id: str,
        event: str,
        data: Any
    ):
        """이벤트를 run_events 테이블에 저장"""
        # 시퀀스 번호 추출 (예: "run_123_event_42" → 42)
        seq = extract_event_sequence(event_id)

        # PostgreSQL JSONB로 저장
        await engine.execute(
            text("INSERT INTO run_events (run_id, seq, event, data) ...")
        )

    async def get_events_since(
        self,
        run_id: str,
        last_event_id: str
    ) -> list[SSEEvent]:
        """특정 시점 이후 이벤트 조회 (재연결)"""
        last_seq = extract_event_sequence(last_event_id)

        # 시퀀스 번호로 조회
        result = await engine.execute(
            text("SELECT * FROM run_events WHERE run_id = :run_id AND seq > :seq ORDER BY seq")
        )
        return [SSEEvent(...) for row in result]
```

**자동 정리 작업**:

```python
async def _cleanup_loop(self):
    """백그라운드 정리 루프 (5분마다)"""
    while True:
        await asyncio.sleep(300)

        # 1시간 이상 된 이벤트 삭제
        await engine.execute(
            text("DELETE FROM run_events WHERE created_at < NOW() - INTERVAL '1 hour'")
        )
```

### 5. BrokerManager (`services/broker.py`)

**역할**: 실행별 이벤트 큐 관리 (Producer-Consumer 패턴)

```python
class RunBroker:
    """단일 실행의 이벤트 브로커"""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.queue: asyncio.Queue = asyncio.Queue()
        self.finished = asyncio.Event()

    async def put(self, event_id: str, payload: Any):
        """Producer: 이벤트 큐에 추가"""
        await self.queue.put((event_id, payload))

        # "end" 이벤트 감지 시 브로커 완료
        if payload[0] == "end":
            self.mark_finished()

    async def aiter(self) -> AsyncIterator[tuple[str, Any]]:
        """Consumer: 이벤트 순회"""
        while True:
            try:
                event_id, payload = await asyncio.wait_for(
                    self.queue.get(), timeout=0.1
                )
                yield event_id, payload

                # "end" 이벤트 수신 시 종료
                if payload[0] == "end":
                    break
            except asyncio.TimeoutError:
                if self.finished.is_set():
                    break

class BrokerManager:
    """여러 RunBroker 인스턴스 관리"""

    def get_or_create_broker(self, run_id: str) -> RunBroker:
        """실행 ID로 브로커 조회/생성"""
        if run_id not in self._brokers:
            self._brokers[run_id] = RunBroker(run_id)
        return self._brokers[run_id]
```

---

## 데이터 흐름

### 실행 생성 → 백그라운드 처리 → SSE 스트리밍

**전체 흐름도**:

```
1. HTTP POST /threads/{thread_id}/runs/stream
         ↓
2. create_run_streaming(run_create)
         ↓
3. Run ORM 생성 (DB 저장)
         ↓
4. asyncio.create_task(execute_run_async)  ← 백그라운드 실행
         ↓                                     ↓
5. StreamingResponse                    6. graph.astream(...)
         ↓                                     ↓
7. streaming_service.stream_run_execution()   LangGraph 이벤트 생성
         ↓                                     ↓
8. broker.aiter()  ←────────────────────  broker.put(event)
         ↓                                     ↓
9. EventConverter                         event_store.store_event()
         ↓
10. SSE → Client
```

**백그라운드 실행 상세 (`execute_run_async`)**:

```python
async def execute_run_async(
    run: Run,
    input_data: dict,
    stream_modes: list[str],
    user: User
):
    """백그라운드에서 그래프 실행 (Producer 역할)"""

    # 1. 그래프 로드
    graph = await langgraph_service.get_graph(run.assistant_id)

    # 2. 실행 설정 생성 (사용자 컨텍스트 포함)
    config = create_run_config(run.run_id, run.thread_id, user)

    # 3. 브로커 생성
    broker = broker_manager.get_or_create_broker(run.run_id)

    # 4. LangGraph 스트리밍 실행
    async for raw_event in graph.astream(
        input_data,
        config=config,
        stream_mode=stream_modes
    ):
        # 5. 이벤트 ID 생성
        event_id = generate_event_id(run.run_id, seq)

        # 6. 브로커에 전송 (Consumer가 수신)
        await broker.put(event_id, raw_event)

        # 7. 이벤트 저장소에 영속화 (재연결용)
        await store_sse_event(run.run_id, event_id, raw_event)

    # 8. 실행 완료 처리
    await update_run_status(run.run_id, "success")
```

### 체크포인트 저장 → 상태 복원

**체크포인트 생명주기**:

```
그래프 실행 중 노드 완료
         ↓
AsyncPostgresSaver.aput()
         ↓
checkpoints 테이블에 저장
{
  thread_id: "thread_123",
  checkpoint_ns: "",
  checkpoint_id: "1ef...",
  channel_values: {...},  ← 현재 상태
  channel_versions: {...}
}
         ↓
이후 실행 시 자동 복원
         ↓
graph.astream(..., config={"configurable": {"thread_id": "thread_123"}})
         ↓
AsyncPostgresSaver.aget()
         ↓
마지막 체크포인트 로드
```

**상태 조회 API**:

```python
# GET /threads/{thread_id}/state
async def get_thread_state(thread_id: str):
    checkpointer = await db_manager.get_checkpointer()

    # 최신 체크포인트 조회
    config = {"configurable": {"thread_id": thread_id}}
    state = await checkpointer.aget(config)

    return {
        "values": state["channel_values"],
        "next": state.get("next", []),
        "checkpoint": state["checkpoint"]
    }
```

### 인터럽트 → 승인 → 재개

**Human-in-the-Loop (HITL) 흐름**:

```
1. 그래프 노드에서 interrupt() 호출
         ↓
2. LangGraph가 체크포인트 저장 후 중단
         ↓
3. "end" 이벤트 발행 (status="requires_action")
         ↓
4. Client가 승인 또는 거부 결정
         ↓
5. PATCH /threads/{thread_id}/runs/{run_id}
   {
     "command": {
       "resume": "approved",  ← 또는 "rejected"
       "goto": ["next_node"]
     }
   }
         ↓
6. graph.astream(..., input=Command(...))
         ↓
7. 체크포인트에서 상태 복원 후 재개
```

**인터럽트 구현 예시**:

```python
# graphs/react_agent_hitl/graph.py
def approval_node(state: State, runtime: Runtime[Context]):
    """인간 승인이 필요한 노드"""

    # 승인 요청 생성
    approval_request = {
        "type": "approval_required",
        "action": state["planned_action"],
        "reason": "This action requires human approval"
    }

    # 실행 중단 (체크포인트 저장)
    interrupt(approval_request)

    # 재개 시 이 지점부터 계속 실행
    if state.get("approved"):
        return {"status": "approved"}
    else:
        return {"status": "rejected"}
```

---

## 인증 시스템

### LangGraph SDK Auth 통합

Open LangGraph는 **LangGraph SDK Auth**를 사용하여 인증 및 권한 부여를 처리합니다.

**인증 흐름**:

```
1. HTTP Request
   Authorization: Bearer <token>
         ↓
2. AuthenticationMiddleware (Starlette)
         ↓
3. get_auth_backend()
         ↓
4. @auth.authenticate 호출 (auth.py)
         ↓
5. MinimalUserDict 반환
   {
     "identity": "user_123",
     "display_name": "John Doe",
     "email": "john@example.com",
     "permissions": ["admin"],
     "org_id": "org_456",
     "is_authenticated": True
   }
         ↓
6. request.user에 저장
         ↓
7. FastAPI 라우터 핸들러
   user = get_current_user(request)
```

### 인증 타입

**환경 변수 기반 전환**:

```bash
# .env
AUTH_TYPE=noop    # 인증 없음 (개발용)
AUTH_TYPE=custom  # 커스텀 인증 (프로덕션)
```

**Noop 인증** (`AUTH_TYPE=noop`):

```python
# auth.py
@auth.authenticate
async def authenticate(headers: dict[str, str]) -> MinimalUserDict:
    """모든 요청 허용"""
    return {
        "identity": "anonymous",
        "display_name": "Anonymous User",
        "is_authenticated": True,
    }

@auth.on
async def authorize(ctx: AuthContext, value: dict) -> dict:
    """모든 리소스 접근 허용"""
    return {}  # 빈 필터 = 접근 제한 없음
```

**커스텀 인증** (`AUTH_TYPE=custom`):

```python
# auth.py
@auth.authenticate
async def authenticate(headers: dict[str, str]) -> MinimalUserDict:
    """커스텀 인증 로직 (Firebase, JWT 등)"""
    authorization = headers.get("authorization")

    if not authorization:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="Authorization header required"
        )

    # 토큰 검증 로직
    if authorization == "Bearer dev-token":
        return {
            "identity": "dev-user",
            "display_name": "Development User",
            "email": "dev@example.com",
            "permissions": ["admin"],
            "org_id": "dev-org",
            "is_authenticated": True,
        }

    # 실제 인증 서비스 연동
    # user = await verify_token(authorization)
    # return user_to_minimal_dict(user)

    raise Auth.exceptions.HTTPException(
        status_code=401,
        detail="Invalid authentication token"
    )
```

### 권한 부여 (Authorization)

**리소스별 접근 제어**:

```python
# auth.py
@auth.on
async def authorize(ctx: AuthContext, value: dict) -> dict:
    """사용자별 리소스 필터링"""

    # 컨텍스트 정보
    # ctx.resource: "assistants", "threads", "runs", "store"
    # ctx.action: "create", "read", "update", "delete", "search"
    # ctx.user: MinimalUserDict

    # 관리자는 모든 리소스 접근 가능
    if "admin" in ctx.user.get("permissions", []):
        return {}  # 필터링 없음

    # 일반 사용자는 자신의 org_id 리소스만 접근
    return {
        "user_id": ctx.user["identity"],
        "org_id": ctx.user.get("org_id")
    }
```

**필터링 적용 예시**:

```python
# api/threads.py
async def list_threads(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """스레드 목록 조회 (사용자별 필터링)"""

    # 권한 컨텍스트 생성
    auth_filter = await authorize(
        AuthContext(resource="threads", action="search", user=user),
        value={}
    )

    # WHERE 절 동적 생성
    query = select(ThreadORM)
    if "user_id" in auth_filter:
        query = query.where(ThreadORM.user_id == auth_filter["user_id"])

    result = await session.execute(query)
    return result.scalars().all()
```

### 멀티테넌트 격리

**사용자 컨텍스트 주입**:

```python
# services/langgraph_service.py
def inject_user_context(config: dict, user: User) -> dict:
    """사용자 정보를 LangGraph config에 주입"""
    config["configurable"]["user_id"] = user.identity
    config["configurable"]["user_data"] = {
        "email": user.email,
        "org_id": user.metadata.get("org_id"),
        "permissions": user.metadata.get("permissions", [])
    }
    return config

# 실행 시 자동 주입
config = create_run_config(run_id, thread_id, user)
# config["configurable"]["user_id"] = "user_123"
# config["configurable"]["user_data"] = {...}
```

**그래프에서 사용자 정보 접근**:

```python
# graphs/my_agent/graph.py
def my_node(state: State, runtime: Runtime[Context]):
    """노드에서 사용자 정보 사용"""

    # Runtime[Context]에서 사용자 정보 추출
    user_id = runtime.context.user_id
    org_id = runtime.context.user_data.get("org_id")

    # 사용자별 로직 분기
    if org_id == "premium_org":
        return handle_premium_request(state)
    else:
        return handle_basic_request(state)
```

---

## 그래프 실행 모델

### StateGraph 패턴

LangGraph는 **StateGraph**를 사용하여 에이전트를 정의합니다.

**기본 구조**:

```python
# graphs/my_agent/graph.py
from langgraph.graph import StateGraph, MessagesState, START, END

# 1. 상태 정의
class MyState(MessagesState):
    query: str
    result: str | None
    step_count: int

# 2. 노드 함수 정의
def process_node(state: MyState):
    """상태를 처리하는 노드"""
    return {
        "result": f"Processed: {state['query']}",
        "step_count": state.get("step_count", 0) + 1
    }

def decision_node(state: MyState):
    """분기 결정 노드"""
    if state.get("step_count", 0) > 5:
        return "end"
    else:
        return "process"

# 3. 그래프 구성
workflow = StateGraph(MyState)

# 노드 추가
workflow.add_node("process", process_node)
workflow.add_node("decision", decision_node)

# 엣지 추가
workflow.add_edge(START, "process")
workflow.add_edge("process", "decision")
workflow.add_conditional_edges(
    "decision",
    lambda x: x,  # decision_node의 반환값 사용
    {
        "process": "process",  # 다시 process로
        "end": END             # 종료
    }
)

# 4. 그래프 컴파일 및 내보내기
graph = workflow.compile()  # 반드시 'graph' 이름으로 내보내기
```

**open_langgraph.json 등록**:

```json
{
  "graphs": {
    "my_agent": "./graphs/my_agent/graph.py:graph"
  }
}
```

### Runtime[Context] 패턴

그래프 노드는 `Runtime[Context]`를 통해 사용자 인증 정보 및 설정에 접근할 수 있습니다.

**Context 클래스 정의**:

```python
# graphs/my_agent/graph.py
from langgraph.types import Runtime
from dataclasses import dataclass

@dataclass
class Context:
    """그래프 실행 컨텍스트"""
    user_id: str
    user_data: dict
    model: str = "gpt-4"
    temperature: float = 0.7

def my_node(state: MyState, runtime: Runtime[Context]):
    """Runtime을 통한 컨텍스트 접근"""

    # 사용자 정보
    user_id = runtime.context.user_id
    org_id = runtime.context.user_data.get("org_id")

    # 모델 설정
    model = runtime.context.model
    temperature = runtime.context.temperature

    # LLM 호출 시 사용자별 설정 적용
    response = llm.invoke(
        state["messages"],
        model=model,
        temperature=temperature,
        user=user_id  # 사용자 추적
    )

    return {"messages": [response]}
```

**컨텍스트 주입**:

```python
# 실행 시 자동으로 주입됨
config = create_run_config(run_id, thread_id, user)
config["configurable"]["user_id"] = user.identity
config["configurable"]["user_data"] = {...}

# LangGraph가 Runtime[Context]로 자동 변환
await graph.ainvoke(input_data, config=config)
```

### Human-in-the-Loop (HITL) 패턴

**인터럽트 구현**:

```python
# graphs/react_agent_hitl/graph.py
from langgraph.types import interrupt

def approval_node(state: State, runtime: Runtime[Context]):
    """인간 승인 요청 노드"""

    # 1. 승인 요청 데이터 생성
    approval_data = {
        "type": "tool_approval",
        "tool_name": state["tool_name"],
        "tool_input": state["tool_input"],
        "reason": "This tool requires human approval before execution"
    }

    # 2. 실행 중단 (체크포인트 저장)
    result = interrupt(approval_data)

    # 3. 재개 시 result에 사용자 입력이 담김
    # PATCH /runs/{run_id} {"command": {"resume": "approved"}}

    if result == "approved":
        return {"approved": True, "status": "executing"}
    else:
        return {"approved": False, "status": "cancelled"}

# 조건부 엣지로 분기
workflow.add_conditional_edges(
    "approval",
    lambda state: "execute" if state["approved"] else "cancel",
    {
        "execute": "execute_tool",
        "cancel": END
    }
)
```

**재개 API 호출**:

```bash
# 1. 실행 생성 (인터럽트 발생)
POST /threads/thread_123/runs
{
  "assistant_id": "agent_hitl",
  "input": {"query": "Execute dangerous command"}
}
# → run_id: "run_456", status: "requires_action"

# 2. 승인 또는 거부
PATCH /threads/thread_123/runs/run_456
{
  "command": {
    "resume": "approved",  # 또는 "rejected"
    "goto": ["execute_tool"]  # 선택적: 다음 노드 지정
  }
}
# → 그래프 재개, 체크포인트에서 복원
```

---

## 스트리밍 아키텍처

### Producer-Consumer 패턴

Open LangGraph의 스트리밍은 **Producer-Consumer** 패턴으로 구현됩니다.

**아키텍처 다이어그램**:

```
┌─────────────────────────────────────────────────────────┐
│                     execute_run_async                    │
│                     (Producer)                           │
└─────────────────┬───────────────────────────────────────┘
                  │ put(event_id, payload)
                  ▼
┌─────────────────────────────────────────────────────────┐
│                   RunBroker (Queue)                      │
│              asyncio.Queue[(str, Any)]                   │
└─────────────────┬───────────────────────────────────────┘
                  │ aiter()
                  ▼
┌─────────────────────────────────────────────────────────┐
│              StreamingService (Consumer)                 │
│                  SSE 변환 및 전송                          │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│                    HTTP Client                           │
│               (Server-Sent Events)                       │
└──────────────────────────────────────────────────────────┘
```

**Producer (백그라운드 작업)**:

```python
async def execute_run_async(run: Run, input_data: dict, stream_modes: list[str]):
    """LangGraph 실행 및 이벤트 생성"""

    # 브로커 생성
    broker = broker_manager.get_or_create_broker(run.run_id)

    # LangGraph 스트리밍
    async for raw_event in graph.astream(input_data, stream_mode=stream_modes):
        # 이벤트 ID 생성
        event_id = generate_event_id(run.run_id, seq)

        # 브로커에 전송 (Consumer가 수신)
        await broker.put(event_id, raw_event)

        # 영속화 (재연결용)
        await store_sse_event(run.run_id, event_id, raw_event)

        seq += 1

    # 종료 이벤트
    await broker.put(end_event_id, ("end", {}))
```

**Consumer (SSE 스트림)**:

```python
async def stream_run_execution(run: Run, last_event_id: str | None):
    """브로커에서 이벤트를 읽어 SSE로 전송"""

    # 재연결 시 과거 이벤트 재생
    if last_event_id:
        async for event in event_store.get_events_since(run.run_id, last_event_id):
            yield event.to_string()

    # 실시간 이벤트 수신
    broker = broker_manager.get_or_create_broker(run.run_id)
    async for event_id, payload in broker.aiter():
        # LangGraph → Agent Protocol 변환
        sse_event = event_converter.convert(payload)

        # SSE 형식으로 전송
        yield f"id: {event_id}\n"
        yield f"event: {sse_event.event}\n"
        yield f"data: {json.dumps(sse_event.data)}\n\n"
```

### SSE 이벤트 형식

**LangGraph 이벤트 타입**:

```python
# stream_mode="values"
("values", {"messages": [...], "step_count": 3})

# stream_mode="updates"
("updates", {"__interrupt__": [{"value": {...}, "when": "during"}]})

# stream_mode="messages"
("messages", (AIMessage(content="Hello"), {"langgraph_node": "agent"}))

# stream_mode="custom"
("custom", {"event_type": "tool_start", "data": {...}})

# 종료 이벤트
("end", {})
```

**Agent Protocol SSE 형식**:

```
id: run_123_event_0
event: thread.run.created
data: {"run_id": "run_123", "status": "queued"}

id: run_123_event_1
event: thread.run.step.created
data: {"step": {"type": "message_creation", "step_details": {...}}}

id: run_123_event_2
event: thread.run.step.delta
data: {"delta": {"type": "message_delta", "delta": {"content": [...]}}}

id: run_123_event_3
event: thread.run.completed
data: {"run_id": "run_123", "status": "completed"}

id: run_123_event_4
event: done
data: [DONE]
```

### 재연결 지원

**Last-Event-ID 헤더 사용**:

```
Client                              Server
  │                                   │
  │  GET /runs/run_123/stream         │
  ├──────────────────────────────────>│
  │                                   │
  │  event: thread.run.created        │
  │  id: run_123_event_0              │
  │<──────────────────────────────────┤
  │                                   │
  │  event: thread.run.step.created   │
  │  id: run_123_event_1              │
  │<──────────────────────────────────┤
  │                                   │
  X  연결 끊김                         │
  │                                   │
  │  GET /runs/run_123/stream         │
  │  Last-Event-ID: run_123_event_1   │
  ├──────────────────────────────────>│
  │                                   │
  │  (재생: event_2, event_3, ...)    │
  │<──────────────────────────────────┤
```

**구현**:

```python
# api/runs.py
@router.get("/threads/{thread_id}/runs/{run_id}/stream")
async def stream_run(
    thread_id: str,
    run_id: str,
    last_event_id: str | None = Header(None, alias="Last-Event-ID")
):
    """SSE 스트리밍 (재연결 지원)"""

    async def event_generator():
        async for sse_event in streaming_service.stream_run_execution(
            run,
            last_event_id=last_event_id
        ):
            yield sse_event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Nginx 버퍼링 비활성화
        }
    )
```

---

## 라이프사이클 관리

### FastAPI Lifespan

Open LangGraph는 `@asynccontextmanager`를 사용하여 애플리케이션 수명 주기를 관리합니다.

```python
# src/agent_server/main.py
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """애플리케이션 시작 및 종료 관리"""

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Startup 시퀀스
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # 1. 데이터베이스 및 LangGraph 초기화
    await db_manager.initialize()
    # - SQLAlchemy 엔진 생성
    # - LangGraph DSN 준비

    # 2. LangGraph 서비스 초기화
    service = get_langgraph_service()
    await service.initialize()
    # - open_langgraph.json 로드
    # - 그래프 레지스트리 구성
    # - 기본 어시스턴트 생성

    # 3. 이벤트 저장소 정리 작업 시작
    await event_store.start_cleanup_task()
    # - 5분마다 1시간 이상 된 이벤트 삭제

    print("✅ Application startup complete")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 애플리케이션 실행 중
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    yield

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Shutdown 시퀀스
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # 1. 실행 중인 작업 취소
    from .api.runs import active_runs
    for run_id, task in active_runs.items():
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    # 2. 이벤트 저장소 정리 작업 중지
    await event_store.stop_cleanup_task()

    # 3. 데이터베이스 연결 종료
    await db_manager.close()
    # - SQLAlchemy 엔진 dispose
    # - LangGraph checkpointer/store 종료

    print("✅ Application shutdown complete")

# FastAPI 앱 생성
app = FastAPI(lifespan=lifespan)
```

### 백그라운드 작업 관리

**활성 실행 추적**:

```python
# api/runs.py
active_runs: dict[str, asyncio.Task] = {}

async def create_run_background(run_create: RunCreate):
    """백그라운드 실행 생성"""

    # 1. Run ORM 생성 (DB 저장)
    run = Run(...)

    # 2. 백그라운드 작업 생성
    task = asyncio.create_task(
        execute_run_async(run, input_data, stream_modes, user)
    )

    # 3. 활성 실행 레지스트리에 등록
    active_runs[run.run_id] = task

    # 4. 완료 콜백 등록 (자동 정리)
    task.add_done_callback(
        lambda _: active_runs.pop(run.run_id, None)
    )

    return run
```

**실행 취소**:

```python
@router.post("/threads/{thread_id}/runs/{run_id}/cancel")
async def cancel_run(thread_id: str, run_id: str):
    """실행 취소"""

    # 1. 활성 작업 확인
    task = active_runs.get(run_id)

    if task and not task.done():
        # 2. 작업 취소
        task.cancel()

        # 3. DB 상태 업데이트
        await update_run_status(run_id, "cancelled")

        # 4. 브로커에 취소 시그널
        await streaming_service.signal_run_cancelled(run_id)

    return {"status": "cancelled"}
```

### 정리 작업 (Cleanup Tasks)

**이벤트 자동 정리**:

```python
# services/event_store.py
class EventStore:
    CLEANUP_INTERVAL = 300  # 5분

    async def _cleanup_loop(self):
        """백그라운드 정리 루프"""
        while True:
            try:
                await asyncio.sleep(self.CLEANUP_INTERVAL)

                # 1시간 이상 된 이벤트 삭제
                engine = db_manager.get_engine()
                async with engine.begin() as conn:
                    await conn.execute(
                        text("""
                            DELETE FROM run_events
                            WHERE created_at < NOW() - INTERVAL '1 hour'
                        """)
                    )

                logger.info("Event cleanup completed")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
```

**브로커 자동 정리**:

```python
# services/broker.py
class BrokerManager:
    async def cleanup_finished_brokers(self):
        """완료된 브로커 정리 (메모리 누수 방지)"""

        # 15분 이상 된 완료 브로커 삭제
        cutoff_time = asyncio.get_event_loop().time() - 900

        to_remove = [
            run_id
            for run_id, broker in self._brokers.items()
            if broker.finished.is_set() and broker._created_at < cutoff_time
        ]

        for run_id in to_remove:
            del self._brokers[run_id]

        logger.info(f"Removed {len(to_remove)} finished brokers")
```

---

## 요약

### 핵심 아키텍처 특징

1. **레이어드 아키텍처**: API → Service → Core → LangGraph
2. **데이터베이스 이중화**: SQLAlchemy (메타데이터) + LangGraph (상태)
3. **싱글톤 패턴**: 전역 리소스 공유 및 일관성 보장
4. **Producer-Consumer**: 백그라운드 실행 + SSE 스트리밍
5. **LangGraph SDK Auth**: 인증 및 멀티테넌트 격리

### 주요 데이터 흐름

```
요청 → 인증 → 실행 생성 → 백그라운드 처리
                            ↓
                    LangGraph 실행
                            ↓
                    이벤트 생성 → 브로커 → SSE 스트리밍
                            ↓
                    체크포인트 저장
                            ↓
                    이벤트 영속화 (재연결용)
```

### 확장 포인트

- **커스텀 인증**: `auth.py`에서 `@auth.authenticate` 구현
- **새 그래프 추가**: `graphs/` 디렉토리에 추가 후 `open_langgraph.json`에 등록
- **관찰성 통합**: `observability/` 디렉토리에 콜백 추가
- **이벤트 변환**: `services/event_converter.py`에서 변환 로직 확장

---

이 문서는 Open LangGraph의 아키텍처를 이해하고 효과적으로 개발/확장하는 데 필요한 모든 정보를 담고 있습니다.
