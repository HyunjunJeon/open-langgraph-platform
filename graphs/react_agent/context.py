"""ReAct Agent Runtime Context Definition

This module defines the configuration parameters required for agent execution
using LangGraph's Runtime[Context] pattern. The context is accessible in graph nodes
via runtime.context and controls user-specific settings, model selection, and tool behavior.

Main components:
• Context - A dataclass containing agent execution settings
  - system_prompt: The system prompt that defines the agent's behavior
  - model: The LLM model to use (in provider/model-name format)
  - max_search_results: The maximum number of results for the search tool

Usage pattern:
    # Accessing context in a graph node
    def my_node(state: State, *, runtime: Runtime[Context]):
        model_name = runtime.context.model
        system_prompt = runtime.context.system_prompt

Features:
- Automatic environment variable loading: __post_init__ checks for uppercase environment variables
- Type safety: Defined as a dataclass, providing IDE autocompletion support
- Metadata: Each field includes a description to support documentation and UI generation
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from typing import Annotated

from react_agent import prompts


@dataclass(kw_only=True)
class Context:
    """ReAct Agent Runtime Context

    This class defines the configuration parameters passed to nodes via the
    Runtime[Context] pattern during LangGraph graph execution. Each field
    controls the agent's behavior and can be set via default values or
    environment variables.

    Key fields:
    - system_prompt: The system prompt that defines the agent's role and behavior
    - model: The LLM model identifier (e.g., "openai/gpt-4o-mini")
    - max_search_results: The maximum number of results the search tool should return

    Usage example:
        # Create context with default values
        context = Context()

        # Create context with custom settings
        context = Context(
            model="anthropic/claude-3-5-sonnet-20241022",
            max_search_results=5
        )

        # Access in a graph node
        def my_node(state: State, *, runtime: Runtime[Context]):
            model = runtime.context.model
            prompt = runtime.context.system_prompt

    Note:
        - kw_only=True allows keyword-only arguments
        - __post_init__ performs automatic loading from environment variables
        - metadata is used by LangGraph Studio to generate configuration forms in the UI
    """

    system_prompt: str = field(
        default=prompts.SYSTEM_PROMPT,
        metadata={
            "description": "The system prompt to use for the agent's interactions. "
            "This prompt sets the context and behavior for the agent."
        },
    )
    """The agent's system prompt.

    This prompt defines the agent's role, behavior, and constraints.
    The default value is taken from prompts.SYSTEM_PROMPT and can be
    overridden by the SYSTEM_PROMPT environment variable.
    """

    model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = field(
        default="openai/gpt-4o-mini",
        metadata={
            "description": "The name of the language model to use for the agent's main interactions. "
            "Should be in the form: provider/model-name."
        },
    )
    """The LLM model identifier to use.

    Specified in "provider/model-name" format.
    Examples: "openai/gpt-4o-mini", "anthropic/claude-3-5-sonnet-20241022"

    The "__template_metadata__": {"kind": "llm"} is used by LangGraph Studio
    to render a model selection UI.

    Can be overridden by the MODEL environment variable.
    """

    max_search_results: int = field(
        default=10,
        metadata={
            "description": "The maximum number of search results to return for each search query."
        },
    )
    """The maximum number of results for the search tool.

    This is the maximum number of results the search tool will return for each query.
    A larger value provides more information but increases token usage and processing time.

    Can be overridden by the MAX_SEARCH_RESULTS environment variable.
    """

    def __post_init__(self) -> None:
        """Automatically load settings from environment variables.

        This method runs after the dataclass is initialized and loads values
        from environment variables for fields that were not explicitly provided.
        It checks for environment variables named after the uppercase version of the field names.

        Flow:
        1. Iterate through all dataclass fields.
        2. Skip fields with init=False (e.g., calculated fields).
        3. If the current value is the same as the default, check for an environment variable.
        4. If the environment variable exists, set the field to its value; otherwise, keep the default.

        Example:
            # Set environment variable: MODEL=anthropic/claude-3-5-sonnet-20241022
            context = Context()  # The model field will be loaded from the environment variable.

            # Explicitly passed values ignore environment variables.
            context = Context(model="openai/gpt-4o-mini")

        Note:
            - Environment variable names are generated by converting field names to uppercase.
            - system_prompt -> SYSTEM_PROMPT
            - max_search_results -> MAX_SEARCH_RESULTS
        """
        for f in fields(self):
            # Skip non-initializable fields (e.g., calculated fields, internal fields)
            if not f.init:
                continue

            # Only check environment variables if the default value is still being used
            if getattr(self, f.name) == f.default:
                # Look up environment variable by converting field name to uppercase
                # e.g., system_prompt -> SYSTEM_PROMPT
                setattr(self, f.name, os.environ.get(f.name.upper(), f.default))
