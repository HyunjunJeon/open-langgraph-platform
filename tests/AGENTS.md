# AGENTS.md - Tests Directory

This document provides comprehensive guidance for understanding and working with the test suite in the Open LangGraph project. It serves as a companion to the human-readable `README.md` in this directory.

## 1. 테스트 구조 개요 (Test Structure Overview)

Open LangGraph의 테스트 시스템은 3계층 아키텍처를 따릅니다:

### Test Pyramid Architecture

```
        /\
       /  \      E2E Tests (Slowest, Most Coverage)
      /____\     End-to-end workflows
     /      \    Integration Tests (Medium Speed)
    /________\   Service + Database
   /          \  Unit Tests (Fastest, Most Granular)
  /__________\   Isolated functions/classes
```

**핵심 원칙 (Core Principles):**

- **Isolation**: Unit tests는 외부 의존성 없이 독립적으로 실행
- **Integration**: Integration tests는 실제 데이터베이스와 여러 컴포넌트 연동
- **End-to-End**: E2E tests는 전체 시스템을 실제 사용자 시나리오로 검증
- **Speed**: 테스트는 피라미드 하단으로 갈수록 빠르게 실행
- **Coverage**: 각 레이어는 서로 다른 관점에서 코드 커버리지 제공

### LangGraph Integration Testing

Open LangGraph는 LangGraph 위에 구축되었으므로, 테스트는 다음을 고려합니다:

- **State Persistence**: LangGraph checkpointer와 store의 동작 검증
- **Graph Execution**: Workflow 실행 및 상태 전이 테스트
- **Event Streaming**: SSE (Server-Sent Events) 스트리밍 검증
- **Human-in-the-Loop**: Interrupt 및 resume 기능 테스트

## 2. 테스트 유형 (Test Types)

### Unit Tests (`tests/unit/`)

**목적 (Purpose)**: 개별 함수, 클래스, 메서드를 격리된 환경에서 테스트

**특징 (Characteristics):**
- 속도: ⚡ 매우 빠름 (밀리초 단위)
- 의존성: 모든 외부 의존성은 Mock으로 대체
- 범위: 단일 함수/클래스의 로직 검증
- 격리: 데이터베이스, 네트워크, 파일 시스템 접근 없음

**하위 디렉토리:**
- `test_core/`: 핵심 유틸리티 및 인증 로직
  - `test_auth_ctx.py`: 인증 컨텍스트 유틸리티
  - `test_auth_middleware.py`: 인증 미들웨어
  - `test_serializers/`: 직렬화 로직
  - `test_sse.py`: SSE 이벤트 생성
- `test_middleware/`: HTTP 미들웨어
  - `test_double_encoded_json.py`: JSON 인코딩 처리
- `test_services/`: 서비스 레이어 로직
  - `test_assistant_service.py`: Assistant 관리
  - `test_broker.py`: 메시지 브로커
  - `test_event_converter.py`: 이벤트 변환
  - `test_event_store.py`: 이벤트 저장소
  - `test_langgraph_service.py`: Graph 로딩 및 캐싱
- `test_utils/`: 유틸리티 함수
  - `test_assistants_utils.py`: Assistant 헬퍼
  - `test_sse_utils.py`: SSE 유틸리티
- `test_observability/`: 관찰성 통합
  - `test_langfuse_integration.py`: Langfuse 트레이싱

**Example:**
```python
# tests/unit/test_services/test_event_converter.py
from src.agent_server.services.event_converter import EventConverter

class TestEventConverter:
    def setup_method(self):
        self.converter = EventConverter()

    def test_parse_raw_event_tuple_2_elements(self):
        """Test parsing raw event with 2-element tuple"""
        raw_event = ("values", {"key": "value"})
        stream_mode, payload = self.converter._parse_raw_event(raw_event)

        assert stream_mode == "values"
        assert payload == {"key": "value"}
```

### Integration Tests (`tests/integration/`)

**목적 (Purpose)**: 여러 컴포넌트가 함께 작동하는지 검증

**특징 (Characteristics):**
- 속도: 🐢 중간 속도 (100ms-1s per test)
- 의존성: 실제 PostgreSQL 데이터베이스, Mocked 외부 API
- 범위: 서비스 레이어 + 데이터베이스 연동
- 격리: 각 테스트는 독립된 트랜잭션에서 실행

