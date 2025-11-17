"""Example tool collection for the ReAct agent.

This module defines basic tools that provide web search and scraping functionality.
Used with LangGraph's tool calling pattern, it allows the agent to
access external information and perform tasks.

Main tools:
• search - Web search via the Tavily search engine (simulated).

Note:
    These tools are provided as examples to get started.
    For production environments, it is recommended to implement more robust
    and specialized tools that fit your requirements.

Usage Example:
    from react_agent.tools import TOOLS

    # Bind tools to a LangGraph graph
    model = ChatOpenAI(model="gpt-4").bind_tools(TOOLS)
"""

from collections.abc import Callable
from typing import Any

from langgraph.runtime import get_runtime

from react_agent.context import Context


async def search(query: str) -> dict[str, Any] | None:
    """Performs a web search and returns the search results.

    This function simulates a web search using the Tavily search engine.
    Tavily is designed to provide comprehensive, accurate, and reliable search results,
    and is particularly useful for questions about recent events or current information.

    Flow:
    1. Extract Context from the LangGraph Runtime.
    2. Get the max_search_results setting from the Context.
    3. Return a results dictionary including the search query and settings.

    Args:
        query (str): The query or keywords to search for.

    Returns:
        dict[str, Any] | None: A dictionary of search results.
            - query (str): The input search query.
            - max_search_results (int): The maximum number of search results setting.
            - results (str): A string of simulated search results.

    Note:
        - Currently, this is in simulation mode and does not perform an actual search.
        - To use the actual Tavily API, you need to set up an API key and integrate the client.
        - Accesses user-specific settings via the Runtime[Context] pattern.

    Usage Example:
        results = await search("Latest features of LangGraph")
        print(results["results"])
    """
    # Get the user context from the LangGraph Runtime
    runtime = get_runtime(Context)

    # Create a search results dictionary (simulation)
    return {
        "query": query,
        "max_search_results": runtime.context.max_search_results,
        "results": f"Simulated search results for '{query}'",
    }


# ---------------------------------------------------------------------------
# Tool List (for LangGraph Tool Binding)
# ---------------------------------------------------------------------------

# A list of all tool functions available to the agent.
# This is bound to the LLM in LangGraph with model.bind_tools(TOOLS).
TOOLS: list[Callable[..., Any]] = [search]
