"""LangGraph Store API용 Pydantic 모델

이 모듈은 LangGraph의 AsyncPostgresStore와 통합하여 장기 메모리 및
키-값 저장소 기능을 제공하는 Agent Protocol 호환 모델을 정의합니다.

주요 구성 요소:
• StorePutRequest - 저장소에 항목 저장 요청 모델
• StoreGetResponse - 저장소에서 항목 조회 응답 모델
• StoreSearchRequest - 저장소 항목 검색 요청 모델
• StoreSearchResponse - 저장소 항목 검색 응답 모델
• StoreItem - 저장소 항목 표현 모델
• StoreDeleteRequest - 저장소 항목 삭제 요청 모델

네임스페이스 처리:
    - API는 list[str] 형식으로 네임스페이스 수신
    - LangGraph Store는 tuple[str, ...] 형식 요구
    - 서비스 레이어에서 변환 처리

사용 예:
    # 항목 저장
    request = StorePutRequest(
        namespace=["user", "123", "preferences"],
        key="theme",
        value={"mode": "dark"}
    )

    # 항목 검색
    search = StoreSearchRequest(
        namespace_prefix=["user", "123"],
        query="theme",
        limit=10
    )
"""

from typing import Any

from pydantic import BaseModel, Field


class StorePutRequest(BaseModel):
    """저장소에 항목을 저장하기 위한 요청 모델

    LangGraph Store에 키-값 쌍을 저장할 때 사용됩니다.
    네임스페이스를 통해 항목을 계층적으로 구조화할 수 있습니다.

    사용 예:
        request = StorePutRequest(
            namespace=["user", "123", "settings"],
            key="language",
            value="ko-KR"
        )
    """

    namespace: list[str] = Field(
        ...,
        description="저장소 네임스페이스 (계층적 경로, 예: ['user', '123', 'preferences'])",
    )
    key: str = Field(..., description="항목 키 (네임스페이스 내에서 고유)")
    value: Any = Field(..., description="저장할 값 (JSON 직렬화 가능한 모든 타입)")


class StoreGetResponse(BaseModel):
    """저장소에서 조회한 항목의 응답 모델

    특정 네임스페이스와 키로 조회한 항목을 반환할 때 사용됩니다.

    사용 예:
        response = StoreGetResponse(
            key="theme",
            value={"mode": "dark", "color": "blue"},
            namespace=["user", "123", "preferences"]
        )
    """

    key: str  # 항목 키
    value: Any  # 저장된 값 (모든 JSON 직렬화 가능 타입)
    namespace: list[str]  # 항목이 속한 네임스페이스 경로


class StoreSearchRequest(BaseModel):
    """저장소 항목 검색을 위한 요청 모델

    네임스페이스 접두사를 기반으로 항목을 검색하며,
    선택적으로 쿼리를 통한 필터링을 지원합니다.

    검색 방식:
    - namespace_prefix로 계층적 범위 제한
    - query가 제공되면 키나 값에서 검색 (구현에 따라 다름)
    - limit/offset을 통한 페이지네이션

    사용 예:
        # 특정 사용자의 모든 설정 검색
        request = StoreSearchRequest(
            namespace_prefix=["user", "123"],
            query=None,
            limit=50,
            offset=0
        )

        # 특정 키워드로 검색
        request = StoreSearchRequest(
            namespace_prefix=["user"],
            query="theme",
            limit=10
        )
    """

    namespace_prefix: list[str] = Field(
        ...,
        description="검색할 네임스페이스 접두사 (해당 접두사로 시작하는 모든 항목 검색)",
    )
    query: str | None = Field(None, description="검색 쿼리 (키 또는 값에서 검색, None이면 모든 항목 반환)")
    limit: int | None = Field(20, le=100, ge=1, description="반환할 최대 결과 수 (1-100, 기본값: 20)")
    offset: int | None = Field(0, ge=0, description="건너뛸 결과 수 (페이지네이션용, 기본값: 0)")


class StoreItem(BaseModel):
    """저장소 항목을 나타내는 모델

    검색 결과나 목록 조회 시 개별 항목을 표현하는데 사용됩니다.
    StoreGetResponse와 동일한 구조이지만 목록 컨텍스트에서 사용됩니다.

    사용 예:
        item = StoreItem(
            key="language",
            value="ko-KR",
            namespace=["user", "123", "settings"]
        )
    """

    key: str  # 항목 키
    value: Any  # 저장된 값
    namespace: list[str]  # 항목이 속한 네임스페이스 경로


class StoreSearchResponse(BaseModel):
    """저장소 검색 결과 응답 모델

    검색 요청에 대한 결과를 페이지네이션 메타데이터와 함께 반환합니다.

    페이지네이션 정보:
    - items: 현재 페이지의 항목들
    - total: 검색 조건에 맞는 전체 항목 수
    - limit: 요청한 페이지 크기
    - offset: 현재 페이지의 시작 위치

    사용 예:
        response = StoreSearchResponse(
            items=[item1, item2, item3],
            total=100,
            limit=20,
            offset=0
        )

        # 다음 페이지 여부 확인
        has_more = response.offset + len(response.items) < response.total
    """

    items: list[StoreItem]  # 검색된 항목 목록
    total: int  # 전체 검색 결과 수 (페이지네이션 전)
    limit: int  # 요청한 페이지 크기
    offset: int  # 현재 페이지 시작 오프셋


class StoreDeleteRequest(BaseModel):
    """저장소 항목 삭제 요청 모델 (LangGraph SDK 호환)

    특정 네임스페이스와 키를 가진 항목을 삭제할 때 사용됩니다.
    LangGraph SDK의 delete 인터페이스와 호환되도록 설계되었습니다.

    사용 예:
        request = StoreDeleteRequest(
            namespace=["user", "123", "settings"],
            key="theme"
        )
    """

    namespace: list[str]  # 삭제할 항목의 네임스페이스
    key: str  # 삭제할 항목의 키
