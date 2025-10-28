# Services Layer - 서비스 계층 아키텍처

## 폴더 개요

`services/` 디렉토리는 Open LangGraph의 **비즈니스 로직 계층**으로, FastAPI 라우터와 데이터베이스 사이의 중간 계층 역할을 합니다. 이 계층은 다음과 같은 책임을 가집니다:

- **비즈니스 로직 캡슐화**: API 엔드포인트에서 복잡한 로직을 분리하여 유지보수성 향상
- **LangGraph 통합**: LangGraph 그래프 로딩, 실행, 상태 관리
- **실시간 스트리밍**: SSE(Server-Sent Events) 기반 이벤트 스트리밍
- **이벤트 영속화**: PostgreSQL 기반 이벤트 저장 및 재생
- **프로듀서-컨슈머 패턴**: 비동기 이벤트 분배 및 브로드캐스팅

이 계층은 **관심사 분리**(Separation of Concerns) 원칙을 따르며, 각 서비스는 단일 책임을 가집니다.

---

## 파일 목록 및 설명

### 1. `langgraph_service.py` - LangGraph 통합 서비스

**역할**: 그래프 로딩, 설정 관리, 실행 설정 생성

```python
from services.langgraph_service import get_langgraph_service

service = get_langgraph_service()
await service.initialize()
graph = await service.get_graph("weather_agent")
```

**주요 기능**:
- **그래프 레지스트리 관리**: `open_langgraph.json`에서 그래프 정의 로드
- **동적 그래프 로딩**: Python 파일에서 그래프 모듈 동적 import
- **그래프 컴파일**: Postgres 체크포인터와 함께 자동 컴파일
- **캐싱**: 로드된 그래프를 메모리에 캐시하여 성능 향상
- **기본 어시스턴트 생성**: Deterministic UUID로 각 그래프마다 기본 어시스턴트 생성

**핵심 클래스**:
- `LangGraphService`: 그래프 로딩 및 설정 관리
- `inject_user_context()`: 사용자 컨텍스트를 LangGraph config에 주입
- `create_thread_config()`: 스레드별 실행 설정 생성
- `create_run_config()`: 실행별 설정 생성 (관찰성 콜백 포함)

**아키텍처 패턴**:
- **싱글톤**: 애플리케이션 전체에서 단일 인스턴스 사용
- **지연 로딩**: 그래프를 필요할 때만 로드 및 컴파일
- **설정 주입**: 사용자 컨텍스트 및 추적 콜백 자동 주입

---

### 2. `streaming_service.py` - SSE 스트리밍 오케스트레이션

**역할**: LangGraph 이벤트를 SSE로 스트리밍하고 PostgreSQL에 영속화

```python
from services.streaming_service import streaming_service

# 실행 스트리밍 (재연결 지원)
async for sse_event in streaming_service.stream_run_execution(
    run, last_event_id="run_123_event_42"
):
    yield sse_event

# 실행 취소
await streaming_service.signal_run_cancelled(run_id)
```

**주요 기능**:
- **실시간 이벤트 스트리밍**: 브로커를 통한 프로듀서-컨슈머 패턴
- **이벤트 영속화**: PostgreSQL 기반 이벤트 저장소 활용
- **재연결 지원**: `last_event_id` 기반 이벤트 재생
- **이벤트 변환**: LangGraph 형식 → Agent Protocol SSE 형식
- **실행 제어**: 취소, 인터럽트, 에러 시그널링

**핵심 클래스**:
- `StreamingService`: SSE 스트리밍 총괄 서비스
- `put_to_broker()`: 브로커에 이벤트 전달 (Producer)
- `store_event_from_raw()`: 이벤트를 PostgreSQL에 저장
- `stream_run_execution()`: 클라이언트에게 SSE 스트리밍 (Consumer)

**아키텍처**:
```
Producer (execute_run_async) → [Broker + EventStore] → Consumer (stream_run_execution) → SSE Client
```

---

### 3. `event_store.py` - PostgreSQL 기반 이벤트 저장소

**역할**: SSE 이벤트를 PostgreSQL에 저장하여 재생 기능 제공

