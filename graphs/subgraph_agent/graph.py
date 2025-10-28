"""서브그래프 구성을 시연하는 메인 그래프 정의

이 모듈은 `react_agent.graph`를 서브그래프 노드로 위임하는 최소한의 메인 그래프를 구현합니다.
서브그래프 패턴은 복잡한 에이전트를 재사용 가능한 모듈식 구성 요소로 분해할 수 있게 해줍니다.

서브그래프 구성 패턴:
1. 메인 그래프가 입력을 받아 전처리 노드에서 처리
2. 전처리된 상태를 서브그래프 노드로 전달
3. 서브그래프(react_agent)가 독립적으로 실행
4. 서브그래프 결과가 메인 그래프로 반환
5. 메인 그래프가 최종 처리 및 응답

주요 구성 요소:
• no_stream - langsmith:nostream 태그로 LLM 호출하는 전처리 노드
• subgraph_agent - react_agent.graph를 서브그래프로 실행하는 노드
• graph - 컴파일된 메인 StateGraph 인스턴스

그래프 구조:
    __start__ → no_stream → subgraph_agent → __end__

서브그래프의 장점:
- 재사용성: 기존 그래프를 노드로 삽입하여 재사용
- 모듈성: 복잡한 로직을 독립적인 서브그래프로 분리
- 유지보수성: 각 서브그래프를 독립적으로 개발 및 테스트 가능
- 구성 가능성: 여러 서브그래프를 조합하여 복잡한 워크플로우 구축

사용 요구사항:
- react_agent 그래프와 동일한 State 구조 사용
- Runtime[Context]를 통해 설정 공유
- 도구 호출을 지원하는 채팅 모델 필요
"""

from datetime import UTC, datetime
from typing import cast

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph
from langgraph.runtime import Runtime
from react_agent import graph as react_graph
from react_agent.context import Context
from react_agent.state import InputState, State
from react_agent.utils import load_chat_model

# ---------------------------------------------------------------------------
# 메인 그래프 빌더 초기화
# ---------------------------------------------------------------------------
# react_agent와 동일한 State, InputState, Context를 사용하여
# 서브그래프와 메인 그래프 간의 원활한 데이터 흐름을 보장합니다.
builder = StateGraph(State, input_schema=InputState, context_schema=Context)


# ---------------------------------------------------------------------------
# 노드 함수: 전처리 노드 (스트리밍 비활성화)
# ---------------------------------------------------------------------------


async def no_stream(
    state: State, runtime: Runtime[Context]
) -> dict[str, list[AIMessage]]:
    """langsmith:nostream 태그와 함께 LLM을 호출하는 전처리 노드

    이 함수는 서브그래프로 전달하기 전에 LLM을 호출하여 초기 응답을 생성합니다.
    langsmith:nostream 태그를 사용하여 이 특정 호출에 대한 스트리밍을 비활성화하며,
    LangSmith 추적 시스템에서 스트리밍 없이 한 번에 전체 응답을 기록합니다.

    동작 흐름:
    1. Runtime[Context]에서 모델 설정 및 시스템 프롬프트 로드
    2. langsmith:nostream 태그와 함께 채팅 모델 초기화
    3. 현재 시각을 시스템 프롬프트에 포맷팅
    4. 시스템 메시지와 대화 이력을 결합하여 LLM 호출
    5. LLM 응답을 메시지 목록에 추가하여 반환

    Args:
        state (State): 현재 대화 상태 (메시지 이력 포함)
        runtime (Runtime[Context]): 런타임 컨텍스트 (모델 설정, 시스템 프롬프트 등)

    Returns:
        dict[str, list[AIMessage]]: LLM 응답 메시지를 담은 딕셔너리
            - "messages" 키로 AIMessage 목록 반환
            - add_messages 리듀서가 기존 메시지에 병합

    참고:
        - 이 노드는 서브그래프 실행 전 초기 컨텍스트를 설정하는 역할
        - langsmith:nostream 태그는 LangSmith 대시보드에서 스트리밍 이벤트 없이
          단일 완료된 응답으로 표시되도록 함
        - 서브그래프(react_agent)는 이 응답을 포함한 전체 상태를 받음
    """
    # langsmith:nostream 태그와 함께 모델 초기화
    # 이 태그는 LangSmith 추적 시스템에서 이 호출을 스트리밍하지 않음을 나타냄
    model = load_chat_model(runtime.context.model).with_config(
        config={"tags": ["langsmith:nostream"]}
    )

    # 시스템 프롬프트 포맷팅
    # 현재 UTC 시각을 ISO 형식으로 프롬프트에 삽입하여 시간 컨텍스트 제공
    system_message = runtime.context.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )

    # LLM 호출 및 응답 받기
    # 시스템 메시지와 기존 대화 이력을 결합하여 전달
    response = cast(
        "AIMessage",
        await model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
    )

    # 응답 메시지를 리스트로 반환하여 기존 메시지에 추가
    # add_messages 리듀서가 이를 state.messages에 병합
    return {"messages": [response]}


# ---------------------------------------------------------------------------
# 그래프 구성: 노드 추가 및 엣지 연결
# ---------------------------------------------------------------------------

# 서브그래프 노드 추가
# react_graph를 "subgraph_agent" 노드로 직접 추가
# LangGraph는 컴파일된 그래프를 노드로 사용할 수 있으며,
# 서브그래프는 메인 그래프의 상태를 받아 실행 후 업데이트된 상태를 반환합니다.
builder.add_node("subgraph_agent", react_graph)

# 전처리 노드 추가
# no_stream 함수를 "no_stream" 노드로 추가
# 서브그래프 실행 전 초기 LLM 호출을 수행합니다.
builder.add_node("no_stream", no_stream)

# 엣지 연결: 선형 실행 흐름 정의
# 1. 시작 → no_stream: 항상 전처리 노드를 먼저 거침
builder.add_edge("__start__", "no_stream")

# 2. no_stream → subgraph_agent: 전처리 후 서브그래프로 전달
#    no_stream 노드의 응답이 메시지에 추가된 상태로 서브그래프 실행
builder.add_edge("no_stream", "subgraph_agent")

# 3. subgraph_agent → 종료: 서브그래프 완료 후 메인 그래프 종료
#    서브그래프(react_agent)의 최종 상태가 메인 그래프의 최종 상태가 됨
builder.add_edge("subgraph_agent", "__end__")

# ---------------------------------------------------------------------------
# 그래프 컴파일
# ---------------------------------------------------------------------------
# 빌더를 컴파일하여 실행 가능한 그래프 인스턴스 생성
# name="Subgraph Agent"는 LangSmith 추적 및 디버깅에서 사용되는 식별자
graph = builder.compile(name="Subgraph Agent")
