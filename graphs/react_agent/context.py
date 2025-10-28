"""ReAct 에이전트 런타임 컨텍스트 정의

이 모듈은 LangGraph의 Runtime[Context] 패턴을 사용하여 에이전트 실행 시
필요한 설정 매개변수를 정의합니다. 컨텍스트는 그래프 노드에서 runtime.context를
통해 접근할 수 있으며, 사용자별 설정, 모델 선택, 도구 동작을 제어합니다.

주요 구성 요소:
• Context - 에이전트 실행 설정을 담는 데이터클래스
  - system_prompt: 에이전트 동작을 정의하는 시스템 프롬프트
  - model: 사용할 LLM 모델 (provider/model-name 형식)
  - max_search_results: 검색 도구의 최대 결과 수

사용 패턴:
    # 그래프 노드에서 컨텍스트 접근
    def my_node(state: State, *, runtime: Runtime[Context]):
        model_name = runtime.context.model
        system_prompt = runtime.context.system_prompt

특징:
- 환경 변수 자동 로드: __post_init__에서 대문자 환경 변수 확인
- 타입 안전성: dataclass로 정의되어 IDE 자동완성 지원
- 메타데이터: 각 필드에 설명 포함하여 문서화 및 UI 생성 지원
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from typing import Annotated

from react_agent import prompts


@dataclass(kw_only=True)
class Context:
    """ReAct 에이전트 런타임 컨텍스트

    이 클래스는 LangGraph 그래프 실행 시 Runtime[Context] 패턴을 통해
    노드에 전달되는 설정 매개변수를 정의합니다. 각 필드는 에이전트의
    동작을 제어하며, 기본값 또는 환경 변수를 통해 설정할 수 있습니다.

    주요 필드:
    - system_prompt: 에이전트의 역할과 동작을 정의하는 시스템 프롬프트
    - model: LLM 모델 식별자 (예: "openai/gpt-4o-mini")
    - max_search_results: 검색 도구가 반환할 최대 결과 수

    사용 예:
        # 기본값으로 컨텍스트 생성
        context = Context()

        # 커스텀 설정으로 컨텍스트 생성
        context = Context(
            model="anthropic/claude-3-5-sonnet-20241022",
            max_search_results=5
        )

        # 그래프 노드에서 접근
        def my_node(state: State, *, runtime: Runtime[Context]):
            model = runtime.context.model
            prompt = runtime.context.system_prompt

    참고:
        - kw_only=True로 키워드 인자만 허용
        - __post_init__에서 환경 변수 자동 로드 수행
        - metadata는 LangGraph Studio UI에서 설정 폼 생성에 사용됨
    """

    system_prompt: str = field(
        default=prompts.SYSTEM_PROMPT,
        metadata={
            "description": "The system prompt to use for the agent's interactions. "
            "This prompt sets the context and behavior for the agent."
        },
    )
    """에이전트의 시스템 프롬프트

    에이전트의 역할, 동작 방식, 제약 사항을 정의하는 프롬프트입니다.
    기본값은 prompts.SYSTEM_PROMPT에서 가져오며, 환경 변수 SYSTEM_PROMPT로
    오버라이드할 수 있습니다.
    """

    model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = field(
        default="openai/gpt-4o-mini",
        metadata={
            "description": "The name of the language model to use for the agent's main interactions. "
            "Should be in the form: provider/model-name."
        },
    )
    """사용할 LLM 모델 식별자

    "provider/model-name" 형식으로 지정합니다.
    예: "openai/gpt-4o-mini", "anthropic/claude-3-5-sonnet-20241022"

    __template_metadata__의 "kind": "llm"은 LangGraph Studio에서
    모델 선택 UI를 렌더링할 때 사용됩니다.

    환경 변수 MODEL로 오버라이드할 수 있습니다.
    """

    max_search_results: int = field(
        default=10,
        metadata={
            "description": "The maximum number of search results to return for each search query."
        },
    )
    """검색 도구의 최대 결과 수

    search 도구가 각 검색 쿼리에 대해 반환할 최대 결과 개수입니다.
    값이 클수록 더 많은 정보를 제공하지만 토큰 사용량과 처리 시간이 증가합니다.

    환경 변수 MAX_SEARCH_RESULTS로 오버라이드할 수 있습니다.
    """

    def __post_init__(self) -> None:
        """환경 변수에서 설정값 자동 로드

        데이터클래스 초기화 후 실행되어, 명시적으로 전달되지 않은 필드에 대해
        환경 변수에서 값을 로드합니다. 필드명을 대문자로 변환한 환경 변수를 확인합니다.

        동작 흐름:
        1. 모든 dataclass 필드를 순회
        2. init=False인 필드는 건너뜀 (계산된 필드 등)
        3. 현재 값이 기본값과 같으면 환경 변수 확인
        4. 환경 변수가 존재하면 해당 값으로 설정, 없으면 기본값 유지

        예시:
            # 환경 변수 설정: MODEL=anthropic/claude-3-5-sonnet-20241022
            context = Context()  # model 필드는 환경 변수에서 로드됨

            # 명시적으로 전달하면 환경 변수 무시
            context = Context(model="openai/gpt-4o-mini")

        참고:
            - 필드명을 대문자로 변환하여 환경 변수명 생성
            - system_prompt -> SYSTEM_PROMPT
            - max_search_results -> MAX_SEARCH_RESULTS
        """
        for f in fields(self):
            # 초기화 불가능한 필드는 건너뜀 (계산된 필드, 내부 필드 등)
            if not f.init:
                continue

            # 기본값이 그대로 사용된 경우에만 환경 변수 확인
            if getattr(self, f.name) == f.default:
                # 필드명을 대문자로 변환하여 환경 변수 조회
                # 예: system_prompt -> SYSTEM_PROMPT
                setattr(self, f.name, os.environ.get(f.name.upper(), f.default))
