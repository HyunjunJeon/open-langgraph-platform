"""Main FastAPI application entrypoint for Open LangGraph.

This module defines the core FastAPI application for the Open LangGraph Agent Protocol server.
It exposes LangGraph-based agents as an HTTP API, compliant with the Agent Protocol standard.

Application Architecture:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Middleware Stack (Request processing order):
   ├─ CORS Middleware: Cross-Origin Resource Sharing settings
   ├─ DoubleEncodedJSON Middleware: Handles double-encoded JSON from frontends
   └─ Authentication Middleware: User authentication based on LangGraph SDK

2. Router Structure (API Endpoints):
   ├─ /health: Server and database health checks
   ├─ /assistants: Assistant (graph) management
   ├─ /threads: Conversation thread management
   ├─ /runs: Agent execution and streaming
   └─ /store: LangGraph Store for long-term memory

3. Lifecycle Management:
   ├─ Startup: Initialize database, LangGraph service, and event store
   └─ Shutdown: Cancel running tasks, clean up resources

Key Components:
• lifespan() - Application lifecycle management (startup/shutdown)
• active_runs - Dictionary of asyncio.Tasks for tracking cancellable runs
• Global Exception Handlers - Convert exceptions to Agent Protocol error format

Usage Example:
    # Run development server
    uvicorn src.agent_server.main:app --reload

    # Run in production (specify port)
    PORT=8000 uvicorn src.agent_server.main:app

Note:
    - LangGraph graphs are defined in open_langgraph.json
    - Authentication is configured via auth.py and environment variables (AUTH_TYPE)
    - Database migrations are managed with scripts/migrate.py
"""

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
# This loads application settings like database URL, auth settings, etc.
load_dotenv()

# Add the 'graphs/' directory to the Python path to enable importing graph modules.
# Note: This must be done before importing modules that use the 'graphs/' path.
# For graphs defined in open_langgraph.json to be dynamically imported,
# they need to be in sys.path.
current_dir = Path(__file__).parent.parent.parent  # Navigate to the open-langgraph root directory
graphs_dir = current_dir / "graphs"
if str(graphs_dir) not in sys.path:
    sys.path.insert(0, str(graphs_dir))

# ruff: noqa: E402 - The imports below must be executed after the sys.path modification above
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
# Global State: Manage running agent tasks
# ---------------------------------------------------------------------------
# Track active run asyncio.Tasks for cancellation.
# key: run_id (string), value: the asyncio.Task performing the run.
# Used to cancel unfinished tasks on shutdown.
active_runs: dict[str, asyncio.Task] = {}

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """FastAPI application lifespan management context manager.

    Performs all necessary initialization tasks when the application starts,
    and safely cleans up resources on shutdown.

    Startup Sequence:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    1. Initialize Database Manager
       - Create SQLAlchemy engine (for Agent Protocol metadata)
       - Initialize LangGraph AsyncPostgresSaver (for checkpoint storage)
       - Initialize LangGraph AsyncPostgresStore (for long-term memory)
       - Automatically create database schema (.setup() call)

    2. Initialize LangGraph Service
       - Load graph definitions from open_langgraph.json
       - Create default assistants for each graph (based on UUID5)
       - Prepare graph caching system

    3. Start Event Store Cleanup Task
       - Start a background task for auto-deleting old SSE events
       - Cleans up events older than the default 7 days

    Shutdown Sequence:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    1. Cancel Active Runs
       - Cancel all running tasks registered in `active_runs`
       - Ensures graceful shutdown of in-progress agent runs

    2. Stop Event Store Cleanup Task
       - Safely terminate the background cleanup task

    3. Clean Up Database Connections
       - Dispose of the SQLAlchemy engine
       - Disconnect LangGraph components

    Args:
        _app (FastAPI): The FastAPI application instance (not used).

    Yields:
        None: Yields control back to the application as per the context manager protocol.

    Note:
        - Uses the recommended lifespan pattern for FastAPI 0.109.0+.
        - Replaces the older @app.on_event("startup")/on_event("shutdown") decorators.
        - Ensures exception safety with an async context manager.
    """
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Startup: Initialize database and LangGraph components
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    await db_manager.initialize()

    # Initialize LangGraph service
    # Loads graph definitions from open_langgraph.json and creates default assistants
    from .services.langgraph_service import get_langgraph_service

    langgraph_service = get_langgraph_service()
    await langgraph_service.initialize()

    # Start event store background cleanup task
    # Periodically deletes old SSE events to manage disk space
    from .services.event_store import event_store

    await event_store.start_cleanup_task()

    yield

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Shutdown: Clean up resources and cancel active tasks
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # Cancel all unfinished run tasks
    # Sends a cancellation signal to each task for graceful shutdown
    for task in active_runs.values():
        if not task.done():
            task.cancel()

    # Stop the event store cleanup task
    await event_store.stop_cleanup_task()

    # Close database connections
    await db_manager.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Create FastAPI application instance
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
app = FastAPI(
    title="Open LangGraph",
    description="Open LangGraph: Production-ready Agent Protocol server built on LangGraph",
    version="0.1.0",
    docs_url="/docs",  # Swagger UI auto-docs: http://localhost:8000/docs
    redoc_url="/redoc",  # ReDoc documentation: http://localhost:8000/redoc
    lifespan=lifespan,  # Application lifecycle management function
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Configure Middleware Stack (added in reverse order of execution)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Note: FastAPI middleware is executed in the reverse order it's added.
# Order of addition: CORS → DoubleEncodedJSON → Authentication
# Order of execution: Authentication → DoubleEncodedJSON → CORS → Router

# 1. CORS Middleware: Configure Cross-Origin Resource Sharing
# Allows frontend clients from different domains to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific domains
    allow_credentials=True,  # Allow cookies and auth headers
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all HTTP headers
)

