"""Authentication dependency functions for FastAPI endpoints.

This module provides authentication helpers that integrate with FastAPI's dependency injection system.
Use them with Depends() in router functions to handle user authentication.

Key functions:
- get_current_user: Extracts the authenticated user from the current request.
- get_user_id: Use when only the user ID is needed.
- require_permission: Use when a specific permission is required.
- require_authenticated: Use to verify authentication status only.

Usage example:
    @router.get("/assistants")
    async def list_assistants(user: User = Depends(get_current_user)):
        # user is the authenticated user object
        return await get_assistants_for_user(user.identity)
"""

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, Request

from ..models.auth import User


def get_current_user(request: Request) -> User:
    """Extracts the current user from the request context set by the authentication middleware.

    Flow:
    1. The authentication middleware calls the LangGraph auth handler (@auth.authenticate).
    2. On success, it sets a LangGraphUser instance on request.user.
    3. This function converts the LangGraphUser to Open LangGraph's User model.

    Args:
        request (Request): The FastAPI request object.

    Returns:
        User: The authenticated user object (including identity, permissions, etc.).

    Raises:
        HTTPException: If the user is not authenticated (401).

    Usage Example:
        @router.get("/profile")
        async def get_profile(user: User = Depends(get_current_user)):
            return {"user_id": user.identity, "name": user.display_name}
    """

    # Starlette 인증 미들웨어에서 사용자 정보 가져오기
    if not hasattr(request, "user") or request.user is None:
        # Authentication middleware is missing or user is not set
        raise HTTPException(status_code=401, detail="Authentication required")

    if not request.user.is_authenticated:
        # User is explicitly not authenticated
        raise HTTPException(status_code=401, detail="Invalid authentication")

    # Convert LangGraphUser to Open LangGraph User model
    # request.user is the LangGraphUser instance set by auth_middleware
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
    """Helper dependency to safely get the user ID.

    Use this when only the user ID is needed, not the full user object.

    Args:
        user (User): The user object from the get_current_user dependency.

    Returns:
        str: The user's unique identifier (identity).

    Usage Example:
        @router.get("/my-data")
        async def get_my_data(user_id: str = Depends(get_user_id)):
            return await fetch_data_for_user(user_id)
    """
    return user.identity


def require_permission(permission: str) -> Callable[[User], User]:
    """Create a dependency that requires a specific permission.

    This function uses a currying pattern to create a dependency that requires a specific permission.
    It returns a 403 Forbidden error if the user does not have the required permission.

    Args:
        permission (str): The required permission string (e.g., "admin", "read", "write").

    Returns:
        Callable: A dependency function that checks for the permission.

    Usage Example:
        @router.get("/admin")
        async def admin_endpoint(user: User = Depends(require_permission("admin"))):
            return {"message": "Admin access granted"}

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
    """A simplified dependency that only checks if the user is authenticated.

    This is identical to get_current_user but provides a more explicit name.
    Use this for endpoints that only require authentication, not specific permissions.

    Args:
        request (Request): The FastAPI request object.

    Returns:
        User: The authenticated user object.

    Usage Example:
        @router.get("/profile")
        async def my_profile(user: User = Depends(require_authenticated)):
            return {"user": user.identity}
    """
    return get_current_user(request)