```python
from services.event_store import event_store, store_sse_event

# 이벤트 저장
await store_sse_event(run_id, event_id, "values", {"key": "value"})

# 특정 시점 이후 이벤트 조회 (재연결 시)
events = await event_store.get_events_since(run_id, last_event_id)

# 정리 작업 시작/중지
await event_store.start_cleanup_task()
await event_store.stop_cleanup_task()
```

**주요 기능**:
- **이벤트 저장**: SSE 이벤트를 시퀀스 번호와 함께 저장
- **이벤트 재생**: 특정 시점 이후 이벤트 조회 (재연결 지원)
- **자동 정리**: 1시간 이상 된 이벤트를 300초마다 자동 삭제
- **실행 정보**: 이벤트 카운트, 마지막 이벤트 조회

**데이터베이스 스키마**:
```sql
CREATE TABLE run_events (
    id TEXT PRIMARY KEY,           -- 이벤트 ID
    run_id TEXT NOT NULL,          -- 실행 ID
    seq INTEGER NOT NULL,          -- 시퀀스 번호
    event TEXT NOT NULL,           -- 이벤트 타입
    data JSONB NOT NULL,           -- 페이로드
    created_at TIMESTAMP NOT NULL
);
CREATE INDEX idx_run_events_run_id ON run_events(run_id);
CREATE INDEX idx_run_events_run_id_seq ON run_events(run_id, seq);
```

**정리 정책**:
- 정리 주기: 300초 (5분)
- 보존 기간: 1시간
- 백그라운드 작업: asyncio.Task로 실행

---

### 4. `event_converter.py` - 이벤트 형식 변환기

**역할**: LangGraph 이벤트를 SSE 형식으로 변환

```python
from services.event_converter import EventConverter

converter = EventConverter()

# 실시간 이벤트 변환
sse_event = converter.convert_raw_to_sse(event_id, raw_event)

# 저장된 이벤트 변환 (재생)
sse_event = converter.convert_stored_to_sse(stored_event, run_id)
```

**주요 기능**:
- **실시간 이벤트 변환**: LangGraph `astream()`에서 나오는 이벤트 처리
- **저장된 이벤트 변환**: PostgreSQL에 저장된 이벤트 재생
- **스트림 모드 감지**: 이벤트 타입 자동 인식 및 SSE 형식 적용
- **Interrupt 처리**: `__interrupt__` 업데이트를 `values` 이벤트로 변환

**지원하는 이벤트 타입**:
- `messages`: 메시지 청크 (스트리밍 응답)
- `values`: 상태 값
- `updates`: 상태 업데이트
- `state`: 전체 상태
- `logs`: 로그 메시지
- `tasks`: 실행 작업
- `subgraphs`: 서브그래프 정보
- `debug`: 디버그 정보
- `events`: 커스텀 이벤트
- `checkpoints`: 체크포인트
- `custom`: 사용자 정의 이벤트
- `end`: 스트림 종료
- `error`: 오류 정보

**SSE 형식 예시**:
```
event: messages
data: {"chunk": "Hello", "metadata": {...}}
id: 1

```

---

### 5. `broker.py` - 메시지 브로커 (Producer-Consumer 패턴)

**역할**: 실행별 이벤트 큐 관리 및 다중 클라이언트 분배

```python
from services.broker import broker_manager

# Producer: 이벤트 전송
broker = broker_manager.get_or_create_broker(run_id)
await broker.put(event_id, payload)

# Consumer: 이벤트 수신
async for event_id, payload in broker.aiter():
    print(f"Received: {event_id}")
```

**주요 기능**:
- **asyncio.Queue 기반**: 비동기 이벤트 큐잉
- **여러 Consumer 지원**: 브로드캐스트 패턴 (현재는 단일 Consumer)
- **실행 완료 감지**: 자동 정리 및 종료 시그널
- **브로커 생명주기 관리**: 생성, 완료, 정리

**핵심 클래스**:
- `RunBroker`: 단일 실행의 이벤트 큐 및 분배 관리
- `BrokerManager`: 여러 RunBroker 인스턴스 생명주기 관리
- `broker_manager`: 전역 싱글톤 인스턴스

