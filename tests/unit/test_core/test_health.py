"""Health check endpoints unit tests

health.py의 모든 엔드포인트를 테스트하여 커버리지를 100%로 달성합니다.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError

from src.agent_server.core.health import (
    InfoResponse,
    health_check,
    info,
    liveness_check,
    readiness_check,
)


class TestInfoEndpoint:
    """Info 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_info_returns_correct_structure(self):
        """서비스 정보가 올바른 형식으로 반환되는지 검증"""
        result = await info()

        assert isinstance(result, InfoResponse)
        assert result.name == "Open LangGraph"
        assert result.version == "0.1.0"
        assert result.status == "running"
        assert "Agent Protocol" in result.description

    @pytest.mark.asyncio
    async def test_info_status_is_running(self):
        """서비스 상태가 항상 running인지 검증"""
        result = await info()
        assert result.status == "running"


class TestLivenessEndpoint:
    """Liveness probe 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_liveness_returns_alive(self):
        """Liveness probe가 항상 alive를 반환하는지 검증"""
        result = await liveness_check()

        assert result == {"status": "alive"}

    @pytest.mark.asyncio
    async def test_liveness_no_dependencies(self):
        """Liveness check가 외부 의존성 없이 동작하는지 검증"""
        # DB가 없어도 liveness는 성공해야 함
        result = await liveness_check()
        assert result["status"] == "alive"


class TestHealthEndpoint:
    """Health check 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self):
        """모든 컴포넌트가 정상일 때 healthy 반환"""
        # Mock database connection with proper async context manager
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__.return_value = mock_conn
        mock_conn.__aexit__.return_value = None

        # Mock engine with begin() returning async context manager
        mock_engine = MagicMock()
        mock_engine.begin.return_value = mock_conn

        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget_tuple = AsyncMock(return_value=None)

        mock_store = AsyncMock()
        mock_store.aget = AsyncMock(return_value=None)

        with patch("src.agent_server.core.database.db_manager") as mock_db:
            mock_db.engine = mock_engine
            mock_db.get_checkpointer = AsyncMock(return_value=mock_checkpointer)
            mock_db.get_store = AsyncMock(return_value=mock_store)

            result = await health_check()

            assert result["status"] == "healthy"
            assert result["database"] == "connected"
            assert result["langgraph_checkpointer"] == "connected"
            assert result["langgraph_store"] == "connected"

    @pytest.mark.asyncio
    async def test_health_check_database_not_initialized(self):
        """데이터베이스가 초기화되지 않았을 때 unhealthy 반환"""
        with patch("src.agent_server.core.database.db_manager") as mock_db:
            mock_db.engine = None
            mock_db.get_checkpointer = AsyncMock()
            mock_db.get_store = AsyncMock()

            with pytest.raises(HTTPException) as exc_info:
                await health_check()

            assert exc_info.value.status_code == 503
            assert "unhealthy" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_health_check_database_connection_error(self):
        """데이터베이스 연결 오류 시 unhealthy 반환"""
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_engine.begin = AsyncMock(return_value=mock_conn)
        mock_conn.__aenter__ = AsyncMock(side_effect=OperationalError("Connection failed", None, None))

        with patch("src.agent_server.core.database.db_manager") as mock_db:
            mock_db.engine = mock_engine
            mock_db.get_checkpointer = AsyncMock()
            mock_db.get_store = AsyncMock()

            with pytest.raises(HTTPException) as exc_info:
                await health_check()

            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_health_check_checkpointer_error(self):
        """Checkpointer 오류 시 unhealthy 반환"""
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_engine.begin = AsyncMock(return_value=mock_conn)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()

        with patch("src.agent_server.core.database.db_manager") as mock_db:
            mock_db.engine = mock_engine
            mock_db.get_checkpointer = AsyncMock(side_effect=Exception("Checkpointer failed"))
            mock_db.get_store = AsyncMock()

            with pytest.raises(HTTPException) as exc_info:
                await health_check()

            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_health_check_store_error(self):
        """Store 오류 시 unhealthy 반환"""
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_engine.begin = AsyncMock(return_value=mock_conn)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()

        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget_tuple = AsyncMock(return_value=None)

        with patch("src.agent_server.core.database.db_manager") as mock_db:
            mock_db.engine = mock_engine
            mock_db.get_checkpointer = AsyncMock(return_value=mock_checkpointer)
            mock_db.get_store = AsyncMock(side_effect=Exception("Store failed"))

            with pytest.raises(HTTPException) as exc_info:
                await health_check()

            assert exc_info.value.status_code == 503


