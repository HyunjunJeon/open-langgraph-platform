"""서브그래프 에이전트 (Subgraph Agent)

이 모듈은 다른 그래프를 노드로 포함하는 서브그래프 구성(composition) 패턴을 보여주는
최소한의 위임 그래프를 제공합니다.

서브그래프 구성 패턴:
• 기존 그래프(react_agent)를 새로운 그래프의 노드로 재사용
• 그래프 중첩(nesting)을 통한 복잡한 워크플로우 구축
• 위임(delegation) 패턴으로 모듈화된 에이전트 구조 구현

주요 구성 요소:
• subgraph_agent 노드 - react_agent 그래프를 서브그래프로 실행
• no_stream 노드 - 스트리밍 비활성화 태그를 사용한 LLM 호출

사용 예:
    from subgraph_agent import graph

    # 서브그래프를 포함한 복합 그래프 실행
    result = await graph.ainvoke({"messages": [...]})
"""

from subgraph_agent.graph import graph

__all__ = ["graph"]