**정리 정책**:
- 정리 주기: 300초 (5분)
- 정리 조건: 완료됨 + 큐 비어있음 + 1시간 이상 경과

**아키텍처**:
```
Producer → [RunBroker Queue] → Consumer 1
                             → Consumer 2 (future)
                             → Consumer N (future)
```

---

### 6. `assistant_service.py` - 어시스턴트 비즈니스 로직

**역할**: 어시스턴트 CRUD 및 버전 관리

```python
from services.assistant_service import get_assistant_service

service = get_assistant_service()

# 어시스턴트 생성
assistant = await service.create_assistant(request, user.identity)

# 어시스턴트 조회
assistant = await service.get_assistant(assistant_id, user.identity)

# 그래프 스키마 조회
schemas = await service.get_assistant_schemas(assistant_id, user.identity)
```

**주요 기능**:
- **어시스턴트 생성**: 그래프 검증, 중복 검사, 버전 이력 생성
- **버전 관리**: 업데이트 시 이전 버전 보존, 롤백 지원
- **그래프 스키마 조회**: 입력/출력/상태 스키마 추출
- **검색 및 페이지네이션**: 필터링 및 페이지네이션
- **멀티테넌트 격리**: `user_id` 기반 데이터 격리

**핵심 클래스**:
- `AssistantService`: 어시스턴트 CRUD 및 버전 관리
- `to_pydantic()`: SQLAlchemy ORM → Pydantic 모델 변환
- `_extract_graph_schemas()`: LangGraph 스키마 추출

**버전 관리 흐름**:
1. 어시스턴트 업데이트 요청
2. 현재 버전을 `assistant_versions` 테이블에 저장
3. 버전 번호 증가 (max_version + 1)
4. 어시스턴트 메인 레코드 업데이트
5. 롤백 시 특정 버전으로 복원 가능

---

### 7. `thread_state_service.py` - 스레드 상태 변환

**역할**: LangGraph 스냅샷을 ThreadState 형식으로 변환

```python
from services.thread_state_service import ThreadStateService

service = ThreadStateService()
thread_state = service.convert_snapshot_to_thread_state(snapshot, thread_id)
```

**주요 기능**:
- **단일/다중 스냅샷 변환**: LangGraph 스냅샷 → Agent Protocol ThreadState
- **체크포인트 메타데이터 추출**: 현재/부모 체크포인트 정보
- **태스크 및 인터럽트 직렬화**: LangGraphSerializer 활용
- **타임스탬프 파싱**: ISO 8601 형식 지원

**핵심 클래스**:
- `ThreadStateService`: 스냅샷 → ThreadState 변환 서비스
- `LangGraphSerializer`: 태스크 및 인터럽트 직렬화

**변환 과정**:
1. 기본 값 추출: `values`, `next`, `metadata`, `created_at`
2. 태스크/인터럽트: `serializer`로 직렬화
3. 체크포인트 객체 생성: `current`, `parent`
4. 하위 호환성: `checkpoint_id` 추출

---

## 서비스 간 관계 및 의존성

