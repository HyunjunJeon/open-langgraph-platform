"""Agent Protocol 메타데이터 영속성을 위한 SQLAlchemy ORM 설정

이 모듈은 Open LangGraph의 핵심 데이터베이스 모델을 정의합니다.
LangGraph는 자체 체크포인터로 대화 상태를 관리하고,
이 모듈의 ORM 모델은 Agent Protocol 메타데이터만 저장합니다.

주요 구성 요소:
• `Base` - 모든 ORM 모델의 기반 클래스 (declarative base)
• `Assistant` - 어시스턴트 정의 (그래프 ID, 설정, 사용자 정보)
• `AssistantVersion` - 어시스턴트 버전 이력 추적
• `Thread` - 대화 스레드 메타데이터 (상태, 사용자 정보)
• `Run` - 실행 기록 (입력/출력, 상태, 타임스탬프)
• `RunEvent` - SSE 이벤트 저장 (스트리밍 재생용)
• `async_session_maker` - AsyncSession 팩토리
• `get_session` - FastAPI 라우터용 의존성 헬퍼

사용법:
    from ...core.orm import get_session, Assistant

    @router.get("/assistants")
    async def list_assistants(session: AsyncSession = Depends(get_session)):
        result = await session.execute(select(Assistant))
        return result.scalars().all()
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from sqlalchemy import (
    TIMESTAMP,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""

    pass


class Assistant(Base):
    """어시스턴트 정의 ORM 모델

    어시스턴트는 특정 LangGraph 그래프와 설정을 결합한 실행 가능한 엔티티입니다.
    사용자는 여러 어시스턴트를 생성하여 동일한 그래프를 다른 설정으로 실행할 수 있습니다.

    주요 필드:
    - assistant_id: 고유 식별자 (UUID, DB에서 자동 생성)
    - graph_id: 실행할 LangGraph 그래프 ID (open_langgraph.json에 정의)
    - name: 사용자가 지정한 어시스턴트 이름
    - config: LangGraph 실행 설정 (JSONB)
    - context: 그래프 런타임 컨텍스트 (JSONB)
    - version: 버전 번호 (기본값 1)
    - metadata_dict: 추가 메타데이터 (JSONB)
    """

    __tablename__ = "assistant"

    # TEXT 타입 PK, DB 측에서 uuid_generate_v4()로 자동 생성
    assistant_id: Mapped[str] = mapped_column(
        Text, primary_key=True, server_default=text("uuid_generate_v4()::text")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    graph_id: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    metadata_dict: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), name="metadata"
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # 성능 최적화를 위한 인덱스
    # - user_id: 사용자별 어시스턴트 조회 최적화
    # - (user_id, assistant_id): 고유성 보장
    # - (user_id, graph_id, config): 동일 설정 중복 방지
    __table_args__ = (
        Index("idx_assistant_user", "user_id"),
        Index("idx_assistant_user_assistant", "user_id", "assistant_id", unique=True),
        Index(
            "idx_assistant_user_graph_config",
            "user_id",
            "graph_id",
            "config",
            unique=True,
        ),
    )


class AssistantVersion(Base):
    """어시스턴트 버전 이력 추적 ORM 모델

    어시스턴트가 업데이트될 때마다 이전 버전을 이 테이블에 보관합니다.
    사용자는 과거 버전으로 롤백하거나 변경 이력을 조회할 수 있습니다.

    복합 PK: (assistant_id, version)
    - assistant_id: 어시스턴트 식별자 (FK, CASCADE DELETE)
    - version: 버전 번호 (1, 2, 3, ...)
    """

    __tablename__ = "assistant_versions"

    assistant_id: Mapped[str] = mapped_column(
        Text, ForeignKey("assistant.assistant_id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    graph_id: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    metadata_dict: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), name="metadata"
    )
    name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)


class Thread(Base):
    """대화 스레드 메타데이터 ORM 모델

    스레드는 하나의 대화 세션을 나타냅니다.
    실제 대화 메시지와 상태는 LangGraph 체크포인터에 저장되며,
    이 테이블은 스레드 상태(idle/busy/interrupted)와 메타데이터만 관리합니다.

    상태 종류:
    - idle: 대기 중 (실행 가능)
    - busy: 실행 중
    - interrupted: 중단됨 (Human-in-the-Loop)

    주요 필드:
    - thread_id: 고유 식별자 (클라이언트가 생성)
    - status: 현재 상태
    - metadata_json: 어시스턴트/그래프 정보 등 (JSONB)
    - user_id: 소유자 (멀티테넌트 격리)
    """

    __tablename__ = "thread"

    thread_id: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text, server_default=text("'idle'"))
    # DB 컬럼명은 'metadata_json', ORM 속성도 'metadata_json'으로 매핑
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata_json", JSONB, server_default=text("'{}'::jsonb")
    )
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # 성능 최적화: 사용자별 스레드 조회용 인덱스
    __table_args__ = (Index("idx_thread_user", "user_id"),)


class Run(Base):
    """실행 기록 ORM 모델

    Run은 특정 스레드에서 어시스턴트를 실행한 하나의 인스턴스입니다.
    입력, 출력, 상태, 타임스탬프 등 실행 메타데이터를 저장합니다.

    상태 종류:
    - pending: 대기 중
    - running: 실행 중
    - streaming: 스트리밍 중
    - completed: 성공 완료
    - failed: 실패
    - cancelled: 취소됨
    - interrupted: 중단됨 (HITL)

    주요 필드:
    - run_id: 고유 식별자 (UUID, DB 자동 생성)
    - thread_id: 소속 스레드 (FK, CASCADE DELETE)
    - assistant_id: 사용된 어시스턴트 (FK, CASCADE DELETE)
    - input: 실행 입력 데이터 (JSONB)
    - output: 실행 결과 (JSONB)
    - config: LangGraph 실행 설정 (JSONB)
    - context: 런타임 컨텍스트 (JSONB)
    - error_message: 오류 발생 시 메시지
    """

    __tablename__ = "runs"

    # TEXT 타입 PK, DB 측에서 uuid_generate_v4()로 자동 생성
    run_id: Mapped[str] = mapped_column(
        Text, primary_key=True, server_default=text("uuid_generate_v4()::text")
    )
    thread_id: Mapped[str] = mapped_column(
        Text, ForeignKey("thread.thread_id", ondelete="CASCADE"), nullable=False
    )
    assistant_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("assistant.assistant_id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    input: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    # config 컬럼: 일부 환경에서는 아직 없을 수 있어 nullable 설정
    # 마이그레이션으로 추가되면 이미 ORM에 정의되어 있음
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # 성능 최적화 인덱스
    # - thread_id: 스레드별 실행 목록 조회
    # - user_id: 사용자별 실행 조회
    # - status: 상태별 필터링
    # - assistant_id: 어시스턴트별 실행 조회
    # - created_at: 시간순 정렬 최적화
    __table_args__ = (
        Index("idx_runs_thread_id", "thread_id"),
        Index("idx_runs_user", "user_id"),
        Index("idx_runs_status", "status"),
        Index("idx_runs_assistant_id", "assistant_id"),
        Index("idx_runs_created_at", "created_at"),
    )


class RunEvent(Base):
    """실행 이벤트 저장 ORM 모델 (SSE 재생용)

    SSE(Server-Sent Events) 스트리밍 중 발생한 모든 이벤트를 저장합니다.
    클라이언트가 연결이 끊겼다가 재연결하면 저장된 이벤트를 재생할 수 있습니다.

    주요 필드:
    - id: 이벤트 고유 ID (형식: {run_id}_event_{seq})
    - run_id: 소속 실행 ID
    - seq: 시퀀스 번호 (정렬용)
    - event: 이벤트 타입 (values, messages, end 등)
    - data: 이벤트 페이로드 (JSONB)
    - created_at: 생성 시간

    정리 정책:
    - event_store 서비스가 주기적으로 오래된 이벤트 삭제 (기본 300초 이상)
    """

    __tablename__ = "run_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(Text, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # 성능 최적화 인덱스
    # - run_id: 실행별 이벤트 조회
    # - (run_id, seq): 시퀀스 기반 이벤트 재생 최적화
    __table_args__ = (
        Index("idx_run_events_run_id", "run_id"),
        Index("idx_run_events_seq", "run_id", "seq"),
    )


# ---------------------------------------------------------------------------
# 세션 팩토리 (FastAPI 의존성 주입용)
# ---------------------------------------------------------------------------

async_session_maker: async_sessionmaker[AsyncSession] | None = None


def _get_session_maker() -> async_sessionmaker[AsyncSession]:
    """db_manager 엔진에 바인딩된 async_sessionmaker 반환 (캐시됨)

    이 함수는 AsyncSession 팩토리를 지연 생성하고 캐시합니다.
    FastAPI 의존성에서 사용되며, 각 요청마다 새로운 세션을 생성합니다.

    Returns:
        async_sessionmaker: AsyncSession 팩토리
    """
    global async_session_maker
    if async_session_maker is None:
        from .database import db_manager

        engine = db_manager.get_engine()
        async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    return async_session_maker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 라우터용 데이터베이스 세션 의존성

    이 함수는 FastAPI의 Depends()에서 사용되어 각 요청마다
    새로운 AsyncSession을 생성하고 요청 종료 시 자동으로 정리합니다.

    사용 예:
        @router.get("/assistants")
        async def list_assistants(session: AsyncSession = Depends(get_session)):
            result = await session.execute(select(Assistant))
            return result.scalars().all()

    Yields:
        AsyncSession: 요청별 데이터베이스 세션
    """
    maker = _get_session_maker()
    async with maker() as session:
        yield session
