# 실전 예제 가이드

이 문서는 Open LangGraph를 사용하여 다양한 시나리오를 구현하는 실전 예제를 제공합니다. 각 예제는 코드, 설명, 실행 결과, 그리고 주의사항을 포함합니다.

## 목차

1. [기본 에이전트 실행](#1-기본-에이전트-실행)
2. [HITL 에이전트 사용](#2-hitl-에이전트-사용)
3. [SSE 스트리밍](#3-sse-스트리밍)
4. [커스텀 그래프 작성](#4-커스텀-그래프-작성)
5. [Store 활용](#5-store-활용)
6. [인증 커스터마이징](#6-인증-커스터마이징)

---

## 1. 기본 에이전트 실행

가장 기본적인 에이전트 실행 워크플로우입니다. 스레드를 생성하고, 어시스턴트를 선택한 후, 실행을 시작하는 과정을 다룹니다.

### 1.1 스레드 생성

```python
import httpx

# API 엔드포인트
BASE_URL = "http://localhost:8000"

async def create_thread():
    """새로운 대화 스레드를 생성합니다."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/threads",
            json={
                "metadata": {
                    "user_name": "김철수",
                    "session_type": "demo"
                }
            }
        )
        thread = response.json()
        print(f"스레드 생성됨: {thread['thread_id']}")
        return thread["thread_id"]
```

**설명:**
- `POST /threads` 엔드포인트를 호출하여 새로운 대화 스레드를 생성합니다.
- `metadata`는 선택사항이며, 스레드에 대한 추가 정보를 저장할 수 있습니다.
- 반환된 `thread_id`는 이후 모든 대화에서 사용됩니다.

**실행 결과:**
```json
{
  "thread_id": "thread_abc123xyz",
  "created_at": 1698765432,
  "metadata": {
    "user_name": "김철수",
    "session_type": "demo"
  }
}
```

**주의사항:**
- 스레드는 영구적으로 저장되므로, 개발 중에는 주기적으로 정리가 필요할 수 있습니다.
- `thread_id`는 UUID 형식으로 생성되며, 클라이언트에서 안전하게 저장해야 합니다.

### 1.2 어시스턴트 선택

```python
async def list_assistants():
    """사용 가능한 어시스턴트 목록을 조회합니다."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/assistants")
        assistants = response.json()

        print("사용 가능한 어시스턴트:")
        for assistant in assistants:
            print(f"- {assistant['name']} (ID: {assistant['assistant_id']})")
            print(f"  설명: {assistant.get('description', 'N/A')}")

        return assistants

async def get_assistant(assistant_id: str):
    """특정 어시스턴트의 상세 정보를 조회합니다."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/assistants/{assistant_id}")
        assistant = response.json()
        print(f"어시스턴트: {assistant['name']}")
        print(f"그래프 ID: {assistant['graph_id']}")
        return assistant
```

**설명:**
- `GET /assistants` 엔드포인트로 전체 어시스턴트 목록을 조회합니다.
- 각 어시스턴트는 특정 그래프와 연결되어 있으며, 고유한 기능을 제공합니다.
- `assistant_id` 또는 `graph_id`를 사용하여 특정 어시스턴트를 선택할 수 있습니다.

**실행 결과:**
```
사용 가능한 어시스턴트:
- Weather Agent (ID: asst_weather_agent)
  설명: Provides weather information for any location
- ReAct Agent (ID: asst_react_agent)
  설명: General-purpose agent with tool calling capabilities
```

### 1.3 실행 시작 및 결과 확인

```python
async def run_agent(thread_id: str, assistant_id: str, user_message: str):
    """에이전트 실행을 시작하고 결과를 확인합니다."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. 실행 생성
        response = await client.post(
            f"{BASE_URL}/threads/{thread_id}/runs",
            json={
                "assistant_id": assistant_id,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": user_message
                        }
                    ]
                }
            }
        )
        run = response.json()
        run_id = run["run_id"]
        print(f"실행 시작: {run_id}")

        # 2. 실행 완료 대기
        import asyncio
        while True:
            response = await client.get(
                f"{BASE_URL}/threads/{thread_id}/runs/{run_id}"
            )
            run_status = response.json()
            status = run_status["status"]
            print(f"상태: {status}")

            if status in ["success", "error", "interrupted"]:
                break

            await asyncio.sleep(1)

        # 3. 결과 조회
        if status == "success":
            print("\n결과:")
            for message in run_status.get("output", {}).get("messages", []):
                if message["role"] == "assistant":
                    print(f"Assistant: {message['content']}")

        return run_status

# 사용 예제
async def main():
    thread_id = await create_thread()
    assistants = await list_assistants()

    # weather_agent 사용
    result = await run_agent(
        thread_id=thread_id,
        assistant_id="weather_agent",
        user_message="서울의 날씨를 알려주세요"
    )

# 실행
import asyncio
asyncio.run(main())
```

**설명:**
- `POST /threads/{thread_id}/runs`로 실행을 시작합니다.
- `input.messages`에 사용자 메시지를 포함합니다.
- 실행은 비동기로 처리되므로, 폴링을 통해 상태를 확인합니다.
- 완료 후 `output.messages`에서 에이전트의 응답을 확인할 수 있습니다.

**실행 결과:**
```
실행 시작: run_abc123xyz
상태: running
상태: running
상태: success

결과:
Assistant: 서울의 현재 날씨는 맑음이며, 기온은 15°C입니다.
```

**주의사항:**
- 폴링 간격은 1초로 설정했지만, 실제 운영 환경에서는 조정이 필요할 수 있습니다.
- 타임아웃 설정을 통해 무한 대기를 방지해야 합니다.
- `interrupted` 상태는 HITL 에이전트에서 사용됩니다 (다음 섹션 참조).

---

## 2. HITL 에이전트 사용

Human-in-the-Loop (HITL) 에이전트는 실행 중에 사용자 승인을 요청할 수 있습니다. 이를 통해 중요한 작업을 실행하기 전에 사용자 확인을 받을 수 있습니다.

### 2.1 인터럽트 처리

```python
async def run_hitl_agent(thread_id: str, user_message: str):
    """HITL 에이전트를 실행하고 인터럽트를 처리합니다."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. 실행 시작
        response = await client.post(
            f"{BASE_URL}/threads/{thread_id}/runs",
            json={
                "assistant_id": "react_agent_hitl",  # HITL 에이전트
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": user_message
                        }
                    ]
                }
            }
        )
        run = response.json()
        run_id = run["run_id"]
        print(f"실행 시작: {run_id}")

        # 2. 상태 확인 - 인터럽트 대기
        import asyncio
        while True:
            response = await client.get(
                f"{BASE_URL}/threads/{thread_id}/runs/{run_id}"
            )
            run_status = response.json()
            status = run_status["status"]

            if status == "interrupted":
                print("\n인터럽트 발생!")
                print(f"승인 요청: {run_status.get('interrupt_info', {})}")
                break
            elif status in ["success", "error"]:
                print(f"실행 완료: {status}")
                return run_status

            await asyncio.sleep(1)

        return run_status

# 사용 예제
async def main():
    thread_id = await create_thread()

    result = await run_hitl_agent(
        thread_id=thread_id,
        user_message="weather_app 프로젝트의 모든 파일을 삭제해줘"
    )

    print("\n도구 호출 정보:")
    print(result.get("interrupt_info"))

asyncio.run(main())
```

**설명:**
- HITL 에이전트는 위험한 작업(파일 삭제, API 호출 등)을 수행하기 전에 `interrupted` 상태로 전환됩니다.
- `interrupt_info`에는 승인이 필요한 작업의 상세 정보가 포함됩니다.
- 사용자는 작업을 승인하거나 거부, 또는 수정할 수 있습니다.

**실행 결과:**
```
실행 시작: run_def456uvw

인터럽트 발생!
승인 요청: {
  "tool_name": "delete_files",
  "arguments": {
    "path": "weather_app",
    "recursive": true
  },
  "reason": "User approval required for destructive operation"
}

도구 호출 정보:
{
  "tool_name": "delete_files",
  "arguments": {...}
}
```

### 2.2 도구 승인/수정

```python
async def approve_tool_call(thread_id: str, run_id: str, approve: bool = True):
    """도구 호출을 승인합니다."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 승인
        response = await client.post(
            f"{BASE_URL}/threads/{thread_id}/runs/{run_id}",
            json={
                "input": None,  # 수정 없이 승인
                "command": "resume"
            }
        )
        print("도구 호출이 승인되었습니다.")
        return response.json()

async def modify_tool_call(thread_id: str, run_id: str, modified_args: dict):
    """도구 호출 인자를 수정합니다."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 수정된 인자로 재개
        response = await client.post(
            f"{BASE_URL}/threads/{thread_id}/runs/{run_id}",
            json={
                "input": modified_args,
                "command": "update"
            }
        )
        print("도구 호출이 수정되었습니다.")
        return response.json()

async def reject_tool_call(thread_id: str, run_id: str):
    """도구 호출을 거부합니다."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/threads/{thread_id}/runs/{run_id}",
            json={
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": "작업을 취소합니다."
                        }
                    ]
                },
                "command": "resume"
            }
        )
        print("도구 호출이 거부되었습니다.")
        return response.json()

# 사용 예제
async def main():
    thread_id = await create_thread()

    # HITL 에이전트 실행
    result = await run_hitl_agent(
        thread_id=thread_id,
        user_message="weather_app 프로젝트의 모든 파일을 삭제해줘"
    )

    # 인터럽트 발생 시
    if result["status"] == "interrupted":
        # 옵션 1: 그대로 승인
        # await approve_tool_call(thread_id, result["run_id"])

        # 옵션 2: 인자 수정 (일부 파일만 삭제)
        await modify_tool_call(
            thread_id,
            result["run_id"],
            {
                "path": "weather_app/temp",  # 경로 수정
                "recursive": False
            }
        )

        # 옵션 3: 거부
        # await reject_tool_call(thread_id, result["run_id"])

asyncio.run(main())
```

**설명:**
- `command: "resume"` - 실행을 재개합니다 (승인).
- `command: "update"` - 상태를 업데이트하고 재개합니다 (수정).
- 거부하려면 새로운 사용자 메시지를 `input`에 포함시킵니다.

**주의사항:**
- 인터럽트 후 재개하지 않으면 실행은 `interrupted` 상태로 유지됩니다.
- 재개 시에는 반드시 동일한 `thread_id`와 `run_id`를 사용해야 합니다.
- LangGraph는 인터럽트 시점의 상태를 자동으로 저장하므로, 정확한 지점부터 재개됩니다.

### 2.3 재개 실행

```python
async def wait_for_completion(thread_id: str, run_id: str):
    """실행이 완료될 때까지 대기합니다."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        import asyncio

        while True:
            response = await client.get(
                f"{BASE_URL}/threads/{thread_id}/runs/{run_id}"
            )
            run_status = response.json()
            status = run_status["status"]

            print(f"상태: {status}")

            if status == "success":
                print("\n최종 결과:")
                for message in run_status.get("output", {}).get("messages", []):
                    if message["role"] == "assistant":
                        print(f"Assistant: {message['content']}")
                break
            elif status == "error":
                print(f"오류 발생: {run_status.get('error')}")
                break
            elif status == "interrupted":
                print("여전히 인터럽트 상태입니다. 승인이 필요합니다.")
                break

            await asyncio.sleep(1)

        return run_status

# 전체 워크플로우
async def full_hitl_workflow():
    thread_id = await create_thread()

    # 1. HITL 실행 시작
    result = await run_hitl_agent(
        thread_id=thread_id,
        user_message="config.json 파일의 debug 값을 true로 변경해줘"
    )

    # 2. 인터럽트 처리
    if result["status"] == "interrupted":
        print("\n사용자 승인 대기 중...")

        # 사용자 입력 시뮬레이션
        user_approval = input("승인하시겠습니까? (y/n): ")

        if user_approval.lower() == "y":
            await approve_tool_call(thread_id, result["run_id"])

            # 3. 완료 대기
            await wait_for_completion(thread_id, result["run_id"])
        else:
            await reject_tool_call(thread_id, result["run_id"])
            print("작업이 취소되었습니다.")

asyncio.run(full_hitl_workflow())
```

**실행 결과:**
```
실행 시작: run_ghi789rst

인터럽트 발생!
승인 요청: {
  "tool_name": "edit_file",
  "arguments": {
    "file": "config.json",
    "changes": {"debug": true}
  }
}

사용자 승인 대기 중...
승인하시겠습니까? (y/n): y
도구 호출이 승인되었습니다.
상태: running
상태: success

최종 결과:
Assistant: config.json 파일의 debug 값을 true로 변경했습니다.
```

---

## 3. SSE 스트리밍

Server-Sent Events (SSE)를 사용하면 에이전트의 실행 과정을 실시간으로 스트리밍할 수 있습니다. 이는 긴 실행 시간이 소요되는 작업에서 사용자 경험을 개선합니다.

### 3.1 스트리밍 연결

```python
import httpx
import json

async def stream_agent_run(thread_id: str, assistant_id: str, user_message: str):
    """에이전트 실행을 스트리밍합니다."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 스트리밍 모드로 실행
        async with client.stream(
            "POST",
            f"{BASE_URL}/threads/{thread_id}/runs/stream",
            json={
                "assistant_id": assistant_id,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": user_message
                        }
                    ]
                }
            }
        ) as response:
            print("스트리밍 시작...\n")

            async for line in response.aiter_lines():
                # SSE 형식: "data: {json}\n"
                if line.startswith("data: "):
                    data = line[6:]  # "data: " 제거

                    if data == "[DONE]":
                        print("\n스트리밍 완료")
                        break

                    try:
                        event = json.loads(data)
                        handle_stream_event(event)
                    except json.JSONDecodeError:
                        continue

def handle_stream_event(event: dict):
    """스트림 이벤트를 처리합니다."""
    event_type = event.get("event")

    if event_type == "metadata":
        print(f"[메타데이터] Run ID: {event['data']['run_id']}")

    elif event_type == "messages/partial":
        # 메시지 스트리밍
        for msg in event["data"]:
            if msg["role"] == "assistant":
                print(msg["content"], end="", flush=True)

    elif event_type == "messages/complete":
        print()  # 줄바꿈

    elif event_type == "agent":
        # 에이전트 상태 변경
        print(f"\n[에이전트] {event['data'].get('action', 'processing')}")

    elif event_type == "tool":
        # 도구 호출
        tool_info = event["data"]
        print(f"\n[도구 호출] {tool_info.get('name')}")
        print(f"  인자: {tool_info.get('input')}")

    elif event_type == "error":
        print(f"\n[오류] {event['data'].get('message')}")

# 사용 예제
async def main():
    thread_id = await create_thread()

    await stream_agent_run(
        thread_id=thread_id,
        assistant_id="react_agent",
        user_message="Python으로 피보나치 수열을 계산하는 함수를 작성해줘"
    )

asyncio.run(main())
```

**설명:**
- `/threads/{thread_id}/runs/stream` 엔드포인트를 사용합니다.
- SSE 형식은 `data: {json}\n`으로 전송됩니다.
- 각 이벤트는 `event` 타입과 `data` 페이로드를 포함합니다.
- `[DONE]` 메시지는 스트리밍의 종료를 나타냅니다.

**실행 결과:**
```
스트리밍 시작...

[메타데이터] Run ID: run_jkl012mno

[에이전트] processing
피보나치 수열을 계산하는 함수를 작성하겠습니다.

[도구 호출] python_repl
  인자: {'code': 'def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)'}

함수가 작성되었습니다. 재귀 방식으로 구현했습니다.

스트리밍 완료
```

### 3.2 이벤트 처리

```python
from typing import Callable, Dict
from enum import Enum

class EventType(str, Enum):
    """스트림 이벤트 타입"""
    METADATA = "metadata"
    MESSAGE_PARTIAL = "messages/partial"
    MESSAGE_COMPLETE = "messages/complete"
    AGENT = "agent"
    TOOL = "tool"
    ERROR = "error"
    INTERRUPT = "interrupt"

class StreamEventHandler:
    """스트림 이벤트를 처리하는 핸들러 클래스"""

    def __init__(self):
        self.handlers: Dict[EventType, Callable] = {
            EventType.METADATA: self.on_metadata,
            EventType.MESSAGE_PARTIAL: self.on_message_partial,
            EventType.MESSAGE_COMPLETE: self.on_message_complete,
            EventType.AGENT: self.on_agent,
            EventType.TOOL: self.on_tool,
            EventType.ERROR: self.on_error,
            EventType.INTERRUPT: self.on_interrupt,
        }
        self.run_id = None
        self.message_buffer = ""

    def handle(self, event: dict):
        """이벤트를 적절한 핸들러로 라우팅합니다."""
        event_type = event.get("event")
        handler = self.handlers.get(event_type)

        if handler:
            handler(event["data"])
        else:
            print(f"알 수 없는 이벤트: {event_type}")

    def on_metadata(self, data: dict):
        """메타데이터 이벤트 처리"""
        self.run_id = data.get("run_id")
        print(f"[시작] Run ID: {self.run_id}")
        print(f"Thread ID: {data.get('thread_id')}")

    def on_message_partial(self, data: list):
        """부분 메시지 이벤트 처리 (스트리밍 중)"""
        for msg in data:
            if msg["role"] == "assistant":
                content = msg["content"]
                # 이전 버퍼와의 차이만 출력
                if content.startswith(self.message_buffer):
                    new_content = content[len(self.message_buffer):]
                    print(new_content, end="", flush=True)
                    self.message_buffer = content
                else:
                    print(content, end="", flush=True)
                    self.message_buffer = content

    def on_message_complete(self, data: list):
        """완전한 메시지 이벤트 처리"""
        print()  # 줄바꿈
        self.message_buffer = ""

    def on_agent(self, data: dict):
        """에이전트 상태 이벤트 처리"""
        action = data.get("action", "processing")
        print(f"\n[에이전트] 상태: {action}")

    def on_tool(self, data: dict):
        """도구 호출 이벤트 처리"""
        tool_name = data.get("name")
        tool_input = data.get("input")
        print(f"\n[도구] {tool_name} 호출")
        print(f"  입력: {json.dumps(tool_input, ensure_ascii=False, indent=2)}")

    def on_error(self, data: dict):
        """오류 이벤트 처리"""
        error_msg = data.get("message")
        print(f"\n[오류] {error_msg}")

    def on_interrupt(self, data: dict):
        """인터럽트 이벤트 처리"""
        print(f"\n[인터럽트] 사용자 승인 필요")
        print(f"  상세: {json.dumps(data, ensure_ascii=False, indent=2)}")

async def stream_with_handler(thread_id: str, assistant_id: str, user_message: str):
    """핸들러를 사용하여 스트리밍합니다."""
    handler = StreamEventHandler()

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            f"{BASE_URL}/threads/{thread_id}/runs/stream",
            json={
                "assistant_id": assistant_id,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": user_message
                        }
                    ]
                }
            }
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]

                    if data == "[DONE]":
                        print("\n\n[완료] 스트리밍 종료")
                        break

                    try:
                        event = json.loads(data)
                        handler.handle(event)
                    except json.JSONDecodeError:
                        continue

# 사용 예제
async def main():
    thread_id = await create_thread()

    await stream_with_handler(
        thread_id=thread_id,
        assistant_id="react_agent",
        user_message="서울의 날씨를 확인하고, 그 정보를 JSON 파일로 저장해줘"
    )

asyncio.run(main())
```

**설명:**
- `StreamEventHandler` 클래스는 각 이벤트 타입별로 전용 핸들러를 제공합니다.
- `message_buffer`를 사용하여 중복 출력을 방지합니다.
- 확장 가능한 구조로 새로운 이벤트 타입을 쉽게 추가할 수 있습니다.

### 3.3 재연결 처리

```python
import asyncio
from datetime import datetime

class StreamReconnectHandler:
    """스트림 재연결을 처리하는 클래스"""

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.last_event_id = None

    async def stream_with_retry(
        self,
        thread_id: str,
        run_id: str,
        on_event: Callable[[dict], None]
    ):
        """재연결 로직이 포함된 스트리밍"""
        retries = 0

        while retries <= self.max_retries:
            try:
                await self._stream_once(thread_id, run_id, on_event)
                # 정상 완료
                break
            except (httpx.ReadTimeout, httpx.ConnectError) as e:
                retries += 1
                if retries > self.max_retries:
                    print(f"\n[오류] 최대 재시도 횟수 초과: {e}")
                    raise

                print(f"\n[재연결] 연결이 끊어졌습니다. {self.retry_delay}초 후 재시도... ({retries}/{self.max_retries})")
                await asyncio.sleep(self.retry_delay)

    async def _stream_once(
        self,
        thread_id: str,
        run_id: str,
        on_event: Callable[[dict], None]
    ):
        """단일 스트림 연결"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 마지막 이벤트 이후부터 재개
            url = f"{BASE_URL}/threads/{thread_id}/runs/{run_id}/stream"
            if self.last_event_id:
                url += f"?after={self.last_event_id}"

            async with client.stream("GET", url) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]

                        if data == "[DONE]":
                            return

                        try:
                            event = json.loads(data)

                            # 이벤트 ID 추적
                            if "id" in event:
                                self.last_event_id = event["id"]

                            on_event(event)
                        except json.JSONDecodeError:
                            continue

# 사용 예제
async def main():
    thread_id = await create_thread()

    # 실행 시작 (비스트리밍)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/threads/{thread_id}/runs",
            json={
                "assistant_id": "react_agent",
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": "복잡한 데이터 분석을 수행해줘"
                        }
                    ]
                }
            }
        )
        run = response.json()
        run_id = run["run_id"]

    # 재연결 핸들러로 스트리밍
    reconnect_handler = StreamReconnectHandler(max_retries=5, retry_delay=2.0)
    event_handler = StreamEventHandler()

    try:
        await reconnect_handler.stream_with_retry(
            thread_id=thread_id,
            run_id=run_id,
            on_event=event_handler.handle
        )
    except Exception as e:
        print(f"스트리밍 실패: {e}")

asyncio.run(main())
```

**설명:**
- `last_event_id`를 추적하여 재연결 시 누락된 이벤트를 방지합니다.
- `?after={event_id}` 쿼리 파라미터로 특정 시점부터 재개합니다.
- 지수 백오프를 추가하면 더 안정적인 재연결이 가능합니다.

**주의사항:**
- 이벤트 재생(replay) 기능은 일정 기간 동안만 유효합니다 (기본 1시간).
- 네트워크 불안정 환경에서는 재시도 횟수와 지연 시간을 조정해야 합니다.
- 실시간 사용자 경험을 위해 재연결 중임을 UI에 표시하는 것이 좋습니다.

---

## 4. 커스텀 그래프 작성

LangGraph를 사용하여 자신만의 에이전트 그래프를 작성할 수 있습니다. 이 섹션에서는 간단한 번역 에이전트를 만들어봅니다.

### 4.1 StateGraph 정의

```python
# graphs/translator_agent.py

from typing import TypedDict, Annotated
from operator import add
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

# 1. 상태 정의
class TranslatorState(TypedDict):
    """번역 에이전트의 상태"""
    messages: Annotated[list[BaseMessage], add]
    source_language: str
    target_language: str
    translation: str

# 2. 그래프 생성
workflow = StateGraph(TranslatorState)

# 3. 노드 정의 (다음 섹션에서 구현)
workflow.add_node("detect_language", detect_language_node)
workflow.add_node("translate", translate_node)
workflow.add_node("respond", respond_node)

# 4. 엣지 정의
workflow.set_entry_point("detect_language")
workflow.add_edge("detect_language", "translate")
workflow.add_edge("translate", "respond")
workflow.add_edge("respond", END)

# 5. 컴파일
graph = workflow.compile()
```

**설명:**
- `StateGraph`는 상태 기반 그래프를 정의합니다.
- `TypedDict`로 상태의 스키마를 정의합니다.
- `Annotated[list, add]`는 메시지 리스트가 누적됨을 나타냅니다.
- 노드는 상태를 처리하는 함수이며, 엣지는 실행 흐름을 정의합니다.

### 4.2 노드 작성

```python
# graphs/translator_agent.py (계속)

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# LLM 초기화
llm = ChatOpenAI(model="gpt-4", temperature=0)

def detect_language_node(state: TranslatorState) -> TranslatorState:
    """사용자 메시지의 언어를 감지합니다."""
    messages = state["messages"]
    last_message = messages[-1]

    if isinstance(last_message, HumanMessage):
        user_text = last_message.content

        # 언어 감지 프롬프트
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Detect the language of the following text. Reply with only the language name in English."),
            ("user", "{text}")
        ])

        chain = prompt | llm
        result = chain.invoke({"text": user_text})

        detected_language = result.content.strip()

        return {
            **state,
            "source_language": detected_language
        }

    return state

def translate_node(state: TranslatorState) -> TranslatorState:
    """텍스트를 번역합니다."""
    messages = state["messages"]
    last_message = messages[-1]
    source_lang = state.get("source_language", "Unknown")
    target_lang = state.get("target_language", "English")

    if isinstance(last_message, HumanMessage):
        user_text = last_message.content

        # 번역 프롬프트
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"Translate the following text from {source_lang} to {target_lang}. Provide only the translation."),
            ("user", "{text}")
        ])

        chain = prompt | llm
        result = chain.invoke({"text": user_text})

        translation = result.content.strip()

        return {
            **state,
            "translation": translation
        }

    return state

def respond_node(state: TranslatorState) -> TranslatorState:
    """번역 결과를 응답 메시지로 추가합니다."""
    translation = state.get("translation", "")
    source_lang = state.get("source_language", "Unknown")
    target_lang = state.get("target_language", "English")

    response_message = AIMessage(
        content=f"[{source_lang} → {target_lang}]\n\n{translation}"
    )

    return {
        **state,
        "messages": [response_message]
    }
```

**설명:**
- 각 노드는 `state`를 입력받아 업데이트된 `state`를 반환합니다.
- `detect_language_node`: LLM을 사용하여 언어를 감지합니다.
- `translate_node`: LLM을 사용하여 번역을 수행합니다.
- `respond_node`: 번역 결과를 메시지 형태로 포맷팅합니다.
- 상태 업데이트 시 스프레드 연산자(`**state`)를 사용하여 기존 상태를 유지합니다.

### 4.3 Context 활용

```python
# graphs/translator_agent.py (Context 버전)

from typing import Any
from langgraph.types import Runtime
from pydantic import BaseModel, Field

# 1. Context 정의
class TranslatorContext(BaseModel):
    """번역 에이전트의 런타임 컨텍스트"""
    user_id: str = Field(description="사용자 ID")
    target_language: str = Field(default="English", description="목표 언어")
    formality: str = Field(default="neutral", description="번역 어조 (formal/neutral/casual)")
    model_name: str = Field(default="gpt-4", description="사용할 LLM 모델")

def detect_language_node_v2(
    state: TranslatorState,
    runtime: Runtime[TranslatorContext]
) -> TranslatorState:
    """Context를 활용한 언어 감지 노드"""
    # 런타임 컨텍스트 접근
    context = runtime.context
    model_name = context.model_name
    user_id = context.user_id

    # 사용자별 설정을 반영한 LLM
    llm = ChatOpenAI(model=model_name, temperature=0)

    messages = state["messages"]
    last_message = messages[-1]

    if isinstance(last_message, HumanMessage):
        user_text = last_message.content

        prompt = ChatPromptTemplate.from_messages([
            ("system", f"Detect the language of the following text for user {user_id}. Reply with only the language name in English."),
            ("user", "{text}")
        ])

        chain = prompt | llm
        result = chain.invoke({"text": user_text})

        return {
            **state,
            "source_language": result.content.strip()
        }

    return state

def translate_node_v2(
    state: TranslatorState,
    runtime: Runtime[TranslatorContext]
) -> TranslatorState:
    """Context를 활용한 번역 노드"""
    context = runtime.context
    target_lang = context.target_language
    formality = context.formality
    model_name = context.model_name

    llm = ChatOpenAI(model=model_name, temperature=0)

    messages = state["messages"]
    last_message = messages[-1]
    source_lang = state.get("source_language", "Unknown")

    if isinstance(last_message, HumanMessage):
        user_text = last_message.content

        # 어조를 반영한 번역 프롬프트
        formality_instruction = {
            "formal": "Use formal language and honorifics.",
            "neutral": "Use neutral, standard language.",
            "casual": "Use casual, conversational language."
        }.get(formality, "")

        prompt = ChatPromptTemplate.from_messages([
            ("system", f"Translate from {source_lang} to {target_lang}. {formality_instruction}"),
            ("user", "{text}")
        ])

        chain = prompt | llm
        result = chain.invoke({"text": user_text})

        return {
            **state,
            "translation": result.content.strip(),
            "target_language": target_lang
        }

    return state

# Context를 사용하는 그래프 컴파일
workflow_v2 = StateGraph(TranslatorState)
workflow_v2.add_node("detect_language", detect_language_node_v2)
workflow_v2.add_node("translate", translate_node_v2)
workflow_v2.add_node("respond", respond_node)

workflow_v2.set_entry_point("detect_language")
workflow_v2.add_edge("detect_language", "translate")
workflow_v2.add_edge("translate", "respond")
workflow_v2.add_edge("respond", END)

graph = workflow_v2.compile()
```

**설명:**
- `Runtime[Context]` 패턴을 사용하여 런타임 정보에 접근합니다.
- `Context` 클래스는 Pydantic BaseModel로 정의하여 타입 안전성을 보장합니다.
- 사용자별 설정(모델, 언어, 어조 등)을 Context를 통해 주입할 수 있습니다.

**open_langgraph.json 등록:**
```json
{
  "graphs": {
    "translator_agent": "./graphs/translator_agent.py:graph"
  }
}
```

**Context 사용 예제:**
```python
# 클라이언트에서 Context 전달
async def run_translator_with_context():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/threads/{thread_id}/runs",
            json={
                "assistant_id": "translator_agent",
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": "Hello, how are you?"
                        }
                    ]
                },
                "config": {
                    "configurable": {
                        "target_language": "Korean",
                        "formality": "formal",
                        "model_name": "gpt-4"
                    }
                }
            }
        )
```

**주의사항:**
- Context는 실행 시점에 주입되므로, 그래프 정의 시에는 기본값을 설정해야 합니다.
- Context 필드는 `config.configurable`을 통해 클라이언트에서 전달됩니다.
- 타입 안전성을 위해 Pydantic 모델을 사용하는 것을 권장합니다.

---

## 5. Store 활용

LangGraph Store는 장기 메모리를 위한 영구 저장소입니다. 대화 히스토리를 넘어 사용자별 정보, 지식 베이스 등을 저장할 수 있습니다.

### 5.1 장기 메모리 저장

```python
# 그래프 내에서 Store 사용
from langgraph.store.base import BaseStore

async def save_user_preference_node(
    state: dict,
    runtime: Runtime[Any],
    store: BaseStore
) -> dict:
    """사용자 선호도를 Store에 저장합니다."""
    user_id = runtime.context.user_id
    messages = state["messages"]
    last_message = messages[-1]

    # 사용자 메시지에서 선호도 추출
    if isinstance(last_message, HumanMessage):
        content = last_message.content

        # 예: "내 선호 언어는 한국어야" 같은 메시지 처리
        if "선호 언어" in content or "preferred language" in content.lower():
            # LLM을 사용하여 언어 추출
            llm = ChatOpenAI(model="gpt-4", temperature=0)
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Extract the language preference from the user message. Reply with only the language name."),
                ("user", "{text}")
            ])
            result = (prompt | llm).invoke({"text": content})
            preferred_language = result.content.strip()

            # Store에 저장
            await store.aput(
                namespace=("user_preferences", user_id),
                key="language",
                value={
                    "preferred_language": preferred_language,
                    "updated_at": datetime.now().isoformat()
                }
            )

            response = f"선호 언어를 '{preferred_language}'로 저장했습니다."
            return {
                **state,
                "messages": [AIMessage(content=response)]
            }

    return state

async def load_user_preference_node(
    state: dict,
    runtime: Runtime[Any],
    store: BaseStore
) -> dict:
    """Store에서 사용자 선호도를 로드합니다."""
    user_id = runtime.context.user_id

    # Store에서 조회
    item = await store.aget(
        namespace=("user_preferences", user_id),
        key="language"
    )

    if item:
        preferred_language = item.value.get("preferred_language")
        return {
            **state,
            "preferred_language": preferred_language
        }

    # 기본값
    return {
        **state,
        "preferred_language": "English"
    }
```

**설명:**
- `store.aput()`: 데이터를 저장합니다.
- `store.aget()`: 데이터를 조회합니다.
- `namespace`: 데이터를 논리적으로 그룹화합니다 (예: `("user_preferences", user_id)`).
- `key`: 네임스페이스 내의 고유 식별자입니다.

**API를 통한 Store 접근:**
```python
async def save_user_preference_via_api(user_id: str, language: str):
    """API를 통해 사용자 선호도를 저장합니다."""
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{BASE_URL}/store/items",
            json={
                "namespace": ["user_preferences", user_id],
                "key": "language",
                "value": {
                    "preferred_language": language,
                    "updated_at": datetime.now().isoformat()
                }
            }
        )
        return response.json()

async def load_user_preference_via_api(user_id: str):
    """API를 통해 사용자 선호도를 조회합니다."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/store/items",
            params={
                "namespace": ["user_preferences", user_id],
                "key": "language"
            }
        )
        return response.json()
```

### 5.2 검색 (키워드/시맨틱)

```python
# 지식 베이스 구축 및 검색
from datetime import datetime

async def build_knowledge_base():
    """지식 베이스를 구축합니다."""
    knowledge_items = [
        {
            "key": "python_basics",
            "value": {
                "title": "Python 기초",
                "content": "Python은 간결하고 읽기 쉬운 문법을 가진 프로그래밍 언어입니다.",
                "tags": ["python", "programming", "basics"],
                "created_at": datetime.now().isoformat()
            }
        },
        {
            "key": "langgraph_intro",
            "value": {
                "title": "LangGraph 소개",
                "content": "LangGraph는 상태 기반 에이전트를 구축하기 위한 프레임워크입니다.",
                "tags": ["langgraph", "agent", "framework"],
                "created_at": datetime.now().isoformat()
            }
        },
        {
            "key": "fastapi_guide",
            "value": {
                "title": "FastAPI 가이드",
                "content": "FastAPI는 빠르고 현대적인 Python 웹 프레임워크입니다.",
                "tags": ["fastapi", "web", "api"],
                "created_at": datetime.now().isoformat()
            }
        }
    ]

    async with httpx.AsyncClient() as client:
        for item in knowledge_items:
            await client.put(
                f"{BASE_URL}/store/items",
                json={
                    "namespace": ["knowledge_base", "tech"],
                    "key": item["key"],
                    "value": item["value"]
                }
            )

    print(f"{len(knowledge_items)}개의 지식 항목이 저장되었습니다.")

async def search_knowledge_base(query: str, limit: int = 5):
    """키워드 기반 지식 베이스 검색"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/store/search",
            json={
                "namespace_prefix": ["knowledge_base"],
                "query": query,
                "limit": limit
            }
        )
        results = response.json()

        print(f"\n'{query}' 검색 결과:")
        for i, result in enumerate(results.get("items", []), 1):
            value = result["value"]
            print(f"{i}. {value['title']}")
            print(f"   {value['content']}")
            print(f"   태그: {', '.join(value['tags'])}")

        return results

# 시맨틱 검색 (임베딩 기반)
async def semantic_search_knowledge_base(query: str, limit: int = 5):
    """시맨틱 검색 (벡터 유사도 기반)"""
    # OpenAI 임베딩 생성
    from langchain_openai import OpenAIEmbeddings

    embeddings = OpenAIEmbeddings()
    query_embedding = await embeddings.aembed_query(query)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/store/search",
            json={
                "namespace_prefix": ["knowledge_base"],
                "query_embedding": query_embedding,
                "limit": limit
            }
        )
        results = response.json()

        print(f"\n'{query}' 시맨틱 검색 결과:")
        for i, result in enumerate(results.get("items", []), 1):
            value = result["value"]
            score = result.get("score", 0)
            print(f"{i}. {value['title']} (유사도: {score:.2f})")
            print(f"   {value['content']}")

        return results

# 사용 예제
async def main():
    # 지식 베이스 구축
    await build_knowledge_base()

    # 키워드 검색
    await search_knowledge_base("Python")
    await search_knowledge_base("agent framework")

    # 시맨틱 검색
    await semantic_search_knowledge_base("상태 기반 에이전트를 만드는 방법")

asyncio.run(main())
```

**설명:**
- **키워드 검색**: `query` 파라미터를 사용하여 텍스트 매칭을 수행합니다.
- **시맨틱 검색**: `query_embedding` 파라미터를 사용하여 벡터 유사도 기반 검색을 수행합니다.
- `namespace_prefix`를 사용하여 특정 네임스페이스 하위를 검색할 수 있습니다.

**실행 결과:**
```
3개의 지식 항목이 저장되었습니다.

'Python' 검색 결과:
1. Python 기초
   Python은 간결하고 읽기 쉬운 문법을 가진 프로그래밍 언어입니다.
   태그: python, programming, basics

'agent framework' 검색 결과:
1. LangGraph 소개
   LangGraph는 상태 기반 에이전트를 구축하기 위한 프레임워크입니다.
   태그: langgraph, agent, framework

'상태 기반 에이전트를 만드는 방법' 시맨틱 검색 결과:
1. LangGraph 소개 (유사도: 0.89)
   LangGraph는 상태 기반 에이전트를 구축하기 위한 프레임워크입니다.
```

### 5.3 네임스페이스 관리

```python
async def manage_namespaces():
    """네임스페이스를 활용한 데이터 조직화"""

    # 1. 다양한 네임스페이스로 데이터 저장
    async with httpx.AsyncClient() as client:
        # 사용자 프로필
        await client.put(
            f"{BASE_URL}/store/items",
            json={
                "namespace": ["users", "user123", "profile"],
                "key": "info",
                "value": {
                    "name": "홍길동",
                    "email": "hong@example.com"
                }
            }
        )

        # 사용자 설정
        await client.put(
            f"{BASE_URL}/store/items",
            json={
                "namespace": ["users", "user123", "settings"],
                "key": "preferences",
                "value": {
                    "theme": "dark",
                    "language": "ko"
                }
            }
        )

        # 사용자 대화 요약
        await client.put(
            f"{BASE_URL}/store/items",
            json={
                "namespace": ["users", "user123", "conversations"],
                "key": "summary_2024_01",
                "value": {
                    "total_messages": 45,
                    "topics": ["Python", "LangGraph", "FastAPI"]
                }
            }
        )

    print("다양한 네임스페이스에 데이터가 저장되었습니다.")

async def list_namespace_items(namespace: list[str]):
    """특정 네임스페이스의 모든 항목을 조회합니다."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/store/search",
            json={
                "namespace_prefix": namespace,
                "limit": 100
            }
        )
        items = response.json().get("items", [])

        print(f"\n네임스페이스 {namespace}의 항목:")
        for item in items:
            print(f"- Key: {item['key']}")
            print(f"  Namespace: {item['namespace']}")
            print(f"  Value: {item['value']}")

        return items

async def delete_namespace_items(namespace: list[str]):
    """특정 네임스페이스의 모든 항목을 삭제합니다."""
    async with httpx.AsyncClient() as client:
        # 먼저 항목 조회
        items = await list_namespace_items(namespace)

        # 각 항목 삭제
        for item in items:
            await client.delete(
                f"{BASE_URL}/store/items",
                params={
                    "namespace": item["namespace"],
                    "key": item["key"]
                }
            )

        print(f"\n{len(items)}개 항목이 삭제되었습니다.")

# 사용 예제
async def main():
    # 네임스페이스 구조로 데이터 저장
    await manage_namespaces()

    # 사용자 전체 데이터 조회
    await list_namespace_items(["users", "user123"])

    # 특정 하위 네임스페이스만 조회
    await list_namespace_items(["users", "user123", "settings"])

    # 네임스페이스 정리
    # await delete_namespace_items(["users", "user123", "conversations"])

asyncio.run(main())
```

**설명:**
- 네임스페이스는 계층적 구조로 데이터를 조직화합니다.
- `["users", "user123", "profile"]` 형태로 명확한 구조를 만들 수 있습니다.
- `namespace_prefix`를 사용하여 하위 네임스페이스를 일괄 조회/삭제할 수 있습니다.

**실행 결과:**
```
다양한 네임스페이스에 데이터가 저장되었습니다.

네임스페이스 ['users', 'user123']의 항목:
- Key: info
  Namespace: ['users', 'user123', 'profile']
  Value: {'name': '홍길동', 'email': 'hong@example.com'}
- Key: preferences
  Namespace: ['users', 'user123', 'settings']
  Value: {'theme': 'dark', 'language': 'ko'}
- Key: summary_2024_01
  Namespace: ['users', 'user123', 'conversations']
  Value: {'total_messages': 45, 'topics': ['Python', 'LangGraph', 'FastAPI']}

네임스페이스 ['users', 'user123', 'settings']의 항목:
- Key: preferences
  Namespace: ['users', 'user123', 'settings']
  Value: {'theme': 'dark', 'language': 'ko'}
```

**주의사항:**
- 네임스페이스는 문자열 리스트로 표현됩니다.
- 깊이 제한은 없지만, 너무 깊은 구조는 관리가 어려울 수 있습니다.
- 멀티테넌트 환경에서는 네임스페이스 첫 번째 레벨을 사용자/조직 ID로 설정하는 것이 일반적입니다.

---

## 6. 인증 커스터마이징

Open LangGraph는 LangGraph SDK Auth를 사용하여 유연한 인증 시스템을 제공합니다. 커스텀 인증 로직을 구현하여 다양한 인증 방식을 지원할 수 있습니다.

### 6.1 auth.py 수정

```python
# auth.py

import os
from typing import Optional
from langgraph_sdk import Auth
from langgraph_sdk.auth.types import MinimalUserDict
import jwt
from datetime import datetime, timedelta

# Auth 인스턴스 생성
auth = Auth()

# JWT 설정
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

# 1. 인증 구현
@auth.authenticate
async def authenticate(authorization: Optional[str]) -> MinimalUserDict:
    """JWT 토큰 기반 인증"""

    # 인증 타입 확인
    auth_type = os.getenv("AUTH_TYPE", "noop")

    if auth_type == "noop":
        # 개발 모드: 모든 요청 허용
        return MinimalUserDict(
            identity="dev_user",
            display_name="Development User",
            is_authenticated=True
        )

    # JWT 인증
    if not authorization:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="Authorization header is required"
        )

    # "Bearer <token>" 형식 파싱
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid authentication scheme")
    except ValueError:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Expected 'Bearer <token>'"
        )

    # JWT 토큰 검증
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        user_id = payload.get("sub")
        if not user_id:
            raise Auth.exceptions.HTTPException(
                status_code=401,
                detail="Invalid token: missing user ID"
            )

        # 만료 시간 확인
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp) < datetime.now():
            raise Auth.exceptions.HTTPException(
                status_code=401,
                detail="Token has expired"
            )

        # 사용자 정보 반환
        return MinimalUserDict(
            identity=user_id,
            display_name=payload.get("name", user_id),
            is_authenticated=True,
            metadata={
                "email": payload.get("email"),
                "org_id": payload.get("org_id"),
                "roles": payload.get("roles", []),
                "permissions": payload.get("permissions", [])
            }
        )

    except jwt.ExpiredSignatureError:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}"
        )

# 2. 리소스별 권한 부여
@auth.on.threads.create
async def authorize_thread_create(
    metadata: dict,
    *,
    user: MinimalUserDict
) -> dict:
    """스레드 생성 시 사용자 정보를 메타데이터에 추가"""
    return {
        **metadata,
        "user_id": user["identity"],
        "org_id": user.get("metadata", {}).get("org_id"),
        "created_by": user["display_name"]
    }

@auth.on.threads.read
async def authorize_thread_read(
    thread_id: str,
    *,
    user: MinimalUserDict
) -> bool:
    """스레드 조회 권한 확인"""
    # 관리자는 모든 스레드 조회 가능
    if "admin" in user.get("metadata", {}).get("roles", []):
        return True

    # TODO: 데이터베이스에서 스레드 소유자 확인
    # 여기서는 간단히 True 반환
    return True

@auth.on.threads.update
async def authorize_thread_update(
    thread_id: str,
    metadata: dict,
    *,
    user: MinimalUserDict
) -> dict:
    """스레드 업데이트 권한 확인 및 메타데이터 주입"""
    # 관리자가 아니면 user_id 변경 불가
    if "admin" not in user.get("metadata", {}).get("roles", []):
        metadata.pop("user_id", None)
        metadata.pop("org_id", None)

    return {
        **metadata,
        "updated_by": user["display_name"],
        "updated_at": datetime.now().isoformat()
    }

@auth.on.runs.create
async def authorize_run_create(
    thread_id: str,
    *,
    user: MinimalUserDict
) -> bool:
    """실행 생성 권한 확인"""
    # 사용 량 제한 확인
    user_metadata = user.get("metadata", {})

    # 예: 프리미엄 사용자는 무제한, 무료 사용자는 일일 10회
    if "premium" in user_metadata.get("roles", []):
        return True

    # TODO: 데이터베이스에서 오늘의 실행 횟수 확인
    # 여기서는 간단히 True 반환
    return True

@auth.on.store.get
async def authorize_store_get(
    namespace: tuple[str, ...],
    key: str,
    *,
    user: MinimalUserDict
) -> bool:
    """Store 조회 권한 확인"""
    # 네임스페이스 첫 번째 요소가 사용자 ID인 경우만 허용
    if namespace and namespace[0] == user["identity"]:
        return True

    # 관리자는 모든 네임스페이스 조회 가능
    if "admin" in user.get("metadata", {}).get("roles", []):
        return True

    raise Auth.exceptions.HTTPException(
        status_code=403,
        detail="You don't have permission to access this namespace"
    )

@auth.on.store.put
async def authorize_store_put(
    namespace: tuple[str, ...],
    key: str,
    value: dict,
    *,
    user: MinimalUserDict
) -> dict:
    """Store 저장 권한 확인 및 메타데이터 주입"""
    # 네임스페이스 첫 번째 요소가 사용자 ID인 경우만 허용
    if not (namespace and namespace[0] == user["identity"]):
        if "admin" not in user.get("metadata", {}).get("roles", []):
            raise Auth.exceptions.HTTPException(
                status_code=403,
                detail="You can only write to your own namespace"
            )

    # 메타데이터 추가
    return {
        **value,
        "_metadata": {
            "created_by": user["identity"],
            "created_at": datetime.now().isoformat()
        }
    }
```

**설명:**
- `@auth.authenticate`: 모든 요청에 대해 실행되며, 사용자 인증을 수행합니다.
- `@auth.on.{resource}.{action}`: 특정 리소스/액션에 대한 권한을 확인합니다.
- JWT 토큰을 사용하여 사용자 정보(ID, 역할, 조직 등)를 전달합니다.
- 멀티테넌트 지원을 위해 `org_id`를 메타데이터에 포함시킵니다.

### 6.2 권한 설정

```python
# auth.py (계속) - 세밀한 권한 제어

from enum import Enum

class Permission(str, Enum):
    """권한 정의"""
    THREAD_CREATE = "thread:create"
    THREAD_READ = "thread:read"
    THREAD_UPDATE = "thread:update"
    THREAD_DELETE = "thread:delete"
    RUN_CREATE = "run:create"
    STORE_READ = "store:read"
    STORE_WRITE = "store:write"
    ADMIN = "admin"

class Role(str, Enum):
    """역할 정의"""
    ADMIN = "admin"
    PREMIUM_USER = "premium"
    FREE_USER = "free"
    GUEST = "guest"

# 역할별 권한 매핑
ROLE_PERMISSIONS = {
    Role.ADMIN: [perm for perm in Permission],  # 모든 권한
    Role.PREMIUM_USER: [
        Permission.THREAD_CREATE,
        Permission.THREAD_READ,
        Permission.THREAD_UPDATE,
        Permission.RUN_CREATE,
        Permission.STORE_READ,
        Permission.STORE_WRITE,
    ],
    Role.FREE_USER: [
        Permission.THREAD_CREATE,
        Permission.THREAD_READ,
        Permission.RUN_CREATE,
        Permission.STORE_READ,
    ],
    Role.GUEST: [
        Permission.THREAD_READ,
    ],
}

def has_permission(user: MinimalUserDict, permission: Permission) -> bool:
    """사용자가 특정 권한을 가지고 있는지 확인"""
    user_roles = user.get("metadata", {}).get("roles", [])

    for role in user_roles:
        if role in ROLE_PERMISSIONS:
            if permission in ROLE_PERMISSIONS[role]:
                return True

    return False

@auth.on.threads.delete
async def authorize_thread_delete(
    thread_id: str,
    *,
    user: MinimalUserDict
) -> bool:
    """스레드 삭제 권한 확인"""
    if not has_permission(user, Permission.THREAD_DELETE):
        raise Auth.exceptions.HTTPException(
            status_code=403,
            detail="You don't have permission to delete threads"
        )

    # TODO: 스레드 소유자 확인
    return True

@auth.on.assistants.read
async def authorize_assistant_read(
    assistant_id: str,
    *,
    user: MinimalUserDict
) -> bool:
    """어시스턴트 조회 권한 확인"""
    # 모든 인증된 사용자는 어시스턴트 조회 가능
    return user["is_authenticated"]

@auth.on.store.search
async def authorize_store_search(
    namespace_prefix: tuple[str, ...],
    *,
    user: MinimalUserDict
) -> bool:
    """Store 검색 권한 확인"""
    if not has_permission(user, Permission.STORE_READ):
        raise Auth.exceptions.HTTPException(
            status_code=403,
            detail="You don't have permission to search the store"
        )

    # 자신의 네임스페이스만 검색 가능 (관리자 제외)
    if namespace_prefix and namespace_prefix[0] != user["identity"]:
        if not has_permission(user, Permission.ADMIN):
            raise Auth.exceptions.HTTPException(
                status_code=403,
                detail="You can only search your own namespace"
            )

    return True
```

**설명:**
- `Permission` Enum으로 명확한 권한 정의를 제공합니다.
- `Role` Enum으로 역할을 정의하고, 역할별 권한을 매핑합니다.
- `has_permission()` 헬퍼 함수로 권한 확인을 단순화합니다.
- 각 리소스/액션마다 세밀한 권한 제어가 가능합니다.

### 6.3 멀티테넌트 구성

```python
# auth.py (계속) - 멀티테넌트 지원

@auth.on.threads.list
async def filter_threads_by_org(
    *,
    user: MinimalUserDict
) -> dict:
    """조직별로 스레드 목록 필터링"""
    user_metadata = user.get("metadata", {})
    org_id = user_metadata.get("org_id")

    if not org_id:
        # 조직이 없는 사용자는 자신의 스레드만 조회
        return {
            "filter": {
                "metadata.user_id": user["identity"]
            }
        }

    # 관리자는 조직 내 모든 스레드 조회 가능
    if has_permission(user, Permission.ADMIN):
        return {
            "filter": {
                "metadata.org_id": org_id
            }
        }

    # 일반 사용자는 자신의 스레드만
    return {
        "filter": {
            "metadata.user_id": user["identity"],
            "metadata.org_id": org_id
        }
    }

@auth.on.runs.list
async def filter_runs_by_org(
    thread_id: str,
    *,
    user: MinimalUserDict
) -> bool:
    """조직별로 실행 목록 필터링"""
    # TODO: thread_id의 소유 조직 확인
    # 여기서는 간단히 True 반환
    return True

# JWT 토큰 생성 헬퍼 (클라이언트/인증 서비스에서 사용)
def create_access_token(
    user_id: str,
    name: str,
    email: str,
    org_id: str,
    roles: list[str],
    expires_delta: timedelta = timedelta(hours=24)
) -> str:
    """JWT 액세스 토큰 생성"""
    expire = datetime.utcnow() + expires_delta

    payload = {
        "sub": user_id,
        "name": name,
        "email": email,
        "org_id": org_id,
        "roles": roles,
        "exp": expire,
        "iat": datetime.utcnow()
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

# 토큰 갱신
def refresh_access_token(refresh_token: str) -> str:
    """리프레시 토큰으로 새 액세스 토큰 생성"""
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])

        # 리프레시 토큰 검증
        if payload.get("type") != "refresh":
            raise Auth.exceptions.HTTPException(
                status_code=401,
                detail="Invalid refresh token"
            )

        # 새 액세스 토큰 생성
        return create_access_token(
            user_id=payload["sub"],
            name=payload["name"],
            email=payload["email"],
            org_id=payload["org_id"],
            roles=payload["roles"]
        )

    except jwt.InvalidTokenError:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token"
        )
```

**클라이언트 사용 예제:**
```python
# 토큰 생성 (인증 서비스)
from auth import create_access_token

token = create_access_token(
    user_id="user123",
    name="홍길동",
    email="hong@company.com",
    org_id="org456",
    roles=["premium"]
)

print(f"Access Token: {token}")

# 클라이언트에서 토큰 사용
async def call_api_with_auth(token: str):
    """인증 토큰을 사용하여 API 호출"""
    headers = {
        "Authorization": f"Bearer {token}"
    }

    async with httpx.AsyncClient() as client:
        # 스레드 생성
        response = await client.post(
            f"{BASE_URL}/threads",
            headers=headers,
            json={"metadata": {"project": "demo"}}
        )
        thread = response.json()
        print(f"스레드 생성: {thread['thread_id']}")

        # 실행 시작
        response = await client.post(
            f"{BASE_URL}/threads/{thread['thread_id']}/runs",
            headers=headers,
            json={
                "assistant_id": "react_agent",
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": "안녕하세요!"
                        }
                    ]
                }
            }
        )
        run = response.json()
        print(f"실행 시작: {run['run_id']}")

# 실행
asyncio.run(call_api_with_auth(token))
```

**환경 변수 설정:**
```bash
# .env 파일
AUTH_TYPE=custom  # 커스텀 인증 활성화
JWT_SECRET_KEY=your-super-secret-key-change-in-production
```

**주의사항:**
- JWT SECRET_KEY는 반드시 안전한 랜덤 문자열로 변경해야 합니다.
- 프로덕션 환경에서는 HTTPS를 사용하여 토큰을 안전하게 전송해야 합니다.
- 토큰 만료 시간을 적절히 설정하여 보안을 강화하세요.
- 리프레시 토큰을 별도로 관리하여 장기간 세션을 유지할 수 있습니다.
- 멀티테넌트 환경에서는 `org_id`를 일관되게 사용하여 데이터 격리를 보장해야 합니다.

---

## 마무리

이 가이드에서 다룬 실전 예제들은 Open LangGraph의 핵심 기능을 활용하는 방법을 보여줍니다:

1. **기본 에이전트 실행**: 스레드 생성부터 실행 완료까지의 전체 워크플로우
2. **HITL 에이전트**: 사용자 승인이 필요한 작업을 안전하게 처리
3. **SSE 스트리밍**: 실시간 응답으로 사용자 경험 개선
4. **커스텀 그래프**: 자신만의 에이전트 로직 구현
5. **Store 활용**: 장기 메모리와 지식 베이스 구축
6. **인증 커스터마이징**: 보안과 멀티테넌시 지원

각 예제는 실제 프로덕션 환경에서 바로 사용할 수 있도록 작성되었으며, 필요에 따라 확장하거나 수정할 수 있습니다.

추가 정보는 다음 문서를 참고하세요:
- [아키텍처 가이드](./architecture-ko.md)
- [API 레퍼런스](./api-reference-ko.md)
- [개발 가이드](./development-guide-ko.md)
