"""Reasoning-Action Agent Graph Definition using the ReAct Pattern

This module implements a ReAct (Reasoning and Action) agent based on LangGraph.
The ReAct pattern involves the LLM iteratively reasoning and executing tools to solve a problem.

ReAct Pattern Flow:
1. User question is input.
2. The LLM reasons and selects a necessary tool.
3. The selected tool is executed.
4. The tool execution result is passed to the LLM.
5. Steps 2-4 are repeated to derive the final answer.

Main Components:
• call_model - LLM call node (reasoning and tool selection)
• tools - Tool execution node (ToolNode)
• route_model_output - Conditional routing function (continue execution or end)
• graph - Compiled StateGraph instance

Graph Structure:
    __start__ → call_model ⇄ tools
                     ↓
                 __end__

Requirements:
- A chat model that supports tool calling.
- Injection of model settings and system prompt via Runtime[Context].
"""

from datetime import UTC, datetime
from typing import Literal, cast

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime

from react_agent.context import Context
from react_agent.state import InputState, State
from react_agent.tools import TOOLS
from react_agent.utils import load_chat_model

# ---------------------------------------------------------------------------
# Node Function: LLM Call and Reasoning
# ---------------------------------------------------------------------------


async def call_model(
    state: State, runtime: Runtime[Context]
) -> dict[str, list[AIMessage]]:
    """Core LLM call node for the ReAct agent - performs reasoning and tool selection.

    This function is responsible for the "Reasoning" step in the ReAct pattern.
    It calls the LLM based on the current conversation state to decide the next action (tool call or final answer).

    Flow:
    1. Extract model information from the Runtime Context and bind tools.
    2. Format the system prompt (injecting the current time).
    3. Call the LLM (with system message + conversation history).
    4. Process the response (handling termination if max steps are reached).
    5. Return a new message to add to the state.

    Args:
        state (State): The current conversation state (includes message history, step counter, etc.).
        runtime (Runtime[Context]): The runtime context (includes model settings, system prompt).

    Returns:
        dict[str, list[AIMessage]]: A dictionary for updating the state.
            - "messages": The LLM's response message (may include tool call information).

    Note:
        - If the LLM decides to call a tool, response.tool_calls will contain tool information.
        - If the max steps are reached and it still tries to call a tool, an error message is returned.
        - bind_tools() makes the LLM aware of the available tools.
    """
    # Get model settings from the runtime context and bind them with tools.
    # This tells the model which tools it can use (injects tool schema).
    model = load_chat_model(runtime.context.model).bind_tools(TOOLS)

    # Format the system prompt - inject the current time to make the agent time-aware.
    # The system prompt defines the agent's role and behavior.
    system_message = runtime.context.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )

    # Call the LLM - pass the system message and conversation history as input.
    # The LLM analyzes the context and decides the next action (tool call or answer).
    response = cast(
        "AIMessage",
        await model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
    )

    # Check for max steps: a safety measure to prevent infinite loops.
    # If the LLM still tries to call a tool on the last step, force termination.
    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }

    # Add the LLM response to the state and return it.
    # The next node (route_model_output) will make a routing decision based on this message.
    return {"messages": [response]}


# ---------------------------------------------------------------------------
# Graph Configuration: Initialize StateGraph Builder and Add Nodes
# ---------------------------------------------------------------------------

# Create the ReAct agent graph builder.
# - State: The schema of the state maintained during graph execution (messages, steps, etc.).
# - InputState: The schema for user input (contains only the initial message).
# - Context: The schema for the runtime context (model settings, system prompt, etc.).
builder = StateGraph(State, input_schema=InputState, context_schema=Context)

# Node 1: call_model - The LLM call and reasoning node.
# The LLM analyzes the conversation context and decides the next action (tool call or answer).
builder.add_node(call_model)

# Node 2: tools - The tool execution node (using LangGraph's ToolNode).
# Actually executes the tool selected by the LLM and adds the result to the state.
# ToolNode automatically parses tool_calls and calls the corresponding tool.
builder.add_node("tools", ToolNode(TOOLS))

# ---------------------------------------------------------------------------
# Edge Definition: Configure the Graph's Execution Flow
# ---------------------------------------------------------------------------

# Set the entry point: The graph starts execution from the call_model node.
# __start__ is a special node in LangGraph that signifies the graph's starting point.
builder.add_edge("__start__", "call_model")


def route_model_output(state: State) -> Literal["__end__", "tools"]:
    """Determines the next node based on the LLM output - conditional routing for the ReAct pattern.

    This function is responsible for the core branching logic of the ReAct pattern.
    It checks the LLM's last response to determine if a tool call is needed (Action) or if it's a final answer (End).

    Routing Logic:
    - Tool call present → Go to the "tools" node (execute tool).
    - No tool call → Go to the "__end__" node (end graph).

    Args:
        state (State): The current conversation state (includes message history).

    Returns:
        Literal["__end__", "tools"]: The name of the next node to execute.
            - "__end__": End the graph (final answer is complete).
            - "tools": Go to the tool execution node.

    Raises:
        ValueError: If the last message is not an AIMessage
            (in the graph structure, the node after call_model must always be an AIMessage).

    Note:
        - Implements the "Thought → Action → Observation" cycle of the ReAct pattern.
        - If a tool is called, it's executed in the tools node, and then it returns to call_model.
        - If there's no tool call, it's assumed the LLM has completed the final answer, so it ends.
    """
    # Extract the most recent message (LLM response) from the state.
    last_message = state.messages[-1]

    # Type safety check: The node after call_model must always be an AIMessage.
    if not isinstance(last_message, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
        )

    # If there are no tool calls, end the graph.
    # This means the LLM has returned only text as the final answer (no more tools needed).
    if not last_message.tool_calls:
        return "__end__"

    # If there are tool calls, go to the tools node to execute them.
    # Enter the "Action" step of the ReAct pattern.
    return "tools"


# call_model → (conditional branch) → __end__ or tools
# After the call_model node executes, the route_model_output function dynamically determines the next node.
# The core of the ReAct pattern: choose to execute a tool or end based on the LLM's response.
builder.add_conditional_edges(
    "call_model",
    # After call_model completes, execute route_model_output to determine the next node.
    # Branches to the "__end__" or "tools" node based on the return value.
    route_model_output,
)

# tools → call_model (fixed edge)
# After tool execution is complete, always return to call_model to analyze the results.
# Implements the ReAct cycle: Action (tool execution) → Observation (result) → Thought (LLM reasoning again).
builder.add_edge("tools", "call_model")

# ---------------------------------------------------------------------------
# Graph Compilation: Convert to an Executable Graph
# ---------------------------------------------------------------------------

# Compile the StateGraph builder into an executable CompiledGraph.
# name="ReAct Agent" is used as an identifier in LangSmith tracing, etc.
# After compilation, the graph is referenced in open_langgraph.json to be exposed via an HTTP API.
graph = builder.compile(name="ReAct Agent")
