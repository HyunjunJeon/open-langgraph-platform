"""Open LangGraph 메인 FastAPI 애플리케이션 엔트리포인트

이 모듈은 Open LangGraph Agent Protocol 서버의 핵심 FastAPI 애플리케이션을 정의합니다.
LangGraph 기반 에이전트를 HTTP API로 노출하며, Agent Protocol 표준을 준수합니다.

애플리케이션 아키텍처:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 미들웨어 스택 (요청 처리 순서):
   ├─ Audit 미들웨어: 감사 로그 수집 (outbox 패턴)
   ├─ RateLimit 미들웨어: 요청 속도 제한 (Redis 기반)
   ├─ Authentication 미들웨어: LangGraph SDK 기반 사용자 인증
   ├─ DoubleEncodedJSON 미들웨어: 프론트엔드 이중 인코딩 처리
   └─ CORS 미들웨어: 교차 출처 리소스 공유 설정

2. 라우터 구조 (API 엔드포인트):
   ├─ /health: 서버 및 데이터베이스 상태 확인
   ├─ /assistants: 어시스턴트(그래프) 관리
   ├─ /threads: 대화 스레드 관리
   ├─ /runs: 에이전트 실행 및 스트리밍
   ├─ /store: LangGraph Store 장기 메모리
   ├─ /organizations: 조직 멀티테넌시 관리 (RBAC 포함)
   ├─ /organizations/{org_id}/quotas: 쿼터 및 Rate Limit 관리
   └─ /a2a: A2A (Agent-to-Agent) Protocol 통신

3. 라이프사이클 관리:
   ├─ Startup: 데이터베이스, LangGraph 서비스, 이벤트 저장소 초기화
   └─ Shutdown: 실행 중인 작업 취소, 리소스 정리

주요 구성 요소:
• lifespan() - 애플리케이션 수명 주기 관리 (시작/종료)
• active_runs - 취소 가능한 실행 추적용 Task 딕셔너리
• 전역 예외 핸들러 - Agent Protocol 오류 형식 변환

사용 예:
    # 개발 서버 실행
    uvicorn src.agent_server.main:app --reload

    # 프로덕션 실행 (포트 지정)
    PORT=8000 uvicorn src.agent_server.main:app

	참고:
	    - LangGraph 그래프는 open_langgraph.json에서 정의
	    - 인증 설정은 auth.py 및 환경변수(AUTH_TYPE)로 제어
	    - 데이터베이스 마이그레이션은 Alembic(`alembic/`, `alembic.ini`)으로 관리
"""

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
# 데이터베이스 URL, 인증 설정 등 애플리케이션 설정을 불러옴
load_dotenv()

# graphs/ 디렉토리를 Python 경로에 추가하여 그래프 모듈 임포트 가능하게 설정
# 주의: 이 작업은 graphs/ 경로를 사용하는 모듈을 임포트하기 전에 반드시 수행되어야 함
# open_langgraph.json에 정의된 그래프들이 동적으로 임포트되려면 sys.path에 등록 필요
current_dir = Path(__file__).parent.parent.parent  # open-langgraph 루트 디렉토리로 이동
graphs_dir = current_dir / "graphs"
if str(graphs_dir) not in sys.path:
    sys.path.insert(0, str(graphs_dir))

# ruff: noqa: E402 - 아래 임포트들은 위의 sys.path 수정 이후에 실행되어야 함
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.authentication import AuthenticationMiddleware

from .a2a.router import router as a2a_router
from .api.agent_auth import router as agent_auth_router
from .api.agents import router as agents_router
from .api.assistants import router as assistants_router
from .api.audit import router as audit_router
from .api.crons import router as crons_router
from .api.feature_flags import router as feature_flags_router
from .api.organizations import router as organizations_router
from .api.quotas import router as quotas_router
from .api.rate_limit_rules import router as rate_limit_rules_router
from .api.rbac import router as rbac_router
from .api.runs import router as runs_router
from .api.runs_standalone import router as runs_standalone_router
from .api.store import router as store_router
from .api.threads import router as threads_router
from .core.auth_middleware import get_auth_backend, on_auth_error
from .core.cache import cache_manager
from .core.database import db_manager
from .core.health import router as health_router
from .core.rate_limiter import rate_limiter
from .middleware import AuditMiddleware, DoubleEncodedJSONMiddleware, RateLimitMiddleware
from .models.errors import AgentProtocolError, get_error_type

