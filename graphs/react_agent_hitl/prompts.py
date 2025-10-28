"""Human-in-the-Loop ReAct 에이전트의 프롬프트 템플릿

이 모듈은 HITL(Human-in-the-Loop) ReAct 에이전트가 사용하는 시스템 프롬프트를 정의합니다.
프롬프트는 에이전트의 행동과 성격을 결정하며, 시스템 시간과 같은 동적 정보를 포함할 수 있습니다.

주요 구성 요소:
• SYSTEM_PROMPT - 에이전트의 기본 페르소나 및 시스템 정보를 정의하는 템플릿

사용 예:
    from graphs.react_agent_hitl.prompts import SYSTEM_PROMPT

    # 시스템 시간을 포함한 프롬프트 생성
    formatted_prompt = SYSTEM_PROMPT.format(system_time=datetime.now().isoformat())

참고:
    - 프롬프트 텍스트는 LLM이 이해할 수 있도록 영어로 유지됩니다
    - 템플릿 변수는 Python str.format() 문법을 사용합니다
    - HITL 에이전트는 이 프롬프트를 기반으로 사용자와 상호작용합니다
"""

# 에이전트 시스템 프롬프트 템플릿
# LLM이 사용할 프롬프트이므로 영어로 유지됨
# {system_time} 변수는 런타임에 현재 시스템 시간으로 치환됩니다
SYSTEM_PROMPT = """You are a helpful AI assistant.

System time: {system_time}"""