**하위 디렉토리:**
- `test_api/`: API 엔드포인트 통합 테스트
  - `test_assistants_crud.py`: Assistant CRUD 작업
  - `test_runs_crud.py`: Run CRUD 작업
  - `test_store_crud.py`: Store CRUD 작업
  - `test_threads_crud.py`: Thread CRUD 작업
  - `test_threads_history.py`: Thread 히스토리 조회
- `test_services/`: 서비스 레이어 통합 테스트
  - `test_assistant_service_db.py`: Assistant 서비스 + DB
  - `test_event_store_integration.py`: 이벤트 저장소 + DB
  - `test_langgraph_service_integration.py`: LangGraph 서비스 통합
  - `test_streaming_hitl.py`: Human-in-the-Loop 스트리밍

**Example:**
```python
# tests/integration/test_api/test_assistants_crud.py
import pytest
from tests.fixtures.clients import create_test_app, make_client

@pytest.fixture
def client(mock_assistant_service):
    app = create_test_app(include_runs=False, include_threads=False)
    app.dependency_overrides[get_assistant_service] = lambda: mock_assistant_service
    return make_client(app)

class TestCreateAssistant:
    def test_create_assistant_basic(self, client, mock_assistant_service):
        """Test creating a basic assistant"""
        assistant = make_assistant()
        mock_assistant_service.create_assistant.return_value = assistant

        resp = client.post("/assistants", json={
            "name": "Test Assistant",
            "graph_id": "test-graph"
        })

        assert resp.status_code == 200
        assert resp.json()["assistant_id"] == "test-assistant-123"
```

### E2E Tests (`tests/e2e/`)

**목적 (Purpose)**: 실제 사용자 워크플로우를 전체 시스템에서 검증

**특징 (Characteristics):**
- 속도: 🐌 가장 느림 (1s-10s per test)
- 의존성: 전체 시스템 (DB, LangGraph, 모든 서비스)
- 범위: 완전한 사용자 시나리오
- 격리: 실제 환경과 유사한 설정

**하위 디렉토리:**
- `test_assistants/`: Assistant 기능 E2E
  - `test_assistant_deletion.py`: Assistant 삭제 워크플로우
  - `test_assistant_graph.py`: Graph 구조 조회
  - `test_assistant_search.py`: Assistant 검색
  - `test_assistant_version.py`: 버전 관리
- `test_runs/`: Run 실행 E2E
  - `test_runs.py`: 기본 Run 실행
  - `test_background_run_join.py`: 백그라운드 실행 및 Join
  - `test_run_join_output.py`: Join 출력 검증
- `test_threads/`: Thread 관리 E2E
  - `test_thread_deletion.py`: Thread 삭제
  - `test_history_endpoint.py`: 히스토리 조회
  - `test_state_endpoint.py`: 상태 조회
- `test_streaming/`: 스트리밍 E2E
  - `test_chat_streaming.py`: 채팅 스트리밍
  - `test_event_filtering_and_subgraphs.py`: 이벤트 필터링 및 서브그래프
- `test_store/`: Store E2E
  - `test_store.py`: Store 기능 전체 테스트
- `test_human_in_loop/`: Human-in-the-Loop E2E
  - `test_human_in_loop.py`: HITL 워크플로우

**Example:**
```python
# tests/e2e/test_assistants/test_assistant_graph.py
import pytest
from tests.e2e._utils import elog, get_e2e_client

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_assistant_graph():
    """Test that we can retrieve the graph structure for an assistant."""
    client = get_e2e_client()

    # Create an assistant
    assistant = await client.assistants.create(
        name="Test Graph Assistant",
        graph_id="agent",
        if_exists="do_nothing"
    )

    try:
        # Get the graph structure
        graph = await client.assistants.get_graph(
            assistant_id=assistant["assistant_id"]
        )

        # Verify graph structure
        assert "nodes" in graph
        assert "edges" in graph
        assert len(graph["nodes"]) > 0

        elog("Graph structure retrieved", {
            "node_count": len(graph["nodes"]),
            "edge_count": len(graph["edges"])
        })
    finally:
        await client.assistants.delete(assistant_id=assistant["assistant_id"])
```

## 3. 디렉토리 구조 (Directory Structure)

