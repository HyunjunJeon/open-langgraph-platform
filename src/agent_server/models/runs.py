"""Agent Protocol 실행(Run) 관련 Pydantic 모델

이 모듈은 Agent Protocol의 실행(Run) 리소스를 위한 요청/응답 모델을 정의합니다.
LangGraph 그래프 실행의 전체 생명주기를 관리하며, 스트리밍, HITL(Human-in-the-Loop),
동시 실행 제어 등의 고급 기능을 지원합니다.

주요 모델:
• RunCreate - 실행 생성 요청 모델 (입력, 설정, HITL 제어 포함)
• Run - 실행 엔티티 모델 (상태, 출력, 메타데이터 포함)
• RunStatus - 간단한 실행 상태 응답 모델

사용 예:
    # 기본 실행 생성
    run_create = RunCreate(
        assistant_id="weather_agent",
        input={"location": "Seoul"}
    )

    # HITL interrupt 설정
    run_create = RunCreate(
        assistant_id="approval_agent",
        input={"request": "data"},
        interrupt_before=["approval_node"]
    )

    # 중단된 실행 재개
    run_create = RunCreate(
        assistant_id="approval_agent",
        command={"resume": {"approved": True}}
    )
"""

from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunCreate(BaseModel):
    """실행 생성 요청 모델

    새로운 그래프 실행을 시작하거나 중단된 실행을 재개하기 위한 요청 모델입니다.
    LangGraph의 모든 실행 옵션(스트리밍, HITL, 동시성 제어 등)을 지원합니다.

    주요 기능:
    - 기본 실행: assistant_id + input으로 새 실행 시작
    - HITL 재개: command로 중단된 실행 재개 및 상태 업데이트
    - 스트리밍 제어: stream, stream_mode로 실시간 이벤트 수신
    - Interrupt 설정: interrupt_before/after로 실행 일시 중지 지점 지정
    - 동시성 제어: multitask_strategy로 동일 스레드의 동시 실행 처리 방식 결정

    유효성 검증:
    - input과 command는 상호 배타적 (둘 중 하나만 지정 가능)
    - 빈 input dict는 command 존재 시 None으로 처리 (프론트엔드 호환성)
    - 둘 다 None이면 오류 발생
    """

    # 필수 필드
    assistant_id: str = Field(..., description="실행할 어시스턴트(그래프) ID")

    # 입력 데이터 (새 실행 시작 시 사용)
    input: dict[str, Any] | None = Field(
        None, description="그래프 실행에 전달할 입력 데이터. 체크포인트에서 재개 시 선택사항"
    )

    # LangGraph 실행 설정
    config: dict[str, Any] | None = Field({}, description="LangGraph 실행 설정 (타임아웃, 재귀 깊이 제한 등)")

    context: dict[str, Any] | None = Field(
        {}, description="LangGraph 실행 컨텍스트 (사용자 정의 데이터, 모델 설정 등)"
    )

    checkpoint: dict[str, Any] | None = Field(
        None,
        description="체크포인트 설정 (예: {'checkpoint_id': '...', 'checkpoint_ns': ''}). 특정 체크포인트에서 시작 시 사용",
    )

    # 스트리밍 설정
    stream: bool = Field(
        False, description="스트리밍 응답 활성화 여부. True시 SSE(Server-Sent Events)로 실시간 이벤트 전송"
    )

    stream_mode: str | list[str] | None = Field(
        None,
        description="LangGraph 스트림 모드 지정. 'values', 'updates', 'messages', 'events' 등 지원. 리스트로 여러 모드 동시 요청 가능",
    )

    # 클라이언트 연결 관리
    on_disconnect: str | None = Field(
        None,
        description="클라이언트 연결 끊김 시 동작. 'cancel'(실행 취소) 또는 'continue'(계속 실행, 기본값)",
    )

    # 동시성 제어
    multitask_strategy: str | None = Field(
        None,
        description="동일 스레드에서 동시 실행 처리 전략. 'reject'(거부), 'interrupt'(기존 중단), 'rollback'(롤백), 'enqueue'(대기열) 중 선택",
    )

    # ---------------------------------------------------------------------------
    # Human-in-the-Loop (HITL) 필드
    # ---------------------------------------------------------------------------
    command: dict[str, Any] | None = Field(
        None,
        description="중단된 실행 재개를 위한 명령. 상태 업데이트나 그래프 탐색 명령 포함. input과 상호 배타적",
    )

    interrupt_before: str | list[str] | None = Field(
        None, description="실행 직전에 중단할 노드 이름(들). '*'는 모든 노드에서 중단. HITL 승인 흐름에 유용"
    )

    interrupt_after: str | list[str] | None = Field(
        None, description="실행 직후에 중단할 노드 이름(들). '*'는 모든 노드에서 중단. 결과 검증 시 유용"
    )

    # ---------------------------------------------------------------------------
    # 서브그래프 설정
    # ---------------------------------------------------------------------------
    stream_subgraphs: bool | None = Field(
        False,
        description="스트리밍에 서브그래프 이벤트 포함 여부. True시 모든 서브그래프 이벤트 포함, False(기본값)시 제외. 하위 호환성을 위해 기본값 False",
    )

    @model_validator(mode="after")
    def validate_input_command_exclusivity(self) -> Self:
        """input과 command의 상호 배타성 검증

        동작 방식:
        1. input과 command가 모두 존재하는지 확인
        2. input이 빈 dict({})인 경우 None으로 처리 (프론트엔드 호환성)
        3. 둘 다 실제 값이 있으면 오류 발생
        4. 둘 다 None이면 오류 발생

        Returns:
            Self: 검증된 모델 인스턴스

        Raises:
            ValueError: input과 command를 동시에 지정하거나 둘 다 없는 경우

        참고:
            - 새 실행: input 사용, command는 None
            - 재개 실행: command 사용, input은 None
        """
        # 프론트엔드 호환성: 빈 input dict를 command 존재 시 None으로 처리
        if self.input is not None and self.command is not None:
            # input이 빈 dict인 경우 호환성을 위해 None으로 간주
            if self.input == {}:
                self.input = None
            else:
                raise ValueError("Cannot specify both 'input' and 'command' - they are mutually exclusive")
        if self.input is None and self.command is None:
            raise ValueError("Must specify either 'input' or 'command'")
        return self


