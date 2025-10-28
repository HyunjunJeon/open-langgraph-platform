# 미구현 API 개발 계획

**작성일:** 2025-10-28
**SDK 버전:** langgraph-sdk 0.2.9
**현재 API 준수율:** 83.8% (31/37 메서드)

## 개요

이 문서는 LangGraph SDK 0.2.9 기준으로 아직 구현되지 않은 API 엔드포인트들의 개발 계획을 상세히 기술합니다. 각 API는 SDK 메서드 시그니처 분석, 현재 구현 패턴 검토, 구현 전략 제시 순으로 정리되어 있습니다.

## 목표 준수율

- **목표:** 95% 이상 (36/37 메서드)
- **제외 항목:** `threads.copy` (낮은 우선순위)

## 미구현 항목 요약

### 우선순위별 분류

**높은 우선순위 (Phase 1)**
- CronsClient 전체 (5개 메서드) - SDK 0.2.9 신규 추가
- `threads.update` - 메타데이터 업데이트 필수 기능
- `store.list_namespaces` - 스토어 탐색 기능

**중간 우선순위 (Phase 2)**
- `threads.count` - 통계/대시보드용
- `runs.create_batch` - 고성능 배치 처리

**낮은 우선순위 (Phase 3)**
- `threads.join_stream` - runs 스트리밍으로 대체 가능
- `threads.copy` - 편의 기능, 필수 아님

---

## Phase 1: 핵심 기능 구현

### 1. CronsClient - 스케줄링 API

#### 1.1 crons.count

**SDK 시그니처**
```python
count(
    *,
    assistant_id: str | None = None,
    thread_id: str | None = None,
    headers: Mapping[str, str] | None = None,
    params: QueryParamTypes | None = None
) -> int
```

**HTTP 스펙**
- **메서드:** `POST`
- **경로:** `/crons/count`
- **요청 본문:**
  ```json
  {
    "assistant_id": "string (optional)",
    "thread_id": "string (optional)"
  }
  ```
- **응답:**
  ```json
  {
    "count": 0
  }
  ```

**구현 전략**

1. **모델 정의** (`src/agent_server/models/crons.py` 생성)
   ```python
   class CronCountRequest(BaseModel):
       assistant_id: str | None = None
       thread_id: str | None = None

   class CronCountResponse(BaseModel):
       count: int
   ```

2. **ORM 모델 정의** (`src/agent_server/core/orm.py` 추가)
   ```python
   class Cron(Base):
       __tablename__ = "crons"

       cron_id: Mapped[str] = mapped_column(String, primary_key=True)
       assistant_id: Mapped[str] = mapped_column(String, index=True)
       thread_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
       user_id: Mapped[str] = mapped_column(String, index=True)
       schedule: Mapped[str] = mapped_column(String)  # cron 표현식
       payload: Mapped[dict] = mapped_column(JSONB)  # 실행 설정
       next_run_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
       end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
       created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(UTC))
       updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(UTC), onupdate=datetime.now(UTC))
   ```

3. **엔드포인트 구현** (`src/agent_server/api/crons.py` 생성)
   ```python
   @router.post("/crons/count", response_model=CronCountResponse)
   async def count_crons(
       request: CronCountRequest,
       user: User = Depends(get_current_user),
       session: AsyncSession = Depends(get_session),
   ) -> CronCountResponse:
       query = select(func.count(CronORM.cron_id)).where(CronORM.user_id == user.identity)

       if request.assistant_id:
           query = query.where(CronORM.assistant_id == request.assistant_id)
       if request.thread_id:
           query = query.where(CronORM.thread_id == request.thread_id)

       result = await session.execute(query)
       count = result.scalar() or 0

       return CronCountResponse(count=count)
   ```

4. **마이그레이션 생성**
   ```bash
   python3 scripts/migrate.py revision --autogenerate -m "add crons table"
   ```

#### 1.2 crons.create

**SDK 시그니처**
```python
create(
    assistant_id: str,
    *,
    schedule: str,
    input: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    config: Config | None = None,
    context: Context | None = None,
    checkpoint_during: bool | None = None,
    interrupt_before: All | list[str] | None = None,
    interrupt_after: All | list[str] | None = None,
    webhook: str | None = None,
    multitask_strategy: str | None = None,
    headers: Mapping[str, str] | None = None,
    params: QueryParamTypes | None = None
) -> Run
```

**HTTP 스펙**
- **메서드:** `POST`
- **경로:** `/crons`
- **요청 본문:**
  ```json
  {
    "assistant_id": "string (required)",
    "schedule": "0 9 * * *",
    "input": {},
    "metadata": {},
    "config": {},
    "context": {},
    "checkpoint_during": true,
    "interrupt_before": ["node1"],
    "interrupt_after": ["node2"],
    "webhook": "https://...",
    "multitask_strategy": "reject"
  }
  ```
- **응답:** `Run` 객체

**구현 전략**

