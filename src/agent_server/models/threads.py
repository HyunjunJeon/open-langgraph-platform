"""Agent Protocol 스레드 관련 Pydantic 모델

이 모듈은 스레드(대화 세션)의 생성, 조회, 검색, 상태 관리를 위한 Pydantic 모델을 정의합니다.
스레드는 LangGraph 그래프 실행의 격리된 컨텍스트를 제공하며, 각 스레드는 독립적인 상태와
체크포인트 이력을 유지합니다.

주요 구성 요소:
• ThreadCreate - 스레드 생성 요청 모델
• Thread - 스레드 엔티티 모델 (ORM 매핑)
• ThreadList/ThreadSearchResponse - 스레드 목록 응답 모델
• ThreadState - 스레드 상태 및 체크포인트 정보
• ThreadCheckpoint - 체크포인트 식별자
• ThreadHistoryRequest - 상태 이력 조회 요청

사용 예:
    # 스레드 생성
    thread_create = ThreadCreate(
        metadata={"user_name": "Alice"},
        initial_state={"messages": []}
    )

    # 스레드 상태 조회
    state = ThreadState(
        values={"messages": [...]},
        checkpoint=ThreadCheckpoint(checkpoint_id="abc123")
    )
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ThreadCreate(BaseModel):
    """스레드 생성 요청 모델

    새로운 스레드를 생성할 때 사용하는 요청 모델입니다.
    스레드는 대화의 격리된 컨텍스트를 제공하며, 각 스레드는 독립적인
    체크포인트 이력과 상태를 유지합니다.

    필드 설명:
        metadata: 스레드와 연결된 사용자 정의 메타데이터 (선택)
            - 예: {"user_name": "Alice", "topic": "weather"}
            - 스레드 검색 및 필터링에 활용 가능
        initial_state: LangGraph 그래프의 초기 상태 (선택)
            - 그래프의 채널 값을 미리 설정 가능
            - 예: {"messages": [], "context": "initial"}
    """

    metadata: dict[str, Any] | None = Field(None, description="스레드에 연결된 사용자 정의 메타데이터")
    initial_state: dict[str, Any] | None = Field(None, description="LangGraph 그래프의 초기 채널 상태")


class Thread(BaseModel):
    """스레드 엔티티 모델

    데이터베이스에 저장된 스레드의 메타데이터를 나타내는 모델입니다.
    ORM 모델(ThreadMetadata)과 직접 매핑되며, Agent Protocol 응답으로 반환됩니다.

    필드 설명:
        thread_id: 스레드 고유 식별자 (UUID)
        status: 스레드 현재 상태
            - "idle": 대기 중 (기본값)
            - "busy": 실행 중
        metadata: 사용자 정의 메타데이터 딕셔너리
            - 생성 시 제공된 메타데이터 저장
            - 검색 및 필터링에 활용
        user_id: 스레드 소유자의 사용자 ID
            - 멀티테넌시 격리를 위해 사용
        created_at: 스레드 생성 타임스탬프

    참고:
        - ORM 모델 ThreadMetadata와 from_attributes=True로 자동 변환
        - 실제 대화 상태는 LangGraph 체크포인트에 저장 (별도)
    """

    thread_id: str  # 스레드 고유 식별자
    status: str = "idle"  # 스레드 상태 (idle/busy)
    metadata: dict[str, Any] = Field(
        default_factory=dict  # 사용자 정의 메타데이터
    )
    user_id: str  # 스레드 소유 사용자 ID
    created_at: datetime  # 생성 타임스탬프

    model_config = ConfigDict(from_attributes=True)  # ORM 모델에서 자동 변환 허용


class ThreadList(BaseModel):
    """스레드 목록 응답 모델

    여러 스레드를 조회할 때 사용하는 응답 모델입니다.
    페이지네이션 없이 전체 결과를 반환합니다.

    필드 설명:
        threads: 스레드 엔티티 목록
        total: 전체 스레드 개수
    """

    threads: list[Thread]  # 스레드 목록
    total: int  # 전체 개수


class ThreadSearchRequest(BaseModel):
    """스레드 검색 요청 모델

    메타데이터, 상태, 페이지네이션 등을 기반으로 스레드를 검색하는 요청 모델입니다.
    사용자별로 격리된 스레드만 검색됩니다 (인증 미들웨어에서 처리).

    필드 설명:
        metadata: 메타데이터 기반 필터 (선택)
            - JSONB 필드에 대한 부분 매칭
            - 예: {"topic": "weather"} → topic이 weather인 스레드
        status: 스레드 상태 필터 (선택)
            - "idle" 또는 "busy"
        limit: 최대 결과 개수 (1~100)
            - 기본값: 20
        offset: 결과 시작 위치
            - 페이지네이션을 위한 오프셋
            - 기본값: 0
        order_by: 정렬 순서
            - 기본값: "created_at DESC" (최신순)
            - 예: "created_at ASC", "status DESC"
    """

    metadata: dict[str, Any] | None = Field(None, description="메타데이터 기반 필터 (JSONB 부분 매칭)")
    status: str | None = Field(None, description="스레드 상태 필터 (idle/busy)")
    limit: int | None = Field(20, le=100, ge=1, description="최대 결과 개수 (1~100)")
    offset: int | None = Field(0, ge=0, description="결과 시작 위치 (페이지네이션)")
    order_by: str | None = Field("created_at DESC", description="정렬 순서 (예: created_at DESC)")


class ThreadSearchResponse(BaseModel):
    """스레드 검색 응답 모델

    검색 요청에 대한 응답을 나타내며, 페이지네이션 정보를 포함합니다.

    필드 설명:
        threads: 검색된 스레드 목록
        total: 필터 조건을 만족하는 전체 스레드 개수
        limit: 요청된 최대 결과 개수
        offset: 결과 시작 위치

    참고:
        - total은 전체 매칭 개수, threads는 limit/offset으로 잘린 결과
        - 클라이언트는 total을 사용해 페이지네이션 UI 구성 가능
    """

    threads: list[Thread]  # 검색된 스레드 목록
    total: int  # 전체 매칭 개수
    limit: int  # 요청된 최대 개수
    offset: int  # 결과 시작 위치


class ThreadCheckpoint(BaseModel):
    """스레드 체크포인트 식별자

    LangGraph 체크포인트를 고유하게 식별하는 모델입니다.
    체크포인트는 그래프 실행의 특정 시점 상태를 나타냅니다.

    필드 설명:
        checkpoint_id: 체크포인트 고유 ID
            - LangGraph가 자동 생성 (UUID)
            - None이면 최신 체크포인트를 의미
        thread_id: 체크포인트가 속한 스레드 ID
            - 멀티 스레드 환경에서 식별용
        checkpoint_ns: 체크포인트 네임스페이스
            - 서브그래프 실행을 구분하기 위한 네임스페이스
            - 빈 문자열("")이면 메인 그래프
            - 예: "subgraph_1", "nested.subgraph_2"

    참고:
        - 체크포인트는 LangGraph의 AsyncPostgresSaver에 저장됨
        - 네임스페이스는 서브그래프 실행 추적에 활용
    """

    checkpoint_id: str | None = None  # 체크포인트 ID (None=최신)
    thread_id: str | None = None  # 스레드 ID
    checkpoint_ns: str | None = ""  # 네임스페이스 (서브그래프 구분용)


class ThreadCheckpointPostRequest(BaseModel):
    """스레드 체크포인트 조회 요청 모델

    특정 체크포인트의 상태를 조회하기 위한 POST 요청 모델입니다.

    필드 설명:
        checkpoint: 조회할 체크포인트 식별자
            - checkpoint_id, thread_id, checkpoint_ns로 체크포인트 지정
        subgraphs: 서브그래프 상태 포함 여부
            - True: 서브그래프의 체크포인트도 함께 반환
            - False: 메인 그래프 체크포인트만 반환 (기본값)

    참고:
        - 서브그래프 포함 시 네임스페이스 기반으로 계층적 상태 조회
    """

    checkpoint: ThreadCheckpoint = Field(description="조회할 체크포인트 식별자")
    subgraphs: bool | None = Field(False, description="서브그래프 상태 포함 여부 (기본: False)")


class ThreadState(BaseModel):
    """스레드 상태 모델

    특정 시점의 그래프 실행 상태를 나타내는 모델입니다.
    LangGraph 체크포인트에서 로드된 상태를 Agent Protocol 형식으로 변환하여 제공합니다.

    이 모델은 Thread 모델(메타데이터)과는 다른 개념입니다:
    - Thread: 스레드의 메타데이터 (상태, 생성일, user_id 등)
    - ThreadState: 특정 체크포인트의 그래프 실행 상태 (채널 값, 다음 노드 등)

    필드 설명:
        values: 그래프의 채널 값
            - 예: {"messages": [...], "context": {...}}
            - StateGraph에서 정의된 채널의 현재 값
        next: 다음에 실행될 노드 이름 목록
            - 예: ["agent_node", "tool_node"]
            - 빈 리스트면 그래프 실행 완료
        tasks: 실행 예정 태스크 목록
            - 각 태스크는 노드 실행 정보 포함
            - Human-in-the-loop 시 대기 중인 태스크 표시
        interrupts: 인터럽트 데이터 목록
            - interrupt() 호출로 생성된 중단 지점 정보
            - 사용자 승인 대기 시 활용
        metadata: 체크포인트 메타데이터
            - LangGraph가 자동 생성하는 메타정보
            - 예: step, source, writes 등
        created_at: 체크포인트 생성 타임스탬프
        checkpoint: 현재 체크포인트 식별자
            - 이 상태에 해당하는 체크포인트
        parent_checkpoint: 부모 체크포인트 식별자 (선택)
            - 이전 단계의 체크포인트 (상태 이력 추적용)
        checkpoint_id: 체크포인트 ID (하위 호환성)
            - checkpoint.checkpoint_id와 동일
        parent_checkpoint_id: 부모 체크포인트 ID (하위 호환성)
            - parent_checkpoint.checkpoint_id와 동일

    참고:
        - values는 그래프의 모든 채널 값을 포함 (messages, context 등)
        - next가 비어있으면 그래프가 최종 상태(종료)에 도달한 것
        - interrupts가 있으면 사용자 입력 대기 중
    """

    values: dict[str, Any] = Field(description="그래프 채널의 현재 값 (messages, context 등)")
    next: list[str] = Field(default_factory=list, description="다음에 실행될 노드 이름 목록")
    tasks: list[dict[str, Any]] = Field(
        default_factory=list, description="실행 예정 태스크 목록 (HITL 대기 중 태스크 포함)"
    )
    interrupts: list[dict[str, Any]] = Field(
        default_factory=list, description="인터럽트 데이터 목록 (사용자 승인 대기)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="체크포인트 메타데이터 (step, source 등)"
    )
    created_at: datetime | None = Field(None, description="체크포인트 생성 타임스탬프")
    checkpoint: ThreadCheckpoint = Field(description="현재 체크포인트 식별자")
    parent_checkpoint: ThreadCheckpoint | None = Field(None, description="부모 체크포인트 식별자 (이전 단계)")
    checkpoint_id: str | None = Field(
        None, description="체크포인트 ID (하위 호환성, checkpoint.checkpoint_id와 동일)"
    )
    parent_checkpoint_id: str | None = Field(
        None,
        description="부모 체크포인트 ID (하위 호환성, parent_checkpoint.checkpoint_id와 동일)",
    )


class ThreadHistoryRequest(BaseModel):
    """스레드 이력 조회 요청 모델

    스레드의 체크포인트 이력을 조회하기 위한 요청 모델입니다.
    시간순으로 역순(최신→과거)으로 체크포인트 목록을 반환합니다.

    필드 설명:
        limit: 반환할 상태 개수
            - 범위: 1~1000
            - 기본값: 10
            - 최신 N개의 체크포인트 반환
        before: 기준 체크포인트 ID (선택)
            - 이 체크포인트 이전의 상태만 반환 (페이지네이션)
            - 예: 첫 페이지 10개 조회 후 가장 오래된 ID를 before로 전달
        metadata: 메타데이터 필터 (선택)
            - 특정 메타데이터를 가진 체크포인트만 필터링
            - 예: {"step": 5} → step이 5인 체크포인트
        checkpoint: 서브그래프 필터링을 위한 체크포인트 (선택)
            - 특정 체크포인트의 서브그래프 이력 조회
            - checkpoint_id, checkpoint_ns 포함
        subgraphs: 서브그래프 상태 포함 여부
            - True: 서브그래프의 체크포인트도 포함
            - False: 메인 그래프만 (기본값)
        checkpoint_ns: 체크포인트 네임스페이스 (선택)
            - 특정 네임스페이스의 체크포인트만 조회
            - 예: "subgraph_1" → 해당 서브그래프의 이력만

    참고:
        - 반환 순서: 최신 → 과거 (created_at DESC)
        - before를 사용하면 커서 기반 페이지네이션 가능
        - subgraphs=True 시 모든 네임스페이스의 체크포인트 포함
    """

    limit: int | None = Field(10, ge=1, le=1000, description="반환할 상태 개수 (1~1000, 기본: 10)")
    before: str | None = Field(None, description="이 체크포인트 ID 이전의 상태만 반환 (페이지네이션)")
    metadata: dict[str, Any] | None = Field(
        None, description="메타데이터 필터 (특정 메타데이터를 가진 체크포인트만)"
    )
    checkpoint: dict[str, Any] | None = Field(
        None, description="서브그래프 필터링을 위한 체크포인트 (checkpoint_id, ns 포함)"
    )
    subgraphs: bool | None = Field(False, description="서브그래프 상태 포함 여부 (기본: False)")
    checkpoint_ns: str | None = Field(None, description="체크포인트 네임스페이스 (특정 네임스페이스만 조회)")
