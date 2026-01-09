# (Reference) API Layer (`src/agent_server/api/`)

> This is a long-form reference companion to `src/agent_server/api/AGENTS.md`.
> Prefer the MUST-KNOW guide in `src/agent_server/api/AGENTS.md` when implementing changes.

## What this layer does

The API layer is the HTTP contract boundary:

- Implements Agent Protocol-compatible endpoints (FastAPI routers).
- Validates inputs and shapes outputs using Pydantic models.
- Applies authentication/authorization dependencies and tenant scoping.
- Delegates business logic to `src/agent_server/services/`.
- Provides SSE streaming endpoints (including reconnect/replay via `Last-Event-ID`).

## Router map (high-signal)

Core Agent Protocol resources:

- `assistants.py`: assistant CRUD + graph schemas/graph structure/subgraphs
- `threads.py`: thread CRUD + state/history
- `runs.py`: run CRUD + stream/join/cancel + HITL resume flows
- `store.py`: LangGraph Store API (long-term memory)

Aliases / extensions:

- `agents.py`: “agents” endpoints (often assistant aliases/compat)

Operational / enterprise surface:

- `organizations.py`, `rbac.py`, `quotas.py`
- `rate_limit_rules.py`
- `audit.py`
- `feature_flags.py`
- `crons.py`
- `agent_auth.py`
- `runs_standalone.py` (extended/standalone runs surface)

## Key patterns

### Dependency injection (FastAPI)

- Authentication: `Depends(get_current_user)` (or explicitly allow unauthenticated access)
- DB sessions: `Depends(get_session)` (or `get_session_with_rls` when strengthening isolation)
- Keep handlers thin: request parsing + dependency wiring + service calls only.

### Tenant scoping (avoid data leaks)

- Treat `identity` (user_id) + optional `org_id` as mandatory scoping signals.
- Never query metadata tables without tenant filters.
- Prefer shared helper/filter patterns over ad-hoc query assembly.

### Streaming (SSE)

- Streaming endpoints must use Core helpers for:
  - headers (`src/agent_server/core/sse.py`)
  - event formatting and IDs
- Reconnect/replay uses `Last-Event-ID` + persisted events (service layer).

Minimal example:

```bash
curl -N \\\n  -H 'Accept: text/event-stream' \\\n  -H 'Content-Type: application/json' \\\n  -d '{\"assistant_id\":\"...\",\"input\":{\"messages\":[{\"role\":\"user\",\"content\":\"hello\"}]}}' \\\n  http://localhost:8000/threads/<thread_id>/runs/stream
```

## Error handling

- Keep error shapes compatible with Agent Protocol.
- Most exception-to-response mapping is centralized (see `src/agent_server/main.py`).

## Debugging checklist

1. Confirm the router and request model match the SDK contract.
2. Confirm auth and tenant scoping dependencies are applied correctly.
3. Follow the call into the relevant service method.
4. Validate DB queries include `identity`/`org_id` filtering (or RLS context).
5. For SSE: confirm `Last-Event-ID` parsing and event replay behavior.

## References

- `src/agent_server/api/AGENTS.md`
- `src/agent_server/services/AGENTS.md`
- Agent Protocol spec: `https://github.com/langchain-ai/agent-protocol`