1. **모델 정의**
   ```python
   class CronCreate(BaseModel):
       assistant_id: str
       schedule: str  # cron 표현식 (예: "0 9 * * *")
       input: dict[str, Any] | None = None
       metadata: dict[str, Any] | None = None
       config: dict[str, Any] | None = None
       context: dict[str, Any] | None = None
       checkpoint_during: bool | None = None
       interrupt_before: list[str] | None = None
       interrupt_after: list[str] | None = None
       webhook: str | None = None
       multitask_strategy: str | None = Field(None, pattern="^(reject|interrupt|rollback|enqueue)$")

   class Cron(BaseModel):
       cron_id: str
       assistant_id: str
       thread_id: str | None = None
       user_id: str
       schedule: str
       payload: dict[str, Any]
       next_run_date: datetime | None = None
       end_time: datetime | None = None
       created_at: datetime
       updated_at: datetime

       model_config = ConfigDict(from_attributes=True)
   ```

2. **스케줄 파싱 유틸리티** (`src/agent_server/utils/cron.py` 생성)
   ```python
   from croniter import croniter
   from datetime import datetime, UTC

   def parse_cron_schedule(schedule: str) -> datetime:
       """cron 표현식을 파싱하여 다음 실행 시간 반환"""
       if not croniter.is_valid(schedule):
           raise ValueError(f"Invalid cron expression: {schedule}")

       now = datetime.now(UTC)
       cron = croniter(schedule, now)
       return cron.get_next(datetime)

   def validate_cron_schedule(schedule: str) -> bool:
       """cron 표현식 유효성 검증"""
       return croniter.is_valid(schedule)
   ```

3. **엔드포인트 구현**
   ```python
   @router.post("/crons", response_model=Cron)
   async def create_cron(
       request: CronCreate,
       user: User = Depends(get_current_user),
       session: AsyncSession = Depends(get_session),
   ) -> Cron:
       # 1. cron 표현식 검증
       if not validate_cron_schedule(request.schedule):
           raise HTTPException(status_code=400, detail="Invalid cron schedule")

       # 2. assistant 존재 확인
       assistant_id = await resolve_assistant_id(session, request.assistant_id, user.identity)
       if not assistant_id:
           raise HTTPException(status_code=404, detail="Assistant not found")

       # 3. 다음 실행 시간 계산
       next_run = parse_cron_schedule(request.schedule)

       # 4. cron 작업 생성
       cron_id = str(uuid4())
       payload = {
           "input": request.input or {},
           "metadata": request.metadata or {},
           "config": request.config or {},
           "context": request.context or {},
           "checkpoint_during": request.checkpoint_during,
           "interrupt_before": request.interrupt_before,
           "interrupt_after": request.interrupt_after,
           "webhook": request.webhook,
           "multitask_strategy": request.multitask_strategy,
       }

       cron_orm = CronORM(
           cron_id=cron_id,
           assistant_id=assistant_id,
           user_id=user.identity,
           schedule=request.schedule,
           payload=payload,
           next_run_date=next_run,
       )

       session.add(cron_orm)
       await session.commit()
       await session.refresh(cron_orm)

       return Cron.model_validate(cron_orm)
   ```

4. **의존성 추가** (`pyproject.toml`)
   ```toml
   dependencies = [
       # ... 기존 의존성
       "croniter>=2.0.0",  # cron 표현식 파싱
   ]
   ```

#### 1.3 crons.create_for_thread

**SDK 시그니처**
```python
create_for_thread(
    thread_id: str,
    assistant_id: str,
    *,
    schedule: str,
    input: Mapping[str, Any] | None = None,
    # ... (create와 동일한 매개변수)
) -> Run
```

**HTTP 스펙**
- **메서드:** `POST`
- **경로:** `/threads/{thread_id}/crons`
- **요청 본문:** `crons.create`와 동일 (assistant_id 제외)
- **응답:** `Run` 객체

**구현 전략**

1. **모델 재사용**
   - `CronCreate` 모델 그대로 사용 (thread_id는 경로에서 추출)

2. **엔드포인트 구현**
   ```python
   @router.post("/threads/{thread_id}/crons", response_model=Cron)
   async def create_cron_for_thread(
       thread_id: str,
       request: CronCreate,
       user: User = Depends(get_current_user),
       session: AsyncSession = Depends(get_session),
   ) -> Cron:
       # 1. 스레드 존재 및 소유권 확인
       thread = await session.get(ThreadORM, thread_id)
       if not thread or thread.user_id != user.identity:
           raise HTTPException(status_code=404, detail="Thread not found")

       # 2. cron 생성 (create_cron 로직 재사용, thread_id 추가)
       # ... (create_cron과 동일, 단 thread_id 설정)

       cron_orm = CronORM(
           cron_id=cron_id,
           assistant_id=assistant_id,
           thread_id=thread_id,  # 차이점: thread_id 설정
           user_id=user.identity,
           schedule=request.schedule,
           payload=payload,
           next_run_date=next_run,
       )

       # ... 저장 로직
   ```

#### 1.4 crons.delete

**SDK 시그니처**
```python
delete(
    cron_id: str,
    *,
    headers: Mapping[str, str] | None = None,
    params: QueryParamTypes | None = None
) -> None
```