# 2. DoubleEncodedJSON Middleware: Handle double-encoded JSON from frontends
# Automatically decodes JSON if it has been encoded twice by some clients
app.add_middleware(DoubleEncodedJSONMiddleware)

# 3. Authentication Middleware: User authentication based on LangGraph SDK
# Note: Must be added after CORS to handle preflight requests
# Verifies Authorization header on all requests and sets request.user
app.add_middleware(AuthenticationMiddleware, backend=get_auth_backend(), on_error=on_auth_error)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Register API Routers (Agent Protocol Endpoints)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Each router provides HTTP endpoints compliant with the Agent Protocol standard

# /health - Server health check and database connection test
app.include_router(health_router, prefix="", tags=["Health"])

# /assistants - List and create assistants (graphs)
# Graphs defined in open_langgraph.json are exposed as assistants
app.include_router(assistants_router, prefix="", tags=["Assistants"])

# /threads - Create, retrieve, update, delete (CRUD) conversation threads
# Manages conversation state based on LangGraph checkpoints
app.include_router(threads_router, prefix="", tags=["Threads"])

# /runs - Agent execution and real-time streaming
# Supports streaming via Server-Sent Events (SSE)
app.include_router(runs_router, prefix="", tags=["Runs"])

# /store - Long-term memory management via LangGraph Store
# Persistent, user- and thread-specific data storage (JSONB)
app.include_router(store_router, prefix="", tags=["Store"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Global Exception Handlers: Convert to Agent Protocol error format
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@app.exception_handler(HTTPException)
async def agent_protocol_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """Convert HTTPException to Agent Protocol standard error format.

    Transforms FastAPI's HTTPException into a standardized error response
    that complies with the Agent Protocol specification.

    Workflow:
    1. Map HTTP status code to an error type (get_error_type)
       - 400 → "invalid_request"
       - 401 → "authentication_error"
       - 403 → "permission_denied"
       - 404 → "not_found"
       - 500 → "internal_error"
    2. Create a structured error using the AgentProtocolError model.
    3. Return the response in JSON format.

    Args:
        _request (Request): The HTTP request object (not used).
        exc (HTTPException): The raised HTTP exception.

    Returns:
        JSONResponse: An error response in Agent Protocol format.
            {
                "error": "error_type",
                "message": "Human-readable error message",
                "details": {...}  # Optional additional info
            }

    Example:
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
    """Convert unexpected exceptions to an Agent Protocol error.

    Catches all Python exceptions other than HTTPException and transforms them
    into a 500 Internal Server Error in the Agent Protocol format.

    Workflow:
    1. Catch any unhandled exception (e.g., ValueError, TypeError).
    2. Include the exception message in the `details` for debugging support.
    3. Return a standardized error response with a 500 status code.

    Args:
        _request (Request): The HTTP request object (not used).
        exc (Exception): The raised exception.

    Returns:
        JSONResponse: An Agent Protocol error response with a 500 status code.
            {
                "error": "internal_error",
                "message": "An unexpected error occurred",
                "details": {"exception": "Exception message"}
            }

    Note:
        - Be cautious about exposing sensitive information in production environments.
        - Recommended to integrate with a logging system for detailed error tracking.
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
# Root Endpoint
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint: returns basic server information.

    Provides basic metadata to confirm that the server is running correctly.

    Returns:
        dict[str, str]: A dictionary with server information.
            - message: Application name
            - version: Current version
            - status: Server status ("running")

    Example:
        GET http://localhost:8000/
        → {"message": "Open LangGraph", "version": "0.1.0", "status": "running"}

    Note:
        - For detailed health checks, use the /health endpoint.
    """
    return {"message": "Open LangGraph", "version": "0.1.0", "status": "running"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Start development server when script is run directly
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    import os

    import uvicorn

    # Read port from environment variable (default: 8000)
    port = int(os.getenv("PORT", "8000"))

    # Run the development server
    # host="0.0.0.0": Allows connections from all network interfaces
    # nosec B104: Suppress Bandit security warning (binding to all interfaces is intentional)
    uvicorn.run(app, host="0.0.0.0", port=port)  # nosec B104 - binding to all interfaces is intentional
