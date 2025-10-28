"""ReAct 패턴을 활용한 추론-실행 에이전트 그래프 정의

이 모듈은 LangGraph 기반의 ReAct(Reasoning and Action) 에이전트를 구현합니다.
ReAct 패턴은 LLM이 추론(Reasoning)과 도구 실행(Action)을 반복하며 문제를 해결하는 방식입니다.

ReAct 패턴 동작 흐름:
1. 사용자 질문 입력
2. LLM이 추론하고 필요한 도구 선택
3. 선택된 도구 실행
4. 도구 실행 결과를 LLM에 전달
5. 2-4 반복하며 최종 답변 도출

주요 구성 요소:
• call_model - LLM 호출 노드 (추론 및 도구 선택)
• tools - 도구 실행 노드 (ToolNode)
• route_model_output - 조건부 라우팅 함수 (계속 실행 or 종료)
• graph - 컴파일된 StateGraph 인스턴스

그래프 구조:
    __start__ → call_model ⇄ tools
                     ↓
                 __end__

사용 요구사항:
- 도구 호출(tool calling)을 지원하는 채팅 모델 필요
- Runtime[Context]를 통해 모델 설정 및 시스템 프롬프트 주입
"""

from datetime import UTC, datetime
from typing import Literal, cast

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime

from react_agent.context import Context
from react_agent.state import InputState, State
from react_agent.tools import TOOLS
from react_agent.utils import load_chat_model

# ---------------------------------------------------------------------------
# 노드 함수: LLM 호출 및 추론
# ---------------------------------------------------------------------------


async def call_model(
    state: State, runtime: Runtime[Context]
) -> dict[str, list[AIMessage]]:
    """ReAct 에이전트의 핵심 LLM 호출 노드 - 추론 및 도구 선택 수행

    이 함수는 ReAct 패턴의 "Reasoning(추론)" 단계를 담당합니다.
    현재 대화 상태를 기반으로 LLM을 호출하여 다음 행동(도구 호출 또는 최종 답변)을 결정합니다.

    동작 흐름:
    1. Runtime Context에서 모델 정보 추출 및 도구 바인딩
    2. 시스템 프롬프트 포맷팅 (현재 시간 주입)
    3. LLM 호출 (시스템 메시지 + 대화 히스토리)
    4. 응답 처리 (최대 스텝 도달 시 종료 처리)
    5. 상태에 새 메시지 추가하여 반환

    Args:
        state (State): 현재 대화 상태 (메시지 히스토리, 스텝 카운터 등 포함)
        runtime (Runtime[Context]): 런타임 컨텍스트 (모델 설정, 시스템 프롬프트 포함)

    Returns:
        dict[str, list[AIMessage]]: 상태 업데이트용 딕셔너리
            - "messages": LLM의 응답 메시지 (도구 호출 정보 포함 가능)

    참고:
        - LLM이 도구 호출을 결정하면 response.tool_calls에 도구 정보가 포함됨
        - 최대 스텝에 도달했는데 여전히 도구 호출을 시도하면 에러 메시지 반환
        - bind_tools()를 통해 LLM이 사용 가능한 도구 목록을 인지하게 함
    """
    # 런타임 컨텍스트에서 모델 설정을 가져와 도구와 바인딩
    # 모델이 어떤 도구를 사용할 수 있는지 알려줌 (도구 스키마 주입)
    model = load_chat_model(runtime.context.model).bind_tools(TOOLS)

    # 시스템 프롬프트 포맷팅 - 현재 시간을 주입하여 에이전트가 시간 정보를 인지
    # 시스템 프롬프트는 에이전트의 역할과 행동 방식을 정의함
    system_message = runtime.context.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )

    # LLM 호출 - 시스템 메시지와 대화 히스토리를 입력으로 전달
    # LLM은 컨텍스트를 분석하고 다음 행동(도구 호출 or 답변)을 결정
    response = cast(
        "AIMessage",
        await model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
    )

    # 최대 스텝 도달 체크: 무한 루프 방지를 위한 안전 장치
    # 마지막 스텝인데도 LLM이 여전히 도구를 호출하려 하면 강제 종료
    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }

    # LLM 응답을 상태에 추가하여 반환
    # 다음 노드(route_model_output)가 이 메시지를 기반으로 라우팅 결정
    return {"messages": [response]}


# ---------------------------------------------------------------------------
# 그래프 구성: StateGraph 빌더 초기화 및 노드 추가
# ---------------------------------------------------------------------------

