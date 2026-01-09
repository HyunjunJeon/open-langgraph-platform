"""
A2A Protocol Router

Provides A2A endpoints for LangGraph agents.
"""

import logging
from typing import TYPE_CHECKING

from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from .card_generator import AgentCardGenerator
from .converter import A2AMessageConverter
from .detector import is_a2a_compatible
from .executor import LangGraphA2AExecutor

if TYPE_CHECKING:
    from ..services.langgraph_service import LangGraphService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/a2a", tags=["A2A Protocol"])

# Cache for A2A apps per graph
_a2a_apps: dict[str, A2AFastAPIApplication] = {}

# Task store (shared across all graphs)
_task_store = InMemoryTaskStore()


def _get_langgraph_service() -> "LangGraphService | None":
    """Get LangGraph service (lazy import to avoid circular deps)"""
    try:
        from ..services.langgraph_service import get_langgraph_service

        return get_langgraph_service()
    except ImportError:
        return None


def _get_base_url() -> str:
    """Get server base URL"""
    import os

    host = os.getenv("SERVER_HOST", "localhost")
    port = os.getenv("SERVER_PORT", "8000")
    scheme = os.getenv("SERVER_SCHEME", "http")
    return f"{scheme}://{host}:{port}"


async def get_or_create_a2a_app(graph_id: str) -> A2AFastAPIApplication:
    """
    Get or create A2A application for a graph.

    Args:
        graph_id: Graph identifier

    Returns:
        A2AFastAPIApplication instance

    Raises:
        HTTPException: If graph not found or not A2A compatible
    """
    if graph_id in _a2a_apps:
        return _a2a_apps[graph_id]

    service = _get_langgraph_service()
    if service is None:
        raise HTTPException(status_code=500, detail="LangGraph service not available")

    try:
        graph = await service.get_graph(graph_id)
    except ValueError:
        # Service raises ValueError when graph not in registry
        raise HTTPException(status_code=404, detail=f"Graph '{graph_id}' not found") from None

    if graph is None:
        raise HTTPException(status_code=404, detail=f"Graph '{graph_id}' not found")

    if not is_a2a_compatible(graph):
        raise HTTPException(status_code=404, detail=f"Graph '{graph_id}' is not A2A compatible (no 'messages' field)")

    # Create Agent Card
    generator = AgentCardGenerator(base_url=_get_base_url())
    agent_card = generator.generate_for_graph(graph_id, graph)

    # Create Executor
    executor = LangGraphA2AExecutor(
        graph=graph,
        graph_id=graph_id,
        converter=A2AMessageConverter(),
    )

    # Create Request Handler
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=_task_store,
    )

    # Create A2A App
    app = A2AFastAPIApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    _a2a_apps[graph_id] = app
    logger.info(f"Created A2A app for graph '{graph_id}'")

    return app


@router.get("/")
async def list_a2a_agents() -> dict:
    """
    List all A2A-compatible agents.

    Returns:
        Dictionary with agents list and count
    """
    service = _get_langgraph_service()
    if service is None:
        return {"agents": [], "count": 0}

    agents = []
    base_url = _get_base_url()

    for graph_id in service.get_graph_ids():
        graph = await service.get_graph(graph_id)
        if graph and is_a2a_compatible(graph):
            agents.append({
                "graph_id": graph_id,
                "agent_card_url": f"{base_url}/a2a/{graph_id}/.well-known/agent-card.json",
                "endpoint_url": f"{base_url}/a2a/{graph_id}",
            })

    return {"agents": agents, "count": len(agents)}


@router.get("/{graph_id}/.well-known/agent-card.json")
async def get_agent_card(graph_id: str) -> dict:
    """
    Get Agent Card for discovery.

    Args:
        graph_id: Graph identifier

    Returns:
        Agent Card as JSON (a2a.types.AgentCard Pydantic model)
    """
    app = await get_or_create_a2a_app(graph_id)
    # Use Pydantic's model_dump() for proper serialization
    # by_alias=True ensures field names match A2A protocol spec
    # exclude_none=True omits optional fields that aren't set
    return app.agent_card.model_dump(by_alias=True, exclude_none=True)


@router.post("/{graph_id}")
async def handle_a2a_post(graph_id: str, request: Request) -> Response:
    """
    Handle A2A JSON-RPC POST requests.

    Note: We use _handle_requests because A2A SDK is designed for standalone servers
    (server.build() → uvicorn.run), not for integration into existing FastAPI apps
    with dynamic {graph_id} routing. The SDK's public APIs (on_message_send, etc.)
    require manual JSON-RPC parsing which _handle_requests handles internally.

    Args:
        graph_id: Graph identifier
        request: FastAPI request

    Returns:
        A2A JSON-RPC response
    """
    app = await get_or_create_a2a_app(graph_id)
    return await app._handle_requests(request)


@router.get("/{graph_id}")
async def handle_a2a_get(graph_id: str, request: Request) -> Response:  # noqa: ARG001
    """
    Handle A2A GET requests (e.g., task subscriptions via SSE).

    Note: This endpoint is for Server-Sent Events subscriptions.
    For agent cards, use /{graph_id}/.well-known/agent-card.json

    Args:
        graph_id: Graph identifier
        request: FastAPI request

    Returns:
        A2A response (typically SSE stream)
    """
    # GET to the main endpoint is used for SSE subscriptions in A2A
    # The SDK doesn't have a direct handler for this - it's handled via POST
    # Return a helpful message instead
    return JSONResponse(
        status_code=200,
        content={
            "message": "A2A endpoint ready",
            "graph_id": graph_id,
            "hint": "Use POST for JSON-RPC requests, GET /.well-known/agent-card.json for agent card",
        },
    )


def clear_cache() -> None:
    """Clear A2A app cache (for testing)"""
    _a2a_apps.clear()
