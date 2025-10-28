"""Human-in-the-Loop ReAct 에이전트용 예제 도구 모듈

이 모듈은 웹 검색 기능을 제공하는 기본 도구를 포함합니다.
Tavily 검색 엔진을 사용하는 간단한 예제로 구성되어 있습니다.

주요 구성 요소:
• search - 웹 검색 도구 (Tavily 기반)
• TOOLS - 에이전트가 사용할 도구 목록

사용 예:
    from react_agent_hitl.tools import TOOLS

    # 그래프에 도구 바인딩
    model_with_tools = model.bind_tools(TOOLS)

참고:
    이 도구들은 시작을 위한 무료 예제입니다.
    프로덕션 환경에서는 더 강력하고 특화된 도구를 구현하는 것을 권장합니다.
"""

from collections.abc import Callable
from typing import Any

from langgraph.runtime import get_runtime

from react_agent_hitl.context import Context


async def search(query: str) -> dict[str, Any] | None:
    """일반 웹 검색을 수행하는 도구 함수

    이 함수는 Tavily 검색 엔진을 사용하여 웹 검색을 수행합니다.
    Tavily는 포괄적이고 정확하며 신뢰할 수 있는 검색 결과를 제공하도록 설계되었으며,
    특히 최신 이벤트나 현재 사건에 대한 질문에 유용합니다.

    동작 흐름:
    1. Runtime 컨텍스트에서 검색 설정 가져오기
    2. 최대 검색 결과 개수 확인
    3. 시뮬레이션된 검색 결과 반환 (예제)

    Args:
        query (str): 검색할 쿼리 문자열

    Returns:
        dict[str, Any] | None: 검색 결과 딕셔너리
            - query: 원본 검색 쿼리
            - max_search_results: 최대 검색 결과 개수
            - results: 검색 결과 (현재는 시뮬레이션)

    참고:
        - 실제 프로덕션 환경에서는 Tavily API를 호출하도록 구현해야 합니다
        - Runtime[Context]를 통해 사용자별 검색 설정에 접근합니다
    """
    runtime = get_runtime(Context)
    return {
        "query": query,
        "max_search_results": runtime.context.max_search_results,
        "results": f"Simulated search results for '{query}'",
    }


# 에이전트가 사용할 도구 목록
# LangGraph 그래프에서 model.bind_tools(TOOLS)로 바인딩하여 사용
TOOLS: list[Callable[..., Any]] = [search]
