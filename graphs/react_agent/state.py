"""ReAct 에이전트의 상태 구조 정의

이 모듈은 LangGraph 그래프에서 사용되는 상태(State) 구조를 정의합니다.
TypedDict를 사용하여 상태 채널과 리듀서를 명확히 정의하고,
에이전트 실행 중 필요한 모든 정보를 추적합니다.

주요 구성 요소:
• InputState - 외부 세계와의 인터페이스를 나타내는 입력 상태
• State - 에이전트의 전체 생애주기 동안 사용되는 완전한 상태

상태 채널:
• messages - 대화 메시지 이력 (add_messages 리듀서로 관리)
• is_last_step - 재귀 제한 도달 여부를 나타내는 관리형 변수
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from langgraph.managed import IsLastStep


@dataclass
class InputState:
    """에이전트의 입력 상태를 정의하며, 외부 세계와의 좁은 인터페이스를 나타냄

    이 클래스는 외부로부터 들어오는 데이터의 초기 상태와 구조를 정의합니다.
    LangGraph 그래프의 입력 채널로 사용되며, 클라이언트가 제공하는
    최소한의 정보만 포함합니다.

    주요 특징:
    - 외부 API 요청으로부터 받은 입력 데이터 구조화
    - State 클래스의 부모 클래스로 사용
    - 입력 검증 및 타입 안정성 제공

    사용 예:
        input_state = InputState(messages=[HumanMessage(content="안녕하세요")])
    """

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(
        default_factory=list
    )
    """
    에이전트의 주요 실행 상태를 추적하는 메시지 이력

    일반적으로 다음과 같은 패턴으로 누적됩니다:
    1. HumanMessage - 사용자 입력
    2. AIMessage with .tool_calls - 에이전트가 정보 수집을 위해 선택한 도구
    3. ToolMessage(s) - 실행된 도구의 응답 또는 오류
    4. AIMessage without .tool_calls - 에이전트가 사용자에게 비구조화된 형식으로 응답
    5. HumanMessage - 사용자가 다음 대화 턴으로 응답

    2-5 단계는 필요에 따라 반복됩니다.

    `add_messages` 리듀서 동작:
    - 새 메시지를 기존 메시지와 병합
    - ID를 기준으로 업데이트하여 "추가 전용(append-only)" 상태 유지
    - 동일한 ID를 가진 메시지가 제공되면 기존 메시지를 업데이트
    - 이를 통해 메시지 수정 및 재시도 패턴 지원
    """


@dataclass
class State(InputState):
    """에이전트의 완전한 상태를 나타내며, InputState를 추가 속성으로 확장

    이 클래스는 에이전트의 전체 생애주기 동안 필요한 모든 정보를 저장합니다.
    InputState를 상속받아 입력 데이터뿐만 아니라 실행 중 생성되는
    내부 상태 정보도 포함합니다.

    주요 특징:
    - InputState의 모든 채널 포함 (messages 등)
    - 실행 제어를 위한 관리형 변수 추가 (is_last_step)
    - LangGraph가 체크포인트로 영속화하는 완전한 상태

    사용 패턴:
    - 노드 함수는 State를 입력으로 받고 부분 업데이트를 반환
    - LangGraph는 리듀서를 사용하여 부분 업데이트를 병합
    - 각 단계마다 전체 상태가 체크포인트에 저장됨

    사용 예:
        def my_node(state: State) -> dict:
            # 상태에서 메시지 읽기
            messages = state.messages
            # 부분 업데이트 반환 (리듀서가 병합)
            return {"messages": [AIMessage(content="응답")]}
    """

    is_last_step: IsLastStep = field(default=False)
    """
    그래프가 오류를 발생시키기 전 현재 단계가 마지막인지 여부를 나타냄

    관리형 변수 특징:
    - 사용자 코드가 아닌 LangGraph 상태 머신이 제어
    - 단계 카운트가 recursion_limit - 1에 도달하면 True로 설정
    - 무한 루프 방지 및 재귀 제한 처리에 사용

    동작 방식:
    1. LangGraph가 각 단계마다 카운트 증가
    2. recursion_limit - 1 도달 시 is_last_step = True
    3. 노드는 이 값을 확인하여 종료 여부 결정 가능
    4. 다음 단계에서 recursion_limit 도달 시 RecursionError 발생

    사용 예:
        def my_node(state: State) -> dict:
            if state.is_last_step:
                # 마지막 단계이므로 강제 종료
                return {"messages": [AIMessage(content="제한 도달")]}
            # 정상 처리 계속
    """
