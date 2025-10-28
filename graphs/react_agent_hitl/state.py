"""Human-in-the-Loop 에이전트의 상태 구조 정의

이 모듈은 HITL(Human-in-the-Loop) 기능을 지원하는 ReAct 에이전트의 상태 채널과
데이터 구조를 정의합니다. LangGraph의 상태 관리 시스템을 활용하여 대화 히스토리,
도구 호출, 인터럽트 지점 등을 추적합니다.

주요 구성 요소:
• InputState - 외부와의 인터페이스를 정의하는 입력 상태
• State - 그래프 실행 전체에서 사용되는 완전한 상태

상태 채널:
- messages: 대화 메시지 히스토리 (add_messages 리듀서 사용)
- is_last_step: 재귀 한계 도달 여부 (LangGraph 관리 변수)

사용 예:
    from react_agent_hitl.state import State, InputState

    # 그래프 정의 시 상태 스키마 지정
    builder = StateGraph(State, input_schema=InputState)
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
    """외부와의 인터페이스를 정의하는 에이전트 입력 상태

    이 클래스는 그래프가 외부로부터 받는 입력 데이터의 구조를 정의합니다.
    LangGraph는 input_schema로 이 클래스를 사용하여 클라이언트가 제공해야 하는
    최소한의 데이터만 요구하고, 내부 상태는 숨깁니다.

    HITL 맥락에서의 역할:
    - 클라이언트는 메시지만 제공하면 됨 (is_last_step 등은 자동 관리)
    - 인터럽트 재개 시에도 동일한 구조 사용
    - 상태의 "공개 API" 역할
    """

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(
        default_factory=list
    )
    """에이전트의 주요 실행 상태를 추적하는 메시지 목록

    HITL 에이전트에서의 일반적인 메시지 누적 패턴:
    1. HumanMessage - 사용자 입력
    2. AIMessage (tool_calls 포함) - 에이전트가 정보 수집을 위해 선택한 도구
    3. ToolMessage(s) - 실행된 도구의 응답 또는 에러
    4. AIMessage (tool_calls 없음) - 에이전트가 사용자에게 최종 응답
    5. HumanMessage - 사용자의 다음 대화 턴

    2-5단계는 필요에 따라 반복됩니다.

    인터럽트 처리:
    - human_approval 노드에서 interrupt() 호출 시 현재 메시지 상태가 보존됨
    - 사용자가 도구 실행을 수정하면 업데이트된 AIMessage로 교체됨
    - 사용자가 응답을 선택하면 새로운 HumanMessage가 추가됨

    리듀서 동작:
    `add_messages` 어노테이션은 새 메시지를 기존 메시지와 병합하며,
    동일한 ID를 가진 메시지가 제공되면 기존 메시지를 업데이트합니다.
    이를 통해 "추가 전용" 상태를 유지하면서도 메시지 수정이 가능합니다.
    """


@dataclass
class State(InputState):
    """에이전트의 완전한 내부 상태를 나타내는 클래스

    이 클래스는 InputState를 확장하여 그래프 실행 중에만 필요한
    추가 속성을 포함합니다. LangGraph 내부에서 사용되며,
    클라이언트에게는 노출되지 않습니다.

    상속 관계:
    - InputState의 모든 필드 포함 (messages)
    - 그래프 내부 제어를 위한 관리 변수 추가 (is_last_step)

    HITL 에이전트에서의 역할:
    - 노드 함수들이 이 상태를 읽고 수정함
    - 인터럽트 발생 시 체크포인트에 전체 상태가 저장됨
    - 재귀 한계 감지를 통해 무한 루프 방지

    사용 패턴:
    그래프의 각 노드는 State를 입력받아 상태 업데이트를 반환:
        async def call_model(state: State) -> dict:
            # state.messages 읽기
            # state.is_last_step 확인
            return {"messages": [new_message]}
    """

    is_last_step: IsLastStep = field(default=False)
    """재귀 한계 도달 직전 단계인지 나타내는 플래그

    이 변수는 LangGraph가 관리하는 '관리 변수(managed variable)'로,
    사용자 코드가 아닌 상태 머신이 자동으로 제어합니다.

    동작 방식:
    - 그래프 실행 단계가 (recursion_limit - 1)에 도달하면 True로 설정됨
    - call_model 노드에서 이 값을 확인하여 적절한 종료 처리 수행
    - 무한 루프를 방지하기 위한 안전장치

    HITL 맥락에서의 활용:
    - 최대 단계에서 모델이 여전히 도구를 호출하려는 경우 감지
    - 사용자에게 "단계 제한 내에 답을 찾지 못함" 메시지 반환
    - 인터럽트 대기 중에는 단계 수에 포함되지 않음

    타입:
    IsLastStep은 LangGraph의 특수 타입으로, bool처럼 동작하지만
    내부적으로 관리 상태를 추적합니다.

    참고:
        recursion_limit은 그래프 컴파일 시 설정하거나 실행 config에서 지정합니다:
        graph = builder.compile(checkpointer=checkpointer)
        config = {"recursion_limit": 10}
    """
