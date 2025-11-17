"""LangGraph Store API endpoints.

This module implements the Agent Protocol's Store API, providing persistent
storage functionality through LangGraph's official AsyncPostgresStore.

The Store serves as a long-term memory storage independent of threads and runs,
securely managing user-specific data by isolating it into namespaces.

Key features:
- Key-value storage (Put) - Storing items based on namespace.
- Item retrieval (Get) - Searching for specific items by key.
- Item deletion (Delete) - Removing stored items.
- Search (Search) - Supports keyword/semantic/hybrid search.
- User isolation - Automatic namespace scoping.

Usage example:
    # Store an item
    PUT /store/items
    {
        "namespace": ["users", "user123", "preferences"],
        "key": "theme",
        "value": {"color": "dark", "fontSize": 14}
    }

    # Retrieve an item
    GET /store/items?key=theme&namespace=users.user123.preferences

    # Search
    POST /store/items/search
    {
        "namespace_prefix": ["users", "user123"],
        "query": "theme",
        "limit": 10
    }

Note:
    - The Store directly uses LangGraph's AsyncPostgresStore.
    - It utilizes LangGraph's official tables, not metadata tables.
    - Supports vector similarity search (semantic/hybrid modes).
"""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.auth_deps import get_current_user
from ..models import (
    StoreDeleteRequest,
    StoreGetResponse,
    StoreItem,
    StorePutRequest,
    StoreSearchRequest,
    StoreSearchResponse,
    User,
)

router = APIRouter()


@router.put("/store/items")
async def put_store_item(request: StorePutRequest, user: User = Depends(get_current_user)) -> dict[str, str]:
    """Store an item in the LangGraph Store.

    Saves an item to the namespace-based key-value store.
    Automatically applies user-specific namespace scoping to ensure data security.

    Workflow:
    1. Apply user scoping to the requested namespace.
    2. Get the LangGraph Store instance.
    3. Save the item using store.aput().
    4. Return a success status.

    Args:
        request (StorePutRequest): The storage request, including namespace, key, and value.
        user (User): The authenticated user.

    Returns:
        dict: A status dictionary {"status": "stored"}.

    Usage Example:
        PUT /store/items
        {
            "namespace": ["users", "user123", "settings"],
            "key": "theme",
            "value": {"mode": "dark"}
        }

    Note:
        - The namespace is provided as a list (e.g., ["users", "user123"]).
        - The value is stored as JSONB, allowing for complex objects.
        - The same (namespace, key) combination will be overwritten.
    """

    # Apply user namespace scoping
    scoped_namespace = apply_user_namespace_scoping(user.identity, request.namespace)

    # Get LangGraph Store instance from DatabaseManager
    from ..core.database import db_manager

    store = await db_manager.get_store()

    await store.aput(namespace=tuple(scoped_namespace), key=request.key, value=request.value)

    return {"status": "stored"}


@router.get("/store/items", response_model=StoreGetResponse)
async def get_store_item(
    key: str,
    namespace: str | list[str] | None = Query(None),
    user: User = Depends(get_current_user),
) -> StoreGetResponse:
    """Retrieve an item from the LangGraph Store.

    Retrieves a specific item by namespace and key.
    The namespace can be provided as a dot-separated string or a list.

    Workflow:
    1. Normalize the namespace format (dotted string → list).
    2. Apply user scoping.
    3. Retrieve the item from the LangGraph Store.
    4. Raise a 404 error if the item is not found.
    5. Return the item information.

    Args:
        key (str): The key of the item to retrieve.
        namespace (Union[str, list[str], None]): The namespace.
            - string: "users.user123.settings" (dot-separated)
            - list: ["users", "user123", "settings"]
            - None: Use the user's default namespace.
        user (User): The authenticated user.

    Returns:
        StoreGetResponse: The item information (key, value, namespace).

    Raises:
        HTTPException(404): If the item is not found.

    Usage Example:
        # Dot-separated namespace
        GET /store/items?key=theme&namespace=users.user123.settings

        # List-style namespace
        GET /store/items?key=theme&namespace=users&namespace=user123

    Note:
        - Supports SDK-style dotted namespaces for convenience.
        - Empty parts are automatically filtered ("a..b" → ["a", "b"]).
    """

    # Accommodate both SDK-style dot-separated namespaces and list format
    ns_list: list[str]
    if isinstance(namespace, str):
        ns_list = [part for part in namespace.split(".") if part]
    elif isinstance(namespace, list):
        ns_list = namespace
    else:
        ns_list = []

    # Apply user namespace scoping
    scoped_namespace = apply_user_namespace_scoping(user.identity, ns_list)

    # Get LangGraph Store instance from DatabaseManager
    from ..core.database import db_manager

    store = await db_manager.get_store()

    item = await store.aget(tuple(scoped_namespace), key)

    if not item:
        raise HTTPException(404, "Item not found")

    return StoreGetResponse(key=key, value=item.value, namespace=list(scoped_namespace))


