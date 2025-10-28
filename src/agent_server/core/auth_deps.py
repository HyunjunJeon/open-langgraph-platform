"""FastAPI 엔드포인트용 인증 의존성 함수

이 모듈은 FastAPI의 의존성 주입 시스템과 통합되는 인증 헬퍼를 제공합니다.
라우터 함수에서 Depends()와 함께 사용하여 사용자 인증을 처리합니다.

주요 기능:
- get_current_user: 현재 요청의 인증된 사용자 추출
- get_user_id: 사용자 ID만 필요한 경우 사용
- require_permission: 특정 권한 필요 시 사용
- require_authenticated: 인증 여부만 확인

사용 예:
    @router.get("/assistants")
    async def list_assistants(user: User = Depends(get_current_user)):
        # user는 인증된 사용자 객체
        return await get_assistants_for_user(user.identity)
"""

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, Request

from ..models.auth import User


def get_current_user(request: Request) -> User:
    """인증 미들웨어가 설정한 요청 컨텍스트에서 현재 사용자 추출

    동작 흐름:
    1. 인증 미들웨어가 LangGraph auth 핸들러(@auth.authenticate) 호출
    2. 성공 시 request.user에 LangGraphUser 인스턴스 설정
    3. 이 함수가 LangGraphUser를 Open LangGraph의 User 모델로 변환

    Args:
        request (Request): FastAPI 요청 객체

    Returns:
        User: 인증된 사용자 객체 (identity, permissions 등 포함)

    Raises:
        HTTPException: 사용자가 인증되지 않은 경우 (401)

    사용 예:
        @router.get("/profile")
        async def get_profile(user: User = Depends(get_current_user)):
            return {"user_id": user.identity, "name": user.display_name}
    """

    # Starlette 인증 미들웨어에서 사용자 정보 가져오기
    if not hasattr(request, "user") or request.user is None:
        # 인증 미들웨어가 없거나 사용자가 설정되지 않음
        raise HTTPException(status_code=401, detail="Authentication required")

    if not request.user.is_authenticated:
        # 사용자가 명시적으로 인증되지 않음
        raise HTTPException(status_code=401, detail="Invalid authentication")

    # LangGraphUser를 Open LangGraph User 모델로 변환
    # request.user는 auth_middleware에서 설정한 LangGraphUser 인스턴스
    user_payload = request.user.to_dict()
    user_data: dict[str, Any] = user_payload if isinstance(user_payload, dict) else dict(user_payload)

    return User(
        identity=user_data["identity"],
        display_name=user_data.get("display_name"),
        permissions=user_data.get("permissions", []),
        org_id=user_data.get("org_id"),
        is_authenticated=user_data.get("is_authenticated", True),
    )


def get_user_id(user: User = Depends(get_current_user)) -> str:
    """사용자 ID를 안전하게 가져오는 헬퍼 의존성

    사용자 객체 전체가 아닌 ID만 필요한 경우 사용합니다.

    Args:
        user (User): get_current_user 의존성에서 가져온 사용자 객체

    Returns:
        str: 사용자 고유 식별자 (identity)

    사용 예:
        @router.get("/my-data")
        async def get_my_data(user_id: str = Depends(get_user_id)):
            return await fetch_data_for_user(user_id)
    """
    return user.identity


def require_permission(permission: str) -> Callable[[User], User]:
    """특정 권한을 요구하는 의존성 생성

    이 함수는 커링(currying) 패턴을 사용하여 특정 권한이 필요한 의존성을 생성합니다.
    사용자가 해당 권한을 가지고 있지 않으면 403 Forbidden을 반환합니다.

    Args:
        permission (str): 필요한 권한 문자열 (예: "admin", "read", "write")

    Returns:
        Callable: 권한을 확인하는 의존성 함수

    사용 예:
        @router.get("/admin")
        async def admin_endpoint(user: User = Depends(require_permission("admin"))):
            return {"message": "관리자 접근 허용"}

        @router.delete("/users/{user_id}")
        async def delete_user(
            user_id: str,
            admin: User = Depends(require_permission("delete_users"))
        ):
            await delete_user_by_id(user_id)
    """

    def permission_dependency(user: User = Depends(get_current_user)) -> User:
        if permission not in user.permissions:
            raise HTTPException(status_code=403, detail=f"Permission '{permission}' required")
        return user

    return permission_dependency


def require_authenticated(request: Request) -> User:
    """사용자가 인증되었는지만 확인하는 단순화된 의존성

    get_current_user와 동일하지만 더 명확한 이름을 제공합니다.
    특정 권한이 필요 없고 인증 여부만 확인하는 엔드포인트에 사용합니다.

    Args:
        request (Request): FastAPI 요청 객체

    Returns:
        User: 인증된 사용자 객체

    사용 예:
        @router.get("/profile")
        async def my_profile(user: User = Depends(require_authenticated)):
            return {"user": user.identity}
    """
    return get_current_user(request)
