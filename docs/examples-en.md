# Practical Examples Guide

This document provides practical examples for implementing various scenarios using Open LangGraph. Each example includes code, explanations, execution results, and important notes.

## Table of Contents

1. [Basic Agent Execution](#1-basic-agent-execution)
2. [Using a HITL Agent](#2-using-a-hitl-agent)
3. [SSE Streaming](#3-sse-streaming)
4. [Creating a Custom Graph](#4-creating-a-custom-graph)
5. [Utilizing the Store](#5-utilizing-the-store)
6. [Customizing Authentication](#6-customizing-authentication)

---

## 1. Basic Agent Execution

This is the most basic agent execution workflow. It covers creating a thread, selecting an assistant, and starting the execution.

### 1.1 Create a Thread

```python
import httpx

# API Endpoint
BASE_URL = "http://localhost:8000"

async def create_thread():
    """Creates a new conversation thread."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/threads",
            json={
                "metadata": {
                    "user_name": "John Doe",
                    "session_type": "demo"
                }
            }
        )
        thread = response.json()
        print(f"Thread created: {thread['thread_id']}")
        return thread["thread_id"]
```

**Explanation:**
- Call the `POST /threads` endpoint to create a new conversation thread.
- `metadata` is optional and can be used to store additional information about the thread.
- The returned `thread_id` is used in all subsequent conversations.

**Execution Result:**
```json
{
  "thread_id": "thread_abc123xyz",
  "created_at": 1698765432,
  "metadata": {
    "user_name": "John Doe",
    "session_type": "demo"
  }
}
```

**Notes:**
- Threads are stored permanently, so they may need to be cleaned up periodically during development.
- The `thread_id` is generated in UUID format and should be stored securely on the client side.

### 1.2 Select an Assistant

```python
async def list_assistants():
    """Retrieves a list of available assistants."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/assistants")
        assistants = response.json()

        print("Available Assistants:")
        for assistant in assistants:
            print(f"- {assistant['name']} (ID: {assistant['assistant_id']})")
            print(f"  Description: {assistant.get('description', 'N/A')}")

        return assistants

async def get_assistant(assistant_id: str):
    """Retrieves detailed information for a specific assistant."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/assistants/{assistant_id}")
        assistant = response.json()
        print(f"Assistant: {assistant['name']}")
        print(f"Graph ID: {assistant['graph_id']}")
        return assistant
```

**Explanation:**
- Use the `GET /assistants` endpoint to get a list of all assistants.
- Each assistant is linked to a specific graph and provides unique functionality.
- You can select a specific assistant using `assistant_id` or `graph_id`.

**Execution Result:**
```
Available Assistants:
- Weather Agent (ID: asst_weather_agent)
  Description: Provides weather information for any location
- ReAct Agent (ID: asst_react_agent)
  Description: General-purpose agent with tool calling capabilities
```

### 1.3 Start Execution and Check Results

```python
async def run_agent(thread_id: str, assistant_id: str, user_message: str):
    """Starts an agent execution and checks the results."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Create execution
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
        print(f"Execution started: {run_id}")

        # 2. Wait for execution to complete
        import asyncio
        while True:
            response = await client.get(
                f"{BASE_URL}/threads/{thread_id}/runs/{run_id}"
            )
            run_status = response.json()
            status = run_status["status"]
            print(f"Status: {status}")

            if status in ["success", "error", "interrupted"]:
                break

            await asyncio.sleep(1)

        # 3. Retrieve results
        if status == "success":
            print("\nResult:")
            for message in run_status.get("output", {}).get("messages", []):
                if message["role"] == "assistant":
                    print(f"Assistant: {message['content']}")

        return run_status

# Example usage
async def main():
    thread_id = await create_thread()
    assistants = await list_assistants()

    # Use weather_agent
    result = await run_agent(
        thread_id=thread_id,
        assistant_id="weather_agent",
        user_message="What's the weather in Seoul?"
    )

# Run
import asyncio
asyncio.run(main())
```

**Explanation:**
- Start the execution with `POST /threads/{thread_id}/runs`.
- Include the user message in `input.messages`.
- Since the execution is asynchronous, poll to check the status.
- After completion, you can get the agent's response from `output.messages`.

**Execution Result:**
```
Execution started: run_abc123xyz
Status: running
Status: running
Status: success

Result:
Assistant: The current weather in Seoul is clear, with a temperature of 15°C.
```

**Notes:**
- The polling interval is set to 1 second, but may need adjustment in a real production environment.
- A timeout setting should be used to prevent infinite waiting.
- The `interrupted` status is used by HITL agents (see next section).

---

## 2. Using a HITL Agent

A Human-in-the-Loop (HITL) agent can request user approval during execution. This allows for user confirmation before performing important tasks.

### 2.1 Handling Interrupts

```python
async def run_hitl_agent(thread_id: str, user_message: str):
    """Runs a HITL agent and handles interrupts."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Start execution
        response = await client.post(
            f"{BASE_URL}/threads/{thread_id}/runs",
            json={
                "assistant_id": "react_agent_hitl",  # HITL agent
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
        print(f"Execution started: {run_id}")

        # 2. Check status - wait for interrupt
        import asyncio
        while True:
            response = await client.get(
                f"{BASE_URL}/threads/{thread_id}/runs/{run_id}"
            )
            run_status = response.json()
            status = run_status["status"]

            if status == "interrupted":
                print("\nInterrupt occurred!")
                print(f"Approval request: {run_status.get('interrupt_info', {})}")
                break
            elif status in ["success", "error"]:
                print(f"Execution complete: {status}")
                return run_status

            await asyncio.sleep(1)

        return run_status

# Example usage
async def main():
    thread_id = await create_thread()

    result = await run_hitl_agent(
        thread_id=thread_id,
        user_message="Delete all files in the weather_app project"
    )

    print("\nTool call information:")
    print(result.get("interrupt_info"))

asyncio.run(main())
```

**Explanation:**
- A HITL agent switches to the `interrupted` state before performing risky operations (file deletion, API calls, etc.).
- `interrupt_info` contains detailed information about the task that requires approval.
- The user can approve, reject, or modify the task.

**Execution Result:**
```
Execution started: run_def456uvw

Interrupt occurred!
Approval request: {
  "tool_name": "delete_files",
  "arguments": {
    "path": "weather_app",
    "recursive": true
  },
  "reason": "User approval required for destructive operation"
}

Tool call information:
{
  "tool_name": "delete_files",
  "arguments": {...}
}
```

### 2.2 Approving/Modifying a Tool Call

```python
async def approve_tool_call(thread_id: str, run_id: str, approve: bool = True):
    """Approves a tool call."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Approve
        response = await client.post(
            f"{BASE_URL}/threads/{thread_id}/runs/{run_id}",
            json={
                "input": None,  # Approve without modification
                "command": "resume"
            }
        )
        print("Tool call approved.")
        return response.json()

async def modify_tool_call(thread_id: str, run_id: str, modified_args: dict):
    """Modifies the arguments of a tool call."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Resume with modified arguments
        response = await client.post(
            f"{BASE_URL}/threads/{thread_id}/runs/{run_id}",
            json={
                "input": modified_args,
                "command": "update"
            }
        )
        print("Tool call modified.")
        return response.json()

async def reject_tool_call(thread_id: str, run_id: str):
    """Rejects a tool call."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/threads/{thread_id}/runs/{run_id}",
            json={
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": "Cancel the task."
                        }
                    ]
                },
                "command": "resume"
            }
        )
        print("Tool call rejected.")
        return response.json()

# Example usage
async def main():
    thread_id = await create_thread()

    # Start HITL agent execution
    result = await run_hitl_agent(
        thread_id=thread_id,
        user_message="Delete all files in the weather_app project"
    )

    # On interrupt
    if result["status"] == "interrupted":
        # Option 1: Approve as is
        # await approve_tool_call(thread_id, result["run_id"])

        # Option 2: Modify arguments (delete only some files)
        await modify_tool_call(
            thread_id,
            result["run_id"],
            {
                "path": "weather_app/temp",  # Modify path
                "recursive": False
            }
        )

        # Option 3: Reject
        # await reject_tool_call(thread_id, result["run_id"])

asyncio.run(main())
```

**Explanation:**
- `command: "resume"` - Resumes execution (approval).
- `command: "update"` - Updates the state and resumes (modification).
- To reject, include a new user message in the `input`.

**Notes:**
- If not resumed after an interrupt, the execution remains in the `interrupted` state.
- You must use the same `thread_id` and `run_id` when resuming.
- LangGraph automatically saves the state at the time of interrupt, so it resumes from the exact point.

### 2.3 Resumed Execution

```python
async def wait_for_completion(thread_id: str, run_id: str):
    """Waits for the execution to complete."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        import asyncio

        while True:
            response = await client.get(
                f"{BASE_URL}/threads/{thread_id}/runs/{run_id}"
            )
            run_status = response.json()
            status = run_status["status"]

            print(f"Status: {status}")

            if status == "success":
                print("\nFinal Result:")
                for message in run_status.get("output", {}).get("messages", []):
                    if message["role"] == "assistant":
                        print(f"Assistant: {message['content']}")
                break
            elif status == "error":
                print(f"Error occurred: {run_status.get('error')}")
                break
            elif status == "interrupted":
                print("Still in interrupted state. Approval needed.")
                break

            await asyncio.sleep(1)

        return run_status

# Full workflow
async def full_hitl_workflow():
    thread_id = await create_thread()

    # 1. Start HITL execution
    result = await run_hitl_agent(
        thread_id=thread_id,
        user_message="Change the debug value in config.json to true"
    )

    # 2. Handle interrupt
    if result["status"] == "interrupted":
        print("\nWaiting for user approval...")

        # Simulate user input
        user_approval = input("Do you approve? (y/n): ")

        if user_approval.lower() == "y":
            await approve_tool_call(thread_id, result["run_id"])

            # 3. Wait for completion
            await wait_for_completion(thread_id, result["run_id"])
        else:
            await reject_tool_call(thread_id, result["run_id"])
            print("Task canceled.")

asyncio.run(full_hitl_workflow())
```

**Execution Result:**
```
Execution started: run_ghi789rst

Interrupt occurred!
Approval request: {
  "tool_name": "edit_file",
  "arguments": {
    "file": "config.json",
    "changes": {"debug": true}
  }
}

Waiting for user approval...
Do you approve? (y/n): y
Tool call approved.
Status: running
Status: success

Final Result:
Assistant: The debug value in config.json has been changed to true.
```

---

## 3. SSE Streaming

Using Server-Sent Events (SSE), you can stream the agent's execution process in real-time. This improves the user experience for long-running tasks.

### 3.1 Streaming Connection

```python
import httpx
import json

async def stream_agent_run(thread_id: str, assistant_id: str, user_message: str):
    """Streams an agent's execution."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Execute in streaming mode
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
            print("Streaming started...\n")

            async for line in response.aiter_lines():
                # SSE format: "data: {json}\n"
                if line.startswith("data: "):
                    data = line[6:]  # Remove "data: "

                    if data == "[DONE]":
                        print("\nStreaming complete")
                        break

                    try:
                        event = json.loads(data)
                        handle_stream_event(event)
                    except json.JSONDecodeError:
                        continue

def handle_stream_event(event: dict):
    """Handles a stream event."""
    event_type = event.get("event")

    if event_type == "metadata":
        print(f"[Metadata] Run ID: {event['data']['run_id']}")

    elif event_type == "messages/partial":
        # Message streaming
        for msg in event["data"]:
            if msg["role"] == "assistant":
                print(msg["content"], end="", flush=True)

    elif event_type == "messages/complete":
        print()  # Newline

    elif event_type == "agent":
        # Agent state change
        print(f"\n[Agent] {event['data'].get('action', 'processing')}")

    elif event_type == "tool":
        # Tool call
        tool_info = event["data"]
        print(f"\n[Tool Call] {tool_info.get('name')}")
        print(f"  Arguments: {tool_info.get('input')}")

    elif event_type == "error":
        print(f"\n[Error] {event['data'].get('message')}")

# Example usage
async def main():
    thread_id = await create_thread()

    await stream_agent_run(
        thread_id=thread_id,
        assistant_id="react_agent",
        user_message="Write a Python function to calculate the Fibonacci sequence"
    )

asyncio.run(main())
```

**Explanation:**
- Use the `/threads/{thread_id}/runs/stream` endpoint.
- SSE format is sent as `data: {json}\n`.
- Each event includes an `event` type and a `data` payload.
- The `[DONE]` message indicates the end of the stream.

**Execution Result:**
```
Streaming started...

[Metadata] Run ID: run_jkl012mno

[Agent] processing
I will write a function to calculate the Fibonacci sequence.

[Tool Call] python_repl
  Arguments: {'code': 'def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)'}

The function has been written. It's implemented recursively.

Streaming complete
```

### 3.2 Event Handling

```python
from typing import Callable, Dict
from enum import Enum

class EventType(str, Enum):
    """Stream event types"""
    METADATA = "metadata"
    MESSAGE_PARTIAL = "messages/partial"
    MESSAGE_COMPLETE = "messages/complete"
    AGENT = "agent"
    TOOL = "tool"
    ERROR = "error"
    INTERRUPT = "interrupt"

class StreamEventHandler:
    """Handler class for stream events"""

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
        """Routes an event to the appropriate handler."""
        event_type = event.get("event")
        handler = self.handlers.get(event_type)

        if handler:
            handler(event["data"])
        else:
            print(f"Unknown event: {event_type}")

    def on_metadata(self, data: dict):
        """Handles metadata events"""
        self.run_id = data.get("run_id")
        print(f"[Start] Run ID: {self.run_id}")
        print(f"Thread ID: {data.get('thread_id')}")

    def on_message_partial(self, data: list):
        """Handles partial message events (during streaming)"""
        for msg in data:
            if msg["role"] == "assistant":
                content = msg["content"]
                # Print only the difference from the previous buffer
                if content.startswith(self.message_buffer):
                    new_content = content[len(self.message_buffer):]
                    print(new_content, end="", flush=True)
                    self.message_buffer = content
                else:
                    print(content, end="", flush=True)
                    self.message_buffer = content

    def on_message_complete(self, data: list):
        """Handles complete message events"""
        print()  # Newline
        self.message_buffer = ""

    def on_agent(self, data: dict):
        """Handles agent state events"""
        action = data.get("action", "processing")
        print(f"\n[Agent] Status: {action}")

    def on_tool(self, data: dict):
        """Handles tool call events"""
        tool_name = data.get("name")
        tool_input = data.get("input")
        print(f"\n[Tool] Calling {tool_name}")
        print(f"  Input: {json.dumps(tool_input, ensure_ascii=False, indent=2)}")

    def on_error(self, data: dict):
        """Handles error events"""
        error_msg = data.get("message")
        print(f"\n[Error] {error_msg}")

    def on_interrupt(self, data: dict):
        """Handles interrupt events"""
        print(f"\n[Interrupt] User approval required")
        print(f"  Details: {json.dumps(data, ensure_ascii=False, indent=2)}")

async def stream_with_handler(thread_id: str, assistant_id: str, user_message: str):
    """Streams using a handler."""
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
                        print("\n\n[Complete] Streaming finished")
                        break

                    try:
                        event = json.loads(data)
                        handler.handle(event)
                    except json.JSONDecodeError:
                        continue

# Example usage
async def main():
    thread_id = await create_thread()

    await stream_with_handler(
        thread_id=thread_id,
        assistant_id="react_agent",
        user_message="Check the weather in Seoul and save the information to a JSON file"
    )

asyncio.run(main())
```

**Explanation:**
- The `StreamEventHandler` class provides dedicated handlers for each event type.
- `message_buffer` is used to prevent duplicate output.
- This extensible structure makes it easy to add new event types.

### 3.3 Handling Reconnections

```python
import asyncio
from datetime import datetime

class StreamReconnectHandler:
    """Class for handling stream reconnections"""

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
        """Streaming with reconnection logic"""
        retries = 0

        while retries <= self.max_retries:
            try:
                await self._stream_once(thread_id, run_id, on_event)
                # Normal completion
                break
            except (httpx.ReadTimeout, httpx.ConnectError) as e:
                retries += 1
                if retries > self.max_retries:
                    print(f"\n[Error] Max retries exceeded: {e}")
                    raise

                print(f"\n[Reconnect] Connection lost. Retrying in {self.retry_delay}s... ({retries}/{self.max_retries})")
                await asyncio.sleep(self.retry_delay)

    async def _stream_once(
        self,
        thread_id: str,
        run_id: str,
        on_event: Callable[[dict], None]
    ):
        """A single stream connection"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Resume from the last event
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

                            # Track event ID
                            if "id" in event:
                                self.last_event_id = event["id"]

                            on_event(event)
                        except json.JSONDecodeError:
                            continue

# Example usage
async def main():
    thread_id = await create_thread()

    # Start execution (non-streaming)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/threads/{thread_id}/runs",
            json={
                "assistant_id": "react_agent",
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": "Perform a complex data analysis"
                        }
                    ]
                }
            }
        )
        run = response.json()
        run_id = run["run_id"]

    # Stream with reconnect handler
    reconnect_handler = StreamReconnectHandler(max_retries=5, retry_delay=2.0)
    event_handler = StreamEventHandler()

    try:
        await reconnect_handler.stream_with_retry(
            thread_id=thread_id,
            run_id=run_id,
            on_event=event_handler.handle
        )
    except Exception as e:
        print(f"Streaming failed: {e}")

asyncio.run(main())
```

**Explanation:**
- Track `last_event_id` to prevent missing events on reconnection.
- Use the `?after={event_id}` query parameter to resume from a specific point.
- Adding exponential backoff can make reconnections more stable.

**Notes:**
- The event replay feature is valid for a limited time (default 1 hour).
- Adjust the number of retries and delay time for unstable network environments.
- It's good practice to display a "reconnecting" message in the UI.

---

## 4. Creating a Custom Graph

You can create your own agent graphs using LangGraph. This section shows how to create a simple translation agent.

### 4.1 Defining a StateGraph

```python
# graphs/translator_agent.py

from typing import TypedDict, Annotated
from operator import add
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

# 1. Define state
class TranslatorState(TypedDict):
    """State for the translation agent"""
    messages: Annotated[list[BaseMessage], add]
    source_language: str
    target_language: str
    translation: str

# 2. Create graph
workflow = StateGraph(TranslatorState)

# 3. Define nodes (implemented in the next section)
workflow.add_node("detect_language", detect_language_node)
workflow.add_node("translate", translate_node)
workflow.add_node("respond", respond_node)

# 4. Define edges
workflow.set_entry_point("detect_language")
workflow.add_edge("detect_language", "translate")
workflow.add_edge("translate", "respond")
workflow.add_edge("respond", END)

# 5. Compile
graph = workflow.compile()
```

**Explanation:**
- `StateGraph` defines a state-based graph.
- The state schema is defined with `TypedDict`.
- `Annotated[list, add]` indicates that the message list is cumulative.
- Nodes are functions that process the state, and edges define the execution flow.

### 4.2 Writing Nodes

```python
# graphs/translator_agent.py (continued)

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# Initialize LLM
llm = ChatOpenAI(model="gpt-4", temperature=0)

def detect_language_node(state: TranslatorState) -> TranslatorState:
    """Detects the language of the user's message."""
    messages = state["messages"]
    last_message = messages[-1]

    if isinstance(last_message, HumanMessage):
        user_text = last_message.content

        # Language detection prompt
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
    """Translates the text."""
    messages = state["messages"]
    last_message = messages[-1]
    source_lang = state.get("source_language", "Unknown")
    target_lang = state.get("target_language", "English")

    if isinstance(last_message, HumanMessage):
        user_text = last_message.content

        # Translation prompt
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
    """Adds the translation result as a response message."""
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

**Explanation:**
- Each node takes `state` as input and returns an updated `state`.
- `detect_language_node`: Detects the language using an LLM.
- `translate_node`: Performs the translation using an LLM.
- `respond_node`: Formats the translation result as a message.
- Use the spread operator (`**state`) to maintain the existing state when updating.

### 4.3 Utilizing Context

```python
# graphs/translator_agent.py (Context version)

from typing import Any
from langgraph.types import Runtime
from pydantic import BaseModel, Field

# 1. Define Context
class TranslatorContext(BaseModel):
    """Runtime context for the translation agent"""
    user_id: str = Field(description="User ID")
    target_language: str = Field(default="English", description="Target language")
    formality: str = Field(default="neutral", description="Translation tone (formal/neutral/casual)")
    model_name: str = Field(default="gpt-4", description="LLM model to use")

def detect_language_node_v2(
    state: TranslatorState,
    runtime: Runtime[TranslatorContext]
) -> TranslatorState:
    """Language detection node using Context"""
    # Access runtime context
    context = runtime.context
    model_name = context.model_name
    user_id = context.user_id
```