class TestReadinessEndpoint:
    """Readiness probe 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_readiness_check_all_ready(self):
        """모든 컴포넌트가 준비되었을 때 ready 반환"""
        # Mock database connection with proper async context manager
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__.return_value = mock_conn
        mock_conn.__aexit__.return_value = None

        # Mock engine
        mock_engine = MagicMock()
        mock_engine.begin.return_value = mock_conn

        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget_tuple = AsyncMock(return_value=None)

        mock_store = AsyncMock()
        mock_store.aget = AsyncMock(return_value=None)

        with patch("src.agent_server.core.database.db_manager") as mock_db:
            mock_db.engine = mock_engine
            mock_db.get_checkpointer = AsyncMock(return_value=mock_checkpointer)
            mock_db.get_store = AsyncMock(return_value=mock_store)

            result = await readiness_check()

            assert result == {"status": "ready"}

    @pytest.mark.asyncio
    async def test_readiness_check_engine_not_initialized(self):
        """엔진이 초기화되지 않았을 때 503 반환"""
        with patch("src.agent_server.core.database.db_manager") as mock_db:
            mock_db.engine = None

            with pytest.raises(HTTPException) as exc_info:
                await readiness_check()

            assert exc_info.value.status_code == 503
            assert "not ready" in str(exc_info.value.detail).lower()
            assert "not initialized" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_readiness_check_database_error(self):
        """데이터베이스 쿼리 실패 시 503 반환"""
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_engine.begin = AsyncMock(return_value=mock_conn)
        mock_conn.__aenter__ = AsyncMock(side_effect=OperationalError("DB error", None, None))

        with patch("src.agent_server.core.database.db_manager") as mock_db:
            mock_db.engine = mock_engine

            with pytest.raises(HTTPException) as exc_info:
                await readiness_check()

            assert exc_info.value.status_code == 503
            assert "database error" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_readiness_check_components_unavailable(self):
        """LangGraph 컴포넌트를 가져올 수 없을 때 503 반환"""
        # Mock database connection with proper async context manager
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__.return_value = mock_conn
        mock_conn.__aexit__.return_value = None

        # Mock engine
        mock_engine = MagicMock()
        mock_engine.begin.return_value = mock_conn

        with patch("src.agent_server.core.database.db_manager") as mock_db:
            mock_db.engine = mock_engine
            mock_db.get_checkpointer = AsyncMock(side_effect=Exception("Components unavailable"))

            with pytest.raises(HTTPException) as exc_info:
                await readiness_check()

            assert exc_info.value.status_code == 503
            assert "components unavailable" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_readiness_check_database_query_success(self):
        """데이터베이스 쿼리가 성공하면 ready 반환"""
        # Mock database connection with proper async context manager
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=None)  # SELECT 1 성공
        mock_conn.__aenter__.return_value = mock_conn
        mock_conn.__aexit__.return_value = None

        # Mock engine
        mock_engine = MagicMock()
        mock_engine.begin.return_value = mock_conn

        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget_tuple = AsyncMock(return_value=None)

        mock_store = AsyncMock()
        mock_store.aget = AsyncMock(return_value=None)

        with patch("src.agent_server.core.database.db_manager") as mock_db:
            mock_db.engine = mock_engine
            mock_db.get_checkpointer = AsyncMock(return_value=mock_checkpointer)
            mock_db.get_store = AsyncMock(return_value=mock_store)

            result = await readiness_check()

            # execute가 호출되었는지 확인
            mock_conn.execute.assert_called_once()
            assert result["status"] == "ready"
