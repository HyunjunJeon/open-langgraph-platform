"""Custom ReAct agent with Human-in-the-Loop functionality.

This module implements a ReAct (Reasoning and Action) agent that requires human approval before executing tools.
It uses LangGraph's interrupt() feature to pause execution at the point of a tool call,
allowing a user to choose one of: approve, reject, modify, or respond.

Main Components:
• call_model - Calls the LLM to decide the next action.
• human_approval - Requests user approval before tool execution (the interrupt point).
• tools - Executes the approved tools.
• route_model_output - Determines the next node based on the model's output.

Interrupt and Resume Mechanism:
1. When the model requests a tool call, it is routed to the human_approval node.
2. interrupt() pauses execution and sends an approval request to the client.
3. The client chooses one of the following:
   - accept: Execute the tool as is.
   - edit: Execute the tool after modifying its arguments.
   - response: Cancel the tool execution and pass on a user message.
   - ignore: Cancel the tool execution and end.
4. Execution resumes with the user's response (using the POST /threads/{thread_id}/runs/{run_id} endpoint).

Works with chat models that have tool-calling support.
"""

import json
from datetime import UTC, datetime
from typing import Literal, cast

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from react_agent_hitl.context import Context
from react_agent_hitl.state import InputState, State
from react_agent_hitl.tools import TOOLS
from react_agent_hitl.utils import load_chat_model

# ---------------------------------------------------------------------------
# Model Calling Function
# ---------------------------------------------------------------------------


async def call_model(
    state: State, runtime: Runtime[Context]
) -> dict[str, list[AIMessage]]:
    """Calls the LLM that drives the agent to decide the next action.

    This function calls the language model based on the conversation state and processes the response.
    The model has tool binding applied, so it can request tool calls if needed.

    Flow:
    1. Initialize the model with settings from the Runtime context.
    2. Bind the list of tools to the model.
    3. Format the system prompt with the current time.
    4. Call the model and receive the response.
    5. Return an appropriate error message if the maximum number of steps is reached.

    Args:
        state (State): The current conversation state (including message history).
        runtime (Runtime[Context]): Includes user context and model settings.

    Returns:
        dict[str, list[AIMessage]]: A dictionary containing the model's response message,
                                     formatted to be added to the existing message list.

    Note:
        - To change the model or tools, modify the TOOLS list.
        - To change the agent's behavior, customize the system_prompt.
    """
    # Initialize the model with tool binding.
    # To use a different model or add tools, modify this section.
    model = load_chat_model(runtime.context.model).bind_tools(TOOLS)

    # Format the system prompt.
    # To change the agent's behavior, customize this part.
    system_message = runtime.context.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )

    # Get the model's response.
    response = cast(
        "AIMessage",
        await model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
    )

    # Handle the case where the max steps are reached, but the model still wants to use a tool.
    # This returns an error message to prevent infinite loops.
    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }

    # Return the model's response as a list to be added to the existing messages.
    return {"messages": [response]}


def _find_tool_message(messages: list) -> AIMessage | None:
    """Finds the most recent AI message that contains a tool call.

    It searches the message list in reverse to find the first AIMessage
    that has tool_calls. This is used to find the original tool call at the time of interruption.

    Args:
        messages (list): The list of messages (AIMessage, HumanMessage, ToolMessage, etc.).

    Returns:
        AIMessage | None: The AI message with a tool call, or None if not found.
    """
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            return msg
    return None


def _create_tool_cancellations(tool_calls: list, reason: str) -> list[ToolMessage]:
    """Creates cancellation messages for tool calls.

    When a user rejects a tool execution or chooses another action,
    this creates a ToolMessage for each tool call to convey the reason for cancellation.

    Args:
        tool_calls (list): The list of tool calls to be cancelled (each item includes id, name).
        reason (str): The reason for cancellation (e.g., "cancelled by human operator", "invalid format").

    Returns:
        list[ToolMessage]: A list of cancellation messages for each tool call.
    """
    return [
        ToolMessage(
            content=f"Tool execution {reason}.", tool_call_id=tc["id"], name=tc["name"]
        )
        for tc in tool_calls
    ]


