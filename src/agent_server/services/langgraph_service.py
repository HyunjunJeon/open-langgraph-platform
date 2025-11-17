"""LangGraph 통합 서비스 및 그래프 관리자

이 모듈은 Open LangGraph의 LangGraph 그래프 로딩, 설정 관리, 실행 설정 생성을 담당합니다.
open_langgraph.json에서 그래프 정의를 읽어 동적으로 로드하고,
각 그래프에 대한 기본 어시스턴트를 자동으로 생성합니다.

주요 구성 요소:
• LangGraphService - 그래프 로딩, 캐싱, 설정 관리
• inject_user_context() - 사용자 컨텍스트를 LangGraph config에 주입
• create_thread_config() - 스레드별 실행 설정 생성
• create_run_config() - 실행별 설정 생성 (관찰성 콜백 포함)

사용 예:
    from services.langgraph_service import get_langgraph_service

    service = get_langgraph_service()
    await service.initialize()
    graph = await service.get_graph("weather_agent")
"""

import importlib.util
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, TypedDict, cast
from uuid import uuid5

from langgraph.graph.state import CompiledStateGraph

from ..constants import ASSISTANT_NAMESPACE_UUID
from ..observability.langfuse_integration import get_tracing_callbacks

CompiledGraph = CompiledStateGraph[Any, Any, Any, Any]


class GraphDefinition(TypedDict):
    file_path: str
    export_name: str


