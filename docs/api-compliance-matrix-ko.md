# OpenSource LangGraph Platform API 준수 매트릭스

> OpenSource LangGraph Platform 버전: v0.1.0
**SDK 버전:** langgraph-sdk 0.2.9

## 요약

이 문서는 OpenSource LangGraph Platform이 LangGraph Platform 공식 SDK의 API 스펙을 얼마나 준수하고 있는지 보여줍니다.

- **SDK 전체 메서드**: 37개
- **OpenSource LangGraph Platform 구현 엔드포인트**: 34개 / 39개
- **미구현**: 5개
- **준수율**: 87.2%

---

## Assistants

**SDK 클라이언트**: `AssistantsClient`

**SDK 메서드 (11개)**:

- `count()`
- `create()`
- `delete()`
- `get()`
- `get_graph()`
- `get_schemas()`
- `get_subgraphs()`
- `get_versions()`
- `search()`
- `set_latest()`
- `update()`

### OpenSource LangGraph Platform 구현 상태

| SDK 메서드 | HTTP Endpoint | OpenSource LangGraph Platform Handler | 상태 | 비고 |
|-----------|---------------|---------------|------|------|
| `create()` | `POST /assistants` | `create_assistant` | ✅ 구현 | - |
| `search()` | `GET /assistants` | `list_assistants` | ✅ 구현 | - |
| `search()` | `POST /assistants/search` | `search_assistants` | ✅ 구현 | - |
| `count()` | `POST /assistants/count` | `count_assistants` | ✅ 구현 | - |
| `get()` | `GET /assistants/{assistant_id}` | `get_assistant` | ✅ 구현 | - |
| `update()` | `PATCH /assistants/{assistant_id}` | `update_assistant` | ✅ 구현 | - |
| `delete()` | `DELETE /assistants/{assistant_id}` | `delete_assistant` | ✅ 구현 | - |
| `set_latest()` | `POST /assistants/{assistant_id}/latest` | `set_latest_version` | ✅ 구현 | - |
| `get_versions()` | `POST /assistants/{assistant_id}/versions` | `get_versions` | ✅ 구현 | - |
| `get_schemas()` | `GET /assistants/{assistant_id}/schemas` | `get_schemas` | ✅ 구현 | - |
| `get_graph()` | `GET /assistants/{assistant_id}/graph` | `get_graph` | ✅ 구현 | - |
| `get_subgraphs()` | `GET /assistants/{assistant_id}/subgraphs` | `get_subgraphs` | ✅ 구현 | - |

**구현률**: 12/12 (100.0%)

---

## Threads

**SDK 클라이언트**: `ThreadsClient`

**SDK 메서드 (11개)**:

- `copy()`
- `count()`
- `create()`
- `delete()`
- `get()`
- `get_history()`
- `get_state()`
- `join_stream()`
- `search()`
- `update()`
- `update_state()`

### OpenSource LangGraph Platform 구현 상태

| SDK 메서드 | HTTP Endpoint | OpenSource LangGraph Platform Handler | 상태 | 비고 |
|-----------|---------------|---------------|------|------|
| `create()` | `POST /threads` | `create_thread` | ✅ 구현 | - |
| `search()` | `GET /threads` | `list_threads` | ✅ 구현 | - |
| `get()` | `GET /threads/{thread_id}` | `get_thread` | ✅ 구현 | - |
| `get_state()` | `GET /threads/{thread_id}/state/{checkpoint_id}` | `get_state` | ✅ 구현 | - |
| `create (checkpoint)()` | `POST /threads/{thread_id}/state/checkpoint` | `create_checkpoint` | ✅ 구현 | - |
| `get_history()` | `POST /threads/{thread_id}/history` | `get_history_post` | ✅ 구현 | - |
| `get_history()` | `GET /threads/{thread_id}/history` | `get_history_get` | ✅ 구현 | - |
| `delete()` | `DELETE /threads/{thread_id}` | `delete_thread` | ✅ 구현 | - |
| `search()` | `POST /threads/search` | `search_threads` | ✅ 구현 | - |
| `update()` | `/threads/{thread_id} (PATCH)` | `update_thread` | ❌ 미구현 | SDK has update(), OpenSource LangGraph Platform missing |
| `copy()` | `/threads/{thread_id}/copy` | `copy_thread` | ❌ 미구현 | SDK has copy(), OpenSource LangGraph Platform missing |
| `count()` | `/threads/count` | `count_threads` | ❌ 미구현 | SDK has count(), OpenSource LangGraph Platform missing |