**HTTP 스펙**
- **메서드:** `DELETE`
- **경로:** `/crons/{cron_id}`
- **응답:** 204 No Content

**구현 전략**

```python
@router.delete("/crons/{cron_id}", status_code=204)
async def delete_cron(
    cron_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    # 1. cron 조회 및 소유권 확인
    cron = await session.get(CronORM, cron_id)
    if not cron or cron.user_id != user.identity:
        raise HTTPException(status_code=404, detail="Cron not found")

    # 2. 삭제
    await session.delete(cron)
    await session.commit()
```

#### 1.5 crons.search

**SDK 시그니처**
```python
search(
    *,
    assistant_id: str | None = None,
    thread_id: str | None = None,
    limit: int = 10,
    offset: int = 0,
    sort_by: CronSortBy | None = None,
    sort_order: SortOrder | None = None,
    select: list[CronSelectField] | None = None,
    headers: Mapping[str, str] | None = None,
    params: QueryParamTypes | None = None
) -> list[Cron]
```

**HTTP 스펙**
- **메서드:** `POST`
- **경로:** `/crons/search`
- **요청 본문:**
  ```json
  {
    "assistant_id": "string (optional)",
    "thread_id": "string (optional)",
    "limit": 10,
    "offset": 0,
    "sort_by": "created_at",
    "sort_order": "desc"
  }
  ```
- **응답:**
  ```json
  {
    "crons": [...],
    "total": 0
  }
  ```

**구현 전략**

1. **모델 정의**
   ```python
   class CronSearchRequest(BaseModel):
       assistant_id: str | None = None
       thread_id: str | None = None
       limit: int = Field(10, ge=1, le=100)
       offset: int = Field(0, ge=0)
       sort_by: str | None = Field("created_at", pattern="^(created_at|updated_at|next_run_date)$")
       sort_order: str | None = Field("desc", pattern="^(asc|desc)$")

   class CronSearchResponse(BaseModel):
       crons: list[Cron]
       total: int
   ```

2. **엔드포인트 구현**
   ```python
   @router.post("/crons/search", response_model=CronSearchResponse)
   async def search_crons(
       request: CronSearchRequest,
       user: User = Depends(get_current_user),
       session: AsyncSession = Depends(get_session),
   ) -> CronSearchResponse:
       # 1. 기본 쿼리 (사용자 격리)
       query = select(CronORM).where(CronORM.user_id == user.identity)
       count_query = select(func.count(CronORM.cron_id)).where(CronORM.user_id == user.identity)

       # 2. 필터 적용
       if request.assistant_id:
           query = query.where(CronORM.assistant_id == request.assistant_id)
           count_query = count_query.where(CronORM.assistant_id == request.assistant_id)

       if request.thread_id:
           query = query.where(CronORM.thread_id == request.thread_id)
           count_query = count_query.where(CronORM.thread_id == request.thread_id)

       # 3. 정렬
       sort_column = getattr(CronORM, request.sort_by or "created_at")
       if request.sort_order == "asc":
           query = query.order_by(sort_column.asc())
       else:
           query = query.order_by(sort_column.desc())

       # 4. 페이지네이션
       query = query.limit(request.limit).offset(request.offset)

       # 5. 실행
       result = await session.execute(query)
       crons = result.scalars().all()

       count_result = await session.execute(count_query)
       total = count_result.scalar() or 0

       return CronSearchResponse(
           crons=[Cron.model_validate(c) for c in crons],
           total=total,
       )
   ```

#### 1.6 Cron 실행 스케줄러 (백그라운드 작업)

**참고:** Cron 작업은 데이터베이스에 저장만 하고, 실제 실행은 별도 스케줄러가 필요합니다.

**옵션 1: APScheduler 사용**
```python
# src/agent_server/services/cron_scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

class CronSchedulerService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    async def start(self):
        """스케줄러 시작 (앱 시작 시 호출)"""
        # 1. DB에서 모든 활성 cron 작업 로드
        # 2. 각 cron에 대해 스케줄러에 작업 등록
        self.scheduler.start()

    async def schedule_cron(self, cron: CronORM):
        """개별 cron 작업 스케줄 등록"""
        trigger = CronTrigger.from_crontab(cron.schedule)
        self.scheduler.add_job(
            self._execute_cron,
            trigger=trigger,
            args=[cron.cron_id],
            id=cron.cron_id,
        )

    async def _execute_cron(self, cron_id: str):
        """cron 작업 실행"""
        # 1. DB에서 cron 조회
        # 2. payload로 Run 생성
        # 3. 다음 실행 시간 업데이트
```

**옵션 2: Celery Beat 사용** (프로덕션 권장)
- 분산 환경에서 안정적
- Redis/RabbitMQ 필요

**권장 사항:** Phase 1에서는 DB 저장만 구현, 스케줄러는 Phase 2로 연기

---

### 2. threads.update - 스레드 메타데이터 업데이트

