"""Pydantic models for Agent Protocol assistants.

This module defines request/response models for creating, updating, and querying assistants.
An assistant is a user-managed entity that wraps a specific LangGraph graph.

Key Models:
- AssistantCreate: Request to create an assistant.
- AssistantUpdate: Request to update an assistant.
- Assistant: Assistant entity (response).
- AssistantList: Response for a list of assistants.
- AssistantSearchRequest: Request to search for assistants.
- AgentSchemas: Graph schema definitions (input/output/state/config).

Config vs. Context (LangGraph 0.6.0+):
- config: Runtime settings for LangGraph execution (e.g., model_name, temperature).
- context: Compile-time context if the graph is configurable.

Usage Example:
    # Create an assistant
    assistant = AssistantCreate(
        graph_id="weather_agent",
        config={"model": "gpt-4"},
        metadata={"team": "sales"}
    )
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AssistantCreate(BaseModel):
    """Request model for creating an assistant.

    Defines the request data for creating a new assistant.
    The minimum requirement is only `graph_id`; other fields are auto-generated.

    Key Fields:
    - assistant_id: Auto-generated UUID if omitted.
    - name: Auto-generated based on `graph_id` if omitted.
    - config: LangGraph execution settings (runtime).
    - context: LangGraph compile context.
    - if_exists: Controls behavior on duplicate creation.
    """

    # Unique assistant identifier (auto-generated UUID if omitted)
    assistant_id: str | None = Field(
        None, description="Unique assistant identifier (auto-generated if not provided)"
    )

    # Human-readable assistant name (auto-generated if omitted)
    name: str | None = Field(
        None,
        description="Human-readable assistant name (auto-generated if not provided)",
    )

    # Assistant description (optional)
    description: str | None = Field(None, description="Assistant description")

    # LangGraph execution settings (e.g., model_name, temperature)
    config: dict[str, Any] | None = Field({}, description="Assistant configuration")

    # LangGraph compile context (used if the graph is configurable)
    context: dict[str, Any] | None = Field({}, description="Assistant context")

    # Graph ID defined in open_langgraph.json (required)
    graph_id: str = Field(..., description="LangGraph graph ID from open_langgraph.json")

    # Metadata for searching and filtering
    metadata: dict[str, Any] | None = Field(
        {}, description="Metadata to use for searching and filtering assistants."
    )

    # Behavior on duplicate creation: "error" (return error) or "do_nothing" (ignore)
    if_exists: str | None = Field("error", description="What to do if assistant exists: error or do_nothing")


class Assistant(BaseModel):
    """Response model for an assistant entity.

    Represents the full information of an assistant stored in the database.
    This model is automatically converted from the ORM model (AssistantORM).

    Key Features:
    - Versioning: The `version` field is auto-incremented on updates.
    - User Scoping: Isolated per user via `user_id`.
    - Timestamps: Creation and modification times are automatically tracked.
    - Metadata: Flexible search/filtering support with a JSONB column.

    Note:
        - The `metadata` field is mapped from the ORM's `metadata_dict` column.
        - Supports automatic conversion from ORM objects with `from_attributes=True`.
    """

    # Unique assistant identifier
    assistant_id: str

    # Human-readable name
    name: str

    # Assistant description (optional)
    description: str | None = None

    # LangGraph execution settings (runtime)
    config: dict[str, Any] = Field(default_factory=dict)

    # LangGraph compile context (for configurable graphs)
    context: dict[str, Any] = Field(default_factory=dict)

    # Graph ID defined in open_langgraph.json
    graph_id: str

    # Owner's user ID (for multi-tenancy isolation)
    user_id: str

    # Assistant version (increments on each update)
    version: int = Field(..., description="The version of the assistant.")

    # Metadata for search/filtering (mapped from ORM's metadata_dict)
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_dict")

    # Creation timestamp (UTC)
    created_at: datetime

    # Last modification timestamp (UTC)
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)  # Support auto-conversion from ORM model


class AssistantUpdate(BaseModel):
    """Request model for updating an assistant.

    Defines the request data for modifying the settings of an existing assistant.
    All fields are optional; only the provided fields will be updated.

    Key Features:
    - Partial Updates: Provide only the fields to be changed.
    - Versioning: `version` is auto-incremented on successful update.
    - config/context: Allows modification of runtime settings or compile context.

    Note:
        - A new version of the assistant is created upon update.
        - `assistant_id` cannot be changed (immutable identifier).
    """

    # Assistant name (keeps existing value if omitted)
    name: str | None = Field(None, description="The name of the assistant (auto-generated if not provided)")

    # Assistant description (keeps existing value if omitted)
    description: str | None = Field(None, description="The description of the assistant. Defaults to null.")

    # Update LangGraph execution settings
    config: dict[str, Any] | None = Field({}, description="Configuration to use for the graph.")

    # Change the graph ID to be used (default: "agent")
    graph_id: str = Field("agent", description="The ID of the graph")

    # Update LangGraph compile context (for configurable graphs)
    context: dict[str, Any] | None = Field(
        {},
        description="The context to use for the graph. Useful when graph is configurable.",
    )

    # Update metadata for search/filtering
    metadata: dict[str, Any] | None = Field(
        {}, description="Metadata to use for searching and filtering assistants."
    )


class AssistantList(BaseModel):
    """Response model for a list of assistants.

    This is the paginated response returned when querying for multiple assistants.

    Key Fields:
    - assistants: List of assistants on the current page.
    - total: Total number of assistants (for pagination calculation).

    Usage Example:
        # Paginate by 20
        GET /assistants?limit=20&offset=0
        -> AssistantList(assistants=[...], total=150)
    """

    # List of assistants on the current page
    assistants: list[Assistant]

    # Total number of assistants matching the search criteria
    total: int


class AssistantSearchRequest(BaseModel):
    """Request model for searching for assistants.

    어시스턴트를 검색하고 필터링하기 위한 쿼리 파라미터를 정의합니다.
    모든 필터는 선택사항이며, 여러 필터를 조합하여 사용할 수 있습니다.

    Key Features:
    - Text Search: Partial match search on `name` and `description` fields.
    - Graph Filtering: Query only assistants using a specific `graph_id`.
    - Metadata Filtering: Flexible search with JSONB queries.
    - Pagination: Control the result range with `limit`/`offset`.

    Validation Rules:
    - limit: 1-100 range (default: 20).
    - offset: 0 or greater (default: 0).

    Usage Example:
        # Search for weather_agent for the sales team
        SearchRequest(
            graph_id="weather_agent",
            metadata={"team": "sales"},
            limit=10
        )
    """

    # Filter by assistant name (partial match)
    name: str | None = Field(None, description="Filter by assistant name")

    # Filter by assistant description (partial match)
    description: str | None = Field(None, description="Filter by assistant description")

    # Filter by graph ID (exact match)
    graph_id: str | None = Field(None, description="Filter by graph ID")

    # Page size (1-100, default: 20)
    limit: int | None = Field(20, le=100, ge=1, description="Maximum results")

    # Start offset (0 or greater, default: 0)
    offset: int | None = Field(0, ge=0, description="Results offset")

    # Filter by metadata (JSONB query)
    metadata: dict[str, Any] | None = Field(
        {}, description="Metadata to use for searching and filtering assistants."
    )


class AgentSchemas(BaseModel):
    """Model for graph schema definitions (for client integration).

    Provides the input, output, state, and config schemas of a LangGraph graph in JSON Schema format.
    Clients can use this schema to dynamically generate UIs or validate data.

    Key Schema Types (4 types):
    1. input_schema: Format of input data required for graph execution.
       e.g., {"messages": [{"role": "user", "content": "..."}]}

    2. output_schema: Format of data returned as the result of graph execution.
       e.g., {"messages": [...], "status": "completed"}

    3. state_schema: The entire structure of the graph's internal state.
       e.g., TypedDict definition of a StateGraph.

    4. config_schema: Parameters for graph execution settings.
       e.g., {"model_name": "gpt-4", "temperature": 0.7}

    JSON Schema Format:
        Each schema follows the standard JSON Schema (Draft 7) format.
        {
            "type": "object",
            "properties": {...},
            "required": [...],
            "additionalProperties": false
        }

    Usage Example:
        # Get graph schemas
        GET /assistants/{assistant_id}/schemas
        -> AgentSchemas(
            input_schema={...},
            output_schema={...},
            state_schema={...},
            config_schema={...}
        )

    Note:
        - Schemas are automatically extracted from the graph definition.
        - Clients should validate request data against these schemas.
    """

    # JSON Schema for graph input data
    input_schema: dict[str, Any] = Field(..., description="JSON Schema for agent inputs")

    # JSON Schema for graph output data
    output_schema: dict[str, Any] = Field(..., description="JSON Schema for agent outputs")

    # JSON Schema for graph state (entire StateGraph structure)
    state_schema: dict[str, Any] = Field(..., description="JSON Schema for agent state")

    # JSON Schema for graph execution settings (config parameters)
    config_schema: dict[str, Any] = Field(..., description="JSON Schema for agent config")