### 의존성 그래프

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Router Layer                    │
│            (api/runs.py, api/assistants.py, etc.)           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Service Layer                          │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────────┐    ┌──────────────────┐                │
│  │ LangGraph      │◄───│ Assistant        │                │
│  │ Service        │    │ Service          │                │
│  └────────────────┘    └──────────────────┘                │
│         │                                                    │
│         ▼                                                    │
│  ┌────────────────┐    ┌──────────────────┐                │
│  │ Streaming      │◄───│ Thread State     │                │
│  │ Service        │    │ Service          │                │
│  └────────────────┘    └──────────────────┘                │
│         │                                                    │
│         ├──────────┬──────────┐                            │
│         ▼          ▼          ▼                            │
│  ┌──────────┐ ┌────────┐ ┌─────────────┐                  │
│  │ Broker   │ │ Event  │ │ Event       │                  │
│  │ Manager  │ │ Store  │ │ Converter   │                  │
│  └──────────┘ └────────┘ └─────────────┘                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Database Layer                           │
│         (SQLAlchemy ORM, LangGraph Checkpointer)           │
└─────────────────────────────────────────────────────────────┘
```

### 서비스 간 상호작용

#### 1. 실행(Run) 생성 및 스트리밍 플로우

```
1. Client → POST /runs
2. API Router → LangGraphService.get_graph()
3. API Router → create_run_config() (사용자 컨텍스트 주입)
4. API Router → graph.ainvoke() or graph.astream()
5. execute_run_async() → StreamingService.put_to_broker() (Producer)
6. execute_run_async() → StreamingService.store_event_from_raw()
7. Client → GET /runs/{run_id}/stream
8. API Router → StreamingService.stream_run_execution() (Consumer)
9. StreamingService → EventStore.get_events_since() (재연결 시)
10. StreamingService → Broker.aiter() (라이브 이벤트)
11. StreamingService → EventConverter.convert_raw_to_sse()
12. API Router → SSE Client
```

#### 2. 어시스턴트 생성 플로우

```
1. Client → POST /assistants
2. API Router → AssistantService.create_assistant()
3. AssistantService → LangGraphService.list_graphs() (그래프 검증)
4. AssistantService → LangGraphService.get_graph() (로드 가능 여부 확인)
5. AssistantService → SQLAlchemy (어시스턴트 레코드 생성)
6. AssistantService → SQLAlchemy (버전 이력 레코드 생성)
7. API Router → Client
```

#### 3. 스레드 상태 조회 플로우

```
1. Client → GET /threads/{thread_id}/state
2. API Router → DatabaseManager.get_checkpointer()
3. API Router → checkpointer.aget_tuple() (LangGraph 스냅샷 조회)
4. API Router → ThreadStateService.convert_snapshot_to_thread_state()
5. ThreadStateService → LangGraphSerializer.extract_tasks_from_snapshot()
6. ThreadStateService → LangGraphSerializer.extract_interrupts_from_snapshot()
7. API Router → Client
```

---

## 주요 패턴

### 1. Producer-Consumer 패턴

**사용 위치**: `streaming_service.py`, `broker.py`

**구조**:
```python
# Producer (execute_run_async)
async for event_id, raw_event in graph.astream():
    await streaming_service.put_to_broker(run_id, event_id, raw_event)
    await streaming_service.store_event_from_raw(run_id, event_id, raw_event)

# Consumer (stream_run_execution)
broker = broker_manager.get_or_create_broker(run_id)
async for event_id, raw_event in broker.aiter():
    sse_event = await event_converter.convert_raw_to_sse(event_id, raw_event)
    yield sse_event
```

**장점**:
- 비동기 이벤트 분배
- 다중 클라이언트 지원 (향후 확장 가능)
- 실행 엔진과 스트리밍 계층 분리

---

### 2. Event-Driven 아키텍처

**사용 위치**: `event_store.py`, `event_converter.py`

**이벤트 흐름**:
```
LangGraph Event → Raw Event → Broker Queue → SSE Event → Client
                            ↓
                    PostgreSQL (영속화)
                            ↓
                    재연결 시 재생
```

**이벤트 타입 변환**:
```python
# LangGraph 이벤트 (tuple 형식)
("messages", message_chunk)
("values", state_values)
("end", {"status": "completed"})

# SSE 이벤트 (문자열 형식)
"""
event: messages
data: {"chunk": "Hello"}
id: 1

"""
```

---

### 3. 싱글톤 패턴

**사용 위치**: 모든 서비스

```python
# langgraph_service.py
_langgraph_service = None

def get_langgraph_service() -> LangGraphService:
    global _langgraph_service
    if _langgraph_service is None:
        _langgraph_service = LangGraphService()
    return _langgraph_service

# streaming_service.py
streaming_service = StreamingService()

# event_store.py
event_store = EventStore()

