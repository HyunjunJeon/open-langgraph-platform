"""Lightweight context-var helpers for passing authenticated user info into LangGraph graphs.

Graph nodes can access the current request's authentication context by calling
`get_auth_ctx()`.  The server sets the context for the lifetime of a single run
(using an async context-manager) so the information is automatically scoped and
cleaned up.

We mirror the structure used by the vendored reference implementation so that
libraries expecting `Auth.types.BaseAuthContext` work unchanged.
"""

from __future__ import annotations

import contextvars
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any, cast

from langgraph_sdk.auth.types import BaseAuthContext
from langgraph_sdk.auth.types import BaseUser as LangGraphBaseUser
from starlette.authentication import AuthCredentials, BaseUser

from .auth_middleware import LangGraphUser

# 내부 컨텍스트 변수: 현재 인증 컨텍스트 저장 (없으면 None)
# 스레드 로컬 대신 asyncio 친화적인 contextvars 사용
_AuthCtx: contextvars.ContextVar[BaseAuthContext | None] = contextvars.ContextVar(
    "LangGraphAuthContext", default=None
)


def get_auth_ctx() -> BaseAuthContext | None:
    """현재 인증 컨텍스트 반환

    Returns:
        Auth.types.BaseAuthContext | None: 설정된 경우 인증 컨텍스트, 없으면 None

    사용 예:
        # 그래프 노드에서 사용자 확인
        auth_ctx = get_auth_ctx()
        if auth_ctx and auth_ctx.user:
            user_id = auth_ctx.user.identity
    """
    return _AuthCtx.get()


@asynccontextmanager
async def with_auth_ctx(
    user: LangGraphBaseUser | BaseUser | Mapping[str, Any] | None,
    permissions: list[str] | AuthCredentials | None = None,
) -> AsyncIterator[None]:
    """비동기 블록 실행 동안 인증 컨텍스트를 임시로 설정

    이 컨텍스트 매니저는 LangGraph 그래프 실행 중 인증 정보를 주입합니다.
    블록 종료 시 자동으로 이전 컨텍스트로 복원됩니다.

    Parameters
    ----------
    user : BaseUser | None
        인증된 사용자 (None이면 익명 접근)
    permissions : list[str] | AuthCredentials | None
        Starlette AuthCredentials 인스턴스 또는 권한 문자열 리스트
        None이면 권한 없음

    사용 예:
        async with with_auth_ctx(user, ["read", "write"]):
            # 이 블록 안에서 get_auth_ctx()로 사용자 정보 접근 가능
            result = await graph.ainvoke(input_data)
    """
    # 권한 리스트 정규화
    scopes: list[str] = []
    if isinstance(permissions, AuthCredentials):
        scopes = list(permissions.scopes)
    elif isinstance(permissions, list):
        scopes = list(permissions)

    normalized_user: LangGraphBaseUser | None
    if user is None:
        normalized_user = None
    elif isinstance(user, LangGraphBaseUser):
        normalized_user = user
    elif isinstance(user, BaseUser):
        normalized_user = cast("LangGraphBaseUser", user)
    else:
        payload: Mapping[str, Any] | None = None
        if isinstance(user, Mapping):
            payload = user
        elif hasattr(user, "model_dump"):
            raw_dump = user.model_dump()
            if isinstance(raw_dump, Mapping):
                payload = raw_dump
        elif hasattr(user, "to_dict"):
            raw_dict = user.to_dict()
            if isinstance(raw_dict, Mapping):
                payload = raw_dict

        if payload is None and hasattr(user, "identity"):
            identity_value = user.identity
            if identity_value is not None:
                payload = {
                    "identity": str(identity_value),
                    "display_name": getattr(user, "display_name", None),
                    "permissions": getattr(user, "permissions", []),
                    "is_authenticated": getattr(user, "is_authenticated", True),
                }

        normalized_user = LangGraphUser(payload) if payload is not None else None

    if normalized_user is None:
        if not scopes:
            token = _AuthCtx.set(None)
        else:
            synthetic_user = LangGraphUser(
                {
                    "identity": "anonymous",
                    "display_name": "anonymous",
                    "permissions": list(scopes),
                    "is_authenticated": False,
                }
            )
            token = _AuthCtx.set(BaseAuthContext(user=synthetic_user, permissions=scopes))
    else:
        token = _AuthCtx.set(BaseAuthContext(user=normalized_user, permissions=scopes))
    try:
        yield
    finally:
        _AuthCtx.reset(token)