**SDK 시그니처**
```python
update(
    thread_id: str,
    *,
    metadata: Mapping[str, Any],
    ttl: int | Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    params: QueryParamTypes | None = None
) -> Thread
```

**HTTP 스펙**
- **메서드:** `PATCH`
- **경로:** `/threads/{thread_id}`
- **요청 본문:**
  ```json
  {
    "metadata": {"key": "value"},
    "ttl": 43200
  }
  ```
- **응답:** `Thread` 객체

**구현 전략**

1. **모델 정의** (`src/agent_server/models/threads.py` 추가)
   ```python
   class ThreadUpdate(BaseModel):
       metadata: dict[str, Any]
       ttl: int | dict[str, Any] | None = None

       @field_validator("ttl")
       def validate_ttl(cls, v):
           if isinstance(v, dict):
               if "ttl" not in v:
                   raise ValueError("ttl mapping must contain 'ttl' key")
               if "strategy" in v and v["strategy"] not in ["delete", "archive"]:
                   raise ValueError("ttl strategy must be 'delete' or 'archive'")
           return v
   ```

2. **ORM 확장** (`src/agent_server/core/orm.py` 수정)
   ```python
   class Thread(Base):
       # ... 기존 필드
       ttl_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
       ttl_strategy: Mapped[str | None] = mapped_column(String, nullable=True)
       expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
   ```

3. **엔드포인트 구현** (`src/agent_server/api/threads.py` 추가)
   ```python
   @router.patch("/threads/{thread_id}", response_model=Thread)
   async def update_thread(
       thread_id: str,
       request: ThreadUpdate,
       user: User = Depends(get_current_user),
       session: AsyncSession = Depends(get_session),
   ) -> Thread:
       # 1. 스레드 조회 및 소유권 확인
       thread = await session.get(ThreadORM, thread_id)
       if not thread or thread.user_id != user.identity:
           raise HTTPException(status_code=404, detail="Thread not found")

       # 2. 메타데이터 병합 (기존 메타데이터에 새 값 병합)
       if request.metadata:
           thread.metadata = {**thread.metadata, **request.metadata}

       # 3. TTL 설정
       if request.ttl is not None:
           if isinstance(request.ttl, int):
               thread.ttl_minutes = request.ttl
               thread.ttl_strategy = "delete"  # 기본 전략
               thread.expires_at = datetime.now(UTC) + timedelta(minutes=request.ttl)
           elif isinstance(request.ttl, dict):
               thread.ttl_minutes = request.ttl["ttl"]
               thread.ttl_strategy = request.ttl.get("strategy", "delete")
               thread.expires_at = datetime.now(UTC) + timedelta(minutes=request.ttl["ttl"])

       # 4. 저장
       await session.commit()
       await session.refresh(thread)

       return Thread.model_validate(thread)
   ```

4. **TTL 정리 백그라운드 작업** (`src/agent_server/services/ttl_cleaner.py` 생성)
   ```python
   import asyncio
   from datetime import datetime, UTC
   from sqlalchemy import select, delete

   class TTLCleanerService:
       def __init__(self):
           self.running = False

       async def start(self):
           """백그라운드 정리 작업 시작"""
           self.running = True
           asyncio.create_task(self._cleanup_loop())

       async def _cleanup_loop(self):
           """주기적으로 만료된 스레드 정리"""
           while self.running:
               await self._cleanup_expired_threads()
               await asyncio.sleep(3600)  # 1시간마다

       async def _cleanup_expired_threads(self):
           async with _get_session_maker()() as session:
               # 만료된 스레드 조회
               query = select(ThreadORM).where(
                   ThreadORM.expires_at < datetime.now(UTC)
               )
               result = await session.execute(query)
               expired_threads = result.scalars().all()

               for thread in expired_threads:
                   if thread.ttl_strategy == "delete":
                       await session.delete(thread)
                   elif thread.ttl_strategy == "archive":
                       # TODO: 아카이브 로직 (예: 다른 테이블로 이동)
                       pass

               await session.commit()
   ```

5. **앱 시작 시 정리 작업 등록** (`src/agent_server/main.py` 수정)
   ```python
   from .services.ttl_cleaner import TTLCleanerService

   ttl_cleaner = TTLCleanerService()

   @asynccontextmanager
   async def lifespan(app: FastAPI):
       # ... 기존 초기화
       await ttl_cleaner.start()
       yield
       # ... 기존 정리
       ttl_cleaner.running = False
   ```

6. **마이그레이션**
   ```bash
   python3 scripts/migrate.py revision --autogenerate -m "add ttl fields to threads"
   ```

---

### 3. store.list_namespaces - 네임스페이스 목록 조회

**SDK 시그니처**
```python
list_namespaces(
    prefix: list[str] | None = None,
    suffix: list[str] | None = None,
    max_depth: int | None = None,
    limit: int = 100,
    offset: int = 0,
    headers: Mapping[str, str] | None = None,
    params: QueryParamTypes | None = None
) -> ListNamespaceResponse
```

