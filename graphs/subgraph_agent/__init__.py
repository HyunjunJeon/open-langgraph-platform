"""Subgraph Agent

This module provides a minimal delegation graph that demonstrates the subgraph
composition pattern, where another graph is included as a node.

Subgraph Composition Pattern:
• Reuse an existing graph (react_agent) as a node in a new graph.
• Build complex workflows through graph nesting.
• Implement a modular agent structure with a delegation pattern.

Key Components:
• subgraph_agent node - Executes the react_agent graph as a subgraph.
• no_stream node - Calls an LLM with a streaming-disabled tag.

Usage Example:
    from subgraph_agent import graph

    # Execute the composite graph that includes the subgraph
    result = await graph.ainvoke({"messages": [...]})
"""

from subgraph_agent.graph import graph

__all__ = ["graph"]