```
tests/
├── __init__.py                      # Package initialization
├── conftest.py                      # 글로벌 pytest 설정 및 공통 픽스처
├── README.md                        # Human-readable test documentation
├── AGENTS.md                        # AI agent guidance (this file)
│
├── unit/                            # Unit tests (fast, isolated)
│   ├── __init__.py
│   ├── conftest.py                  # Unit-specific fixtures
│   ├── test_core/                   # Core utilities tests
│   │   ├── test_auth_ctx.py         # Authentication context
│   │   ├── test_auth_middleware.py  # Auth middleware
│   │   ├── test_sse.py              # SSE event generation
│   │   └── test_serializers/        # Serialization logic
│   ├── test_middleware/             # HTTP middleware tests
│   │   └── test_double_encoded_json.py
│   ├── test_services/               # Service layer unit tests
│   │   ├── test_assistant_service.py
│   │   ├── test_broker.py
│   │   ├── test_event_converter.py
│   │   ├── test_event_store.py
│   │   └── test_langgraph_service.py
│   ├── test_observability/          # Observability tests
│   │   └── test_langfuse_integration.py
│   └── test_utils/                  # Utility function tests
│       ├── test_assistants_utils.py
│       └── test_sse_utils.py
│
├── integration/                     # Integration tests (DB + services)
│   ├── __init__.py
│   ├── conftest.py                  # Integration-specific fixtures
│   ├── test_api/                    # API integration tests
│   │   ├── test_assistants_crud.py  # Assistant CRUD operations
│   │   ├── test_runs_crud.py        # Run CRUD operations
│   │   ├── test_store_crud.py       # Store CRUD operations
│   │   ├── test_threads_crud.py     # Thread CRUD operations
│   │   └── test_threads_history.py  # Thread history queries
│   └── test_services/               # Service integration tests
│       ├── test_assistant_service_db.py
│       ├── test_event_store_integration.py
│       ├── test_langgraph_service_integration.py
│       └── test_streaming_hitl.py
│
├── e2e/                             # End-to-end tests (full system)
│   ├── __init__.py
│   ├── conftest.py                  # E2E-specific fixtures
│   ├── _utils.py                    # E2E test utilities
│   ├── test_assistants/             # Assistant E2E workflows
│   │   ├── test_assistant_deletion.py
│   │   ├── test_assistant_graph.py
│   │   ├── test_assistant_search.py
│   │   └── test_assistant_version.py
│   ├── test_runs/                   # Run execution E2E
│   │   ├── test_runs.py
│   │   ├── test_background_run_join.py
│   │   └── test_run_join_output.py
│   ├── test_threads/                # Thread management E2E
│   │   ├── test_thread_deletion.py
│   │   ├── test_history_endpoint.py
│   │   └── test_state_endpoint.py
│   ├── test_streaming/              # Streaming E2E
│   │   ├── test_chat_streaming.py
│   │   └── test_event_filtering_and_subgraphs.py
│   ├── test_store/                  # Store E2E
│   │   └── test_store.py
│   └── test_human_in_loop/          # HITL E2E
│       └── test_human_in_loop.py
│
└── fixtures/                        # Shared test fixtures and helpers
    ├── __init__.py
    ├── auth.py                      # Authentication fixtures (DummyUser)
    ├── clients.py                   # Test client fixtures
    ├── database.py                  # Database fixtures
    ├── langgraph.py                 # LangGraph mocks (FakeAgent, FakeGraph)
    ├── session_fixtures.py          # Session fixtures
    └── test_helpers.py              # Helper functions (make_assistant, make_thread, make_run)
```

### 각 디렉토리 역할 (Directory Roles)

**`unit/`**: 최소한의 의존성으로 개별 컴포넌트 테스트. 모든 외부 서비스는 Mock으로 대체.

**`integration/`**: 실제 데이터베이스를 사용하여 서비스 레이어와 API 레이어의 통합 검증. LangGraph 관련 외부 호출은 여전히 Mock.

**`e2e/`**: 전체 시스템을 실제 사용자 관점에서 테스트. LangGraph SDK 클라이언트를 사용하여 HTTP API를 통한 완전한 워크플로우 검증.

**`fixtures/`**: 모든 테스트 레벨에서 재사용 가능한 테스트 헬퍼, Mock 객체, 픽스처 제공.

## 4. 테스트 실행 (Running Tests)

### Basic Commands

