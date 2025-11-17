"""Collection of prompt templates for the ReAct agent.

This module defines the prompt templates used by the ReAct agent.
Prompts are a crucial component that determines the agent's behavior and response style.

Main components:
• SYSTEM_PROMPT - The agent's default system message (defines its role and provides context).

Prompt Design Principles:
- Clearly define the agent's role and capabilities.
- Include dynamic context information such as system time.
- Provide clear instructions to ensure the LLM behaves consistently.

Usage Example:
    from graphs.react_agent.prompts import SYSTEM_PROMPT

    # Substitute template variables at runtime
    formatted_prompt = SYSTEM_PROMPT.format(system_time=datetime.now())
"""

# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a helpful AI assistant.

System time: {system_time}"""
# Template variables:
#   - system_time: The current system time (provides time context to the agent).
#
# Role: A system message that defines the agent's basic persona and behavior.
#
# Description:
#   - "helpful AI assistant": Guides the agent to respond in a friendly and helpful manner.
#   - system_time variable: Enables accurate answers for time-based questions or scheduling-related tasks.
#
# Note:
#   - This prompt is the system message passed to the LLM at the start of a conversation.
#   - The prompt content is kept in English (for consistency with the LLM model's training data).
#   - The agent's role can be customized to fit project requirements if needed.