# ---------------------------------------------------------------------------
# 전역 상태: 실행 중인 에이전트 태스크 관리
# ---------------------------------------------------------------------------
# 실행 취소를 위해 활성 실행(run)의 asyncio.Task를 추적
# key: run_id (문자열), value: 해당 실행을 수행하는 asyncio.Task
# Shutdown 시 완료되지 않은 작업들을 취소하는 데 사용됨
active_runs: dict[str, asyncio.Task] = {}

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:  # noqa: C901
    """FastAPI 애플리케이션 수명 주기(lifespan) 관리 컨텍스트 매니저

    애플리케이션 시작 시 필요한 모든 초기화 작업을 수행하고,
    종료 시 리소스를 안전하게 정리합니다.

    시작(Startup) 시퀀스:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    1. 데이터베이스 매니저 초기화
       - SQLAlchemy 엔진 생성 (Agent Protocol 메타데이터)
       - LangGraph AsyncPostgresSaver 초기화 (체크포인트 저장소)
       - LangGraph AsyncPostgresStore 초기화 (장기 메모리)
       - 데이터베이스 스키마 자동 생성 (.setup() 호출)

    2. Redis 캐시 초기화 (Optional)
       - REDIS_URL 환경변수가 있으면 Redis 연결
       - 없으면 캐싱 비활성화 (graceful degradation)

    3. LangGraph 서비스 초기화
       - open_langgraph.json에서 그래프 정의 로드
       - 각 그래프에 대한 기본 어시스턴트 생성 (UUID5 기반)
       - 그래프 캐싱 시스템 준비

    4. 이벤트 저장소 정리 작업 시작
       - 오래된 SSE 이벤트 자동 삭제를 위한 백그라운드 태스크 시작
       - 기본 7일 이상 경과한 이벤트 정리

    종료(Shutdown) 시퀀스:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    1. 활성 실행 취소
       - active_runs에 등록된 모든 실행 중인 태스크 취소
       - 진행 중인 에이전트 실행의 graceful shutdown 보장

    2. 이벤트 저장소 정리 작업 중지
       - 백그라운드 정리 태스크 안전하게 종료

    3. 데이터베이스 연결 정리
       - SQLAlchemy 엔진 종료
       - LangGraph 컴포넌트 연결 해제

    Args:
        _app (FastAPI): FastAPI 애플리케이션 인스턴스 (사용하지 않음)

    Yields:
        None: 컨텍스트 매니저 프로토콜에 따라 yield로 제어 반환

    참고:
        - FastAPI 0.109.0+에서 권장하는 lifespan 패턴 사용
        - 이전의 @app.on_event("startup")/on_event("shutdown") 대체
        - 비동기 컨텍스트 매니저로 예외 안전성 보장
    """
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Startup: OpenTelemetry 초기화 (가장 먼저 실행)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # OpenTelemetry는 다른 컴포넌트 초기화 전에 설정해야 모든 요청이 추적됨
    from .observability.otel_integration import setup_opentelemetry

    setup_opentelemetry(_app)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Startup: 데이터베이스 및 LangGraph 컴포넌트 초기화
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    await db_manager.initialize()

    # Redis 캐시 초기화 (Optional - 없으면 캐싱 비활성화)
    await cache_manager.initialize()

    # Rate Limiter 초기화 (Optional - Redis 없으면 비활성화)
    await rate_limiter.initialize()

    # LangGraph 서비스 초기화
    # open_langgraph.json에서 그래프 정의 로드 및 기본 어시스턴트 생성
    from .services.langgraph_service import get_langgraph_service

    langgraph_service = get_langgraph_service()
    await langgraph_service.initialize()

    # Custom endpoint 서비스 초기화 및 라우트 등록
    from .services.custom_endpoint_service import get_custom_endpoint_service

    custom_endpoint_service = get_custom_endpoint_service()
    custom_endpoint_service.initialize()
    custom_endpoint_service.register_routes(_app)

    # 이벤트 저장소 백그라운드 정리 작업 시작
    # 오래된 SSE 이벤트를 주기적으로 삭제하여 디스크 공간 관리
    from .services.event_store import event_store

    await event_store.start_cleanup_task()

    # TTL 만료 스레드 정리 작업 시작
    # 1시간마다 expires_at이 지난 스레드를 삭제/아카이브
    from .services.thread_cleanup_service import thread_cleanup_service

    await thread_cleanup_service.start()

    # Cron 스케줄러 서비스 시작
    # 60초마다 예약된 cron 작업 확인 및 실행
    from .services.cron_scheduler_service import cron_scheduler_service

    await cron_scheduler_service.start()

    # 감사 로그 Outbox 배치 이동 작업 시작
    # outbox 테이블에서 파티션 테이블로 주기적으로 이동
    from .services.audit_outbox_service import audit_outbox_service

    await audit_outbox_service.start_mover()

    # 감사 로그 파티션 자동 생성 (향후 3개월 파티션 확보)
    # 파티션이 없으면 INSERT가 실패하므로 시작 시 확보 필수
    from .services.partition_service import partition_service

    try:
        await partition_service.ensure_future_partitions(months_ahead=3)
    except Exception as e:
        logger.warning("Failed to ensure audit log partitions: %s", e)

    yield

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Shutdown: 리소스 정리 및 활성 작업 취소
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # 완료되지 않은 모든 실행 작업 취소
    # graceful shutdown을 위해 각 태스크에 취소 신호 전송
    for task in active_runs.values():
        if not task.done():
            task.cancel()

    # OpenTelemetry 종료 (남은 span 플러시)
    from .observability.otel_integration import shutdown_opentelemetry

    shutdown_opentelemetry()

    # 감사 로그 Outbox 배치 이동 작업 중지 (남은 레코드 플러시)
    await audit_outbox_service.stop_mover()

    # 이벤트 저장소 정리 작업 중지
    await event_store.stop_cleanup_task()

    # TTL 스레드 정리 작업 중지
    await thread_cleanup_service.stop()

    # Cron 스케줄러 서비스 중지
    await cron_scheduler_service.stop()

    # Rate Limiter 정리
    await rate_limiter.close()

    # Redis 캐시 연결 종료
    await cache_manager.close()

    # 데이터베이스 연결 종료
    await db_manager.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FastAPI 애플리케이션 인스턴스 생성
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
app = FastAPI(
    title="Open LangGraph",
    description="Open LangGraph: Production-ready Agent Protocol server built on LangGraph",
    version="0.1.0",
    docs_url="/docs",  # Swagger UI 자동 문서: http://localhost:8000/docs
    redoc_url="/redoc",  # ReDoc 문서: http://localhost:8000/redoc
    lifespan=lifespan,  # 애플리케이션 수명 주기 관리 함수
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 미들웨어 스택 구성 (역순으로 추가 = 실행은 정순)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 주의: FastAPI 미들웨어는 추가한 역순으로 실행됨
# 추가 순서: CORS → DoubleEncodedJSON → Authentication → RateLimit → Audit
# 실행 순서: Audit → RateLimit → Authentication → DoubleEncodedJSON → CORS → 라우터

# 1. CORS 미들웨어: 교차 출처 리소스 공유 설정
# 프론트엔드가 다른 도메인에서 API를 호출할 수 있도록 허용
# SECURITY: CORS 설정은 환경변수로 제어됨
# - CORS_ORIGINS: 허용할 도메인 목록 (쉼표 구분, 기본값: 비어있음 = 차단)
# - CORS_ALLOW_CREDENTIALS: 자격 증명 허용 여부 (기본값: false)
# - CORS_ALLOW_ALL: "*" 허용 여부 - 개발 전용! (기본값: false)
_cors_origins_str = os.getenv("CORS_ORIGINS", "")
_cors_allow_all = os.getenv("CORS_ALLOW_ALL", "false").lower() == "true"
_cors_allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"

# SECURITY: allow_origins=["*"]와 allow_credentials=True는 함께 사용하면 안됨
# 브라우저가 이 조합을 거부하고, 보안상 위험함
if _cors_allow_all:
    # 개발 환경에서만 사용해야 함
    _env = os.getenv("ENVIRONMENT", "development").lower()
    if _env not in ("development", "dev", "test", "testing", "local"):
        logger.warning(
            "⚠️  SECURITY WARNING: CORS_ALLOW_ALL=true in non-development environment (%s). "
            "This allows requests from ANY origin. Set CORS_ORIGINS explicitly for production.",
            _env,
        )
    _cors_origins: list[str] = ["*"]
    # SECURITY FIX: credentials와 "*"는 함께 사용 불가
    _cors_allow_credentials = False
elif _cors_origins_str:
    _cors_origins = [origin.strip() for origin in _cors_origins_str.split(",") if origin.strip()]
else:
    # 기본값: 빈 목록 = CORS 요청 차단 (보안 기본값)
    _cors_origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],  # 명시적 메서드
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],  # 명시적 헤더
)

