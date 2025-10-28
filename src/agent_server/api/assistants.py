"""Agent Protocol용 어시스턴트 엔드포인트

이 API는 비즈니스 로직을 서비스 계층(assistant_service.py)으로 분리한
계층화된 아키텍처 패턴을 따릅니다. 이 패턴은 어시스턴트 API에 최초로 적용되었으며,
향후 다른 모든 API(runs, threads 등)도 동일한 패턴으로 리팩토링할 예정입니다.

아키텍처:
• API 계층(이 파일): 얇은 FastAPI 라우트 핸들러, 요청/응답 처리
• 서비스 계층(assistant_service.py): 비즈니스 로직, 검증, 오케스트레이션

주요 구성 요소:
• create_assistant - 어시스턴트 생성 (중복 검사 포함)
• list_assistants - 사용자의 어시스턴트 목록 조회
• search_assistants - 필터링 및 페이지네이션 검색
• get_assistant - 특정 어시스턴트 조회
• update_assistant - 어시스턴트 업데이트 (버전 이력 생성)
• delete_assistant - 어시스턴트 삭제
• set_assistant_latest - 특정 버전으로 롤백
• list_assistant_versions - 버전 이력 조회
• get_assistant_schemas - 그래프 스키마 추출 (5가지 타입)
• get_assistant_graph - 그래프 구조 조회 (시각화용)
• get_assistant_subgraphs - 서브그래프 조회

사용 예:
    from fastapi import FastAPI
    from .api.assistants import router

    app = FastAPI()
    app.include_router(router)

    # POST /assistants - 어시스턴트 생성
    # GET /assistants - 어시스턴트 목록 조회
    # GET /assistants/{assistant_id} - 특정 어시스턴트 조회
    # PATCH /assistants/{assistant_id} - 어시스턴트 업데이트
    # DELETE /assistants/{assistant_id} - 어시스턴트 삭제
"""

from typing import Any

from fastapi import APIRouter, Body, Depends

from ..core.auth_deps import get_current_user
from ..models import (
    Assistant,
    AssistantCreate,
    AssistantList,
    AssistantSearchRequest,
    AssistantUpdate,
    User,
)
from ..services.assistant_service import AssistantService, get_assistant_service

router = APIRouter()