class Run(BaseModel):
    """실행 엔티티 모델

    데이터베이스에 저장된 실행의 전체 상태를 표현하는 모델입니다.
    Agent Protocol 규격을 준수하며, LangGraph 그래프 실행의 생명주기를 추적합니다.

    생명주기 상태:
    - pending: 실행 생성됨, 아직 시작 안 됨
    - running: 현재 실행 중
    - completed: 성공적으로 완료됨
    - failed: 오류로 인해 실패함
    - cancelled: 사용자 또는 시스템에 의해 취소됨

    필드 설명:
    - run_id: 실행 고유 식별자 (UUID)
    - thread_id: 이 실행이 속한 스레드 ID (대화 컨텍스트)
    - assistant_id: 실행한 어시스턴트(그래프) ID
    - status: 현재 실행 상태 (위의 5가지 중 하나)
    - input: 실행 시작 시 제공된 입력 데이터
    - output: 실행 완료 시 생성된 출력 데이터 (완료 전에는 None)
    - error_message: 실패 시 오류 메시지 (성공 시 None)
    - config: LangGraph 실행 설정 (타임아웃, 재귀 깊이 등)
    - context: 실행 컨텍스트 (사용자 정의 데이터)
    - user_id: 실행을 시작한 사용자 ID (다중 테넌트 격리)
    - created_at: 실행 생성 시각
    - updated_at: 마지막 업데이트 시각

    사용 예:
        # ORM 모델에서 변환
        run = Run.model_validate(orm_run)

        # 상태 확인
        if run.status == "completed":
            print(run.output)
        elif run.status == "failed":
            print(run.error_message)
    """

    # 식별자
    run_id: str  # 실행 고유 ID
    thread_id: str  # 스레드(대화) ID
    assistant_id: str  # 어시스턴트(그래프) ID

    # 실행 상태
    status: str = "pending"  # pending, running, completed, failed, cancelled

    # 입출력 데이터
    input: dict[str, Any]  # 실행 입력 데이터
    output: dict[str, Any] | None = None  # 실행 출력 데이터 (완료 시에만 존재)
    error_message: str | None = None  # 오류 메시지 (실패 시에만 존재)

    # 실행 설정
    config: dict[str, Any] | None = {}  # LangGraph 실행 설정
    context: dict[str, Any] | None = {}  # 실행 컨텍스트

    # 메타데이터
    user_id: str  # 실행 소유자 (다중 테넌트 격리용)
    created_at: datetime  # 생성 시각
    updated_at: datetime  # 마지막 업데이트 시각

    model_config = ConfigDict(from_attributes=True)  # ORM 모델에서 직접 변환 허용


class RunStatus(BaseModel):
    """간단한 실행 상태 응답 모델

    실행의 현재 상태만을 반환하는 경량 응답 모델입니다.
    전체 Run 모델이 필요 없는 상태 폴링이나 헬스체크에 사용됩니다.

    필드:
    - run_id: 실행 고유 식별자
    - status: 현재 실행 상태 (pending, running, completed, failed, cancelled)
    - message: 선택적 상태 메시지 (추가 컨텍스트 제공)

    사용 예:
        # 실행 상태만 조회
        status = RunStatus(
            run_id="run_123",
            status="running",
            message="Processing step 3 of 5"
        )
    """

    run_id: str  # 실행 ID
    status: str  # 현재 상태
    message: str | None = None  # 선택적 상태 메시지