# ReAct 에이전트 그래프 빌더 생성
# - State: 그래프 실행 중 유지되는 상태 스키마 (메시지, 스텝 등)
# - InputState: 사용자 입력 스키마 (초기 메시지만 포함)
# - Context: 런타임 컨텍스트 스키마 (모델 설정, 시스템 프롬프트 등)
builder = StateGraph(State, input_schema=InputState, context_schema=Context)

# 노드 1: call_model - LLM 호출 및 추론 노드
# LLM이 대화 컨텍스트를 분석하고 다음 행동(도구 호출 or 답변) 결정
builder.add_node(call_model)

# 노드 2: tools - 도구 실행 노드 (LangGraph의 ToolNode 활용)
# LLM이 선택한 도구를 실제로 실행하고 결과를 상태에 추가
# ToolNode는 tool_calls를 자동으로 파싱하여 해당 도구를 호출함
builder.add_node("tools", ToolNode(TOOLS))

# ---------------------------------------------------------------------------
# 엣지 정의: 그래프의 실행 흐름 구성
# ---------------------------------------------------------------------------

# 진입점 설정: 그래프 시작 시 call_model 노드부터 실행
# __start__는 LangGraph의 특수 노드로 그래프의 시작점을 의미
builder.add_edge("__start__", "call_model")


def route_model_output(state: State) -> Literal["__end__", "tools"]:
    """LLM 출력을 기반으로 다음 노드 결정 - ReAct 패턴의 조건부 라우팅

    이 함수는 ReAct 패턴의 핵심 분기 로직을 담당합니다.
    LLM의 마지막 응답을 확인하여 도구 호출이 필요한지(Action) 또는 최종 답변인지(End) 판단합니다.

    라우팅 로직:
    - 도구 호출 있음 → "tools" 노드로 이동 (도구 실행)
    - 도구 호출 없음 → "__end__" 노드로 이동 (그래프 종료)

    Args:
        state (State): 현재 대화 상태 (메시지 히스토리 포함)

    Returns:
        Literal["__end__", "tools"]: 다음에 실행할 노드 이름
            - "__end__": 그래프 종료 (최종 답변 완료)
            - "tools": 도구 실행 노드로 이동

    Raises:
        ValueError: 마지막 메시지가 AIMessage가 아닌 경우
            (그래프 구조상 call_model 다음은 항상 AIMessage여야 함)

    참고:
        - ReAct 패턴의 "Thought → Action → Observation" 사이클을 구현
        - 도구 호출이 있으면 tools 노드에서 실행 후 다시 call_model로 복귀
        - 도구 호출이 없으면 LLM이 최종 답변을 완성했다고 판단하여 종료
    """
    # 상태에서 가장 최근 메시지(LLM 응답) 추출
    last_message = state.messages[-1]

    # 타입 안전성 검증: call_model 노드 다음은 항상 AIMessage여야 함
    if not isinstance(last_message, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
        )

    # 도구 호출이 없으면 그래프 종료
    # LLM이 최종 답변을 텍스트로만 반환했다는 의미 (더 이상 도구 실행 불필요)
    if not last_message.tool_calls:
        return "__end__"

    # 도구 호출이 있으면 tools 노드로 이동하여 실행
    # ReAct 패턴의 "Action" 단계 진입
    return "tools"


# call_model → (조건부 분기) → __end__ or tools
# call_model 노드 실행 후 route_model_output 함수로 다음 노드를 동적으로 결정
# ReAct 패턴의 핵심: LLM 응답에 따라 도구 실행 or 종료를 선택
builder.add_conditional_edges(
    "call_model",
    # call_model 완료 후 route_model_output 함수 실행하여 다음 노드 결정
    # 반환값에 따라 "__end__" 또는 "tools" 노드로 분기
    route_model_output,
)

# tools → call_model (고정 엣지)
# 도구 실행 완료 후 항상 call_model로 복귀하여 결과 분석
# ReAct 사이클 구현: Action(도구 실행) → Observation(결과) → Thought(다시 LLM 추론)
builder.add_edge("tools", "call_model")

# ---------------------------------------------------------------------------
# 그래프 컴파일: 실행 가능한 그래프로 변환
# ---------------------------------------------------------------------------

# StateGraph 빌더를 실행 가능한 CompiledGraph로 컴파일
# name="ReAct Agent"는 LangSmith 트레이싱 등에서 식별자로 사용됨
# 컴파일 후 graph는 open_langgraph.json에서 참조되어 HTTP API로 노출됨
graph = builder.compile(name="ReAct Agent")
