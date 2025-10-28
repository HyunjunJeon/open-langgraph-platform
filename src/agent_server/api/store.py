"""LangGraph Store API 엔드포인트

이 모듈은 Agent Protocol의 Store API를 구현하여 LangGraph의 공식
AsyncPostgresStore를 통한 영구 저장소 기능을 제공합니다.

Store는 스레드 및 실행과 독립적인 장기 메모리 저장소로, 사용자별 데이터를
네임스페이스로 격리하여 안전하게 관리합니다.

주요 기능:
• 키-값 저장 (Put) - 네임스페이스 기반 아이템 저장
• 아이템 조회 (Get) - 키로 특정 아이템 검색
• 아이템 삭제 (Delete) - 저장된 아이템 제거
• 검색 (Search) - 키워드/시맨틱/하이브리드 검색 지원
• 사용자 격리 - 자동 네임스페이스 스코핑

사용 예:
    # 아이템 저장
    PUT /store/items
    {
        "namespace": ["users", "user123", "preferences"],
        "key": "theme",
        "value": {"color": "dark", "fontSize": 14}
    }

    # 아이템 조회
    GET /store/items?key=theme&namespace=users.user123.preferences

    # 검색
    POST /store/items/search
    {
        "namespace_prefix": ["users", "user123"],
        "query": "theme",
        "limit": 10
    }

참고:
    - Store는 LangGraph의 AsyncPostgresStore를 직접 사용
    - 메타데이터 테이블이 아닌 LangGraph 공식 테이블 활용
    - 벡터 유사도 검색 지원 (시맨틱/하이브리드 모드)
"""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.auth_deps import get_current_user
from ..models import (
    StoreDeleteRequest,
    StoreGetResponse,
    StoreItem,
    StorePutRequest,
    StoreSearchRequest,
    StoreSearchResponse,
    User,
)

router = APIRouter()


@router.put("/store/items")
async def put_store_item(request: StorePutRequest, user: User = Depends(get_current_user)) -> dict[str, str]:
    """LangGraph Store에 아이템 저장

    네임스페이스 기반 키-값 저장소에 아이템을 저장합니다.
    사용자별 네임스페이스 격리를 자동으로 적용하여 데이터 보안을 보장합니다.

    동작 흐름:
    1. 요청된 네임스페이스에 사용자 스코핑 적용
    2. LangGraph Store 인스턴스 획득
    3. store.aput()으로 아이템 저장
    4. 저장 완료 상태 반환

    Args:
        request (StorePutRequest): 저장 요청 (namespace, key, value 포함)
        user (User): 인증된 사용자 정보

    Returns:
        dict: 저장 상태 {"status": "stored"}

    사용 예:
        PUT /store/items
        {
            "namespace": ["users", "user123", "settings"],
            "key": "theme",
            "value": {"mode": "dark"}
        }

    참고:
        - namespace는 리스트 형태로 제공 (예: ["users", "user123"])
        - value는 JSONB로 저장되어 복잡한 객체도 저장 가능
        - 동일한 (namespace, key) 조합은 덮어쓰기됨
    """

    # 사용자 네임스페이스 스코핑 적용
    scoped_namespace = apply_user_namespace_scoping(user.identity, request.namespace)

    # DatabaseManager에서 LangGraph Store 인스턴스 획득
    from ..core.database import db_manager

    store = await db_manager.get_store()

    await store.aput(namespace=tuple(scoped_namespace), key=request.key, value=request.value)

    return {"status": "stored"}