class LangGraphService:
    """LangGraph 그래프 로딩 및 설정 관리 서비스

    이 클래스는 open_langgraph.json 설정 파일을 읽어 LangGraph 그래프를 동적으로 로드하고,
    각 그래프에 대한 기본 어시스턴트를 자동으로 생성합니다.

    주요 기능:
    - 그래프 레지스트리 관리: open_langgraph.json에서 그래프 정의 로드
    - 그래프 캐싱: 로드된 그래프를 메모리에 캐시하여 성능 향상
    - 자동 컴파일: 그래프를 Postgres 체크포인터와 함께 컴파일
    - 기본 어시스턴트 생성: 각 그래프에 대해 deterministic UUID로 어시스턴트 생성

    아키텍처 패턴:
    - 싱글톤: 애플리케이션 전체에서 단일 인스턴스 사용
    - 지연 로딩: 그래프를 필요할 때만 로드 및 컴파일
    - 캐싱: 컴파일된 그래프를 메모리에 저장하여 재사용
    """

    def __init__(self, config_path: str = "open_langgraph.json") -> None:
        # 설정 파일 경로 (OPEN_LANGGRAPH_CONFIG 환경 변수나 open_langgraph.json으로 오버라이드 가능)
        self.config_path = Path(config_path)
        self.config: dict[str, Any] | None = None
        # 그래프 레지스트리: graph_id -> {file_path, export_name}
        self._graph_registry: dict[str, GraphDefinition] = {}
        # 컴파일된 그래프 캐시: graph_id -> CompiledGraph
        self._graph_cache: dict[str, CompiledGraph] = {}

    async def initialize(self) -> None:
        """설정 파일을 로드하고 그래프 레지스트리 설정

        open_langgraph.json 설정 파일을 찾아 로드한 후 그래프 레지스트리를 초기화합니다.
        각 그래프에 대해 기본 어시스턴트를 자동으로 생성하여
        클라이언트가 graph_id만으로 그래프를 실행할 수 있도록 합니다.

        설정 파일 해석 우선순위:
        1) OPEN_LANGGRAPH_CONFIG 환경 변수 (절대 경로 또는 상대 경로)
        2) 생성자에 명시된 self.config_path (존재하는 경우)
        3) 현재 작업 디렉토리의 open_langgraph.json
        4) 현재 작업 디렉토리의 langgraph.json (fallback)

        동작 흐름:
        1. 설정 파일 경로 해석 (위 우선순위에 따라)
        2. JSON 파일 로드 및 파싱
        3. 그래프 레지스트리 초기화 (_load_graph_registry)
        4. 각 그래프에 대한 기본 어시스턴트 생성 (_ensure_default_assistants)

        Raises:
            ValueError: 설정 파일을 찾을 수 없는 경우
        """
        # 1) 환경 변수 오버라이드 우선
        env_path = os.getenv("OPEN_LANGGRAPH_CONFIG")
        resolved_path: Path
        if env_path:
            resolved_path = Path(env_path)
        # 2) 생성자에 제공된 경로가 존재하면 사용
        elif self.config_path and Path(self.config_path).exists():
            resolved_path = Path(self.config_path)
        # 3) open_langgraph.json이 현재 디렉토리에 있으면 사용
        elif Path("open_langgraph.json").exists():
            resolved_path = Path("open_langgraph.json")
        # 4) langgraph.json으로 fallback
        else:
            resolved_path = Path("langgraph.json")

        if not resolved_path.exists():
            raise ValueError(
                "Configuration file not found. Expected one of: "
                "OPEN_LANGGRAPH_CONFIG path, ./open_langgraph.json, or ./langgraph.json"
            )

        # 선택된 경로를 저장하여 나중에 참조할 수 있도록 함
        self.config_path = resolved_path

        with self.config_path.open() as f:
            loaded_config = json.load(f)

        if not isinstance(loaded_config, dict):
            raise ValueError(f"Invalid configuration format in {self.config_path}; expected JSON object")

        self.config = cast("dict[str, Any]", loaded_config)

        # 설정 파일에서 그래프 레지스트리 로드
        self._load_graph_registry()

        # 각 그래프에 대해 deterministic UUID로 기본 어시스턴트 생성
        # 클라이언트가 graph_id를 직접 전달할 수 있도록 함
        await self._ensure_default_assistants()

    def _load_graph_registry(self) -> None:
        """open_langgraph.json에서 그래프 정의를 파싱하여 레지스트리에 등록

        설정 파일의 "graphs" 섹션을 읽어 각 그래프의 파일 경로와
        export 이름을 파싱합니다.

        경로 형식:
            "./graphs/weather_agent.py:graph"
            - 콜론(:) 앞: Python 파일 경로
            - 콜론(:) 뒤: 모듈에서 export할 변수 이름

        동작:
            각 graph_id를 키로 하여 {file_path, export_name} 딕셔너리를
            _graph_registry에 저장합니다.

        Raises:
            ValueError: 경로 형식이 잘못된 경우 (콜론이 없는 경우)
        """
        if self.config is None:
            self._graph_registry = {}
            return

        graphs_config = self.config.get("graphs", {})

        for graph_id, graph_path in graphs_config.items():
            # 경로 형식 파싱: "./graphs/weather_agent.py:graph"
            if ":" not in graph_path:
                raise ValueError(f"Invalid graph path format: {graph_path}")

            file_path, export_name = graph_path.split(":", 1)
            self._graph_registry[graph_id] = {
                "file_path": file_path,
                "export_name": export_name,
            }

    async def _ensure_default_assistants(self) -> None:
        """각 그래프에 대해 deterministic UUID로 기본 어시스턴트 생성

        이 메서드는 각 그래프마다 하나의 기본 어시스턴트를 생성하여
        클라이언트가 graph_id만으로 그래프를 실행할 수 있도록 합니다.

        UUID 생성 방식:
            uuid5(ASSISTANT_NAMESPACE_UUID, graph_id)를 사용하여
            동일한 graph_id는 항상 동일한 assistant_id를 생성합니다.
            이를 통해 서버 재시작 후에도 일관된 ID를 유지합니다.

        멱등성:
            이미 존재하는 어시스턴트는 스킵하므로 여러 번 호출해도 안전합니다.

        생성되는 어시스턴트:
        - assistant_id: uuid5(namespace, graph_id)
        - name: graph_id
        - description: "Default assistant for graph '{graph_id}'"
        - graph_id: 해당 그래프 ID
        - config: {} (빈 설정)
        - user_id: "system"
        """
        from sqlalchemy import select

        from ..core.orm import Assistant as AssistantORM
        from ..core.orm import get_session

        # 고정된 네임스페이스로 graph_id로부터 assistant_id 도출
        NS = ASSISTANT_NAMESPACE_UUID
        session_gen = get_session()
        session = await anext(session_gen)
        try:
            for graph_id in self._graph_registry:
                # deterministic UUID 생성
                assistant_id = str(uuid5(NS, graph_id))
                existing = await session.scalar(
                    select(AssistantORM).where(AssistantORM.assistant_id == assistant_id)
                )
                if existing:
                    # 이미 존재하면 스킵 (멱등성 보장)
                    continue
                # 새 기본 어시스턴트 생성
                session.add(
                    AssistantORM(
                        assistant_id=assistant_id,
                        name=graph_id,
                        description=f"Default assistant for graph '{graph_id}'",
                        graph_id=graph_id,
                        config={},
                        user_id="system",
                    )
                )
            await session.commit()
        finally:
            await session.close()

    async def get_graph(self, graph_id: str, force_reload: bool = False) -> CompiledGraph:
        """그래프 ID로 컴파일된 그래프를 가져오기 (캐싱 및 LangGraph 통합)

        이 메서드는 요청된 그래프를 로드하고 Postgres 체크포인터와 함께
        컴파일하여 상태 영속성을 보장합니다.

        동작 흐름:
        1. 그래프 레지스트리에서 그래프 존재 확인
        2. 캐시 확인: force_reload가 아니면 캐시된 그래프 반환
        3. 파일에서 그래프 로드 (_load_graph_from_file)
        4. 그래프 컴파일 처리:
           a. 미컴파일 StateGraph: Postgres 체크포인터로 컴파일
           b. 이미 컴파일된 그래프: copy()로 체크포인터 주입 시도
           c. 주입 실패 시: 원본 그래프 사용 (경고 출력)
        5. 컴파일된 그래프를 캐시에 저장
        6. 컴파일된 그래프 반환

        Args:
            graph_id (str): 로드할 그래프 ID (open_langgraph.json에 정의)
            force_reload (bool): True면 캐시 무시하고 재로드 (기본값: False)

        Returns:
            StateGraph[Any]: Postgres 체크포인터와 함께 컴파일된 그래프

        Raises:
            ValueError: 그래프를 레지스트리에서 찾을 수 없는 경우

        참고:
            - Postgres 체크포인터: 상태 스냅샷(체크포인트) 저장
            - Postgres Store: 장기 메모리 및 키-값 저장소
            - 캐싱: 동일 그래프의 반복 로드 성능 향상
        """
        if graph_id not in self._graph_registry:
            raise ValueError(f"Graph not found: {graph_id}")

        # 캐시된 그래프가 있고 강제 재로드가 아니면 캐시 반환
        if not force_reload and graph_id in self._graph_cache:
            return self._graph_cache[graph_id]

        graph_info = self._graph_registry[graph_id]

        # 파일에서 그래프 로드
        base_graph = await self._load_graph_from_file(graph_id, graph_info)

        # 모든 그래프를 Postgres 체크포인터와 함께 컴파일하여 영속성 보장
        from ..core.database import db_manager

        checkpointer_cm = await db_manager.get_checkpointer()
        store_cm = await db_manager.get_store()

        compiled_graph: CompiledGraph
        if isinstance(base_graph, CompiledStateGraph):
            try:
                compiled_graph = cast(
                    "CompiledGraph",
                    base_graph.copy(update={"checkpointer": checkpointer_cm, "store": store_cm}),
                )
            except Exception:
                print(
                    f"⚠️  Pre-compiled graph '{graph_id}' does not support checkpointer injection; running without persistence"
                )
                compiled_graph = cast("CompiledGraph", base_graph)
        elif hasattr(base_graph, "compile"):
            print(f"🔧 Compiling graph '{graph_id}' with Postgres persistence")
            compiled_graph = cast(
                "CompiledGraph",
                base_graph.compile(checkpointer=checkpointer_cm, store=store_cm),
            )
        else:
            raise TypeError(f"Graph '{graph_id}' must export a StateGraph or CompiledStateGraph")

        # 컴파일된 그래프를 캐시에 저장
        self._graph_cache[graph_id] = compiled_graph

        return compiled_graph

    async def _load_graph_from_file(self, graph_id: str, graph_info: GraphDefinition) -> Any:
        """Dynamically load a graph module from the filesystem

        This method dynamically imports a graph module from a Python file
        and returns the graph object with the specified export name.

        Workflow:
        1. Check if the file path exists
        2. Create a module spec using importlib
        3. Dynamically load and execute the module
        4. Extract the graph object specified by export_name
        5. Return the graph object (regardless of whether it's compiled)

        Args:
            graph_id (str): Graph ID (for logging/debugging)
            graph_info (dict[str, str]): Graph information
                - file_path: Path to the Python file
                - export_name: Name of the variable to export from the module

        Returns:
            StateGraph | CompiledGraph: The loaded graph object
                (compilation status depends on the module)

        Raises:
            ValueError: If the file does not exist, module loading fails, or the export cannot be found

        Note:
            The graph may be in a compiled or uncompiled state.
            Checkpointer injection is handled by the caller (get_graph).
        """
        file_path = Path(graph_info["file_path"])
        if not file_path.exists():
            raise ValueError(f"Graph file not found: {file_path}")

        # 그래프 모듈 동적 import
        spec = importlib.util.spec_from_file_location(f"graphs.{graph_id}", str(file_path.resolve()))
        if spec is None or spec.loader is None:
            raise ValueError(f"Failed to load graph module: {file_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # export된 그래프 가져오기
        export_name = graph_info["export_name"]
        if not hasattr(module, export_name):
            raise ValueError(f"Graph export not found: {export_name} in {file_path}")

        graph = getattr(module, export_name)

        # 그래프는 모듈에서 이미 컴파일되어 있을 수도 있음
        # 체크포인터/store 주입은 실행 시점에 처리됨
        return graph

    def list_graphs(self) -> dict[str, str]:
        """Return a list of all registered graphs

        Returns:
            dict[str, str]: A mapping of graph_id to file_path
                e.g., {"weather_agent": "./graphs/weather_agent.py"}
        """
        return {graph_id: info["file_path"] for graph_id, info in self._graph_registry.items()}

    def invalidate_cache(self, graph_id: str | None = None) -> None:
        """Invalidate the graph cache (for hot reloading)

        This method deletes a cached graph, forcing it to be reloaded from the filesystem
        on the next get_graph() call.

        Use cases:
        - Hot reloading after changing graph code during development
        - Applying a new version of a graph after deployment

        Args:
            graph_id (str | None): The ID of the graph to invalidate.
                If None, clears the entire graph cache.
        """
        if graph_id:
            self._graph_cache.pop(graph_id, None)
        else:
            self._graph_cache.clear()

    def get_config(self) -> dict[str, Any] | None:
        """Return the loaded configuration file content

        Returns:
            dict[str, Any] | None: The full content of open_langgraph.json
        """
        return self.config

    def get_dependencies(self) -> list[str]:
        """Return the dependencies section of the configuration file

        Returns:
            list: A list of dependency packages (the "dependencies" field in open_langgraph.json)
        """
        if self.config is None:
            return []
        deps = self.config.get("dependencies", [])
        if isinstance(deps, list):
            return [str(dep) for dep in deps]
        return []


# Global service instance (singleton pattern)
_langgraph_service: LangGraphService | None = None


def get_langgraph_service() -> LangGraphService:
    """Return the global LangGraph service instance (singleton)

    This function returns the same LangGraphService instance throughout the application,
    sharing the graph cache and configuration.

    Returns:
        LangGraphService: The singleton service instance
    """
    global _langgraph_service
    if _langgraph_service is None:
        _langgraph_service = LangGraphService()
    return _langgraph_service


def inject_user_context(user: Any, base_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Inject user context into LangGraph config (for multi-tenancy isolation)

    This function injects user information into LangGraph's configurable section,
    allowing graph nodes to access user data.

    Injected information:
    - user_id: Unique user identifier (for multi-tenancy isolation)
    - user_display_name: User's display name
    - langgraph_auth_user: Full authentication payload (for graph nodes)

    Use cases:
    - Accessing user info in graph nodes via Runtime[Context]
    - Filtering data and checking permissions by user
    - Including user ID in logging and tracing

    Args:
        user: Authenticated user object (with identity, display_name, to_dict())
        base_config (dict | None): Existing config (default: {})

    Returns:
        dict: LangGraph config with user context injected

    Note:
        - Does not overwrite existing configurable values (uses setdefault)
        - Skips user info injection if user is None
        - Injects minimal identity if to_dict() fails
    """
    config: dict[str, Any] = (base_config or {}).copy()
    configurable = config.get("configurable")
    if not isinstance(configurable, dict):
        configurable = {}
    config["configurable"] = configurable

    # Inject user-related data (only if user exists)
    if user:
        # Default user identifier for multi-tenancy isolation
        identity = getattr(user, "identity", None)
        if identity is not None:
            config["configurable"].setdefault("user_id", identity)
        display_name = getattr(user, "display_name", None)
        config["configurable"].setdefault("user_display_name", display_name or identity)

        # Full authentication payload for use in graph nodes
        if "langgraph_auth_user" not in config["configurable"]:
            try:
                payload = user.to_dict()  # type: ignore[attr-defined]
                if isinstance(payload, dict):
                    config["configurable"]["langgraph_auth_user"] = payload
                else:
                    raise TypeError("User payload is not a dictionary")
            except Exception:
                # Fallback: use minimal dictionary if to_dict() is not available
                if identity is not None:
                    config["configurable"]["langgraph_auth_user"] = {"identity": identity}

    return config


def create_thread_config(
    thread_id: str,
    user: Any,
    additional_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create LangGraph config for a specific thread (with user context)

    This function creates a per-thread execution config and automatically injects user information.
    LangGraph uses this config to load the correct thread state from the checkpointer.

    Workflow:
    1. Create a base config including thread_id
    2. Merge additional_config into the base config
    3. Inject user information with inject_user_context()
    4. Return the completed config

    Args:
        thread_id (str): Unique thread identifier
        user: Authenticated user object
        additional_config (dict | None): Additional config (default: None)

    Returns:
        dict: LangGraph config including thread_id and user context

    Usage example:
        config = create_thread_config("thread_123", user)
        state = await graph.aget_state(config)
    """
    base_config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

    if isinstance(additional_config, dict):
        base_config.update(additional_config)

    return inject_user_context(user, base_config)


def create_run_config(
    run_id: str,
    thread_id: str,
    user: Any,
    additional_config: dict[str, Any] | None = None,
    checkpoint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create LangGraph config for a specific run (with observability callbacks)

    This function creates a per-run config and automatically adds:
    - thread_id, run_id: Execution context identifiers
    - User context: For multi-tenancy isolation and permission management
    - Observability callbacks: For integration with tracing systems like Langfuse
    - Checkpoint parameters: For resuming from a specific state

    Design principle:
        This function is **additive** and does not remove or rename any settings
        provided by the client. It just ensures the configurable dictionary
        exists and merges server-side keys so that graph nodes can rely on them.

    Args:
        run_id (str): Unique run identifier
        thread_id (str): Unique thread identifier
        user: Authenticated user object
        additional_config (dict | None): Additional config provided by the client
        checkpoint (dict | None): Checkpoint parameters (for resuming from a specific state)

    Returns:
        dict: The complete LangGraph run config
            - configurable: thread_id, run_id, user context, checkpoint params
            - callbacks: Observability callbacks (e.g., for Langfuse)
            - metadata: Metadata for tracing systems

    Note:
        - Does not overwrite values already set by the client (uses setdefault)
        - Automatically adds callbacks and metadata if Langfuse is enabled
        - Checkpoint parameters are merged into configurable
    """

    cfg: dict[str, Any] = deepcopy(additional_config) if additional_config else {}

    # Ensure the configurable section exists
    cfg.setdefault("configurable", {})

    # Merge server-provided fields (without overwriting if client already set them)
    cfg["configurable"].setdefault("thread_id", thread_id)
    cfg["configurable"].setdefault("run_id", run_id)

    # Add observability callbacks from various potential sources
    tracing_callbacks = get_tracing_callbacks()
    if tracing_callbacks:
        existing_callbacks = cfg.get("callbacks", [])
        if not isinstance(existing_callbacks, list):
            # Could log a warning here for more robustness
            existing_callbacks = []

        # Combine existing callbacks with new tracing callbacks non-destructively
        cfg["callbacks"] = existing_callbacks + tracing_callbacks

        # Add metadata for Langfuse
        cfg.setdefault("metadata", {})
        cfg["metadata"]["langfuse_session_id"] = thread_id
        if user:
            cfg["metadata"]["langfuse_user_id"] = user.identity
            cfg["metadata"]["langfuse_tags"] = [
                "open_langgraph_run",
                f"run:{run_id}",
                f"thread:{thread_id}",
                f"user:{user.identity}",
            ]
        else:
            cfg["metadata"]["langfuse_tags"] = [
                "open_langgraph_run",
                f"run:{run_id}",
                f"thread:{thread_id}",
            ]

    # Apply checkpoint parameters if provided
    if checkpoint and isinstance(checkpoint, dict):
        cfg["configurable"].update({k: v for k, v in checkpoint.items() if v is not None})

    # Finally, inject user context via the existing helper
    return inject_user_context(user, cfg)