**HTTP 스펙**
- **메서드:** `GET`
- **경로:** `/store/namespaces`
- **쿼리 파라미터:**
  - `prefix`: 네임스페이스 접두사 (예: `["users", "user123"]`)
  - `suffix`: 네임스페이스 접미사
  - `max_depth`: 최대 깊이
  - `limit`: 최대 개수 (기본 100)
  - `offset`: 오프셋
- **응답:**
  ```json
  {
    "namespaces": [
      ["users", "user123", "settings"],
      ["users", "user123", "preferences"]
    ]
  }
  ```

**구현 전략**

1. **모델 정의** (`src/agent_server/models/store.py` 추가)
   ```python
   class ListNamespaceResponse(BaseModel):
       namespaces: list[list[str]]
   ```

2. **엔드포인트 구현** (`src/agent_server/api/store.py` 추가)
   ```python
   @router.get("/store/namespaces", response_model=ListNamespaceResponse)
   async def list_namespaces(
       prefix: list[str] | None = Query(None),
       suffix: list[str] | None = Query(None),
       max_depth: int | None = Query(None),
       limit: int = Query(100, ge=1, le=1000),
       offset: int = Query(0, ge=0),
       user: User = Depends(get_current_user),
   ) -> ListNamespaceResponse:
       # 1. LangGraph Store 인스턴스 획득
       from ..core.database import db_manager
       store = await db_manager.get_store()

       # 2. 사용자 네임스페이스 스코핑
       scoped_prefix = apply_user_namespace_scoping(user.identity, prefix or [])

       # 3. Store의 list_namespaces 호출
       # 주의: LangGraph Store에 list_namespaces 메서드가 있는지 확인 필요
       # 없다면 직접 SQL 쿼리로 구현

       # 옵션 1: LangGraph Store 메서드 사용 (있는 경우)
       namespaces = await store.list_namespaces(
           prefix=scoped_prefix,
           suffix=suffix,
           max_depth=max_depth,
           limit=limit,
           offset=offset,
       )

       # 옵션 2: 직접 SQL 쿼리 (LangGraph Store에 메서드 없는 경우)
       # PostgreSQL의 DISTINCT와 배열 연산 활용
       from sqlalchemy import text

       query = text("""
           SELECT DISTINCT namespace
           FROM store
           WHERE (:prefix IS NULL OR namespace @> :prefix::text[])
             AND (:suffix IS NULL OR namespace <@ :suffix::text[])
             AND (:max_depth IS NULL OR array_length(namespace, 1) <= :max_depth)
             AND namespace && :user_prefix::text[]
           ORDER BY namespace
           LIMIT :limit OFFSET :offset
       """)

       async with db_manager.get_engine().begin() as conn:
           result = await conn.execute(
               query,
               {
                   "prefix": scoped_prefix,
                   "suffix": suffix,
                   "max_depth": max_depth,
                   "user_prefix": [user.identity],
                   "limit": limit,
                   "offset": offset,
               }
           )
           namespaces = [row[0] for row in result]

       return ListNamespaceResponse(namespaces=namespaces)
   ```

3. **참고 사항**
   - LangGraph Store의 `list_namespaces` 메서드 지원 여부 확인 필요
   - 지원하지 않으면 PostgreSQL의 배열 연산자로 직접 구현
   - 사용자 네임스페이스 격리 필수

---

## Phase 2: 편의 기능 구현

### 4. threads.count - 스레드 개수 조회

**SDK 시그니처**
```python
count(
    *,
    metadata: Json = None,
    values: Json = None,
    status: ThreadStatus | None = None,
    headers: Mapping[str, str] | None = None,
    params: QueryParamTypes | None = None
) -> int
```

**HTTP 스펙**
- **메서드:** `POST`
- **경로:** `/threads/count`
- **요청 본문:**
  ```json
  {
    "metadata": {"key": "value"},
    "values": {},
    "status": "idle"
  }
  ```
- **응답:**
  ```json
  {
    "count": 0
  }
  ```

**구현 전략**

1. **모델 정의** (`src/agent_server/models/threads.py` 추가)
   ```python
   class ThreadCountRequest(BaseModel):
       metadata: dict[str, Any] | None = None
       values: dict[str, Any] | None = None
       status: str | None = None

   class ThreadCountResponse(BaseModel):
       count: int
   ```

2. **엔드포인트 구현** (`src/agent_server/api/threads.py` 추가)
   ```python
   @router.post("/threads/count", response_model=ThreadCountResponse)
   async def count_threads(
       request: ThreadCountRequest,
       user: User = Depends(get_current_user),
       session: AsyncSession = Depends(get_session),
   ) -> ThreadCountResponse:
       # 1. 기본 쿼리 (사용자 격리)
       query = select(func.count(ThreadORM.thread_id)).where(
           ThreadORM.user_id == user.identity
       )

       # 2. 메타데이터 필터
       if request.metadata:
           for key, value in request.metadata.items():
               query = query.where(
                   ThreadORM.metadata[key].astext == str(value)
               )

       # 3. 상태 필터
       if request.status:
           query = query.where(ThreadORM.status == request.status)

       # 4. values 필터 (LangGraph 체크포인트 조회 필요)
       # 주의: values는 LangGraph 체크포인트에 저장되므로 복잡함
       # 우선은 metadata와 status만 지원, values는 TODO

       # 5. 실행
       result = await session.execute(query)
       count = result.scalar() or 0

       return ThreadCountResponse(count=count)
   ```

