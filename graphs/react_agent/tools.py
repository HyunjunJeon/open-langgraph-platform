"""ReAct 에이전트용 예제 도구 모음

이 모듈은 웹 검색 및 스크래핑 기능을 제공하는 기본 도구들을 정의합니다.
LangGraph의 도구 호출(tool calling) 패턴과 함께 사용되어 에이전트가
외부 정보에 접근하고 작업을 수행할 수 있게 합니다.

주요 도구:
• search - Tavily 검색 엔진을 통한 웹 검색 (시뮬레이션)

참고:
    이 도구들은 시작을 위한 예제로 제공됩니다.
    프로덕션 환경에서는 요구사항에 맞는 더 강력하고 전문화된 도구를
    구현하는 것을 권장합니다.

사용 예:
    from react_agent.tools import TOOLS

    # LangGraph 그래프에 도구 바인딩
    model = ChatOpenAI(model="gpt-4").bind_tools(TOOLS)
"""

from collections.abc import Callable
from typing import Any

from langgraph.runtime import get_runtime

from react_agent.context import Context


async def search(query: str) -> dict[str, Any] | None:
    """웹 검색을 수행하고 검색 결과를 반환

    이 함수는 Tavily 검색 엔진을 사용하여 웹 검색을 시뮬레이션합니다.
    Tavily는 포괄적이고 정확하며 신뢰할 수 있는 검색 결과를 제공하도록
    설계되었으며, 특히 최신 이벤트나 현재 정보에 대한 질문에 유용합니다.

    동작 흐름:
    1. LangGraph Runtime에서 Context 추출
    2. Context에서 max_search_results 설정 값 가져오기
    3. 검색 쿼리와 설정을 포함한 결과 딕셔너리 반환

    Args:
        query (str): 검색할 질의어 또는 키워드

    Returns:
        dict[str, Any] | None: 검색 결과 딕셔너리
            - query (str): 입력받은 검색 쿼리
            - max_search_results (int): 최대 검색 결과 개수 설정값
            - results (str): 시뮬레이션된 검색 결과 문자열

    참고:
        - 현재는 시뮬레이션 모드로 실제 검색은 수행하지 않습니다
        - 실제 Tavily API를 사용하려면 API 키 설정 및 클라이언트 통합 필요
        - Runtime[Context] 패턴을 통해 사용자별 설정에 접근합니다

    사용 예:
        results = await search("LangGraph 최신 기능")
        print(results["results"])
    """
    # LangGraph Runtime에서 사용자 컨텍스트 가져오기
    runtime = get_runtime(Context)

    # 검색 결과 딕셔너리 생성 (시뮬레이션)
    return {
        "query": query,
        "max_search_results": runtime.context.max_search_results,
        "results": f"Simulated search results for '{query}'",
    }


# ---------------------------------------------------------------------------
# 도구 목록 (LangGraph 도구 바인딩용)
# ---------------------------------------------------------------------------

# 에이전트가 사용할 수 있는 모든 도구 함수들의 리스트
# LangGraph에서 model.bind_tools(TOOLS)로 LLM에 바인딩됩니다
TOOLS: list[Callable[..., Any]] = [search]
