"""Main graph definition demonstrating subgraph composition.

This module implements a minimal main graph that delegates to `react_agent.graph` as a subgraph node.
The subgraph pattern allows complex agents to be broken down into reusable, modular components.

Subgraph Composition Pattern:
1. The main graph receives input and processes it in a preprocessing node.
2. The preprocessed state is passed to the subgraph node.
3. The subgraph (react_agent) executes independently.
4. The result of the subgraph is returned to the main graph.
5. The main graph performs final processing and responds.

Key Components:
• no_stream - A preprocessing node that calls an LLM with the langsmith:nostream tag.
• subgraph_agent - A node that runs react_agent.graph as a subgraph.
• graph - The compiled main StateGraph instance.

Graph Structure:
    __start__ → no_stream → subgraph_agent → __end__

Advantages of Subgraphs:
- Reusability: Reuse existing graphs by inserting them as nodes.
- Modularity: Decompose complex logic into independent subgraphs.
- Maintainability: Develop and test each subgraph independently.
- Composability: Combine multiple subgraphs to build complex workflows.

Usage Requirements:
- Uses the same State structure as the react_agent graph.
- Shares configuration via Runtime[Context].
- Requires a chat model that supports tool calling.
"""

from datetime import UTC, datetime
from typing import cast

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph
from langgraph.runtime import Runtime
from react_agent import graph as react_graph
from react_agent.context import Context
from react_agent.state import InputState, State
from react_agent.utils import load_chat_model

# ---------------------------------------------------------------------------
# Initialize Main Graph Builder
# ---------------------------------------------------------------------------
# Uses the same State, InputState, and Context as react_agent to
# ensure seamless data flow between the main graph and the subgraph.
builder = StateGraph(State, input_schema=InputState, context_schema=Context)


# ---------------------------------------------------------------------------
# Node Function: Preprocessing Node (Disable Streaming)
# ---------------------------------------------------------------------------


async def no_stream(
    state: State, runtime: Runtime[Context]
) -> dict[str, list[AIMessage]]:
    """A preprocessing node that calls an LLM with the langsmith:nostream tag.

    This function calls the LLM to generate an initial response before passing it to the subgraph.
    It uses the langsmith:nostream tag to disable streaming for this specific call,
    ensuring that the LangSmith tracing system records the entire response at once without streaming.

    Workflow:
    1. Load model settings and system prompt from Runtime[Context].
    2. Initialize the chat model with the langsmith:nostream tag.
    3. Format the current time into the system prompt.
    4. Call the LLM by combining the system message and conversation history.
    5. Return the LLM response in a list of messages.

    Args:
        state (State): The current conversation state (including message history).
        runtime (Runtime[Context]): The runtime context (model settings, system prompt, etc.).

    Returns:
        dict[str, list[AIMessage]]: A dictionary containing the LLM response message.
            - Returns a list of AIMessages under the "messages" key.
            - The add_messages reducer merges this into the existing messages.

    Note:
        - This node sets the initial context before the subgraph executes.
        - The langsmith:nostream tag ensures that the call is displayed as a single
          completed response in the LangSmith dashboard, without streaming events.
        - The subgraph (react_agent) receives the full state, including this response.
    """
    # Initialize the model with the langsmith:nostream tag.
    # This tag indicates that this call should not be streamed in the LangSmith tracing system.
    model = load_chat_model(runtime.context.model).with_config(
        config={"tags": ["langsmith:nostream"]}
    )

    # Format the system prompt.
    # Insert the current UTC time in ISO format into the prompt to provide time context.
    system_message = runtime.context.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )

    # Call the LLM and get the response.
    # Pass the combined system message and existing conversation history.
    response = cast(
        "AIMessage",
        await model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
    )

    # Return the response message as a list to add to the existing messages.
    # The add_messages reducer will merge this into state.messages.
    return {"messages": [response]}


# ---------------------------------------------------------------------------
# Graph Configuration: Add Nodes and Connect Edges
# ---------------------------------------------------------------------------

# Add the subgraph node.
# Directly add react_graph as the "subgraph_agent" node.
# LangGraph allows compiled graphs to be used as nodes,
# where the subgraph receives the main graph's state, executes, and returns an updated state.
builder.add_node("subgraph_agent", react_graph)

# Add the preprocessing node.
# Add the no_stream function as the "no_stream" node.
# This performs an initial LLM call before the subgraph executes.
builder.add_node("no_stream", no_stream)

# Connect edges: Define the linear execution flow.
# 1. Start → no_stream: Always go through the preprocessing node first.
builder.add_edge("__start__", "no_stream")

# 2. no_stream → subgraph_agent: Pass to the subgraph after preprocessing.
#    The subgraph executes with the state updated by the no_stream node's response.
builder.add_edge("no_stream", "subgraph_agent")

# 3. subgraph_agent → End: The main graph finishes after the subgraph completes.
#    The final state of the subgraph (react_agent) becomes the final state of the main graph.
builder.add_edge("subgraph_agent", "__end__")

# ---------------------------------------------------------------------------
# Compile the Graph
# ---------------------------------------------------------------------------
# Compile the builder to create an executable graph instance.
# The name "Subgraph Agent" is an identifier used in LangSmith tracing and debugging.
graph = builder.compile(name="Subgraph Agent")