3. **제한 사항**
   - `values` 필터는 LangGraph 체크포인트를 조회해야 하므로 성능 이슈 가능
   - Phase 2에서는 `metadata`와 `status`만 지원
   - `values` 지원은 추후 고려

---

### 5. runs.create_batch - 배치 실행 생성

**SDK 시그니처**
```python
create_batch(
    payloads: list[RunCreate],
    *,
    headers: Mapping[str, str] | None = None,
    params: QueryParamTypes | None = None
) -> list[Run]
```

**HTTP 스펙**
- **메서드:** `POST`
- **경로:** `/runs/batch`
- **요청 본문:**
  ```json
  {
    "payloads": [
      {
        "thread_id": "thread1",
        "assistant_id": "assistant1",
        "input": {}
      },
      {
        "thread_id": "thread2",
        "assistant_id": "assistant1",
        "input": {}
      }
    ]
  }
  ```
- **응답:** `list[Run]`

**구현 전략**

1. **모델 정의** (`src/agent_server/models/runs.py` 추가)
   ```python
   class RunBatchCreate(BaseModel):
       thread_id: str
       assistant_id: str
       input: dict[str, Any] | None = None
       metadata: dict[str, Any] | None = None
       config: dict[str, Any] | None = None
       # ... RunCreate의 모든 필드

   class RunBatchRequest(BaseModel):
       payloads: list[RunBatchCreate]

       @field_validator("payloads")
       def validate_payloads(cls, v):
           if len(v) > 100:
               raise ValueError("Maximum 100 runs per batch")
           return v
   ```

2. **엔드포인트 구현** (`src/agent_server/api/runs.py` 추가)
   ```python
   @router.post("/runs/batch", response_model=list[Run])
   async def create_batch_runs(
       request: RunBatchRequest,
       user: User = Depends(get_current_user),
       session: AsyncSession = Depends(get_session),
   ) -> list[Run]:
       runs = []

       # 배치 검증 및 생성
       for payload in request.payloads:
           # 1. 스레드 존재 및 소유권 확인
           thread = await session.get(ThreadORM, payload.thread_id)
           if not thread or thread.user_id != user.identity:
               raise HTTPException(
                   status_code=404,
                   detail=f"Thread {payload.thread_id} not found"
               )

           # 2. assistant 확인
           assistant_id = await resolve_assistant_id(
               session, payload.assistant_id, user.identity
           )
           if not assistant_id:
               raise HTTPException(
                   status_code=404,
                   detail=f"Assistant {payload.assistant_id} not found"
               )

           # 3. Run 생성 (DB 저장만, 실행은 백그라운드)
           run_id = str(uuid4())
           run_orm = RunORM(
               run_id=run_id,
               thread_id=payload.thread_id,
               assistant_id=assistant_id,
               status="pending",
               input=payload.input or {},
               metadata=payload.metadata or {},
               user_id=user.identity,
           )

           session.add(run_orm)
           runs.append(Run.model_validate(run_orm))

       # 4. 일괄 커밋
       await session.commit()

       # 5. 백그라운드 실행 시작
       for run in runs:
           asyncio.create_task(
               execute_run_background(run.run_id, run.thread_id, user)
           )

       return runs
   ```

3. **성능 최적화**
   - SQLAlchemy의 `bulk_insert_mappings` 사용 고려
   - 트랜잭션 단위로 일괄 커밋
   - 백그라운드 실행은 asyncio.gather로 병렬 처리

4. **제한 사항**
   - 배치 크기 제한: 최대 100개 (과부하 방지)
   - 스트리밍 지원 안 함 (배치는 백그라운드 전용)

---

## Phase 3: 낮은 우선순위

### 6. threads.join_stream - 스레드 스트리밍

**우선순위:** 낮음 (runs 스트리밍으로 대체 가능)

**SDK 시그니처**
```python
join_stream(
    thread_id: str,
    *,
    last_event_id: str | None = None,
    stream_mode: ThreadStreamMode | Sequence[ThreadStreamMode] = "run_modes",
    headers: Mapping[str, str] | None = None,
    params: QueryParamTypes | None = None
) -> AsyncIterator[StreamPart]
```

**구현 연기 사유:**
- 현재 `/threads/{thread_id}/runs/{run_id}/stream`로 충분히 커버 가능
- 스레드 레벨 스트리밍은 실제 사용 케이스가 적음
- 복잡도 대비 효용성 낮음

**추후 구현 시 전략:**
- 스레드의 모든 활성 Run을 집계하여 스트리밍
- event_store에서 thread_id로 필터링
- `last_event_id`로 재연결 지원

---

### 7. threads.copy - 스레드 복사