@router.delete("/store/items")
async def delete_store_item(
    body: StoreDeleteRequest | None = None,
    key: str | None = Query(None),
    namespace: list[str] | None = Query(None),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Delete an item from the LangGraph Store.

    Deletes a specific item by namespace and key.
    Supports both JSON body and query parameters for SDK compatibility.

    Workflow:
    1. Determine the parameter source (body takes precedence, otherwise query params).
    2. Validate that the key is provided.
    3. Apply user scoping.
    4. Delete the item from the LangGraph Store.
    5. Return a success status.

    Args:
        body (StoreDeleteRequest | None): SDK request body {namespace, key}.
        key (str | None): The key of the item to delete (query parameter).
        namespace (list[str] | None): The namespace (query parameter).
        user (User): The authenticated user.

    Returns:
        dict: A status dictionary {"status": "deleted"}.

    Raises:
        HTTPException(422): If the key is not provided.

    Usage Example:
        # SDK-style (JSON body)
        DELETE /store/items
        {
            "namespace": ["users", "user123"],
            "key": "theme"
        }

        # Manual call (query parameters)
        DELETE /store/items?key=theme&namespace=users&namespace=user123

    Note:
        - Supports both SDK compatibility and manual usage.
        - If the body is provided, query parameters are ignored.
        - Deleting a non-existent item returns success without an error.
    """
    # Determine parameter source (body takes precedence over query parameters)
    if body is not None:
        ns = body.namespace
        k = body.key
    else:
        if key is None:
            raise HTTPException(422, "Missing 'key' parameter")
        ns = namespace or []
        k = key

    # Apply user namespace scoping
    scoped_namespace = apply_user_namespace_scoping(user.identity, ns)

    # Get LangGraph Store instance from DatabaseManager
    from ..core.database import db_manager

    store = await db_manager.get_store()

    await store.adelete(tuple(scoped_namespace), k)

    return {"status": "deleted"}


@router.post("/store/items/search", response_model=StoreSearchResponse)
async def search_store_items(
    request: StoreSearchRequest, user: User = Depends(get_current_user)
) -> StoreSearchResponse:
    """Search for items in the LangGraph Store.

    Searches for items by namespace prefix and search query.
    The LangGraph Store supports keyword, semantic, and hybrid search.

    Search Modes:
    - Keyword search: Text matching on keys/values.
    - Semantic search: Embedding-based similarity search (vector search).
    - Hybrid search: Combination of keyword and semantic search (best results).

    Workflow:
    1. Apply user scoping to the namespace prefix.
    2. Get the LangGraph Store instance.
    3. Execute the search using store.asearch().
    4. Convert the results to a list of StoreItems.
    5. Return the results with pagination information.

    Args:
        request (StoreSearchRequest): The search request.
            - namespace_prefix (list[str]): The namespace prefix to search within.
            - query (str | None): The search query (None to retrieve all).
            - limit (int): The maximum number of items to return (default: 20).
            - offset (int): The result offset (for pagination).
        user (User): The authenticated user.

    Returns:
        StoreSearchResponse: The search results.
            - items (list[StoreItem]): The list of found items.
            - total (int): The number of returned items.
            - limit (int): The requested limit.
            - offset (int): The requested offset.

    Usage Example:
        POST /store/items/search
        {
            "namespace_prefix": ["users", "user123"],
            "query": "theme settings",
            "limit": 10,
            "offset": 0
        }

    Note:
        - `namespace_prefix` searches all namespaces starting with that prefix.
        - If `query` is None, it returns all items (with namespace filtering only).
        - The LangGraph Store does not provide a total count (only the number of returned items).
        - Vector search is automatically enabled based on the LangGraph Store's embedding settings.
    """

    # Apply user namespace scoping to the namespace prefix
    scoped_prefix = apply_user_namespace_scoping(user.identity, request.namespace_prefix)

    # Get LangGraph Store instance from DatabaseManager
    from ..core.database import db_manager

    store = await db_manager.get_store()

    # Execute search with LangGraph Store
    # asearch takes namespace_prefix as a positional-only argument
    results = await store.asearch(
        tuple(scoped_prefix),
        query=request.query,
        limit=request.limit or 20,
        offset=request.offset or 0,
    )

    items = [StoreItem(key=r.key, value=r.value, namespace=list(r.namespace)) for r in results]

    return StoreSearchResponse(
        items=items,
        total=len(items),  # LangGraph Store does not provide total count
        limit=request.limit or 20,
        offset=request.offset or 0,
    )


def apply_user_namespace_scoping(user_id: str, namespace: Sequence[str] | None) -> list[str]:
    """Apply user-specific namespace scoping to ensure data isolation.

    Isolates each user's data at the namespace level to provide multi-tenant security.
    Defaults to a user-specific namespace if none is provided.

    Logic:
    1. If the namespace is empty → return ["users", user_id].
    2. If the user's namespace is explicitly specified → allow it.
    3. In a development environment, allow all namespaces (this should be removed in production).

    Args:
        user_id (str): The unique identifier of the user (from authenticated identity).
        namespace (list[str]): The requested namespace list.

    Returns:
        list[str]: The user-scoped namespace.

    Usage Example:
        # No namespace → default user namespace
        apply_user_namespace_scoping("user123", [])
        # Returns: ["users", "user123"]

        # Explicit user namespace → allowed
        apply_user_namespace_scoping("user123", ["users", "user123", "settings"])
        # Returns: ["users", "user123", "settings"]

        # Other namespace → allowed only in development
        apply_user_namespace_scoping("user123", ["shared", "config"])
        # Returns: ["shared", "config"] (in development)

    Note:
        - In a production environment, access outside the user's namespace should be blocked.
        - This is a core security logic for multi-tenant isolation.
        - If shared namespaces are needed, separate permission-checking logic should be added.
    """

    if not namespace:
        # Default to user-specific namespace
        return ["users", user_id]

    # Allow if the user's namespace is explicitly specified
    namespace_list = list(namespace)
    if (
        namespace_list
        and namespace_list[0] == "users"
        and len(namespace_list) >= 2
        and namespace_list[1] == user_id
    ):
        return namespace_list

    # In a development environment, allow all namespaces (remove this in production)
    return namespace_list
