# AGENTS.md - `src/agent_server/api/` (HTTP Contract Layer)

This document keeps only MUST-KNOW guidance for `src/agent_server/api/`.
Long-form details are delegated to: `docs/agents_reference/api-layer.md`.

## Purpose
- Provide HTTP endpoints that conform to the Agent Protocol specification.
- Own request/response validation (Pydantic), auth/permission dependencies (Depends), service invocation, and SSE streaming endpoints.

## Non-Goals
- Business logic is owned by `src/agent_server/services/` (API delegates).
- DB sessions/RLS/serialization/SSE formatting are owned by `src/agent_server/core/`.

---

## Scope & Boundaries

### In scope (this layer owns)
- FastAPI router implementations (validation, response models, status codes)
- Authn/authz dependency application (`get_current_user`, RBAC-related Depends)
- Calling services and mapping results to Agent Protocol shapes
- SSE streaming endpoints (including `Last-Event-ID` reconnect)

### Boundary rules
- [MUST] Do not implement complex business logic inside API handlers → move to Services.
- [MUST] DB access must go through `Depends(get_session)` (or `get_session_with_rls` when required).

---

## MUST-KNOW (Invariants)

### Authentication / Authorization
- [MUST] Most protected endpoints use `Depends(get_current_user)`.
  - `get_current_user()` requires `request.user.is_authenticated == True`.
  - With `AUTH_TYPE=noop`, `is_authenticated=False` by default, so 401 may occur.
  - Sources: `auth.py`, `src/agent_server/core/auth_deps.py`
- [SHOULD] Multi-tenancy scope is `identity` (user_id) + optional `org_id`.
  - Missing filters can leak data.

### DB Session / Tenant Scoping
- [MUST] Most routers apply application-level `user_id`/`org_id` filtering.
  - Example pattern: runs `_build_*_access_filter()`
- [REF] To strengthen with Postgres RLS, consider `Depends(get_session_with_rls)`.
  - Sources: `src/agent_server/core/orm.py`, `src/agent_server/core/rls.py`

### Streaming (SSE)
- [MUST] SSE headers/format are owned by Core.
  - Headers: `src/agent_server/core/sse.py#get_sse_headers`
  - Event ID rule: `{run_id}_event_{seq}` (`src/agent_server/utils/sse_utils.py`)
- [MUST] Reconnect uses `Last-Event-ID` to replay from the event store.
  - Orchestration: `src/agent_server/services/streaming_service.py`
  - Storage: `src/agent_server/services/event_store.py`

### Error Format
- [MUST] Error responses must preserve the Agent Protocol standard shape.
  - Models/helpers: `src/agent_server/models/errors.py`
  - Global exception handling: `src/agent_server/main.py`

---

## What’s Here (Routers)
- `assistants.py`: assistants CRUD + schemas/graph structure
- `agents.py`: Agent Protocol "agents" endpoints (assistant alias/extension)
- `threads.py`: thread CRUD + state/history
- `runs.py`: run CRUD + stream/join/cancel + HITL resume
- `runs_standalone.py`: (enterprise/extension) standalone runs API
- `store.py`: LangGraph Store API (long-term memory) — namespace scoping is critical

Enterprise/Operations:
- `organizations.py`, `rbac.py`, `quotas.py`, `rate_limit_rules.py`
- `audit.py`, `feature_flags.py`, `crons.py`
- `agent_auth.py`: agent identity/credential management within an org

---

## Common Tasks

### 1) Add a new endpoint
1. Add/adjust request/response models in `src/agent_server/models/` (prefer spec-driven)
2. Add logic in `src/agent_server/services/`
3. Add a router in `src/agent_server/api/<router>.py` + Depends (auth/session)
4. Verify multi-tenancy filtering (`user_id`/`org_id`) is applied correctly
5. Add tests (see `tests/AGENTS.md`)

### 2) Debug SSE streaming issues
- Order: `api/runs.py` (headers/`Last-Event-ID`) → `services/streaming_service.py` → `services/event_store.py` → `services/broker.py`

---

## References
- Upstream (server-wide rules): `src/agent_server/AGENTS.md`
- Core (infrastructure): `src/agent_server/core/AGENTS.md`
- Services (business logic): `src/agent_server/services/AGENTS.md`
- Models (Pydantic contracts): `src/agent_server/models/AGENTS.md`
- (Reference) Legacy long-form doc: `docs/agents_reference/api-layer.md`
- Agent Protocol spec: `https://github.com/langchain-ai/agent-protocol`

## Keywords Router
- `get_current_user`, `AUTH_TYPE` → `src/agent_server/core/auth_deps.py`, `auth.py`
- `Last-Event-ID`, `replay`, `stream` → `src/agent_server/api/runs.py`, `src/agent_server/services/event_store.py`
- `store`, `namespace` → `src/agent_server/api/store.py`
- `org`, `rbac`, `quota` → `src/agent_server/api/organizations.py`, `src/agent_server/api/rbac.py`