**우선순위:** 매우 낮음 (편의 기능)

**SDK 시그니처**
```python
copy(
    thread_id: str,
    *,
    headers: Mapping[str, str] | None = None,
    params: QueryParamTypes | None = None
) -> None
```

**구현 연기 사유:**
- 클라이언트에서 `create` + `update_state`로 구현 가능
- 사용 빈도 매우 낮음
- 서버 자원 소모 대비 효용성 낮음

**추후 구현 시 전략:**
1. 원본 스레드 메타데이터 복사
2. 최신 체크포인트 상태 로드
3. 새 스레드 생성 및 상태 복사
4. 체크포인트 히스토리는 복사하지 않음 (새 스레드는 새 히스토리 시작)

---

## 데이터베이스 마이그레이션 계획

### 새로운 테이블

#### 1. crons 테이블
```sql
CREATE TABLE crons (
    cron_id VARCHAR PRIMARY KEY,
    assistant_id VARCHAR NOT NULL,
    thread_id VARCHAR,
    user_id VARCHAR NOT NULL,
    schedule VARCHAR NOT NULL,
    payload JSONB NOT NULL,
    next_run_date TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    FOREIGN KEY (assistant_id) REFERENCES assistants(assistant_id) ON DELETE CASCADE,
    FOREIGN KEY (thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE
);

CREATE INDEX idx_crons_user_id ON crons(user_id);
CREATE INDEX idx_crons_assistant_id ON crons(assistant_id);
CREATE INDEX idx_crons_thread_id ON crons(thread_id);
CREATE INDEX idx_crons_next_run_date ON crons(next_run_date);
```

#### 2. threads 테이블 확장
```sql
ALTER TABLE threads
ADD COLUMN ttl_minutes INTEGER,
ADD COLUMN ttl_strategy VARCHAR,
ADD COLUMN expires_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX idx_threads_expires_at ON threads(expires_at)
WHERE expires_at IS NOT NULL;
```

### 마이그레이션 순서

1. **Phase 1-1: Crons 테이블 추가**
   ```bash
   python3 scripts/migrate.py revision --autogenerate -m "add crons table"
   python3 scripts/migrate.py upgrade
   ```

2. **Phase 1-2: Threads TTL 필드 추가**
   ```bash
   python3 scripts/migrate.py revision --autogenerate -m "add ttl fields to threads"
   python3 scripts/migrate.py upgrade
   ```

3. **Phase 2: 인덱스 최적화**
   - 쿼리 패턴 모니터링 후 추가 인덱스 생성

---

## 의존성 추가

### pyproject.toml 업데이트

```toml
dependencies = [
    # ... 기존 의존성
    "croniter>=2.0.0",        # cron 표현식 파싱 및 다음 실행 시간 계산
    "apscheduler>=3.10.0",    # 백그라운드 스케줄링 (옵션)
]
```

---

## 테스트 계획

### 단위 테스트

#### CronsClient 테스트 (`tests/test_api/test_crons.py`)
```python
import pytest
from datetime import datetime, UTC

@pytest.mark.asyncio
async def test_create_cron(client, auth_headers):
    """Cron 작업 생성 테스트"""
    response = await client.post(
        "/crons",
        json={
            "assistant_id": "test_assistant",
            "schedule": "0 9 * * *",
            "input": {"message": "Daily report"},
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["schedule"] == "0 9 * * *"
    assert data["next_run_date"] is not None

@pytest.mark.asyncio
async def test_invalid_cron_schedule(client, auth_headers):
    """잘못된 cron 표현식 테스트"""
    response = await client.post(
        "/crons",
        json={
            "assistant_id": "test_assistant",
            "schedule": "invalid cron",
            "input": {},
        },
        headers=auth_headers,
    )
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_search_crons(client, auth_headers):
    """Cron 검색 테스트"""
    # 1. Cron 생성
    await client.post(
        "/crons",
        json={"assistant_id": "test", "schedule": "0 9 * * *"},
        headers=auth_headers,
    )

    # 2. 검색
    response = await client.post(
        "/crons/search",
        json={"assistant_id": "test", "limit": 10},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["crons"]) >= 1
```

#### ThreadUpdate 테스트 (`tests/test_api/test_threads.py`)
```python
@pytest.mark.asyncio
async def test_update_thread_metadata(client, auth_headers):
    """스레드 메타데이터 업데이트 테스트"""
    # 1. 스레드 생성
    create_response = await client.post(
        "/threads",
        json={"metadata": {"version": 1}},
        headers=auth_headers,
    )
    thread_id = create_response.json()["thread_id"]

    # 2. 메타데이터 업데이트
    update_response = await client.patch(
        f"/threads/{thread_id}",
        json={"metadata": {"version": 2, "updated": True}},
        headers=auth_headers,
    )

    assert update_response.status_code == 200
    data = update_response.json()
    assert data["metadata"]["version"] == 2
    assert data["metadata"]["updated"] is True

@pytest.mark.asyncio
async def test_thread_ttl(client, auth_headers):
    """스레드 TTL 테스트"""
    create_response = await client.post(
        "/threads",
        json={"metadata": {}},
        headers=auth_headers,
    )
    thread_id = create_response.json()["thread_id"]

    # TTL 설정 (1440분 = 24시간)
    update_response = await client.patch(
        f"/threads/{thread_id}",
        json={
            "metadata": {},
            "ttl": {"ttl": 1440, "strategy": "delete"}
        },
        headers=auth_headers,
    )

    assert update_response.status_code == 200
    data = update_response.json()
    assert data["ttl_minutes"] == 1440
    assert data["expires_at"] is not None
```