def _parse_args(args) -> dict:
    """Parses tool arguments (including handling JSON strings).

    If the tool call arguments are a JSON string, it parses them into a dictionary.
    If they are already a dictionary, it returns them as is. If parsing fails, it returns an empty dictionary.

    Args:
        args: The tool arguments (str, dict, or other types).

    Returns:
        dict: The parsed arguments dictionary, or an empty dictionary on failure.
    """
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return {}
    return args if isinstance(args, dict) else {}


def _update_tool_calls(original_calls: list, edited_args: dict) -> list:
    """Updates tool calls with user-modified arguments.

    When a user selects the "edit" response type, this replaces the arguments
    of the original tool call with the new arguments provided by the user.

    Args:
        original_calls (list): The list of original tool calls (each item includes name, args).
        edited_args (dict): The dictionary of user-modified arguments.
                            Example: {"args": {"tool_name": {"param": "new_value"}}}

    Returns:
        list: The list of updated tool calls.
    """
    updated_calls = []
    for call in original_calls:
        updated_call = call.copy()
        tool_name = call["name"]

        # Check if the user provided modified arguments for this tool.
        if tool_name in edited_args.get("args", {}):
            updated_call["args"] = _parse_args(edited_args["args"][tool_name])
        else:
            # If no modified arguments, use the original ones.
            updated_call["args"] = _parse_args(call["args"])

        updated_calls.append(updated_call)
    return updated_calls


async def human_approval(state: State) -> Command:
    """Requests user approval before tool execution (the core interrupt point).

    This function is the core of the Human-in-the-Loop pattern. It suspends execution
    to get the user's approval before the agent executes a tool. It calls LangGraph's
    interrupt() function to stop execution and send an approval request to the client.

    Interrupt Mechanism:
    1. When interrupt() is called, LangGraph saves the current state to a checkpoint.
    2. An approval request is sent to the client as an SSE event.
    3. Execution is suspended, waiting for the user's response.
    4. The user sends a response via the POST /threads/{thread_id}/runs/{run_id} endpoint.
    5. This function resumes with the user's response and routes to the next node.

    User Response Types:
    - accept: Execute the tool with the original arguments.
    - edit: Execute the tool after modifying its arguments.
    - response: Cancel the tool execution and provide the user's text response.
    - ignore: Cancel the tool execution and end the conversation.

    Args:
        state (State): The current conversation state (including the message with the tool call).

    Returns:
        Command: A routing instruction for the next node and a state update.
                 - accept: goto="tools" (execute tool).
                 - edit: goto="tools" with updated args (execute tool with modified arguments).
                 - response: goto="call_model" (cancel and re-call the model).
                 - ignore: goto=END (end execution).

    Note:
        - How to resume: POST /threads/{thread_id}/runs/{run_id}
          Body: [{"type": "accept"}] or another response type.
        - LangGraph automatically manages checkpoints, so no explicit saving is needed.
    """
    # TODO: The Mark as Resolved feature needs to be fixed.
    # Issue: Command(goto=END) creates an infinite loop due to a LangGraph bug.
    # GitHub Issue: https://github.com/langchain-ai/langgraph/issues/5572
    # The goto=END command is ignored, and a "branch:to:__end__" channel error occurs.

    # Find the most recent AI message that contains a tool call.
    tool_message = _find_tool_message(state.messages)
    if not tool_message:
        # If there's no tool call, end.
        return Command(goto=END)

    # Call interrupt: suspend execution and request user approval.
    # This function will pause here until the user responds.
    human_response = interrupt(
        {
            "action_request": {
                "action": "tool_execution",
                "args": {
                    tc["name"]: tc.get("args", {}) for tc in tool_message.tool_calls
                },
            },
            "config": {
                "allow_respond": True,  # User can respond directly.
                "allow_accept": True,  # Tool approval is allowed.
                "allow_edit": True,  # Tool argument modification is allowed.
                "allow_ignore": True,  # Tool execution rejection is allowed.
            },
        }
    )

    # If there's no user response or it's in an invalid format, end.
    if not human_response or not isinstance(human_response, list):
        return Command(goto=END)

    # Extract the first response and check its type.
    response = human_response[0]
    response_type = response.get("type", "")
    response_args = response.get("args")

    # Branch based on the user's response type.

    if response_type == "accept":
        # Approval: Execute the tool with the original arguments.
        return Command(goto="tools")

    elif response_type == "response":
        # Response: Cancel the tool execution and pass the user's message to the model.
        # Convert the tool calls to cancellation messages.
        tool_responses = _create_tool_cancellations(
            tool_message.tool_calls, "was interrupted for human input"
        )
        # Create a HumanMessage from the user's text response.
        human_message = HumanMessage(content=str(response_args))
        # Add the cancellation and user messages to the state and re-call the model.
        return Command(
            goto="call_model", update={"messages": tool_responses + [human_message]}
        )

    elif (
        response_type == "edit"
        and isinstance(response_args, dict)
        and "args" in response_args
    ):
        # Modification: Update the tool arguments with the user-provided values and then execute.
        updated_calls = _update_tool_calls(tool_message.tool_calls, response_args)
        # Create a new AIMessage with the modified tool calls.
        updated_message = AIMessage(
            content=tool_message.content, tool_calls=updated_calls, id=tool_message.id
        )
        # Execute the tool with the updated message.
        return Command(goto="tools", update={"messages": [updated_message]})

    else:  # ignore or invalid format
        # Rejection: Cancel the tool execution and end.
        reason = (
            "cancelled by human operator"
            if response_type == "ignore"
            else "invalid format"
        )
        tool_responses = _create_tool_cancellations(tool_message.tool_calls, reason)
        return Command(goto=END, update={"messages": tool_responses})


