"""Agent Protocol 오류 응답 모델

이 모듈은 Agent Protocol 표준을 준수하는 오류 응답 구조를 정의합니다.
모든 API 오류는 일관된 형식으로 클라이언트에게 반환되며,
HTTP 상태 코드에 따라 적절한 오류 타입이 자동으로 매핑됩니다.

주요 구성 요소:
• AgentProtocolError - 표준 오류 응답 모델 (error, message, details)
• get_error_type() - HTTP 상태 코드를 오류 타입으로 변환

오류 응답 예시:
    {
        "error": "not_found",
        "message": "Thread not found",
        "details": {"thread_id": "abc-123"}
    }

Agent Protocol 표준:
- error: 기계 판독 가능한 오류 타입 (snake_case)
- message: 사람이 읽을 수 있는 오류 메시지
- details: 추가 오류 정보 (선택적)
"""

from typing import Any

from pydantic import BaseModel, Field


class AgentProtocolError(BaseModel):
    """Agent Protocol 표준 오류 응답 모델

    이 클래스는 Agent Protocol 명세에 정의된 표준 오류 응답 형식을 나타냅니다.
    모든 API 오류는 이 형식으로 직렬화되어 클라이언트에게 전달됩니다.

    오류 응답 구조:
    - error: 오류 타입 식별자 (예: not_found, unauthorized)
    - message: 사용자 친화적인 오류 설명
    - details: 디버깅을 위한 추가 정보 (선택적)

    사용 시나리오:
    - 리소스를 찾을 수 없는 경우 (404)
    - 인증 실패 (401)
    - 권한 부족 (403)
    - 잘못된 요청 데이터 (400, 422)
    - 서버 내부 오류 (500)

    FastAPI 통합:
    HTTPException과 함께 사용하여 일관된 오류 응답 제공

    예시:
        error_response = AgentProtocolError(
            error="not_found",
            message="Thread abc-123 not found",
            details={"thread_id": "abc-123", "user_id": "user-456"}
        )
    """

    error: str = Field(..., description="오류 타입 (snake_case 식별자)")
    message: str = Field(..., description="사용자가 읽을 수 있는 오류 메시지")
    details: dict[str, Any] | None = Field(None, description="추가 오류 정보 (디버깅 용도, 선택적)")


def get_error_type(status_code: int) -> str:
    """HTTP 상태 코드를 Agent Protocol 오류 타입으로 변환

    이 함수는 표준 HTTP 상태 코드를 Agent Protocol이 정의한
    오류 타입 문자열로 매핑합니다. 클라이언트는 이 오류 타입을 통해
    프로그래밍 방식으로 오류를 처리할 수 있습니다.

    지원하는 상태 코드 및 매핑:
    - 400: bad_request - 잘못된 요청 형식 또는 파라미터
    - 401: unauthorized - 인증 실패 또는 토큰 누락
    - 403: forbidden - 권한 부족
    - 404: not_found - 리소스를 찾을 수 없음
    - 409: conflict - 리소스 충돌 (중복 생성 등)
    - 422: validation_error - 요청 데이터 검증 실패
    - 500: internal_error - 서버 내부 오류
    - 501: not_implemented - 미구현 기능
    - 503: service_unavailable - 서비스 일시 중단

    Args:
        status_code (int): HTTP 상태 코드 (예: 404, 500)

    Returns:
        str: Agent Protocol 오류 타입 (예: "not_found", "internal_error")
             알 수 없는 상태 코드는 "unknown_error" 반환

    예시:
        >>> get_error_type(404)
        'not_found'
        >>> get_error_type(401)
        'unauthorized'
        >>> get_error_type(999)
        'unknown_error'

    참고:
        - 매핑되지 않은 상태 코드는 기본값 "unknown_error" 사용
        - 클라이언트는 error 필드를 통해 오류 유형을 프로그래밍 방식으로 판단
    """
    # HTTP 상태 코드 → Agent Protocol 오류 타입 매핑 테이블
    error_map = {
        400: "bad_request",  # 잘못된 요청 (형식 오류, 잘못된 파라미터)
        401: "unauthorized",  # 인증 실패 (토큰 누락/만료)
        403: "forbidden",  # 권한 부족 (인증은 되었으나 접근 불가)
        404: "not_found",  # 리소스 없음 (thread, run, assistant 등)
        409: "conflict",  # 리소스 충돌 (중복 ID, 상태 불일치)
        422: "validation_error",  # 요청 데이터 검증 실패 (Pydantic)
        500: "internal_error",  # 서버 내부 오류
        501: "not_implemented",  # 미구현 기능
        503: "service_unavailable",  # 서비스 이용 불가 (DB 연결 실패 등)
    }
    return error_map.get(status_code, "unknown_error")
