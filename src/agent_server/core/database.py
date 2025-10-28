"""LangGraph 통합 데이터베이스 관리자

이 모듈은 Open LangGraph의 데이터베이스 연결 및 LangGraph 영속성 컴포넌트를 관리합니다.
SQLAlchemy를 통해 Agent Protocol 메타데이터 테이블을 관리하고,
LangGraph의 공식 AsyncPostgresSaver와 AsyncPostgresStore를 통해 대화 상태를 저장합니다.
"""

import os
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


class DatabaseManager:
    """데이터베이스 연결 및 LangGraph 영속성 컴포넌트 관리자

    이 클래스는 다음 두 가지 데이터베이스 시스템을 관리합니다:
    1. SQLAlchemy AsyncEngine: Agent Protocol 메타데이터 테이블용 (Assistant, Thread, Run)
    2. LangGraph 컴포넌트: 대화 상태 및 체크포인트 저장용
       - AsyncPostgresSaver: 체크포인트(상태 스냅샷) 저장
       - AsyncPostgresStore: 장기 메모리 및 키-값 저장소

    주요 특징:
    - URL 형식 자동 변환: asyncpg → psycopg (LangGraph 요구사항)
    - 싱글톤 패턴: 애플리케이션 전체에서 단일 인스턴스 사용
    - 지연 초기화: 컴포넌트를 필요할 때만 생성
    - 컨텍스트 매니저: 리소스 자동 정리
    """

    def __init__(self) -> None:
        self.engine: AsyncEngine | None = None
        self._checkpointer: AsyncPostgresSaver | None = None
        self._checkpointer_cm: Any = None  # holds the contextmanager so we can close it
        self._store: AsyncPostgresStore | None = None
        self._store_cm: Any = None
        self._database_url = os.getenv(
            "DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/open_langgraph"
        )

    async def initialize(self) -> None:
        """데이터베이스 연결 및 LangGraph 컴포넌트 초기화

        이 메서드는 FastAPI 앱 시작 시 lifespan에서 호출됩니다.
        SQLAlchemy 엔진을 생성하고 LangGraph DSN을 준비합니다.
        실제 LangGraph 컴포넌트는 get_checkpointer/get_store에서 지연 생성됩니다.

        참고: 데이터베이스 스키마는 Alembic 마이그레이션으로 관리됩니다.
              초기 설정 시 'python3 scripts/migrate.py upgrade' 실행 필요
        """
        # SQLAlchemy: Agent Protocol 메타데이터 테이블용 (최소한의 테이블만 사용)
        self.engine = create_async_engine(
            self._database_url,
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
        )

        # asyncpg URL을 psycopg 형식으로 변환 (LangGraph 요구사항)
        # LangGraph 패키지는 psycopg 드라이버를 사용하므로 URL 형식 변환 필요
        # 예: postgresql+asyncpg://user:pass@host/db → postgresql://user:pass@host/db
        dsn = self._database_url.replace("postgresql+asyncpg://", "postgresql://")

        # LangGraph 컴포넌트를 필요할 때 생성하기 위해 연결 문자열 저장
        self._langgraph_dsn = dsn
        self.checkpointer = None
        self.store = None
        # 참고: LangGraph 컴포넌트는 컨텍스트 매니저로 필요할 때 생성됩니다

        # 참고: 데이터베이스 스키마는 이제 Alembic 마이그레이션으로 관리됩니다
        # 마이그레이션 적용: 'alembic upgrade head' 또는 'python3 scripts/migrate.py upgrade'

        print("✅ Database and LangGraph components initialized")

    async def close(self) -> None:
        """데이터베이스 연결 종료

        FastAPI 앱 종료 시 lifespan에서 호출됩니다.
        모든 활성 연결을 정리하고 리소스를 해제합니다.
        """
        if self.engine:
            await self.engine.dispose()

        # 캐시된 checkpointer가 있으면 종료
        if self._checkpointer_cm is not None:
            await self._checkpointer_cm.__aexit__(None, None, None)
            self._checkpointer_cm = None
            self._checkpointer = None

        if self._store_cm is not None:
            await self._store_cm.__aexit__(None, None, None)
            self._store_cm = None
            self._store = None

        print("✅ Database connections closed")

    async def get_checkpointer(self) -> AsyncPostgresSaver:
        """LangGraph 체크포인터(상태 저장소) 반환

        이 메서드는 AsyncPostgresSaver의 활성 인스턴스를 반환합니다.

        동작 방식:
        1. 첫 호출 시: 비동기 컨텍스트 매니저를 진입하고 saver 객체를 캐시
        2. 이후 호출: 캐시된 saver 재사용 (DB 연결 풀 공유)

        캐싱 이유:
        - LangGraph는 실제 saver 객체가 필요함 (get_next_version 등 메서드 호출)
        - 컨텍스트 매니저 래퍼를 반환하면 실패
        - 연결 풀 재사용으로 성능 향상

        Returns:
            AsyncPostgresSaver: LangGraph 체크포인터 인스턴스

        Raises:
            RuntimeError: 데이터베이스가 초기화되지 않은 경우
        """
        if not hasattr(self, "_langgraph_dsn"):
            raise RuntimeError("Database not initialized")
        if self._checkpointer is None:
            self._checkpointer_cm = AsyncPostgresSaver.from_conn_string(self._langgraph_dsn)
            self._checkpointer = await self._checkpointer_cm.__aenter__()
            # 필요한 테이블 생성 (멱등성: 여러 번 호출해도 안전)
            await self._checkpointer.setup()
        return self._checkpointer

    async def get_store(self) -> AsyncPostgresStore:
        """LangGraph Store 인스턴스 반환 (벡터 검색 + 키-값 저장소)

        AsyncPostgresStore는 다음 기능을 제공합니다:
        - 키-값 저장소: 장기 메모리, 사용자 선호도 등
        - 벡터 검색: 임베딩 기반 유사도 검색 (향후 지원)

        체크포인터와 동일한 캐싱 패턴을 사용합니다.

        Returns:
            AsyncPostgresStore: LangGraph Store 인스턴스

        Raises:
            RuntimeError: 데이터베이스가 초기화되지 않은 경우
        """
        if not hasattr(self, "_langgraph_dsn"):
            raise RuntimeError("Database not initialized")
        if self._store is None:
            self._store_cm = AsyncPostgresStore.from_conn_string(self._langgraph_dsn)
            self._store = await self._store_cm.__aenter__()
            # 스키마 생성 (멱등성 보장)
            await self._store.setup()
        return self._store

    def get_engine(self) -> AsyncEngine:
        """메타데이터 테이블용 SQLAlchemy 엔진 반환

        이 엔진은 Agent Protocol 메타데이터 테이블(Assistant, Thread, Run 등)에만 사용됩니다.
        LangGraph 상태 저장은 별도의 checkpointer/store를 사용합니다.

        Returns:
            AsyncEngine: SQLAlchemy 비동기 엔진

        Raises:
            RuntimeError: 데이터베이스가 초기화되지 않은 경우
        """
        if not self.engine:
            raise RuntimeError("Database not initialized")
        return self.engine


# 전역 데이터베이스 관리자 인스턴스 (싱글톤 패턴)
# 애플리케이션 전체에서 이 인스턴스를 사용하여 DB에 접근합니다
db_manager = DatabaseManager()
