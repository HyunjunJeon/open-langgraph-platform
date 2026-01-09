"""Unit tests for RateLimitMiddleware

These tests verify the middleware's rate limiting logic in isolation,
including path exclusion, endpoint type detection, limit calculation,
and 429 response generation.

Test Categories:
1. Path Exclusion Tests - Verify /health, /docs, etc. are skipped
2. Endpoint Type Detection Tests - streaming, runs, write, read classification
3. Rate Limit Calculation Tests - Authenticated vs anonymous limits
4. Response Header Tests - X-RateLimit-* headers
5. 429 Response Tests - Rate limit exceeded handling
6. Graceful Degradation Tests - Behavior when Redis unavailable
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_server.middleware.rate_limit import (
    ENDPOINT_TYPE_LIMITS,
    EXCLUDED_PATHS,
    EXCLUDED_PREFIXES,
    RUN_CREATE_ENDPOINTS,
    STREAMING_ENDPOINTS,
    RateLimitMiddleware,
    get_rate_limit_headers,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def middleware():
    """Create middleware with mocked app."""
    app = AsyncMock()
    return RateLimitMiddleware(app), app


@pytest.fixture
def mock_rate_limiter():
    """Mock the rate_limiter singleton."""
    with patch("agent_server.middleware.rate_limit.rate_limiter") as mock_limiter:
        mock_limiter.is_available = True
        mock_limiter.check_limit = AsyncMock(return_value=(True, 999, 1704326400))
        yield mock_limiter


@pytest.fixture
def mock_rate_limit_disabled():
    """Mock rate limiting as disabled."""
    with patch("agent_server.middleware.rate_limit.RATE_LIMIT_ENABLED", False):
        yield


# ---------------------------------------------------------------------------
# Test: Path Exclusion
# ---------------------------------------------------------------------------


class TestPathExclusion:
    """Tests for path exclusion logic."""

    @pytest.mark.asyncio
    async def test_skips_health_endpoint(self, middleware):
        """Test that /health is skipped."""
        mw, app = middleware

        scope = {"type": "http", "path": "/health", "method": "GET", "headers": []}
        receive = AsyncMock()
        send = AsyncMock()

        await mw(scope, receive, send)

        # Should pass through without rate limiting
        app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_skips_docs_endpoint(self, middleware):
        """Test that /docs is skipped."""
        mw, app = middleware

        scope = {"type": "http", "path": "/docs", "method": "GET", "headers": []}
        receive = AsyncMock()
        send = AsyncMock()

        await mw(scope, receive, send)

        app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_skips_openapi_json(self, middleware):
        """Test that /openapi.json is skipped."""
        mw, app = middleware

        scope = {"type": "http", "path": "/openapi.json", "method": "GET", "headers": []}
        receive = AsyncMock()
        send = AsyncMock()

        await mw(scope, receive, send)

        app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_skips_metrics_endpoint(self, middleware):
        """Test that /metrics is skipped."""
        mw, app = middleware

        scope = {"type": "http", "path": "/metrics", "method": "GET", "headers": []}
        receive = AsyncMock()
        send = AsyncMock()

        await mw(scope, receive, send)

        app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_skips_static_prefix(self, middleware):
        """Test that /static/* paths are skipped."""
        mw, app = middleware

        scope = {"type": "http", "path": "/static/js/app.js", "method": "GET", "headers": []}
        receive = AsyncMock()
        send = AsyncMock()

        await mw(scope, receive, send)

        app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_skips_non_http_requests(self, middleware):
        """Test that websocket and other non-HTTP requests are skipped."""
        mw, app = middleware

        scope = {"type": "websocket", "path": "/ws"}
        receive = AsyncMock()
        send = AsyncMock()

        await mw(scope, receive, send)

        app.assert_called_once_with(scope, receive, send)

    def test_all_excluded_paths_in_set(self):
        """Verify expected paths are in EXCLUDED_PATHS."""
        expected_paths = {"/health", "/docs", "/redoc", "/openapi.json", "/metrics"}
        for path in expected_paths:
            assert path in EXCLUDED_PATHS or f"{path}/" in EXCLUDED_PATHS

    def test_all_excluded_prefixes_defined(self):
        """Verify expected prefixes are in EXCLUDED_PREFIXES."""
        assert "/static/" in EXCLUDED_PREFIXES


# ---------------------------------------------------------------------------
# Test: Endpoint Type Detection
# ---------------------------------------------------------------------------


class TestEndpointTypeDetection:
    """Tests for endpoint type classification."""

    def test_get_requests_are_read_type(self, middleware):
        """GET requests should always be 'read' type."""
        mw, _ = middleware

        assert mw._get_endpoint_type("/threads", "GET") == "read"
        assert mw._get_endpoint_type("/runs/123", "GET") == "read"
        assert mw._get_endpoint_type("/assistants", "GET") == "read"
        assert mw._get_endpoint_type("/runs/stream", "GET") == "read"

    def test_streaming_endpoint_detection(self, middleware):
        """POST to streaming endpoints should be 'streaming' type."""
        mw, _ = middleware

        # Standalone streaming
        assert mw._get_endpoint_type("/runs/stream", "POST") == "streaming"
        assert mw._get_endpoint_type("/runs/wait", "POST") == "streaming"

        # Thread-scoped streaming
        assert mw._get_endpoint_type("/threads/abc/runs/stream", "POST") == "streaming"

    def test_run_creation_endpoint_detection(self, middleware):
        """POST to /runs should be 'runs' type."""
        mw, _ = middleware

        # Standalone run creation
        assert mw._get_endpoint_type("/runs", "POST") == "runs"

        # Thread-scoped run creation
        assert mw._get_endpoint_type("/threads/abc/runs", "POST") == "runs"

    def test_write_operations(self, middleware):
        """Other POST/PUT/DELETE/PATCH should be 'write' type."""
        mw, _ = middleware

        # POST operations (not streaming or runs)
        assert mw._get_endpoint_type("/threads", "POST") == "write"
        assert mw._get_endpoint_type("/assistants", "POST") == "write"

        # PUT operations
        assert mw._get_endpoint_type("/threads/abc", "PUT") == "write"

        # DELETE operations
        assert mw._get_endpoint_type("/threads/abc", "DELETE") == "write"

        # PATCH operations
        assert mw._get_endpoint_type("/threads/abc", "PATCH") == "write"

    def test_streaming_takes_priority_over_runs(self, middleware):
        """Streaming detection should be more specific than runs."""
        mw, _ = middleware

        # /runs/stream should be streaming, not runs
        assert mw._get_endpoint_type("/runs/stream", "POST") == "streaming"
        # /runs should be runs
        assert mw._get_endpoint_type("/runs", "POST") == "runs"


# ---------------------------------------------------------------------------
# Test: Rate Limit Calculation
# ---------------------------------------------------------------------------


class TestRateLimitCalculation:
    """Tests for rate limit value calculation."""

    def test_authenticated_user_limits(self, middleware):
        """Authenticated users get full limits by endpoint type."""
        mw, _ = middleware

        # Org-based key
        assert mw._get_limit_for_endpoint("org:abc123", "streaming") == ENDPOINT_TYPE_LIMITS["streaming"]
        assert mw._get_limit_for_endpoint("org:abc123", "runs") == ENDPOINT_TYPE_LIMITS["runs"]
        assert mw._get_limit_for_endpoint("org:abc123", "write") == ENDPOINT_TYPE_LIMITS["write"]
        assert mw._get_limit_for_endpoint("org:abc123", "read") == ENDPOINT_TYPE_LIMITS["read"]

        # User-based key
        assert mw._get_limit_for_endpoint("user:xyz789", "streaming") == ENDPOINT_TYPE_LIMITS["streaming"]
        assert mw._get_limit_for_endpoint("user:xyz789", "read") == ENDPOINT_TYPE_LIMITS["read"]

    def test_anonymous_user_limits(self, middleware):
        """Anonymous users (IP-based) get reduced limits."""
        mw, _ = middleware

        # IP-based key gets 1/5 of the limit (minimum 20)
        streaming_limit = mw._get_limit_for_endpoint("ip:192.168.1.1", "streaming")
        assert streaming_limit == max(20, ENDPOINT_TYPE_LIMITS["streaming"] // 5)

        read_limit = mw._get_limit_for_endpoint("ip:192.168.1.1", "read")
        assert read_limit == max(20, ENDPOINT_TYPE_LIMITS["read"] // 5)

    def test_anonymous_minimum_limit(self, middleware):
        """Anonymous users should have at least 20 requests."""
        mw, _ = middleware

        # Even very low limits should floor at 20
        limit = mw._get_limit_for_endpoint("ip:10.0.0.1", "streaming")
        assert limit >= 20

    def test_endpoint_type_limits_values(self):
        """Verify expected limit values are configured."""
        assert ENDPOINT_TYPE_LIMITS["streaming"] == 100  # Most restrictive
        assert ENDPOINT_TYPE_LIMITS["runs"] == 500
        assert ENDPOINT_TYPE_LIMITS["write"] == 2000
        assert ENDPOINT_TYPE_LIMITS["read"] == 5000  # Most permissive


# ---------------------------------------------------------------------------
# Test: Response Headers
# ---------------------------------------------------------------------------


class TestResponseHeaders:
    """Tests for rate limit response headers."""

    @pytest.mark.asyncio
    async def test_adds_rate_limit_headers(self, middleware, mock_rate_limiter):
        """Test that X-RateLimit-* headers are added to responses."""
        mw, app = middleware

        # Mock user
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.org_id = "org123"

        scope = {
            "type": "http",
            "path": "/threads",
            "method": "GET",
            "headers": [],
            "user": mock_user,
        }

        # Collect headers from response
        captured_headers = {}

        async def capture_send(message):
            if message["type"] == "http.response.start":
                for key, value in message.get("headers", []):
                    if isinstance(key, bytes):
                        key = key.decode()
                    if isinstance(value, bytes):
                        value = value.decode()
                    captured_headers[key.lower()] = value

        # App returns a response
        async def mock_app(scope, receive, send):
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({"type": "http.response.body", "body": b"{}"})

        app.side_effect = mock_app

        await mw(scope, AsyncMock(), capture_send)

        assert "x-ratelimit-limit" in captured_headers
        assert "x-ratelimit-remaining" in captured_headers
        assert "x-ratelimit-reset" in captured_headers

    def test_get_rate_limit_headers_helper(self):
        """Test the helper function for generating headers."""
        headers = get_rate_limit_headers(
            limit=1000,
            remaining=999,
            reset_at=1704326400,
        )

        assert headers["X-RateLimit-Limit"] == "1000"
        assert headers["X-RateLimit-Remaining"] == "999"
        assert headers["X-RateLimit-Reset"] == "1704326400"


# ---------------------------------------------------------------------------
# Test: 429 Response
# ---------------------------------------------------------------------------


class TestRateLimitExceeded:
    """Tests for 429 rate limit exceeded responses."""

    @pytest.mark.asyncio
    async def test_returns_429_when_limit_exceeded(self, middleware):
        """Test that 429 is returned when rate limit is exceeded."""
        mw, app = middleware

        with patch("agent_server.middleware.rate_limit.rate_limiter") as mock_limiter:
            mock_limiter.is_available = True
            # Return not allowed
            mock_limiter.check_limit = AsyncMock(return_value=(False, 0, 1704326400))

            mock_user = MagicMock()
            mock_user.is_authenticated = True
            mock_user.org_id = "org123"

            scope = {
                "type": "http",
                "path": "/runs/stream",
                "method": "POST",
                "headers": [],
                "user": mock_user,
            }

            captured_response = {}

            async def capture_send(message):
                if message["type"] == "http.response.start":
                    captured_response["status"] = message["status"]
                    captured_response["headers"] = dict(message.get("headers", []))
                elif message["type"] == "http.response.body":
                    captured_response["body"] = message.get("body", b"")

            with patch("agent_server.middleware.rate_limit.RATE_LIMIT_ENABLED", True):
                await mw(scope, AsyncMock(), capture_send)

            assert captured_response["status"] == 429
            assert b"retry-after" in captured_response["headers"]

    @pytest.mark.asyncio
    async def test_429_response_body_format(self, middleware):
        """Test that 429 response body has correct format."""
        mw, app = middleware

        with patch("agent_server.middleware.rate_limit.rate_limiter") as mock_limiter:
            mock_limiter.is_available = True
            mock_limiter.check_limit = AsyncMock(return_value=(False, 0, 1704326400))

            mock_user = MagicMock()
            mock_user.is_authenticated = False

            scope = {
                "type": "http",
                "path": "/threads",
                "method": "POST",
                "headers": [],
                "user": mock_user,  # Include user in scope to avoid assertion error
            }

            captured_body = b""

            async def capture_send(message):
                nonlocal captured_body
                if message["type"] == "http.response.body":
                    captured_body = message.get("body", b"")

            with patch("agent_server.middleware.rate_limit.RATE_LIMIT_ENABLED", True):
                await mw(scope, AsyncMock(), capture_send)

            response = json.loads(captured_body)
            assert response["error"] == "rate_limit_exceeded"
            assert "message" in response
            assert "retry_after" in response
            assert "details" in response


# ---------------------------------------------------------------------------
# Test: Graceful Degradation
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """Tests for graceful degradation when rate limiting is unavailable."""

    @pytest.mark.asyncio
    async def test_passes_through_when_disabled(self, middleware, mock_rate_limit_disabled):
        """Test that requests pass through when rate limiting is disabled."""
        mw, app = middleware

        scope = {"type": "http", "path": "/threads", "method": "POST", "headers": []}
        receive = AsyncMock()
        send = AsyncMock()

        await mw(scope, receive, send)

        app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_passes_through_when_redis_unavailable(self, middleware):
        """Redis가 사용 불가능하고 fallback=skip일 때 요청이 통과해야 합니다.

        참고: RATE_LIMIT_FALLBACK 기본값은 "error" (fail-closed)입니다.
        요청이 통과하려면 "skip" (fail-open)으로 설정해야 합니다.
        """
        mw, app = middleware

        with patch("agent_server.middleware.rate_limit.rate_limiter") as mock_limiter:
            mock_limiter.is_available = False

            scope = {"type": "http", "path": "/threads", "method": "POST", "headers": []}
            receive = AsyncMock()
            send = AsyncMock()

            # RATE_LIMIT_FALLBACK="skip"이어야 Redis 실패 시 요청이 통과함
            # 기본값 "error"는 503 Service Unavailable을 반환함
            with (
                patch("agent_server.middleware.rate_limit.RATE_LIMIT_ENABLED", True),
                patch("agent_server.middleware.rate_limit.RATE_LIMIT_FALLBACK", "skip"),
            ):
                await mw(scope, receive, send)

            app.assert_called_once_with(scope, receive, send)


# ---------------------------------------------------------------------------
# Test: Key Generation
# ---------------------------------------------------------------------------


class TestKeyGeneration:
    """Tests for rate limit key generation."""

    @pytest.mark.asyncio
    async def test_uses_org_key_for_authenticated_user(self, middleware, mock_rate_limiter):
        """Test that org-based key is used for authenticated users."""
        mw, app = middleware

        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.org_id = "test-org-123"

        scope = {
            "type": "http",
            "path": "/runs/stream",
            "method": "POST",
            "headers": [],
            "user": mock_user,
        }

        async def mock_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        app.side_effect = mock_app

        with patch("agent_server.middleware.rate_limit.RATE_LIMIT_ENABLED", True):
            await mw(scope, AsyncMock(), AsyncMock())

        # Check that check_limit was called with org-based key
        call_args = mock_rate_limiter.check_limit.call_args
        key = call_args.kwargs.get("key") or call_args[1].get("key")
        assert "org:test-org-123" in key

    @pytest.mark.asyncio
    async def test_uses_ip_key_for_anonymous_user(self, middleware, mock_rate_limiter):
        """Test that IP-based key is used for anonymous users."""
        mw, app = middleware

        # Anonymous user (not authenticated)
        mock_user = MagicMock()
        mock_user.is_authenticated = False

        scope = {
            "type": "http",
            "path": "/threads",
            "method": "GET",
            "headers": [],
            "client": ("192.168.1.100", 12345),
            "user": mock_user,  # Include user in scope to avoid assertion error
        }

        async def mock_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        app.side_effect = mock_app

        with patch("agent_server.middleware.rate_limit.RATE_LIMIT_ENABLED", True):
            await mw(scope, AsyncMock(), AsyncMock())

        # Check that check_limit was called with IP-based key
        call_args = mock_rate_limiter.check_limit.call_args
        key = call_args.kwargs.get("key") or call_args[1].get("key")
        assert "ip:" in key


# ---------------------------------------------------------------------------
# Test: Constants
# ---------------------------------------------------------------------------


class TestConstants:
    """Tests for module constants."""

    def test_streaming_endpoints_defined(self):
        """Verify streaming endpoints are properly defined."""
        assert "/runs/stream" in STREAMING_ENDPOINTS
        assert "/runs/wait" in STREAMING_ENDPOINTS

    def test_run_create_endpoints_defined(self):
        """Verify run creation endpoints are properly defined."""
        assert "/runs" in RUN_CREATE_ENDPOINTS
