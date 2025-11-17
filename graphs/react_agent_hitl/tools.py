"""Example tools module for the Human-in-the-Loop ReAct agent.

This module contains a basic tool that provides web search functionality.
It consists of a simple example that uses the Tavily search engine.

Main Components:
• search - A web search tool (based on Tavily).
• TOOLS - A list of tools for the agent to use.

Usage Example:
    from react_agent_hitl.tools import TOOLS

    # Bind tools to the graph
    model_with_tools = model.bind_tools(TOOLS)

Note:
    These tools are free examples to get you started.
    For a production environment, it is recommended to implement more robust and specialized tools.
"""

from collections.abc import Callable
from typing import Any

from langgraph.runtime import get_runtime

from react_agent_hitl.context import Context


async def search(query: str) -> dict[str, Any] | None:
    """A tool function that performs a general web search.

    This function performs a web search using the Tavily search engine.
    Tavily is designed to provide comprehensive, accurate, and reliable search results,
    and is particularly useful for questions about recent or current events.

    Flow:
    1. Get search settings from the Runtime context.
    2. Check the maximum number of search results.
    3. Return simulated search results (example).

    Args:
        query (str): The query string to search for.

    Returns:
        dict[str, Any] | None: A dictionary of search results.
            - query: The original search query.
            - max_search_results: The maximum number of search results.
            - results: The search results (currently simulated).

    Note:
        - In a real production environment, this should be implemented to call the Tavily API.
        - Accesses user-specific search settings via Runtime[Context].
    """
    runtime = get_runtime(Context)
    return {
        "query": query,
        "max_search_results": runtime.context.max_search_results,
        "results": f"Simulated search results for '{query}'",
    }


# A list of tools for the agent to use.
# Used in the LangGraph graph by binding with model.bind_tools(TOOLS).
TOOLS: list[Callable[..., Any]] = [search]