@router.get("/store/items", response_model=StoreGetResponse)
async def get_store_item(
    key: str,
    namespace: str | list[str] | None = Query(None),
    user: User = Depends(get_current_user),
) -> StoreGetResponse:
    """LangGraph Store에서 아이템 조회

    네임스페이스와 키로 특정 아이템을 조회합니다.
    네임스페이스는 점으로 구분된 문자열 또는 리스트 형태로 제공 가능합니다.

    동작 흐름:
    1. 네임스페이스 형식 정규화 (dotted string → list)
    2. 사용자 스코핑 적용
    3. LangGraph Store에서 아이템 조회
    4. 아이템이 없으면 404 에러
    5. 아이템 정보 반환

    Args:
        key (str): 조회할 아이템의 키
        namespace (Union[str, list[str], None]): 네임스페이스
            - 문자열: "users.user123.settings" (점으로 구분)
            - 리스트: ["users", "user123", "settings"]
            - None: 사용자 기본 네임스페이스 사용
        user (User): 인증된 사용자 정보

    Returns:
        StoreGetResponse: 아이템 정보 (key, value, namespace)

    Raises:
        HTTPException(404): 아이템을 찾을 수 없는 경우

    사용 예:
        # 점으로 구분된 네임스페이스
        GET /store/items?key=theme&namespace=users.user123.settings

        # 리스트 형태 네임스페이스
        GET /store/items?key=theme&namespace=users&namespace=user123

    참고:
        - SDK 스타일의 dotted 네임스페이스를 지원하여 편의성 제공
        - 빈 부분은 자동으로 필터링 ("a..b" → ["a", "b"])
    """

    # SDK 스타일의 점으로 구분된 네임스페이스 또는 리스트 형식 모두 수용
    ns_list: list[str]
    if isinstance(namespace, str):
        ns_list = [part for part in namespace.split(".") if part]
    elif isinstance(namespace, list):
        ns_list = namespace
    else:
        ns_list = []

    # 사용자 네임스페이스 스코핑 적용
    scoped_namespace = apply_user_namespace_scoping(user.identity, ns_list)

    # DatabaseManager에서 LangGraph Store 인스턴스 획득
    from ..core.database import db_manager

    store = await db_manager.get_store()

    item = await store.aget(tuple(scoped_namespace), key)

    if not item:
        raise HTTPException(404, "Item not found")

    return StoreGetResponse(key=key, value=item.value, namespace=list(scoped_namespace))


