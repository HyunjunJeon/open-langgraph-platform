"""LangGraph Agent Server용 인증 미들웨어 통합

이 모듈은 LangGraph의 인증 시스템을 FastAPI와 통합합니다.
Starlette의 AuthenticationMiddleware를 사용하여 모든 요청에 대해
인증을 처리하고 request.user에 사용자 정보를 설정합니다.

주요 구성 요소:
- LangGraphUser: Starlette BaseUser 인터페이스 구현
- LangGraphAuthBackend: auth.py의 @auth.authenticate 핸들러 호출
- get_auth_backend: 환경 변수 기반 인증 백엔드 선택
- on_auth_error: Agent Protocol 형식의 오류 응답

흐름:
1. 클라이언트 요청 → AuthenticationMiddleware
2. Middleware → LangGraphAuthBackend.authenticate()
3. Backend → auth.py의 @auth.authenticate 핸들러
4. 성공 시 → request.user = LangGraphUser 설정
5. 실패 시 → on_auth_error로 401 응답
"""

import importlib.util
import logging
import os
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from langgraph_sdk import Auth
from langgraph_sdk.auth.types import BaseUser as LangGraphBaseUser
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    BaseUser,
)
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse

from ..models.errors import AgentProtocolError

logger = logging.getLogger(__name__)


class LangGraphUser(LangGraphBaseUser, BaseUser):
    """Starlette BaseUser 인터페이스를 구현하면서 LangGraph 인증 데이터를 보존하는 사용자 래퍼

    이 클래스는 LangGraph auth 핸들러가 반환한 MinimalUserDict를 Starlette가
    요구하는 BaseUser 인터페이스로 감쌉니다.

    필수 속성:
    - identity: 사용자 고유 식별자
    - is_authenticated: 인증 여부 (기본값 True)
    - display_name: 표시 이름 (없으면 identity 사용)

    추가 속성:
    - auth 핸들러가 반환한 모든 추가 필드에 __getattr__로 접근 가능
      (예: permissions, org_id, email 등)
    """

    def __init__(self, user_data: Mapping[str, Any]) -> None:
        # Copy to avoid mutating caller-provided data structures
        self._user_data: dict[str, Any] = dict(user_data)

    @property
    def identity(self) -> str:
        identity = self._user_data.get("identity")
        if not isinstance(identity, str):
            raise ValueError("Authenticated user must include an 'identity' string")
        return identity

    @property
    def is_authenticated(self) -> bool:
        return bool(self._user_data.get("is_authenticated", True))

    @property
    def display_name(self) -> str:
        display_name = self._user_data.get("display_name")
        if isinstance(display_name, str):
            return display_name
        return self.identity

    def __getattr__(self, name: str) -> Any:
        """인증 데이터의 추가 필드에 접근 허용

        auth 핸들러가 반환한 커스텀 필드(permissions, org_id 등)에
        user.field_name 형식으로 접근할 수 있게 합니다.
        """
        if name in self._user_data:
            return self._user_data[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def to_dict(self) -> dict[str, Any]:
        """원본 사용자 데이터 딕셔너리 반환

        Returns:
            MinimalUserDict: auth 핸들러가 반환한 원본 데이터의 복사본
        """
        return dict(self._user_data)

    @property
    def permissions(self) -> Sequence[str]:
        raw_permissions = self._user_data.get("permissions", [])
        if isinstance(raw_permissions, str):
            return (raw_permissions,)
        if isinstance(raw_permissions, Sequence):
            return tuple(scope for scope in raw_permissions if isinstance(scope, str))
        return ()

    def __getitem__(self, key: str) -> Any:
        return self._user_data[key]

    def __contains__(self, key: object) -> bool:
        return key in self._user_data

    def __iter__(self) -> Iterator[str]:
        return iter(self._user_data)


class LangGraphAuthBackend(AuthenticationBackend):
    """LangGraph 인증 시스템을 사용하는 인증 백엔드

    이 클래스는 LangGraph의 @auth.authenticate 핸들러를 Starlette의
    AuthenticationMiddleware와 연결합니다.

    동작 방식:
    1. 애플리케이션 시작 시 auth.py 파일에서 Auth 인스턴스 로드
    2. 각 요청마다 authenticate() 메서드 호출
    3. 요청 헤더를 auth 핸들러에 전달
    4. 핸들러가 반환한 사용자 데이터를 LangGraphUser로 변환
    5. Starlette에게 (credentials, user) 튜플 반환
    """

    def __init__(self) -> None:
        self.auth_instance = self._load_auth_instance()

    def _load_auth_instance(self) -> Auth | None:
        """auth.py 파일에서 Auth 인스턴스 동적 로드

        프로젝트 루트의 auth.py에서 'auth' 변수를 찾아 로드합니다.
        이를 통해 사용자가 auth.py를 수정하여 커스텀 인증을 구현할 수 있습니다.

        Returns:
            Auth | None: 성공 시 Auth 인스턴스, 실패 시 None
        """
        try:
            # 프로젝트 루트의 auth.py에서 auth 인스턴스 임포트
            auth_path = Path.cwd() / "auth.py"
            if not auth_path.exists():
                logger.warning(f"Auth file not found at {auth_path}")
                return None

            spec = importlib.util.spec_from_file_location("auth_module", str(auth_path))
            if spec is None or spec.loader is None:
                logger.error(f"Could not load auth module from {auth_path}")
                return None

            auth_module = importlib.util.module_from_spec(spec)
            sys.modules["auth_module"] = auth_module
            spec.loader.exec_module(auth_module)

            auth_instance = getattr(auth_module, "auth", None)
            if not isinstance(auth_instance, Auth):
                logger.error(f"No valid Auth instance found in {auth_path}")
                return None

            logger.info(f"Successfully loaded auth instance from {auth_path}")
            return auth_instance

        except Exception as e:
            logger.error(f"Error loading auth instance: {e}", exc_info=True)
            return None

    async def authenticate(self, conn: HTTPConnection) -> tuple[AuthCredentials, BaseUser] | None:
        """LangGraph 인증 시스템을 사용하여 요청 인증

        이 메서드는 모든 HTTP 요청에 대해 호출됩니다.
        auth.py의 @auth.authenticate 핸들러를 호출하여 사용자를 검증합니다.

        Args:
            conn (HTTPConnection): 요청 헤더가 포함된 HTTP 연결

        Returns:
            tuple[AuthCredentials, BaseUser] | None:
                인증 성공 시 (자격증명, 사용자) 튜플, 실패 시 None

        Raises:
            AuthenticationError: 인증 실패 시 발생
                - 잘못된 토큰
                - 만료된 토큰
                - auth 핸들러가 Auth.exceptions.HTTPException 발생 시
        """
        if self.auth_instance is None:
            logger.warning("No auth instance available, skipping authentication")
            return None

        if self.auth_instance._authenticate_handler is None:
            logger.warning("No authenticate handler configured, skipping authentication")
            return None

        try:
            # 헤더를 LangGraph가 기대하는 dict 형식으로 변환
            # bytes 타입 헤더는 문자열로 디코딩
            headers: dict[str, str] = {
                key.decode() if isinstance(key, bytes) else key: value.decode()
                if isinstance(value, bytes)
                else value
                for key, value in conn.headers.items()
            }

            # LangGraph의 authenticate 핸들러 호출 (auth.py의 @auth.authenticate)
            user_payload = await self.auth_instance._authenticate_handler(headers)

            if not user_payload:
                raise AuthenticationError("Invalid user data returned from auth handler")

            if not isinstance(user_payload, Mapping):
                raise AuthenticationError("Auth handler must return a mapping-compatible object")

            user_data = dict(user_payload)

            if "identity" not in user_data:
                raise AuthenticationError("Auth handler must return 'identity' field")

            # 권한 추출하여 자격증명 생성
            raw_permissions = user_data.get("permissions", [])
            if isinstance(raw_permissions, str):
                permissions_list = [raw_permissions]
            elif isinstance(raw_permissions, Sequence):
                permissions_list = [str(scope) for scope in raw_permissions if isinstance(scope, str)]
            else:
                permissions_list = []

            # Starlette 호환 사용자 및 자격증명 생성
            credentials = AuthCredentials(permissions_list)
            user = LangGraphUser(user_data)

            logger.debug(f"Successfully authenticated user: {user.identity}")
            return credentials, user

        except Auth.exceptions.HTTPException as e:
            logger.warning(f"Authentication failed: {e.detail}")
            raise AuthenticationError(e.detail) from e

        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}", exc_info=True)
            raise AuthenticationError("Authentication system error") from e


