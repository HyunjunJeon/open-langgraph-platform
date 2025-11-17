"""Health check endpoints unit tests

Test all endpoints in health.py to achieve 100% coverage.
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
    """Tests for the info endpoint"""

    @pytest.mark.asyncio
    async def test_info_returns_correct_structure(self):
        """Verify that service information is returned in the correct format"""
        result = await info()

        assert isinstance(result, InfoResponse)
        assert result.name == "Open LangGraph"
        assert result.version == "0.1.0"
        assert result.status == "running"
        assert "Agent Protocol" in result.description

    @pytest.mark.asyncio
    async def test_info_status_is_running(self):
        """Verify that the service status is always running"""
        result = await info()
        assert result.status == "running"


class TestLivenessEndpoint:
    """Tests for the liveness probe endpoint"""

    @pytest.mark.asyncio
    async def test_liveness_returns_alive(self):
        """Verify that the liveness probe always returns alive"""
        result = await liveness_check()

        assert result == {"status": "alive"}

    @pytest.mark.asyncio
    async def test_liveness_no_dependencies(self):
        """Verify that the liveness check works without external dependencies"""
        # Liveness should succeed even if the DB is not available
        result = await liveness_check()
        assert result["status"] == "alive"


class TestHealthEndpoint:
    """Tests for the health check endpoint"""

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self):
        """Return healthy when all components are normal"""
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
        """Return unhealthy when the database is not initialized"""
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
        """Return unhealthy on database connection error"""
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
        """Return unhealthy on Checkpointer error"""
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
        """Return unhealthy on Store error"""
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
    """Tests for the readiness probe endpoint"""

    @pytest.mark.asyncio
    async def test_readiness_check_all_ready(self):
        """Return ready when all components are ready"""
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
        """Return 503 when the engine is not initialized"""
        with patch("src.agent_server.core.database.db_manager") as mock_db:
            mock_db.engine = None

            with pytest.raises(HTTPException) as exc_info:
                await readiness_check()

            assert exc_info.value.status_code == 503
            assert "not ready" in str(exc_info.value.detail).lower()
            assert "not initialized" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_readiness_check_database_error(self):
        """Return 503 on database query failure"""
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
        """Return 503 when LangGraph components cannot be retrieved"""
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
        """Return ready if the database query succeeds"""
        # Mock database connection with proper async context manager
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=None)  # SELECT 1 succeeds
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

            # Verify that execute was called
            mock_conn.execute.assert_called_once()
            assert result["status"] == "ready"