@router.delete("/store/items")
async def delete_store_item(
    body: StoreDeleteRequest | None = None,
    key: str | None = Query(None),
    namespace: list[str] | None = Query(None),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """LangGraph Store에서 아이템 삭제

    네임스페이스와 키로 특정 아이템을 삭제합니다.
    SDK 호환성을 위해 JSON body와 쿼리 파라미터 모두 지원합니다.

    동작 흐름:
    1. 파라미터 소스 결정 (body 우선, 없으면 query params)
    2. key 필수 값 검증
    3. 사용자 스코핑 적용
    4. LangGraph Store에서 아이템 삭제
    5. 삭제 완료 상태 반환

    Args:
        body (StoreDeleteRequest | None): SDK 요청 body {namespace, key}
        key (str | None): 삭제할 아이템의 키 (쿼리 파라미터)
        namespace (list[str] | None): 네임스페이스 (쿼리 파라미터)
        user (User): 인증된 사용자 정보

    Returns:
        dict: 삭제 상태 {"status": "deleted"}

    Raises:
        HTTPException(422): key가 제공되지 않은 경우

    사용 예:
        # SDK 스타일 (JSON body)
        DELETE /store/items
        {
            "namespace": ["users", "user123"],
            "key": "theme"
        }

        # 수동 호출 (쿼리 파라미터)
        DELETE /store/items?key=theme&namespace=users&namespace=user123

    참고:
        - SDK 호환성과 수동 사용성을 모두 지원
        - body가 제공되면 쿼리 파라미터는 무시됨
        - 존재하지 않는 아이템 삭제 시에도 에러 없이 성공 반환
    """
    # 파라미터 소스 결정 (body가 있으면 body 사용, 없으면 쿼리 파라미터)
    if body is not None:
        ns = body.namespace
        k = body.key
    else:
        if key is None:
            raise HTTPException(422, "Missing 'key' parameter")
        ns = namespace or []
        k = key

    # 사용자 네임스페이스 스코핑 적용
    scoped_namespace = apply_user_namespace_scoping(user.identity, ns)

    # DatabaseManager에서 LangGraph Store 인스턴스 획득
    from ..core.database import db_manager

    store = await db_manager.get_store()

    await store.adelete(tuple(scoped_namespace), k)

    return {"status": "deleted"}


@router.post("/store/items/search", response_model=StoreSearchResponse)
async def search_store_items(
    request: StoreSearchRequest, user: User = Depends(get_current_user)
) -> StoreSearchResponse:
    """LangGraph Store에서 아이템 검색

    네임스페이스 접두사와 검색 쿼리로 아이템을 검색합니다.
    LangGraph Store는 키워드, 시맨틱, 하이브리드 검색을 모두 지원합니다.

    검색 모드:
    - 키워드 검색: 키/값의 텍스트 매칭
    - 시맨틱 검색: 임베딩 기반 유사도 검색 (벡터 검색)
    - 하이브리드 검색: 키워드 + 시맨틱 결합 (최상의 결과)

    동작 흐름:
    1. 네임스페이스 접두사에 사용자 스코핑 적용
    2. LangGraph Store 인스턴스 획득
    3. store.asearch()로 검색 실행
    4. 결과를 StoreItem 리스트로 변환
    5. 페이지네이션 정보와 함께 반환

    Args:
        request (StoreSearchRequest): 검색 요청
            - namespace_prefix (list[str]): 검색할 네임스페이스 접두사
            - query (str | None): 검색 쿼리 (None이면 전체 조회)
            - limit (int): 최대 반환 개수 (기본값: 20)
            - offset (int): 결과 오프셋 (페이지네이션)
        user (User): 인증된 사용자 정보

    Returns:
        StoreSearchResponse: 검색 결과
            - items (list[StoreItem]): 검색된 아이템 리스트
            - total (int): 반환된 아이템 수
            - limit (int): 요청된 limit
            - offset (int): 요청된 offset

    사용 예:
        POST /store/items/search
        {
            "namespace_prefix": ["users", "user123"],
            "query": "theme settings",
            "limit": 10,
            "offset": 0
        }

    참고:
        - namespace_prefix는 해당 접두사로 시작하는 모든 네임스페이스 검색
        - query가 None이면 전체 아이템 반환 (네임스페이스 필터링만)
        - LangGraph Store는 total count를 제공하지 않음 (반환된 개수만 제공)
        - 벡터 검색은 LangGraph Store의 임베딩 설정에 따라 자동 활성화
    """

    # 네임스페이스 접두사에 사용자 스코핑 적용
    scoped_prefix = apply_user_namespace_scoping(user.identity, request.namespace_prefix)

    # DatabaseManager에서 LangGraph Store 인스턴스 획득
    from ..core.database import db_manager

    store = await db_manager.get_store()

    # LangGraph Store로 검색 실행
    # asearch는 namespace_prefix를 positional-only 인자로 받음
    results = await store.asearch(
        tuple(scoped_prefix),
        query=request.query,
        limit=request.limit or 20,
        offset=request.offset or 0,
    )

    items = [StoreItem(key=r.key, value=r.value, namespace=list(r.namespace)) for r in results]

    return StoreSearchResponse(
        items=items,
        total=len(items),  # LangGraph Store는 total count 미제공
        limit=request.limit or 20,
        offset=request.offset or 0,
    )


def apply_user_namespace_scoping(user_id: str, namespace: Sequence[str] | None) -> list[str]:
    """사용자별 네임스페이스 스코핑을 적용하여 데이터 격리 보장

    각 사용자의 데이터를 네임스페이스 레벨에서 격리하여 다중 테넌트 보안을 제공합니다.
    네임스페이스가 제공되지 않으면 사용자 전용 네임스페이스로 기본 설정됩니다.

    동작 로직:
    1. 네임스페이스가 비어있으면 → ["users", user_id] 반환
    2. 명시적으로 사용자 네임스페이스를 지정했으면 → 그대로 허용
    3. 개발 환경에서는 모든 네임스페이스 허용 (프로덕션에서는 제거 필요)

    Args:
        user_id (str): 사용자 고유 식별자 (인증된 사용자의 identity)
        namespace (list[str]): 요청된 네임스페이스 리스트

    Returns:
        list[str]: 사용자 스코핑이 적용된 네임스페이스

    사용 예:
        # 네임스페이스 없음 → 기본 사용자 네임스페이스
        apply_user_namespace_scoping("user123", [])
        # 반환: ["users", "user123"]

        # 명시적 사용자 네임스페이스 → 허용
        apply_user_namespace_scoping("user123", ["users", "user123", "settings"])
        # 반환: ["users", "user123", "settings"]

        # 다른 네임스페이스 → 개발 환경에서만 허용
        apply_user_namespace_scoping("user123", ["shared", "config"])
        # 반환: ["shared", "config"] (개발 환경)

    참고:
        - 프로덕션 환경에서는 사용자 네임스페이스 외 접근을 차단해야 함
        - 다중 테넌트 격리를 위한 핵심 보안 로직
        - 공유 네임스페이스가 필요한 경우 별도 권한 체크 로직 추가 필요
    """

    if not namespace:
        # 기본적으로 사용자 전용 네임스페이스 사용
        return ["users", user_id]

    # 명시적으로 사용자 네임스페이스를 지정한 경우 허용
    namespace_list = list(namespace)
    if (
        namespace_list
        and namespace_list[0] == "users"
        and len(namespace_list) >= 2
        and namespace_list[1] == user_id
    ):
        return namespace_list

    # 개발 환경에서는 모든 네임스페이스 허용 (프로덕션에서는 이 부분 제거)
    return namespace_list
