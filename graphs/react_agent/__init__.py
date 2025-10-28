"""ReAct 에이전트 그래프 패키지

이 패키지는 Reasoning(추론)과 Acting(행동)을 반복하는 ReAct 패턴 기반의
에이전트 그래프를 제공합니다. 사용자의 요청을 처리하기 위해 추론 단계에서
필요한 도구를 결정하고, 행동 단계에서 해당 도구를 실행하는 간단한 루프를
구현합니다.

주요 특징:
• ReAct 패턴 - 추론(Reason) → 행동(Act) → 관찰(Observe) 사이클
• 도구 호출 - LLM이 결정한 도구를 자동으로 실행
• 상태 관리 - LangGraph StateGraph를 통한 대화 상태 유지
• 간단한 구조 - 복잡한 중단(interrupt) 없이 연속 실행

사용 예:
    from graphs.react_agent import graph

    # 그래프는 open_langgraph.json에 등록하여 사용
    # "react_agent": "./graphs/react_agent/__init__.py:graph"

내보내기:
    graph: 컴파일된 ReAct 에이전트 그래프 인스턴스
"""

from react_agent.graph import graph

__all__ = ["graph"]