# ---------------------------------------------------------------------------
# Graph Definition and Configuration
# ---------------------------------------------------------------------------

builder = StateGraph(State, input_schema=InputState, context_schema=Context)

# Define the nodes that will cycle in the graph.
builder.add_node(call_model)  # LLM calling node
builder.add_node("tools", ToolNode(TOOLS))  # Tool execution node
builder.add_node(human_approval)  # User approval node (interrupt point)

# Set the entry point to call_model.
# This is the first node called when the graph is executed.
builder.add_edge("__start__", "call_model")


def route_model_output(state: State) -> Literal["__end__", "human_approval"]:
    """Determines the next node based on the model's output (routing function).

    This function checks the model's last message to see if it includes a tool call.
    If a tool call is present, it routes to the human_approval node to get user approval.
    If there is no tool call, it ends the conversation.

    Routing Logic:
    - Tool call present → human_approval (request user approval)
    - No tool call → __end__ (end conversation)

    Args:
        state (State): The current conversation state (including message history).

    Returns:
        Literal["__end__", "human_approval"]: The name of the next node to execute.

    Raises:
        ValueError: If the last message is not an AIMessage.
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
        )

    # If there are no tool calls, end the conversation.
    if not last_message.tool_calls:
        return "__end__"

    # If there are tool calls, user approval is needed first.
    return "human_approval"


# Add a conditional edge from the call_model node.
# This checks the model's output and branches to human_approval or ends.
builder.add_conditional_edges(
    "call_model", route_model_output, path_map=["human_approval", END]
)


# Add a regular edge from the tools node to call_model.
# This creates a cycle: after using a tool, it always goes back to the model.
# (The model decides the next action based on the tool execution results).
builder.add_edge("tools", "call_model")

# Compile the builder into an executable graph.
# This completes the ReAct agent with Human-in-the-Loop functionality.
graph = builder.compile(name="ReAct Agent")
