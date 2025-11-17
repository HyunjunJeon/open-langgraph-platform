"""ReAct agent graph with Human-in-the-Loop support.

This module defines a ReAct agent that requires human approval before executing tools.
It follows the same reason-act pattern as the basic react_agent, but requests
human intervention via an interrupt before executing a tool.

Key differences (compared to react_agent):
- Added human_approval node: An approval step before tool execution.
- Interrupt mechanism: Halts execution using LangGraph's interrupt() function.
- User response handling:
  - "yes": Proceeds with tool execution.
  - "no": Skips tool execution and returns to the reasoning step.
  - Other responses: The agent asks for clarification.

This pattern is useful for tasks requiring safety, such as financial transactions
or operations on sensitive data.
"""

from react_agent_hitl.graph import graph

__all__ = ["graph"]