# 2. DoubleEncodedJSON 미들웨어: 프론트엔드의 이중 인코딩 처리
# 일부 프론트엔드 클라이언트가 JSON을 두 번 인코딩하는 경우 자동 디코딩
app.add_middleware(DoubleEncodedJSONMiddleware)

# 3. Authentication 미들웨어: LangGraph SDK 기반 사용자 인증
# 주의: CORS 이후에 추가되어야 preflight 요청 처리 가능
# 모든 요청에서 Authorization 헤더 검증 후 request.user 설정
app.add_middleware(AuthenticationMiddleware, backend=get_auth_backend(), on_error=on_auth_error)

# 4. Rate Limit 미들웨어: 요청 속도 제한
# Authentication 이후에 실행되어 user.org_id 기반 제한 가능
# Redis 없으면 비활성화 (graceful degradation)
app.add_middleware(RateLimitMiddleware)

# 5. Audit 미들웨어: 감사 로그 수집
# 모든 요청을 감시하고 outbox 테이블에 로그 기록
# Rate limit 응답 포함 모든 요청 기록
app.add_middleware(AuditMiddleware)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API 라우터 등록 (Agent Protocol 엔드포인트)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 각 라우터는 Agent Protocol 표준을 따르는 HTTP 엔드포인트 제공