```bash
# 모든 테스트 실행 (Run all tests)
uv run pytest

# 특정 테스트 레벨 실행 (Run specific test level)
uv run pytest tests/unit/              # Unit tests only
uv run pytest tests/integration/       # Integration tests only
uv run pytest tests/e2e/              # E2E tests only

# 특정 파일 실행 (Run specific file)
uv run pytest tests/unit/test_services/test_event_converter.py

# 특정 테스트 클래스 실행 (Run specific test class)
uv run pytest tests/unit/test_services/test_event_converter.py::TestEventConverter

# 특정 테스트 메서드 실행 (Run specific test method)
uv run pytest tests/unit/test_services/test_event_converter.py::TestEventConverter::test_parse_raw_event_tuple_2_elements
```

### Advanced Options

```bash
# Verbose output (자세한 출력)
uv run pytest -v

# Very verbose output (매우 자세한 출력)
uv run pytest -vv

# Show local variables on failure (실패 시 로컬 변수 표시)
uv run pytest -l

# Stop on first failure (첫 실패 시 중단)
uv run pytest -x

# Run only failed tests from last run (마지막 실행에서 실패한 테스트만)
uv run pytest --lf

# Run failed tests first, then others (실패한 테스트 먼저, 그 다음 나머지)
uv run pytest --ff

# Async mode (비동기 테스트 지원)
uv run pytest -v --asyncio-mode=auto
```

### Test Markers

```bash
# pytest 마커를 사용한 필터링 (Filter by pytest markers)
uv run pytest -m unit              # @pytest.mark.unit 테스트만
uv run pytest -m integration       # @pytest.mark.integration 테스트만
uv run pytest -m e2e              # @pytest.mark.e2e 테스트만
uv run pytest -m "not slow"       # 느린 테스트 제외
uv run pytest -m "unit or integration"  # Unit 또는 Integration 테스트
```

### Coverage Reports

```bash
# 코드 커버리지 측정 (Measure code coverage)
uv run pytest --cov=src/agent_server

# HTML 커버리지 리포트 생성 (Generate HTML coverage report)
uv run pytest --cov=src/agent_server --cov-report=html

# 터미널에 커버리지 리포트 출력 (Print coverage report to terminal)
uv run pytest --cov=src/agent_server --cov-report=term-missing

# 커버리지 최소 임계값 설정 (Set minimum coverage threshold)
uv run pytest --cov=src/agent_server --cov-fail-under=80
```

### Parallel Execution

```bash
# pytest-xdist를 사용한 병렬 실행 (Run tests in parallel using pytest-xdist)
# Note: Install first with `uv add --dev pytest-xdist`
uv run pytest -n auto              # Auto-detect CPU count
uv run pytest -n 4                 # Run on 4 cores
```

### Output Control

```bash
# Capture control (출력 캡처 제어)
uv run pytest -s                   # Show print statements (no capture)
uv run pytest --capture=no         # Same as -s
uv run pytest --tb=short           # Shorter traceback format
uv run pytest --tb=line            # One line per failure
uv run pytest --tb=no              # No traceback
```

### E2E Test Execution

E2E 테스트는 실제 서버가 필요합니다:

```bash
# 1. Start the database (데이터베이스 시작)
docker compose up postgres -d

# 2. Run migrations (마이그레이션 실행)
python3 scripts/migrate.py upgrade

# 3. Start the server (서버 시작)
uv run uvicorn src.agent_server.main:app --reload

# 4. In another terminal, run E2E tests (다른 터미널에서 E2E 테스트 실행)
uv run pytest tests/e2e/

# Or use Docker Compose for full setup (또는 Docker Compose로 전체 설정)
docker compose up open-langgraph -d
uv run pytest tests/e2e/
```

**Environment Variables for E2E:**

```bash
# Set custom server URL (커스텀 서버 URL 설정)
SERVER_URL=http://localhost:8000 uv run pytest tests/e2e/

# Use different auth type (다른 인증 타입 사용)
AUTH_TYPE=noop uv run pytest tests/e2e/
```

### Makefile Shortcuts

프로젝트 루트의 `Makefile`은 편리한 단축 명령어를 제공합니다:

```bash
# Run all tests (모든 테스트 실행)
make test

# Run with coverage (커버리지 측정)
make test-cov

# Run specific test types
make test-unit          # Unit tests only
make test-integration   # Integration tests only
make test-e2e          # E2E tests only
```

## 5. 픽스처 및 헬퍼 (Fixtures and Helpers)

### Global Fixtures (`tests/conftest.py`)

전역 픽스처는 모든 테스트에서 사용 가능합니다.