# broker.py
broker_manager = BrokerManager()
```

**장점**:
- 애플리케이션 전체에서 동일한 인스턴스 공유
- 상태 및 캐시 공유 (그래프 캐시, 브로커 등)
- 메모리 효율성

---

### 4. Dependency Injection 패턴

**사용 위치**: `assistant_service.py`

```python
from fastapi import Depends

def get_assistant_service(
    session: AsyncSession = Depends(get_session),
    langgraph_service: LangGraphService = Depends(get_langgraph_service),
) -> AssistantService:
    return AssistantService(session, langgraph_service)

# API Router에서 사용
@router.post("/assistants")
async def create_assistant(
    request: AssistantCreate,
    service: AssistantService = Depends(get_assistant_service),
    user = Depends(get_current_user),
):
    return await service.create_assistant(request, user.identity)
```

**장점**:
- 테스트 가능성 향상 (모킹 용이)
- 의존성 자동 주입
- 코드 간결성

---

## 사용 예제

### 예제 1: 그래프 로딩 및 실행

```python
from services.langgraph_service import get_langgraph_service, create_run_config

# 1. 서비스 초기화
service = get_langgraph_service()
await service.initialize()

# 2. 그래프 로드
graph = await service.get_graph("weather_agent")

# 3. 실행 설정 생성 (사용자 컨텍스트 + 추적 콜백)
config = create_run_config(
    run_id="run_123",
    thread_id="thread_456",
    user=user,
    additional_config={"configurable": {"model": "gpt-4"}}
)

# 4. 그래프 실행
async for event in graph.astream(input_data, config):
    print(event)
```

---

### 예제 2: SSE 스트리밍 (재연결 지원)

```python
from services.streaming_service import streaming_service

# 1. 실행 생성
run = await create_run(...)

# 2. SSE 스트리밍 시작
async def stream_events():
    async for sse_event in streaming_service.stream_run_execution(
        run=run,
        last_event_id="run_123_event_42",  # 재연결 시 제공
        cancel_on_disconnect=True
    ):
        yield sse_event

# 3. FastAPI StreamingResponse로 전달
return StreamingResponse(stream_events(), media_type="text/event-stream")
```

**재연결 시나리오**:
1. 클라이언트가 이벤트 42까지 수신 후 연결 끊김
2. 재연결 시 `Last-Event-ID: run_123_event_42` 헤더 전송
3. 서버는 PostgreSQL에서 42 이후 이벤트 재생
4. 재생 완료 후 라이브 이벤트 계속 스트리밍

---

### 예제 3: 이벤트 저장 및 재생

```python
from services.event_store import event_store, store_sse_event

# Producer: 이벤트 저장
await store_sse_event(
    run_id="run_123",
    event_id="run_123_event_1",
    event_type="values",
    data={"message": "Hello"}
)

# Consumer: 재연결 시 이벤트 재생
stored_events = await event_store.get_events_since(
    run_id="run_123",
    last_event_id="run_123_event_42"
)

for event in stored_events:
    print(f"Event {event.id}: {event.data}")
```

---

### 예제 4: 어시스턴트 생성 및 버전 관리

```python
from services.assistant_service import get_assistant_service

service = get_assistant_service()

# 1. 어시스턴트 생성
assistant = await service.create_assistant(
    request=AssistantCreate(
        graph_id="weather_agent",
        name="Weather Bot",
        config={"configurable": {"model": "gpt-4"}},
        metadata={"team": "support"}
    ),
    user_identity=user.identity
)

# 2. 어시스턴트 업데이트 (버전 2 생성)
updated = await service.update_assistant(
    assistant_id=assistant.assistant_id,
    request=AssistantUpdate(
        config={"configurable": {"model": "gpt-4-turbo"}}
    ),
    user_identity=user.identity
)

# 3. 버전 이력 조회
versions = await service.list_assistant_versions(
    assistant_id=assistant.assistant_id,
    user_identity=user.identity
)
# [버전 2 (최신), 버전 1 (이전)]

# 4. 버전 1로 롤백
reverted = await service.set_assistant_latest(
    assistant_id=assistant.assistant_id,
    version=1,
    user_identity=user.identity
)
```

---

### 예제 5: 스레드 상태 조회

```python
from services.thread_state_service import ThreadStateService
from core.database import db_manager