# /health - 서버 상태 확인 및 데이터베이스 연결 테스트
app.include_router(health_router, prefix="", tags=["Health"])

# /assistants - 어시스턴트(그래프) 목록 조회 및 생성
# open_langgraph.json에 정의된 그래프들이 어시스턴트로 노출됨
app.include_router(assistants_router, prefix="", tags=["Assistants"])

# /agents - Agent Protocol v0.2.0 호환 에이전트 엔드포인트
# /assistants의 별칭으로, capabilities 필드 추가
app.include_router(agents_router, prefix="", tags=["Agents"])

# /threads - 대화 스레드 생성, 조회, 수정, 삭제 (CRUD)
# LangGraph 체크포인트 기반 대화 상태 관리
# Agent Protocol v0.2.0: /threads/{id}/copy 엔드포인트 포함
app.include_router(threads_router, prefix="", tags=["Threads"])

# /runs - 에이전트 실행 및 실시간 스트리밍 (레거시 경로)
# SSE(Server-Sent Events)를 통한 스트리밍 지원
# 경로: /threads/{thread_id}/runs/*
app.include_router(runs_router, prefix="", tags=["Runs"])

# /runs - Agent Protocol v0.2.0 호환 standalone 실행 엔드포인트
# thread_id를 body에서 받으며, stateless 실행 지원
# 경로: /runs/* (thread_id는 body에)
app.include_router(runs_standalone_router, prefix="", tags=["Runs (Standalone)"])

# /store - LangGraph Store를 통한 장기 메모리 관리
# 사용자별, 스레드별 영구 데이터 저장소 (JSONB)
# Agent Protocol v0.2.0: /store/namespaces 엔드포인트 포함
app.include_router(store_router, prefix="", tags=["Store"])

# /crons - 스케줄된 실행(Cron) 관리
# 정기적인 에이전트 실행을 위한 스케줄링 기능
app.include_router(crons_router, prefix="", tags=["Crons"])

# /organizations - 조직 기반 멀티테넌시 관리
# 조직 CRUD, 멤버십 관리, API 키 관리
# 역할 계층 (RBAC): OWNER, ADMIN, MEMBER, VIEWER
app.include_router(organizations_router, prefix="", tags=["Organizations"])

# /organizations/{org_id}/quotas - 조직 쿼터 및 Rate Limit 관리
# 사용량 조회 (MEMBER+), 제한 변경 (ADMIN+)
app.include_router(quotas_router, prefix="", tags=["Quotas"])

# /organizations/{org_id}/rate-limits - DB-controlled Rate Limit 규칙 관리
# 규칙 조회 (MEMBER+), 규칙 생성/수정/삭제 (ADMIN+)
app.include_router(rate_limit_rules_router, prefix="", tags=["Rate Limits"])

# /organizations/{org_id}/rbac - 역할 기반 접근 제어 관리
# 역할/권한 조회 (MEMBER+), 역할/권한 변경 (ADMIN+)
app.include_router(rbac_router, prefix="", tags=["RBAC"])

# /organizations/{org_id}/feature-flags - 기능 플래그 관리
# 플래그 조회 (MEMBER+), 플래그 생성/수정/삭제 (ADMIN+)
app.include_router(feature_flags_router, prefix="", tags=["Feature Flags"])

