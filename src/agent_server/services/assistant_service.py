"""어시스턴트 비즈니스 로직 서비스 계층

이 모듈은 어시스턴트 관리와 관련된 모든 비즈니스 로직을 캡슐화합니다.
계층화된 아키텍처 패턴을 따르며, api/assistants.py에서 코드를 추출하여
관심사를 분리하고 유지보수성을 향상시켰습니다.

주요 책임:
• 비즈니스 로직 및 유효성 검증
• SQLAlchemy ORM을 통한 데이터베이스 작업
• 그래프 스키마 추출 및 조작
• 여러 컴포넌트 간 조율

이 서비스는 Open LangGraph의 첫 번째 서비스 계층 구현입니다.
동일한 패턴이 다른 API(runs, threads, crons)에도 적용될 예정입니다.

주요 구성 요소:
• AssistantService - 어시스턴트 CRUD 및 버전 관리
• to_pydantic() - SQLAlchemy ORM → Pydantic 모델 변환
• _extract_graph_schemas() - LangGraph 스키마 추출
• get_assistant_service() - FastAPI 의존성 주입 헬퍼
"""

import uuid
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from fastapi import Depends, HTTPException
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.orm import Assistant as AssistantORM
from ..core.orm import AssistantVersion as AssistantVersionORM
from ..core.orm import get_session
from ..models import Assistant, AssistantCreate, AssistantSearchRequest, AssistantUpdate
from ..services.langgraph_service import LangGraphService, get_langgraph_service

CompiledGraph = CompiledStateGraph[Any, Any, Any, Any]


def to_pydantic(row: AssistantORM) -> Assistant:
    """SQLAlchemy ORM 객체를 Pydantic 모델로 변환 (타입 캐스팅 포함)

    Assistant ORM은 속성명과 컬럼명이 불일치하므로 from_attributes=True 사용:
    - ORM 속성: metadata_dict
    - DB 컬럼: metadata
    - Pydantic 필드: metadata (alias="metadata_dict")

    이는 Thread/Run과 다른 점입니다. Thread/Run은 속성명과 컬럼명이 일치합니다.

    Args:
        row (AssistantORM): 변환할 SQLAlchemy ORM 객체

    Returns:
        Assistant: Pydantic Assistant 모델
    """
    # UUID를 문자열로 캐스팅하여 Pydantic 스키마와 일치시킴
    if hasattr(row, "assistant_id") and row.assistant_id is not None:
        row.assistant_id = str(row.assistant_id)
    if hasattr(row, "user_id") and isinstance(row.user_id, uuid.UUID):
        row.user_id = str(row.user_id)

    # Pydantic의 내장 ORM 변환 기능 사용 (from_attributes=True)
    return Assistant.model_validate(row, from_attributes=True)


def _state_jsonschema(graph: CompiledGraph) -> dict[str, Any] | None:
    """그래프 채널로부터 상태 스키마를 추출

    LangGraph의 내부 채널 정보를 기반으로 상태의 JSON 스키마를 생성합니다.
    각 채널의 UpdateType을 추출하여 Pydantic 모델을 동적으로 생성합니다.

    Args:
        graph: LangGraph 그래프 객체

    Returns:
        dict | None: 상태의 JSON 스키마 (딕셔너리 형태)
    """
    from langgraph._internal._pydantic import create_model

    fields: dict[str, tuple[type[Any], Any]] = {}
    for channel_name in getattr(graph, "stream_channels_list", []):
        channel = graph.channels[channel_name]
        update_type = getattr(channel, "UpdateType", Any)
        if not isinstance(update_type, type):
            update_type = Any
        fields[channel_name] = (update_type, None)

    try:
        schema_fields: dict[str, Any] = dict(fields)
        state_model = create_model(graph.get_name("State"), **schema_fields)
    except Exception:
        return None

    try:
        return state_model.model_json_schema()
    except Exception:
        return None


