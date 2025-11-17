"""Authentication middleware integration for LangGraph Agent Server.

This module integrates LangGraph's authentication system with FastAPI.
It uses Starlette's AuthenticationMiddleware to handle authentication
for all requests and sets user information on request.user.

Main components:
- LangGraphUser: Implements the Starlette BaseUser interface.
- LangGraphAuthBackend: Calls the @auth.authenticate handler in auth.py.
- get_auth_backend: Selects the authentication backend based on environment variables.
- on_auth_error: Provides error responses in Agent Protocol format.

Flow:
1. Client request -> AuthenticationMiddleware
2. Middleware -> LangGraphAuthBackend.authenticate()
3. Backend -> @auth.authenticate handler in auth.py
4. On success -> Set request.user = LangGraphUser
5. On failure -> Respond with 401 via on_auth_error
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
    """User wrapper that implements the Starlette BaseUser interface while preserving LangGraph auth data.

    This class wraps the MinimalUserDict returned by the LangGraph auth handler
    into the BaseUser interface required by Starlette.

    Required attributes:
    - identity: The unique identifier for the user.
    - is_authenticated: Whether the user is authenticated (defaults to True).
    - display_name: The display name (uses identity if not provided).

    Additional attributes:
    - Any additional fields returned by the auth handler are accessible via __getattr__
      (e.g., permissions, org_id, email).
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
        """Allow access to additional fields from the authentication data.

        Allows accessing custom fields returned by the auth handler (like permissions, org_id)
        using user.field_name syntax.
        """
        if name in self._user_data:
            return self._user_data[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def to_dict(self) -> dict[str, Any]:
        """Return the original user data dictionary.

        Returns:
            MinimalUserDict: A copy of the original data returned by the auth handler.
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
    """Authentication backend that uses the LangGraph authentication system.

    This class connects LangGraph's @auth.authenticate handler with Starlette's
    AuthenticationMiddleware.

    How it works:
    1. On application startup, dynamically loads the Auth instance from auth.py.
    2. For each request, the authenticate() method is called.
    3. It passes the request headers to the auth handler.
    4. It converts the user data returned by the handler into a LangGraphUser.
    5. It returns a (credentials, user) tuple to Starlette.
    """

    def __init__(self) -> None:
        self.auth_instance = self._load_auth_instance()

    def _load_auth_instance(self) -> Auth | None:
        """Dynamically load the Auth instance from the auth.py file.

        It finds and loads the 'auth' variable from auth.py in the project root.
        This allows users to implement custom authentication by modifying auth.py.

        Returns:
            Auth | None: The Auth instance on success, or None on failure.
        """
        try:
            # Import the auth instance from auth.py in the project root
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
        """Authenticate a request using the LangGraph authentication system.

        This method is called for every HTTP request.
        It calls the @auth.authenticate handler in auth.py to validate the user.

        Args:
            conn (HTTPConnection): The HTTP connection, including request headers.

        Returns:
            tuple[AuthCredentials, BaseUser] | None:
                A (credentials, user) tuple on successful authentication, or None on failure.

        Raises:
            AuthenticationError: Raised on authentication failure.
                - Invalid token
                - Expired token
                - If the auth handler raises Auth.exceptions.HTTPException
        """
        if self.auth_instance is None:
            logger.warning("No auth instance available, skipping authentication")
            return None

        if self.auth_instance._authenticate_handler is None:
            logger.warning("No authenticate handler configured, skipping authentication")
            return None

        try:
            # Convert headers to the dict format expected by LangGraph
            # Decode bytes-type headers to strings
            headers: dict[str, str] = {
                key.decode() if isinstance(key, bytes) else key: value.decode()
                if isinstance(value, bytes)
                else value
                for key, value in conn.headers.items()
            }

            # Call LangGraph's authenticate handler (@auth.authenticate in auth.py)
            user_payload = await self.auth_instance._authenticate_handler(headers)

            if not user_payload:
                raise AuthenticationError("Invalid user data returned from auth handler")

            if not isinstance(user_payload, Mapping):
                raise AuthenticationError("Auth handler must return a mapping-compatible object")

            user_data = dict(user_payload)

            if "identity" not in user_data:
                raise AuthenticationError("Auth handler must return 'identity' field")

            # Extract permissions to create credentials
            raw_permissions = user_data.get("permissions", [])
            if isinstance(raw_permissions, str):
                permissions_list = [raw_permissions]
            elif isinstance(raw_permissions, Sequence):
                permissions_list = [str(scope) for scope in raw_permissions if isinstance(scope, str)]
            else:
                permissions_list = []

            # Create Starlette-compatible user and credentials
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
    """Return an authentication backend based on the AUTH_TYPE environment variable.

    Currently supported AUTH_TYPEs:
    - noop: No authentication (for development, allows all requests).
    - custom: Custom authentication (implemented in auth.py).

    Returns:
        AuthenticationBackend: An instance of the authentication backend.

    Environment Variables:
        AUTH_TYPE: Selects the authentication type (defaults to 'noop').
    """
    auth_type = os.getenv("AUTH_TYPE", "noop").lower()

    if auth_type in ["noop", "custom"]:
        logger.info(f"Using LangGraph auth backend with type: {auth_type}")
        return LangGraphAuthBackend()
    else:
        logger.warning(f"Unknown AUTH_TYPE: {auth_type}, using noop")
        return LangGraphAuthBackend()


def on_auth_error(conn: HTTPConnection, exc: AuthenticationError) -> JSONResponse:
    """Handle authentication errors in the Agent Protocol format.

    Generates a standard Agent Protocol error response on authentication failure.
    This ensures that clients receive a consistent error message format.

    Args:
        conn (HTTPConnection): The HTTP connection (for logging).
        exc (AuthenticationError): The authentication error.

    Returns:
        JSONResponse: A JSON response in the Agent Protocol error format (401 Unauthorized).

    Response Format:
        {
            "error": "unauthorized",
            "message": "Error message",
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
