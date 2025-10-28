"""HITL 에이전트 유틸리티 및 헬퍼 함수

이 모듈은 Human-in-the-Loop ReAct 에이전트를 지원하는 공통 유틸리티 함수를 제공합니다.
LangChain 메시지 처리 및 채팅 모델 로딩을 위한 헬퍼를 포함합니다.

주요 유틸리티:
• get_message_text() - 메시지에서 텍스트 콘텐츠 추출
• load_chat_model() - 문자열 형식으로 채팅 모델 로드

사용 예:
    from graphs.react_agent_hitl.utils import get_message_text, load_chat_model

    # 메시지 텍스트 추출
    text = get_message_text(message)

    # 모델 로드
    model = load_chat_model("openai/gpt-4")
"""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage


def get_message_text(msg: BaseMessage) -> str:
    """메시지 객체에서 텍스트 콘텐츠를 추출

    LangChain 메시지는 다양한 형식의 콘텐츠를 포함할 수 있습니다
    (단순 문자열, 딕셔너리, 또는 멀티모달 콘텐츠 리스트).
    이 함수는 모든 형식을 처리하여 텍스트만 추출합니다.

    지원하는 콘텐츠 형식:
    1. 문자열: 그대로 반환
    2. 딕셔너리: "text" 키의 값 추출
    3. 리스트: 각 항목에서 텍스트 추출 후 결합

    Args:
        msg (BaseMessage): 텍스트를 추출할 LangChain 메시지 객체

    Returns:
        str: 추출된 텍스트 콘텐츠 (리스트인 경우 결합 후 공백 제거)

    사용 예:
        from langchain_core.messages import HumanMessage

        # 단순 문자열 메시지
        msg1 = HumanMessage(content="Hello")
        text1 = get_message_text(msg1)  # "Hello"

        # 멀티모달 메시지 (텍스트 + 이미지)
        msg2 = HumanMessage(content=[
            {"type": "text", "text": "Describe this image"},
            {"type": "image_url", "image_url": "..."}
        ])
        text2 = get_message_text(msg2)  # "Describe this image"
    """
    content = msg.content

    if isinstance(content, str):
        # 단순 문자열 콘텐츠
        return content
    elif isinstance(content, dict):
        # 딕셔너리 형식 (일반적으로 "text" 키 포함)
        return content.get("text", "")
    else:
        # 리스트 형식 (멀티모달 콘텐츠)
        # 각 항목에서 텍스트만 추출하여 결합
        txts = [c if isinstance(c, str) else (c.get("text") or "") for c in content]
        return "".join(txts).strip()


def load_chat_model(fully_specified_name: str) -> BaseChatModel:
    """문자열 형식에서 채팅 모델을 로드

    "provider/model" 형식의 문자열로부터 LangChain 채팅 모델을 초기화합니다.
    이 방식은 설정 파일이나 환경 변수로 모델을 지정할 때 유용합니다.

    지원하는 제공자:
    - openai: OpenAI 모델 (gpt-4, gpt-3.5-turbo 등)
    - anthropic: Anthropic 모델 (claude-3-opus, claude-3-sonnet 등)
    - google-genai: Google Gemini 모델
    - azure-openai: Azure OpenAI 서비스
    - 기타 LangChain이 지원하는 모든 제공자

    Args:
        fully_specified_name (str): "제공자/모델" 형식의 문자열
                                   예: "openai/gpt-4", "anthropic/claude-3-opus"

    Returns:
        BaseChatModel: 초기화된 LangChain 채팅 모델 인스턴스

    Raises:
        ValueError: 형식이 잘못된 경우 (슬래시가 없는 경우)
        ImportError: 제공자의 SDK가 설치되지 않은 경우

    사용 예:
        # OpenAI GPT-4 모델 로드
        model = load_chat_model("openai/gpt-4")

        # Anthropic Claude 모델 로드
        model = load_chat_model("anthropic/claude-3-opus-20240229")

        # 설정에서 동적으로 로드
        model_name = config.get("model")  # "openai/gpt-4o"
        model = load_chat_model(model_name)

    참고:
        - API 키는 환경 변수를 통해 설정되어야 합니다
        - 제공자별로 필요한 패키지가 설치되어 있어야 합니다
    """
    # 문자열을 제공자와 모델명으로 분리
    provider, model = fully_specified_name.split("/", maxsplit=1)

    # LangChain의 init_chat_model로 모델 초기화
    return init_chat_model(model, model_provider=provider)
