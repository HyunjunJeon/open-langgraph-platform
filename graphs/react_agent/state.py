"""Defines the state structure for the ReAct agent.

This module defines the State structure used in the LangGraph graph.
It uses TypedDict to clearly define state channels and reducers,
and tracks all necessary information during agent execution.

Main components:
• InputState - The input state representing the interface with the outside world.
• State - The complete state used throughout the agent's entire lifecycle.

State Channels:
• messages - The conversation message history (managed by the add_messages reducer).
• is_last_step - A managed variable indicating whether the recursion limit has been reached.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from langgraph.managed import IsLastStep


@dataclass
class InputState:
    """Defines the agent's input state, representing a narrow interface with the outside world.

    This class defines the initial state and structure of data coming from external sources.
    It is used as the input channel for the LangGraph graph and contains only the
    minimal information provided by the client.

    Key features:
    - Structures input data received from external API requests.
    - Serves as the parent class for the State class.
    - Provides input validation and type safety.

    Usage Example:
        input_state = InputState(messages=[HumanMessage(content="Hello")])
    """

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(
        default_factory=list
    )
    """
    The message history that tracks the agent's main execution state.

    It typically accumulates in the following pattern:
    1. HumanMessage - User input.
    2. AIMessage with .tool_calls - The tools the agent has chosen to gather information.
    3. ToolMessage(s) - The response or error from the executed tools.
    4. AIMessage without .tool_calls - The agent responds to the user in an unstructured format.
    5. HumanMessage - The user responds for the next turn of the conversation.

    Steps 2-5 are repeated as needed.

    `add_messages` reducer behavior:
    - Merges new messages with existing ones.
    - Updates based on ID to maintain an "append-only" state.
    - If a message with the same ID is provided, it updates the existing message.
    - This supports message modification and retry patterns.
    """


@dataclass
class State(InputState):
    """Represents the complete state of the agent, extending InputState with additional attributes.

    This class stores all the information needed throughout the agent's entire lifecycle.
    It inherits from InputState to include not only input data but also internal state
    information generated during execution.

    Key features:
    - Includes all channels from InputState (e.g., messages).
    - Adds managed variables for execution control (is_last_step).
    - The complete state that LangGraph persists as a checkpoint.

    Usage pattern:
    - Node functions receive State as input and return partial updates.
    - LangGraph uses reducers to merge the partial updates.
    - The full state is saved to a checkpoint at each step.

    Usage Example:
        def my_node(state: State) -> dict:
            # Read messages from the state
            messages = state.messages
            # Return a partial update (the reducer will merge it)
            return {"messages": [AIMessage(content="Response")]}
    """

    is_last_step: IsLastStep = field(default=False)
    """
    Indicates whether the current step is the last before the graph would raise an error.

    Managed variable features:
    - Controlled by the LangGraph state machine, not user code.
    - Set to True when the step count reaches recursion_limit - 1.
    - Used to prevent infinite loops and handle recursion limits.

    How it works:
    1. LangGraph increments a counter at each step.
    2. When recursion_limit - 1 is reached, is_last_step = True.
    3. Nodes can check this value to decide whether to terminate.
    4. If the next step reaches the recursion_limit, a RecursionError is raised.

    Usage Example:
        def my_node(state: State) -> dict:
            if state.is_last_step:
                # Force termination because it's the last step
                return {"messages": [AIMessage(content="Limit reached")]}
            # Continue normal processing
    """