**Available Global Fixtures:**

```python
# User fixtures
dummy_user              # DummyUser instance
test_user_identity      # String: "test-user"

# Session fixtures
basic_session           # BasicSession mock
basic_client            # Test client with basic session
threads_client          # Test client for thread operations
runs_client             # Test client for run operations

# Service mocks
mock_assistant_service  # AsyncMock for assistant service
mock_store              # AsyncMock for store
```

**Usage Example:**

```python
def test_example(dummy_user, basic_client):
    """Test using global fixtures"""
    assert dummy_user.user_id == "test-user"
    response = basic_client.get("/health")
    assert response.status_code == 200
```

### Fixture Modules (`tests/fixtures/`)

#### `auth.py` - Authentication Fixtures

```python
from tests.fixtures.auth import DummyUser

# DummyUser provides a mock user for testing
user = DummyUser()
print(user.user_id)  # "test-user"
print(user.metadata)  # {"role": "user"}
```

#### `clients.py` - Test Client Fixtures

```python
from tests.fixtures.clients import (
    create_test_app,
    make_client,
    install_dummy_user_middleware
)

# Create a FastAPI test app
app = create_test_app(
    include_runs=True,
    include_threads=True
)

# Create a test client
client = make_client(app)

# Install dummy user middleware for auth
install_dummy_user_middleware(app)
```

#### `database.py` - Database Fixtures

```python
from tests.fixtures.database import (
    DummySessionBase,
    override_get_session_dep
)

# Mock database session
session = DummySessionBase()

# Override FastAPI dependency
override_get_session_dep(app, DummySessionBase)
```

#### `langgraph.py` - LangGraph Mocks

```python
from tests.fixtures.langgraph import (
    FakeAgent,
    FakeGraph,
    FakeSnapshot,
    make_snapshot,
    patch_langgraph_service
)

# Create fake snapshot
snapshot = make_snapshot(
    values={"state": "data"},
    cfg={"configurable": {"thread_id": "123"}},
    next_nodes=["node_1"]
)

# Create fake agent with snapshots
agent = FakeAgent(snapshots=[snapshot])

# Create fake graph with events
graph = FakeGraph(events=[
    ("values", {"key": "value"}),
    ("updates", {"data": "test"})
])

# Patch LangGraph service for testing
with patch_langgraph_service(agent=agent):
    # Your test code here
    pass
```

#### `test_helpers.py` - Model Factories

```python
from tests.fixtures.test_helpers import (
    make_assistant,
    make_thread,
    make_run,
    DummyRun,
    DummyThread,
    DummyStoreItem
)

# Create test models
assistant = make_assistant(
    assistant_id="asst-123",
    name="Test Assistant",
    graph_id="my-graph",
    user_id="user-123"
)

thread = make_thread(
    thread_id="thread-123",
    status="idle",
    user_id="user-123"
)

run = make_run(
    run_id="run-123",
    thread_id="thread-123",
    assistant_id="asst-123",
    status="running",
    user_id="user-123"
)

# Or use dummy classes
dummy_run = DummyRun(run_id="run-456")
dummy_thread = DummyThread(thread_id="thread-456")
```

#### `session_fixtures.py` - Session Fixtures

```python
from tests.fixtures.session_fixtures import (
    BasicSession,
    ThreadSession,
    RunSession,
    override_session_dependency
)

# Different session types for different scenarios
basic_session = BasicSession()
thread_session = ThreadSession()
run_session = RunSession()

# Override session dependency in app
override_session_dependency(app, ThreadSession)
```

### E2E Utilities (`tests/e2e/_utils.py`)

```python
from tests.e2e._utils import elog, get_e2e_client

# Get LangGraph SDK client for E2E tests
client = get_e2e_client()  # Uses SERVER_URL env var

# Pretty-print logs for E2E visibility
elog("Test Step", {"key": "value", "status": "success"})
# Output:
# === Test Step ===
# {
#   "key": "value",
#   "status": "success"
# }
```

### Custom Fixtures by Test Level

각 테스트 레벨은 자체 `conftest.py`에서 특화된 픽스처를 정의할 수 있습니다:

- **`tests/unit/conftest.py`**: Unit test에 특화된 픽스처
- **`tests/integration/conftest.py`**: Integration test에 특화된 픽스처
- **`tests/e2e/conftest.py`**: E2E test에 특화된 픽스처

## 6. 테스트 작성 가이드 (Test Writing Guide)