# /organizations/{org_id}/agents - 에이전트 신원 및 자격 증명 관리
app.include_router(agent_auth_router, prefix="", tags=["Agent Auth"])

# /audit - 감사 로그 조회 및 내보내기
# ADMIN: 조회 가능, OWNER: 내보내기 가능
# 멀티테넌트 격리를 위해 org_id 필터링 필수
app.include_router(audit_router, prefix="", tags=["Audit"])

# /a2a - A2A (Agent-to-Agent) Protocol endpoints
# 외부 A2A 클라이언트와의 에이전트 간 통신 지원
app.include_router(a2a_router)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 전역 예외 핸들러: Agent Protocol 오류 형식 변환
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@app.exception_handler(HTTPException)
async def agent_protocol_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """HTTPException을 Agent Protocol 표준 오류 형식으로 변환

    FastAPI에서 발생하는 HTTPException을 Agent Protocol 스펙에 맞는
    표준화된 오류 응답으로 변환합니다.

    동작 흐름:
    1. HTTP 상태 코드에 따라 오류 타입 매핑 (get_error_type)
       - 400 → "invalid_request"
       - 401 → "authentication_error"
       - 403 → "permission_denied"
       - 404 → "not_found"
       - 500 → "internal_error"
    2. AgentProtocolError 모델로 구조화된 오류 생성
    3. JSON 형식으로 응답 반환

    Args:
        _request (Request): HTTP 요청 객체 (사용하지 않음)
        exc (HTTPException): 발생한 HTTP 예외

    Returns:
        JSONResponse: Agent Protocol 형식의 오류 응답
            {
                "error": "error_type",
                "message": "사람이 읽을 수 있는 오류 메시지",
                "details": {...}  # 선택적 추가 정보
            }

    예시:
        raise HTTPException(status_code=404, detail="Thread not found")
        → {"error": "not_found", "message": "Thread not found"}
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=AgentProtocolError(
            error=get_error_type(exc.status_code),
            message=exc.detail,
            details=getattr(exc, "details", None),
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """예상치 못한 예외를 Agent Protocol 오류로 변환

    HTTPException 이외의 모든 Python 예외를 포착하여
    Agent Protocol 형식의 500 Internal Server Error로 변환합니다.

    동작 흐름:
    1. 처리되지 않은 예외 포착 (ValueError, TypeError 등)
    2. 예외 메시지를 details에 포함하여 디버깅 지원
    3. 500 상태 코드로 표준화된 오류 응답 반환

    Args:
        _request (Request): HTTP 요청 객체 (사용하지 않음)
        exc (Exception): 발생한 예외

    Returns:
        JSONResponse: 500 상태 코드와 함께 Agent Protocol 오류 응답
            {
                "error": "internal_error",
                "message": "An unexpected error occurred",
                "details": {"exception": "예외 메시지"}
            }

    참고:
        - 프로덕션 환경에서는 민감한 정보가 노출되지 않도록 주의 필요
        - 로깅 시스템과 통합하여 상세 오류 추적 권장
    """
    return JSONResponse(
        status_code=500,
        content=AgentProtocolError(
            error="internal_error",
            message="An unexpected error occurred",
            details={"exception": str(exc)},
        ).model_dump(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 루트 엔드포인트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@app.get("/")
async def root() -> dict[str, str]:
    """루트 엔드포인트: 서버 기본 정보 반환

    서버가 정상적으로 실행 중인지 확인하고 기본 메타데이터를 제공합니다.

    Returns:
        dict[str, str]: 서버 정보 딕셔너리
            - message: 애플리케이션 이름
            - version: 현재 버전
            - status: 서버 상태 ("running")

    예시:
        GET http://localhost:8000/
        → {"message": "Open LangGraph", "version": "0.1.0", "status": "running"}

    참고:
        - 상세한 상태 확인은 /health 엔드포인트 사용 권장
    """
    return {"message": "Open LangGraph", "version": "0.1.0", "status": "running"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 스크립트 직접 실행 시 개발 서버 시작
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    import os

    import uvicorn

    # 환경 변수에서 포트 읽기 (기본값: 8000)
    port = int(os.getenv("PORT", "8000"))

    # 개발 서버 실행
    # host="0.0.0.0": 모든 네트워크 인터페이스에서 접속 허용
    # nosec B104: Bandit 보안 경고 억제 (의도적으로 모든 인터페이스에 바인딩)
    uvicorn.run(app, host="0.0.0.0", port=port)  # nosec B104 - binding to all interfaces is intentional
