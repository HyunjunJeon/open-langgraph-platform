"""ReAct 에이전트 유틸리티 및 헬퍼 함수

이 모듈은 ReAct 에이전트 그래프에서 사용되는 공통 유틸리티 함수를 제공합니다.
주로 LangChain 메시지 처리 및 채팅 모델 로딩과 관련된 헬퍼 함수들로 구성됩니다.

주요 구성 요소:
• get_message_text() - BaseMessage에서 텍스트 콘텐츠 추출
• load_chat_model() - 제공자/모델 문자열로부터 채팅 모델 초기화

사용 예:
    from graphs.react_agent.utils import get_message_text, load_chat_model

    # 메시지에서 텍스트 추출
    text = get_message_text(ai_message)

    # 채팅 모델 로드
    model = load_chat_model("openai/gpt-4")
"""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage


def get_message_text(msg: BaseMessage) -> str:
    """LangChain 메시지 객체에서 텍스트 콘텐츠 추출

    BaseMessage는 다양한 형식의 content를 가질 수 있습니다:
    - 단순 문자열 (str)
    - 딕셔너리 (dict) - "text" 키에서 추출
    - 리스트 (list) - 각 요소를 문자열로 변환 후 결합

    이 함수는 모든 경우를 처리하여 일관된 문자열 결과를 반환합니다.

    사용 사례:
    - AI 응답 메시지에서 텍스트 추출
    - 사용자 입력 메시지 정규화
    - 메시지 히스토리 텍스트 변환

    Args:
        msg (BaseMessage): LangChain 메시지 객체 (AIMessage, HumanMessage 등)

    Returns:
        str: 추출된 텍스트 콘텐츠 (빈 문자열 가능)

    예제:
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
        # 가장 일반적인 경우: content가 단순 문자열
        return content
    elif isinstance(content, dict):
        # 구조화된 콘텐츠: "text" 키에서 추출
        return content.get("text", "")
    else:
        # 복합 콘텐츠 (리스트 등): 각 부분을 텍스트로 변환 후 결합
        txts = [c if isinstance(c, str) else (c.get("text") or "") for c in content]
        return "".join(txts).strip()


def load_chat_model(fully_specified_name: str) -> BaseChatModel:
    """제공자와 모델명을 포함한 전체 이름으로 채팅 모델 초기화

    이 헬퍼 함수는 "provider/model" 형식의 문자열을 파싱하여
    LangChain의 init_chat_model()을 호출합니다. 이를 통해 다양한
    LLM 제공자의 모델을 일관된 방식으로 로드할 수 있습니다.

    지원되는 제공자 예시:
    - openai: OpenAI GPT 모델
    - anthropic: Anthropic Claude 모델
    - google: Google PaLM/Gemini 모델
    - cohere: Cohere 모델

    사용 사례:
    - Runtime Context에서 모델 설정 읽어서 초기화
    - 사용자별 커스텀 모델 설정 적용
    - 환경 변수 기반 모델 전환

    Args:
        fully_specified_name (str): "provider/model" 형식 문자열
                                    예: "openai/gpt-4", "anthropic/claude-3-opus"

    Returns:
        BaseChatModel: 초기화된 채팅 모델 인스턴스

    Raises:
        ValueError: 형식이 잘못된 경우 (슬래시 누락 등)
        ImportError: 제공자 패키지가 설치되지 않은 경우

    예제:
        >>> model = load_chat_model("openai/gpt-4")
        >>> response = model.invoke("Hello!")

        >>> # Runtime Context와 함께 사용
        >>> model = load_chat_model(runtime.context.model)
    """
    # "provider/model" 형식을 파싱 (최대 1번만 분할)
    provider, model = fully_specified_name.split("/", maxsplit=1)
    return init_chat_model(model, model_provider=provider)