service = ThreadStateService()

# 1. 체크포인터에서 스냅샷 조회
checkpointer = await db_manager.get_checkpointer()
config = create_thread_config(thread_id, user)
snapshot = await checkpointer.aget_tuple(config)

# 2. 스냅샷 → ThreadState 변환
thread_state = service.convert_snapshot_to_thread_state(
    snapshot=snapshot,
    thread_id=thread_id
)

# 3. 체크포인트 히스토리 조회
snapshots = [s async for s in checkpointer.alist(config)]
history = service.convert_snapshots_to_thread_states(
    snapshots=snapshots,
    thread_id=thread_id
)
```

---

## 데이터 흐름

### 실행(Run) 생성부터 SSE 스트리밍까지

```
┌──────────┐
│  Client  │
└────┬─────┘
     │ POST /runs
     ▼
┌──────────────────────────────────────────────────────────┐
│                    API Router Layer                      │
│  1. get_graph(graph_id)                                 │
│  2. create_run_config(run_id, thread_id, user)          │
│  3. create_task(execute_run_async(graph, config))       │
└────┬─────────────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────────────────┐
│              execute_run_async (Producer)                │
│  async for event in graph.astream(input, config):       │
│    1. put_to_broker(run_id, event_id, raw_event)        │
│    2. store_event_from_raw(run_id, event_id, raw_event) │
└────┬─────────────────────────────────────────────────────┘
     │
     ├────────────────────┬────────────────────┐
     ▼                    ▼                    ▼
┌──────────┐      ┌──────────────┐    ┌───────────────┐
│ Broker   │      │ Event Store  │    │ Event         │
│ Queue    │      │ (PostgreSQL) │    │ Converter     │
│ (Memory) │      └──────────────┘    └───────────────┘
└────┬─────┘
     │
     ▼
┌──────────────────────────────────────────────────────────┐
│         stream_run_execution (Consumer)                  │
│  1. 재생: get_events_since(run_id, last_event_id)       │
│  2. 라이브: broker.aiter()                               │
│  3. 변환: event_converter.convert_raw_to_sse()          │
└────┬─────────────────────────────────────────────────────┘
     │
     ▼
┌──────────┐
│  Client  │ ← SSE Stream
└──────────┘
```

### 재연결 시 이벤트 재생 흐름

```
Client (재연결)
    │ GET /runs/{run_id}/stream
    │ Header: Last-Event-ID: run_123_event_42
    ▼
StreamingService.stream_run_execution()
    │
    ├─► EventStore.get_events_since(run_id, "run_123_event_42")
    │       │
    │       ▼ SELECT * FROM run_events WHERE run_id='run_123' AND seq > 42
    │       │
    │       ▼ [Event 43, Event 44, ..., Event 50]
    │       │
    │   ┌───┴───┐
    │   │ 재생   │ (저장된 이벤트)
    │   └───┬───┘
    │       │
    │       ▼ EventConverter.convert_stored_to_sse()
    │       │
    │       ▼ SSE Event 43, 44, ..., 50
    │
    └─► Broker.aiter()
            │
            ▼ [Event 51, Event 52, ...] (라이브)
            │
            ▼ EventConverter.convert_raw_to_sse()
            │
            ▼ SSE Event 51, 52, ...
```

---

## 정리

서비스 계층은 Open LangGraph의 **핵심 비즈니스 로직**을 담당하며, 다음과 같은 설계 원칙을 따릅니다:

1. **관심사 분리**: 각 서비스는 단일 책임을 가짐
2. **재사용성**: 여러 API 엔드포인트에서 공통 로직 공유
3. **테스트 가능성**: 의존성 주입으로 단위 테스트 용이
4. **확장성**: 프로듀서-컨슈머 패턴으로 다중 클라이언트 지원
5. **안정성**: 이벤트 영속화 및 재생으로 재연결 지원

이 계층은 **FastAPI 라우터**와 **데이터베이스/LangGraph** 사이의 중간 계층으로, 코드 유지보수성과 확장성을 크게 향상시킵니다.
