"""HITL Agent Utilities and Helper Functions

This module provides common utility functions that support the Human-in-the-Loop ReAct agent.
It includes helpers for LangChain message processing and chat model loading.

Main Utilities:
• get_message_text() - Extracts text content from a message.
• load_chat_model() - Loads a chat model from a string format.

Usage Example:
    from graphs.react_agent_hitl.utils import get_message_text, load_chat_model

    # Extract message text
    text = get_message_text(message)

    # Load a model
    model = load_chat_model("openai/gpt-4")
"""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage


def get_message_text(msg: BaseMessage) -> str:
    """Extracts the text content from a message object.

    LangChain messages can contain content in various formats
    (a simple string, a dictionary, or a list for multimodal content).
    This function handles all formats to extract only the text.

    Supported content formats:
    1. String: Returns as is.
    2. Dictionary: Extracts the value of the "text" key.
    3. List: Extracts the text from each item and then joins them.

    Args:
        msg (BaseMessage): The LangChain message object to extract text from.

    Returns:
        str: The extracted text content (joined and stripped if it's a list).

    Usage Example:
        from langchain_core.messages import HumanMessage

        # Simple string message
        msg1 = HumanMessage(content="Hello")
        text1 = get_message_text(msg1)  # "Hello"

        # Multimodal message (text + image)
        msg2 = HumanMessage(content=[
            {"type": "text", "text": "Describe this image"},
            {"type": "image_url", "image_url": "..."}
        ])
        text2 = get_message_text(msg2)  # "Describe this image"
    """
    content = msg.content

    if isinstance(content, str):
        # Simple string content
        return content
    elif isinstance(content, dict):
        # Dictionary format (usually includes a "text" key)
        return content.get("text", "")
    else:
        # List format (multimodal content)
        # Extract only the text from each item and join them
        txts = [c if isinstance(c, str) else (c.get("text") or "") for c in content]
        return "".join(txts).strip()


def load_chat_model(fully_specified_name: str) -> BaseChatModel:
    """Loads a chat model from a string format.

    Initializes a LangChain chat model from a string in "provider/model" format.
    This approach is useful for specifying a model in a configuration file or environment variable.

    Supported providers:
    - openai: OpenAI models (gpt-4, gpt-3.5-turbo, etc.)
    - anthropic: Anthropic models (claude-3-opus, claude-3-sonnet, etc.)
    - google-genai: Google Gemini models
    - azure-openai: Azure OpenAI service
    - Any other provider supported by LangChain

    Args:
        fully_specified_name (str): A string in "provider/model" format.
                                   Examples: "openai/gpt-4", "anthropic/claude-3-opus"

    Returns:
        BaseChatModel: An initialized LangChain chat model instance.

    Raises:
        ValueError: If the format is incorrect (e.g., no slash).
        ImportError: If the provider's SDK is not installed.

    Usage Example:
        # Load the OpenAI GPT-4 model
        model = load_chat_model("openai/gpt-4")

        # Load the Anthropic Claude model
        model = load_chat_model("anthropic/claude-3-opus-20240229")

        # Load dynamically from a configuration
        model_name = config.get("model")  # "openai/gpt-4o"
        model = load_chat_model(model_name)

    Note:
        - API keys must be set via environment variables.
        - The necessary packages for each provider must be installed.
    """
    # Split the string into provider and model name
    provider, model = fully_specified_name.split("/", maxsplit=1)

    # Initialize the model with LangChain's init_chat_model
    return init_chat_model(model, model_provider=provider)