### Unit Test 작성 패턴

**Structure:**

```python
"""Module docstring describing what's being tested"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from src.agent_server.module import ClassToTest


class TestClassName:
    """Test class for ClassName"""

    def setup_method(self):
        """Setup runs before each test method"""
        self.instance = ClassToTest()

    def teardown_method(self):
        """Cleanup runs after each test method"""
        pass

    def test_method_success_case(self):
        """Test method behavior in success case"""
        # Arrange
        input_data = {"key": "value"}

        # Act
        result = self.instance.method(input_data)

        # Assert
        assert result == expected_value

    def test_method_error_case(self):
        """Test method behavior when error occurs"""
        # Arrange
        invalid_input = None

        # Act & Assert
        with pytest.raises(ValueError):
            self.instance.method(invalid_input)
```

**Best Practices:**

1. **AAA Pattern**: Arrange, Act, Assert
2. **Descriptive Names**: `test_<method>_<scenario>_<expected>`
3. **One Concept**: 하나의 테스트는 하나의 개념만 검증
4. **Mock External Dependencies**: 외부 의존성은 항상 Mock
5. **Use Fixtures**: 공통 설정은 픽스처로 추출

**Example - Testing with Mocks:**

```python
from unittest.mock import AsyncMock, patch
import pytest

class TestAssistantService:
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = AsyncMock()
        session.execute.return_value.scalars.return_value.first.return_value = None
        return session

    @pytest.mark.asyncio
    async def test_create_assistant_success(self, mock_session):
        """Test successful assistant creation"""
        # Arrange
        service = AssistantService(session=mock_session)
        data = {"name": "Test", "graph_id": "my-graph"}

        # Act
        result = await service.create_assistant(data, user_id="user-123")

        # Assert
        assert result.name == "Test"
        assert result.graph_id == "my-graph"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
```

### Integration Test 작성 패턴

**Structure:**

```python
import pytest
from tests.fixtures.database import get_test_db_session
from src.agent_server.services import AssistantService


@pytest.mark.integration
class TestAssistantServiceIntegration:
    """Integration tests for AssistantService with real database"""

    @pytest.fixture
    async def db_session(self):
        """Get real test database session"""
        async with get_test_db_session() as session:
            yield session
            # Cleanup happens after yield

    @pytest.mark.asyncio
    async def test_crud_operations(self, db_session):
        """Test complete CRUD workflow with database"""
        service = AssistantService(session=db_session)

        # Create
        assistant = await service.create_assistant(
            {"name": "Test", "graph_id": "graph"},
            user_id="user-123"
        )
        assert assistant.assistant_id is not None

        # Read
        retrieved = await service.get_assistant(assistant.assistant_id)
        assert retrieved.name == "Test"

        # Update
        updated = await service.update_assistant(
            assistant.assistant_id,
            {"name": "Updated"}
        )
        assert updated.name == "Updated"

        # Delete
        await service.delete_assistant(assistant.assistant_id)
        deleted = await service.get_assistant(assistant.assistant_id)
        assert deleted is None
```

**Best Practices:**

1. **Real Database**: 실제 PostgreSQL 데이터베이스 사용
2. **Transaction Isolation**: 각 테스트는 독립된 트랜잭션
3. **Cleanup**: 테스트 후 데이터 정리
4. **Test Data**: 의미 있는 테스트 데이터 사용
5. **Async/Await**: 비동기 작업 적절히 처리

### E2E Test 작성 패턴

**Structure:**

```python
import pytest
from tests.e2e._utils import elog, get_e2e_client


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_complete_workflow():
    """Test complete user workflow from start to finish"""
    client = get_e2e_client()

    # Step 1: Create assistant
    assistant = await client.assistants.create(
        name="E2E Test Assistant",
        graph_id="agent"
    )
    elog("Assistant created", assistant)

    try:
        # Step 2: Create thread
        thread = await client.threads.create(
            metadata={"test": "e2e"}
        )
        elog("Thread created", thread)

        # Step 3: Create run
        run = await client.runs.create(
            thread_id=thread["thread_id"],
            assistant_id=assistant["assistant_id"],
            input={"message": "Hello"}
        )
        elog("Run created", run)

        # Step 4: Wait for completion
        await client.runs.join(
            thread_id=thread["thread_id"],
            run_id=run["run_id"]
        )

        # Step 5: Verify results
        final_run = await client.runs.get(
            thread_id=thread["thread_id"],
            run_id=run["run_id"]
        )
        assert final_run["status"] == "success"
        elog("Run completed successfully", final_run)

    finally:
        # Cleanup
        await client.assistants.delete(
            assistant_id=assistant["assistant_id"]
        )
```

