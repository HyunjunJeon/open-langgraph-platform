# 관찰성을 위한 Langfuse 통합

Open LangGraph는 LangGraph 실행에 대한 상세한 추적 및 관찰성을 제공하기 위해 [Langfuse](https://langfuse.com/)의 플러그 앤 플레이 통합 기능을 포함하고 있습니다. 활성화되면 모든 그래프 실행이 추적되고 로그가 Langfuse 프로젝트로 전송됩니다.

## Langfuse 활성화하기

Langfuse를 활성화하려면 몇 가지 환경 변수를 구성해야 합니다. 권장 방법은 프로젝트 루트에 `.env` 파일을 생성하고 다음 키-값 쌍을 추가하는 것입니다.

1. **통합 활성화**: `.env` 파일에 다음 변수를 `true`로 설정합니다.

    ```env
    LANGFUSE_LOGGING=true
    ```

2. **Langfuse 자격 증명 구성**: Langfuse 프로젝트 자격 증명도 제공해야 합니다. 이는 Langfuse 프로젝트 설정에서 찾을 수 있습니다. [Langfuse Cloud](https://cloud.langfuse.com) 또는 자체 호스팅 인스턴스를 사용할 수 있습니다.

    ```env
    LANGFUSE_PUBLIC_KEY="pk-lf-..."
    LANGFUSE_SECRET_KEY="sk-lf-..."
    LANGFUSE_HOST="https://cloud.langfuse.com" # 또는 자체 호스팅 인스턴스 URL
    ```

3. **Langfuse 패키지 설치**: 이 통합 기능을 사용하려면 `langfuse` Python 패키지가 설치되어 있어야 합니다.

    ```bash
    pip install langfuse
    ```

    `LANGFUSE_LOGGING`이 활성화되어 있지만 패키지가 설치되지 않은 경우, Open LangGraph는 경고를 로그로 남기고 추적 없이 계속 실행됩니다.

## 추적되는 메타데이터

이 통합 기능은 제로 구성(zero-config)으로 설계되었습니다. 활성화되면 모든 추적과 함께 다음 메타데이터를 자동으로 캡처하고 전송합니다:

- **세션 ID**: 대화의 `thread_id`가 자동으로 `langfuse_session_id`로 사용됩니다. 이는 동일한 스레드의 모든 실행을 Langfuse의 단일 세션으로 그룹화합니다.
- **사용자 ID**: `user.identity`가 `langfuse_user_id`로 사용되어 사용자별로 추적을 필터링할 수 있습니다.
- **태그**: 각 추적에 컨텍스트를 제공하기 위해 기본 태그 세트가 자동으로 추가됩니다:
  - `open_langgraph_run`: Open LangGraph 서버에서 발생한 추적임을 식별합니다.
  - `run:<run_id>`: 실행의 특정 ID입니다.
  - `thread:<thread_id>`: 스레드 ID입니다.
  - `user:<user_id>`: 사용자 ID입니다.

이러한 메타데이터가 풍부한 추적 기능을 통해 Langfuse UI에서 문제를 쉽게 디버그하고, 성능을 분석하고, 에이전트가 어떻게 사용되는지 이해할 수 있습니다.

- **중요**: `.env` 파일을 변경한 후에는 서버를 재시작해야 합니다.

## 향후 개선 사항

- **추적 ID 상관관계**: 디버깅을 더욱 쉽게 하기 위해, Langfuse `trace_id`를 Open LangGraph `run_id`와 동일하게 설정할 계획입니다. 이를 통해 시스템의 실행과 Langfuse의 해당 추적 간에 직접적인 일대일 매핑이 가능해집니다.

Langfuse와 그 기능에 대한 더 자세한 정보는 [공식 Langfuse 문서](https://langfuse.com/docs)를 참조하세요.
