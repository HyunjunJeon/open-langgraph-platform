"""State structure definition for the Human-in-the-Loop agent.

This module defines the state channels and data structures for the ReAct agent
that supports HITL (Human-in-the-Loop) functionality. It leverages LangGraph's
state management system to track conversation history, tool calls, and interrupt points.

Main Components:
• InputState - Defines the input state for the interface with the outside world.
• State - The complete state used throughout the graph's execution.

State Channels:
- messages: The conversation message history (using the add_messages reducer).
- is_last_step: Indicates whether the recursion limit has been reached (a LangGraph managed variable).

Usage Example:
    from react_agent_hitl.state import State, InputState

    # Specify the state schema when defining the graph
    builder = StateGraph(State, input_schema=InputState)
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
    """The agent's input state, defining the interface with the outside world.

    This class defines the structure of the input data that the graph receives from external sources.
    LangGraph uses this class as the input_schema to require only the minimal data
    that the client needs to provide, while hiding the internal state.

    Role in the HITL context:
    - The client only needs to provide messages (is_last_step, etc., are managed automatically).
    - The same structure is used when resuming from an interrupt.
    - Acts as the "public API" of the state.
    """

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(
        default_factory=list
    )
    """The list of messages that tracks the agent's main execution state.

    The typical message accumulation pattern in a HITL agent:
    1. HumanMessage - User input.
    2. AIMessage (with tool_calls) - The tools the agent has chosen to gather information.
    3. ToolMessage(s) - The response or error from the executed tools.
    4. AIMessage (without tool_calls) - The agent's final response to the user.
    5. HumanMessage - The user's next turn in the conversation.

    Steps 2-5 are repeated as needed.

    Interrupt Handling:
    - When interrupt() is called in the human_approval node, the current message state is preserved.
    - If the user modifies a tool execution, it is replaced with an updated AIMessage.
    - If the user chooses to respond, a new HumanMessage is added.

    Reducer Behavior:
    The `add_messages` annotation merges new messages with existing ones,
    and if a message with the same ID is provided, it updates the existing message.
    This allows for message modification while maintaining an "append-only" state.
    """


@dataclass
class State(InputState):
    """A class representing the complete internal state of the agent.

    This class extends InputState to include additional attributes that are
    only needed during graph execution. It is used internally by LangGraph
    and is not exposed to the client.

    Inheritance Relationship:
    - Includes all fields from InputState (messages).
    - Adds managed variables for internal graph control (is_last_step).

    Role in the HITL agent:
    - Node functions read and modify this state.
    - The entire state is saved to a checkpoint when an interrupt occurs.
    - Prevents infinite loops by detecting the recursion limit.

    Usage Pattern:
    Each node in the graph receives State as input and returns a state update:
        async def call_model(state: State) -> dict:
            # Read state.messages
            # Check state.is_last_step
            return {"messages": [new_message]}
    """

    is_last_step: IsLastStep = field(default=False)
    """A flag indicating if the current step is the one right before the recursion limit is reached.

    This variable is a 'managed variable' controlled by the LangGraph state machine,
    not by user code.

    How it works:
    - It is set to True when the graph execution step reaches (recursion_limit - 1).
    - The call_model node checks this value to perform appropriate termination handling.
    - It's a safety measure to prevent infinite loops.

    Use in the HITL context:
    - Detects when the model still wants to call a tool at the maximum step.
    - Returns a "Could not find an answer within the step limit" message to the user.
    - It is not included in the step count while waiting for an interrupt.

    Type:
    IsLastStep is a special type in LangGraph that behaves like a bool but
    internally tracks the managed state.

    Note:
        The recursion_limit is set when compiling the graph or specified in the execution config:
        graph = builder.compile(checkpointer=checkpointer)
        config = {"recursion_limit": 10}
    """