def _get_configurable_jsonschema(graph: CompiledGraph) -> dict[str, Any]:
    """그래프의 configurable 부분에 대한 JSON 스키마 추출

    그래프 설정에서 사용자가 설정 가능한(configurable) 필드들의 스키마를 추출합니다.
    LangGraph 내부용 필드(__pregel_resuming, __pregel_checkpoint_id)는 제외합니다.

    Args:
        graph: LangGraph 그래프 객체

    Returns:
        dict: configurable 필드의 JSON 스키마 (없으면 빈 딕셔너리)
    """
    from pydantic import TypeAdapter

    # LangGraph 내부 전용 설정 필드 (사용자에게 노출하지 않음)
    EXCLUDED_CONFIG_SCHEMA = {"__pregel_resuming", "__pregel_checkpoint_id"}

    config_schema = graph.config_schema()
    model_fields = getattr(config_schema, "model_fields", None) or getattr(config_schema, "__fields__", None)

    if not model_fields or "configurable" not in model_fields:
        return {}

    field_info = model_fields["configurable"]
    configurable = TypeAdapter(field_info.annotation)
    json_schema = configurable.json_schema()
    if not isinstance(json_schema, dict):
        return {}

    properties = json_schema.get("properties")
    if isinstance(properties, dict):
        for key in EXCLUDED_CONFIG_SCHEMA:
            properties.pop(key, None)

    config_type = getattr(graph, "config_type", None)
    if config_type is not None and hasattr(config_type, "__name__"):
        json_schema["title"] = cast("str", config_type.__name__)

    return json_schema


def _extract_graph_schemas(graph: CompiledGraph) -> dict[str, Any]:
    """컴파일된 LangGraph 그래프 객체에서 모든 스키마 추출

    그래프의 입력, 출력, 상태, 설정, 컨텍스트 스키마를 JSON 형식으로 추출합니다.
    각 스키마 추출은 독립적으로 시도하며, 실패 시 None으로 설정됩니다.

    Args:
        graph: 컴파일된 LangGraph 그래프 객체

    Returns:
        dict: 5가지 스키마를 담은 딕셔너리
            - input_schema: 그래프 입력 스키마
            - output_schema: 그래프 출력 스키마
            - state_schema: 그래프 상태 스키마
            - config_schema: configurable 설정 스키마
            - context_schema: 런타임 컨텍스트 스키마
    """
    try:
        input_schema = graph.get_input_jsonschema()
    except Exception:
        input_schema = None

    try:
        output_schema = graph.get_output_jsonschema()
    except Exception:
        output_schema = None

    try:
        state_schema = _state_jsonschema(graph)
    except Exception:
        state_schema = None

    try:
        config_schema = _get_configurable_jsonschema(graph)
    except Exception:
        config_schema = None

    try:
        context_schema = graph.get_context_jsonschema()
    except Exception:
        context_schema = None

    return {
        "input_schema": input_schema,
        "output_schema": output_schema,
        "state_schema": state_schema,
        "config_schema": config_schema,
        "context_schema": context_schema,
    }


