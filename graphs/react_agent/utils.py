"""ReAct Agent Utilities and Helper Functions

This module provides common utility functions used in the ReAct agent graph.
It mainly consists of helper functions related to LangChain message processing and chat model loading.

Main components:
• get_message_text() - Extracts text content from a BaseMessage.
• load_chat_model() - Initializes a chat model from a provider/model string.

Usage Example:
    from graphs.react_agent.utils import get_message_text, load_chat_model

    # Extract text from a message
    text = get_message_text(ai_message)

    # Load a chat model
    model = load_chat_model("openai/gpt-4")
"""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage


def get_message_text(msg: BaseMessage) -> str:
    """Extracts text content from a LangChain message object.

    A BaseMessage can have content in various formats:
    - A simple string (str).
    - A dictionary (dict) - extracted from the "text" key.
    - A list (list) - each element is converted to a string and then joined.

    This function handles all cases to return a consistent string result.

    Use cases:
    - Extracting text from an AI response message.
    - Normalizing user input messages.
    - Transforming message history to text.

    Args:
        msg (BaseMessage): A LangChain message object (e.g., AIMessage, HumanMessage).

    Returns:
        str: The extracted text content (can be an empty string).

    Example:
        >>> from langchain_core.messages import HumanMessage
        >>> msg = HumanMessage(content="Hello")
        >>> get_message_text(msg)
        'Hello'

        >>> msg = HumanMessage(content={"text": "Hello", "type": "text"})
        >>> get_message_text(msg)
        'Hello'
    """
    content = msg.content
    if isinstance(content, str):
        # The most common case: content is a simple string.
        return content
    elif isinstance(content, dict):
        # Structured content: extract from the "text" key.
        return content.get("text", "")
    else:
        # Complex content (list, etc.): convert each part to text and then join.
        txts = [c if isinstance(c, str) else (c.get("text") or "") for c in content]
        return "".join(txts).strip()


def load_chat_model(fully_specified_name: str) -> BaseChatModel:
    """Initializes a chat model from a full name including the provider and model.

    This helper function parses a string in "provider/model" format and calls
    LangChain's init_chat_model(). This allows loading models from various
    LLM providers in a consistent way.

    Supported provider examples:
    - openai: OpenAI GPT models
    - anthropic: Anthropic Claude models
    - google: Google PaLM/Gemini models
    - cohere: Cohere models

    Use cases:
    - Initializing from model settings read from the Runtime Context.
    - Applying user-specific custom model settings.
    - Switching models based on environment variables.

    Args:
        fully_specified_name (str): A string in "provider/model" format.
                                    Examples: "openai/gpt-4", "anthropic/claude-3-opus"

    Returns:
        BaseChatModel: An initialized chat model instance.

    Raises:
        ValueError: If the format is incorrect (e.g., missing slash).
        ImportError: If the provider package is not installed.

    Example:
        >>> model = load_chat_model("openai/gpt-4")
        >>> response = model.invoke("Hello!")

        >>> # Used with Runtime Context
        >>> model = load_chat_model(runtime.context.model)
    """
    # Parse the "provider/model" format (split at most once).
    provider, model = fully_specified_name.split("/", maxsplit=1)
    return init_chat_model(model, model_provider=provider)