### 통합 테스트

#### E2E Cron 워크플로우 테스트
```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_cron_workflow(client, auth_headers):
    """Cron 전체 워크플로우 테스트"""
    # 1. Cron 생성
    create_response = await client.post(
        "/crons",
        json={
            "assistant_id": "test_assistant",
            "schedule": "*/5 * * * *",  # 5분마다
            "input": {"test": True},
        },
        headers=auth_headers,
    )
    cron_id = create_response.json()["cron_id"]

    # 2. 검색으로 확인
    search_response = await client.post(
        "/crons/search",
        json={},
        headers=auth_headers,
    )
    assert search_response.json()["total"] >= 1

    # 3. 삭제
    delete_response = await client.delete(
        f"/crons/{cron_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204

    # 4. 삭제 확인
    search_response = await client.post(
        "/crons/search",
        json={},
        headers=auth_headers,
    )
    crons = [c for c in search_response.json()["crons"] if c["cron_id"] == cron_id]
    assert len(crons) == 0
```

---

## 구현 일정 (예상)

### Phase 1: 핵심 기능 (2-3주)

**Week 1: Crons 기본 CRUD**
- Day 1-2: ORM 모델 및 마이그레이션
- Day 3-4: create, create_for_thread 엔드포인트
- Day 5: count, search, delete 엔드포인트

**Week 2: Threads 업데이트 및 Store**
- Day 1-2: threads.update 구현 (메타데이터 + TTL)
- Day 3: TTL 정리 백그라운드 작업
- Day 4-5: store.list_namespaces 구현

**Week 3: 테스트 및 문서화**
- Day 1-3: 단위 테스트 작성
- Day 4: 통합 테스트
- Day 5: API 문서 업데이트

### Phase 2: 편의 기능 (1주)

**Week 4: Count 및 Batch**
- Day 1-2: threads.count 구현
- Day 3-4: runs.create_batch 구현
- Day 5: 테스트 및 문서화

### Phase 3: 낮은 우선순위 (추후 결정)
- threads.join_stream
- threads.copy

---

## 품질 보장

### 코드 품질 체크리스트

모든 구현은 다음을 만족해야 합니다:

- [ ] Ruff 포매팅 및 린팅 통과
- [ ] mypy 타입 체크 통과
- [ ] 단위 테스트 커버리지 80% 이상
- [ ] 통합 테스트 포함
- [ ] 사용자 인증 및 권한 검증
- [ ] 에러 처리 및 로깅
- [ ] API 문서 업데이트 (SDK 참조 문서)
- [ ] 마이그레이션 스크립트 테스트

### 성능 고려사항

- **Cron 검색:** 인덱스 최적화 (user_id, assistant_id, thread_id)
- **TTL 정리:** 배치 삭제로 성능 향상
- **Batch Runs:** 트랜잭션 크기 제한 (최대 100개)
- **Store Namespaces:** 쿼리 복잡도에 따라 캐싱 고려

---

## 롤백 계획

각 Phase는 독립적으로 배포 가능하도록 설계:

1. **마이그레이션 롤백**
   ```bash
   python3 scripts/migrate.py downgrade -1
   ```

2. **기능 플래그 (추후 도입 고려)**
   - 환경 변수로 새 기능 활성화/비활성화
   - 예: `ENABLE_CRONS=false`

3. **데이터 백업**
   - Phase 1 배포 전 전체 DB 백업
   - 각 마이그레이션 전 백업

---

## 참고 자료

- [LangGraph SDK 0.2.9 API Reference](https://langchain-ai.github.io/langgraph/cloud/reference/sdk/python_sdk_ref/)
- [LangGraph Cron Jobs](https://langchain-ai.github.io/langgraph/cloud/concepts/cron_jobs/)
- [AsyncPostgresStore Documentation](https://python.langchain.com/docs/langgraph/how-tos/persistence_postgres/)
- [croniter Documentation](https://github.com/kiorky/croniter)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/)

---

## 결론

이 계획을 따라 구현하면 API 준수율이 **83.8%에서 95%로** 향상됩니다. Phase 1의 핵심 기능(Crons, threads.update, store.list_namespaces)을 우선 구현하여 프로덕션 사용성을 높이고, Phase 2/3는 사용자 피드백에 따라 우선순위를 조정할 수 있습니다.

각 기능은 현재 코드베이스의 패턴을 따르므로 일관성이 유지되며, 충분한 테스트와 문서화를 통해 품질을 보장합니다.
