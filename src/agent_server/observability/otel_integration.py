"""OpenTelemetry integration for Open LangGraph Platform.

This module provides OpenTelemetry tracing setup with OTLP export,
FastAPI auto-instrumentation, and HTTPX client instrumentation.

환경 변수:
    OTEL_ENABLED: OpenTelemetry 활성화 여부 (기본값: false)
    OTEL_EXPORTER_OTLP_ENDPOINT: OTLP 수집기 엔드포인트 (기본값: http://localhost:4317)
    OTEL_SERVICE_NAME: 서비스 이름 (기본값: open-langgraph)
    OTEL_SERVICE_VERSION: 서비스 버전 (기본값: 0.1.0)
    OTEL_DEPLOYMENT_ENVIRONMENT: 배포 환경 (기본값: development)
    OTEL_INSECURE: 비보안 연결 사용 여부 (기본값: true)

사용 예:
    ```python
    from fastapi import FastAPI
    from src.agent_server.observability.otel_integration import setup_opentelemetry

    app = FastAPI()
    setup_opentelemetry(app)
    ```

참고:
    - OpenTelemetry 의존성이 설치되어 있어야 함 (`pip install open-langgraph-platform[otel]`)
    - OTEL_ENABLED=true로 설정해야 활성화됨
    - 의존성이 없거나 비활성화된 경우 graceful하게 무시됨
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

# 환경 변수 기본값
_OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"
_OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
_OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "open-langgraph")
_OTEL_SERVICE_VERSION = os.getenv("OTEL_SERVICE_VERSION", "0.1.0")
_OTEL_ENVIRONMENT = os.getenv("OTEL_DEPLOYMENT_ENVIRONMENT", "development")
_OTEL_INSECURE = os.getenv("OTEL_INSECURE", "true").lower() == "true"

# 전역 상태: 초기화 여부 추적
_otel_initialized = False


def is_otel_enabled() -> bool:
    """OpenTelemetry 활성화 여부를 반환합니다.

    Returns:
        bool: OTEL_ENABLED 환경 변수가 "true"이면 True
    """
    return _OTEL_ENABLED


def is_otel_initialized() -> bool:
    """OpenTelemetry가 성공적으로 초기화되었는지 반환합니다.

    Returns:
        bool: 초기화 성공 여부
    """
    return _otel_initialized


def get_tracer(name: str = __name__) -> Any:
    """OpenTelemetry tracer를 반환합니다.

    OpenTelemetry가 활성화되지 않았거나 초기화되지 않은 경우
    no-op tracer를 반환합니다.

    Args:
        name: Tracer 이름 (일반적으로 모듈명)

    Returns:
        Tracer 인스턴스 (또는 no-op tracer)
    """
    if not _otel_initialized:
        # Return a no-op tracer if not initialized
        try:
            from opentelemetry import trace

            return trace.get_tracer(name)
        except ImportError:
            return _NoOpTracer()

    from opentelemetry import trace

    return trace.get_tracer(name)


class _NoOpTracer:
    """OpenTelemetry가 설치되지 않은 경우를 위한 No-op tracer."""

    def start_span(self, name: str, **kwargs) -> "_NoOpSpan":
        """No-op span을 반환합니다."""
        return _NoOpSpan()

    def start_as_current_span(self, name: str, **kwargs) -> "_NoOpSpanContextManager":
        """No-op context manager를 반환합니다."""
        return _NoOpSpanContextManager()


class _NoOpSpan:
    """No-op span 구현."""

    def end(self, **kwargs) -> None:
        """No-op."""
        pass

    def set_attribute(self, key: str, value) -> None:
        """No-op."""
        pass

    def set_status(self, status, description=None) -> None:
        """No-op."""
        pass

    def record_exception(self, exception, **kwargs) -> None:
        """No-op."""
        pass

    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, *args) -> None:
        pass


class _NoOpSpanContextManager:
    """No-op span context manager."""

    def __enter__(self) -> "_NoOpSpan":
        return _NoOpSpan()

    def __exit__(self, *args) -> None:
        pass


def setup_opentelemetry(app: FastAPI) -> bool:
    """OpenTelemetry를 설정하고 FastAPI 앱에 계측을 적용합니다.

    이 함수는 다음을 수행합니다:
    1. OTEL_ENABLED 환경 변수 확인
    2. 필요한 OpenTelemetry 패키지 임포트 시도
    3. Resource (서비스 메타데이터) 정의
    4. TracerProvider 설정
    5. OTLP gRPC Exporter 연결
    6. BatchSpanProcessor 설정 (성능 최적화)
    7. FastAPIInstrumentor 적용 (HTTP 요청/응답 자동 추적)
    8. HTTPXClientInstrumentor 적용 (A2A/Federation 호출 추적)

    Args:
        app: FastAPI 애플리케이션 인스턴스

    Returns:
        bool: 초기화 성공 여부

    Example:
        ```python
        app = FastAPI()
        if setup_opentelemetry(app):
            logger.info("OpenTelemetry configured successfully")
        ```
    """
    global _otel_initialized

    # 비활성화 상태 확인
    if not _OTEL_ENABLED:
        logger.debug("OpenTelemetry is disabled (OTEL_ENABLED != true)")
        return False

    # 이미 초기화된 경우
    if _otel_initialized:
        logger.debug("OpenTelemetry already initialized")
        return True

    try:
        # OpenTelemetry 패키지 임포트
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as e:
        logger.warning(
            "OpenTelemetry is enabled (OTEL_ENABLED=true), but required packages are not installed. "
            "Please install with: pip install open-langgraph-platform[otel]. "
            f"Missing module: {e.name}"
        )
        return False

    try:
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 1. Resource 정의: 서비스 메타데이터
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        resource = Resource.create({
            "service.name": _OTEL_SERVICE_NAME,
            "service.version": _OTEL_SERVICE_VERSION,
            "deployment.environment": _OTEL_ENVIRONMENT,
            "telemetry.sdk.language": "python",
        })

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 2. TracerProvider 설정
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        provider = TracerProvider(resource=resource)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 3. OTLP gRPC Exporter 설정
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        otlp_exporter = OTLPSpanExporter(
            endpoint=_OTEL_ENDPOINT,
            insecure=_OTEL_INSECURE,
        )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 4. BatchSpanProcessor 추가 (성능 최적화)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # BatchSpanProcessor는 span을 버퍼에 모아서 일괄 전송
        # - 네트워크 오버헤드 감소
        # - 애플리케이션 성능에 미치는 영향 최소화
        processor = BatchSpanProcessor(otlp_exporter)
        provider.add_span_processor(processor)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 5. 전역 TracerProvider 설정
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        trace.set_tracer_provider(provider)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 6. FastAPI 자동 계측
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 모든 HTTP 요청/응답을 자동으로 추적
        # - 요청 메서드, 경로, 상태 코드
        # - 요청 시작/종료 시간
        # - 예외 정보
        FastAPIInstrumentor.instrument_app(app)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 7. HTTPX 클라이언트 계측
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # A2A/Federation 호출 등 외부 HTTP 호출 추적
        HTTPXClientInstrumentor().instrument()

        _otel_initialized = True
        logger.info(
            f"OpenTelemetry initialized: service={_OTEL_SERVICE_NAME}, "
            f"version={_OTEL_SERVICE_VERSION}, "
            f"endpoint={_OTEL_ENDPOINT}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}")
        return False


def shutdown_opentelemetry() -> None:
    """OpenTelemetry를 정리합니다.

    애플리케이션 종료 시 호출하여 남은 span을 플러시하고
    리소스를 정리합니다.
    """
    global _otel_initialized

    if not _otel_initialized:
        return

    try:
        from opentelemetry import trace

        provider = trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()
        _otel_initialized = False
        logger.info("OpenTelemetry shutdown complete")
    except Exception as e:
        logger.error(f"Error during OpenTelemetry shutdown: {e}")