@router.post("/assistants", response_model=Assistant)
async def create_assistant(
    request: AssistantCreate,
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> Assistant:
    """새로운 어시스턴트 생성

    open_langgraph.json에 정의된 그래프 ID를 기반으로 어시스턴트를 생성합니다.
    중복 검사를 수행하며, if_exists 정책에 따라 동작합니다.

    동작 흐름:
    1. 요청 데이터 검증 (graph_id, config, context)
    2. 그래프 존재 및 로드 가능 여부 확인
    3. 중복 어시스턴트 검사 (user_id + graph_id + config 조합)
    4. 어시스턴트 레코드 생성
    5. 버전 1 이력 레코드 생성

    Args:
        request (AssistantCreate): 어시스턴트 생성 요청 데이터
            - graph_id: open_langgraph.json에 정의된 그래프 ID (필수)
            - name: 어시스턴트 이름 (선택, 기본값: "Assistant for {graph_id}")
            - config: LangGraph 설정 (선택, 기본값: {})
            - context: 런타임 컨텍스트 (선택, LangGraph 0.6.0+에서 configurable 대체)
            - metadata: 사용자 정의 메타데이터 (선택)
            - if_exists: 중복 정책 ("error" 또는 "do_nothing")
        user (User): 인증된 사용자 (의존성 주입)
        service (AssistantService): 어시스턴트 서비스 (의존성 주입)

    Returns:
        Assistant: 생성된 어시스턴트 (assistant_id, version=1 포함)

    Raises:
        HTTPException(400): 그래프가 존재하지 않거나 로드 실패
        HTTPException(400): config와 context를 동시에 지정한 경우
        HTTPException(409): 동일한 어시스턴트가 이미 존재 (if_exists="error")
    """
    return await service.create_assistant(request, user.identity)


@router.get("/assistants", response_model=AssistantList)
async def list_assistants(
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> AssistantList:
    """사용자의 모든 어시스턴트 목록 조회

    인증된 사용자가 소유한 모든 어시스턴트를 반환합니다.
    멀티테넌트 격리를 위해 user_id로 자동 필터링됩니다.

    Args:
        user (User): 인증된 사용자 (의존성 주입)
        service (AssistantService): 어시스턴트 서비스 (의존성 주입)

    Returns:
        AssistantList: 어시스턴트 목록 및 총 개수
            - assistants: 어시스턴트 배열
            - total: 전체 개수
    """
    assistants = await service.list_assistants(user.identity)
    return AssistantList(assistants=assistants, total=len(assistants))


@router.post("/assistants/search", response_model=list[Assistant])
async def search_assistants(
    request: AssistantSearchRequest,
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> list[Assistant]:
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
            - name: 이름 필터 (부분 일치)
            - description: 설명 필터 (부분 일치)
            - graph_id: 그래프 ID 필터 (정확히 일치)
            - metadata: 메타데이터 필터 (JSONB @> 연산)
            - offset: 시작 위치 (기본값: 0)
            - limit: 최대 개수 (기본값: 20)
        user (User): 인증된 사용자 (의존성 주입)
        service (AssistantService): 어시스턴트 서비스 (의존성 주입)

    Returns:
        list[Assistant]: 필터링 및 페이지네이션된 어시스턴트 목록
    """
    return await service.search_assistants(request, user.identity)


@router.post("/assistants/count", response_model=int)
async def count_assistants(
    request: AssistantSearchRequest,
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> int:
    """필터 조건에 맞는 어시스턴트 총 개수 조회

    search_assistants()와 동일한 필터를 사용하여 전체 개수를 반환합니다.
    페이지네이션 UI에서 전체 페이지 수를 계산하는 데 사용됩니다.

    Args:
        request (AssistantSearchRequest): 검색 필터 (offset, limit 제외)
            - name: 이름 필터 (부분 일치)
            - description: 설명 필터 (부분 일치)
            - graph_id: 그래프 ID 필터 (정확히 일치)
            - metadata: 메타데이터 필터 (JSONB @> 연산)
        user (User): 인증된 사용자 (의존성 주입)
        service (AssistantService): 어시스턴트 서비스 (의존성 주입)

    Returns:
        int: 필터 조건을 만족하는 어시스턴트 총 개수
    """
    return await service.count_assistants(request, user.identity)


@router.get("/assistants/{assistant_id}", response_model=Assistant)
async def get_assistant(
    assistant_id: str,
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> Assistant:
    """ID로 특정 어시스턴트 조회

    사용자가 소유하거나 시스템이 제공하는 어시스턴트를 조회합니다.
    시스템 어시스턴트는 open_langgraph.json에 정의된 그래프의 기본 어시스턴트입니다.

    Args:
        assistant_id (str): 어시스턴트 고유 식별자
        user (User): 인증된 사용자 (의존성 주입)
        service (AssistantService): 어시스턴트 서비스 (의존성 주입)

    Returns:
        Assistant: 조회된 어시스턴트

    Raises:
        HTTPException(404): 어시스턴트를 찾을 수 없음
    """
    return await service.get_assistant(assistant_id, user.identity)


@router.patch("/assistants/{assistant_id}", response_model=Assistant)
async def update_assistant(
    assistant_id: str,
    request: AssistantUpdate,
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
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
            - name: 어시스턴트 이름 (선택)
            - description: 설명 (선택)
            - graph_id: 그래프 ID 변경 (선택)
            - config: LangGraph 설정 (선택)
            - context: 런타임 컨텍스트 (선택)
            - metadata: 메타데이터 (선택)
        user (User): 인증된 사용자 (의존성 주입)
        service (AssistantService): 어시스턴트 서비스 (의존성 주입)

    Returns:
        Assistant: 업데이트된 어시스턴트 (새로운 버전 번호 포함)

    Raises:
        HTTPException(400): config와 context를 동시에 지정한 경우
        HTTPException(404): 어시스턴트를 찾을 수 없음
    """
    return await service.update_assistant(assistant_id, request, user.identity)


@router.delete("/assistants/{assistant_id}")
async def delete_assistant(
    assistant_id: str,
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> dict[str, str]:
    """어시스턴트 삭제

    어시스턴트를 영구적으로 삭제합니다.
    CASCADE 설정으로 인해 연관된 버전 이력, 실행, 이벤트도 함께 삭제됩니다.

    Args:
        assistant_id (str): 어시스턴트 고유 식별자
        user (User): 인증된 사용자 (의존성 주입)
        service (AssistantService): 어시스턴트 서비스 (의존성 주입)

    Returns:
        dict: 삭제 완료 상태 {"status": "deleted"}

    Raises:
        HTTPException(404): 어시스턴트를 찾을 수 없음
    """
    return await service.delete_assistant(assistant_id, user.identity)


@router.post("/assistants/{assistant_id}/latest", response_model=Assistant)
async def set_assistant_latest(
    assistant_id: str,
    version: int = Body(..., embed=True, description="The version number to set as latest"),
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> Assistant:
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
        user (User): 인증된 사용자 (의존성 주입)
        service (AssistantService): 어시스턴트 서비스 (의존성 주입)

    Returns:
        Assistant: 버전이 복원된 어시스턴트

    Raises:
        HTTPException(404): 어시스턴트 또는 버전을 찾을 수 없음
    """
    return await service.set_assistant_latest(assistant_id, version, user.identity)


@router.post("/assistants/{assistant_id}/versions", response_model=list[Assistant])
async def list_assistant_versions(
    assistant_id: str,
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> list[Assistant]:
    """어시스턴트의 모든 버전 이력 조회

    assistant_versions 테이블에 저장된 모든 버전을 최신순으로 반환합니다.
    각 버전은 과거의 설정, 그래프, 메타데이터를 보존하고 있습니다.

    Args:
        assistant_id (str): 어시스턴트 고유 식별자
        user (User): 인증된 사용자 (의존성 주입)
        service (AssistantService): 어시스턴트 서비스 (의존성 주입)

    Returns:
        list[Assistant]: 버전 목록 (최신순 정렬)

    Raises:
        HTTPException(404): 어시스턴트 또는 버전이 없음
    """
    return await service.list_assistant_versions(assistant_id, user.identity)


@router.get("/assistants/{assistant_id}/schemas")
async def get_assistant_schemas(
    assistant_id: str,
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> dict[str, Any]:
    """어시스턴트의 그래프 스키마 조회 (5가지 타입)

    어시스턴트가 사용하는 LangGraph 그래프의 모든 스키마를 추출하여 반환합니다.
    클라이언트는 이 정보를 통해 입력 형식, 출력 형식, 상태 구조를 파악할 수 있습니다.

    반환 스키마:
    1. input_schema: 그래프 입력 JSON 스키마
    2. output_schema: 그래프 출력 JSON 스키마
    3. state_schema: 그래프 상태(채널) JSON 스키마
    4. config_schema: configurable 설정 JSON 스키마
    5. context_schema: 런타임 컨텍스트 JSON 스키마

    Args:
        assistant_id (str): 어시스턴트 고유 식별자
        user (User): 인증된 사용자 (의존성 주입)
        service (AssistantService): 어시스턴트 서비스 (의존성 주입)

    Returns:
        dict: graph_id와 5가지 스키마를 포함한 딕셔너리
            - graph_id: 그래프 고유 식별자
            - input_schema: 입력 스키마
            - output_schema: 출력 스키마
            - state_schema: 상태 스키마
            - config_schema: 설정 스키마
            - context_schema: 컨텍스트 스키마

    Raises:
        HTTPException(404): 어시스턴트를 찾을 수 없음
        HTTPException(400): 스키마 추출 실패
    """
    return await service.get_assistant_schemas(assistant_id, user.identity)


@router.get("/assistants/{assistant_id}/graph")
async def get_assistant_graph(
    assistant_id: str,
    xray: bool | int | None = None,
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> dict[str, Any]:
    """그래프 구조 조회 (시각화용)

    어시스턴트의 LangGraph 그래프 구조를 JSON 형식으로 반환합니다.
    노드, 엣지, 조건부 분기 등 그래프의 전체 구조를 시각화할 수 있습니다.

    xray 파라미터:
    - False (기본값): 최상위 그래프 구조만 반환
    - True: 모든 서브그래프까지 완전히 펼침
    - int (양수): 특정 깊이만큼만 펼침

    Args:
        assistant_id (str): 어시스턴트 고유 식별자
        xray (bool | int | None): 서브그래프 펼침 옵션 (기본값: False)
        user (User): 인증된 사용자 (의존성 주입)
        service (AssistantService): 어시스턴트 서비스 (의존성 주입)

    Returns:
        dict: 그래프 구조 JSON (nodes, edges 포함)

    Raises:
        HTTPException(404): 어시스턴트를 찾을 수 없음
        HTTPException(422): xray 값이 유효하지 않거나 그래프가 시각화를 지원하지 않음
        HTTPException(400): 그래프 조회 실패
    """
    # xray가 None이면 기본값 False로 설정 (최상위 그래프만 반환)
    xray_value = xray if xray is not None else False
    return await service.get_assistant_graph(assistant_id, xray_value, user.identity)


@router.get("/assistants/{assistant_id}/subgraphs")
async def get_assistant_subgraphs(
    assistant_id: str,
    recurse: bool = False,
    namespace: str | None = None,
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
) -> dict[str, Any]:
    """어시스턴트의 서브그래프 조회

    LangGraph 그래프 내에 포함된 서브그래프들의 스키마를 추출합니다.
    서브그래프는 복잡한 그래프를 모듈화하기 위해 사용되는 중첩된 그래프입니다.

    Args:
        assistant_id (str): 어시스턴트 고유 식별자
        recurse (bool): 중첩된 서브그래프도 재귀적으로 조회할지 여부 (기본값: False)
        namespace (str | None): 특정 네임스페이스의 서브그래프만 조회 (None이면 전체)
        user (User): 인증된 사용자 (의존성 주입)
        service (AssistantService): 어시스턴트 서비스 (의존성 주입)

    Returns:
        dict: {namespace: schemas} 형태의 서브그래프 스키마 딕셔너리
            각 스키마는 input_schema, output_schema, state_schema,
            config_schema, context_schema를 포함합니다.

    Raises:
        HTTPException(404): 어시스턴트를 찾을 수 없음
        HTTPException(422): 그래프가 서브그래프를 지원하지 않음
        HTTPException(400): 서브그래프 조회 실패
    """
    return await service.get_assistant_subgraphs(assistant_id, namespace, recurse, user.identity)
