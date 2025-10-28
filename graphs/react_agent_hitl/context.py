"""Human-in-the-Loop ReAct 에이전트의 런타임 컨텍스트 정의

이 모듈은 HITL(Human-in-the-Loop) ReAct 에이전트의 실행 시 사용되는
설정 가능한 파라미터들을 정의합니다. Context 클래스는 LangGraph의
Runtime[Context] 패턴을 통해 그래프 노드에서 접근 가능합니다.

주요 구성 요소:
• Context - HITL 에이전트의 런타임 설정 (시스템 프롬프트, 모델, 검색 설정)

특징:
- 환경 변수 자동 로드: 명시적으로 전달되지 않은 파라미터는 환경 변수에서 로드
- LLM 메타데이터: model 필드는 LangGraph 템플릿 시스템과 통합
- HITL 특화: 도구 실행 전 인간 승인을 위한 인터럽트 기능 지원

사용 예:
    # 그래프 노드에서 컨텍스트 접근
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
    """HITL ReAct 에이전트의 런타임 컨텍스트

    이 클래스는 에이전트 실행 시 필요한 모든 설정 파라미터를 담고 있습니다.
    LangGraph의 Runtime[Context] 패턴을 통해 그래프의 모든 노드에서 접근 가능하며,
    환경 변수를 통해 동적으로 설정을 변경할 수 있습니다.

    HITL 특징:
    - 도구 호출 전 인간의 승인/수정/거부를 요청하는 interrupt() 기능 사용
    - 사용자는 도구 실행을 승인, 파라미터 수정, 거부, 또는 직접 응답 가능
    - 모든 도구 실행은 human_approval 노드를 거쳐 검증됨

    필드 설명:
        system_prompt: 에이전트의 동작 방식을 정의하는 시스템 프롬프트
        model: 사용할 언어 모델 (형식: provider/model-name)
        max_search_results: 검색 쿼리당 최대 결과 개수

    환경 변수 지원:
        SYSTEM_PROMPT, MODEL, MAX_SEARCH_RESULTS 환경 변수로 기본값 오버라이드 가능
    """

    system_prompt: str = field(
        default=prompts.SYSTEM_PROMPT,
        metadata={
            "description": "The system prompt to use for the agent's interactions. "
            "This prompt sets the context and behavior for the agent."
        },
    )
    # 에이전트와의 상호작용에 사용할 시스템 프롬프트
    # 이 프롬프트는 에이전트의 컨텍스트와 행동 방식을 설정합니다
    # HITL 에이전트의 경우, 사용자 승인을 요청하는 방식도 이 프롬프트에 영향받습니다

    model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = field(
        default="openai/gpt-4o-mini",
        metadata={
            "description": "The name of the language model to use for the agent's main interactions. "
            "Should be in the form: provider/model-name."
        },
    )
    # 에이전트의 주요 상호작용에 사용할 언어 모델 이름
    # 형식: provider/model-name (예: openai/gpt-4o-mini, anthropic/claude-3-5-sonnet)
    # Annotated 타입의 메타데이터는 LangGraph 템플릿 시스템에서 LLM 필드임을 표시

    max_search_results: int = field(
        default=10,
        metadata={
            "description": "The maximum number of search results to return for each search query."
        },
    )
    # 각 검색 쿼리에서 반환할 최대 결과 개수
    # 도구 호출 시 검색 결과의 양을 제한하여 컨텍스트 길이를 관리

    def __post_init__(self) -> None:
        """초기화 후 환경 변수에서 미설정 속성값 로드

        동작 흐름:
        1. 모든 dataclass 필드를 순회
        2. init=False인 필드는 건너뜀
        3. 필드값이 기본값과 같으면 환경 변수 확인
        4. 환경 변수가 있으면 해당 값으로 설정

        환경 변수 규칙:
        - 필드명을 대문자로 변환 (예: model → MODEL)
        - 환경 변수가 없으면 기본값 유지

        예시:
            # 환경 변수 설정
            export MODEL="anthropic/claude-3-5-sonnet"
            export MAX_SEARCH_RESULTS="20"

            # Context 생성 시 자동으로 환경 변수 값 사용
            context = Context()
            # context.model == "anthropic/claude-3-5-sonnet"
            # context.max_search_results == "20"
        """
        for f in fields(self):
            if not f.init:
                continue

            if getattr(self, f.name) == f.default:
                setattr(self, f.name, os.environ.get(f.name.upper(), f.default))
