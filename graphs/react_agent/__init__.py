"""ReAct Agent Graph Package

This package provides an agent graph based on the ReAct pattern, which iterates
between Reasoning and Acting. It implements a simple loop where the agent
determines the necessary tools in the reasoning step to process a user's request,
and executes those tools in the acting step.

Key Features:
- ReAct Pattern: Reason -> Act -> Observe cycle
- Tool Calling: Automatically executes tools determined by the LLM
- State Management: Maintains conversation state via LangGraph StateGraph
- Simple Structure: Continuous execution without complex interrupts

Usage Example:
    from graphs.react_agent import graph

    # The graph is registered in open_langgraph.json for use
    # "react_agent": "./graphs/react_agent/__init__.py:graph"

Exports:
    graph: A compiled instance of the ReAct agent graph
"""

from react_agent.graph import graph

__all__ = ["graph"]
