"""Rate Limiter 핵심 모듈

이 모듈은 SlowAPI 기반의 Rate Limiting 인프라를 제공합니다.
Redis 백엔드를 사용하여 분산 환경에서 일관된 rate limiting을 지원합니다.

주요 특징:
- Optional Redis: Redis 없으면 rate limiting 비활성화 (graceful degradation)
- 다양한 키 전략: IP, User, Org 기반 rate limiting
- SlowAPI 통합: FastAPI/Starlette 미들웨어 및 데코레이터 지원
- 응답 헤더: X-RateLimit-* 헤더 자동 추가

사용법:
    # 초기화 (FastAPI lifespan에서)
    await rate_limiter.initialize()

    # 엔드포인트 데코레이터
    @router.post("/runs")
    @limiter.limit("500/hour", key_func=get_org_rate_limit_key)
    async def create_run(...):
        ...
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Any

from fastapi import Request

from .cache import cache_manager

if TYPE_CHECKING:
    from slowapi import Limiter

# SlowAPI 선택적 import (Redis optional-dependency에 포함)
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False
    Limiter = None  # type: ignore
    RateLimitExceeded = Exception  # type: ignore

    def _rate_limit_exceeded_handler(*args: Any, **kwargs: Any) -> Any:
        """Fallback handler"""
        pass


def get_remote_address(request: Request) -> str:
    """Extract client IP address from request, handling X-Forwarded-For safely.

    Security Note:
    - Most load balancers APPEND the real client IP to X-Forwarded-For
    - Taking the RIGHTMOST IP prevents spoofing via fake X-Forwarded-For headers
    - For direct connections without proxy, uses request.client.host

    This replaces SlowAPI's get_remote_address which may be susceptible to
    IP spoofing if X-Forwarded-For is not validated against trusted proxies.

    Args:
        request: FastAPI Request object

    Returns:
        Client IP address string
    """
    try:
        # Check X-Forwarded-For header first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take LAST IP in chain (rightmost) - this is what trusted load balancers add
            # This prevents spoofing via fake X-Forwarded-For headers injected by clients
            ips = forwarded_for.split(",")
            for ip in reversed(ips):
                cleaned = ip.strip()
                if cleaned:
                    return cleaned

        # Fall back to direct client connection
        client = getattr(request, "client", None)
        if client and client.host:
            return client.host

    except Exception:
        pass

    return "unknown"


logger = logging.getLogger(__name__)


# =============================================================================
# 환경 변수 기반 설정
# =============================================================================

RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_STORAGE = os.getenv("RATE_LIMIT_STORAGE", "redis")
RATE_LIMIT_DEFAULT_PER_HOUR = int(os.getenv("RATE_LIMIT_DEFAULT_PER_HOUR", "5000"))
RATE_LIMIT_ANON_PER_HOUR = int(os.getenv("RATE_LIMIT_ANON_PER_HOUR", "1000"))
RATE_LIMIT_STREAMING_PER_HOUR = int(os.getenv("RATE_LIMIT_STREAMING_PER_HOUR", "100"))
RATE_LIMIT_RUNS_PER_HOUR = int(os.getenv("RATE_LIMIT_RUNS_PER_HOUR", "500"))
# SECURITY: Default to "error" (fail-closed) for safety.
# "skip" allows all requests when Redis fails - use only if availability > security.
RATE_LIMIT_FALLBACK = os.getenv("RATE_LIMIT_FALLBACK", "error")  # error (default) or skip

# Lua script for atomic INCR + EXPIRE
# This prevents race conditions where TTL could fail to be set
INCR_WITH_EXPIRE_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


# =============================================================================
# 키 추출 함수
# =============================================================================


def get_rate_limit_key(request: Request) -> str:
    """요청에서 Rate Limit 키 추출

    인증된 사용자의 경우 user_id를, 비인증 사용자의 경우 IP 주소를 반환합니다.

    Args:
        request: FastAPI Request 객체

    Returns:
        Rate limit 키 (예: "user:abc123" 또는 "ip:192.168.1.1")
    """
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        identity = getattr(user, "identity", None)
        if identity:
            return f"user:{identity}"
    return f"ip:{get_remote_address(request)}"


def get_org_rate_limit_key(request: Request) -> str:
    """요청에서 조직 기반 Rate Limit 키 추출

    인증된 사용자의 경우:
    - org_id가 있으면 조직 기준으로 제한
    - org_id가 없으면 사용자 기준으로 제한
    비인증 사용자의 경우 IP 주소를 사용합니다.

    Args:
        request: FastAPI Request 객체

    Returns:
        Rate limit 키 (예: "org:org123", "user:abc123", 또는 "ip:192.168.1.1")
    """
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        # 조직 ID가 있으면 조직 기준으로 제한
        org_id = getattr(user, "org_id", None)
        if org_id:
            return f"org:{org_id}"
        # 조직이 없으면 사용자 기준
        identity = getattr(user, "identity", None)
        if identity:
            return f"user:{identity}"
    return f"ip:{get_remote_address(request)}"


def get_streaming_rate_limit_key(request: Request) -> str:
    """스트리밍 엔드포인트용 Rate Limit 키 추출

    스트리밍 작업은 리소스 소비가 크므로 별도로 관리합니다.
    키에 "stream:" 프리픽스를 추가하여 일반 요청과 분리합니다.

    Args:
        request: FastAPI Request 객체

    Returns:
        Rate limit 키 (예: "stream:org:org123")
    """
    base_key = get_org_rate_limit_key(request)
    return f"stream:{base_key}"


# =============================================================================
# In-Memory Rate Limiter (Fallback)
# =============================================================================


class InMemoryRateLimiter:
    """Simple in-memory rate limiter for fallback when Redis unavailable.

    Uses a fixed-window algorithm with per-key counters.
    Thread-safe for multi-worker scenarios.

    Limitations:
    - Not distributed (per-process only)
    - Memory bounded by max_keys parameter
    - Less accurate than Redis sliding window
    """

    def __init__(self, max_keys: int = 10000) -> None:
        import threading

        self._counters: dict[str, tuple[int, float]] = {}  # key -> (count, window_start)
        self._lock = threading.Lock()
        self._max_keys = max_keys

    def check_and_increment(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> tuple[bool, int, int]:
        """Check rate limit and increment counter.

        Args:
            key: Rate limit key
            limit: Maximum requests per window
            window: Window size in seconds

        Returns:
            (allowed, remaining, reset_at) tuple
        """
        now = time.time()
        reset_at = int(now) + window

        with self._lock:
            # Cleanup if over capacity
            if len(self._counters) > self._max_keys:
                self._cleanup_expired(now)

            # Get or create counter
            if key in self._counters:
                count, window_start = self._counters[key]
                # Check if window expired
                if now - window_start >= window:
                    # New window
                    self._counters[key] = (1, now)
                    return True, limit - 1, reset_at
                else:
                    # Same window
                    new_count = count + 1
                    self._counters[key] = (new_count, window_start)
                    remaining = max(0, limit - new_count)
                    return new_count <= limit, remaining, int(window_start) + window
            else:
                # First request
                self._counters[key] = (1, now)
                return True, limit - 1, reset_at

    def _cleanup_expired(self, now: float) -> None:
        """Remove expired entries to prevent memory growth."""
        expired_keys = [
            k
            for k, (_, start) in self._counters.items()
            if now - start > 3600  # 1 hour max retention
        ]
        for k in expired_keys[: len(self._counters) // 2]:  # Remove at most half
            self._counters.pop(k, None)

    def reset(self) -> None:
        """Clear all counters."""
        with self._lock:
            self._counters.clear()


# =============================================================================
# Rate Limiter Manager
# =============================================================================


class RateLimiterManager:
    """Rate Limiter 관리자

    SlowAPI와 Redis를 통합하여 분산 rate limiting을 제공합니다.
    Redis가 없는 경우 rate limiting을 비활성화합니다 (graceful degradation).

    Attributes:
        limiter: SlowAPI Limiter 인스턴스
        is_available: Rate limiting 활성화 여부
    """

    # Rate limit 윈도우별 TTL (캐시용)
    TTL_RATE_LIMIT = 3600  # 1시간 윈도우
    TTL_RATE_LIMIT_MINUTE = 60  # 1분 윈도우

    def __init__(self) -> None:
        self._limiter: Limiter | None = None
        self._is_available = False
        self._redis_available = False
        self._fallback_limiter: InMemoryRateLimiter | None = None
        self._using_fallback = False
        self._incr_script: Any = None  # Registered Lua script

    async def initialize(self) -> None:
        """Rate Limiter 초기화

        Redis와 SlowAPI가 모두 사용 가능한 경우에만 rate limiting을 활성화합니다.
        """
        if not RATE_LIMIT_ENABLED:
            logger.info("ℹ️  Rate limiting disabled by configuration")
            return

        if not SLOWAPI_AVAILABLE:
            logger.warning('⚠️  SlowAPI package not installed - run: uv pip install ".[redis]"')
            return

        # Redis 가용성 확인
        self._redis_available = cache_manager.is_available

        if not self._redis_available:
            if RATE_LIMIT_FALLBACK == "skip":
                logger.warning("⚠️  Rate limiting disabled - Redis unavailable (fallback=skip)")
                return
            else:
                # Initialize in-memory fallback instead of disabling
                logger.warning("⚠️  Redis unavailable - using in-memory rate limiting fallback")
                self._fallback_limiter = InMemoryRateLimiter()
                self._using_fallback = True
                self._is_available = True  # Enable rate limiting with fallback
                return

        try:
            # SlowAPI Limiter 생성 (Redis 스토리지 사용)
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            self._limiter = Limiter(
                key_func=get_rate_limit_key,
                storage_uri=redis_url,
                strategy="moving-window",
                headers_enabled=True,
            )
            self._is_available = True
            logger.info("✅ Rate limiter initialized with Redis backend")

            # Register Lua script for atomic operations
            try:
                client = cache_manager._client
                if client:
                    self._incr_script = client.register_script(INCR_WITH_EXPIRE_SCRIPT)
                    logger.debug("✅ Registered atomic increment Lua script")
            except Exception as e:
                logger.warning(f"⚠️  Failed to register Lua script, using fallback: {e}")
                self._incr_script = None

            # Always create fallback limiter as backup for Redis errors
            self._fallback_limiter = InMemoryRateLimiter()

        except Exception as e:
            logger.error(f"❌ Rate limiter initialization failed: {e}")
            self._limiter = None
            self._is_available = False

    async def close(self) -> None:
        """Rate Limiter 정리"""
        self._limiter = None
        self._is_available = False
        self._redis_available = False
        self._incr_script = None
        if self._fallback_limiter:
            self._fallback_limiter.reset()
            self._fallback_limiter = None
        self._using_fallback = False

    @property
    def is_available(self) -> bool:
        """Rate limiting이 활성화되어 있는지 확인"""
        return self._is_available

    @property
    def limiter(self) -> Limiter | None:
        """SlowAPI Limiter 인스턴스 반환"""
        return self._limiter

    # ==================== Rate Limit 체크 ====================

    async def check_limit(
        self,
        key: str,
        limit: int,
        window: int = 3600,
    ) -> tuple[bool, int, int]:
        """Rate limit 체크 및 카운터 증가

        Args:
            key: Rate limit 키 (예: "org:abc123")
            limit: 최대 요청 수
            window: 시간 윈도우 (초), 기본 1시간

        Returns:
            (allowed, remaining, reset_at) 튜플
            - allowed: 요청 허용 여부
            - remaining: 남은 요청 수
            - reset_at: 리셋 타임스탬프 (Unix)
        """
        if not self._is_available:
            # Rate limiting 비활성화 시 모든 요청 허용
            return True, limit, int(time.time()) + window

        # Use in-memory fallback if Redis unavailable
        if self._using_fallback and self._fallback_limiter:
            return self._fallback_limiter.check_and_increment(key, limit, window)

        # Redis에서 현재 카운터 확인 및 증가
        counter_key = f"rate_limit:{key}:{window}"
        try:
            current = await self._increment_counter(counter_key, window)
            remaining = max(0, limit - current)
            allowed = current <= limit
            reset_at = int(time.time()) + window
            return allowed, remaining, reset_at
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fallback to in-memory on Redis error
            if self._fallback_limiter:
                logger.warning("Using in-memory fallback due to Redis error")
                return self._fallback_limiter.check_and_increment(key, limit, window)
            # SECURITY FIX: Fail-closed by default - deny requests on Redis errors
            # Set RATE_LIMIT_FALLBACK=skip to allow requests (fail-open) if needed
            if RATE_LIMIT_FALLBACK == "skip":
                logger.warning("Rate limit fallback=skip: allowing request despite Redis error")
                return True, limit, int(time.time()) + window
            else:
                # Default: fail-closed - deny the request
                logger.warning("Rate limit fallback=error: denying request due to Redis error")
                return False, 0, int(time.time()) + window

    async def _increment_counter(self, key: str, ttl: int) -> int:
        """Redis 카운터 증가 (Lua 스크립트로 원자적 연산)

        Args:
            key: 카운터 키
            ttl: 만료 시간 (초)

        Returns:
            증가 후 카운터 값
        """
        if not cache_manager.is_available:
            return 0

        try:
            client = cache_manager._client
            if not client:
                return 0

            # Use Lua script for atomic INCR + EXPIRE
            if self._incr_script:
                result = await self._incr_script(keys=[key], args=[ttl])
                return int(result)

            # Fallback: Original non-atomic approach (legacy compatibility)
            current = await client.incr(key)
            if current == 1:
                await client.expire(key, ttl)
            return int(current)

        except Exception as e:
            logger.error(f"Counter increment failed: {e}")
            return 0

    async def get_usage(
        self,
        key: str,
        window: int = 3600,
    ) -> int:
        """현재 사용량 조회

        Args:
            key: Rate limit 키
            window: 시간 윈도우 (초)

        Returns:
            현재 카운터 값
        """
        if not cache_manager.is_available:
            return 0

        counter_key = f"rate_limit:{key}:{window}"
        try:
            client = cache_manager._client
            if not client:
                return 0

            value = await client.get(counter_key)
            return int(value) if value else 0
        except Exception:
            return 0

    async def get_ttl(
        self,
        key: str,
        window: int = 3600,
    ) -> int:
        """카운터 TTL 조회

        Args:
            key: Rate limit 키
            window: 시간 윈도우 (초)

        Returns:
            남은 TTL (초), 키가 없으면 -1
        """
        if not cache_manager.is_available:
            return -1

        counter_key = f"rate_limit:{key}:{window}"
        try:
            client = cache_manager._client
            if not client:
                return -1

            ttl = await client.ttl(counter_key)
            return ttl if ttl > 0 else -1
        except Exception:
            return -1

    async def reset_limit(self, key: str, window: int = 3600) -> bool:
        """Rate limit 카운터 리셋

        Args:
            key: Rate limit 키
            window: 시간 윈도우 (초)

        Returns:
            성공 여부
        """
        if not cache_manager.is_available:
            return False

        counter_key = f"rate_limit:{key}:{window}"
        return await cache_manager.delete(counter_key)


# =============================================================================
# 전역 싱글톤 인스턴스
# =============================================================================

rate_limiter = RateLimiterManager()

# SlowAPI 관련 export (미들웨어/라우터에서 사용)
__all__ = [
    "rate_limiter",
    "get_rate_limit_key",
    "get_org_rate_limit_key",
    "get_streaming_rate_limit_key",
    "get_remote_address",
    "RateLimitExceeded",
    "_rate_limit_exceeded_handler",
    "SLOWAPI_AVAILABLE",
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_FALLBACK",
    "RATE_LIMIT_DEFAULT_PER_HOUR",
    "RATE_LIMIT_ANON_PER_HOUR",
    "RATE_LIMIT_STREAMING_PER_HOUR",
    "RATE_LIMIT_RUNS_PER_HOUR",
    "InMemoryRateLimiter",
    "RateLimiterManager",
]
