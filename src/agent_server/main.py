"""Open LangGraph 메인 FastAPI 애플리케이션 엔트리포인트

이 모듈은 Open LangGraph Agent Protocol 서버의 핵심 FastAPI 애플리케이션을 정의합니다.
LangGraph 기반 에이전트를 HTTP API로 노출하며, Agent Protocol 표준을 준수합니다.

애플리케이션 아키텍처:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 미들웨어 스택 (요청 처리 순서):
   ├─ CORS 미들웨어: 교차 출처 리소스 공유 설정
   ├─ DoubleEncodedJSON 미들웨어: 프론트엔드 이중 인코딩 처리
   └─ Authentication 미들웨어: LangGraph SDK 기반 사용자 인증

2. 라우터 구조 (API 엔드포인트):
   ├─ /health: 서버 및 데이터베이스 상태 확인
   ├─ /assistants: 어시스턴트(그래프) 관리
   ├─ /threads: 대화 스레드 관리
   ├─ /runs: 에이전트 실행 및 스트리밍
   └─ /store: LangGraph Store 장기 메모리

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
    - 데이터베이스 마이그레이션은 scripts/migrate.py로 관리
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

from .api.assistants import router as assistants_router
from .api.runs import router as runs_router
from .api.store import router as store_router
from .api.threads import router as threads_router
from .core.auth_middleware import get_auth_backend, on_auth_error
from .core.database import db_manager
from .core.health import router as health_router
from .middleware import DoubleEncodedJSONMiddleware
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
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
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

    2. LangGraph 서비스 초기화
       - open_langgraph.json에서 그래프 정의 로드
       - 각 그래프에 대한 기본 어시스턴트 생성 (UUID5 기반)
       - 그래프 캐싱 시스템 준비

    3. 이벤트 저장소 정리 작업 시작
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
    # Startup: 데이터베이스 및 LangGraph 컴포넌트 초기화
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    await db_manager.initialize()

    # LangGraph 서비스 초기화
    # open_langgraph.json에서 그래프 정의 로드 및 기본 어시스턴트 생성
    from .services.langgraph_service import get_langgraph_service

    langgraph_service = get_langgraph_service()
    await langgraph_service.initialize()

    # 이벤트 저장소 백그라운드 정리 작업 시작
    # 오래된 SSE 이벤트를 주기적으로 삭제하여 디스크 공간 관리
    from .services.event_store import event_store

    await event_store.start_cleanup_task()

    yield

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Shutdown: 리소스 정리 및 활성 작업 취소
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # 완료되지 않은 모든 실행 작업 취소
    # graceful shutdown을 위해 각 태스크에 취소 신호 전송
    for task in active_runs.values():
        if not task.done():
            task.cancel()

    # 이벤트 저장소 정리 작업 중지
    await event_store.stop_cleanup_task()

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
# 추가 순서: CORS → DoubleEncodedJSON → Authentication
# 실행 순서: Authentication → DoubleEncodedJSON → CORS → 라우터

# 1. CORS 미들웨어: 교차 출처 리소스 공유 설정
# 프론트엔드가 다른 도메인에서 API를 호출할 수 있도록 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한 필요
    allow_credentials=True,  # 쿠키 및 인증 헤더 허용
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 HTTP 헤더 허용
)

# 2. DoubleEncodedJSON 미들웨어: 프론트엔드의 이중 인코딩 처리
# 일부 프론트엔드 클라이언트가 JSON을 두 번 인코딩하는 경우 자동 디코딩
app.add_middleware(DoubleEncodedJSONMiddleware)

# 3. Authentication 미들웨어: LangGraph SDK 기반 사용자 인증
# 주의: CORS 이후에 추가되어야 preflight 요청 처리 가능
# 모든 요청에서 Authorization 헤더 검증 후 request.user 설정
app.add_middleware(AuthenticationMiddleware, backend=get_auth_backend(), on_error=on_auth_error)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API 라우터 등록 (Agent Protocol 엔드포인트)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 각 라우터는 Agent Protocol 표준을 따르는 HTTP 엔드포인트 제공

# /health - 서버 상태 확인 및 데이터베이스 연결 테스트
app.include_router(health_router, prefix="", tags=["Health"])

# /assistants - 어시스턴트(그래프) 목록 조회 및 생성
# open_langgraph.json에 정의된 그래프들이 어시스턴트로 노출됨
app.include_router(assistants_router, prefix="", tags=["Assistants"])

# /threads - 대화 스레드 생성, 조회, 수정, 삭제 (CRUD)
# LangGraph 체크포인트 기반 대화 상태 관리
app.include_router(threads_router, prefix="", tags=["Threads"])

# /runs - 에이전트 실행 및 실시간 스트리밍
# SSE(Server-Sent Events)를 통한 스트리밍 지원
app.include_router(runs_router, prefix="", tags=["Runs"])

# /store - LangGraph Store를 통한 장기 메모리 관리
# 사용자별, 스레드별 영구 데이터 저장소 (JSONB)
app.include_router(store_router, prefix="", tags=["Store"])


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
