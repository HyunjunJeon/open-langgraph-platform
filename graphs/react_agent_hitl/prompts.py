"""Prompt templates for the Human-in-the-Loop ReAct agent.

This module defines the system prompt used by the HITL (Human-in-the-Loop) ReAct agent.
The prompt determines the agent's behavior and personality, and can include dynamic information such as the system time.

Main Components:
• SYSTEM_PROMPT - A template that defines the agent's basic persona and system information.

Usage Example:
    from graphs.react_agent_hitl.prompts import SYSTEM_PROMPT

    # Create a prompt including the system time
    formatted_prompt = SYSTEM_PROMPT.format(system_time=datetime.now().isoformat())

Note:
    - The prompt text is kept in English so that the LLM can understand it.
    - Template variables use Python's str.format() syntax.
    - The HITL agent interacts with the user based on this prompt.
"""

# Agent system prompt template
# Kept in English as it's the prompt the LLM will use.
# The {system_time} variable is substituted with the current system time at runtime.
SYSTEM_PROMPT = """You are a helpful AI assistant.

System time: {system_time}"""