**구현률**: 9/12 (75.0%)

---

## Runs

**SDK 클라이언트**: `RunsClient`

**SDK 메서드 (10개)**:

- `cancel()`
- `create()`
- `create_batch()`
- `delete()`
- `get()`
- `join()`
- `join_stream()`
- `list()`
- `stream()`
- `wait()`

### OpenSource LangGraph Platform 구현 상태

| SDK 메서드 | HTTP Endpoint | OpenSource LangGraph Platform Handler | 상태 | 비고 |
|-----------|---------------|---------------|------|------|
| `create()` | `POST /threads/{thread_id}/runs` | `create_run` | ✅ 구현 | - |
| `stream()` | `POST /threads/{thread_id}/runs/stream` | `create_and_stream_run` | ✅ 구현 | - |
| `get()` | `GET /threads/{thread_id}/runs/{run_id}` | `get_run` | ✅ 구현 | - |
| `list()` | `GET /threads/{thread_id}/runs` | `list_runs` | ✅ 구현 | - |
| `wait()` | `PATCH /threads/{thread_id}/runs/{run_id}` | `update_run` | ✅ 구현 | - |
| `join()` | `GET /threads/{thread_id}/runs/{run_id}/join` | `join_run` | ✅ 구현 | - |
| `stream (reconnect)()` | `GET /threads/{thread_id}/runs/{run_id}/stream` | `stream_run_reconnect` | ✅ 구현 | - |
| `cancel()` | `POST /threads/{thread_id}/runs/{run_id}/cancel` | `cancel_run` | ✅ 구현 | - |
| `delete()` | `DELETE /threads/{thread_id}/runs/{run_id}` | `delete_run` | ✅ 구현 | - |
| `create_batch()` | `/runs/batch` | `create_batch` | ❌ 미구현 | SDK has create_batch(), OpenSource LangGraph Platform missing |

**구현률**: 9/10 (90.0%)

---

## Store

**SDK 클라이언트**: `StoreClient`

**SDK 메서드 (5개)**:

- `delete_item()`
- `get_item()`
- `list_namespaces()`
- `put_item()`
- `search_items()`

### OpenSource LangGraph Platform 구현 상태

| SDK 메서드 | HTTP Endpoint | OpenSource LangGraph Platform Handler | 상태 | 비고 |
|-----------|---------------|---------------|------|------|
| `put_item()` | `PUT /store/items` | `put_item` | ✅ 구현 | - |
| `get_item()` | `GET /store/items` | `get_item` | ✅ 구현 | - |
| `delete_item()` | `DELETE /store/items` | `delete_item` | ✅ 구현 | - |
| `search_items()` | `POST /store/items/search` | `search_items` | ✅ 구현 | - |
| `list_namespaces()` | `/store/namespaces` | `list_namespaces` | ❌ 미구현 | SDK has list_namespaces(), OpenSource LangGraph Platform missing |

**구현률**: 4/5 (80.0%)

---

## 미구현 기능 목록

다음 SDK 메서드는 OpenSource LangGraph Platform에 구현되지 않았습니다:

### Threads

- `update()` - SDK has update(), OpenSource LangGraph Platform missing
- `copy()` - SDK has copy(), OpenSource LangGraph Platform missing
- `count()` - SDK has count(), OpenSource LangGraph Platform missing

### Runs

- `create_batch()` - SDK has create_batch(), OpenSource LangGraph Platform missing

### Store

- `list_namespaces()` - SDK has list_namespaces(), OpenSource LangGraph Platform missing

## 구현 권장사항

### 우선순위 1 (필수)

- `ThreadsClient.update()` - 스레드 메타데이터 업데이트
- `StoreClient.list_namespaces()` - 네임스페이스 목록 조회

### 우선순위 2 (권장)

- `ThreadsClient.copy()` - 스레드 복사 기능
- `ThreadsClient.count()` - 스레드 개수 카운트
- `RunsClient.create_batch()` - 배치 실행 생성

### 우선순위 3 (선택)

- 추가 확장 기능은 사용자 피드백에 따라 구현
