"""Human-in-the-Loop을 지원하는 ReAct 에이전트 그래프

이 모듈은 도구 실행 전 사람의 승인을 받는 ReAct 에이전트를 정의합니다.
기본 react_agent와 동일한 추론-행동 패턴을 따르지만,
도구를 실행하기 전에 인터럽트(interrupt)를 통해 사람의 개입을 요청합니다.

주요 차이점 (react_agent와 비교):
• human_approval 노드 추가: 도구 실행 전 승인 단계
• 인터럽트 메커니즘: LangGraph의 interrupt() 함수로 실행 중단
• 사용자 응답 처리:
  - accept: 도구 실행 승인
  - edit: 도구 인자 수정 후 실행
  - response: 도구 취소 후 사용자 메시지로 대체
  - ignore: 도구 실행 취소

HITL 패턴 동작 흐름:
1. call_model: LLM이 도구 호출 결정
2. human_approval: 인터럽트로 사용자 승인 대기
3. 사용자 응답에 따라 분기:
   - tools: 승인 시 도구 실행
   - call_model: 수정/대체 메시지와 함께 재실행
   - END: 취소 시 종료

사용 예:
    # open_langgraph.json에 등록
    {
      "graphs": {
        "react_agent_hitl": "./graphs/react_agent_hitl/__init__.py:graph"
      }
    }

    # 클라이언트에서 인터럽트 처리
    # 1. 실행 시작 (정상 실행과 동일)
    # 2. interrupt 이벤트 수신 (action_request 포함)
    # 3. 사용자 승인/수정/취소 결정
    # 4. 업데이트 전송으로 실행 재개
"""

from react_agent_hitl.graph import graph

__all__ = ["graph"]
