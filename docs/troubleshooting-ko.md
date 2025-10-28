# 문제 해결 가이드

이 문서는 Open LangGraph를 사용하는 동안 발생할 수 있는 일반적인 문제와 해결 방법을 다룹니다.

## 목차

- [데이터베이스 문제](#데이터베이스-문제)
- [그래프 실행 문제](#그래프-실행-문제)
- [스트리밍 문제](#스트리밍-문제)
- [인증 문제](#인증-문제)
- [환경 설정 문제](#환경-설정-문제)

---

## 데이터베이스 문제

### 1. 데이터베이스 연결 실패

**증상:**
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**원인:**
- PostgreSQL 서버가 실행되지 않음
- 잘못된 데이터베이스 연결 정보
- 방화벽 또는 네트워크 문제

**해결 방법:**

1. PostgreSQL이 실행 중인지 확인:
```bash
# Docker로 실행하는 경우
docker compose ps postgres

# 실행되지 않은 경우 시작
docker compose up postgres -d
```

2. 데이터베이스 연결 정보 확인:
```bash
# .env 파일 확인
cat .env | grep DATABASE_URL

# 올바른 형식: postgresql+asyncpg://user:password@host:port/database
```

3. 데이터베이스 접속 테스트:
```bash
# psql로 직접 연결 테스트
psql postgresql://open_langgraph_user:open_langgraph_password@localhost:5432/open_langgraph_db
```

**예방법:**
- `.env.example`을 참고하여 올바른 연결 문자열 사용
- Docker Compose로 데이터베이스를 관리하여 일관성 유지
- 헬스 체크 엔드포인트(`/health`)로 주기적 모니터링

---

### 2. 마이그레이션 오류

**증상:**
```
alembic.util.exc.CommandError: Can't locate revision identified by 'xxx'
```

**원인:**
- 마이그레이션 파일 누락 또는 손상
- 데이터베이스와 마이그레이션 버전 불일치
- 가상 환경이 활성화되지 않음

**해결 방법:**

1. 현재 마이그레이션 상태 확인:
```bash
# 가상 환경 활성화 (중요!)
source .venv/bin/activate

# 현재 버전 확인
python3 scripts/migrate.py current

# 마이그레이션 이력 확인
python3 scripts/migrate.py history
```

2. 마이그레이션 재적용:
```bash
# 최신 버전으로 업그레이드
python3 scripts/migrate.py upgrade
```

3. 개발 환경에서 데이터베이스 리셋 (주의: 모든 데이터 삭제):
```bash
python3 scripts/migrate.py reset
```

4. 마이그레이션 파일이 손상된 경우:
```bash
# 마이그레이션 파일 확인
ls -la alembic/versions/

# Git에서 복원
git checkout -- alembic/versions/
```

**예방법:**
- 항상 가상 환경을 활성화한 후 마이그레이션 실행
- 마이그레이션 파일을 Git으로 버전 관리
- Docker 사용 시 자동 마이그레이션 활용
- 프로덕션 적용 전 스테이징에서 테스트

---

### 3. 체크포인터 초기화 실패

**증상:**
```
RuntimeError: Checkpointer setup failed
```

**원인:**
- LangGraph 테이블이 생성되지 않음
- 데이터베이스 권한 부족
- URL 형식 불일치 (postgresql:// vs postgresql+asyncpg://)

**해결 방법:**

1. 데이터베이스 권한 확인:
```sql
-- psql로 접속하여 확인
\du open_langgraph_user

-- 필요한 권한: CREATEDB, CREATE TABLE
```

2. LangGraph 테이블 수동 생성:
```python
# Python 인터프리터에서 실행
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import AsyncPostgresStore

# 연결 문자열 (psycopg 형식)
conn_string = "postgresql://open_langgraph_user:open_langgraph_password@localhost:5432/open_langgraph_db"

# 테이블 생성
import asyncio
async def setup():
    async with AsyncPostgresSaver.from_conn_string(conn_string) as saver:
        await saver.setup()
    async with AsyncPostgresStore.from_conn_string(conn_string) as store:
        await store.setup()

asyncio.run(setup())
```

3. 서버 재시작:
```bash
# Docker
docker compose restart open-langgraph

# 로컬 개발
uvicorn src.agent_server.main:app --reload
```

**예방법:**
- 초기 설정 시 마이그레이션 스크립트 실행
- 데이터베이스 사용자에게 충분한 권한 부여
- `DatabaseManager`가 자동으로 `.setup()` 호출하도록 구현됨

---

## 그래프 실행 문제

### 1. 그래프 로딩 실패

**증상:**
```
ValueError: Graph 'my_agent' not found in registry
```

**원인:**
- `open_langgraph.json`에 그래프가 등록되지 않음
- 그래프 파일 경로 오류
- 그래프 모듈에 `graph` 변수 미정의

**해결 방법:**

1. `open_langgraph.json` 확인:
```json
{
  "graphs": {
    "my_agent": "./graphs/my_agent.py:graph"
  }
}
```

2. 그래프 파일이 존재하는지 확인:
```bash
ls -la graphs/my_agent.py
```

3. 그래프가 올바르게 정의되었는지 확인:
```python
# graphs/my_agent.py
from langgraph.graph import StateGraph

workflow = StateGraph(MyState)
# ... 노드 및 엣지 정의

# 반드시 'graph' 변수로 export
graph = workflow.compile()
```

4. 그래프 수동 테스트:
```python
# Python 인터프리터에서
from graphs.my_agent import graph
print(graph)  # 정상적으로 로드되는지 확인
```

**예방법:**
- 새 그래프 생성 시 예제(`graphs/react_agent/`)를 참고
- 그래프 등록 후 서버 재시작
- 단위 테스트로 그래프 로딩 검증

---

### 2. 인터럽트 동작 안 함

**증상:**
- `interrupt()` 호출 후에도 그래프가 계속 실행됨
- HITL(Human-in-the-Loop) 기능이 작동하지 않음

**원인:**
- 그래프가 컴파일 시 체크포인터 없이 컴파일됨
- 인터럽트 조건이 잘못 설정됨
- 클라이언트가 인터럽트 상태를 확인하지 않음

**해결 방법:**

1. 체크포인터가 설정되었는지 확인:
```python
# 서비스에서 그래프 실행 시 config에 checkpointer 포함 확인
config = {
    "configurable": {
        "thread_id": thread_id,
        "checkpoint_id": checkpoint_id
    }
}

# LangGraphService가 자동으로 체크포인터를 주입함
```

2. 인터럽트 조건 확인:
```python
# 노드에서 인터럽트 호출
from langgraph.types import interrupt

def approval_node(state):
    # 사용자 승인이 필요한 경우
    user_input = interrupt("Approve this action?")
    # 재개 시 user_input에 값이 전달됨
    return {"approved": user_input}
```

3. 스레드 상태 확인:
```bash
# API로 현재 상태 확인
curl http://localhost:8000/threads/{thread_id}/state
```

4. 인터럽트 재개:
```python
# 클라이언트에서 업데이트 전송
import requests

response = requests.post(
    f"http://localhost:8000/threads/{thread_id}/runs",
    json={
        "assistant_id": assistant_id,
        "input": {"approval": True}  # 인터럽트 응답
    }
)
```

**예방법:**
- `graphs/react_agent_hitl/` 예제 참고
- 인터럽트가 있는 그래프는 항상 체크포인터 사용
- 클라이언트에서 `next` 필드로 인터럽트 상태 확인

---

### 3. 그래프 무한 루프

**증상:**
- 그래프 실행이 종료되지 않음
- 타임아웃 오류 발생

**원인:**
- 순환 엣지에 종료 조건 없음
- `END` 노드로 향하는 경로 없음
- 조건부 엣지 로직 오류

**해결 방법:**

1. 그래프 구조 시각화:
```python
# 그래프를 Mermaid 형식으로 출력
from langraph.graph import StateGraph

print(graph.get_graph().draw_mermaid())
```

2. 종료 조건 추가:
```python
from langgraph.graph import END

def should_continue(state):
    # 최대 반복 횟수 설정
    if state.get("iterations", 0) > 10:
        return END
    return "next_node"

workflow.add_conditional_edges(
    "my_node",
    should_continue,
    {END: END, "next_node": "next_node"}
)
```

3. 실행 제한 설정:
```python
# 최대 스텝 수 제한
config = {
    "recursion_limit": 50  # 기본값: 25
}

result = await graph.ainvoke(input, config)
```

**예방법:**
- 모든 순환 경로에 명확한 종료 조건 설정
- 그래프 설계 시 상태 다이어그램 작성
- 단위 테스트로 다양한 시나리오 검증
- 재귀 제한을 적절히 설정

---

## 스트리밍 문제

### 1. SSE 연결 끊김

**증상:**
- 스트리밍 중 연결이 갑자기 종료됨
- 클라이언트에서 `EventSource` 에러 발생

**원인:**
- 네트워크 불안정
- 프록시/로드 밸런서 타임아웃
- 서버 오류로 스트림 중단

**해결 방법:**

1. 재연결 로직 구현 (클라이언트):
```javascript
const eventSource = new EventSource(`http://localhost:8000/threads/${threadId}/runs/${runId}/stream`);

eventSource.onerror = (error) => {
  console.error('SSE error:', error);

  // 자동 재연결 (EventSource는 기본적으로 재연결 시도)
  // Last-Event-ID를 통해 이어받기 가능
};

eventSource.addEventListener('end', () => {
  eventSource.close();
});
```

2. 이벤트 저장소에서 재생:
```bash
# 특정 이벤트 ID 이후부터 스트리밍
curl "http://localhost:8000/threads/{thread_id}/runs/{run_id}/stream?after_event_id=123"
```

3. 서버 로그 확인:
```bash
# Docker 로그
docker compose logs -f open-langgraph

# 오류 메시지 확인
```

**예방법:**
- 클라이언트에서 재연결 로직 구현
- `Last-Event-ID` 헤더 활용
- 프록시 타임아웃 설정 증가 (예: nginx `proxy_read_timeout`)
- EventStore의 자동 정리 간격 조정

---

### 2. 이벤트 누락

**증상:**
- 일부 이벤트가 클라이언트에 도착하지 않음
- 스트림이 불완전함

**원인:**
- 네트워크 지연으로 일부 이벤트 손실
- 이벤트 저장 실패
- 클라이언트의 버퍼 오버플로우

**해결 방법:**

1. 이벤트 저장소 확인:
```sql
-- 데이터베이스에서 이벤트 조회
SELECT * FROM sse_events
WHERE run_id = 'your-run-id'
ORDER BY sequence_number;
```

2. 완료 후 전체 이벤트 다시 받기:
```bash
# 처음부터 모든 이벤트 재생
curl "http://localhost:8000/threads/{thread_id}/runs/{run_id}/stream"
```

3. 이벤트 순서 검증 (클라이언트):
```javascript
let lastSequence = -1;

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);

  // 순서 번호 확인
  if (data.sequence !== lastSequence + 1) {
    console.warn('Event sequence gap detected');
    // 재연결 또는 재생 로직
  }

  lastSequence = data.sequence;
};
```

**예방법:**
- EventStore를 통한 영구 저장 활용
- 클라이언트에서 순서 번호 검증
- 완료 후 전체 이벤트 재조회로 무결성 확인
- 중요한 데이터는 최종 상태 조회로 이중 검증

---

### 3. 재연결 실패

**증상:**
- 연결이 끊긴 후 재연결 시 404 오류
- 이전 이벤트를 이어받지 못함

**원인:**
- 이벤트가 이미 삭제됨 (정리 작업)
- 잘못된 run_id 또는 thread_id
- 이벤트 저장소 오류

**해결 방법:**

1. Run 상태 확인:
```bash
# Run이 아직 존재하는지 확인
curl http://localhost:8000/threads/{thread_id}/runs/{run_id}
```

2. 이벤트 보존 기간 확인:
```python
# src/agent_server/services/event_store.py
# EVENT_RETENTION_HOURS 설정 확인 (기본: 24시간)
```

3. 새로운 스트림 시작:
```bash
# 이벤트가 삭제된 경우, 새 run 생성
curl -X POST http://localhost:8000/threads/{thread_id}/runs \
  -H "Content-Type: application/json" \
  -d '{"assistant_id": "your-assistant-id"}'
```

**예방법:**
- 이벤트 보존 기간을 적절히 설정
- 중요한 실행 결과는 별도 저장
- 재연결 시도 전 run 상태 확인
- 타임아웃된 경우 새 run 생성

---

## 인증 문제

### 1. 토큰 검증 실패

**증상:**
```
401 Unauthorized: Invalid authentication credentials
```

**원인:**
- 잘못된 또는 만료된 토큰
- Authorization 헤더 형식 오류
- 인증 타입 불일치

**해결 방법:**

1. 인증 타입 확인:
```bash
# .env 파일 확인
cat .env | grep AUTH_TYPE

# noop: 인증 없음 (개발용)
# custom: 커스텀 인증
```

2. 개발 시 인증 비활성화:
```bash
# .env에서 설정
AUTH_TYPE=noop
```

3. 커스텀 인증 사용 시 토큰 형식 확인:
```bash
# 올바른 헤더 형식
curl -H "Authorization: Bearer your-token" http://localhost:8000/assistants
```

4. `auth.py`의 인증 로직 확인:
```python
# auth.py
@auth.authenticate
async def authenticate(authorization: str | None) -> Auth.types.MinimalUserDict:
    # 토큰 검증 로직 확인
    # 디버그 로그 추가
    print(f"Received token: {authorization}")
    ...
```

**예방법:**
- 개발 환경에서는 `AUTH_TYPE=noop` 사용
- 프로덕션에서는 안전한 토큰 관리
- 토큰 만료 시간 설정 및 갱신 로직 구현
- 인증 실패 시 명확한 에러 메시지 반환

---

### 2. 권한 오류

**증상:**
```
403 Forbidden: Access denied
```

**원인:**
- 사용자가 리소스에 대한 권한 없음
- `@auth.on` 데코레이터 설정 오류
- 멀티테넌트 격리 실패

**해결 방법:**

1. 사용자 컨텍스트 확인:
```python
# 디버깅: 현재 사용자 정보 출력
from src.agent_server.core.auth import get_current_user

user = await get_current_user(request)
print(f"User: {user}")
```

2. `auth.py`의 권한 로직 확인:
```python
@auth.on.threads.read
async def authorize_thread_read(
    ctx: Auth.types.AuthContext,
    thread_id: str
) -> bool:
    # 권한 검증 로직 확인
    # 디버그 로그
    print(f"User {ctx.user['user_id']} accessing thread {thread_id}")
    ...
```

3. 리소스 소유권 확인:
```sql
-- 데이터베이스에서 확인
SELECT * FROM thread_metadata WHERE thread_id = 'your-thread-id';
```

**예방법:**
- 모든 리소스에 소유자 정보 저장
- `authorize()` 함수에서 자동으로 사용자별 필터링
- 권한 테스트 케이스 작성
- 멀티테넌트 격리를 데이터베이스 레벨에서 강제

---

### 3. 멀티테넌트 격리 문제

**증상:**
- 다른 사용자의 데이터가 보임
- 데이터 누출 또는 혼재

**원인:**
- 사용자 컨텍스트 주입 누락
- 데이터베이스 쿼리에 사용자 필터 누락
- LangGraph config에 user_id 미포함

**해결 방법:**

1. Config에 사용자 정보 확인:
```python
# LangGraph 실행 시 config 확인
config = {
    "configurable": {
        "thread_id": thread_id,
        "user_id": user.user_id  # 반드시 포함
    }
}
```

2. 데이터베이스 쿼리 필터링:
```python
# 모든 쿼리에 사용자 필터 적용
query = select(ThreadMetadata).where(
    ThreadMetadata.user_id == user.user_id
)
```

3. `inject_user_context()` 사용:
```python
from src.agent_server.services.langgraph_service import inject_user_context

# 사용자 컨텍스트 자동 주입
config = inject_user_context(base_config, user)
```

4. 체크포인터/스토어 격리 확인:
```python
# LangGraph는 config의 user_id로 자동 격리
# 하지만 metadata 테이블은 수동 필터링 필요
```

**예방법:**
- 모든 API 엔드포인트에서 `get_current_user()` 의존성 사용
- 데이터베이스 쿼리에 항상 user_id 필터 적용
- `inject_user_context()` 유틸리티 함수 활용
- 통합 테스트로 격리 검증 (서로 다른 사용자로 테스트)

---

## 환경 설정 문제

### 1. 환경 변수 미설정

**증상:**
```
KeyError: 'DATABASE_URL'
pydantic.error_wrappers.ValidationError: field required
```

**원인:**
- `.env` 파일 누락 또는 미로드
- 필수 환경 변수 미설정

**해결 방법:**

1. `.env` 파일 생성:
```bash
# .env.example을 복사하여 시작
cp .env.example .env

# 필수 값 설정
vim .env
```

2. 필수 환경 변수 확인:
```bash
# 최소 필수 항목
DATABASE_URL=postgresql+asyncpg://open_langgraph_user:open_langgraph_password@localhost:5432/open_langgraph_db
OPENAI_API_KEY=your-openai-api-key
AUTH_TYPE=noop  # 또는 custom
```

3. 환경 변수 로드 확인:
```python
# Python에서 테스트
import os
from dotenv import load_dotenv

load_dotenv()
print(os.getenv('DATABASE_URL'))
```

4. Docker 사용 시:
```yaml
# docker-compose.yml에서 env_file 확인
services:
  open-langgraph:
    env_file:
      - .env
```

**예방법:**
- 프로젝트 시작 시 `.env.example` 참고
- `.env`를 `.gitignore`에 추가 (이미 포함됨)
- README에 필수 환경 변수 문서화
- 시작 스크립트에서 환경 변수 검증

---

### 2. open_langgraph.json 오류

**증상:**
```
json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes
ValueError: Invalid graph configuration
```

**원인:**
- JSON 문법 오류
- 잘못된 파일 경로
- 필수 필드 누락

**해결 방법:**

1. JSON 문법 검증:
```bash
# jq로 검증
cat open_langgraph.json | jq .

# Python으로 검증
python3 -c "import json; json.load(open('open_langgraph.json'))"
```

2. 올바른 형식 확인:
```json
{
  "graphs": {
    "agent_id": "./graphs/agent_file.py:graph"
  },
  "auth": {
    "path": "./auth.py:auth"
  },
  "env": ".env",
  "dependencies": [
    "langchain-openai",
    "langchain-community"
  ]
}
```

3. 파일 경로 확인:
```bash
# 상대 경로가 올바른지 확인
ls -la ./graphs/agent_file.py
ls -la ./auth.py
```

4. 스키마 검증:
```python
# LangGraphService가 자동으로 검증
# 서버 시작 로그 확인
```

**예방법:**
- JSON 편집 시 린터 사용 (VSCode, IDE)
- 예제 파일 참고하여 작성
- 파일 경로는 open_langgraph.json 기준 상대 경로 사용
- Git으로 버전 관리하여 변경 추적

---

### 3. 의존성 충돌

**증상:**
```
pip._vendor.resolvelib.resolvers.ResolutionImpossible
ModuleNotFoundError: No module named 'xxx'
```

**원인:**
- 패키지 버전 충돌
- 호환되지 않는 의존성
- 가상 환경 문제

**해결 방법:**

1. 가상 환경 재생성:
```bash
# 기존 환경 삭제
rm -rf .venv

# 새로 설치
uv install
```

2. 의존성 버전 확인:
```bash
# 현재 설치된 패키지
uv pip list

# pyproject.toml 확인
cat pyproject.toml
```

3. 특정 패키지 재설치:
```bash
# 문제가 있는 패키지 재설치
uv pip install --force-reinstall langchain-openai
```

4. 캐시 정리:
```bash
# pip 캐시 삭제
uv cache clean
```

5. Docker 사용 시:
```bash
# 이미지 재빌드 (캐시 없이)
docker compose build --no-cache open-langgraph
```

**예방법:**
- `uv`를 사용하여 의존성 관리 (빠르고 안정적)
- `pyproject.toml`에 버전 범위 명시
- 가상 환경을 항상 활성화한 상태로 작업
- 정기적으로 `uv pip check`로 충돌 확인
- 프로덕션 배포 전 깨끗한 환경에서 테스트

---

## 일반적인 디버깅 팁

### 로그 확인

```bash
# Docker 로그
docker compose logs -f open-langgraph

# 특정 시간대 로그
docker compose logs --since 10m open-langgraph

# 로컬 개발 시 uvicorn 로그
# 기본적으로 콘솔에 출력됨
```

### 헬스 체크

```bash
# 전체 시스템 상태 확인
curl http://localhost:8000/health

# 응답 예시:
# {
#   "status": "healthy",
#   "database": "ok",
#   "checkpointer": "ok",
#   "store": "ok"
# }
```

### 데이터베이스 직접 접근

```bash
# PostgreSQL 접속
docker compose exec postgres psql -U open_langgraph_user -d open_langgraph_db

# 테이블 확인
\dt

# 스키마 확인
\d table_name
```

### Python 디버거 사용

```python
# 코드에 브레이크포인트 추가
import pdb; pdb.set_trace()

# 또는 Python 3.7+
breakpoint()
```

### 테스트로 격리된 환경 확인

```bash
# 특정 기능만 테스트
uv run pytest tests/test_api/test_threads.py -v

# 실패한 테스트만 재실행
uv run pytest --lf

# 커버리지와 함께 테스트
uv run pytest --cov=src --cov-report=html
```

---

## 추가 지원

문제가 해결되지 않는 경우:

1. **GitHub Issues**: [프로젝트 저장소](https://github.com/your-repo/open-langgraph)에서 이슈 검색 또는 생성
2. **문서**: `docs/` 디렉토리의 다른 가이드 참고
3. **로그 수집**: 문제 보고 시 관련 로그 및 설정 파일 첨부
4. **재현 단계**: 문제를 재현할 수 있는 최소한의 단계 제공

---

**마지막 업데이트**: 2025-10-27
