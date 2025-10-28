"""Agent Protocol 어시스턴트 관련 Pydantic 모델

이 모듈은 어시스턴트 생성, 업데이트, 조회를 위한 요청/응답 모델을 정의합니다.
어시스턴트는 특정 LangGraph 그래프를 래핑하여 사용자별로 관리되는 엔티티입니다.

주요 모델:
• AssistantCreate - 어시스턴트 생성 요청
• AssistantUpdate - 어시스턴트 업데이트 요청
• Assistant - 어시스턴트 엔티티 (응답)
• AssistantList - 어시스턴트 목록 응답
• AssistantSearchRequest - 어시스턴트 검색 요청
• AgentSchemas - 그래프 스키마 정의 (input/output/state/config)

Config vs Context (LangGraph 0.6.0+):
• config: LangGraph 실행 시 런타임 설정 (예: model_name, temperature)
• context: 그래프가 configurable한 경우 컴파일 타임 컨텍스트

사용 예:
    # 어시스턴트 생성
    assistant = AssistantCreate(
        graph_id="weather_agent",
        config={"model": "gpt-4"},
        metadata={"team": "sales"}
    )
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AssistantCreate(BaseModel):
    """어시스턴트 생성 요청 모델

    새 어시스턴트를 생성하기 위한 요청 데이터를 정의합니다.
    최소 요구사항은 graph_id만이며, 나머지 필드는 자동 생성됩니다.

    주요 필드:
    - assistant_id: 생략 시 UUID 자동 생성
    - name: 생략 시 graph_id 기반으로 자동 생성
    - config: LangGraph 실행 설정 (런타임)
    - context: LangGraph 컴파일 컨텍스트
    - if_exists: 중복 생성 시 동작 제어
    """

    # 어시스턴트 고유 식별자 (생략 시 UUID 자동 생성)
    assistant_id: str | None = Field(
        None, description="Unique assistant identifier (auto-generated if not provided)"
    )

    # 사람이 읽을 수 있는 어시스턴트 이름 (생략 시 자동 생성)
    name: str | None = Field(
        None,
        description="Human-readable assistant name (auto-generated if not provided)",
    )

    # 어시스턴트 설명 (선택사항)
    description: str | None = Field(None, description="Assistant description")

    # LangGraph 실행 설정 (예: model_name, temperature)
    config: dict[str, Any] | None = Field({}, description="Assistant configuration")

    # LangGraph 컴파일 컨텍스트 (그래프가 configurable한 경우 사용)
    context: dict[str, Any] | None = Field({}, description="Assistant context")

    # open_langgraph.json에 정의된 그래프 ID (필수)
    graph_id: str = Field(..., description="LangGraph graph ID from open_langgraph.json")

    # 검색 및 필터링을 위한 메타데이터
    metadata: dict[str, Any] | None = Field(
        {}, description="Metadata to use for searching and filtering assistants."
    )

    # 중복 생성 시 동작: "error" (오류 반환) 또는 "do_nothing" (무시)
    if_exists: str | None = Field("error", description="What to do if assistant exists: error or do_nothing")


class Assistant(BaseModel):
    """어시스턴트 엔티티 응답 모델

    데이터베이스에 저장된 어시스턴트의 전체 정보를 나타냅니다.
    이 모델은 ORM 모델(AssistantORM)에서 자동 변환됩니다.

    주요 특징:
    - 버전 관리: 업데이트 시 version 필드가 자동 증가
    - 사용자 스코핑: user_id를 통해 사용자별로 격리
    - 타임스탬프: 생성 및 수정 시각 자동 추적
    - 메타데이터: JSONB 컬럼으로 유연한 검색/필터링 지원

    참고:
        - metadata 필드는 ORM의 metadata_dict 컬럼에서 매핑됩니다
        - from_attributes=True로 ORM 객체 자동 변환 지원
    """

    # 어시스턴트 고유 식별자
    assistant_id: str

    # 사람이 읽을 수 있는 이름
    name: str

    # 어시스턴트 설명 (선택사항)
    description: str | None = None

    # LangGraph 실행 설정 (런타임)
    config: dict[str, Any] = Field(default_factory=dict)

    # LangGraph 컴파일 컨텍스트 (configurable 그래프용)
    context: dict[str, Any] = Field(default_factory=dict)

    # open_langgraph.json에 정의된 그래프 ID
    graph_id: str

    # 소유자의 사용자 ID (멀티테넌시 격리)
    user_id: str

    # 어시스턴트 버전 (업데이트마다 증가)
    version: int = Field(..., description="The version of the assistant.")

    # 검색/필터링용 메타데이터 (ORM의 metadata_dict에서 매핑)
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_dict")

    # 생성 시각 (UTC)
    created_at: datetime

    # 최종 수정 시각 (UTC)
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)  # ORM 모델에서 자동 변환 지원


class AssistantUpdate(BaseModel):
    """어시스턴트 업데이트 요청 모델

    기존 어시스턴트의 설정을 수정하기 위한 요청 데이터를 정의합니다.
    모든 필드는 선택사항이며, 제공된 필드만 업데이트됩니다.

    주요 특징:
    - 부분 업데이트: 변경할 필드만 제공
    - 버전 관리: 업데이트 성공 시 version 자동 증가
    - config/context: 런타임 설정 또는 컴파일 컨텍스트 수정 가능

    참고:
        - 업데이트 시 새로운 버전의 어시스턴트가 생성됩니다
        - assistant_id는 변경할 수 없습니다 (불변 식별자)
    """

    # 어시스턴트 이름 (생략 시 기존 값 유지)
    name: str | None = Field(None, description="The name of the assistant (auto-generated if not provided)")

    # 어시스턴트 설명 (생략 시 기존 값 유지)
    description: str | None = Field(None, description="The description of the assistant. Defaults to null.")

    # LangGraph 실행 설정 업데이트
    config: dict[str, Any] | None = Field({}, description="Configuration to use for the graph.")

    # 사용할 그래프 ID 변경 (기본값: "agent")
    graph_id: str = Field("agent", description="The ID of the graph")

    # LangGraph 컴파일 컨텍스트 업데이트 (configurable 그래프용)
    context: dict[str, Any] | None = Field(
        {},
        description="The context to use for the graph. Useful when graph is configurable.",
    )

    # 검색/필터링용 메타데이터 업데이트
    metadata: dict[str, Any] | None = Field(
        {}, description="Metadata to use for searching and filtering assistants."
    )


class AssistantList(BaseModel):
    """어시스턴트 목록 응답 모델

    여러 어시스턴트를 조회할 때 반환되는 페이지네이션 응답입니다.

    주요 필드:
    - assistants: 현재 페이지의 어시스턴트 목록
    - total: 전체 어시스턴트 개수 (페이지네이션 계산용)

    사용 예:
        # 20개씩 페이지네이션
        GET /assistants?limit=20&offset=0
        -> AssistantList(assistants=[...], total=150)
    """

    # 현재 페이지의 어시스턴트 목록
    assistants: list[Assistant]

    # 검색 조건에 맞는 전체 어시스턴트 개수
    total: int


class AssistantSearchRequest(BaseModel):
    """어시스턴트 검색 요청 모델

    어시스턴트를 검색하고 필터링하기 위한 쿼리 파라미터를 정의합니다.
    모든 필터는 선택사항이며, 여러 필터를 조합하여 사용할 수 있습니다.

    주요 기능:
    - 텍스트 검색: name, description 필드로 부분 일치 검색
    - 그래프 필터링: 특정 graph_id를 사용하는 어시스턴트만 조회
    - 메타데이터 필터링: JSONB 쿼리로 유연한 검색
    - 페이지네이션: limit/offset으로 결과 범위 제어

    검증 규칙:
    - limit: 1~100 범위 (기본값: 20)
    - offset: 0 이상 (기본값: 0)

    사용 예:
        # sales 팀의 weather_agent 검색
        SearchRequest(
            graph_id="weather_agent",
            metadata={"team": "sales"},
            limit=10
        )
    """

    # 어시스턴트 이름으로 필터링 (부분 일치)
    name: str | None = Field(None, description="Filter by assistant name")

    # 어시스턴트 설명으로 필터링 (부분 일치)
    description: str | None = Field(None, description="Filter by assistant description")

    # 그래프 ID로 필터링 (정확히 일치)
    graph_id: str | None = Field(None, description="Filter by graph ID")

    # 페이지 크기 (1~100, 기본값: 20)
    limit: int | None = Field(20, le=100, ge=1, description="Maximum results")

    # 시작 오프셋 (0 이상, 기본값: 0)
    offset: int | None = Field(0, ge=0, description="Results offset")

    # 메타데이터로 필터링 (JSONB 쿼리)
    metadata: dict[str, Any] | None = Field(
        {}, description="Metadata to use for searching and filtering assistants."
    )


class AgentSchemas(BaseModel):
    """그래프 스키마 정의 모델 (클라이언트 통합용)

    LangGraph 그래프의 입력/출력/상태/설정 스키마를 JSON Schema 형식으로 제공합니다.
    클라이언트는 이 스키마를 사용하여 UI를 동적으로 생성하거나 유효성을 검증할 수 있습니다.

    주요 스키마 타입 (4가지):
    1. input_schema: 그래프 실행 시 필요한 입력 데이터 형식
       예: {"messages": [{"role": "user", "content": "..."}]}

    2. output_schema: 그래프 실행 결과로 반환되는 데이터 형식
       예: {"messages": [...], "status": "completed"}

    3. state_schema: 그래프 내부 상태의 전체 구조
       예: StateGraph의 TypedDict 정의

    4. config_schema: 그래프 실행 설정 파라미터
       예: {"model_name": "gpt-4", "temperature": 0.7}

    JSON Schema 형식:
        각 스키마는 표준 JSON Schema (Draft 7) 형식을 따릅니다.
        {
            "type": "object",
            "properties": {...},
            "required": [...],
            "additionalProperties": false
        }

    사용 예:
        # 그래프 스키마 조회
        GET /assistants/{assistant_id}/schemas
        -> AgentSchemas(
            input_schema={...},
            output_schema={...},
            state_schema={...},
            config_schema={...}
        )

    참고:
        - 스키마는 그래프 정의에서 자동으로 추출됩니다
        - 클라이언트는 이 스키마로 요청 데이터를 검증해야 합니다
    """

    # 그래프 입력 데이터의 JSON Schema
    input_schema: dict[str, Any] = Field(..., description="JSON Schema for agent inputs")

    # 그래프 출력 데이터의 JSON Schema
    output_schema: dict[str, Any] = Field(..., description="JSON Schema for agent outputs")

    # 그래프 상태의 JSON Schema (전체 StateGraph 구조)
    state_schema: dict[str, Any] = Field(..., description="JSON Schema for agent state")

    # 그래프 실행 설정의 JSON Schema (config 파라미터)
    config_schema: dict[str, Any] = Field(..., description="JSON Schema for agent config")