class AssistantService:
    """어시스턴트 관리 서비스

    어시스턴트의 생성, 조회, 수정, 삭제(CRUD) 및 버전 관리를 담당하는 서비스입니다.
    데이터베이스 작업과 LangGraph 그래프 검증을 조율하며,
    어시스턴트 관련 모든 비즈니스 로직을 캡슐화합니다.

    주요 기능:
    - 어시스턴트 생성 및 중복 검사
    - 버전 이력 추적 및 롤백
    - 그래프 스키마 조회
    - 검색 및 페이지네이션
    - 멀티테넌트 격리 (user_id 기반)

    Attributes:
        session (AsyncSession): SQLAlchemy 비동기 세션
        langgraph_service (LangGraphService): LangGraph 서비스 인스턴스
    """

    def __init__(self, session: AsyncSession, langgraph_service: LangGraphService):
        """AssistantService 초기화

        Args:
            session (AsyncSession): 데이터베이스 세션
            langgraph_service (LangGraphService): LangGraph 서비스
        """
        self.session: AsyncSession = session
        self.langgraph_service: LangGraphService = langgraph_service

    async def create_assistant(self, request: AssistantCreate, user_identity: str) -> Assistant:
        """새로운 어시스턴트 생성

        요청된 그래프를 검증하고 어시스턴트를 생성합니다.
        중복 검사를 수행하며, if_exists 정책에 따라 동작합니다.

        동작 흐름:
        1. open_langgraph.json에 그래프 존재 여부 확인
        2. 그래프 로딩 가능 여부 검증
        3. config와 context 동기화 (LangGraph 0.6.0+ context 권장)
        4. 중복 어시스턴트 검사 (user_id, graph_id, config 조합)
        5. 어시스턴트 레코드 생성
        6. 버전 1 이력 레코드 생성

        Args:
            request (AssistantCreate): 어시스턴트 생성 요청 데이터
            user_identity (str): 사용자 식별자

        Returns:
            Assistant: 생성된 어시스턴트

        Raises:
            HTTPException(400): 그래프가 존재하지 않거나 로드 실패
            HTTPException(400): config와 context를 동시에 지정한 경우
            HTTPException(409): 동일한 어시스턴트가 이미 존재 (if_exists="error")
        """
        # LangGraph 서비스에서 사용 가능한 그래프 목록 조회
        available_graphs = self.langgraph_service.list_graphs()

        # 주요 식별자로 graph_id 사용
        graph_id = request.graph_id

        if graph_id not in available_graphs:
            raise HTTPException(
                400,
                f"Graph '{graph_id}' not found in open_langgraph.json. Available: {list(available_graphs.keys())}",
            )

        # 그래프를 실제로 로드할 수 있는지 검증
        try:
            await self.langgraph_service.get_graph(graph_id)
        except Exception as e:
            raise HTTPException(400, f"Failed to load graph: {str(e)}") from e

        config: dict[str, Any] = dict(request.config) if isinstance(request.config, dict) else {}
        context_dict: dict[str, Any] | None = (
            dict(request.context) if isinstance(request.context, dict) else None
        )

        # LangGraph 0.6.0+에서는 context가 configurable의 대체품
        # 둘 다 지정하면 충돌 방지
        configurable_section = config.get("configurable")
        if isinstance(configurable_section, dict) and context_dict:
            raise HTTPException(
                status_code=400,
                detail="Cannot specify both configurable and context. Prefer setting context alone. Context was introduced in LangGraph 0.6.0 and is the long term planned replacement for configurable.",
            )

        # config와 context를 서로 동기화하여 일관성 유지
        if isinstance(configurable_section, dict):
            context_dict = configurable_section
        elif context_dict is not None:
            config["configurable"] = context_dict

        # assistant_id가 제공되지 않으면 자동 생성
        assistant_id = request.assistant_id or str(uuid4())

        # name이 제공되지 않으면 기본 이름 생성
        name = request.name or f"Assistant for {graph_id}"

        # 동일한 사용자, 그래프, 설정 조합이 이미 존재하는지 확인
        existing_stmt = select(AssistantORM).where(
            AssistantORM.user_id == user_identity,
            or_(
                (AssistantORM.graph_id == graph_id) & (AssistantORM.config == config),
                AssistantORM.assistant_id == assistant_id,
            ),
        )
        existing = await self.session.scalar(existing_stmt)

        if existing:
            if request.if_exists == "do_nothing":
                # 중복 시 기존 레코드 반환 (에러 없음)
                return to_pydantic(existing)
            else:  # error (기본값)
                raise HTTPException(409, f"Assistant '{assistant_id}' already exists")

        # 어시스턴트 레코드 생성
        metadata_dict = dict(request.metadata) if isinstance(request.metadata, dict) else {}

        assistant_orm = AssistantORM(
            assistant_id=assistant_id,
            name=name,
            description=request.description,
            config=config,
            context=context_dict,
            graph_id=graph_id,
            user_id=user_identity,
            metadata_dict=metadata_dict,
            version=1,
        )

        self.session.add(assistant_orm)
        await self.session.commit()
        await self.session.refresh(assistant_orm)

        # 초기 버전(버전 1) 이력 레코드 생성
        assistant_version_orm = AssistantVersionORM(
            assistant_id=assistant_id,
            version=1,
            graph_id=graph_id,
            config=config,
            context=context_dict,
            created_at=datetime.now(UTC),
            name=name,
            description=request.description,
            metadata_dict=metadata_dict,
        )
        self.session.add(assistant_version_orm)
        await self.session.commit()

        return to_pydantic(assistant_orm)

    async def list_assistants(self, user_identity: str) -> list[Assistant]:
        """사용자의 모든 어시스턴트 조회

        인증된 사용자가 소유한 모든 어시스턴트를 반환합니다.
        멀티테넌트 격리를 위해 user_id로 필터링합니다.

        Args:
            user_identity (str): 사용자 식별자

        Returns:
            list[Assistant]: 사용자의 어시스턴트 목록
        """
        # 사용자 소유 어시스턴트만 필터링
        stmt = select(AssistantORM).where(AssistantORM.user_id == user_identity)
        result = await self.session.scalars(stmt)
        user_assistants = [to_pydantic(a) for a in result.all()]
        return user_assistants

    async def search_assistants(self, request: AssistantSearchRequest, user_identity: str) -> list[Assistant]:
        """필터를 사용하여 어시스턴트 검색

        사용자의 어시스턴트를 name, description, graph_id, metadata 등으로 필터링하고
        페이지네이션을 적용하여 반환합니다.

        필터 조건:
        - name: 이름에 대한 부분 일치 검색 (대소문자 무시)
        - description: 설명에 대한 부분 일치 검색 (대소문자 무시)
        - graph_id: 그래프 ID 정확히 일치
        - metadata: JSONB 포함 연산자(@>) 사용하여 메타데이터 필터링

        Args:
            request (AssistantSearchRequest): 검색 필터 및 페이지네이션 파라미터
            user_identity (str): 사용자 식별자

        Returns:
            list[Assistant]: 필터링 및 페이지네이션된 어시스턴트 목록
        """
        # 사용자의 어시스턴트를 기반으로 시작
        stmt = select(AssistantORM).where(AssistantORM.user_id == user_identity)

        # 필터 적용
        if request.name:
            # 부분 일치 검색 (대소문자 무시)
            stmt = stmt.where(AssistantORM.name.ilike(f"%{request.name}%"))

        if request.description:
            # 부분 일치 검색 (대소문자 무시)
            stmt = stmt.where(AssistantORM.description.ilike(f"%{request.description}%"))

        if request.graph_id:
            # 그래프 ID 정확히 일치
            stmt = stmt.where(AssistantORM.graph_id == request.graph_id)

        if request.metadata:
            metadata_filter = (
                dict(request.metadata) if isinstance(request.metadata, dict) else request.metadata
            )
            if isinstance(metadata_filter, dict):
                stmt = stmt.where(AssistantORM.metadata_dict.op("@>")(metadata_filter))

        # 페이지네이션 적용
        offset = request.offset or 0
        limit = request.limit or 20
        stmt = stmt.offset(offset).limit(limit)

        result = await self.session.scalars(stmt)
        paginated_assistants = [to_pydantic(a) for a in result.all()]

        return paginated_assistants

    async def count_assistants(self, request: AssistantSearchRequest, user_identity: str) -> int:
        """필터 조건에 맞는 어시스턴트 총 개수 조회

        search_assistants()와 동일한 필터를 사용하여 전체 개수를 반환합니다.
        페이지네이션 UI에서 전체 페이지 수를 계산하는 데 사용됩니다.

        Args:
            request (AssistantSearchRequest): 검색 필터 (offset, limit 제외)
            user_identity (str): 사용자 식별자

        Returns:
            int: 필터 조건을 만족하는 어시스턴트 총 개수
        """
        stmt = select(func.count()).where(AssistantORM.user_id == user_identity)

        # search_assistants()와 동일한 필터 적용
        if request.name:
            stmt = stmt.where(AssistantORM.name.ilike(f"%{request.name}%"))

        if request.description:
            stmt = stmt.where(AssistantORM.description.ilike(f"%{request.description}%"))

        if request.graph_id:
            stmt = stmt.where(AssistantORM.graph_id == request.graph_id)

        if request.metadata:
            metadata_filter = (
                dict(request.metadata) if isinstance(request.metadata, dict) else request.metadata
            )
            if isinstance(metadata_filter, dict):
                stmt = stmt.where(AssistantORM.metadata_dict.op("@>")(metadata_filter))

        total = await self.session.scalar(stmt)
        return total or 0

    async def get_assistant(self, assistant_id: str, user_identity: str) -> Assistant:
        """ID로 특정 어시스턴트 조회

        사용자가 소유하거나 시스템이 제공하는 어시스턴트를 조회합니다.
        시스템 어시스턴트는 open_langgraph.json에 정의된 그래프의 기본 어시스턴트입니다.

        Args:
            assistant_id (str): 어시스턴트 고유 식별자
            user_identity (str): 사용자 식별자

        Returns:
            Assistant: 조회된 어시스턴트

        Raises:
            HTTPException(404): 어시스턴트를 찾을 수 없음
        """
        stmt = select(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            or_(
                # 사용자 소유 또는 시스템 제공 어시스턴트
                AssistantORM.user_id == user_identity,
                AssistantORM.user_id == "system",
            ),
        )
        assistant = await self.session.scalar(stmt)

        if not assistant:
            raise HTTPException(404, f"Assistant '{assistant_id}' not found")

        return to_pydantic(assistant)

    async def update_assistant(
        self, assistant_id: str, request: AssistantUpdate, user_identity: str
    ) -> Assistant:
        """어시스턴트 업데이트 및 버전 이력 생성

        어시스턴트를 업데이트하고 이전 버전을 assistant_versions 테이블에 보관합니다.
        버전 번호는 자동으로 증가하며, 사용자는 나중에 특정 버전으로 롤백할 수 있습니다.

        동작 흐름:
        1. config와 context 동기화
        2. 기존 어시스턴트 조회
        3. 최대 버전 번호 조회 후 +1
        4. 새로운 버전 이력 레코드 생성
        5. 어시스턴트 메인 레코드 업데이트

        Args:
            assistant_id (str): 어시스턴트 고유 식별자
            request (AssistantUpdate): 업데이트할 필드
            user_identity (str): 사용자 식별자

        Returns:
            Assistant: 업데이트된 어시스턴트

        Raises:
            HTTPException(400): config와 context를 동시에 지정한 경우
            HTTPException(404): 어시스턴트를 찾을 수 없음
        """
        metadata_dict = dict(request.metadata) if isinstance(request.metadata, dict) else {}
        config: dict[str, Any] = dict(request.config) if isinstance(request.config, dict) else {}
        context_dict: dict[str, Any] | None = (
            dict(request.context) if isinstance(request.context, dict) else None
        )

        configurable_section = config.get("configurable")
        if isinstance(configurable_section, dict) and context_dict:
            raise HTTPException(
                status_code=400,
                detail="Cannot specify both configurable and context. Use only one.",
            )

        # config와 context를 서로 동기화하여 일관성 유지
        if isinstance(configurable_section, dict):
            context_dict = configurable_section
        elif context_dict is not None:
            config["configurable"] = context_dict

        stmt = select(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            AssistantORM.user_id == user_identity,
        )
        assistant = await self.session.scalar(stmt)
        if not assistant:
            raise HTTPException(404, f"Assistant '{assistant_id}' not found")

        now = datetime.now(UTC)
        # 최대 버전 번호 조회
        version_stmt = select(func.max(AssistantVersionORM.version)).where(
            AssistantVersionORM.assistant_id == assistant_id
        )
        max_version = await self.session.scalar(version_stmt)
        new_version = (max_version or 1) + 1 if max_version is not None else 1

        # 새로운 버전 정보 구성
        new_version_details = {
            "assistant_id": assistant_id,
            "version": new_version,
            "graph_id": request.graph_id or assistant.graph_id,
            "config": config,
            "context": context_dict,
            "created_at": now,
            "name": request.name or assistant.name,
            "description": request.description or assistant.description,
            "metadata_dict": metadata_dict,
        }

        # 새로운 버전 이력 레코드 생성
        assistant_version_orm = AssistantVersionORM(**new_version_details)
        self.session.add(assistant_version_orm)
        await self.session.commit()

        # 어시스턴트 메인 레코드 업데이트
        assistant_update = (
            update(AssistantORM)
            .where(
                AssistantORM.assistant_id == assistant_id,
                AssistantORM.user_id == user_identity,
            )
            .values(
                name=new_version_details["name"],
                description=new_version_details["description"],
                graph_id=new_version_details["graph_id"],
                config=new_version_details["config"],
                context=new_version_details["context"],
                version=new_version,
                updated_at=now,
            )
        )
        await self.session.execute(assistant_update)
        await self.session.commit()
        updated_assistant = await self.session.scalar(stmt)
        if updated_assistant is None:
            raise HTTPException(500, f"Assistant '{assistant_id}' was updated but could not be reloaded")
        return to_pydantic(updated_assistant)

    async def delete_assistant(self, assistant_id: str, user_identity: str) -> dict:
        """어시스턴트 삭제

        어시스턴트를 영구적으로 삭제합니다.
        CASCADE 설정으로 인해 연관된 버전 이력, 실행, 이벤트도 함께 삭제됩니다.

        Args:
            assistant_id (str): 어시스턴트 고유 식별자
            user_identity (str): 사용자 식별자

        Returns:
            dict: 삭제 완료 상태 {"status": "deleted"}

        Raises:
            HTTPException(404): 어시스턴트를 찾을 수 없음
        """
        stmt = select(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            AssistantORM.user_id == user_identity,
        )
        assistant = await self.session.scalar(stmt)

        if not assistant:
            raise HTTPException(404, f"Assistant '{assistant_id}' not found")

        # CASCADE DELETE로 버전 이력, 실행, 이벤트도 함께 삭제됨
        await self.session.delete(assistant)
        await self.session.commit()

        return {"status": "deleted"}

    async def set_assistant_latest(self, assistant_id: str, version: int, user_identity: str) -> Assistant:
        """특정 버전을 최신 버전으로 설정 (롤백)

        assistant_versions 테이블에 저장된 과거 버전을 어시스턴트의 최신 버전으로 설정합니다.
        이 기능을 통해 사용자는 이전 설정이나 그래프로 롤백할 수 있습니다.

        동작 흐름:
        1. 어시스턴트 존재 여부 확인
        2. 요청된 버전 존재 여부 확인
        3. 어시스턴트 메인 레코드를 해당 버전의 내용으로 업데이트

        Args:
            assistant_id (str): 어시스턴트 고유 식별자
            version (int): 복원할 버전 번호
            user_identity (str): 사용자 식별자

        Returns:
            Assistant: 버전이 복원된 어시스턴트

        Raises:
            HTTPException(404): 어시스턴트 또는 버전을 찾을 수 없음
        """
        stmt = select(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            AssistantORM.user_id == user_identity,
        )
        assistant = await self.session.scalar(stmt)
        if not assistant:
            raise HTTPException(404, f"Assistant '{assistant_id}' not found")

        # 요청된 버전 조회
        version_stmt = select(AssistantVersionORM).where(
            AssistantVersionORM.assistant_id == assistant_id,
            AssistantVersionORM.version == version,
        )
        assistant_version = await self.session.scalar(version_stmt)
        if not assistant_version:
            raise HTTPException(404, f"Version '{version}' for Assistant '{assistant_id}' not found")

        # 어시스턴트를 해당 버전의 내용으로 업데이트
        assistant_update = (
            update(AssistantORM)
            .where(
                AssistantORM.assistant_id == assistant_id,
                AssistantORM.user_id == user_identity,
            )
            .values(
                name=assistant_version.name,
                description=assistant_version.description,
                config=assistant_version.config,
                context=assistant_version.context,
                graph_id=assistant_version.graph_id,
                version=version,
                updated_at=datetime.now(UTC),
            )
        )
        await self.session.execute(assistant_update)
        await self.session.commit()
        updated_assistant = await self.session.scalar(stmt)
        if updated_assistant is None:
            raise HTTPException(
                500,
                f"Assistant '{assistant_id}' was updated but could not be reloaded",
            )
        return to_pydantic(updated_assistant)

    async def list_assistant_versions(self, assistant_id: str, user_identity: str) -> list[Assistant]:
        """어시스턴트의 모든 버전 이력 조회

        assistant_versions 테이블에 저장된 모든 버전을 최신순으로 반환합니다.
        각 버전은 과거의 설정, 그래프, 메타데이터를 보존하고 있습니다.

        Args:
            assistant_id (str): 어시스턴트 고유 식별자
            user_identity (str): 사용자 식별자

        Returns:
            list[Assistant]: 버전 목록 (최신순 정렬)

        Raises:
            HTTPException(404): 어시스턴트 또는 버전이 없음
        """
        stmt = select(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            AssistantORM.user_id == user_identity,
        )
        assistant = await self.session.scalar(stmt)
        if not assistant:
            raise HTTPException(404, f"Assistant '{assistant_id}' not found")

        # 모든 버전을 최신순으로 조회
        versions_stmt = (
            select(AssistantVersionORM)
            .where(AssistantVersionORM.assistant_id == assistant_id)
            .order_by(AssistantVersionORM.version.desc())
        )
        result = await self.session.scalars(versions_stmt)
        versions = result.all()

        if not versions:
            raise HTTPException(404, f"No versions found for Assistant '{assistant_id}'")

        # AssistantVersionORM → Pydantic Assistant 변환
        version_list = []
        for v in versions:
            version_list.append(
                Assistant(
                    assistant_id=assistant_id,
                    name=v.name or assistant.name,
                    description=v.description,
                    config=v.config or {},
                    context=v.context or {},
                    graph_id=v.graph_id,
                    user_id=user_identity,
                    version=v.version,
                    created_at=v.created_at,
                    updated_at=v.created_at,
                    metadata_dict=v.metadata_dict or {},
                )
            )

        return version_list

    async def get_assistant_schemas(self, assistant_id: str, user_identity: str) -> dict:
        """어시스턴트의 그래프 스키마 조회

        어시스턴트가 사용하는 LangGraph 그래프의 모든 스키마를 추출하여 반환합니다.
        클라이언트는 이 정보를 통해 입력 형식, 출력 형식, 상태 구조를 파악할 수 있습니다.

        반환 스키마:
        - input_schema: 그래프 입력 JSON 스키마
        - output_schema: 그래프 출력 JSON 스키마
        - state_schema: 그래프 상태(채널) JSON 스키마
        - config_schema: configurable 설정 JSON 스키마
        - context_schema: 런타임 컨텍스트 JSON 스키마

        Args:
            assistant_id (str): 어시스턴트 고유 식별자
            user_identity (str): 사용자 식별자

        Returns:
            dict: graph_id와 5가지 스키마를 포함한 딕셔너리

        Raises:
            HTTPException(404): 어시스턴트를 찾을 수 없음
            HTTPException(400): 스키마 추출 실패
        """
        stmt = select(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            or_(AssistantORM.user_id == user_identity, AssistantORM.user_id == "system"),
        )
        assistant = await self.session.scalar(stmt)

        if not assistant:
            raise HTTPException(404, f"Assistant '{assistant_id}' not found")

        try:
            graph = cast(
                "CompiledGraph",
                await self.langgraph_service.get_graph(assistant.graph_id),
            )
            compiled_graph = cast("CompiledGraph", graph)
            schemas = _extract_graph_schemas(compiled_graph)

            return {"graph_id": assistant.graph_id, **schemas}

        except Exception as e:
            raise HTTPException(400, f"Failed to extract schemas: {str(e)}") from e

    async def get_assistant_graph(self, assistant_id: str, xray: bool | int, user_identity: str) -> dict:
        """그래프 구조 조회 (시각화용)

        어시스턴트의 LangGraph 그래프 구조를 JSON 형식으로 반환합니다.
        노드, 엣지, 조건부 분기 등 그래프의 전체 구조를 시각화할 수 있습니다.

        xray 파라미터:
        - False (기본값): 최상위 그래프 구조만 반환
        - True: 모든 서브그래프까지 완전히 펼침
        - int (양수): 특정 깊이만큼만 펼침

        Args:
            assistant_id (str): 어시스턴트 고유 식별자
            xray (bool | int): 서브그래프 펼침 옵션
            user_identity (str): 사용자 식별자

        Returns:
            dict: 그래프 구조 JSON (nodes, edges 포함)

        Raises:
            HTTPException(404): 어시스턴트를 찾을 수 없음
            HTTPException(422): xray 값이 유효하지 않거나 그래프가 시각화를 지원하지 않음
            HTTPException(400): 그래프 조회 실패
        """
        stmt = select(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            or_(AssistantORM.user_id == user_identity, AssistantORM.user_id == "system"),
        )
        assistant = await self.session.scalar(stmt)

        if not assistant:
            raise HTTPException(404, f"Assistant '{assistant_id}' not found")

        try:
            graph = await self.langgraph_service.get_graph(assistant.graph_id)

            # xray가 정수인 경우 (boolean이 아님) 양수 검증
            if isinstance(xray, int) and not isinstance(xray, bool) and xray <= 0:
                raise HTTPException(422, detail="Invalid xray value")

            try:
                # LangGraph의 aget_graph()로 시각화 가능한 그래프 구조 추출
                drawable_graph = await graph.aget_graph(xray=xray)
                json_graph = drawable_graph.to_json()

                # 노드 데이터에서 불필요한 id 필드 제거
                for node in json_graph.get("nodes", []):
                    if (data := node.get("data")) and isinstance(data, dict):
                        data.pop("id", None)

                return json_graph
            except NotImplementedError as e:
                raise HTTPException(422, detail="The graph does not support visualization") from e

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Failed to get graph: {str(e)}") from e

    async def get_assistant_subgraphs(
        self,
        assistant_id: str,
        namespace: str | None,
        recurse: bool,
        user_identity: str,
    ) -> dict:
        """어시스턴트의 서브그래프 조회

        LangGraph 그래프 내에 포함된 서브그래프들의 스키마를 추출합니다.
        서브그래프는 복잡한 그래프를 모듈화하기 위해 사용되는 중첩된 그래프입니다.

        Args:
            assistant_id (str): 어시스턴트 고유 식별자
            namespace (str | None): 특정 네임스페이스의 서브그래프만 조회 (None이면 전체)
            recurse (bool): 중첩된 서브그래프도 재귀적으로 조회할지 여부
            user_identity (str): 사용자 식별자

        Returns:
            dict: {namespace: schemas} 형태의 서브그래프 스키마 딕셔너리

        Raises:
            HTTPException(404): 어시스턴트를 찾을 수 없음
            HTTPException(422): 그래프가 서브그래프를 지원하지 않음
            HTTPException(400): 서브그래프 조회 실패
        """
        stmt = select(AssistantORM).where(
            AssistantORM.assistant_id == assistant_id,
            or_(AssistantORM.user_id == user_identity, AssistantORM.user_id == "system"),
        )
        assistant = await self.session.scalar(stmt)

        if not assistant:
            raise HTTPException(404, f"Assistant '{assistant_id}' not found")

        try:
            graph = cast(
                "CompiledGraph",
                await self.langgraph_service.get_graph(assistant.graph_id),
            )

            try:
                # 서브그래프 순회하며 각각의 스키마 추출
                subgraphs = {
                    ns: _extract_graph_schemas(cast("CompiledGraph", subgraph))
                    async for ns, subgraph in graph.aget_subgraphs(namespace=namespace, recurse=recurse)
                }
                return subgraphs
            except NotImplementedError as e:
                raise HTTPException(422, detail="The graph does not support subgraphs") from e

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Failed to get subgraphs: {str(e)}") from e


def get_assistant_service(
    session: AsyncSession = Depends(get_session),
    langgraph_service: LangGraphService = Depends(get_langgraph_service),
) -> AssistantService:
    """AssistantService 의존성 주입 헬퍼

    FastAPI의 Depends()에서 사용되어 AssistantService 인스턴스를 생성합니다.
    필요한 의존성(세션, LangGraph 서비스)을 자동으로 주입받습니다.

    사용 예:
        @router.post("/assistants")
        async def create(
            request: AssistantCreate,
            service: AssistantService = Depends(get_assistant_service),
        ):
            return await service.create_assistant(request, user.identity)

    Args:
        session (AsyncSession): 데이터베이스 세션 (자동 주입)
        langgraph_service (LangGraphService): LangGraph 서비스 (자동 주입)

    Returns:
        AssistantService: AssistantService 인스턴스
    """
    return AssistantService(session, langgraph_service)