def get_auth_backend() -> AuthenticationBackend:
    """AUTH_TYPE 환경 변수 기반으로 인증 백엔드 반환

    현재 지원하는 AUTH_TYPE:
    - noop: 인증 없음 (개발용, 모든 요청 허용)
    - custom: 커스텀 인증 (auth.py에서 구현)

    Returns:
        AuthenticationBackend: 인증 백엔드 인스턴스

    환경 변수:
        AUTH_TYPE: 인증 타입 선택 (기본값: noop)
    """
    auth_type = os.getenv("AUTH_TYPE", "noop").lower()

    if auth_type in ["noop", "custom"]:
        logger.info(f"Using LangGraph auth backend with type: {auth_type}")
        return LangGraphAuthBackend()
    else:
        logger.warning(f"Unknown AUTH_TYPE: {auth_type}, using noop")
        return LangGraphAuthBackend()


def on_auth_error(conn: HTTPConnection, exc: AuthenticationError) -> JSONResponse:
    """Agent Protocol 형식으로 인증 오류 처리

    인증 실패 시 표준 Agent Protocol 오류 응답을 생성합니다.
    클라이언트는 일관된 형식의 오류 메시지를 받게 됩니다.

    Args:
        conn (HTTPConnection): HTTP 연결 (로깅용)
        exc (AuthenticationError): 인증 오류

    Returns:
        JSONResponse: Agent Protocol 오류 형식의 JSON 응답 (401 Unauthorized)

    응답 형식:
        {
            "error": "unauthorized",
            "message": "오류 메시지",
            "details": {"authentication_required": true}
        }
    """
    logger.warning(f"Authentication error for {conn.url}: {exc}")

    return JSONResponse(
        status_code=401,
        content=AgentProtocolError(
            error="unauthorized",
            message=str(exc),
            details={"authentication_required": True},
        ).model_dump(),
    )
