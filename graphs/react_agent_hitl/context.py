"""Runtime Context Definition for the Human-in-the-Loop ReAct Agent

This module defines the configurable parameters used during the execution
of the HITL (Human-in-the-Loop) ReAct agent. The Context class is accessible
in graph nodes via LangGraph's Runtime[Context] pattern.

Main Components:
• Context - Runtime settings for the HITL agent (system prompt, model, search settings)

Features:
- Automatic environment variable loading: Parameters not explicitly passed are loaded from environment variables.
- LLM metadata: The model field integrates with the LangGraph template system.
- HITL-specific: Supports interrupt functionality for human approval before tool execution.

Usage Example:
    # Accessing context in a graph node
    async def call_model(state: State, runtime: Runtime[Context]):
        model = load_chat_model(runtime.context.model)
        prompt = runtime.context.system_prompt.format(...)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from typing import Annotated

from . import prompts


@dataclass(kw_only=True)
class Context:
    """Runtime context for the HITL ReAct agent.

    This class contains all the configuration parameters needed for agent execution.
    It is accessible from all nodes in the graph via LangGraph's Runtime[Context]
    pattern and can be dynamically configured via environment variables.

    HITL Features:
    - Uses the interrupt() function to request human approval/modification/rejection before tool calls.
    - The user can approve the tool execution, modify parameters, reject it, or respond directly.
    - All tool executions are validated through the human_approval node.

    Field Descriptions:
        system_prompt: The system prompt that defines the agent's behavior.
        model: The language model to use (format: provider/model-name).
        max_search_results: The maximum number of results per search query.

    Environment Variable Support:
        Default values can be overridden with the SYSTEM_PROMPT, MODEL, and MAX_SEARCH_RESULTS environment variables.
    """

    system_prompt: str = field(
        default=prompts.SYSTEM_PROMPT,
        metadata={
            "description": "The system prompt to use for the agent's interactions. "
            "This prompt sets the context and behavior for the agent."
        },
    )
    # The system prompt to use for interactions with the agent.
    # This prompt sets the agent's context and behavior.
    # For a HITL agent, the way it requests user approval is also influenced by this prompt.

    model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = field(
        default="openai/gpt-4o-mini",
        metadata={
            "description": "The name of the language model to use for the agent's main interactions. "
            "Should be in the form: provider/model-name."
        },
    )
    # The name of the language model to use for the agent's main interactions.
    # Format: provider/model-name (e.g., openai/gpt-4o-mini, anthropic/claude-3-5-sonnet).
    # The metadata in the Annotated type indicates that this is an LLM field in the LangGraph template system.

    max_search_results: int = field(
        default=10,
        metadata={
            "description": "The maximum number of search results to return for each search query."
        },
    )
    # The maximum number of results to return for each search query.
    # This limits the amount of search results during tool calls to manage context length.

    def __post_init__(self) -> None:
        """Loads unset attribute values from environment variables after initialization.

        Flow:
        1. Iterate through all dataclass fields.
        2. Skip fields with init=False.
        3. If the field's value is the same as its default, check for an environment variable.
        4. If the environment variable exists, set the field to its value.

        Environment Variable Rules:
        - Convert the field name to uppercase (e.g., model → MODEL).
        - If the environment variable is not present, the default value is maintained.

        Example:
            # Set environment variables
            export MODEL="anthropic/claude-3-5-sonnet"
            export MAX_SEARCH_RESULTS="20"

            # Context creation will automatically use the environment variable values
            context = Context()
            # context.model == "anthropic/claude-3-5-sonnet"
            # context.max_search_results == "20"
        """
        for f in fields(self):
            if not f.init:
                continue

            if getattr(self, f.name) == f.default:
                setattr(self, f.name, os.environ.get(f.name.upper(), f.default))