**Best Practices:**

1. **Full System**: 전체 시스템 사용 (DB, LangGraph, API)
2. **Real Workflows**: 실제 사용자 시나리오 재현
3. **Cleanup**: finally 블록에서 리소스 정리
4. **Logging**: `elog()`로 각 단계 로깅
5. **Assertions**: 중요한 상태 전이 검증

### Parametrized Tests

동일한 테스트 로직을 여러 입력값으로 실행:

```python
import pytest

@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("Test", "TEST"),
])
def test_uppercase(input, expected):
    """Test uppercase conversion with multiple inputs"""
    assert input.upper() == expected


@pytest.mark.parametrize("status", ["idle", "running", "completed", "failed"])
@pytest.mark.asyncio
async def test_thread_status_transitions(status):
    """Test thread behavior for different statuses"""
    thread = make_thread(status=status)
    assert thread.status == status
```

### Async Tests

비동기 테스트는 `@pytest.mark.asyncio` 사용:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_async_endpoint():
    """Test async API endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_async_service_method():
    """Test async service method"""
    service = MyAsyncService()
    result = await service.async_method()
    assert result is not None
```

### Testing Exceptions

예외 처리 테스트:

```python
import pytest
from src.agent_server.exceptions import AssistantNotFoundError

def test_raises_exception():
    """Test that exception is raised"""
    with pytest.raises(ValueError):
        raise ValueError("Test error")


def test_raises_with_message():
    """Test exception with specific message"""
    with pytest.raises(ValueError, match="Test error"):
        raise ValueError("Test error")


@pytest.mark.asyncio
async def test_async_raises():
    """Test async exception"""
    async def failing_function():
        raise AssistantNotFoundError("assistant-123")

    with pytest.raises(AssistantNotFoundError) as exc_info:
        await failing_function()

    assert "assistant-123" in str(exc_info.value)
```

### Testing with Context Managers

컨텍스트 매니저 테스트:

```python
from unittest.mock import patch

def test_with_context_manager():
    """Test using context manager"""
    with patch('module.function') as mock_func:
        mock_func.return_value = "mocked"
        result = function_that_calls_function()
        assert result == "mocked"
        mock_func.assert_called_once()
```

### Testing Streaming

SSE 스트리밍 테스트:

```python
@pytest.mark.asyncio
async def test_streaming_events():
    """Test SSE streaming"""
    client = get_e2e_client()

    # Create run
    run = await client.runs.create(...)

    # Stream events
    events = []
    async for chunk in client.runs.stream(
        thread_id=run["thread_id"],
        run_id=run["run_id"]
    ):
        events.append(chunk)

    # Verify events
    assert len(events) > 0
    assert events[0]["event"] == "metadata"
    assert events[-1]["event"] == "end"
```

### Test Organization Checklist

새 테스트를 작성할 때:

- [ ] 적절한 테스트 레벨 선택 (unit/integration/e2e)
- [ ] 명확하고 설명적인 테스트 이름
- [ ] Docstring으로 테스트 목적 설명
- [ ] 적절한 마커 추가 (`@pytest.mark.unit`, etc.)
- [ ] AAA 패턴 따르기 (Arrange, Act, Assert)
- [ ] 외부 의존성 적절히 Mock
- [ ] 테스트 후 리소스 정리 (cleanup)
- [ ] Edge cases 및 error cases 테스트
- [ ] 비동기 테스트에 `@pytest.mark.asyncio` 사용

## 7. CI/CD Integration

### GitHub Actions Workflow

테스트는 CI/CD 파이프라인에서 다음 순서로 실행됩니다:

```yaml
# .github/workflows/test.yml
stages:
  - lint           # Code quality checks
  - unit           # Fast unit tests
  - integration    # Integration tests (if unit passes)
  - e2e           # E2E tests (if integration passes)
```

**Optimization Strategy:**

1. **Fast Feedback**: Unit tests가 가장 먼저 실행되어 빠른 피드백 제공
2. **Fail Fast**: 이전 단계 실패 시 다음 단계 건너뜀
3. **Resource Efficiency**: 느린 테스트는 필요할 때만 실행
4. **Parallel Execution**: 가능한 경우 테스트 병렬 실행

### Pre-commit Hooks

로컬 개발 시 자동 검증:

```bash
# Install pre-commit hooks
make dev-install

# Hooks will run on git commit:
# - ruff format (code formatting)
# - ruff check (linting)
# - mypy (type checking)
# - pytest tests/unit/ (fast unit tests)
```

## 8. Troubleshooting

### Common Issues

**Import Errors:**

```bash
# Problem: ModuleNotFoundError
# Solution: Run pytest from project root
cd /Users/jhj/Desktop/personal/opensource-langgraph-platform
uv run pytest tests/
```

**Database Connection Errors:**

```bash
# Problem: Cannot connect to database
# Solution: Ensure Docker is running
docker compose up postgres -d

# Verify database is accessible
docker compose ps
```

**Async Test Warnings:**

```bash
# Problem: RuntimeWarning about async generators
# Solution: Use --asyncio-mode=auto
uv run pytest --asyncio-mode=auto
```

**Fixture Not Found:**

```python
# Problem: fixture 'xxx' not found
# Solution: Check conftest.py imports and fixture scope

# Make sure fixture is defined in accessible conftest.py
# or imported in the test file
from tests.fixtures.auth import DummyUser
```

**E2E Tests Timeout:**

```bash
# Problem: E2E tests hang or timeout
# Solution: Increase timeout or check server status

# Check if server is running
curl http://localhost:8000/health

# Set custom timeout in pytest.ini
[tool.pytest.ini_options]
asyncio_default_fixture_loop_scope = "function"
timeout = 300
```

### Debugging Tips

**Print Debugging:**

```bash
# Show print statements during test execution
uv run pytest -s

# Show local variables on failure
uv run pytest -l
```

**Verbose Output:**

```bash
# Show detailed test output
uv run pytest -vv

# Show full diff for assertions
uv run pytest -vv --tb=long
```

**Run Specific Test:**

```bash
# When a test fails, run only that test
uv run pytest tests/unit/test_services/test_event_converter.py::TestEventConverter::test_parse_raw_event_tuple_2_elements -vv
```

**Debug with PDB:**

```python
def test_debug_example():
    """Test with debugger"""
    import pdb; pdb.set_trace()  # Breakpoint
    result = function_to_debug()
    assert result == expected
```

```bash
# Run with PDB
uv run pytest --pdb  # Drop into debugger on failure
```

## 9. Best Practices Summary

### Testing Principles

1. **Fast Feedback Loop**: Unit tests가 대부분의 로직 커버
2. **Test Pyramid**: 많은 unit tests, 적당한 integration tests, 적은 E2E tests
3. **DRY (Don't Repeat Yourself)**: 공통 로직은 픽스처로 추출
4. **Isolation**: 각 테스트는 독립적으로 실행 가능
5. **Clarity**: 테스트 이름과 구조로 의도 명확히 전달

### Code Quality

1. **Descriptive Names**: 테스트 이름이 문서 역할
2. **Comments**: 복잡한 로직에 주석 추가
3. **Assertions**: 명확하고 구체적인 assertion
4. **Error Messages**: 실패 시 유용한 에러 메시지
5. **Coverage**: 중요한 코드 경로 모두 테스트

### Maintenance

1. **Keep Tests Updated**: 코드 변경 시 테스트도 업데이트
2. **Refactor Tests**: 테스트 코드도 리팩토링 필요
3. **Remove Obsolete Tests**: 불필요한 테스트 제거
4. **Monitor Performance**: 느려지는 테스트 최적화
5. **Document Changes**: 테스트 구조 변경 시 문서 업데이트

## 10. Additional Resources

### Documentation

- **README.md**: 사람이 읽기 쉬운 테스트 개요
- **AGENTS.md** (this file): AI agent를 위한 상세 가이드
- **CLAUDE.md** (project root): 프로젝트 전체 가이드

### External References

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [LangGraph Testing](https://langchain-ai.github.io/langgraph/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)

### Internal Tools

- **Makefile**: 테스트 실행 단축 명령어
- **pyproject.toml**: pytest 설정 및 dependencies
- **.github/workflows/**: CI/CD 파이프라인 정의

---

**Last Updated**: 2025-10-27
**Maintained by**: Open LangGraph Development Team
**For Questions**: Open an issue or PR in the repository
